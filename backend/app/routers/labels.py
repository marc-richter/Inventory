import io
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .. import models, security
from ..database import get_db
from ..settings_helper import get_setting
from ..printing import send_raw_to_network_printer, PrintError

router = APIRouter(prefix="/api/labels", tags=["labels"])

# Gaengige Brother-Etikettengroessen (Breite x Hoehe in mm) als Presets fuer die Oberflaeche
LABEL_PRESETS = {
    "DK-11201 (29x90mm)": (90, 29),
    "DK-11208 (38x90mm)": (90, 38),
    "DK-11209 (29x62mm)": (62, 29),
    "DK-22205 (62mm endlos)": (62, 100),
    "QL-Klein (50x25mm)": (50, 25),
}


@router.get("/presets")
def label_presets():
    return LABEL_PRESETS


def _draw_label(c: canvas.Canvas, page_w: float, page_h: float, artikelnummer: str, type_name: str, size: str):
    """Zeichnet ein einzelnes Etikett auf die aktuelle Seite des Canvas und
    schliesst die Seite ab (showPage). Wird sowohl fuer den Einzeldruck als
    auch fuer den Sammeldruck (mehrere Etiketten/Seiten in einem PDF) genutzt."""
    qr_img = qrcode.make(artikelnummer)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    qr_size = min(page_h - 4 * mm, page_w * 0.4)
    qr_reader = ImageReader(qr_buf)
    margin = 2 * mm
    c.drawImage(qr_reader, margin, margin, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")

    text_x = margin + qr_size + 3 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(text_x, page_h - 8 * mm, artikelnummer[:24])
    c.setFont("Helvetica", 7)
    c.drawString(text_x, page_h - 13 * mm, (type_name or "")[:28])
    if size:
        c.drawString(text_x, page_h - 18 * mm, f"Groesse: {size}"[:28])

    c.showPage()


def _build_label_pdf(artikelnummer: str, type_name: str, size: str, width_mm: float, height_mm: float) -> bytes:
    page_w = width_mm * mm
    page_h = height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    _draw_label(c, page_w, page_h, artikelnummer, type_name, size)
    c.save()
    buf.seek(0)
    return buf.read()


def _build_bulk_label_pdf(items: list, width_mm: float, height_mm: float) -> bytes:
    """Baut ein einziges PDF mit einer Seite pro Etikett (`items` = Liste von
    (artikelnummer, type_name, size)-Tupeln), zum En-bloc-Ausdrucken einer
    ganzen Mengenerfassung auf einem Etikettendrucker mit fortlaufendem Band."""
    page_w = width_mm * mm
    page_h = height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    for artikelnummer, type_name, size in items:
        _draw_label(c, page_w, page_h, artikelnummer, type_name, size)
    c.save()
    buf.seek(0)
    return buf.read()


@router.get("/article/{article_id}")
def label_for_article(article_id: int, width_mm: float = None, height_mm: float = None,
                       db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    pdf_bytes = _build_label_pdf(a.artikelnummer, a.type.name if a.type else "", a.size, w, h)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="etikett_{a.artikelnummer}.pdf"'},
    )


@router.get("/bulk")
def labels_bulk(
    article_id: List[int] = Query(...), width_mm: Optional[float] = None, height_mm: Optional[float] = None,
    db: Session = Depends(get_db), user=Depends(security.get_current_user),
):
    """Etiketten fuer mehrere Artikel (z.B. eine ganze Mengenerfassung) auf
    einmal als ein einziges PDF - eine Seite je Etikett, in der gleichen
    Reihenfolge wie uebergeben - zum En-bloc-Ausdrucken."""
    articles = db.query(models.Article).filter(models.Article.id.in_(article_id)).all()
    by_id = {a.id: a for a in articles}
    ordered = [by_id[i] for i in article_id if i in by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="Keine passenden Artikel gefunden")

    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    items = [(a.artikelnummer, a.type.name if a.type else "", a.size) for a in ordered]
    pdf_bytes = _build_bulk_label_pdf(items, w, h)
    filename = f"etiketten_sammel_{len(ordered)}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/bulk/print-network")
def labels_bulk_print_network(
    article_id: List[int] = Query(...), width_mm: Optional[float] = None, height_mm: Optional[float] = None,
    db: Session = Depends(get_db), user=Depends(security.require_roles("admin", "verwalter", "helfer")),
):
    """Sendet die Sammel-PDF mehrerer Etiketten in einem Rutsch an einen im
    Netzwerk konfigurierten Brother-Drucker (siehe printing.py fuer die
    Einschraenkungen bzgl. USB/Bluetooth)."""
    articles = db.query(models.Article).filter(models.Article.id.in_(article_id)).all()
    by_id = {a.id: a for a in articles}
    ordered = [by_id[i] for i in article_id if i in by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="Keine passenden Artikel gefunden")

    connection_type = get_setting(db, "printer_connection_type", "none")
    printer_ip = get_setting(db, "printer_ip", "")
    if connection_type != "network" or not printer_ip:
        raise HTTPException(
            status_code=400,
            detail=(
                "Kein Netzwerkdrucker konfiguriert. Bitte in den Einstellungen "
                "unter 'Drucker' die IP-Adresse eines WLAN/LAN-Brother-Druckers "
                "hinterlegen, oder die Sammel-PDF herunterladen und ueber den "
                "Systemdruckdialog drucken (fuer USB/Bluetooth-Drucker)."
            ),
        )

    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    items = [(a.artikelnummer, a.type.name if a.type else "", a.size) for a in ordered]
    pdf_bytes = _build_bulk_label_pdf(items, w, h)

    try:
        send_raw_to_network_printer(printer_ip, pdf_bytes)
    except PrintError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"ok": True, "message": f"Sammel-Druckauftrag ({len(ordered)} Etiketten) an {printer_ip} gesendet."}


@router.post("/article/{article_id}/print-network")
def print_label_network(article_id: int, width_mm: float = None, height_mm: float = None,
                         db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin", "verwalter", "helfer"))):
    """Versucht, das Etikett direkt an einen im Netzwerk konfigurierten Brother-
    Drucker zu senden (Port 9100 Rohdruck). Siehe printing.py fuer die
    ehrliche Einschraenkung: funktioniert nur bei netzwerkfaehigen Druckern,
    NICHT bei per USB/Bluetooth angeschlossenen Geraeten - dafuer bitte den
    PDF-Download nutzen und ueber den normalen Systemdruckdialog drucken."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")

    connection_type = get_setting(db, "printer_connection_type", "none")
    printer_ip = get_setting(db, "printer_ip", "")
    if connection_type != "network" or not printer_ip:
        raise HTTPException(
            status_code=400,
            detail=(
                "Kein Netzwerkdrucker konfiguriert. Bitte in den Einstellungen "
                "unter 'Drucker' die IP-Adresse eines WLAN/LAN-Brother-Druckers "
                "hinterlegen, oder das Etikett als PDF herunterladen und ueber "
                "den Systemdruckdialog drucken (fuer USB/Bluetooth-Drucker)."
            ),
        )

    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    pdf_bytes = _build_label_pdf(a.artikelnummer, a.type.name if a.type else "", a.size, w, h)

    try:
        send_raw_to_network_printer(printer_ip, pdf_bytes)
    except PrintError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"ok": True, "message": f"Druckauftrag an {printer_ip} gesendet."}
