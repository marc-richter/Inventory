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


def _reminders_of(db, type_id):
    return db.query(models.MaintenanceReminder).filter(
        models.MaintenanceReminder.type_id == type_id).order_by(
        models.MaintenanceReminder.days_before.desc()).all()


def _type_out(t, db=None) -> schemas.MaintenanceTypeOut:
    rems = _reminders_of(db, t.id) if db is not None else []
    return schemas.MaintenanceTypeOut(
        id=t.id, name=t.name, description=t.description or "", active=bool(t.active),
        checklist_id=t.checklist_id, checklist_name=t.checklist.name if t.checklist else None,
        interval_months=t.interval_months, interval_km=t.interval_km, km_based=bool(t.km_based),
        trigger_event=t.trigger_event or "", sort_order=t.sort_order or 100,
        fields=[schemas.MaintenanceFieldOut(id=f.id, label=f.label, position=f.position) for f in t.fields],
        reminders=[schemas.MaintReminderOut(id=r.id, days_before=r.days_before, urgency=r.urgency or "normal") for r in rems])


def _set_reminders(db, type_id, rems):
    for r in db.query(models.MaintenanceReminder).filter(models.MaintenanceReminder.type_id == type_id).all():
        db.delete(r)
    for r in rems or []:
        days = max(0, int(getattr(r, "days_before", 0) or 0))
        urg = r.urgency if getattr(r, "urgency", "normal") in ("low", "normal", "high") else "normal"
        db.add(models.MaintenanceReminder(type_id=type_id, days_before=days, urgency=urg))


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
    return [_type_out(t, db) for t in rows]


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
    _set_reminders(db, t.id, payload.reminders)
    db.commit()
    db.refresh(t)
    log_action(db, user, "maintenance_type_create", "maintenance_type", t.id, {"name": name})
    return _type_out(t, db)


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
    if "reminders" in data and data["reminders"] is not None:
        _set_reminders(db, t.id, payload.reminders)
    db.commit()
    db.refresh(t)
    log_action(db, user, "maintenance_type_update", "maintenance_type", t.id)
    return _type_out(t, db)


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
    s.reminded = []   # neuer Termin -> Erinnerungen erneut zulassen
    db.commit()
    db.refresh(s)
    log_action(db, user, "maintenance_schedule", "article", article_id, {"mtype_id": payload.mtype_id})
    # aufgelösten Eintrag zurückgeben
    for item in _resolve(db, a):
        if item.mtype_id == payload.mtype_id:
            return item
    raise HTTPException(status_code=400, detail="Diese Prüfart gilt für den Artikel nicht")


# --------------------- Fällige/anstehende Termine -----------------------------

def _due_list(db, user, within_days):
    """Anstehende (<= within_days) und überfällige Termine im Zuständigkeitsbereich."""
    from .requests import is_responsible
    now = dt.datetime.utcnow()
    limit = now + dt.timedelta(days=within_days)
    rows = db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.active == True,               # noqa: E712
        models.ArticleMaintenance.due_date.isnot(None),
        models.ArticleMaintenance.due_date <= limit).all()
    out = []
    for am in rows:
        a = db.query(models.Article).get(am.article_id)
        if not a:
            continue
        if not is_responsible(db, user, a.category_id):
            continue
        t = db.query(models.MaintenanceType).get(am.mtype_id)
        days = (am.due_date - now).days
        out.append(schemas.MaintDueOut(
            schedule_id=am.id, article_id=a.id, artikelnummer=a.artikelnummer,
            mtype_name=t.name if t else "", due_date=am.due_date, due_km=am.due_km,
            overdue=am.due_date < now, days_until=days))
    out.sort(key=lambda x: (x.due_date or now))
    return out


