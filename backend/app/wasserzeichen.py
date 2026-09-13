"""Monochrome Wasserzeichen fuer erzeugte PDFs.

Ein Wasserzeichen liegt blass HINTER dem Inhalt und sagt auf einen Blick, wozu
ein Blatt gehoert: der Blutstropfen zum Blutspendetermin, die Schneeflocke zum
Winterdienst, die Blutdruckmanschette zur Sanitaetstasche. Auf einem Stapel
ausgedruckter Listen findet man so das richtige Blatt, ohne zu lesen.

Monochrom heisst: EINE Farbe, frei waehlbar, mit einstellbarer Deckkraft. Das
ist Absicht und keine Einschraenkung - ein mehrfarbiges Bild hinter Tabellentext
macht die Zahlen unleserlich, und beim Ausdruck auf einem Schwarzweissdrucker
wird daraus ohnehin ein grauer Fleck.

Mitgelieferte Motive sind als Vektorzeichnung hinterlegt (keine Bilddateien):
sie bleiben in jeder Groesse scharf, brauchen keinen Speicher und lassen sich in
jeder Farbe ausgeben. Eigene Motive kann der Administrator hochladen; sie werden
beim Zeichnen auf dieselbe eine Farbe reduziert.
"""
import io
import math
import os

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

from .config import BRANDING_DIR

# Dateiname-Vorsatz der hochgeladenen Motive im Branding-Ordner.
DATEI_VORSATZ = "wm_"
ERLAUBTE_ENDUNGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

POSITIONEN = [
    {"key": "mitte", "label": "Mitte"},
    {"key": "oben_links", "label": "oben links"},
    {"key": "oben_rechts", "label": "oben rechts"},
    {"key": "unten_links", "label": "unten links"},
    {"key": "unten_rechts", "label": "unten rechts"},
    {"key": "kachel", "label": "über die ganze Seite gekachelt"},
]

MOTIVE = [
    {"key": "blutstropfen", "label": "Blutstropfen (Blutspende)"},
    {"key": "kreuz", "label": "Kreuz"},
    {"key": "schneeflocke", "label": "Schneeflocke"},
    {"key": "blutdruckmanschette", "label": "Blutdruckmanschette"},
    {"key": "infusionsbeutel", "label": "Infusionsbeutel mit Leitung"},
    {"key": "spritze", "label": "Spritze"},
    {"key": "nadeln", "label": "Gekreuzte Nadeln"},
    {"key": "pflaster", "label": "Gekreuzte Pflaster"},
    {"key": "verbandsrolle", "label": "Verbandsrolle"},
    {"key": "sauerstoffflasche", "label": "Sauerstoffflasche"},
    {"key": "herz_ekg", "label": "Herz mit EKG-Linie"},
]

STANDARD = {
    "art": "",                  # "" = keins | "motiv" | "bild"
    "motiv": "blutstropfen",
    "datei": "",
    "farbe": "#999999",
    "deckkraft": 10,            # Prozent
    "groesse_mm": 120,
    "drehung": 0,               # Grad
    "position": "mitte",
}


def normalisieren(daten) -> dict:
    """Nimmt, was gespeichert wurde, und macht daraus verlaessliche Werte.

    Alles wird begrenzt: eine Deckkraft von 90 % waere kein Wasserzeichen mehr,
    sondern ein Balken quer ueber der Liste.
    """
    w = dict(STANDARD)
    if isinstance(daten, dict):
        for k in STANDARD:
            if k in daten and daten[k] is not None:
                w[k] = daten[k]
    w["art"] = w["art"] if w["art"] in ("motiv", "bild") else ""
    w["motiv"] = w["motiv"] if w["motiv"] in {m["key"] for m in MOTIVE} else "blutstropfen"
    w["position"] = w["position"] if w["position"] in {p["key"] for p in POSITIONEN} else "mitte"
    w["datei"] = os.path.basename(str(w["datei"] or ""))
    farbe = str(w["farbe"] or "#999999")
    w["farbe"] = farbe if farbe.startswith("#") and len(farbe) == 7 else "#999999"
    w["deckkraft"] = max(1, min(60, int(float(w["deckkraft"] or 10))))
    w["groesse_mm"] = max(10, min(400, float(w["groesse_mm"] or 120)))
    w["drehung"] = float(w["drehung"] or 0) % 360
    return w


def ist_aktiv(daten) -> bool:
    w = normalisieren(daten)
    if w["art"] == "motiv":
        return True
    if w["art"] == "bild":
        return bool(w["datei"]) and (BRANDING_DIR / w["datei"]).exists()
    return False


# ---------------------------------------------------------------------------
# Die Motive. Jedes zeichnet in ein Quadrat 0..100 (Ursprung unten links); die
# Platzierung auf der Seite macht _einmal_zeichnen().
# ---------------------------------------------------------------------------

