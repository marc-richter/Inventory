"""Fahrzeug-Logbuch: automatische Einträge (aus erledigten Wartungen) und manuelle
Einträge; Ausgabe als PDF."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/logbook", tags=["logbook"])

KINDS = ("wartung", "fahrt", "schaden", "hinweis", "sonstiges")


def _uname(u):
    return (u.full_name or u.username) if u else None


def _out(e) -> schemas.LogEntryOut:
    return schemas.LogEntryOut(
        id=e.id, article_id=e.article_id, entry_date=e.entry_date, kind=e.kind,
        title=e.title or "", note=e.note or "", km=e.km, source=e.source or "manual",
        created_by_name=_uname(e.created_by))


def add_auto_entry(db, article_id, title, note="", km=None, when=None, kind="wartung"):
    """Automatischer Logbuch-Eintrag (z.B. nach erledigter Wartung). Best effort."""
    try:
        e = models.VehicleLogEntry(
            article_id=article_id, entry_date=when or dt.datetime.utcnow(), kind=kind,
            title=title or "", note=note or "", km=km, source="auto")
        db.add(e)
    except Exception:
        pass


@router.get("/{article_id}", response_model=list[schemas.LogEntryOut])
def list_entries(article_id: int, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    rows = db.query(models.VehicleLogEntry).filter(
        models.VehicleLogEntry.article_id == article_id).order_by(
        models.VehicleLogEntry.entry_date.desc(), models.VehicleLogEntry.id.desc()).all()
    return [_out(e) for e in rows]


@router.post("/{article_id}", response_model=schemas.LogEntryOut)
def create_entry(article_id: int, payload: schemas.LogEntryCreate, db: Session = Depends(get_db),
                 user=Depends(security.require_capability("maintenance"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    kind = payload.kind if payload.kind in KINDS else "hinweis"
    e = models.VehicleLogEntry(
        article_id=article_id, entry_date=payload.entry_date or dt.datetime.utcnow(),
        kind=kind, title=(payload.title or "").strip(), note=(payload.note or "").strip(),
        km=payload.km, source="manual", created_by_id=user.id)
    db.add(e)
    db.commit()
    db.refresh(e)
    log_action(db, user, "logbook_create", "article", article_id, {"entry_id": e.id})
    return _out(e)


@router.delete("/entry/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_capability("maintenance"))):
    e = db.query(models.VehicleLogEntry).get(entry_id)
    if not e:
        return {"ok": True}
    if e.created_by_id != user.id and "admin" not in (user.roles or []):
        raise HTTPException(status_code=403, detail="Nur der Ersteller oder ein Admin darf löschen")
    db.delete(e)
    db.commit()
    log_action(db, user, "logbook_delete", "article", e.article_id, {"entry_id": entry_id})
    return {"ok": True}


@router.get("/{article_id}/pdf")
def logbook_pdf(article_id: int, db: Session = Depends(get_db),
                user=Depends(security.get_current_user)):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    from .export import build_logbook_pdf
    pdf = build_logbook_pdf(db, a)
    name = (a.license_plate or a.artikelnummer or article_id)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Logbuch_{name}.pdf"'})
