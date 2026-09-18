"""Schlüssel / Schließanlagen.

- KeyType: Lookup-Liste für den Schlüsseltyp (Winkhaus, Bartschlüssel, …).
- LockObject: Objekt/Schließanlage (frei benannt oder mit Standort/Fahrzeug verknüpft).
- Lock: einzelne Schließung (Tür/Schloss) innerhalb eines Objekts.
- KeyLock: welcher Schlüssel (Artikel) öffnet welche Schließung (n:m).
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas, security
from app.database import get_db
from app.audit import log_action

router = APIRouter(prefix="/api/v1/keys", tags=["keys"])


# --------------------------- Lagerort-Schließungen --------------------------

def _traegt_schloesser(db, node) -> bool:
    """Ist dieser Knoten ein Artikel, der seine eigene Schließanlage bildet?

    Ein Fahrzeug ist beides: ein Lagerort im Baum UND ein Gegenstand mit eigenen
    Schlössern - Fahrertür, Heckklappe, Geräteräume. Die gehören zum Fahrzeug,
    nicht zum Standort, denn das Fahrzeug fährt weg und steht morgen woanders.
    """
    if node is None or not node.node_article_id:
        return False
    art = db.get(models.Article, node.node_article_id)
    kat = art.category if art is not None else None
    return bool(kat is not None and kat.effective_has_locks)


def _standort_root(db, node):
    """Findet die Wurzel der Schließanlage über dem gegebenen Lagerort-Knoten.

    Das ist der nächste Fahrzeug-/Behälterknoten mit eigenen Schlössern - und nur
    wenn keiner dazwischenliegt, der Standort ganz oben.
    """
    seen = set()
    cur = node
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        if _traegt_schloesser(db, cur):
            return cur
        if cur.level == "standort" or cur.parent_id is None:
            return cur
        cur = db.get(models.StorageNode, cur.parent_id)
    return node


def _knoten_name(db, node) -> str:
    """Anzeigename der Anlage: beim Fahrzeug das Kennzeichen, sonst der Knotenname."""
    if node.node_article_id:
        art = db.get(models.Article, node.node_article_id)
        if art is not None:
            return (art.license_plate or art.model or art.artikelnummer or node.name).strip()
    return node.name


def _artikel_name(db, article) -> str:
    return (article.license_plate or article.model
            or article.artikelnummer or f"Artikel {article.id}").strip()


def _anlagen_des_artikels(db, article_id, node_id=None):
    """Alle Schließanlagen, die zu diesem Artikel gehören - über die
    Artikel-Verknüpfung ODER über seinen Lagerort-Knoten."""
    bedingungen = [models.LockObject.vehicle_article_id == article_id]
    if node_id:
        bedingungen.append(models.LockObject.storage_node_id == node_id)
    return (db.query(models.LockObject).filter(or_(*bedingungen))
            .order_by(models.LockObject.id).all())


def _zusammenfuehren(db, objekte):
    """Mehrere Anlagen desselben Artikels auf eine zusammenziehen.

    Wie es dazu kam: ein Fahrzeug bekam erst Schlösser und wurde danach erst als
    Lagerort aktiviert. Die erste Anlage hing nur am Artikel, die zweite am
    neuen Knoten - fachlich dieselben Schlösser, technisch zwei Objekte. Im
    Schließplan standen dann zwei gleichnamige Anlagen, und die Karte am
    Fahrzeug zeigte nur die Hälfte.

    Die Schlösser wandern auf das älteste Objekt, der Rest verschwindet. Nichts
    geht verloren, und die Zuordnung der Schlüssel bleibt, weil sie am Schloss
    hängt und nicht an der Anlage.
    """
    behalten = objekte[0]
    for weiteres in objekte[1:]:
        db.query(models.Lock).filter(models.Lock.object_id == weiteres.id) \
            .update({models.Lock.object_id: behalten.id}, synchronize_session=False)
        if weiteres.storage_node_id and not behalten.storage_node_id:
            behalten.storage_node_id = weiteres.storage_node_id
        if weiteres.vehicle_article_id and not behalten.vehicle_article_id:
            behalten.vehicle_article_id = weiteres.vehicle_article_id
        if (weiteres.note or "").strip() and not (behalten.note or "").strip():
            behalten.note = weiteres.note
        db.flush()
        # Neu einlesen, sonst raeumt die Kaskade die eben umgehaengten
        # Schloesser mit weg - die Sitzung kennt sie noch am alten Objekt.
        db.refresh(weiteres)
        db.delete(weiteres)
    db.flush()
    return behalten


def artikel_objekt(db, article, anlegen: bool = True):
    """Die EINE Schließanlage eines Artikels - z.B. die Schlösser eines Fahrzeugs.

    Ein Artikel hat genau eine Anlage, egal auf welchem Weg man zu ihr kommt:
    über die Karte am Fahrzeug, über den Schließplan in den Einstellungen oder
    über ein als Schließung markiertes Fach im Fahrzeug. Für den Benutzer sind
    das dieselben Schlösser, also ist es auch dasselbe Objekt.

    Ist der Artikel zugleich ein Lagerort (Fahrzeug, Behälter), hängt die Anlage
    zusätzlich an seinem Knoten; die als Schließung markierten Fächer darunter
    gehören dann automatisch dazu. Ist er das nicht - ein Fahrzeug, das nur
    inventarisiert und nicht als Lagerort geführt wird - reicht die Verknüpfung
    über den Artikel allein. Wird er es später, übernimmt dieselbe Anlage den
    Knoten, statt dass eine zweite entsteht.
    """
    node = db.query(models.StorageNode).filter(
        models.StorageNode.node_article_id == article.id).first()
    node_id = node.id if node is not None else None
    objekte = _anlagen_des_artikels(db, article.id, node_id)
    if objekte:
        obj = _zusammenfuehren(db, objekte) if len(objekte) > 1 else objekte[0]
        if node_id and not obj.storage_node_id:
            obj.storage_node_id = node_id
        if not obj.vehicle_article_id:
            obj.vehicle_article_id = article.id
        name = _knoten_name(db, node) if node is not None else _artikel_name(db, article)
        if name and obj.name != name:
            obj.name = name
        return obj
    if not anlegen:
        return None
    obj = models.LockObject(
        name=_knoten_name(db, node) if node is not None else _artikel_name(db, article),
        storage_node_id=node_id, vehicle_article_id=article.id)
    db.add(obj)
    db.flush()
    return obj


def _ensure_standort_object(db, root):
    """Liefert das Schließanlagen-Objekt für einen Standort oder ein Fahrzeug
    (legt es bei Bedarf an).

    Verkörpert der Knoten einen Artikel, führt der Weg über `artikel_objekt` -
    dort wird sichergestellt, dass es bei diesem Artikel nur eine Anlage gibt.
    """
    if root.node_article_id:
        art = db.get(models.Article, root.node_article_id)
        if art is not None:
            return artikel_objekt(db, art)
    obj = db.query(models.LockObject).filter(models.LockObject.storage_node_id == root.id).first()
    name = _knoten_name(db, root)
    if not obj:
        obj = models.LockObject(name=name, storage_node_id=root.id)
        db.add(obj)
        db.flush()
    elif obj.name != name:
        obj.name = name
    return obj


INDEPENDENT_OBJECT_NAME = "Unabhängige Schließungen"


def independent_object(db):
    """Sammel-Objekt für unabhängige Schließungen (die nicht mehr an einem Lagerort
    hängen). Wird bei Bedarf angelegt."""
    obj = db.query(models.LockObject).filter(
        models.LockObject.storage_node_id.is_(None),
        models.LockObject.name == INDEPENDENT_OBJECT_NAME,
    ).first()
    if not obj:
        obj = models.LockObject(name=INDEPENDENT_OBJECT_NAME)
        db.add(obj)
        db.flush()
    return obj


def _refresh_node_lock_flag(db, node):
    """is_lock spiegelt, ob der Lagerort mindestens einen Zylinder hat."""
    cnt = db.query(models.Lock).filter(models.Lock.storage_node_id == node.id).count()
    node.is_lock = cnt > 0


# --------------------------- Schlüsseltyp (Lookup) --------------------------

@router.get("/types", response_model=list[schemas.KeyTypeOut])
def list_key_types(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.KeyType).filter(models.KeyType.active == True) \
        .order_by(models.KeyType.name).all()  # noqa: E712


@router.get("/types/check")
def check_key_type(name: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    exists = db.query(models.KeyType).filter(models.KeyType.name.ilike(name.strip())).first()
    return {"exists": bool(exists), "id": exists.id if exists else None}


@router.post("/types", response_model=schemas.KeyTypeOut)
def create_key_type(payload: schemas.KeyTypeCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("articles"))):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name erforderlich")
    existing = db.query(models.KeyType).filter(models.KeyType.name.ilike(name)).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
        return existing
    kt = models.KeyType(name=name)
    db.add(kt)
    db.commit()
    db.refresh(kt)
    log_action(db, user, "create_key_type", "key_type", kt.id, {"name": name})
    return kt


# --------------------------- Objekte / Schließungen -------------------------

@router.get("/objects", response_model=list[schemas.LockObjectOut])
def list_objects(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.LockObject).options(joinedload(models.LockObject.locks)) \
        .order_by(models.LockObject.name).all()


@router.post("/objects", response_model=schemas.LockObjectOut)
def create_object(payload: schemas.LockObjectCreate, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name erforderlich")
    o = models.LockObject(
        name=payload.name.strip(), storage_location_id=payload.storage_location_id,
        vehicle_article_id=payload.vehicle_article_id, note=payload.note or "",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    log_action(db, user, "create_lock_object", "lock_object", o.id, {"name": o.name})
    return o


@router.put("/objects/{object_id}", response_model=schemas.LockObjectOut)
def update_object(object_id: int, payload: schemas.LockObjectUpdate, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    o = db.get(models.LockObject, object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    db.refresh(o)
    return o


@router.delete("/objects/{object_id}")
def delete_object(object_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    o = db.get(models.LockObject, object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    db.delete(o)   # cascade entfernt Schließungen; KeyLock haengt an Lock (ondelete CASCADE)
    db.commit()
    log_action(db, user, "delete_lock_object", "lock_object", object_id)
    return {"ok": True}


@router.put("/nodes/{node_id}/lock")
def set_node_lock(node_id: int, payload: schemas.IssuableRequest, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    """Schnell-Umschalter am Lagerort: Ein -> legt (falls noch keiner da ist) einen
    ersten Schließzylinder an (Name = Lagerort); Aus -> entfernt alle Zylinder dieses
    Lagerorts. Für mehrere/benannte Zylinder siehe die Zylinder-Endpunkte."""
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    if payload.issuable:
        if db.query(models.Lock).filter(models.Lock.storage_node_id == node.id).count() == 0:
            obj = _ensure_standort_object(db, _standort_root(db, node))
            db.add(models.Lock(object_id=obj.id, name=node.name, storage_node_id=node.id))
    else:
        db.query(models.Lock).filter(models.Lock.storage_node_id == node.id).delete()
    _refresh_node_lock_flag(db, node)
    db.commit()
    log_action(db, user, "set_node_lock", "storage_node", node_id, {"is_lock": node.is_lock})
    return {"ok": True, "is_lock": node.is_lock}


@router.post("/nodes/{node_id}/cylinders", response_model=schemas.CylinderOut)
def add_node_cylinder(node_id: int, payload: schemas.CylinderCreate, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin", "verwalter"))):
    """Fügt einem Lagerort einen (weiteren) benannten Schließzylinder hinzu
    (z.B. Garage: 'Tor', 'Tür'). Beliebig viele möglich."""
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    obj = _ensure_standort_object(db, _standort_root(db, node))
    lk = models.Lock(object_id=obj.id, name=(payload.name.strip() or node.name),
                     note=payload.note or "", storage_node_id=node.id)
    db.add(lk)
    db.flush()
    _refresh_node_lock_flag(db, node)
    db.commit()
    db.refresh(lk)
    log_action(db, user, "add_cylinder", "storage_node", node_id, {"name": lk.name})
    return {"id": lk.id, "name": lk.name, "note": lk.note or ""}


@router.put("/cylinders/{lock_id}", response_model=schemas.CylinderOut)
def update_cylinder(lock_id: int, payload: schemas.CylinderCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin", "verwalter"))):
    """Benennt/beschreibt einen Schließzylinder (eines Lagerorts oder manuellen)."""
    lk = db.get(models.Lock, lock_id)
    if not lk:
        raise HTTPException(status_code=404, detail="Schließzylinder nicht gefunden")
    if payload.name.strip():
        lk.name = payload.name.strip()
    lk.note = payload.note or ""
    db.commit()
    return {"id": lk.id, "name": lk.name, "note": lk.note or ""}


@router.delete("/cylinders/{lock_id}")
def delete_cylinder(lock_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin", "verwalter"))):
    lk = db.get(models.Lock, lock_id)
    if lk:
        node_id = lk.storage_node_id
        db.delete(lk)
        db.flush()
        if node_id:
            node = db.get(models.StorageNode, node_id)
            if node:
                _refresh_node_lock_flag(db, node)
        db.commit()
    return {"ok": True}


@router.post("/standort/{node_id}/locks", response_model=schemas.LockOut)
def add_standort_lock(node_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin", "verwalter"))):
    """Fügt einem Standort eine manuelle Zusatz-Schließung hinzu (z.B. Außentor,
    Tresor), die nicht als eigener Lagerort existiert."""
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden")
    root = _standort_root(db, node)
    obj = _ensure_standort_object(db, root)
    lk = models.Lock(object_id=obj.id, name=payload.name.strip(), note=payload.note or "", sort_order=payload.sort_order)
    db.add(lk)
    db.commit()
    db.refresh(lk)
    return lk


# --------------------------- Schlösser eines Artikels -----------------------
#
# Ein Fahrzeug hat mehrere Schlösser: Fahrertür, Beifahrertür, Heckklappe,
# Geräteraum 1-4, Zündschloss, Tankdeckel. Alle zusammen bilden die Schließanlage
# des Fahrzeugs. Welcher Schlüssel welches davon öffnet, wird wie bei jeder
# anderen Schließung am Schlüssel hinterlegt.

def _schloesser_erlaubt(article) -> bool:
    kat = article.category if article is not None else None
    return bool(kat is not None and kat.effective_has_locks)


@router.get("/artikel/{article_id}/schloesser")
def article_locks(article_id: int, db: Session = Depends(get_db),
                  user=Depends(security.get_current_user)):
    """Die Schlösser eines Artikels (Fahrzeug, Behälter) samt den Schlüsseln,
    die sie öffnen."""
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    obj = artikel_objekt(db, a, anlegen=False)
    schloesser = []
    if obj is not None:
        locks = db.query(models.Lock).filter(models.Lock.object_id == obj.id) \
            .order_by(models.Lock.sort_order, models.Lock.name).all()
        for lk in locks:
            rows = db.query(models.KeyLock).filter(models.KeyLock.lock_id == lk.id).all()
            schluessel = []
            for r in rows:
                k = db.get(models.Article, r.article_id)
                if k is None:
                    continue
                schluessel.append({
                    "article_id": k.id, "artikelnummer": k.artikelnummer,
                    "key_alias": k.key_alias or "", "key_serial": k.key_serial or "",
                    "key_ring_name": k.key_ring.name if k.key_ring else "",
                })
            schluessel.sort(key=lambda x: x["artikelnummer"])
            schloesser.append({
                "id": lk.id, "name": lk.name, "note": lk.note or "",
                "sort_order": lk.sort_order or 100,
                # Vom Lagerort abgeleitet (Haekchen im Baum) - dort umbenennen,
                # nicht hier.
                "storage_node_id": lk.storage_node_id,
                "schluessel": schluessel,
            })
    return {
        "erlaubt": _schloesser_erlaubt(a),
        "object_id": obj.id if obj else None,
        "object_name": obj.name if obj else "",
        "schloesser": schloesser,
    }


@router.post("/artikel/{article_id}/schloesser", response_model=schemas.LockOut)
def add_article_lock(article_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    """Legt ein weiteres Schloss an diesem Artikel an - beliebig viele."""
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if not _schloesser_erlaubt(a):
        raise HTTPException(
            status_code=400,
            detail="Für die Materialklasse dieses Artikels sind keine Schlösser "
                   "vorgesehen. Das Kennzeichen „Schlösser\u201c lässt sich unter "
                   "Einstellungen › Stammdaten je Materialklasse setzen.")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name erforderlich")
    obj = artikel_objekt(db, a)
    lk = models.Lock(object_id=obj.id, name=name, note=payload.note or "",
                     sort_order=payload.sort_order)
    db.add(lk)
    db.commit()
    db.refresh(lk)
    log_action(db, user, "add_article_lock", "article", a.id, {"name": name})
    return lk


@router.post("/objects/{object_id}/locks", response_model=schemas.LockOut)
def add_lock(object_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
             user=Depends(security.require_roles("admin", "verwalter"))):
    o = db.get(models.LockObject, object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    lk = models.Lock(object_id=object_id, name=payload.name.strip(), note=payload.note or "",
                     sort_order=payload.sort_order)
    db.add(lk)
    db.commit()
    db.refresh(lk)
    return lk


@router.put("/locks/{lock_id}", response_model=schemas.LockOut)
def update_lock(lock_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    lk = db.get(models.Lock, lock_id)
    if not lk:
        raise HTTPException(status_code=404, detail="Schließung nicht gefunden")
    lk.name = payload.name.strip()
    lk.note = payload.note or ""
    lk.sort_order = payload.sort_order
    db.commit()
    db.refresh(lk)
    return lk


@router.delete("/locks/{lock_id}")
def delete_lock(lock_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    lk = db.get(models.Lock, lock_id)
    if lk:
        db.delete(lk)
        db.commit()
    return {"ok": True}


# --------------------------- Schlüssel ↔ Schließung -------------------------

@router.put("/article/{article_id}/locks")
def set_article_locks(article_id: int, payload: schemas.KeyLocksSet, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("articles"))):
    """Setzt die Schließungen, die dieser Schlüssel öffnet (komplette Liste)."""
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    requested = set(payload.lock_ids or [])
    valid = {row.id for row in db.query(models.Lock.id).filter(
        models.Lock.id.in_(requested or [-1])).all()}
    db.query(models.KeyLock).filter(models.KeyLock.article_id == article_id).delete()
    for lid in valid:
        db.add(models.KeyLock(article_id=article_id, lock_id=lid))
    db.commit()
    log_action(db, user, "set_key_locks", "article", article_id, {"lock_ids": sorted(valid)})
    return {"ok": True, "count": len(valid)}


@router.get("/lock/{lock_id}/keys")
def keys_for_lock(lock_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Rückansicht: welche Schlüssel öffnen diese Schließung und wer hat sie gerade?"""
    lk = db.get(models.Lock, lock_id)
    if not lk:
        raise HTTPException(status_code=404, detail="Schließung nicht gefunden")
    rows = db.query(models.KeyLock).filter(models.KeyLock.lock_id == lock_id).all()
    out = []
    for r in rows:
        a = db.get(models.Article, r.article_id)
        if not a:
            continue
        holder = None
        for iss in a.issues:
            if not iss.return_date:
                holder = (iss.person and f"{iss.person.first_name} {iss.person.last_name}".strip()) \
                    or iss.recipient_name_freetext or None
                break
        out.append({
            "article_id": a.id, "artikelnummer": a.artikelnummer,
            "key_serial": a.key_serial or "", "key_type_name": a.key_type_name,
            "key_alias": a.key_alias or "", "key_group": a.key_group or "",
            "key_ring_name": a.key_ring.name if a.key_ring else "",
            "status": a.status, "holder": holder,
        })
    out.sort(key=lambda x: x["artikelnummer"])
    return {"lock": {"id": lk.id, "name": lk.name, "object_id": lk.object_id,
                     "object_name": lk.object.name if lk.object else ""},
            "keys": out}