def _blutstropfen(c):
    p = c.beginPath()
    p.moveTo(50, 97)
    p.curveTo(34, 74, 22, 57, 22, 42)
    p.curveTo(22, 25, 35, 10, 50, 10)
    p.curveTo(65, 10, 78, 25, 78, 42)
    p.curveTo(78, 57, 66, 74, 50, 97)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _kreuz(c):
    a, b = 36.0, 64.0      # Innenkanten des Kreuzes
    p = c.beginPath()
    p.moveTo(a, 6); p.lineTo(b, 6); p.lineTo(b, a); p.lineTo(94, a)
    p.lineTo(94, b); p.lineTo(b, b); p.lineTo(b, 94); p.lineTo(a, 94)
    p.lineTo(a, b); p.lineTo(6, b); p.lineTo(6, a); p.lineTo(a, a)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _schneeflocke(c):
    c.setLineWidth(4)
    c.setLineCap(1)
    for i in range(6):
        c.saveState()
        c.translate(50, 50)
        c.rotate(i * 60)
        c.line(0, 0, 0, 46)
        for hoehe, laenge in ((24, 13), (36, 10)):
            c.line(0, hoehe, laenge * 0.7, hoehe + laenge * 0.7)
            c.line(0, hoehe, -laenge * 0.7, hoehe + laenge * 0.7)
        c.restoreState()
    c.circle(50, 50, 6, stroke=1, fill=0)


def _blutdruckmanschette(c):
    # Manschette mit Klettlasche
    c.setLineWidth(4)
    c.roundRect(10, 42, 58, 44, 8, stroke=1, fill=0)
    c.setLineWidth(3)
    c.line(26, 42, 26, 86)
    c.rect(68, 58, 5, 10, stroke=1, fill=0)             # Schlauchnippel
    # Schlauch zum Manometer
    p = c.beginPath()
    p.moveTo(73, 63)
    p.curveTo(86, 60, 90, 46, 85, 36)
    c.drawPath(p, stroke=1, fill=0)
    # Manometer mit Skala
    c.setLineWidth(4)
    c.circle(78, 22, 16, stroke=1, fill=0)
    c.setLineWidth(2)
    for winkel in (215, 260, 305, 350):
        r = math.radians(winkel)
        c.line(78 + 11 * math.cos(r), 22 + 11 * math.sin(r),
               78 + 14 * math.cos(r), 22 + 14 * math.sin(r))
    c.setLineWidth(3)
    c.line(78, 22, 87, 30)
    c.circle(78, 22, 2.5, stroke=0, fill=1)


def _infusionsbeutel(c):
    c.setLineWidth(4)
    c.arc(44, 88, 56, 100, 0, 180)                      # Aufhaenger
    c.roundRect(28, 38, 44, 54, 7, stroke=1, fill=0)    # Beutel
    c.setLineWidth(3)
    c.line(34, 64, 66, 64)                              # Fuellstand
    c.line(34, 72, 66, 72)
    p = c.beginPath()                                   # Auslauf
    p.moveTo(44, 38); p.lineTo(46, 32); p.lineTo(54, 32); p.lineTo(56, 38)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(4)
    c.roundRect(44, 16, 12, 16, 4, stroke=1, fill=0)    # Tropfkammer
    c.circle(50, 24, 2.5, stroke=0, fill=1)
    c.setLineWidth(3)
    c.line(50, 16, 50, 6)                               # Leitung, dann zur Kanuele
    p = c.beginPath()
    p.moveTo(50, 6)
    p.curveTo(58, 2, 66, 8, 74, 4)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(2)
    c.rect(46, 8, 8, 6, stroke=1, fill=0)               # Rollenklemme


def _spritze(c, laenge=1.0):
    """Eine Spritze, waagerecht: Kolben links, Kanuele rechts."""
    c.setLineWidth(4)
    c.rect(26, 38, 44, 24, stroke=1, fill=0)        # Zylinder
    c.setLineWidth(3)
    c.line(26, 34, 26, 66)                          # Griffplatte
    c.line(14, 50, 26, 50)                          # Kolbenstange
    c.line(10, 40, 10, 60)                          # Daumenteller
    c.line(10, 50, 14, 50)
    for x in (38, 46, 54, 62):                      # Teilstriche
        c.line(x, 56, x, 62)
    p = c.beginPath()                               # Konus
    p.moveTo(70, 44); p.lineTo(78, 48); p.lineTo(78, 52); p.lineTo(70, 56)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(3)
    c.line(78, 50, 96, 50)                          # Kanuele
    c.setLineWidth(1.5)
    c.line(92, 50, 96, 47)                          # Schliff