@router.get("/due", response_model=list[schemas.MaintDueOut])
def due(within_days: int = 30, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return _due_list(db, user, within_days)


@router.get("/due-count")
def due_count(within_days: int = 30, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    items = _due_list(db, user, within_days)
    return {"count": len(items), "overdue": sum(1 for i in items if i.overdue)}


# --------------------- Durchführen / Abhaken (reuse Prüfvorgang) --------------

def _add_months(base, months):
    import calendar
    m = base.month - 1 + int(months)
    y = base.year + m // 12
    m = m % 12 + 1
    d = min(base.day, calendar.monthrange(y, m)[1])
    return base.replace(year=y, month=m, day=d)


def _ensure_am(db, article_id, mtype_id):
    am = db.query(models.ArticleMaintenance).filter(
        models.ArticleMaintenance.article_id == article_id,
        models.ArticleMaintenance.mtype_id == mtype_id).first()
    if not am:
        am = models.ArticleMaintenance(article_id=article_id, mtype_id=mtype_id)
        db.add(am)
        db.flush()
    return am


@router.post("/article/{article_id}/perform")
def perform(article_id: int, payload: schemas.ArticleMaintScheduleIn, db: Session = Depends(get_db),
            user=Depends(security.get_current_user)):
    """Startet das Abhaken einer Prüf-/Terminart – auch vorzeitig. Legt einen
    Prüfvorgang (Inspection) mit der Checkliste der Art an und liefert ihn samt der
    zu erfassenden Felder zurück."""
    _require_maint(db, user)
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    t = db.query(models.MaintenanceType).get(payload.mtype_id)
    if not t:
        raise HTTPException(status_code=404, detail="Prüfart nicht gefunden")
    am = _ensure_am(db, article_id, payload.mtype_id)
    cl = db.query(models.InspectionChecklist).get(t.checklist_id) if t.checklist_id else None
    # Bereits laufenden Vorgang wiederverwenden
    insp = db.query(models.Inspection).filter(
        models.Inspection.maintenance_id == am.id, models.Inspection.status != "done").first()
    if not insp:
        insp = models.Inspection(article_id=article_id, checklist_id=cl.id if cl else None,
                                 checklist_name=t.name, status="open", maintenance_id=am.id,
                                 field_values={}, started_by_id=user.id)
        db.add(insp)
        db.flush()
        if cl:
            for it in cl.items:
                db.add(models.InspectionItemResult(inspection_id=insp.id, position=it.position, label=it.label))
    db.commit()
    db.refresh(insp)
    log_action(db, user, "maintenance_perform_start", "article", article_id, {"mtype_id": t.id, "inspection_id": insp.id})
    from .inspection_router import _insp_out
    return {"inspection": _insp_out(insp).model_dump(),
            "fields": [f.label for f in t.fields], "km_based": bool(t.km_based)}


@router.post("/perform/{insp_id}/finish", response_model=schemas.ArticleMaintOut)
def perform_finish(insp_id: int, payload: schemas.MaintenanceFinishIn, db: Session = Depends(get_db),
                   user=Depends(security.get_current_user)):
    _require_maint(db, user)
    insp = db.query(models.Inspection).get(insp_id)
    if not insp or not insp.maintenance_id:
        raise HTTPException(status_code=404, detail="Wartungs-Vorgang nicht gefunden")
    am = db.query(models.ArticleMaintenance).get(insp.maintenance_id)
    t = db.query(models.MaintenanceType).get(am.mtype_id) if am else None
    if insp.status != "done":
        insp.result = "failed" if payload.result == "failed" else "passed"
        insp.overall_note = payload.overall_note or ""
        insp.field_values = payload.field_values or {}
        insp.status = "done"
        insp.finished_by_id = user.id
        insp.finished_at = dt.datetime.utcnow()
    done_at = payload.done_date or dt.datetime.utcnow()
    if am:
        am.last_done_at = done_at
        if payload.done_km is not None:
            am.last_done_km = payload.done_km
        # Folgetermin bestimmen
        if payload.reschedule == "keep":
            pass
        elif payload.reschedule == "none":
            am.due_date = None
            am.due_km = None
            am.reminded = []
        elif payload.reschedule == "date":
            am.due_date = payload.next_due_date
            am.due_km = payload.next_due_km
            am.reminded = []
        else:  # interval
            if t and t.interval_months:
                am.due_date = _add_months(done_at, t.interval_months)
            if t and t.km_based and t.interval_km and payload.done_km is not None:
                am.due_km = int(payload.done_km) + int(t.interval_km)
            am.reminded = []
    db.commit()
    log_action(db, user, "maintenance_perform_finish", "article", insp.article_id,
               {"inspection_id": insp.id, "result": insp.result})
    a = db.query(models.Article).get(insp.article_id)
    for item in _resolve(db, a):
        if item.mtype_id == am.mtype_id:
            return item
    # Fallback (falls die Art am Artikel inzwischen ausgeschlossen ist)
    return schemas.ArticleMaintOut(
        mtype_id=am.mtype_id, mtype_name=t.name if t else "", source="article",
        km_based=bool(t.km_based) if t else False,
        interval_months=t.interval_months if t else None, interval_km=t.interval_km if t else None,
        schedule_id=am.id, due_date=am.due_date, due_km=am.due_km,
        last_done_at=am.last_done_at, last_done_km=am.last_done_km, note=am.note or "")
