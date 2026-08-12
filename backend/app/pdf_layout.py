"""Vorlagen-gesteuerter PDF-Kopf/-Fuß (Briefkopf, Kopf-/Fußzeile).

Ohne konfigurierte Vorlage bleibt das bisherige Aussehen erhalten: Die Builder
zeichnen ihren gewohnten Kopf, und es wird lediglich die einheitliche Fußzeile
„Seite X von Y" ergänzt. Sobald für einen Dokumenttyp (oder global) eine AKTIVE
Vorlage existiert, übernimmt diese Kopf UND Fuß vollständig – die Builder lassen
dann ihren eigenen Kopf weg. Elemente sind frei positioniert (mm) und dürfen
Platzhalter enthalten: {titel} {untertitel} {organisation} {datum} {seite} {seiten}.
"""
import datetime as dt

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

from .settings_helper import get_setting
from .config import BRANDING_DIR

# Dokumenttypen, für die eine eigene Vorlage möglich ist.
DOC_USE_CASES = [
    {"key": "receipt_issue", "label": "Ausgabequittung"},
    {"key": "receipt_return", "label": "Rückgabequittung"},
    {"key": "key_doc", "label": "Schlüssel-Ausgabedokument"},
    {"key": "report", "label": "Schaden-/Verlustmeldung"},
    {"key": "inspection", "label": "Prüfprotokoll"},
    {"key": "logbook", "label": "Fahrzeug-Logbuch"},
    {"key": "list_inventory", "label": "Inventarliste"},
    {"key": "list_person", "label": "Materialliste je Person"},
    {"key": "list_inventur", "label": "Inventur-Bericht"},
    {"key": "schliessplan", "label": "Schließplan"},
]

# Wird verwendet, wenn KEINE Vorlage konfiguriert ist: nur einheitliche Fußzeile,
# der Kopf kommt weiter vom Builder (Aussehen unverändert).
_FOOTER_ONLY = {
    "_custom": False, "header_height_mm": 28, "footer_height_mm": 14,
    "elements": [{"region": "footer", "type": "text", "text": "Seite {seite} von {seiten}",
                  "x": 0, "y": 8, "size": 7, "align": "center"}],
}

# Startpunkt für neue Vorlagen im Editor (kompletter Briefkopf + Fuß).
STARTER_TEMPLATE = {
    "header_height_mm": 30, "footer_height_mm": 14,
    "elements": [
        {"region": "header", "type": "logo", "x": 16, "y": 8, "logo_h": 16},
        {"region": "header", "type": "text", "text": "{titel}", "x": 42, "y": 12, "size": 16, "bold": True, "align": "left"},
        {"region": "header", "type": "text", "text": "{untertitel}", "x": 42, "y": 19, "size": 11, "bold": False, "align": "left"},
        {"region": "header", "type": "text", "text": "{organisation} · Stand {datum}", "x": 42, "y": 25, "size": 8, "bold": False, "align": "left"},
        {"region": "footer", "type": "text", "text": "{organisation}", "x": 16, "y": 8, "size": 7, "align": "left"},
        {"region": "footer", "type": "text", "text": "Seite {seite} von {seiten}", "x": 0, "y": 8, "size": 7, "align": "center"},
    ],
}


def resolve_template(db, use_case: str = None) -> dict:
    from . import models
    if use_case:
        t = db.query(models.DocTemplate).filter(
            models.DocTemplate.use_case == use_case, models.DocTemplate.active == True).first()  # noqa: E712
        if t:
            return _as_dict(t)
    g = db.query(models.DocTemplate).filter(
        models.DocTemplate.use_case.is_(None), models.DocTemplate.active == True).first()  # noqa: E712
    if g:
        return _as_dict(g)
    return _FOOTER_ONLY


def _as_dict(t) -> dict:
    return {
        "_custom": True,
        "header_height_mm": t.header_height_mm or 28,
        "footer_height_mm": t.footer_height_mm or 14,
        "elements": t.elements or [],
        "background_filename": t.background_filename or "",
        "background_kind": t.background_kind or "",
    }


