"""Schadens- und Verlustmeldungen.

Beim Anlegen einer Meldung passiert automatisch:
  - Statuswechsel des Artikels (Schaden → Reparatur, Verlust → verschollen),
  - eine Aufgabe im Eingang der zuständigen Materialverantwortlichen,
  - Erzeugung einer PDF-Meldung,
  - Telegram-Benachrichtigung der Verantwortlichen inkl. PDF-Dokument.
"""
import os
import uuid
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..config import DAMAGE_DIR

router = APIRouter(prefix="/api/reports", tags=["reports"])

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _uname(u):
    return (u.full_name or u.username) if u else None


def is_responsible(db, user, category_id):
    """Administrator oder Materialverwalter, dessen Zuständigkeit die Klasse abdeckt."""
    if "admin" in (user.roles or []):
        return True
    rows = db.query(models.MaterialManager).filter(models.MaterialManager.user_id == user.id).all()
    for r in rows:
        if r.category_id is None or r.category_id == category_id:
            return True
    return False


def _responsible_chat_ids(db, category_id):
    """Telegram-Chat-IDs der zuständigen Materialverantwortlichen (Admins + passende
    Materialverwalter), sofern verknüpft und freigeschaltet."""
    from .. import telegram
    out = set()
    users = db.query(models.User).filter(models.User.telegram_chat_id.isnot(None),
                                          models.User.active == True).all()  # noqa: E712
    mgr_uids = {m.user_id for m in db.query(models.MaterialManager).filter(
        (models.MaterialManager.category_id == category_id) | (models.MaterialManager.category_id.is_(None))).all()}
    for u in users:
        if "admin" in (u.roles or []) or u.id in mgr_uids:
            out.add(u.telegram_chat_id)
    return {c for c in out if telegram.is_allowed(db, c)}


def _compute_complete(r) -> bool:
    """Pflichtangaben: Datum/Uhrzeit des Vorfalls, Ort, Hergang (Beschreibung)."""
    return bool(r.incident_at and (r.incident_location or "").strip() and (r.description or "").strip())


def _out(r) -> schemas.DamageReportOut:
    a = r.article
    return schemas.DamageReportOut(
        id=r.id, article_id=r.article_id,
        artikelnummer=a.artikelnummer if a else None,
        type_name=a.type.name if (a and a.type) else None,
        kind=r.kind, reporter_name=_uname(r.reporter), description=r.description or "",
        incident_at=r.incident_at, incident_location=r.incident_location or "",
        is_theft=bool(r.is_theft), police_reference=r.police_reference or "",
        estimated_value=r.estimated_value or "", witnesses=r.witnesses or "",
        reporter_contact=r.reporter_contact or "", complete=bool(r.complete),
        has_photo=bool(r.photo_filename), status=r.status,
        handled_by_name=_uname(r.handled_by), handled_at=r.handled_at,
        resolution_note=r.resolution_note or "", created_at=r.created_at)


def _notify(db, rep):
    """Verantwortliche benachrichtigen (Telegram-Text + PDF-Dokument)."""
    try:
        from .. import telegram
        from .export import build_damage_report_pdf
        a = rep.article
        typ = a.type.name if (a and a.type) else ""
        kind_txt = "Schaden" if rep.kind == "damage" else "Verlust"
        incomplete = "" if rep.complete else " ⚠️ UNVOLLSTÄNDIG – bitte vervollständigen."
        text = (f"⚠️ {kind_txt} gemeldet: {a.artikelnummer if a else ''} {typ} "
                f"(von {_uname(rep.reporter) or '—'}). Neuer Status: "
                f"{'In Reparatur' if rep.kind == 'damage' else 'Verschollen'}.{incomplete}")
        telegram.notify_event(db, "damage_loss", text)
        token = telegram.token_of(db)
        if token and telegram.is_enabled(db):
            cat_id = a.category_id if a else None
            pdf = build_damage_report_pdf(db, rep)
            fname = f"{'Schadensmeldung' if rep.kind == 'damage' else 'Verlustmeldung'}_{a.artikelnummer if a else rep.id}.pdf"
            for cid in _responsible_chat_ids(db, cat_id):
                telegram.send_document(token, cid, fname, pdf, caption=text)
    except Exception:
        pass


