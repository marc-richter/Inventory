import os
import uuid
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..permissions import user_capabilities
from ..config import RECEIPTS_DIR

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


def _user_name(u):
    return (u.full_name or u.username) if u else None


def _person_name(p):
    return f"{p.first_name} {p.last_name}".strip() if p else None


def _row(a):
    return {"artikelnummer": a.artikelnummer, "typ": a.type.name if a.type else "", "size": a.size or ""}


def _rows_for(db: Session, person_id: int, kind: str):
    """(received, remaining): Ausgabe -> aktuelle Bestände / keine; Rückgabe -> heute
    zurückgegebene / weiterhin verbleibende Artikel."""
    open_issues = db.query(models.IssueRecord).filter(
        models.IssueRecord.person_id == person_id,
        models.IssueRecord.return_date.is_(None)).all()
    open_rows = [_row(i.article) for i in open_issues if i.article]
    if kind == "return":
        start = dt.datetime.combine(dt.date.today(), dt.time.min)
        returned = db.query(models.IssueRecord).filter(
            models.IssueRecord.person_id == person_id,
            models.IssueRecord.return_date.isnot(None),
            models.IssueRecord.return_date >= start).all()
        returned_rows = [_row(i.article) for i in returned if i.article]
        return returned_rows, open_rows
    return open_rows, []


def _build(db, person, kind, issuer_name, copies, sig_issuer=None, sig_recipient=None) -> bytes:
    received, remaining = _rows_for(db, person.id, kind)
    from .export import build_receipt_pdf
    return build_receipt_pdf(db, person, kind, received, remaining, issuer_name, copies,
                             sig_issuer=sig_issuer, sig_recipient=sig_recipient)


@router.get("/generate")
def generate(person_id: int, kind: str = "issue", copies: int = 1, db: Session = Depends(get_db),
             user=Depends(security.require_capability("issues"))):
    """Unsignierte Quittung als PDF zum Ausdrucken/Unterschreiben."""
    person = db.query(models.Person).get(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    kind = "return" if kind == "return" else "issue"
    pdf = _build(db, person, kind, _user_name(user), copies)
    safe = "".join(c if c.isalnum() else "_" for c in _person_name(person))[:40]
    fname = f"{'Rueckgabe' if kind == 'return' else 'Ausgabe'}quittung_{safe}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/digital", response_model=schemas.ReceiptOut)
def digital(payload: schemas.ReceiptDigital, db: Session = Depends(get_db),
            user=Depends(security.require_capability("issues"))):
    """Digital unterschriebene Quittung erzeugen (Unterschriften eingebettet) und ablegen."""
    person = db.query(models.Person).get(payload.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    kind = "return" if payload.kind == "return" else "issue"
    pdf = _build(db, person, kind, _user_name(user), payload.copies,
                 sig_issuer=payload.sig_issuer, sig_recipient=payload.sig_recipient)
    fname = f"{kind}_{person.id}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.pdf"
    try:
        (RECEIPTS_DIR / fname).write_bytes(pdf)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    r = models.Receipt(kind=kind, person_id=person.id, issued_by_user_id=user.id,
                       filename=fname, note=payload.note or "", signed=True)
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "receipt_digital", "person", person.id, {"kind": kind, "receipt_id": r.id})
    return _out(r)


@router.post("/upload", response_model=schemas.ReceiptOut)
async def upload(person_id: int = Form(...), kind: str = Form("issue"), note: str = Form(""),
                 file: UploadFile = File(...), db: Session = Depends(get_db),
                 user=Depends(security.require_capability("issues"))):
    """Unterschriebene Quittung (Foto/Scan/PDF) hochladen und ablegen."""
    person = db.query(models.Person).get(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    kind = "return" if kind == "return" else "issue"
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei ist zu groß (max. 25 MB)")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        ext = ".jpg"
    fname = f"{kind}_{person.id}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    try:
        (RECEIPTS_DIR / fname).write_bytes(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    r = models.Receipt(kind=kind, person_id=person.id, issued_by_user_id=user.id,
                       filename=fname, note=note or "", signed=True)
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "receipt_upload", "person", person.id, {"kind": kind, "receipt_id": r.id})
    return _out(r)


def _out(r) -> schemas.ReceiptOut:
    return schemas.ReceiptOut(
        id=r.id, kind=r.kind, person_id=r.person_id, person_name=_person_name(r.person),
        issued_by_name=_user_name(r.issued_by), filename=r.filename, signed=r.signed,
        created_at=r.created_at)


@router.get("", response_model=list[schemas.ReceiptOut])
def list_receipts(person_id: int = None, mine: bool = False, db: Session = Depends(get_db),
                  user=Depends(security.get_current_user)):
    """Abgelegte Quittungen. `person_id` filtert auf eine Person; `mine` zeigt die dem
    eigenen Personenprofil zugeordneten (fuer die Selbstansicht)."""
    q = db.query(models.Receipt)
    if mine:
        if not user.person_id:
            return []
        q = q.filter(models.Receipt.person_id == user.person_id)
    elif person_id:
        q = q.filter(models.Receipt.person_id == person_id)
    else:
        # ohne Filter nur mit Ausgabe-Recht (sonst nur eigene)
        if "issues" not in user_capabilities(db, user) and "admin" not in (user.roles or []):
            if not user.person_id:
                return []
            q = q.filter(models.Receipt.person_id == user.person_id)
    return [_out(r) for r in q.order_by(models.Receipt.created_at.desc()).limit(200).all()]


@router.get("/{receipt_id}/file")
def get_file(receipt_id: int, db: Session = Depends(get_db),
             user=Depends(security.get_current_user)):
    r = db.query(models.Receipt).get(receipt_id)
    if not r or not r.filename:
        raise HTTPException(status_code=404, detail="Quittung nicht gefunden")
    # Zugriff: Ausgabe-Recht/Admin oder die betreffende Person selbst.
    from ..permissions import user_capabilities
    allowed = "admin" in (user.roles or []) or "issues" in user_capabilities(db, user) \
        or (user.person_id and user.person_id == r.person_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    path = RECEIPTS_DIR / os.path.basename(r.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    media = "application/pdf" if r.filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=r.filename)


@router.delete("/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin", "verwalter"))):
    r = db.query(models.Receipt).get(receipt_id)
    if r:
        if r.filename:
            try:
                (RECEIPTS_DIR / os.path.basename(r.filename)).unlink(missing_ok=True)
            except OSError:
                pass
        db.delete(r)
        db.commit()
        log_action(db, user, "receipt_delete", "receipt", receipt_id)
    return {"ok": True}