def _nadel(c):
    """Eine einzelne Kanuele mit Ansatzkonus - Grundform fuer die Kreuzung."""
    c.setLineWidth(3.5)
    c.roundRect(4, 44, 20, 12, 3, stroke=1, fill=0)     # Luer-Ansatz
    c.line(10, 44, 10, 56)
    p = c.beginPath()                                   # Konus
    p.moveTo(24, 46); p.lineTo(34, 48.5); p.lineTo(34, 51.5); p.lineTo(24, 54)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(3)
    c.line(34, 50, 96, 50)                              # Kanuele
    c.setLineWidth(1.5)
    c.line(89, 50, 96, 45.5)                            # Schliff


def _nadeln(c):
    # Gegenlaeufig gedreht - so liegen die Ansaetze an entgegengesetzten Ecken
    # und es sieht nach gekreuzten Nadeln aus statt nach zwei Paddeln.
    for winkel in (26, 154):
        c.saveState()
        c.translate(50, 50)
        c.rotate(winkel)
        c.translate(-50, -50)
        _nadel(c)
        c.restoreState()


def _pflaster_einzeln(c, mit_auflage: bool):
    c.setLineWidth(4)
    c.roundRect(8, 38, 84, 24, 11, stroke=1, fill=0)
    if not mit_auflage:
        return
    c.setLineWidth(3)
    c.rect(37, 43, 26, 14, stroke=1, fill=0)            # Wundauflage
    for x in (43, 50, 57):                              # Loecher
        for y in (47.5, 52.5):
            c.circle(x, y, 1.5, stroke=0, fill=1)


def _pflaster(c):
    # Die Auflage bekommt nur das obere Pflaster; zweimal uebereinander gaebe in
    # der Mitte einen dunklen Fleck statt eines erkennbaren Kreuzes.
    for winkel, auflage in ((-32, False), (32, True)):
        c.saveState()
        c.translate(50, 50)
        c.rotate(winkel)
        c.translate(-50, -50)
        _pflaster_einzeln(c, auflage)
        c.restoreState()


def _verbandsrolle(c):
    c.setLineWidth(4)
    c.circle(40, 58, 32, stroke=1, fill=0)
    c.circle(40, 58, 11, stroke=1, fill=0)
    # Herausgezogenes Bandende als Streifen mit sichtbarer Breite
    p = c.beginPath()
    p.moveTo(64, 37)
    p.curveTo(80, 30, 84, 20, 94, 14)
    p.lineTo(86, 4)
    p.curveTo(76, 10, 70, 16, 54, 22)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(3)
    c.line(88, 10, 92, 7)                               # Bruchkante des Bandes


def _sauerstoffflasche(c):
    c.setLineWidth(4)
    c.roundRect(32, 6, 36, 72, 16, stroke=1, fill=0)    # Flasche
    c.rect(43, 78, 14, 8, stroke=1, fill=0)             # Hals
    c.setLineWidth(3)
    c.circle(50, 91, 8, stroke=1, fill=0)               # Handrad
    c.line(42, 91, 58, 91)
    c.line(50, 83, 50, 99)
    c.line(34, 62, 66, 62)                              # Schulterband
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(50, 34, "O")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(58, 31, "2")


def _herz_ekg(c):
    c.setLineWidth(4)
    p = c.beginPath()
    p.moveTo(50, 22)
    p.curveTo(16, 48, 14, 74, 32, 82)
    p.curveTo(42, 87, 48, 80, 50, 74)
    p.curveTo(52, 80, 58, 87, 68, 82)
    p.curveTo(86, 74, 84, 48, 50, 22)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(3.5)
    p = c.beginPath()
    p.moveTo(16, 56); p.lineTo(32, 56); p.lineTo(38, 68); p.lineTo(46, 40)
    p.lineTo(54, 72); p.lineTo(60, 56); p.lineTo(84, 56)
    c.drawPath(p, stroke=1, fill=0)


_ZEICHNER = {
    "blutstropfen": _blutstropfen,
    "kreuz": _kreuz,
    "schneeflocke": _schneeflocke,
    "blutdruckmanschette": _blutdruckmanschette,
    "infusionsbeutel": _infusionsbeutel,
    "spritze": _spritze,
    "nadeln": _nadeln,
    "pflaster": _pflaster,
    "verbandsrolle": _verbandsrolle,
    "sauerstoffflasche": _sauerstoffflasche,
    "herz_ekg": _herz_ekg,
}


# ---------------------------------------------------------------------------
# Eigene Bilder: auf eine Farbe reduzieren
# ---------------------------------------------------------------------------