@router.post("", response_model=schemas.DamageReportOut)
def create_report(payload: schemas.DamageReportCreate, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("report_damage"))):
    a = db.query(models.Article).get(payload.article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    kind = "loss" if payload.kind == "loss" else "damage"
    rep = models.DamageLossReport(
        article_id=a.id, kind=kind, reporter_user_id=user.id,
        description=(payload.description or "").strip(),
        incident_at=payload.incident_at, incident_location=(payload.incident_location or "").strip(),
        is_theft=bool(payload.is_theft) if kind == "loss" else False,
        police_reference=(payload.police_reference or "").strip(),
        estimated_value=(payload.estimated_value or "").strip(),
        witnesses=(payload.witnesses or "").strip(),
        reporter_contact=(payload.reporter_contact or "").strip(), status="open")
    rep.complete = _compute_complete(rep)
    # Automatischer Statuswechsel.
    if kind == "damage":
        a.status = "reparatur"
        if payload.description:
            a.repair_reason = payload.description.strip()
    else:
        a.status = "verschollen"
    db.add(rep)
    db.commit()
    db.refresh(rep)
    log_action(db, user, "damage_report_create", "article", a.id,
               {"kind": kind, "report_id": rep.id, "complete": rep.complete})
    _notify(db, rep)
    return _out(rep)


@router.put("/{report_id}", response_model=schemas.DamageReportOut)
def update_report(report_id: int, payload: schemas.DamageReportUpdate, db: Session = Depends(get_db),
                  user=Depends(security.get_current_user)):
    """Nachträgliches Ergänzen/Vervollständigen. Erlaubt für zuständige
    Materialverantwortliche sowie den Melder selbst (solange offen)."""
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    cat = rep.article.category_id if rep.article else None
    if not (is_responsible(db, user, cat) or (rep.reporter_user_id == user.id and rep.status == "open")):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Bearbeiten dieser Meldung")
    data = payload.dict(exclude_unset=True)
    for field in ("description", "incident_location", "police_reference", "estimated_value",
                  "witnesses", "reporter_contact"):
        if field in data and data[field] is not None:
            setattr(rep, field, str(data[field]).strip())
    if "incident_at" in data:
        rep.incident_at = data["incident_at"]
    if "is_theft" in data and data["is_theft"] is not None:
        rep.is_theft = bool(data["is_theft"])
    rep.complete = _compute_complete(rep)
    db.commit()
    db.refresh(rep)
    log_action(db, user, "damage_report_update", "damage_report", rep.id, {"complete": rep.complete})
    return _out(rep)


@router.post("/{report_id}/photo", response_model=schemas.DamageReportOut)
async def upload_photo(report_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                       user=Depends(security.require_capability("report_damage"))):
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 25 MB)")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in PHOTO_EXTS:
        ext = ".jpg"
    fname = f"dmg_{rep.id}_{uuid.uuid4().hex[:8]}{ext}"
    try:
        (DAMAGE_DIR / fname).write_bytes(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    rep.photo_filename = fname
    db.commit()
    db.refresh(rep)
    return _out(rep)


@router.get("", response_model=list[schemas.DamageReportOut])
def list_reports(mine: bool = False, inbox: bool = False, include_done: bool = False,
                 db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    q = db.query(models.DamageLossReport).order_by(models.DamageLossReport.created_at.desc())
    if mine:
        rows = q.filter(models.DamageLossReport.reporter_user_id == user.id).all()
    elif inbox:
        rows = [r for r in q.all()
                if is_responsible(db, user, r.article.category_id if r.article else None)]
        if not include_done:
            rows = [r for r in rows if r.status == "open"]
    else:
        rows = q.filter(models.DamageLossReport.reporter_user_id == user.id).all()
    return [_out(r) for r in rows]


@router.get("/inbox-count")
def inbox_count(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    open_reps = db.query(models.DamageLossReport).filter(models.DamageLossReport.status == "open").all()
    mine = [r for r in open_reps if is_responsible(db, user, r.article.category_id if r.article else None)]
    incomplete = sum(1 for r in mine if not r.complete)
    return {"count": len(mine), "incomplete": incomplete}


@router.post("/{report_id}/resolve", response_model=schemas.DamageReportOut)
def resolve(report_id: int, payload: schemas.DamageReportResolve, db: Session = Depends(get_db),
            user=Depends(security.get_current_user)):
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    if not is_responsible(db, user, rep.article.category_id if rep.article else None):
        raise HTTPException(status_code=403, detail="Nur zuständige Materialverantwortliche dürfen erledigen")
    rep.status = "done"
    rep.resolution_note = payload.resolution_note or ""
    rep.handled_by_user_id = user.id
    rep.handled_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(rep)
    log_action(db, user, "damage_report_resolve", "damage_report", rep.id)
    return _out(rep)


@router.get("/{report_id}/pdf")
def report_pdf(report_id: int, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Meldung nicht gefunden")
    from .export import build_damage_report_pdf
    pdf = build_damage_report_pdf(db, rep)
    art = rep.article.artikelnummer if rep.article else rep.id
    kind = "Schadensmeldung" if rep.kind == "damage" else "Verlustmeldung"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{kind}_{art}.pdf"'})


@router.get("/{report_id}/photo")
def report_photo(report_id: int, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep or not rep.photo_filename:
        raise HTTPException(status_code=404, detail="Kein Foto")
    path = DAMAGE_DIR / os.path.basename(rep.photo_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(path, filename=rep.photo_filename)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db),
                  user=Depends(security.get_current_user)):
    rep = db.query(models.DamageLossReport).get(report_id)
    if not rep:
        return {"ok": True}
    if rep.reporter_user_id != user.id and "admin" not in (user.roles or []):
        raise HTTPException(status_code=403, detail="Nur der Melder oder ein Admin darf löschen")
    db.delete(rep)
    db.commit()
    log_action(db, user, "damage_report_delete", "damage_report", report_id)
    return {"ok": True}
