"""Vorlagen-gesteuerter PDF-Kopf/-Fuß (Briefkopf, Kopf-/Fußzeile).

Ohne konfigurierte Vorlage bleibt das bisherige Aussehen erhalten: Die Builder
zeichnen ihren gewohnten Kopf, und es wird lediglich die einheitliche Fußzeile
„Seite X von Y" ergänzt. Sobald für einen Dokumenttyp (oder global) eine AKTIVE
Vorlage existiert, übernimmt diese Kopf UND Fuß vollständig – die Builder lassen
dann ihren eigenen Kopf weg.

Elemente sind frei positioniert (Angaben in mm) und dürfen Platzhalter enthalten
(siehe PLATZHALTER). Die Werte dafür liefert `standardwerte()` zusammen mit dem,
was der jeweilige Builder über `werte=` mitgibt – so steht in der Kopfzeile einer
Inhaltsliste der Lagerort und im Fuß die Programmversion, statt eines
unspezifischen Platzhaltertextes.

Waagerechte Position
--------------------
`x` ist IMMER der Abstand zur Kante, an der das Element hängt: bei ``align`` =
"left" zur linken, bei "right" zur rechten; "center" heißt Seitenmitte (oder,
wenn x gesetzt ist, die Mitte an dieser Stelle). Dadurch sitzt dieselbe Vorlage
im Hoch- UND im Querformat richtig – ein Element am rechten Rand wandert im
Querformat mit, statt mitten auf der Seite zu stehen.
"""
import datetime as dt

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

from .settings_helper import get_setting
from .config import BRANDING_DIR, get_app_version

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
    {"key": "content_list", "label": "Inhaltsliste (Fach/Kiste/Tasche)"},
]

# Alle Platzhalter, die in Texten einer Vorlage stehen dürfen – mit Erklärung und
# einem Beispielwert für die Vorschau. Die Oberfläche zeigt genau diese Liste an,
# damit niemand raten muss, was es gibt.
PLATZHALTER = [
    {"key": "titel", "label": "Überschrift",
     "hint": "Art des Dokuments, z.B. „Inhaltsliste“ oder „Inventarliste“.",
     "beispiel": "Inhaltsliste"},
    {"key": "untertitel", "label": "Untertitel",
     "hint": "Worum es konkret geht – Name des Lagerorts, der Person, der Inventur.",
     "beispiel": "Seitentasche links"},
    {"key": "lagername", "label": "Lagerortname",
     "hint": "Name des Fachs/der Kiste/der Tasche, um die es geht.",
     "beispiel": "Seitentasche links"},
    {"key": "pfad", "label": "Lagerort-Pfad",
     "hint": "Vollständiger Weg dorthin, z.B. „Gerätehaus › KTW › Notfallrucksack“.",
     "beispiel": "Gerätehaus › KTW 1 › Notfallrucksack"},
    {"key": "fahrzeug", "label": "Fahrzeugname",
     "hint": "Fahrzeug, zu dem der Lagerort gehört – leer, wenn es keins gibt.",
     "beispiel": "KTW 1"},
    {"key": "standort", "label": "Standort",
     "hint": "Oberster Lagerort (Gebäude/Standort).",
     "beispiel": "Gerätehaus"},
    {"key": "abteilung", "label": "Abteilung",
     "hint": "Abteilung/Gliederung, zu der das Dokument gehört.",
     "beispiel": "Bereitschaft 1"},
    {"key": "verband", "label": "Verband",
     "hint": "Dachverband über dem Vereinsnamen, z.B. „Deutsches Rotes Kreuz“. Leer = Zeile entfällt.",
     "beispiel": "Deutsches Rotes Kreuz"},
    {"key": "organisation", "label": "Organisation",
     "hint": "Organisationsname aus den Einstellungen.",
     "beispiel": "DRK Ortsverein Musterstadt e.V."},
    {"key": "adresse", "label": "Anschrift (einzeilig)",
     "hint": "Anschrift aus den Einstellungen, Zeilen durch Mittelpunkt getrennt.",
     "beispiel": "Auf der Pirsch 19 · 66877 Ramstein"},
    {"key": "adresse1", "label": "Anschrift Zeile 1",
     "hint": "Erste Zeile der Anschrift (meist Straße).", "beispiel": "Auf der Pirsch 19"},
    {"key": "adresse2", "label": "Anschrift Zeile 2",
     "hint": "Zweite Zeile der Anschrift (meist PLZ und Ort).", "beispiel": "66877 Ramstein"},
    {"key": "adresse3", "label": "Anschrift Zeile 3",
     "hint": "Dritte Zeile der Anschrift, falls vorhanden.", "beispiel": ""},
    {"key": "datum", "label": "Datum mit Uhrzeit",
     "hint": "Zeitpunkt des Ausdrucks, z.B. 13.09.2026 14:20.", "beispiel": "13.09.2026 14:20"},
    {"key": "stand", "label": "Stand (kurz)",
     "hint": "Datum des Ausdrucks in Kurzform, z.B. 13.09.26.", "beispiel": "13.09.26"},
    {"key": "version", "label": "Programmversion",
     "hint": "Version des Inventarprogramms, das den Ausdruck erzeugt hat.",
     "beispiel": ""},
    {"key": "dateiname", "label": "Dateiname",
     "hint": "Name der erzeugten PDF-Datei.", "beispiel": "inhaltsliste.pdf"},
    {"key": "benutzer", "label": "Erzeugt von",
     "hint": "Anmeldename der Person, die den Ausdruck erzeugt hat.", "beispiel": "m.richter"},
    {"key": "seite", "label": "Seitenzahl", "hint": "Nummer der aktuellen Seite.", "beispiel": "1"},
    {"key": "seiten", "label": "Seiten gesamt", "hint": "Gesamtzahl der Seiten.", "beispiel": "1"},
]