@router.get("/objects/{object_id}/matrix")
def object_matrix(object_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Schließplan-Matrix eines Objekts: Schließungen × Schlüssel (welcher Schlüssel
    öffnet welche Tür)."""
    o = db.get(models.LockObject, object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    locks = db.query(models.Lock).filter(models.Lock.object_id == object_id) \
        .order_by(models.Lock.sort_order, models.Lock.name).all()
    lock_ids = [lk.id for lk in locks]
    rows = db.query(models.KeyLock).filter(models.KeyLock.lock_id.in_(lock_ids or [-1])).all()
    # article_id -> set(lock_id)
    by_key = {}
    for r in rows:
        by_key.setdefault(r.article_id, set()).add(r.lock_id)
    keys = []
    for aid, lset in by_key.items():
        a = db.get(models.Article, aid)
        if not a:
            continue
        keys.append({
            "article_id": a.id, "artikelnummer": a.artikelnummer,
            "key_serial": a.key_serial or "", "key_type_name": a.key_type_name,
            "key_alias": a.key_alias or "", "key_group": a.key_group or "",
            "key_ring_name": a.key_ring.name if a.key_ring else "",
            "opens": sorted(lset),
        })
    keys.sort(key=lambda x: x["artikelnummer"])
    return {
        "object": {"id": o.id, "name": o.name},
        "locks": [{"id": lk.id, "name": lk.name} for lk in locks],
        "keys": keys,
    }


def _current_holder(a):
    for iss in a.issues:
        if not iss.return_date:
            return (iss.person and f"{iss.person.first_name} {iss.person.last_name}".strip()) \
                or iss.recipient_name_freetext or None
    return None


def _object_matrix_data(db, o):
    locks = db.query(models.Lock).filter(models.Lock.object_id == o.id) \
        .order_by(models.Lock.sort_order, models.Lock.name).all()
    lock_ids = [lk.id for lk in locks]
    rows = db.query(models.KeyLock).filter(models.KeyLock.lock_id.in_(lock_ids or [-1])).all()
    by_key = {}
    for r in rows:
        by_key.setdefault(r.article_id, set()).add(r.lock_id)
    keys = []
    for aid, lset in by_key.items():
        a = db.get(models.Article, aid)
        if a:
            keys.append((a, lset))
    keys.sort(key=lambda x: x[0].artikelnummer)
    return locks, keys


@router.get("/export/pdf")
def export_schliessplan_pdf(object_id: int = 0, with_holders: bool = False,
                            db: Session = Depends(get_db),
                            user=Depends(security.get_current_user)):
    """Schließplan als PDF (Schlüssel × Schließung je Objekt). Ohne object_id: alle
    Objekte; mit object_id: nur dieses Objekt."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    if object_id:
        objs = [db.get(models.LockObject, object_id)]
        if not objs[0]:
            raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    else:
        objs = db.query(models.LockObject).order_by(models.LockObject.name).all()

    from app import pdf_layout
    untertitel = objs[0].name if (object_id and objs and objs[0]) else "Alle Objekte"
    oben, unten, eigener_kopf, canvasmaker = pdf_layout.doc_setup(
        db, "schliessplan", "Schließplan", untertitel, 12, 12,
        dateiname="schliessplan.pdf", benutzer=getattr(user, "username", "") or "")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=oben, bottomMargin=unten, title="Schließplan")
    styles = getSampleStyleSheet()
    story = [Paragraph("Schließplan", styles["Title"]), Spacer(1, 6)] if eigener_kopf else []
    for o in objs:
        locks, keys = _object_matrix_data(db, o)
        story.append(Paragraph(o.name, styles["Heading2"]))
        if not locks:
            story.append(Paragraph("Keine Schließungen.", styles["Normal"]))
            story.append(Spacer(1, 8))
            continue
        header = ["Schlüssel \\ Schließung"] + [lk.name for lk in locks]
        if with_holders:
            header.append("Aktuell bei")
        data = [header]
        for a, lset in keys:
            # Nummer, danach - sofern vorhanden - der sprechende Name, die
            # Praegung und die Schliessgruppe. Die Nummer bleibt fuehrend.
            zusatz = [t for t in (a.key_alias, a.key_serial,
                                  f"Gruppe {a.key_group}" if a.key_group else "",
                                  f"Bund {a.key_ring.name}" if a.key_ring else "") if t]
            label = a.artikelnummer + (f" ({', '.join(zusatz)})" if zusatz else "")
            row = [label] + ["●" if lk.id in lset else "·" for lk in locks]
            if with_holders:
                row.append(_current_holder(a) or "–")
            data.append(row)
        if not keys:
            data.append(["(keine Schlüssel zugeordnet)"] + ["" for _ in locks] + (["" ] if with_holders else []))
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 12))
    doc.build(story, canvasmaker=canvasmaker)
    rohdaten = pdf_layout.finalize(db, "schliessplan", buf.getvalue())
    return StreamingResponse(io.BytesIO(rohdaten), media_type="application/pdf",
                             headers={"Content-Disposition": 'inline; filename="schliessplan.pdf"'})


