import io
import json
from typing import List, Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderPDF, renderSVG

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

# Verfuegbare Code-Formate fuer die maschinenlesbare Inventarnummer. Code128/Code39
# koennen (anders als EAN) auch alphanumerische Nummern wie "2026-00042" abbilden.
CODE_FORMATS = [
    {"key": "qr", "label": "QR-Code"},
    {"key": "code128", "label": "Strichcode Code 128"},
    {"key": "code39", "label": "Strichcode Code 39"},
]
_BARCODE_NAMES = {"code128": "Code128", "code39": "Standard39"}

# Felder, die (in konfigurierbarer Reihenfolge) als Text aufs Etikett koennen.
LABEL_FIELD_DEFS = [
    {"key": "artikelnummer", "label": "Inventarnummer"},
    {"key": "type", "label": "Typ"},
    {"key": "model", "label": "Modell"},
    {"key": "size", "label": "Größe"},
    {"key": "organization", "label": "Abteilung"},
    {"key": "storage_location", "label": "Lagerort"},
    {"key": "current_location", "label": "Standort"},
    {"key": "properties", "label": "Eigenschaften"},
]
_PREFIX = {
    "model": "Modell: ", "size": "Größe: ", "organization": "Abt.: ",
    "storage_location": "Lager: ", "current_location": "Standort: ",
}
DEFAULT_MAXLEN = {
    "artikelnummer": 24, "type": 28, "size": 24, "model": 10,
    "organization": 24, "storage_location": 24, "current_location": 24, "properties": 24,
}


@router.get("/presets")
def label_presets():
    return LABEL_PRESETS


