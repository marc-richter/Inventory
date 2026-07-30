"""Nativer Direktdruck fuer Brother P-touch PT-E550W (auch P750W/P710BT) ueber das
Netzwerk (Rohdruck-Port 9100), gemaess der offiziellen "Raster Command Reference
PT-E550W/P750W/P710BT" (Version 1.02).

Kernfakten aus der Referenz:
- 180 dpi, Druckkopf mit 128 Pins, IMMER 16 Byte pro Rasterzeile.
- Je TZe-Bandbreite ergeben sich linker/rechter Rand und Druckbereich (Pins):
    3.5mm -> 24 Pins, 6mm -> 32, 9mm -> 50, 12mm -> 70, 18mm -> 112, 24mm -> 128.
- Ablauf: (Invalidate) ESC @  ESC i a 01  ESC i z(Druckinfo)  ESC i M  ESC i K
  ESC i d(Rand)  M 00(unkomprimiert)  je Zeile: G 10 00 + 16 Byte  Abschluss 1A.

Die Rasterzeilen laufen entlang der Bandlaenge (Vorschubrichtung); die 128 Pins
liegen quer ueber das Band. Da hier keine echte Hardware zum Test verfuegbar ist,
gibt es Korrektur-Schalter (rotate180 / mirror), falls der Ausdruck gespiegelt oder
kopfstehend herauskommt.
"""
import io
import socket

import qrcode
from PIL import Image, ImageDraw, ImageFont

# TZe-Band: Breite(mm) -> (linker Rand in Pins, Druckbereich in Pins). Rechter Rand
# = 128 - links - Druckbereich. Summe stets 128.
TAPE_PINS = {
    "3.5": (52, 24), "6": (48, 32), "9": (39, 50),
    "12": (29, 70), "18": (8, 112), "24": (0, 128),
}
DPI = 180.0
TOTAL_PINS = 128
BYTES_PER_LINE = 16


class PTouchError(Exception):
    pass


def dots(mm: float) -> int:
    return int(round(float(mm) * DPI / 25.4))


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10 kann skalieren
    except TypeError:
        return ImageFont.load_default()


def render_label_image(qr_value: str, lines, height: int, length: int) -> Image.Image:
    """Erzeugt ein Graustufenbild (QR links, Textzeilen rechts) in der Groesse
    length x height (Pixel = Punkte bei 180 dpi). height entspricht dem Druckbereich
    des Bandes, length der Etikettenlaenge."""
    img = Image.new("L", (max(1, length), max(1, height)), 255)
    draw = ImageDraw.Draw(img)

    # QR-Code quadratisch links, so hoch wie das Band (hohe Fehlerkorrektur)
    _qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=2)
    _qr.add_data(str(qr_value))
    _qr.make(fit=True)
    qr = _qr.make_image(fill_color="black", back_color="white").convert("L")
    qr = qr.resize((height, height))
    img.paste(qr, (0, 0))

    text_x = height + 6
    avail_w = length - text_x - 2
    rows = [str(t) for t in (lines or []) if str(t).strip()]
    if rows and avail_w > 10:
        n = len(rows)
        line_h = max(8, min(height // n, height))
        fsize = max(8, int(line_h * 0.8))
        y = 0
        first = True
        for txt in rows:
            draw.text((text_x, y), txt, fill=0, font=_font(fsize if not first else min(fsize + 4, height)))
            y += line_h
            first = False
    return img


def build_command_stream(img: Image.Image, tape_mm="24", cut=True, feed_dots=14,
                         rotate180=False, mirror=False) -> bytes:
    """Baut den kompletten Rohdruck-Kommandostrom fuer ein bereits gerendertes Bild."""
    key = str(tape_mm)
    if key not in TAPE_PINS:
        raise PTouchError(f"Unbekannte Bandbreite {tape_mm} mm")
    left, area = TAPE_PINS[key]

    g = img.convert("L")
    if g.height != area:
        g = g.resize((g.width, area))
    if mirror:
        g = g.transpose(Image.FLIP_TOP_BOTTOM)
    if rotate180:
        g = g.transpose(Image.ROTATE_180)
    px = g.load()
    width, height = g.size   # height == area

    out = bytearray()
    out += b"\x00" * 100                      # Invalidate (Rest evtl. Vorbefehle loeschen)
    out += b"\x1b\x40"                          # ESC @  Initialisieren
    out += b"\x1b\x69\x61\x01"                  # ESC i a 01  Rastermodus
    rn = width                                  # Anzahl Rasterzeilen
    width_mm = int(round(float(tape_mm)))
    out += bytes([0x1b, 0x69, 0x7a,             # ESC i z  Druckinformation
                  0x84, 0x00, width_mm & 0xFF, 0x00,
                  rn & 0xFF, (rn >> 8) & 0xFF, (rn >> 16) & 0xFF, (rn >> 24) & 0xFF,
                  0x00, 0x00])
    out += bytes([0x1b, 0x69, 0x4d, 0x40 if cut else 0x00])  # ESC i M  Auto-Schnitt
    out += bytes([0x1b, 0x69, 0x4b, 0x08])      # ESC i K  erweiterter Modus
    out += bytes([0x1b, 0x69, 0x64, feed_dots & 0xFF, (feed_dots >> 8) & 0xFF])  # ESC i d Rand
    out += b"\x4d\x00"                           # M 00  keine Kompression

    for x in range(width):
        line = bytearray(BYTES_PER_LINE)
        for y in range(height):
            if px[x, y] < 128:                  # dunkel = Pin AN
                pin = left + y
                line[pin >> 3] |= (0x80 >> (pin & 7))
        out += bytes([0x47, 0x10, 0x00]) + bytes(line)   # G  10 00  + 16 Byte

    out += b"\x1a"                              # Control-Z  Drucken mit Vorschub
    return bytes(out)


def print_label(ip: str, qr_value: str, lines, tape_mm="24", length_mm=40,
                cut=True, rotate180=False, mirror=False, port=9100, timeout=8.0):
    """Rendert ein Etikett und sendet es als P-touch-Rasterdruck an den Drucker."""
    if not ip:
        raise PTouchError("Keine Drucker-IP hinterlegt")
    key = str(tape_mm)
    if key not in TAPE_PINS:
        raise PTouchError(f"Unbekannte Bandbreite {tape_mm} mm")
    _, area = TAPE_PINS[key]
    length_px = max(area, dots(length_mm))
    img = render_label_image(qr_value, lines, area, length_px)
    data = build_command_stream(img, tape_mm=tape_mm, cut=cut, feed_dots=dots(2),
                                rotate180=rotate180, mirror=mirror)
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(data)
    except (OSError, socket.timeout) as exc:
        raise PTouchError(
            f"Verbindung zum Drucker {ip}:{port} fehlgeschlagen ({exc}). "
            "Ist der PT-E550W eingeschaltet, im WLAN erreichbar und Rohdruck (Port 9100) aktiv?"
        )
    return len(data)
