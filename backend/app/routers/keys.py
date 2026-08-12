"""Schlüssel / Schließanlagen.

- KeyType: Lookup-Liste für den Schlüsseltyp (Winkhaus, Bartschlüssel, …).
- LockObject: Objekt/Schließanlage (frei benannt oder mit Standort/Fahrzeug verknüpft).
- Lock: einzelne Schließung (Tür/Schloss) innerhalb eines Objekts.
- KeyLock: welcher Schlüssel (Artikel) öffnet welche Schließung (n:m).
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    """Schnell-Umschalter am Lagerort: Ein -> legt (falls noch keiner da ist) einen
    ersten Schließzylinder an (Name = Lagerort); Aus -> entfernt alle Zylinder dieses
    Lagerorts. Für mehrere/benannte Zylinder siehe die Zylinder-Endpunkte."""
    node = db.query(models.StorageNode).get(node_id)
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
    node = db.query(models.StorageNode).get(node_id)
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
    lk = db.query(models.Lock).get(lock_id)
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
    lk = db.query(models.Lock).get(lock_id)
    if lk:
        node_id = lk.storage_node_id
        db.delete(lk)
        db.flush()
        if node_id:
            node = db.query(models.StorageNode).get(node_id)
            if node:
                _refresh_node_lock_flag(db, node)
        db.commit()
    return {"ok": True}


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
        a = db.query(models.Article).get(aid)
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
        objs = [db.query(models.LockObject).get(object_id)]
        if not objs[0]:
            raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    else:
        objs = db.query(models.LockObject).order_by(models.LockObject.name).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title="Schließplan")
    styles = getSampleStyleSheet()
    story = [Paragraph("Schließplan", styles["Title"]), Spacer(1, 6)]
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
            label = a.artikelnummer + (f" ({a.key_serial})" if a.key_serial else "")
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
    from .export import NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
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
            "holder": holder, "deposit_amount": deposit,
            "since": open_iss.issue_date.isoformat() if open_iss and open_iss.issue_date else None,
            "locks": a.locks,
        })
    return out