@router.get("/config")
def label_config_meta(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    """Metadaten fuer die Etikett-Einstellungen: verfuegbare Code-Formate, Felder
    und die aktuelle Auswahl (Format, Felder, Feld-Maximallaengen)."""
    cfg = _label_config(db)
    return {
        "formats": CODE_FORMATS,
        "fields": LABEL_FIELD_DEFS,
        "default_maxlen": DEFAULT_MAXLEN,
        "current": cfg,
    }


def _label_config(db: Session) -> dict:
    fmt = (get_setting(db, "label_code_format", "qr") or "qr").lower()
    fields_raw = get_setting(db, "label_fields", "artikelnummer,type,size,model")
    fields = [f.strip() for f in (fields_raw or "").split(",") if f.strip()]
    if not fields:
        fields = ["artikelnummer"]
    try:
        maxlen = json.loads(get_setting(db, "label_maxlen", "") or "{}")
    except (ValueError, TypeError):
        maxlen = {}
    if not isinstance(maxlen, dict):
        maxlen = {}
    return {"format": fmt, "fields": fields, "maxlen": maxlen}


def _barcode_drawing(value: str, fmt: str):
    """Liefert ein reportlab-Drawing des Strichcodes (Vektor) oder None, wenn das
    Format kein Strichcode ist bzw. der Wert nicht darstellbar ist. Bewusst als
    Vektor - so wird KEIN Raster-Renderer (renderPM) benoetigt, der im schlanken
    Server-Container fehlt und bislang zum QR-Rueckfall gefuehrt hat."""
    name = _BARCODE_NAMES.get((fmt or "").lower())
    if not name:
        return None
    try:
        return createBarcodeDrawing(name, value=str(value), humanReadable=True)
    except Exception:
        return None  # ungueltiger Wert fuer dieses Format


def _qr_png(value: str) -> bytes:
    img = qrcode.make(value)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _field_value(a, key: str, type_name: str) -> str:
    if key == "artikelnummer":
        return a.artikelnummer or ""
    if key == "type":
        return type_name or ""
    if key == "model":
        return a.model or ""
    if key == "size":
        return a.size or ""
    if key == "organization":
        return a.organization.name if a.organization else ""
    if key == "storage_location":
        return a.storage_location.name if a.storage_location else ""
    if key == "current_location":
        return a.current_location or ""
    if key == "properties":
        return a.properties or ""
    return ""


def _label_lines(a, type_name: str, cfg: dict) -> list:
    """Baut die Textzeilen fuers Etikett gemaess konfigurierter Felderauswahl und
    kuerzt jeden Wert auf die (fuers Etikett) erlaubte Maximallaenge. Die Laenge im
    Artikel selbst bleibt davon unberuehrt."""
    lines = []
    for key in cfg["fields"]:
        val = _field_value(a, key, type_name)
        if not val:
            continue
        ml = cfg["maxlen"].get(key, DEFAULT_MAXLEN.get(key, 24))
        try:
            ml = int(ml)
        except (ValueError, TypeError):
            ml = DEFAULT_MAXLEN.get(key, 24)
        if ml > 0:
            val = str(val)[:ml]
        lines.append(_PREFIX.get(key, "") + str(val))
    return lines


def _draw_label(c: canvas.Canvas, page_w: float, page_h: float, a, type_name: str, cfg: dict):
    """Zeichnet ein einzelnes Etikett (Code + konfigurierte Textzeilen) und schliesst
    die Seite ab (showPage)."""
    margin = 2 * mm
    fmt = (cfg.get("format") or "qr").lower()
    bc = _barcode_drawing(a.artikelnummer, fmt) if fmt in _BARCODE_NAMES else None

    text_x = margin
    y = page_h - 7 * mm
    if bc is not None and bc.width > 0 and bc.height > 0:
        # Strichcode als Vektor oben ueber die Breite platzieren.
        max_w = page_w - 2 * margin
        max_h = min(page_h * 0.45, 16 * mm)
        s = min(max_w / bc.width, max_h / bc.height)
        bc.width *= s
        bc.height *= s
        bc.scale(s, s)
        renderPDF.draw(bc, c, margin, page_h - margin - bc.height)
        text_x = margin
        y = page_h - margin - bc.height - 4 * mm
    else:
        # QR-Code (quadratisch) links.
        reader = ImageReader(io.BytesIO(_qr_png(a.artikelnummer)))
        code_size = min(page_h - 4 * mm, page_w * 0.4)
        c.drawImage(reader, margin, margin, width=code_size, height=code_size,
                    preserveAspectRatio=True, mask="auto")
        text_x = margin + code_size + 3 * mm
        y = page_h - 7 * mm

    first = True
    for text in _label_lines(a, type_name, cfg):
        if first:
            c.setFont("Helvetica-Bold", 9)
            first = False
        else:
            c.setFont("Helvetica", 7)
        c.drawString(text_x, y, text)
        y -= 4.5 * mm

    c.showPage()


def _type_name(a) -> str:
    return a.type.name if a.type else ""


def _build_label_pdf(a, cfg: dict, width_mm: float, height_mm: float) -> bytes:
    page_w = width_mm * mm
    page_h = height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    _draw_label(c, page_w, page_h, a, _type_name(a), cfg)
    c.save()
    buf.seek(0)
    return buf.read()


def _build_bulk_label_pdf(articles: list, cfg: dict, width_mm: float, height_mm: float) -> bytes:
    """Ein PDF mit einer Seite je Etikett, zum En-bloc-Ausdrucken einer ganzen
    Mengenerfassung auf einem Etikettendrucker mit fortlaufendem Band."""
    page_w = width_mm * mm
    page_h = height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    for a in articles:
        _draw_label(c, page_w, page_h, a, _type_name(a), cfg)
    c.save()
    buf.seek(0)
    return buf.read()


@router.get("/code-preview")
def code_preview(value: str = "2026-00042", format: str = "qr"):
    """Beispielbild des maschinenlesbaren Codes im gewaehlten Format - fuer die
    Live-Vorschau in den Einstellungen. Bewusst ohne Auth (nur lokales Netz), damit
    es per <img src=...> angezeigt werden kann. Strichcodes werden als SVG (reine
    Python) geliefert, QR als PNG - beides ohne den fehlenden Raster-Renderer."""
    value = value or "2026-00042"
    fmt = (format or "qr").lower()
    if fmt in _BARCODE_NAMES:
        d = _barcode_drawing(value, fmt)
        if d is not None:
            svg = renderSVG.drawToString(d)
            return Response(content=svg, media_type="image/svg+xml")
    return Response(content=_qr_png(value), media_type="image/png")


@router.get("/article/{article_id}")
def label_for_article(article_id: int, width_mm: float = None, height_mm: float = None,
                       db: Session = Depends(get_db)):
    # Bewusst ohne Auth-Pruefung, damit das Etikett-PDF per window.open in einem
    # neuen Tab geoeffnet werden kann (dabei wird kein Authorization-Header
    # gesendet). Anwendung laeuft nur im lokalen Netz - wie bei den Bild-Endpoints.
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    pdf_bytes = _build_label_pdf(a, _label_config(db), w, h)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="etikett_{a.artikelnummer}.pdf"'},
    )