def platzhalter_katalog() -> list:
    """Der Platzhalter-Katalog mit ausgefüllten Beispielwerten – für die Oberfläche."""
    katalog = [dict(p) for p in PLATZHALTER]
    for p in katalog:
        if p["key"] == "version":
            p["beispiel"] = get_app_version()
    return katalog


# Farben der Legende. Dieselben Töne verwenden die Listen zum Einfärben der
# Zeilen, damit Legende und Liste zusammenpassen.
FARBE_VERFALL = "#ffe699"    # gelb  – Haltbarkeit/Verfall im Blick behalten
FARBE_FUNKTION = "#bdd7ee"   # blau  – Funktion prüfen

# Wird verwendet, wenn KEINE Vorlage konfiguriert ist: nur einheitliche Fußzeile,
# der Kopf kommt weiter vom Builder (Aussehen unverändert).
_FOOTER_ONLY = {
    "_custom": False, "header_height_mm": 28, "footer_height_mm": 14, "watermark": {},
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

# Der Vordruck („Masterfolie"): Kopf mit Logo rechts, Lagerort/Fahrzeug links,
# Überschrift mittig; Fuß mit Anschrift, Stand/Version und der Farblegende.
# Weil alle Elemente an ihrer eigenen Kante hängen, sieht diese Vorlage im
# Hochformat und im Querformat gleich aus – es ist EINE Vorlage für beides.
VORDRUCK_TEMPLATE = {
    "header_height_mm": 38, "footer_height_mm": 28,
    "elements": [
        # Briefkopf rechts: Bildmarke, darunter der Schriftzug. Enthält das
        # hinterlegte Logo den Schriftzug bereits, lassen sich die beiden
        # Textzeilen einfach entfernen.
        {"region": "header", "type": "logo", "x": 15, "y": 6, "logo_h": 15, "align": "right"},
        {"region": "header", "type": "text", "text": "{verband}", "x": 15, "y": 26,
         "size": 9, "bold": True, "align": "right"},
        {"region": "header", "type": "text", "text": "{organisation}", "x": 15, "y": 30.5,
         "size": 8, "align": "right"},
        # Oben links: wohin das Blatt gehört.
        {"region": "header", "type": "text", "text": "{fahrzeug}", "x": 15, "y": 11, "size": 8, "align": "left"},
        {"region": "header", "type": "text", "text": "{standort}", "x": 15, "y": 15.5, "size": 8, "align": "left"},
        # Mitte: Überschrift, Untertitel, Weg.
        {"region": "header", "type": "text", "text": "{titel}", "x": 0, "y": 13, "size": 16, "bold": True, "align": "center"},
        {"region": "header", "type": "text", "text": "{untertitel}", "x": 0, "y": 20, "size": 11, "align": "center"},
        {"region": "header", "type": "text", "text": "{pfad}", "x": 0, "y": 25.5, "size": 8, "align": "center"},
        {"region": "header", "type": "linie", "x": 15, "y": 34, "thickness": 0.6},
        {"region": "footer", "type": "farbfeld", "text": "Verfall prüfen", "color": FARBE_VERFALL,
         "x": 15, "y": 23, "w": 10, "h": 3.2, "size": 7, "align": "right"},
        {"region": "footer", "type": "farbfeld", "text": "Funktion prüfen", "color": FARBE_FUNKTION,
         "x": 15, "y": 18.5, "w": 10, "h": 3.2, "size": 7, "align": "right"},
        {"region": "footer", "type": "linie", "x": 15, "y": 15, "thickness": 0.6},
        {"region": "footer", "type": "text", "text": "{organisation}", "x": 15, "y": 11, "size": 7, "align": "left"},
        {"region": "footer", "type": "text", "text": "{adresse1}", "x": 15, "y": 7.5, "size": 7, "align": "left"},
        {"region": "footer", "type": "text", "text": "{adresse2}", "x": 15, "y": 4, "size": 7, "align": "left"},
        {"region": "footer", "type": "text", "text": "Stand {stand}", "x": 0, "y": 11, "size": 7, "align": "center"},
        {"region": "footer", "type": "text", "text": "Version {version}", "x": 0, "y": 7.5, "size": 7, "align": "center"},
        {"region": "footer", "type": "text", "text": "{dateiname}", "x": 15, "y": 4, "size": 6, "align": "right"},
        {"region": "footer", "type": "text", "text": "Seite {seite}/{seiten}", "x": 15, "y": 7.5, "size": 7, "align": "right"},
    ],
}


def standardwerte(db, use_case: str = None, **extra) -> dict:
    """Die Werte aller Platzhalter: was sich aus Einstellungen und Zeitpunkt von
    selbst ergibt, plus alles, was der Builder über `extra` mitgibt (Lagerort,
    Fahrzeug, Dateiname …). Leere `extra`-Werte überschreiben nichts."""
    jetzt = dt.datetime.now()
    anschrift = [z.strip() for z in (get_setting(db, "org_address", "") or "").replace(";", "\n").splitlines()
                 if z.strip()]
    werte = {
        "titel": "", "untertitel": "", "lagername": "", "pfad": "", "fahrzeug": "",
        "standort": "", "abteilung": "", "benutzer": "",
        "organisation": get_setting(db, "org_name", "") or "",
        "verband": get_setting(db, "org_verband", "") or "",
        "adresse": " · ".join(anschrift),
        "adresse1": anschrift[0] if len(anschrift) > 0 else "",
        "adresse2": anschrift[1] if len(anschrift) > 1 else "",
        "adresse3": anschrift[2] if len(anschrift) > 2 else "",
        "datum": jetzt.strftime("%d.%m.%Y %H:%M"),
        "stand": jetzt.strftime("%d.%m.%y"),
        "version": get_app_version(),
        "dateiname": _standard_dateiname(use_case),
        "seite": "1", "seiten": "1",
    }
    for schluessel, wert in (extra or {}).items():
        if wert is None or wert == "":
            continue
        werte[schluessel] = str(wert)
    return werte


def beispielwerte(db, use_case: str = None, titel: str = "", untertitel: str = "") -> dict:
    """Werte für die Vorschau: alles Echte (Organisation, Anschrift, Version,
    Datum) bleibt echt, alles Dokumentabhängige bekommt ein Beispiel. So sieht
    der Administrator, wie die Vorlage später aussieht - und nicht bloß
    geschweifte Klammern."""
    werte = standardwerte(db, use_case)
    for p in PLATZHALTER:
        if not werte.get(p["key"]) and p.get("beispiel"):
            werte[p["key"]] = p["beispiel"]
    if titel:
        werte["titel"] = titel
    if untertitel:
        werte["untertitel"] = untertitel
    return werte


def _standard_dateiname(use_case: str = None) -> str:
    if not use_case:
        return "dokument.pdf"
    return f"{use_case}.pdf"


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
        "background_landscape_filename": t.background_landscape_filename or "",
        "background_landscape_kind": t.background_landscape_kind or "",
        "watermark": t.watermark or {},
    }