def bild_monochrom(pfad, farbe: str):
    """Macht aus einem hochgeladenen Bild ein einfarbiges Wasserzeichen.

    Dunkle Stellen werden zur Zeichnung, helle verschwinden. Hat das Bild einen
    Alphakanal, gilt dieser - so bleibt ein freigestelltes Logo freigestellt,
    statt einen weissen Kasten zu bekommen.
    """
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    bild = Image.open(pfad)
    bild = bild.convert("RGBA")
    grau = bild.convert("L")
    alpha = bild.getchannel("A")
    # Deckung = wie dunkel das Pixel ist, begrenzt durch vorhandene Transparenz.
    tinte = grau.point(lambda v: 255 - v)
    maske = Image.new("L", bild.size)
    maske.putdata([min(t, a) for t, a in zip(tinte.getdata(), alpha.getdata())])
    r, g, b = HexColor(farbe).bitmap_rgb()
    flaeche = Image.new("RGBA", bild.size, (r, g, b, 0))
    flaeche.putalpha(maske)
    return ImageReader(flaeche)


# ---------------------------------------------------------------------------
# Platzieren
# ---------------------------------------------------------------------------

def _einmal_zeichnen(c, w, mitte_x, mitte_y, kante, bild=None):
    c.saveState()
    c.translate(mitte_x, mitte_y)
    if w["drehung"]:
        c.rotate(w["drehung"])
    if bild is not None:
        breite, hoehe = bild.getSize()
        seite = kante / max(breite, hoehe)
        c.drawImage(bild, -breite * seite / 2.0, -hoehe * seite / 2.0,
                    width=breite * seite, height=hoehe * seite, mask="auto")
    else:
        c.translate(-kante / 2.0, -kante / 2.0)
        c.scale(kante / 100.0, kante / 100.0)
        _ZEICHNER[w["motiv"]](c)
    c.restoreState()


def auf_canvas(c, daten, seitenbreite: float, seitenhoehe: float):
    """Zeichnet das Wasserzeichen auf einen offenen Canvas.

    Wird sowohl fuer die Hintergrundseite der grossen PDFs verwendet als auch
    direkt beim Einschiebeschildchen, das ohne Vorlage gebaut wird.
    """
    w = normalisieren(daten)
    if not ist_aktiv(w):
        return
    bild = None
    if w["art"] == "bild":
        try:
            bild = bild_monochrom(BRANDING_DIR / w["datei"], w["farbe"])
        except Exception:
            return

    kante = w["groesse_mm"] * mm
    deckkraft = w["deckkraft"] / 100.0
    c.saveState()
    c.setFillColor(HexColor(w["farbe"]))
    c.setStrokeColor(HexColor(w["farbe"]))
    c.setFillAlpha(deckkraft)
    c.setStrokeAlpha(deckkraft)

    if w["position"] == "kachel":
        schritt = kante * 1.5
        spalten = int(math.ceil(seitenbreite / schritt)) + 1
        zeilen = int(math.ceil(seitenhoehe / schritt)) + 1
        for sp in range(spalten):
            for ze in range(zeilen):
                versatz = (schritt / 2.0) if ze % 2 else 0.0
                _einmal_zeichnen(c, w, sp * schritt + versatz, ze * schritt, kante, bild)
    else:
        rand = 12 * mm + kante / 2.0
        stellen = {
            "mitte": (seitenbreite / 2.0, seitenhoehe / 2.0),
            "oben_links": (rand, seitenhoehe - rand),
            "oben_rechts": (seitenbreite - rand, seitenhoehe - rand),
            "unten_links": (rand, rand),
            "unten_rechts": (seitenbreite - rand, rand),
        }
        x, y = stellen.get(w["position"], stellen["mitte"])
        _einmal_zeichnen(c, w, x, y, kante, bild)
    c.restoreState()


def seite_pdf(daten, breite_pt: float, hoehe_pt: float) -> bytes:
    """Eine einzelne leere Seite mit dem Wasserzeichen - wird beim Zusammenbau
    UNTER den Inhalt gelegt, damit der Text obenauf lesbar bleibt."""
    puffer = io.BytesIO()
    c = _canvas.Canvas(puffer, pagesize=(breite_pt, hoehe_pt))
    auf_canvas(c, daten, breite_pt, hoehe_pt)
    c.showPage()
    c.save()
    return puffer.getvalue()


def eigene_dateien() -> list:
    """Die hochgeladenen Motive im Branding-Ordner."""
    if not BRANDING_DIR.exists():
        return []
    treffer = []
    for pfad in sorted(BRANDING_DIR.glob(f"{DATEI_VORSATZ}*")):
        if pfad.is_file() and pfad.suffix.lower() in ERLAUBTE_ENDUNGEN:
            treffer.append({"datei": pfad.name,
                            "label": pfad.stem[len(DATEI_VORSATZ):].replace("_", " "),
                            "bytes": pfad.stat().st_size})
    return treffer
