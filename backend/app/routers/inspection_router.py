import os
import uuid
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..config import INSPECTIONS_DIR

router = APIRouter(prefix="/api/inspection", tags=["inspection"])

TRIGGERS = ("return", "loans", "washes", "months")
ARTICLE_TRIGGERS = TRIGGERS + ("return_once",)   # Einzelartikel zusätzlich: einmalig bei Rückgabe


# --------------------------- Checklisten -------------------------------------

def _cl_out(c) -> schemas.ChecklistOut:
    return schemas.ChecklistOut(
        id=c.id, name=c.name,
        items=[schemas.ChecklistItemOut(id=i.id, position=i.position, label=i.label) for i in c.items])


@router.get("/checklists", response_model=list[schemas.ChecklistOut])
def list_checklists(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return [_cl_out(c) for c in db.query(models.InspectionChecklist).order_by(models.InspectionChecklist.name).all()]


@router.post("/checklists", response_model=schemas.ChecklistOut)
def create_checklist(payload: schemas.ChecklistCreate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = models.InspectionChecklist(name=(payload.name or "").strip() or "Checkliste")
    db.add(c)
    db.flush()
    for i, it in enumerate(payload.items or []):
        if (it.label or "").strip():
            db.add(models.InspectionChecklistItem(checklist_id=c.id, position=i, label=it.label.strip()))
    db.commit()
    db.refresh(c)
    log_action(db, user, "checklist_create", "inspection_checklist", c.id, {"name": c.name})
    return _cl_out(c)


@router.put("/checklists/{cid}", response_model=schemas.ChecklistOut)
def update_checklist(cid: int, payload: schemas.ChecklistUpdate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = db.query(models.InspectionChecklist).get(cid)
    if not c:
        raise HTTPException(status_code=404, detail="Checkliste nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name"):
        c.name = data["name"].strip()
    if "items" in data and data["items"] is not None:
        c.items.clear()
        db.flush()
        for i, it in enumerate(data["items"]):
            label = (it.get("label") or "").strip()
            if label:
                db.add(models.InspectionChecklistItem(checklist_id=c.id, position=i, label=label))
    db.commit()
    db.refresh(c)
    log_action(db, user, "checklist_update", "inspection_checklist", c.id)
    return _cl_out(c)


@router.delete("/checklists/{cid}")
def delete_checklist(cid: int, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = db.query(models.InspectionChecklist).get(cid)
    if c:
        db.delete(c)
        db.commit()
        log_action(db, user, "checklist_delete", "inspection_checklist", cid)
    return {"ok": True}


# --------------------------- Prüfregeln je Typ -------------------------------

def _rule_out(r) -> schemas.InspectionRuleOut:
    return schemas.InspectionRuleOut(
        id=r.id, type_id=r.type_id, type_name=r.type.name if r.type else None,
        article_id=r.article_id,
        trigger=r.trigger, threshold=r.threshold or 1,
        checklist_id=r.checklist_id, checklist_name=r.checklist.name if r.checklist else None)


@router.get("/rules", response_model=list[schemas.InspectionRuleOut])
def list_rules(type_id: int = None, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    q = db.query(models.InspectionRule)
    if type_id:
        q = q.filter(models.InspectionRule.type_id == type_id)
    return [_rule_out(r) for r in q.all()]


@router.post("/rules", response_model=schemas.InspectionRuleOut)
def create_rule(payload: schemas.InspectionRuleCreate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    if not db.query(models.ArticleType).get(payload.type_id):
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    trig = payload.trigger if payload.trigger in TRIGGERS else "return"
    r = models.InspectionRule(type_id=payload.type_id, trigger=trig,
                              threshold=max(1, int(payload.threshold or 1)),
                              checklist_id=payload.checklist_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "inspection_rule_create", "article_type", payload.type_id,
               {"trigger": trig, "threshold": r.threshold})
    return _rule_out(r)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    r = db.query(models.InspectionRule).get(rule_id)
    if r:
        db.delete(r)
        db.commit()
        log_action(db, user, "inspection_rule_delete", "inspection_rule", rule_id)
    return {"ok": True}


# --------------------- Prüfregeln je Einzelartikel (Override) ----------------

@router.get("/article-rules/{article_id}")
def article_rules(article_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    rules = db.query(models.InspectionRule).filter(
        models.InspectionRule.article_id == article_id).all()
    return {"override": bool(a.inspection_override), "rules": [_rule_out(r) for r in rules]}


@router.put("/article-rules/{article_id}/override")
def set_article_override(article_id: int, payload: schemas.OverrideToggle, db: Session = Depends(get_db),
                         user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.inspection_override = bool(payload.enabled)
    db.commit()
    log_action(db, user, "inspection_override", "article", article_id, {"enabled": a.inspection_override})
    return {"override": a.inspection_override}


@router.post("/article-rules/{article_id}", response_model=schemas.InspectionRuleOut)
def create_article_rule(article_id: int, payload: schemas.ArticleRuleCreate, db: Session = Depends(get_db),
                        user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    trig = payload.trigger if payload.trigger in ARTICLE_TRIGGERS else "return"
    r = models.InspectionRule(type_id=a.type_id, article_id=a.id, trigger=trig,
                              threshold=max(1, int(payload.threshold or 1)),
                              checklist_id=payload.checklist_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "inspection_article_rule_create", "article", article_id, {"trigger": trig})
    return _rule_out(r)


# --------------------------- Prüfvorgang -------------------------------------

def _uname(u):
    return (u.full_name or u.username) if u else None


def _insp_out(insp) -> schemas.InspectionOut:
    return schemas.InspectionOut(
        id=insp.id, article_id=insp.article_id,
        artikelnummer=insp.article.artikelnummer if insp.article else None,
        checklist_name=insp.checklist_name or "", status=insp.status, result=insp.result or "",
        overall_note=insp.overall_note or "", has_document=bool(insp.document_filename),
        started_by_name=_uname(insp.started_by), finished_by_name=_uname(insp.finished_by),
        started_at=insp.started_at, finished_at=insp.finished_at,
        maintenance_id=insp.maintenance_id, field_values=insp.field_values or {},
        results=[schemas.InspectionItemOut(id=r.id, position=r.position, label=r.label,
                                           ok=r.ok, note=r.note or "") for r in insp.results])


@router.get("/pending")
def pending(db: Session = Depends(get_db), user=Depends(security.require_capability("articles"))):
    """Artikel, die auf eine Prüfung warten (prüfpflichtig markiert – verfügbar
    „zu prüfen" ebenso wie ausgegebene PSA)."""
    arts = db.query(models.Article).filter(models.Article.needs_inspection == True) \
        .order_by(models.Article.artikelnummer).all()  # noqa: E712
    out = []
    for a in arts:
        insp = db.query(models.Inspection).filter(
            models.Inspection.article_id == a.id, models.Inspection.status != "done").first()
        out.append({"id": a.id, "artikelnummer": a.artikelnummer,
                    "typ": a.type.name if a.type else "", "size": a.size or "",
                    "issued": a.status == "ausgegeben", "current_location": a.current_location or "",
                    "inspection_id": insp.id if insp else None,
                    "inspection_status": insp.status if insp else None})
    return out


@router.post("/start", response_model=schemas.InspectionOut)
def start(payload: schemas.InspectionStart, db: Session = Depends(get_db),
          user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(payload.article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    existing = db.query(models.Inspection).filter(
        models.Inspection.article_id == a.id, models.Inspection.status != "done").first()
    if existing:
        return _insp_out(existing)
    cl = db.query(models.InspectionChecklist).get(a.pending_checklist_id) if a.pending_checklist_id else None
    insp = models.Inspection(article_id=a.id, checklist_id=cl.id if cl else None,
                             checklist_name=cl.name if cl else "", status="open",
                             started_by_id=user.id)
    db.add(insp)
    db.flush()
    if cl:
        for it in cl.items:
            db.add(models.InspectionItemResult(inspection_id=insp.id, position=it.position, label=it.label))
    db.commit()
    db.refresh(insp)
    log_action(db, user, "inspection_start", "article", a.id, {"inspection_id": insp.id})
    return _insp_out(insp)


@router.get("/{insp_id}", response_model=schemas.InspectionOut)
def get_inspection(insp_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("articles"))):
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    return _insp_out(insp)


@router.post("/{insp_id}/item", response_model=schemas.InspectionOut)
def set_item(insp_id: int, payload: schemas.InspectionItemUpdate, db: Session = Depends(get_db),
             user=Depends(security.require_capability("articles"))):
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    if insp.status == "done":
        raise HTTPException(status_code=400, detail="Prüfung ist bereits abgeschlossen")
    it = next((r for r in insp.results if r.id == payload.item_id), None)
    if not it:
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden")
    if payload.ok is not None:
        it.ok = payload.ok
    if payload.note is not None:
        it.note = payload.note
    db.commit()
    db.refresh(insp)
    return _insp_out(insp)


@router.post("/{insp_id}/status", response_model=schemas.InspectionOut)
def set_status(insp_id: int, action: str, db: Session = Depends(get_db),
               user=Depends(security.require_capability("articles"))):
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    if insp.status == "done":
        raise HTTPException(status_code=400, detail="Prüfung ist bereits abgeschlossen")
    if action == "pause":
        insp.status = "paused"
    elif action == "resume":
        insp.status = "open"
    else:
        raise HTTPException(status_code=400, detail="Unbekannte Aktion")
    db.commit()
    db.refresh(insp)
    return _insp_out(insp)


@router.post("/{insp_id}/finish", response_model=schemas.InspectionOut)
def finish(insp_id: int, payload: schemas.InspectionFinish, db: Session = Depends(get_db),
           user=Depends(security.require_capability("articles"))):
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    if insp.status == "done":
        # Schutz gegen Doppelabschluss (z.B. Doppelklick / zwei offene Fenster):
        # Artikelstatus nicht erneut verändern.
        return _insp_out(insp)
    a = insp.article
    result = "failed" if payload.result == "failed" else "passed"
    insp.result = result
    insp.overall_note = payload.overall_note or ""
    insp.status = "done"
    insp.finished_by_id = user.id
    insp.finished_at = dt.datetime.utcnow()
    if a:
        if result == "passed":
            # Bestanden: gesperrte (zu prüfende) Artikel wieder freigeben; ein
            # ausgegebener Artikel bleibt ausgegeben (Ausleihe läuft weiter).
            if a.status == "zu_pruefen":
                a.status = models.ArticleStatus.verfuegbar.value
        else:
            tgt = payload.target_status if payload.target_status in ("reparatur", "ausgemustert") else "reparatur"
            a.status = tgt
        a.last_inspection_at = dt.datetime.utcnow()
        a.pending_checklist_id = None
        a.needs_inspection = False
    db.commit()
    db.refresh(insp)
    log_action(db, user, "inspection_finish", "article", insp.article_id,
               {"inspection_id": insp.id, "result": result})
    return _insp_out(insp)


@router.post("/{insp_id}/abort")
def abort(insp_id: int, db: Session = Depends(get_db),
          user=Depends(security.require_capability("articles"))):
    """Eine versehentlich gestartete (noch nicht abgeschlossene) Prüfung verwerfen.
    Der Artikel bleibt prüfpflichtig, kann also erneut geprüft werden."""
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    if insp.status == "done":
        raise HTTPException(status_code=400, detail="Abgeschlossene Prüfung kann nicht verworfen werden")
    aid = insp.article_id
    db.delete(insp)
    db.commit()
    log_action(db, user, "inspection_abort", "article", aid, {"inspection_id": insp_id})
    return {"ok": True}


@router.get("/by-article/{article_id}", response_model=list[schemas.InspectionOut])
def by_article(article_id: int, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    q = db.query(models.Inspection).filter(models.Inspection.article_id == article_id) \
        .order_by(models.Inspection.started_at.desc()).all()
    return [_insp_out(i) for i in q]


@router.get("/{insp_id}/protocol.pdf")
def protocol_pdf(insp_id: int, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    """Generiertes Prüfprotokoll (PDF) mit Checklisten-Ergebnissen und Unterschriftsfeld."""
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    from .export import build_inspection_pdf
    from fastapi.responses import Response
    pdf = build_inspection_pdf(db, insp)
    art = insp.article.artikelnummer if insp.article else insp_id
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Pruefprotokoll_{art}.pdf"'})


@router.post("/{insp_id}/document", response_model=schemas.InspectionOut)
async def upload_document(insp_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user=Depends(security.require_capability("articles"))):
    """Externes Prüfprotokoll (Foto/PDF) zur Prüfung ablegen."""
    insp = db.query(models.Inspection).get(insp_id)
    if not insp:
        raise HTTPException(status_code=404, detail="Prüfung nicht gefunden")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 25 MB)")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        ext = ".jpg"
    fname = f"insp_{insp.id}_{uuid.uuid4().hex[:8]}{ext}"
    try:
        (INSPECTIONS_DIR / fname).write_bytes(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Ablage fehlgeschlagen")
    insp.document_filename = fname
    db.commit()
    db.refresh(insp)
    log_action(db, user, "inspection_document", "article", insp.article_id, {"inspection_id": insp.id})
    return _insp_out(insp)


@router.get("/{insp_id}/document")
def get_document(insp_id: int, db: Session = Depends(get_db),
                 user=Depends(security.get_current_user)):
    insp = db.query(models.Inspection).get(insp_id)
    if not insp or not insp.document_filename:
        raise HTTPException(status_code=404, detail="Kein Protokoll")
    path = INSPECTIONS_DIR / os.path.basename(insp.document_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    media = "application/pdf" if insp.document_filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=insp.document_filename)