def wasserzeichen_fuer(db, use_case, eigenes=None):
    """Welches Wasserzeichen fuer dieses Dokument gilt: das eigene des Lagerorts,
    sonst das der Vorlage, sonst keins."""
    from . import wasserzeichen as _wz
    if _wz.ist_aktiv(eigenes):
        return _wz.normalisieren(eigenes)
    aus_vorlage = resolve_template(db, use_case).get("watermark")
    return _wz.normalisieren(aus_vorlage) if _wz.ist_aktiv(aus_vorlage) else None


def _hintergrund_datei(tmpl: dict, quer: bool):
    """(Pfad, Art) des Briefpapiers fuer diese Seitenlage.

    Fuer das Querformat gibt es eine eigene Datei. Fehlt sie, wird NICHT die
    hochkante genommen - ein um 90 Grad gekipptes oder breitgezogenes Briefpapier
    sieht schlechter aus als gar keines, und man merkt es erst am Drucker.
    """
    if not tmpl.get("_custom"):
        return None, ""
    if quer:
        name = tmpl.get("background_landscape_filename") or ""
        art = tmpl.get("background_landscape_kind") or ""
    else:
        name = tmpl.get("background_filename") or ""
        art = tmpl.get("background_kind") or ""
    if not name or not art:
        return None, ""
    pfad = BRANDING_DIR / name
    return (pfad, art) if pfad.exists() else (None, "")