@router.get("/bulk")
def labels_bulk(
    article_id: List[int] = Query(...), width_mm: Optional[float] = None, height_mm: Optional[float] = None,
    db: Session = Depends(get_db),
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
    pdf_bytes = _build_bulk_label_pdf(ordered, _label_config(db), w, h)
    filename = f"etiketten_sammel_{len(ordered)}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _resolve_printer_ip(db: Session, printer_ip_override: Optional[str]) -> str:
    """Bestimmt die Ziel-Drucker-IP: entweder eine explizit mitgegebene (z.B. ein
    ueber das mobile Endgeraet erreichbarer Drucker) oder - falls keine angegeben -
    der in den Einstellungen hinterlegte Netzwerkdrucker."""
    override = (printer_ip_override or "").strip()
    if override:
        return override
    if get_setting(db, "printer_connection_type", "none") == "network":
        return (get_setting(db, "printer_ip", "") or "").strip()
    return ""


@router.post("/bulk/print-network")
def labels_bulk_print_network(
    article_id: List[int] = Query(...), width_mm: Optional[float] = None, height_mm: Optional[float] = None,
    printer_ip: Optional[str] = None,
    db: Session = Depends(get_db), user=Depends(security.require_roles("admin", "verwalter", "helfer")),
):
    """Sendet die Sammel-PDF mehrerer Etiketten in einem Rutsch an einen Netzwerk-
    Brother-Drucker - wahlweise an den in den Einstellungen hinterlegten Drucker
    oder an eine explizit mitgegebene Drucker-IP (z.B. ein ueber das mobile
    Endgeraet erreichbarer Drucker). Siehe printing.py zu USB/Bluetooth."""
    articles = db.query(models.Article).filter(models.Article.id.in_(article_id)).all()
    by_id = {a.id: a for a in articles}
    ordered = [by_id[i] for i in article_id if i in by_id]
    if not ordered:
        raise HTTPException(status_code=404, detail="Keine passenden Artikel gefunden")

    printer_ip = _resolve_printer_ip(db, printer_ip)
    if not printer_ip:
        raise HTTPException(
            status_code=400,
            detail=(
                "Kein Drucker angegeben. Bitte in den Einstellungen unter 'Drucker' "
                "die IP-Adresse eines WLAN/LAN-Brother-Druckers hinterlegen oder eine "
                "erreichbare Drucker-IP mitgeben - alternativ die PDF herunterladen und "
                "ueber den Systemdruckdialog drucken (fuer USB/Bluetooth-Drucker)."
            ),
        )

    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    pdf_bytes = _build_bulk_label_pdf(ordered, _label_config(db), w, h)

    try:
        send_raw_to_network_printer(printer_ip, pdf_bytes)
    except PrintError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"ok": True, "message": f"Sammel-Druckauftrag ({len(ordered)} Etiketten) an {printer_ip} gesendet."}


@router.post("/article/{article_id}/print-network")
def print_label_network(article_id: int, width_mm: float = None, height_mm: float = None,
                         printer_ip: Optional[str] = None,
                         db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin", "verwalter", "helfer"))):
    """Sendet das Etikett direkt an einen Netzwerk-Brother-Drucker (Port 9100
    Rohdruck) - wahlweise an den in den Einstellungen hinterlegten Drucker oder an
    eine explizit mitgegebene Drucker-IP (z.B. ein ueber das mobile Endgeraet
    erreichbarer Drucker). Funktioniert nur bei netzwerkfaehigen Druckern, NICHT bei
    USB/Bluetooth - dafuer bitte den PDF-Download ueber den Systemdruckdialog nutzen."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")

    printer_ip = _resolve_printer_ip(db, printer_ip)
    if not printer_ip:
        raise HTTPException(
            status_code=400,
            detail=(
                "Kein Drucker angegeben. Bitte in den Einstellungen unter 'Drucker' "
                "die IP-Adresse eines WLAN/LAN-Brother-Druckers hinterlegen oder eine "
                "erreichbare Drucker-IP mitgeben - alternativ das Etikett als PDF ueber "
                "den Systemdruckdialog drucken (fuer USB/Bluetooth-Drucker)."
            ),
        )

    w = width_mm or float(get_setting(db, "label_width_mm", "62"))
    h = height_mm or float(get_setting(db, "label_height_mm", "29"))
    pdf_bytes = _build_label_pdf(a, _label_config(db), w, h)

    try:
        send_raw_to_network_printer(printer_ip, pdf_bytes)
    except PrintError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"ok": True, "message": f"Druckauftrag an {printer_ip} gesendet."}
