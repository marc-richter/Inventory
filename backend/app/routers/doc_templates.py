"""Dokument-Vorlagen (Briefkopf / Kopf-/Fußzeile) verwalten + Vorschau."""
import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, security, pdf_layout
from ..database import get_db
from ..audit import log_action
from ..config import BRANDING_DIR

router = APIRouter(prefix="/api/doc-templates", tags=["doc-templates"])


@router.get("/use-cases")
def use_cases(user=Depends(security.require_roles("admin"))):
    """Katalog: globale Vorlage + Dokumenttypen; plus der Startpunkt (Standard-Layout)."""
    return {"use_cases": pdf_layout.DOC_USE_CASES, "starter": pdf_layout.STARTER_TEMPLATE}


@router.get("", response_model=list[schemas.DocTemplateOut])
def list_templates(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    return db.query(models.DocTemplate).order_by(models.DocTemplate.use_case.is_(None).desc(),
                                                 models.DocTemplate.use_case).all()


@router.post("", response_model=schemas.DocTemplateOut)
def create_template(payload: schemas.DocTemplateCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    uc = (payload.use_case or None)
    if uc and uc not in {u["key"] for u in pdf_layout.DOC_USE_CASES}:
        raise HTTPException(status_code=400, detail="Unbekannter Dokumenttyp")
    # Nur eine Vorlage je Zweck (global oder je Use-Case): vorhandene aktualisieren.
    existing = db.query(models.DocTemplate).filter(models.DocTemplate.use_case.is_(None) if uc is None
                                                   else models.DocTemplate.use_case == uc).first()
    if existing:
        raise HTTPException(status_code=400, detail="Für diesen Zweck existiert bereits eine Vorlage")
    t = models.DocTemplate(use_case=uc, name=payload.name or "", active=payload.active,
                           header_height_mm=payload.header_height_mm, footer_height_mm=payload.footer_height_mm,
                           elements=payload.elements or [])
    db.add(t)
    db.commit()
    db.refresh(t)
    log_action(db, user, "doc_template_create", "doc_template", t.id, {"use_case": uc})
    return t


@router.put("/{template_id}", response_model=schemas.DocTemplateOut)
def update_template(template_id: int, payload: schemas.DocTemplateUpdate, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    t = db.query(models.DocTemplate).get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    log_action(db, user, "doc_template_update", "doc_template", t.id, {})
    return t


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    t = db.query(models.DocTemplate).get(template_id)
    if t:
        db.delete(t)
        db.commit()
        log_action(db, user, "doc_template_delete", "doc_template", template_id)
    return {"ok": True}


@router.post("/{template_id}/background", response_model=schemas.DocTemplateOut)
async def upload_background(template_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                           user=Depends(security.require_roles("admin"))):
    """Hintergrund-Vorlage (Briefpapier) hochladen – PDF oder Bild (PNG/JPG). Wird
    seitenfüllend hinter den Inhalt gelegt."""
    t = db.query(models.DocTemplate).get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei ist zu groß (max. 25 MB)")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext == ".pdf":
        kind = "pdf"
    elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
        kind = "image"
    else:
        raise HTTPException(status_code=400, detail="Nur PDF, PNG oder JPG erlaubt")
    # alte Datei entfernen
    if t.background_filename:
        try:
            (BRANDING_DIR / os.path.basename(t.background_filename)).unlink(missing_ok=True)
        except OSError:
            pass
    fname = f"tplbg_{t.id}_{uuid.uuid4().hex[:8]}{ext}"
    try:
        BRANDING_DIR.mkdir(parents=True, exist_ok=True)
        (BRANDING_DIR / fname).write_bytes(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    t.background_filename = fname
    t.background_kind = kind
    db.commit()
    db.refresh(t)
    log_action(db, user, "doc_template_background", "doc_template", t.id, {"kind": kind})
    return t


@router.delete("/{template_id}/background", response_model=schemas.DocTemplateOut)
def delete_background(template_id: int, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin"))):
    t = db.query(models.DocTemplate).get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if t.background_filename:
        try:
            (BRANDING_DIR / os.path.basename(t.background_filename)).unlink(missing_ok=True)
        except OSError:
            pass
    t.background_filename = ""
    t.background_kind = ""
    db.commit()
    db.refresh(t)
    return t


@router.get("/{template_id}/background")
def get_background(template_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    t = db.query(models.DocTemplate).get(template_id)
    if not t or not t.background_filename:
        raise HTTPException(status_code=404, detail="Kein Hintergrund")
    path = BRANDING_DIR / os.path.basename(t.background_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    media = "application/pdf" if t.background_kind == "pdf" else "image/*"
    return FileResponse(path, media_type=media)


@router.get("/preview")
def preview(use_case: str = "", db: Session = Depends(get_db),
            user=Depends(security.require_roles("admin"))):
    """Beispiel-PDF mit der (für diesen Zweck) aufgelösten Vorlage – zum Prüfen des
    Layouts, mit Platzhalter-Beispieldaten."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    label = next((u["label"] for u in pdf_layout.DOC_USE_CASES if u["key"] == use_case), "Dokument")
    tmpl = pdf_layout.resolve_template(db, use_case or None)
    cm = pdf_layout.make_canvas(db, tmpl, f"{label} (Vorschau)", "Beispiel-Untertitel")
    top = (tmpl["header_height_mm"] if tmpl.get("_custom") else 28) * mm
    bottom = (tmpl["footer_height_mm"] if tmpl.get("_custom") else 14) * mm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=top, bottomMargin=bottom,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = []
    if not tmpl.get("_custom"):
        story.append(Paragraph(f"{label} (Vorschau)", styles["Title"]))
        story.append(Paragraph("Ohne eigene Vorlage: Kopf kommt wie bisher vom Dokument, es wird nur "
                               "die einheitliche Fußzeile ergänzt.", styles["Normal"]))
        story.append(Spacer(1, 8))
    story.append(Paragraph("Beispiel-Inhalt", styles["Heading3"]))
    for _ in range(40):
        story.append(Paragraph("Musterzeile für den Dokumentinhalt – zeigt Kopf/Fuß auf jeder Seite.", styles["Normal"]))
    doc.build(story, canvasmaker=cm)
    buf.seek(0)
    out = pdf_layout.finalize(db, use_case or None, buf.read())
    return Response(content=out, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="vorlage-vorschau.pdf"'})
