"""Schlüssel / Schließanlagen.

- KeyType: Lookup-Liste für den Schlüsseltyp (Winkhaus, Bartschlüssel, …).
- LockObject: Objekt/Schließanlage (frei benannt oder mit Standort/Fahrzeug verknüpft).
- Lock: einzelne Schließung (Tür/Schloss) innerhalb eines Objekts.
- KeyLock: welcher Schlüssel (Artikel) öffnet welche Schließung (n:m).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/keys", tags=["keys"])


# --------------------------- Lagerort-Schließungen --------------------------

def _standort_root(db, node):
    """Findet den Standort-Wurzelknoten über dem gegebenen Lagerort-Knoten."""
    seen = set()
    cur = node
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        if cur.level == "standort" or cur.parent_id is None:
            return cur
        cur = db.query(models.StorageNode).get(cur.parent_id)
    return node


def _ensure_standort_object(db, root):
    """Liefert das Schließanlagen-Objekt für einen Standort (legt es bei Bedarf an)."""
    obj = db.query(models.LockObject).filter(models.LockObject.storage_node_id == root.id).first()
    if not obj:
        obj = models.LockObject(name=root.name, storage_node_id=root.id)
        db.add(obj)
        db.flush()
    elif obj.name != root.name:
        obj.name = root.name
    return obj


def sync_node_lock(db, node):
    """Gleicht die abgeleitete Schließung eines Lagerort-Knotens mit dessen is_lock-
    Häkchen ab (anlegen/umbenennen/entfernen)."""
    existing = db.query(models.Lock).filter(models.Lock.storage_node_id == node.id).first()
    if node.is_lock:
        root = _standort_root(db, node)
        obj = _ensure_standort_object(db, root)
        if existing:
            existing.name = node.name
            existing.object_id = obj.id
        else:
            db.add(models.Lock(object_id=obj.id, name=node.name, storage_node_id=node.id))
    elif existing:
        db.delete(existing)   # KeyLock hängt per ondelete CASCADE dran


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
    o = db.query(models.LockObject).get(object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    db.refresh(o)
    return o


@router.delete("/objects/{object_id}")
def delete_object(object_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    o = db.query(models.LockObject).get(object_id)
    if not o:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    db.delete(o)   # cascade entfernt Schließungen; KeyLock haengt an Lock (ondelete CASCADE)
    db.commit()
    log_action(db, user, "delete_lock_object", "lock_object", object_id)
    return {"ok": True}


@router.put("/nodes/{node_id}/lock")
def set_node_lock(node_id: int, payload: schemas.IssuableRequest, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin", "verwalter"))):
    """Setzt/entfernt das Schließungs-Häkchen an einem Lagerort-Knoten. Der Knoten
    wird dadurch (als abgeleitete Schließung) in den Schließplan seines Standorts
    aufgenommen bzw. daraus entfernt."""
    node = db.query(models.StorageNode).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    node.is_lock = bool(payload.issuable)
    sync_node_lock(db, node)
    db.commit()
    log_action(db, user, "set_node_lock", "storage_node", node_id, {"is_lock": node.is_lock})
    return {"ok": True, "is_lock": node.is_lock}


@router.post("/standort/{node_id}/locks", response_model=schemas.LockOut)
def add_standort_lock(node_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin", "verwalter"))):
    """Fügt einem Standort eine manuelle Zusatz-Schließung hinzu (z.B. Außentor,
    Tresor), die nicht als eigener Lagerort existiert."""
    node = db.query(models.StorageNode).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden")
    root = _standort_root(db, node)
    obj = _ensure_standort_object(db, root)
    lk = models.Lock(object_id=obj.id, name=payload.name.strip(), note=payload.note or "", sort_order=payload.sort_order)
    db.add(lk)
    db.commit()
    db.refresh(lk)
    return lk


@router.post("/objects/{object_id}/locks", response_model=schemas.LockOut)
def add_lock(object_id: int, payload: schemas.LockCreate, db: Session = Depends(get_db),
             user=Depends(security.require_roles("admin", "verwalter"))):
    o = db.query(models.LockObject).get(object_id)
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
    lk = db.query(models.Lock).get(lock_id)
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
    lk = db.query(models.Lock).get(lock_id)
    if lk:
        db.delete(lk)
        db.commit()
    return {"ok": True}


# --------------------------- Schlüssel ↔ Schließung -------------------------

@router.put("/article/{article_id}/locks")
def set_article_locks(article_id: int, payload: schemas.KeyLocksSet, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("articles"))):
    """Setzt die Schließungen, die dieser Schlüssel öffnet (komplette Liste)."""
    a = db.query(models.Article).get(article_id)
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
    lk = db.query(models.Lock).get(lock_id)
    if not lk:
        raise HTTPException(status_code=404, detail="Schließung nicht gefunden")
    rows = db.query(models.KeyLock).filter(models.KeyLock.lock_id == lock_id).all()
    out = []
    for r in rows:
        a = db.query(models.Article).get(r.article_id)
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
    o = db.query(models.LockObject).get(object_id)
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
        a = db.query(models.Article).get(aid)
        if not a:
            continue
        keys.append({
            "article_id": a.id, "artikelnummer": a.artikelnummer,
            "key_serial": a.key_serial or "", "key_type_name": a.key_type_name,
            "opens": sorted(lset),
        })
    keys.sort(key=lambda x: x["artikelnummer"])
    return {
        "object": {"id": o.id, "name": o.name},
        "locks": [{"id": lk.id, "name": lk.name} for lk in locks],
        "keys": keys,
    }


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
            "holder": holder, "deposit_amount": deposit,
            "since": open_iss.issue_date.isoformat() if open_iss and open_iss.issue_date else None,
            "locks": a.locks,
        })
    return out
