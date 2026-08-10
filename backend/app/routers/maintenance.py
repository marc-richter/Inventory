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
