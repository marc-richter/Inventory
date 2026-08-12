"""Mehrere Server-Drucker verwalten und je Anwendungsfall zuordnen.

Konzept:
- Ein Admin legt in den Einstellungen beliebig viele Drucker an (CUPS-Warteschlange
  oder IP:Port). Auto-Erkennung liest vorhandene CUPS-Drucker vom Server.
- Darunter gibt es eine feste Liste von Anwendungsfaellen (use_cases), fuer die das
  Programm drucken moechte (Etiketten, Quittungen, Berichte, Listen). Je Fall lassen
  sich ein oder mehrere Drucker zuordnen.
- Beim Drucken laedt das Frontend das ohnehin erzeugte PDF und schickt es an
  /print/raw an den gewaehlten Server-Drucker. Ist genau ein Drucker zugeordnet,
  wird direkt gedruckt; bei mehreren waehlt der Nutzer aus; ist keiner zugeordnet,
  bleibt der bisherige PDF-Download/-Druck ueber das Endgeraet.
"""
import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from .. import printing

router = APIRouter(prefix="/api/printers", tags=["printers"])

# Feste Liste der Anwendungsfaelle. `kind` bestimmt, welche Drucker angeboten werden
# ('label' = Etikettendrucker, 'paper' = normaler Papierdrucker).
USE_CASES = [
    {"key": "label", "label": "Etiketten (Artikel-QR/Label)", "kind": "label"},
    {"key": "location_label", "label": "Lagerort-Etiketten (QR)", "kind": "label"},
    {"key": "receipt_issue", "label": "Ausgabequittung", "kind": "paper"},
    {"key": "receipt_return", "label": "Rückgabequittung", "kind": "paper"},
    {"key": "report", "label": "Schaden-/Verlustmeldung (PDF)", "kind": "paper"},
    {"key": "inspection", "label": "Prüfprotokoll", "kind": "paper"},
    {"key": "maintenance", "label": "Wartungsprotokoll", "kind": "paper"},
    {"key": "list_inventory", "label": "Inventarliste", "kind": "paper"},
    {"key": "list_person", "label": "Materialliste je Person", "kind": "paper"},
    {"key": "list_inventur", "label": "Inventur-Bericht", "kind": "paper"},
]
_USE_CASE_KIND = {u["key"]: u["kind"] for u in USE_CASES}


def _mark_status(db, printer, ok, msg):
    printer.last_status = ("OK: " if ok else "Fehler: ") + (msg or "")
    printer.last_status_at = dt.datetime.utcnow()
    db.commit()


def _send(printer: models.Printer, data: bytes, extra_options: str = ""):
    """Schickt PDF-Bytes an den Drucker - je nach Anbindung CUPS oder IP:Port."""
    if printer.conn == "ip":
        printing.send_raw_to_network_printer(printer.host, data, port=printer.port or 9100)
    else:
        opts = " ".join(o for o in [(printer.options or ""), (extra_options or "")] if o).strip()
        printing.send_pdf_to_cups(printer.cups_queue, data, options=opts)


def _test_pdf(printer: models.Printer) -> bytes:
    """Kleine Test-PDF fuer den Testknopf."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(60, 760, "Testdruck – Inventarprogramm")
    c.setFont("Helvetica", 12)
    c.drawString(60, 730, f"Drucker: {printer.name}")
    c.drawString(60, 712, f"Anbindung: {'IP ' + (printer.host or '') if printer.conn == 'ip' else 'CUPS ' + (printer.cups_queue or '')}")
    c.drawString(60, 694, f"Zeit: {dt.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    c.showPage()
    c.save()
    return buf.getvalue()


# --------------------------- Anwendungsfaelle -------------------------------

@router.get("/use-cases")
def list_use_cases(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Katalog der Anwendungsfaelle inkl. der aktuell zugeordneten aktiven Drucker.
    Wird sowohl von der Admin-Verwaltung als auch von den Drucken-Knoepfen genutzt."""
    assigns = db.query(models.PrinterAssignment).order_by(models.PrinterAssignment.sort_order).all()
    by_case = {}
    for a in assigns:
        by_case.setdefault(a.use_case, []).append(a)
    out = []
    for uc in USE_CASES:
        items = by_case.get(uc["key"], [])
        printers = []
        for a in items:
            p = a.printer
            if not p or not p.active:
                continue
            printers.append({
                "assignment_id": a.id, "printer_id": p.id, "name": p.name,
                "kind": p.kind, "format_options": a.format_options or "",
            })
        out.append({**uc, "printers": printers})
    return out