# --------------------------- Ausgabeliste -----------------------------------

@router.get("/issued")
def issued_keys(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Alle aktuell ausgegebenen Schlüssel mit Halter, Objekt/Schließungen und
    Pfand – für die Schlüssel-Ausgabeliste."""
    key_cat_ids = [c.id for c in db.query(models.Category).filter(models.Category.key_system == True).all()]  # noqa: E712
    if not key_cat_ids:
        return []
    arts = db.query(models.Article).filter(
        models.Article.category_id.in_(key_cat_ids),
        models.Article.status == "ausgegeben",
    ).order_by(models.Article.artikelnummer).all()
    out = []
    for a in arts:
        open_iss = next((i for i in a.issues if not i.return_date), None)
        holder = None
        deposit = ""
        if open_iss:
            holder = (open_iss.person and f"{open_iss.person.first_name} {open_iss.person.last_name}".strip()) \
                or open_iss.recipient_name_freetext or None
            deposit = open_iss.deposit_amount or ""
        out.append({
            "article_id": a.id, "artikelnummer": a.artikelnummer,
            "key_type_name": a.key_type_name, "key_serial": a.key_serial or "",
            "key_alias": a.key_alias or "", "key_group": a.key_group or "",
            "key_ring_id": a.key_ring_id,
            "key_ring_name": a.key_ring.name if a.key_ring else "",
            "holder": holder, "deposit_amount": deposit,
            "since": open_iss.issue_date.isoformat() if open_iss and open_iss.issue_date else None,
            "locks": a.locks,
        })
    return out