def _unterlage(pfad, art, breite, hoehe):
    """Das Briefpapier auf genau die Seitengroesse gebracht.

    Ohne das Skalieren behaelt die Hintergrundseite ihre eigene Groesse: ein
    A4-Vordruck hinter einer A5-Liste haette die Liste in die obere Ecke gedraengt.
    """
    import io as _io
    from pypdf import PageObject, PdfReader, Transformation

    if art == "image":
        return PdfReader(_io.BytesIO(_image_page_pdf(pfad, breite, hoehe))).pages[0]
    quelle = PdfReader(_io.BytesIO(pfad.read_bytes())).pages[0]
    qb = float(quelle.mediabox.width) or breite
    qh = float(quelle.mediabox.height) or hoehe
    if abs(qb - breite) < 1 and abs(qh - hoehe) < 1:
        return quelle
    seite = PageObject.create_blank_page(width=breite, height=hoehe)
    seite.merge_transformed_page(quelle, Transformation().scale(breite / qb, hoehe / qh))
    return seite


def finalize(db, use_case, pdf_bytes, wasserzeichen_daten=None):
    """Legt hinter den fertigen Inhalt, was dahinter gehoert: das Briefpapier
    (eigener Vordruck als PDF oder Bild) und das monochrome Wasserzeichen.

    Beides wird UNTER den Inhalt gelegt, nicht darueber - sonst laege ein
    Farbschleier auf den Zahlen, und genau die will man ja lesen.
    `wasserzeichen_daten` schlaegt das Wasserzeichen der Vorlage; so kann ein
    einzelner Lagerort ein eigenes Motiv bekommen.
    """
    import io as _io
    from . import wasserzeichen as _wz

    tmpl = resolve_template(db, use_case)
    wz = wasserzeichen_daten if _wz.ist_aktiv(wasserzeichen_daten) else tmpl.get("watermark")
    wz = wz if _wz.ist_aktiv(wz) else None
    hat_hintergrund = bool((tmpl.get("background_filename") and tmpl.get("background_kind"))
                           or (tmpl.get("background_landscape_filename")
                               and tmpl.get("background_landscape_kind")))
    if not hat_hintergrund and wz is None:
        return pdf_bytes

    try:
        from pypdf import PdfReader, PdfWriter
        inhalt = PdfReader(_io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for cpage in inhalt.pages:
            w = float(cpage.mediabox.width)
            h = float(cpage.mediabox.height)
            pfad, art = _hintergrund_datei(tmpl, quer=(w > h))
            unterlage = _unterlage(pfad, art, w, h) if pfad is not None else None
            if wz is not None:
                marke = PdfReader(_io.BytesIO(_wz.seite_pdf(wz, w, h))).pages[0]
                if unterlage is None:
                    unterlage = marke
                else:
                    unterlage.merge_page(marke)
            if unterlage is None:
                writer.add_page(cpage)
                continue
            unterlage.merge_page(cpage)
            writer.add_page(unterlage)
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
    """Pfad der Logodatei - egal ob Bild oder SVG (siehe _logo_quelle)."""
    name = get_setting(db, "logo_filename", "")
    if not name:
        return None
    path = BRANDING_DIR / name
    return path if path.exists() else None


# Umgewandelte SVG-Logos, damit nicht jede Seite neu geparst wird.
# Schluessel: (Pfad, Aenderungszeit) - ein ausgetauschtes Logo wird so bemerkt.
_SVG_ZEICHNUNGEN = {}


def _svg_zeichnung(pfad):
    """Ein SVG-Logo als reportlab-Zeichnung.

    Bis 1.104.0 wurden SVG-Logos in PDFs schlicht uebersprungen - hochladen
    liess sich eins, im Ausdruck fehlte es dann stillschweigend. Das ist genau
    der Fall, der niemandem auffaellt, bis der erste Ausdruck beim Vorstand
    liegt.
    """
    try:
        schluessel = (str(pfad), pfad.stat().st_mtime)
    except OSError:
        return None
    if schluessel in _SVG_ZEICHNUNGEN:
        return _SVG_ZEICHNUNGEN[schluessel]
    zeichnung = None
    try:
        from svglib.svglib import svg2rlg
        zeichnung = svg2rlg(str(pfad))
    except Exception:
        zeichnung = None
    _SVG_ZEICHNUNGEN.clear()
    _SVG_ZEICHNUNGEN[schluessel] = zeichnung
    return zeichnung


def _logo_quelle(db):
    """(art, quelle, seitenverhaeltnis) - art ist "svg", "bild" oder None."""
    pfad = _logo_path(db)
    if pfad is None:
        return None, None, None
    if pfad.suffix.lower() == ".svg":
        zeichnung = _svg_zeichnung(pfad)
        if zeichnung is None or not zeichnung.height:
            return None, None, None
        return "svg", zeichnung, (zeichnung.width / zeichnung.height)
    try:
        from reportlab.lib.utils import ImageReader
        breite, hoehe = ImageReader(str(pfad)).getSize()
        if not breite or not hoehe:
            return None, None, None
        return "bild", str(pfad), breite / hoehe
    except Exception:
        return None, None, None


def logo_verfuegbar(db) -> dict:
    """Was das hinterlegte Logo fuer PDFs bedeutet - fuer die Oberflaeche, damit
    ein nicht darstellbares Logo auffaellt, bevor gedruckt wird."""
    name = get_setting(db, "logo_filename", "")
    if not name:
        return {"vorhanden": False, "in_pdf": False,
                "hinweis": "Kein Logo hinterlegt - der Briefkopf bleibt ohne Bildmarke."}
    art, _quelle, _v = _logo_quelle(db)
    if art:
        return {"vorhanden": True, "in_pdf": True, "art": art, "hinweis": ""}
    if name.lower().endswith(".svg"):
        return {"vorhanden": True, "in_pdf": False, "art": "svg",
                "hinweis": ("Dieses SVG lässt sich nicht in PDFs zeichnen. Bitte das Logo "
                            "zusätzlich als PNG hochladen.")}
    return {"vorhanden": True, "in_pdf": False, "art": "bild",
            "hinweis": "Die Logodatei lässt sich nicht lesen."}


def _linke_kante(align: str, x_mm: float, seitenbreite: float, elementbreite: float = 0.0) -> float:
    """Linke Kante eines Elements bekannter Breite – x zählt immer von der Kante,
    an der das Element hängt. Damit stimmt dieselbe Vorlage in Hoch und Quer."""
    if align == "right":
        return seitenbreite - x_mm * mm - elementbreite
    if align == "center":
        mitte = x_mm * mm if x_mm else seitenbreite / 2.0
        return mitte - elementbreite / 2.0
    return x_mm * mm


def make_canvas(db, template: dict, title: str = "", subtitle: str = "", werte: dict = None):
    """Canvas-Klasse, die Kopf und Fuß der Vorlage auf jede Seite zeichnet.

    `werte` sind die Platzhalterwerte; fehlt es, werden die Standardwerte
    verwendet und `title`/`subtitle` eingesetzt (Aufrufe alten Stils)."""
    if werte is None:
        werte = standardwerte(db)
    werte = dict(werte)
    if title:
        werte["titel"] = title
    if subtitle:
        werte["untertitel"] = subtitle
    logo_art, logo_quelle, logo_ratio = _logo_quelle(db)
    elements = template.get("elements") or []

    def _fmt(text, page, total):
        s = text or ""
        if "{" not in s:
            return s
        eigene = dict(werte)
        eigene["seite"] = str(page)
        eigene["seiten"] = str(total)
        for schluessel, wert in eigene.items():
            marke = "{" + schluessel + "}"
            if marke in s:
                s = s.replace(marke, wert or "")
        return s.strip()

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

        # -- einzelne Elementarten ------------------------------------------
        def _zeichne_logo(self, el, w, cy):
            if logo_art is None or not logo_ratio:
                return
            lh = float(el.get("logo_h", 16) or 16) * mm
            breite = lh * logo_ratio
            x = _linke_kante(el.get("align", "left"), float(el.get("x", 0) or 0), w, breite)
            try:
                if logo_art == "svg":
                    from reportlab.graphics import renderPDF
                    from copy import deepcopy
                    zeichnung = deepcopy(logo_quelle)
                    faktor = lh / zeichnung.height
                    zeichnung.scale(faktor, faktor)
                    zeichnung.width *= faktor
                    zeichnung.height *= faktor
                    renderPDF.draw(zeichnung, self, x, cy - lh)
                else:
                    self.drawImage(logo_quelle, x, cy - lh, width=breite, height=lh,
                                   preserveAspectRatio=True, mask="auto")
            except Exception:
                pass

        def _zeichne_linie(self, el, w, cy):
            x_mm = float(el.get("x", 0) or 0)
            breite_mm = float(el.get("w", 0) or 0)
            breite = breite_mm * mm if breite_mm else (w - 2 * x_mm * mm)
            x = _linke_kante(el.get("align", "left"), x_mm, w, breite)
            self.setLineWidth(float(el.get("thickness", 0.5) or 0.5))
            self.setStrokeColor(_farbe(el.get("color") or "#888888"))
            self.line(x, cy, x + breite, cy)
            self.setStrokeGray(0)

        def _zeichne_farbfeld(self, el, w, cy, page, total):
            """Farbiges Feld mit Beschriftung daneben – die Legende des Vordrucks."""
            feld_b = float(el.get("w", 10) or 10) * mm
            feld_h = float(el.get("h", 3.2) or 3.2) * mm
            groesse = float(el.get("size", 7) or 7)
            text = _fmt(el.get("text", ""), page, total)
            abstand = 2 * mm if text else 0
            textbreite = self.stringWidth(text, "Helvetica", groesse) if text else 0
            gesamt = feld_b + abstand + textbreite
            x = _linke_kante(el.get("align", "left"), float(el.get("x", 0) or 0), w, gesamt)
            self.setFillColor(_farbe(el.get("color") or "#dddddd"))
            self.setStrokeGray(0.6)
            self.setLineWidth(0.3)
            self.rect(x, cy - feld_h * 0.75, feld_b, feld_h, fill=1, stroke=1)
            if text:
                self.setFont("Helvetica", groesse)
                self.setFillGray(0.25)
                self.drawString(x + feld_b + abstand, cy, text)
            self.setFillGray(0)
            self.setStrokeGray(0)

        def _zeichne_text(self, el, w, cy, region, page, total):
            s = _fmt(el.get("text", ""), page, total)
            if not s:
                return
            self.setFont("Helvetica-Bold" if el.get("bold") else "Helvetica",
                         float(el.get("size", 9) or 9))
            self.setFillGray(0.15 if region == "header" else 0.45)
            align = el.get("align", "left")
            x_mm = float(el.get("x", 0) or 0)
            if align == "center":
                self.drawCentredString(w / 2.0 if not x_mm else x_mm * mm, cy, s)
            elif align == "right":
                self.drawRightString(w - x_mm * mm, cy, s)
            else:
                self.drawString(x_mm * mm, cy, s)

        def _draw(self, page, total):
            w, h = self._pagesize
            for el in elements:
                region = el.get("region", "header")
                y = float(el.get("y", 0) or 0)
                cy = (h - y * mm) if region == "header" else (y * mm)
                art = el.get("type") or "text"
                try:
                    if art == "logo":
                        self._zeichne_logo(el, w, cy)
                    elif art == "linie":
                        self._zeichne_linie(el, w, cy)
                    elif art == "farbfeld":
                        self._zeichne_farbfeld(el, w, cy, page, total)
                    else:
                        self._zeichne_text(el, w, cy, region, page, total)
                except Exception:
                    # Ein fehlerhaftes Element darf nie das ganze Dokument verhindern.
                    continue

    return TemplatedCanvas


def _farbe(wert: str):
    from reportlab.lib import colors
    try:
        return colors.HexColor(wert if wert.startswith("#") else "#" + wert)
    except Exception:
        return colors.grey


def doc_setup(db, use_case, title, subtitle="", default_top_mm=14, default_bottom_mm=14,
              werte: dict = None, **extra):
    """Liefert (topMargin, bottomMargin, draw_inline_header, canvasmaker) für einen
    Builder. Ohne konfigurierte Vorlage bleibt der Builder-Kopf erhalten.

    `extra` sind zusätzliche Platzhalterwerte des Builders (lagername, fahrzeug,
    pfad, dateiname …); `werte` kann ein bereits fertiges Wörterbuch sein."""
    tmpl = resolve_template(db, use_case)
    if werte is None:
        werte = standardwerte(db, use_case, titel=title, untertitel=subtitle, **extra)
    cm = make_canvas(db, tmpl, title, subtitle, werte)
    if tmpl.get("_custom"):
        return tmpl["header_height_mm"] * mm, tmpl["footer_height_mm"] * mm, False, cm
    return default_top_mm * mm, default_bottom_mm * mm, True, cm