@router.get("/for/{use_case}")
def printers_for(use_case: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Aktive Drucker fuer einen Anwendungsfall (fuer die Drucken-Knoepfe)."""
    assigns = db.query(models.PrinterAssignment).filter(
        models.PrinterAssignment.use_case == use_case
    ).order_by(models.PrinterAssignment.sort_order).all()
    res = []
    for a in assigns:
        p = a.printer
        if p and p.active:
            res.append({"assignment_id": a.id, "printer_id": p.id, "name": p.name,
                        "kind": p.kind, "format_options": a.format_options or ""})
    return res


@router.post("/assignments", response_model=schemas.PrinterAssignmentOut)
def add_assignment(payload: schemas.PrinterAssignmentCreate, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    if payload.use_case not in _USE_CASE_KIND:
        raise HTTPException(status_code=400, detail="Unbekannter Anwendungsfall")
    p = db.query(models.Printer).get(payload.printer_id)
    if not p:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    a = models.PrinterAssignment(
        use_case=payload.use_case, printer_id=payload.printer_id,
        format_options=payload.format_options or "", sort_order=payload.sort_order,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(db, user, "printer_assign", "printer", p.id, {"use_case": payload.use_case})
    return a


@router.put("/assignments/{assignment_id}", response_model=schemas.PrinterAssignmentOut)
def update_assignment(assignment_id: int, payload: schemas.PrinterAssignmentCreate,
                      db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    a = db.query(models.PrinterAssignment).get(assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Zuordnung nicht gefunden")
    a.format_options = payload.format_options or ""
    a.sort_order = payload.sort_order
    db.commit()
    db.refresh(a)
    return a


@router.delete("/assignments/{assignment_id}")
def del_assignment(assignment_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    a = db.query(models.PrinterAssignment).get(assignment_id)
    if a:
        db.delete(a)
        db.commit()
    return {"ok": True}


# --------------------------- Drucker (CRUD) ---------------------------------

@router.get("/discover")
def discover(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    """Liest die auf dem Server in CUPS eingerichteten Drucker aus (Auto-Erkennung)."""
    return {"cups_available": printing.cups_available(), "queues": printing.list_cups_printers()}


@router.get("", response_model=list[schemas.PrinterOut])
def list_printers(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    return db.query(models.Printer).order_by(models.Printer.name).all()


@router.post("", response_model=schemas.PrinterOut)
def create_printer(payload: schemas.PrinterCreate, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    p = models.Printer(**payload.dict())
    db.add(p)
    db.commit()
    db.refresh(p)
    log_action(db, user, "printer_create", "printer", p.id, {"name": p.name})
    return p


@router.put("/{printer_id}", response_model=schemas.PrinterOut)
def update_printer(printer_id: int, payload: schemas.PrinterUpdate, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    p = db.query(models.Printer).get(printer_id)
    if not p:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{printer_id}")
def delete_printer(printer_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    p = db.query(models.Printer).get(printer_id)
    if not p:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    db.query(models.PrinterAssignment).filter(models.PrinterAssignment.printer_id == printer_id).delete()
    db.delete(p)
    db.commit()
    log_action(db, user, "printer_delete", "printer", printer_id)
    return {"ok": True}


@router.post("/{printer_id}/test")
def test_printer(printer_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    p = db.query(models.Printer).get(printer_id)
    if not p:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    try:
        _send(p, _test_pdf(p))
    except printing.PrintError as exc:
        _mark_status(db, p, False, str(exc))
        raise HTTPException(status_code=502, detail=str(exc))
    _mark_status(db, p, True, "Testdruck gesendet")
    return {"ok": True, "message": f"Testdruck an '{p.name}' gesendet."}


# --------------------------- Drucken ----------------------------------------

@router.post("/print")
def print_raw(
    printer_id: int = Form(...),
    use_case: str = Form(""),
    format_options: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(security.get_current_user),
):
    """Druckt ein vom Frontend geliefertes PDF an den gewaehlten Server-Drucker.
    Generisch fuer alle Anwendungsfaelle - das PDF wird wie bisher vom jeweiligen
    Endpunkt erzeugt und hier nur weitergeleitet."""
    p = db.query(models.Printer).get(printer_id)
    if not p or not p.active:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden oder inaktiv")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Leeres Dokument")
    try:
        _send(p, data, extra_options=format_options or "")
    except printing.PrintError as exc:
        _mark_status(db, p, False, str(exc))
        raise HTTPException(status_code=502, detail=str(exc))
    _mark_status(db, p, True, f"{use_case or 'Dokument'} gedruckt")
    log_action(db, user, "print", "printer", p.id, {"use_case": use_case})
    return {"ok": True, "message": f"Druckauftrag an '{p.name}' gesendet."}
