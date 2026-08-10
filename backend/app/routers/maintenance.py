"""Prüf-/Terminarten (Wartung) – Stammdaten.

Eine Prüfungsart (z.B. TÜV, Ölwechsel, Inspektion) ist eine wiederverwendbare
Vorlage mit optionaler Checkliste (Checkpunkte), Erfassungsfeldern (z.B. Öl-Typ),
Standard-Intervallen (Monate/km) und optionalem Ereignis-Auslöser. Arten können
archiviert (active=False) statt gelöscht werden.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

TRIGGER_EVENTS = ("", "return", "after_repair")


def _type_out(t) -> schemas.MaintenanceTypeOut:
    return schemas.MaintenanceTypeOut(
        id=t.id, name=t.name, description=t.description or "", active=bool(t.active),
        checklist_id=t.checklist_id, checklist_name=t.checklist.name if t.checklist else None,
        interval_months=t.interval_months, interval_km=t.interval_km, km_based=bool(t.km_based),
        trigger_event=t.trigger_event or "", sort_order=t.sort_order or 100,
        fields=[schemas.MaintenanceFieldOut(id=f.id, label=f.label, position=f.position) for f in t.fields])


def _set_fields(db, t, labels):
    """Erfassungsfelder ersetzen (Reihenfolge = Eingabereihenfolge)."""
    for f in list(t.fields):
        db.delete(f)
    for i, lbl in enumerate(labels or []):
        lbl = (lbl or "").strip()
        if lbl:
            db.add(models.MaintenanceField(type_id=t.id, label=lbl, position=i))


@router.get("/types", response_model=list[schemas.MaintenanceTypeOut])
def list_types(include_archived: bool = False, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    q = db.query(models.MaintenanceType)
    if not include_archived:
        q = q.filter(models.MaintenanceType.active == True)  # noqa: E712
    rows = q.order_by(models.MaintenanceType.sort_order, models.MaintenanceType.name).all()
    return [_type_out(t) for t in rows]


@router.post("/types", response_model=schemas.MaintenanceTypeOut)
def create_type(payload: schemas.MaintenanceTypeCreate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")
    trig = payload.trigger_event if payload.trigger_event in TRIGGER_EVENTS else ""
    t = models.MaintenanceType(
        name=name, description=payload.description or "", active=True,
        checklist_id=payload.checklist_id, interval_months=payload.interval_months,
        interval_km=payload.interval_km, km_based=bool(payload.km_based), trigger_event=trig)
    db.add(t)
    db.flush()
    _set_fields(db, t, payload.fields)
    db.commit()
    db.refresh(t)
    log_action(db, user, "maintenance_type_create", "maintenance_type", t.id, {"name": name})
    return _type_out(t)


@router.put("/types/{type_id}", response_model=schemas.MaintenanceTypeOut)
def update_type(type_id: int, payload: schemas.MaintenanceTypeUpdate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    t = db.query(models.MaintenanceType).get(type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Art nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name") is not None and data["name"].strip():
        t.name = data["name"].strip()
    for f in ("description", "checklist_id", "interval_months", "interval_km"):
        if f in data:
            setattr(t, f, data[f])
    if "active" in data and data["active"] is not None:
        t.active = bool(data["active"])
    if "km_based" in data and data["km_based"] is not None:
        t.km_based = bool(data["km_based"])
    if "trigger_event" in data and data["trigger_event"] is not None:
        t.trigger_event = data["trigger_event"] if data["trigger_event"] in TRIGGER_EVENTS else ""
    if "fields" in data and data["fields"] is not None:
        _set_fields(db, t, data["fields"])
    db.commit()
    db.refresh(t)
    log_action(db, user, "maintenance_type_update", "maintenance_type", t.id)
    return _type_out(t)


@router.delete("/types/{type_id}")
def delete_type(type_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    t = db.query(models.MaintenanceType).get(type_id)
    if not t:
        return {"ok": True}
    # Wird die Art noch von Artikeln genutzt, nicht löschen – nur archivieren.
    in_use = db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.type_id == type_id).count() if hasattr(models, "ArticleMaintenance") else 0
    if in_use:
        t.active = False
        db.commit()
        return {"ok": True, "archived": True}
    db.delete(t)
    db.commit()
    log_action(db, user, "maintenance_type_delete", "maintenance_type", type_id)
    return {"ok": True}


# --------------------- Zuweisung (Kategorie / Typ / Artikel) ------------------

def _asg_out(a) -> schemas.MaintenanceAssignmentOut:
    return schemas.MaintenanceAssignmentOut(
        id=a.id, mtype_id=a.mtype_id, mtype_name=a.mtype.name if a.mtype else None,
        category_id=a.category_id, article_type_id=a.article_type_id,
        article_id=a.article_id, mode=a.mode)


@router.get("/assignments", response_model=list[schemas.MaintenanceAssignmentOut])
def list_assignments(category_id: int = None, article_type_id: int = None, article_id: int = None,
                     db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    q = db.query(models.MaintenanceAssignment)
    if category_id:
        q = q.filter(models.MaintenanceAssignment.category_id == category_id)
    if article_type_id:
        q = q.filter(models.MaintenanceAssignment.article_type_id == article_type_id)
    if article_id:
        q = q.filter(models.MaintenanceAssignment.article_id == article_id)
    return [_asg_out(a) for a in q.all()]


@router.post("/assignments", response_model=schemas.MaintenanceAssignmentOut)
def create_assignment(payload: schemas.MaintenanceAssignmentCreate, db: Session = Depends(get_db),
                      user=Depends(security.get_current_user)):
    targets = [bool(payload.category_id), bool(payload.article_type_id), bool(payload.article_id)]
    if sum(targets) != 1:
        raise HTTPException(status_code=400, detail="Genau ein Ziel (Kategorie, Typ oder Artikel) angeben")
    if not db.query(models.MaintenanceType).get(payload.mtype_id):
        raise HTTPException(status_code=404, detail="Prüfart nicht gefunden")
    mode = "exclude" if payload.mode == "exclude" else "include"
    # Kategorie-/Typ-Zuweisungen sind Stammdaten (Admin/Verwalter); Artikel-Abweichungen
    # darf jeder mit dem Recht „maintenance".
    if payload.article_id:
        _require_maint(db, user)
        if mode == "exclude" and not db.query(models.Article).get(payload.article_id):
            raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    else:
        if not ({"admin", "verwalter"} & set(user.roles or [])):
            raise HTTPException(status_code=403, detail="Nur Admin/Verwalter dürfen Kategorie/Typ zuweisen")
        mode = "include"
    # Duplikate vermeiden
    existing = db.query(models.MaintenanceAssignment).filter(
        models.MaintenanceAssignment.mtype_id == payload.mtype_id,
        models.MaintenanceAssignment.category_id == payload.category_id,
        models.MaintenanceAssignment.article_type_id == payload.article_type_id,
        models.MaintenanceAssignment.article_id == payload.article_id).first()
    if existing:
        existing.mode = mode
        db.commit(); db.refresh(existing)
        return _asg_out(existing)
    a = models.MaintenanceAssignment(
        mtype_id=payload.mtype_id, category_id=payload.category_id,
        article_type_id=payload.article_type_id, article_id=payload.article_id, mode=mode)
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(db, user, "maintenance_assign", "maintenance_type", payload.mtype_id, _asg_out(a).model_dump())
    return _asg_out(a)


@router.delete("/assignments/{asg_id}")
def delete_assignment(asg_id: int, db: Session = Depends(get_db),
                      user=Depends(security.get_current_user)):
    a = db.query(models.MaintenanceAssignment).get(asg_id)
    if not a:
        return {"ok": True}
    if a.article_id:
        _require_maint(db, user)
    elif not ({"admin", "verwalter"} & set(user.roles or [])):
        raise HTTPException(status_code=403, detail="Nur Admin/Verwalter")
    db.delete(a)
    db.commit()
    return {"ok": True}


# --------------------- Auflösung + Termine je Artikel -------------------------

def _require_maint(db, user):
    from ..permissions import user_capabilities
    if "maintenance" not in user_capabilities(db, user):
        raise HTTPException(status_code=403, detail="Recht „Termine/Wartung pflegen“ erforderlich")


def _resolve(db, article):
    """Ermittelt die für einen Artikel geltenden Prüfarten aus Kategorie-/Typ-/Artikel-
    Zuweisungen (Artikel-Ausschluss hebt geerbte auf) und ergänzt den Termin-Stand."""
    # Kategorie des Artikels + ggf. Oberkategorie (Unterkategorie erbt Zuweisungen).
    cat_ids = {article.category_id}
    cat = article.category
    if cat is not None and cat.parent_id:
        cat_ids.add(cat.parent_id)
    asgs = db.query(models.MaintenanceAssignment).filter(
        (models.MaintenanceAssignment.category_id.in_(cat_ids)) |
        (models.MaintenanceAssignment.article_type_id == article.type_id) |
        (models.MaintenanceAssignment.article_id == article.id)).all()
    source = {}   # mtype_id -> Quelle (spezifischer gewinnt: article > type > category)
    excluded = set()
    for a in asgs:
        if a.article_id == article.id and a.mode == "exclude":
            excluded.add(a.mtype_id)
    for a in asgs:
        if a.mode != "include":
            continue
        if a.category_id in cat_ids:
            source.setdefault(a.mtype_id, "category")
    for a in asgs:
        if a.mode == "include" and a.article_type_id == article.type_id:
            source[a.mtype_id] = "type" if source.get(a.mtype_id) != "article" else "article"
    for a in asgs:
        if a.mode == "include" and a.article_id == article.id:
            source[a.mtype_id] = "article"
    mtype_ids = [k for k in source.keys() if k not in excluded]
    scheds = {s.mtype_id: s for s in db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.article_id == article.id).all()}
    out = []
    for mid in mtype_ids:
        t = db.query(models.MaintenanceType).get(mid)
        if not t or not t.active:
            continue
        s = scheds.get(mid)
        out.append(schemas.ArticleMaintOut(
            mtype_id=mid, mtype_name=t.name, source=source[mid],
            km_based=bool(t.km_based), interval_months=t.interval_months, interval_km=t.interval_km,
            schedule_id=s.id if s else None,
            due_date=s.due_date if s else None, due_km=s.due_km if s else None,
            last_done_at=s.last_done_at if s else None, last_done_km=s.last_done_km if s else None,
            note=(s.note if s else "") or ""))
    out.sort(key=lambda x: x.mtype_name.lower())
    return out


@router.get("/article/{article_id}", response_model=list[schemas.ArticleMaintOut])
def article_maintenance(article_id: int, db: Session = Depends(get_db),
                        user=Depends(security.get_current_user)):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return _resolve(db, a)


@router.post("/article/{article_id}/schedule", response_model=schemas.ArticleMaintOut)
def set_schedule(article_id: int, payload: schemas.ArticleMaintScheduleIn, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    _require_maint(db, user)
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    t = db.query(models.MaintenanceType).get(payload.mtype_id)
    if not t:
        raise HTTPException(status_code=404, detail="Prüfart nicht gefunden")
    s = db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.article_id == article_id,
        models.ArticleMaintenance.mtype_id == payload.mtype_id).first()
    if not s:
        s = models.ArticleMaintenance(article_id=article_id, mtype_id=payload.mtype_id)
        db.add(s)
    s.due_date = payload.due_date
    s.due_km = payload.due_km
    s.note = payload.note or ""
    db.commit()
    db.refresh(s)
    log_action(db, user, "maintenance_schedule", "article", article_id, {"mtype_id": payload.mtype_id})
    # aufgelösten Eintrag zurückgeben
    for item in _resolve(db, a):
        if item.mtype_id == payload.mtype_id:
            return item
    raise HTTPException(status_code=400, detail="Diese Prüfart gilt für den Artikel nicht")