def finalize(db, use_case, pdf_bytes):
    """Legt – falls für den Dokumenttyp eine Vorlage mit Hintergrund (Briefpapier als
    PDF oder Bild) aktiv ist – diesen Hintergrund seitenfüllend hinter den Inhalt.
    Ohne Hintergrund werden die Bytes unverändert zurückgegeben."""
    import io as _io
    tmpl = resolve_template(db, use_case)
    bgfile = tmpl.get("background_filename")
    kind = tmpl.get("background_kind")
    if not tmpl.get("_custom") or not bgfile or not kind:
        return pdf_bytes
    path = BRANDING_DIR / bgfile
    if not path.exists():
        return pdf_bytes
    try:
        from pypdf import PdfReader, PdfWriter
        content = PdfReader(_io.BytesIO(pdf_bytes))
        bg_pdf_bytes = None
        if kind == "pdf":
            bg_pdf_bytes = path.read_bytes()
        writer = PdfWriter()
        for cpage in content.pages:
            w = float(cpage.mediabox.width)
            h = float(cpage.mediabox.height)
            if kind == "image":
                base_reader = PdfReader(_io.BytesIO(_image_page_pdf(path, w, h)))
            else:
                base_reader = PdfReader(_io.BytesIO(bg_pdf_bytes))
            base = base_reader.pages[0]
            base.merge_page(cpage)
            writer.add_page(base)
        out = _io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        return pdf_bytes


def _image_page_pdf(img_path, w_pt, h_pt) -> bytes:
    """Erzeugt eine einseitige PDF (w×h Punkte) mit dem Bild seitenfüllend."""
    import io as _io
    buf = _io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=(w_pt, h_pt))
    try:
        c.drawImage(str(img_path), 0, 0, width=w_pt, height=h_pt, preserveAspectRatio=False, mask="auto")
    except Exception:
        pass
    c.showPage()
    c.save()
    return buf.getvalue()


def _logo_path(db):
    name = get_setting(db, "logo_filename", "")
    if not name or name.lower().endswith(".svg"):
        return None
    path = BRANDING_DIR / name
    return path if path.exists() else None


def make_canvas(db, template: dict, title: str, subtitle: str = ""):
    org = get_setting(db, "org_name", "")
    now = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    logo_path = _logo_path(db)
    elements = template.get("elements") or []
    logo_ratio = None
    if logo_path is not None:
        try:
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(str(logo_path)).getSize()
            logo_ratio = (iw / ih) if iw and ih else None
        except Exception:
            logo_path = None

    def _fmt(text, page, total):
        return (text or "").replace("{titel}", title or "").replace("{untertitel}", subtitle or "") \
            .replace("{organisation}", org).replace("{datum}", now) \
            .replace("{seite}", str(page)).replace("{seiten}", str(total))

    class TemplatedCanvas(_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for st in self._saved:
                self.__dict__.update(st)
                self._draw(self._pageNumber, total)
                _canvas.Canvas.showPage(self)
            _canvas.Canvas.save(self)

        def _draw(self, page, total):
            w, h = self._pagesize
            for el in elements:
                region = el.get("region", "header")
                x = float(el.get("x", 0) or 0)
                y = float(el.get("y", 0) or 0)
                cy = (h - y * mm) if region == "header" else (y * mm)
                if el.get("type") == "logo":
                    if logo_path is None or logo_ratio is None:
                        continue
                    lh = float(el.get("logo_h", 16) or 16) * mm
                    try:
                        self.drawImage(str(logo_path), x * mm, cy - lh, width=lh * logo_ratio, height=lh,
                                       preserveAspectRatio=True, mask="auto")
                    except Exception:
                        pass
                    continue
                s = _fmt(el.get("text", ""), page, total)
                if not s:
                    continue
                self.setFont("Helvetica-Bold" if el.get("bold") else "Helvetica", float(el.get("size", 9) or 9))
                self.setFillGray(0.15 if region == "header" else 0.45)
                align = el.get("align", "left")
                if align == "center":
                    self.drawCentredString(w / 2.0 if not x else x * mm, cy, s)
                elif align == "right":
                    self.drawRightString(w - x * mm, cy, s)
                else:
                    self.drawString(x * mm, cy, s)

    return TemplatedCanvas


def doc_setup(db, use_case, title, subtitle="", default_top_mm=14, default_bottom_mm=14):
    """Liefert (topMargin, bottomMargin, draw_inline_header, canvasmaker) für einen
    Builder. Ohne konfigurierte Vorlage bleibt der Builder-Kopf erhalten."""
    tmpl = resolve_template(db, use_case)
    cm = make_canvas(db, tmpl, title, subtitle)
    if tmpl.get("_custom"):
        return tmpl["header_height_mm"] * mm, tmpl["footer_height_mm"] * mm, False, cm
    return default_top_mm * mm, default_bottom_mm * mm, True, cm
