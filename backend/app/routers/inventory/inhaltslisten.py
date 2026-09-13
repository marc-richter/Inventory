"""Inhaltslisten und Einschiebeschildchen fuer Faecher, Kisten und Rucksacktaschen.

Zwei Ausgaben aus derselben Grundlage:

* **Inhaltsliste** - eine Seite zum Mitnehmen und Abhaken. Sie zeigt den
  Soll-Bestand und laesst zwei Spalten frei: "Ist" und "Differenz". So kann man
  vor Ort mit dem Stift arbeiten und die Zahlen spaeter am Schreibtisch
  eintragen oder gleich auffuellen und nur noch den Lagerabgang buchen.
* **Einschiebeschildchen** - dieselbe Liste im Format der Tasche, mit
  Schnittecken. Kommt in die Klarsichthuelle an der Tasche.

Woher der Soll-Bestand kommt
----------------------------
Aus den Mindestbestands-Regeln (models.MinStockRule). Die koennen bereits
"Artikeltyp + Groesse + Lagerort + Menge" und gelten fuer den Knoten samt
Unterebenen. Damit ist die Packliste dieselbe Angabe wie die Warnschwelle - eine
Stelle zum Pflegen, und das Programm meldet von selbst, wenn eine Tasche
unvollstaendig ist. Eine zweite, getrennte Packliste waere eine zweite Wahrheit.

Der Ist-Bestand wird aus den tatsaechlich an diesem Platz liegenden Artikeln
gezaehlt - er steht in der Liste nur als Anhaltspunkt in Klammern, die Spalte
zum Eintragen bleibt frei.
"""

import io
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app import models, pdf_layout, security, wasserzeichen
from app.database import get_db

router = APIRouter(prefix="/api/v1/inhaltslisten", tags=["inhaltslisten"])

FORMATE = {
    "a4": ("DIN A4 hoch", A4),
    "a4quer": ("DIN A4 quer", landscape(A4)),
    "a5": ("DIN A5 hoch", A5),
    "a5quer": ("DIN A5 quer", landscape(A5)),
}

# Die beiden Farben der Legende - dieselben Toene wie auf dem Vordruck.
PRUEFFARBEN = {
    "verfall": pdf_layout.FARBE_VERFALL,
    "funktion": pdf_layout.FARBE_FUNKTION,
}


def _knoten(db: Session, node_id: int) -> models.StorageNode:
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    return node


def _pfad(db: Session, node: models.StorageNode) -> str:
    teile, aktuell, gesehen = [], node, set()
    while aktuell is not None and aktuell.id not in gesehen:
        teile.append(aktuell.name)
        gesehen.add(aktuell.id)
        aktuell = db.get(models.StorageNode, aktuell.parent_id) if aktuell.parent_id else None
    return " › ".join(reversed(teile))


def _umgebung(db: Session, node: models.StorageNode) -> Dict[str, str]:
    """Wo dieser Platz hingehoert: Fahrzeug (falls er in einem liegt) und Standort.

    Das sind die beiden Angaben, die der Vordruck oben links fuehrt - damit auf
    einem ausgedruckten Schild sofort erkennbar ist, wohin es zurueckgehoert.
    """
    fahrzeug, standort, aktuell, gesehen = "", "", node, set()
    while aktuell is not None and aktuell.id not in gesehen:
        gesehen.add(aktuell.id)
        if aktuell.level == "fahrzeug" and not fahrzeug:
            fahrzeug = aktuell.name
        if aktuell.parent_id is None:
            standort = aktuell.name
        aktuell = db.get(models.StorageNode, aktuell.parent_id) if aktuell.parent_id else None
    return {"fahrzeug": fahrzeug, "standort": standort}


def _dateiname(node: models.StorageNode, endung: str = "pdf", vorsatz: str = "inhaltsliste") -> str:
    """Ein sprechender Dateiname statt „inhaltsliste.pdf" fuer jeden Platz - sonst
    liegen im Download-Ordner zwanzig gleichnamige Dateien. ASCII-sicher, denn er
    steht in einer HTTP-Kopfzeile (siehe pdf_layout.dateiname_teil)."""
    sauber = pdf_layout.dateiname_teil(node.name)
    return f"{vorsatz}-{sauber}.{endung}" if sauber else f"{vorsatz}.{endung}"


def _werte(db: Session, node: models.StorageNode, use_case: str, dateiname: str,
           user=None) -> Dict[str, str]:
    umgebung = _umgebung(db, node)
    return pdf_layout.standardwerte(
        db, use_case,
        titel="Inhaltsliste", untertitel=node.name, lagername=node.name,
        pfad=_pfad(db, node), fahrzeug=umgebung["fahrzeug"], standort=umgebung["standort"],
        dateiname=dateiname, benutzer=getattr(user, "username", "") or "")


def _teilbaum(db: Session, node_id: int) -> List[int]:
    ids, offen = [], [node_id]
    while offen:
        ids.extend(offen)
        offen = [k.id for k in db.query(models.StorageNode.id)
                 .filter(models.StorageNode.parent_id.in_(offen)).all() if k.id not in ids]
    return ids


def _kategorie_kette(db: Session, category_id: Optional[int]) -> List[int]:
    """Die Kategorie und alle ihre Oberkategorien - Zuweisungen werden vererbt."""
    ids, aktuell, gesehen = [], category_id, set()
    while aktuell and aktuell not in gesehen:
        ids.append(aktuell)
        gesehen.add(aktuell)
        kat = db.get(models.Category, aktuell)
        aktuell = kat.parent_id if kat else None
    return ids


def pruefart_je_typ(db: Session, type_ids: List[int]) -> Dict[int, str]:
    """Sagt je Artikeltyp, wonach bei ihm geprueft wird: "verfall", "funktion"
    oder "" (gar nicht).

    Grundlage sind die Zuweisungen der Pruefarten - an den Typ selbst oder an
    seine Kategorie (samt Oberkategorien). Verfall geht vor Funktion: was
    ablaeuft, ist dringlicher als was nur geprueft werden will, und auf dem
    Papier hat eine Zeile nur eine Farbe.
    """
    if not type_ids:
        return {}
    typen = {t.id: t for t in db.query(models.ArticleType)
             .filter(models.ArticleType.id.in_(type_ids)).all()}
    zuordnungen = (db.query(models.MaintenanceAssignment, models.MaintenanceType)
                   .join(models.MaintenanceType,
                         models.MaintenanceType.id == models.MaintenanceAssignment.mtype_id)
                   .filter(models.MaintenanceAssignment.mode == "include",
                           models.MaintenanceType.active == True).all())  # noqa: E712
    je_kategorie: Dict[int, set] = {}
    je_typ: Dict[int, set] = {}
    for zu, art in zuordnungen:
        kennung = (art.kind or "funktion").strip() or "funktion"
        if zu.category_id:
            je_kategorie.setdefault(zu.category_id, set()).add(kennung)
        if zu.article_type_id:
            je_typ.setdefault(zu.article_type_id, set()).add(kennung)
    ergebnis: Dict[int, str] = {}
    for tid in type_ids:
        arten = set(je_typ.get(tid, ()))
        typ = typen.get(tid)
        if typ is not None:
            for kid in _kategorie_kette(db, typ.category_id):
                arten |= je_kategorie.get(kid, set())
        ergebnis[tid] = "verfall" if "verfall" in arten else ("funktion" if arten else "")
    return ergebnis


def soll_und_ist(db: Session, node: models.StorageNode) -> List[Dict]:
    """Der Soll-Bestand dieses Platzes samt gezaehltem Ist-Bestand.

    Soll kommt aus den Mindestbestands-Regeln fuer diesen Knoten (nicht geerbt -
    was fuer den ganzen Standort gilt, gehoert nicht auf das Schildchen einer
    einzelnen Tasche). Ist wird ueber den Teilbaum gezaehlt, damit auch zaehlt,
    was in einer Kiste in dieser Tasche liegt.
    """
    regeln = (db.query(models.MinStockRule)
              .filter(models.MinStockRule.node_id == node.id).all())
    ids = _teilbaum(db, node.id)
    zeilen = []
    for regel in regeln:
        typ = db.get(models.ArticleType, regel.type_id)
        abfrage = db.query(models.Article).filter(
            models.Article.type_id == regel.type_id,
            models.Article.storage_node_id.in_(ids))
        if regel.size:
            abfrage = abfrage.filter(models.Article.size == regel.size)
        zeilen.append({
            "type_id": regel.type_id,
            "bezeichnung": typ.name if typ else f"Typ {regel.type_id}",
            "groesse": regel.size or "",
            "soll": regel.min_stock,
            "ist": abfrage.count(),
        })
    arten = pruefart_je_typ(db, [z["type_id"] for z in zeilen])
    for z in zeilen:
        z["pruefart"] = arten.get(z["type_id"], "")
    zeilen.sort(key=lambda z: (z["bezeichnung"].lower(), z["groesse"]))
    return zeilen


@router.get("/{node_id}")
def inhalt_vorschau(node_id: int, db: Session = Depends(get_db),
                    user=Depends(security.get_current_user)):
    """Der Soll-Ist-Vergleich als Daten - fuer die Anzeige vor dem Drucken."""
    node = _knoten(db, node_id)
    zeilen = soll_und_ist(db, node)
    umgebung = _umgebung(db, node)
    return {
        "node_id": node.id,
        "name": node.name,
        "path": _pfad(db, node),
        "fahrzeug": umgebung["fahrzeug"],
        "standort": umgebung["standort"],
        "label_width_mm": node.label_width_mm,
        "label_height_mm": node.label_height_mm,
        "rows": zeilen,
        "legende": [
            {"key": "verfall", "label": "Verfall prüfen", "color": PRUEFFARBEN["verfall"]},
            {"key": "funktion", "label": "Funktion prüfen", "color": PRUEFFARBEN["funktion"]},
        ],
        "vollstaendig": all(z["ist"] >= z["soll"] for z in zeilen) if zeilen else None,
        "hint": ("Der Soll-Bestand kommt aus den Mindestbestands-Regeln dieses Lagerorts. "
                 "Sind noch keine hinterlegt, bleibt die Liste leer."),
    }


@router.get("/{node_id}/pdf")
def inhaltsliste_pdf(node_id: int, format: str = "a4", ist_ausfuellen: bool = False,
                     db: Session = Depends(get_db),
                     user=Depends(security.get_current_user)):
    """Inhaltsliste zum Mitnehmen und Abhaken.

    `ist_ausfuellen=true` traegt den gezaehlten Ist-Bestand schon ein; sonst
    bleiben die Spalten "Ist" und "Differenz" leer - das ist der Normalfall, denn
    gezaehlt wird vor Ort.

    Hoch- und Querformat sind dasselbe Blatt: derselbe Kopf, derselbe Fuss,
    dieselbe Legende. Nur die Seite ist gedreht.
    """
    node = _knoten(db, node_id)
    if format not in FORMATE:
        raise HTTPException(status_code=400, detail=f"Unbekanntes Format. Möglich: {', '.join(FORMATE)}")
    zeilen = soll_und_ist(db, node)
    dateiname = _dateiname(node)
    werte = _werte(db, node, "content_list", dateiname, user)

    puffer = io.BytesIO()
    oben, unten, eigener_kopf, canvasmaker = pdf_layout.doc_setup(
        db, "content_list", "Inhaltsliste", node.name, werte=werte)
    doc = SimpleDocTemplate(puffer, pagesize=FORMATE[format][1],
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=oben, bottomMargin=unten, title="Inhaltsliste")
    stile = getSampleStyleSheet()
    inhalt = []
    if eigener_kopf:
        # Ohne eigene Vorlage steht der Kopf hier - mit denselben Angaben, die
        # der Vordruck oben fuehrt, damit beide Wege dasselbe Blatt ergeben.
        inhalt.append(Paragraph("Inhaltsliste", stile["Title"]))
        inhalt.append(Paragraph(node.name, stile["Heading3"]))
        inhalt.append(Paragraph(_kopfzeile(werte), stile["Normal"]))
        inhalt.append(Spacer(1, 8))

    kopf = ["Bezeichnung", "Größe", "Soll", "Ist", "Differenz"]
    daten = [kopf]
    farben = []
    for z in zeilen:
        daten.append([
            z["bezeichnung"], z["groesse"] or "–", str(z["soll"]),
            str(z["ist"]) if ist_ausfuellen else "",
            str(z["ist"] - z["soll"]) if ist_ausfuellen else "",
        ])
        farben.append(z.get("pruefart") or "")
    if not zeilen:
        daten.append(["(kein Soll-Bestand hinterlegt)", "", "", "", ""])
        farben.append("")
    # Fuenf Leerzeilen zum handschriftlichen Nachtragen - es fehlt immer etwas.
    for _ in range(5):
        daten.append(["", "", "", "", ""])
        farben.append("")

    stil = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]
    for nr, art in enumerate(farben, start=1):
        if art in PRUEFFARBEN:
            stil.append(("BACKGROUND", (0, nr), (-1, nr), colors.HexColor(PRUEFFARBEN[art])))
    # Die Tabelle nimmt die ganze Seitenbreite ein - im Hoch- wie im Querformat.
    # Sonst klebt sie im Querformat als schmaler Streifen in der Mitte, und die
    # Spalten zum Eintragen von Hand werden unnoetig eng.
    nutzbreite = FORMATE[format][1][0] - 30 * mm
    tabelle = Table(daten, repeatRows=1,
                    colWidths=[nutzbreite - 80 * mm, 22 * mm, 18 * mm, 18 * mm, 22 * mm])
    tabelle.setStyle(TableStyle(stil))
    inhalt.append(tabelle)
    inhalt.append(Spacer(1, 10))
    if eigener_kopf and any(farben):
        # Die Legende gehoert auf den Vordruck in den Fuss. Ohne Vordruck steht
        # sie hier, damit die Farben nie unerklaert bleiben.
        inhalt.append(_legende_tabelle())
        inhalt.append(Spacer(1, 8))
    inhalt.append(Paragraph(
        "Geprüft am ____________________ durch ____________________________",
        stile["Normal"]))

    doc.build(inhalt, canvasmaker=canvasmaker)
    rohdaten = pdf_layout.finalize(db, "content_list", puffer.getvalue(),
                                   wasserzeichen_daten=node.watermark)
    return StreamingResponse(io.BytesIO(rohdaten), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{dateiname}"'})


def _kopfzeile(werte: Dict[str, str]) -> str:
    """Die Zeile unter der Ueberschrift: Weg, Fahrzeug, Stand - was auch der
    Vordruck fuehrt, nur in einer Zeile."""
    teile = [werte.get("pfad") or ""]
    if werte.get("fahrzeug"):
        teile.append(f"Fahrzeug: {werte['fahrzeug']}")
    teile.append(f"Stand {werte.get('stand', '')}")
    if werte.get("version"):
        teile.append(f"Version {werte['version']}")
    return " · ".join([t for t in teile if t])


def _legende_tabelle() -> Table:
    """Die Legende fuer den Fall ohne Vorlage - zwei Zeilen, Kaestchen links,
    Erklaerung daneben auf gleicher Hoehe. Dieselbe Anordnung wie auf dem
    Vordruck, damit beide Wege gleich aussehen."""
    zeilen = [["", "Verfall prüfen"], ["", "Funktion prüfen"]]
    t = Table(zeilen, colWidths=[9 * mm, 34 * mm], rowHeights=[4.6 * mm, 4.6 * mm],
              hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#404040")),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(PRUEFFARBEN["verfall"])),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(PRUEFFARBEN["funktion"])),
        ("BOX", (0, 0), (0, 0), 0.3, colors.HexColor("#8c8c8c")),
        ("BOX", (0, 1), (0, 1), 0.3, colors.HexColor("#8c8c8c")),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


@router.get("/{node_id}/schildchen")
def einschiebeschildchen(node_id: int, width_mm: float = None, height_mm: float = None,
                         db: Session = Depends(get_db),
                         user=Depends(security.get_current_user)):
    """Einschiebeschildchen im Format der Tasche, mit Schnittecken.

    Ohne Massangabe gelten die am Lagerort hinterlegten Masse; sind auch die
    nicht gesetzt, ein brauchbares Standardformat (74 x 52 mm, etwa A7 quer).
    """
    node = _knoten(db, node_id)
    breite = float(width_mm or node.label_width_mm or 74)
    hoehe = float(height_mm or node.label_height_mm or 52)
    if not (20 <= breite <= 300 and 15 <= hoehe <= 300):
        raise HTTPException(status_code=400,
                            detail="Maße müssen zwischen 20 und 300 mm liegen.")
    zeilen = soll_und_ist(db, node)
    dateiname = _dateiname(node, vorsatz="einschiebeschild")
    umgebung = _umgebung(db, node)

    puffer = io.BytesIO()
    c = pdfcanvas.Canvas(puffer, pagesize=(breite * mm, hoehe * mm))
    # Das Wasserzeichen zuerst - damit es HINTER der Schrift liegt und nicht
    # ueber den Mengenangaben.
    marke = pdf_layout.wasserzeichen_fuer(db, "content_list", node.watermark)
    if marke:
        eigene = dict(marke)
        # Auf einem Schildchen von wenigen Zentimetern waere ein Motiv in
        # Seitengroesse sinnlos; es bekommt die halbe kurze Kante.
        eigene["groesse_mm"] = min(marke["groesse_mm"], max(12.0, min(breite, hoehe) * 0.7))
        eigene["position"] = "mitte" if marke["position"] != "kachel" else "kachel"
        wasserzeichen.auf_canvas(c, eigene, breite * mm, hoehe * mm)
    _schildchen_zeichnen(c, breite * mm, hoehe * mm, node.name, _pfad(db, node), zeilen,
                         umgebung["fahrzeug"] or umgebung["standort"])
    c.save()
    puffer.seek(0)
    return StreamingResponse(puffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{dateiname}"'})


def _schildchen_zeichnen(c, breite, hoehe, name, pfad, zeilen, umgebung=""):
    rand = 4 * mm
    _schnittecken(c, breite, hoehe)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(rand, hoehe - rand - 7, name[:40])
    if umgebung:
        # Oben rechts, wie auf dem Vordruck: wohin das Teil zurueckgehoert.
        c.setFont("Helvetica", 6)
        c.setFillGray(0.4)
        c.drawRightString(breite - rand, hoehe - rand - 7, umgebung[:28])
        c.setFillGray(0)
    if pfad and pfad != name:
        c.setFont("Helvetica", 5.5)
        c.setFillGray(0.4)
        c.drawString(rand, hoehe - rand - 14, pfad[:70])
        c.setFillGray(0)

    y = hoehe - rand - 21
    c.setFont("Helvetica", 7)
    zeilenhoehe = 8.5
    for z in zeilen:
        if y < rand + 4:
            c.setFont("Helvetica-Oblique", 6)
            c.drawString(rand, rand, "… weitere siehe Inhaltsliste")
            break
        beschriftung = z["bezeichnung"] + (f" ({z['groesse']})" if z["groesse"] else "")
        art = z.get("pruefart") or ""
        if art in PRUEFFARBEN:
            # Farbpunkt statt Legende - auf einem Schildchen ist kein Platz fuer
            # eine Erklaerung, die Farben sind dieselben wie auf der Liste.
            from reportlab.lib import colors as _c
            c.setFillColor(_c.HexColor(PRUEFFARBEN[art]))
            c.rect(rand, y - 0.5, 2.2 * mm, 2.2 * mm, fill=1, stroke=0)
            c.setFillGray(0)
            c.drawString(rand + 3.2 * mm, y, beschriftung[:41])
        else:
            c.drawString(rand, y, beschriftung[:44])
        c.drawRightString(breite - rand, y, f"{z['soll']}×")
        y -= zeilenhoehe
    if not zeilen:
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(rand, y, "kein Soll-Bestand hinterlegt")


def _schnittecken(c, breite, hoehe):
    """Nur Ecken, keine durchgehende Linie - so bleibt der Schnitt sauber und man
    sieht trotzdem genau, wo geschnitten werden muss."""
    laenge = 3 * mm
    c.setLineWidth(0.3)
    c.setStrokeGray(0.55)
    for x, y, dx, dy in ((0, 0, 1, 1), (breite, 0, -1, 1), (0, hoehe, 1, -1), (breite, hoehe, -1, -1)):
        c.line(x, y, x + dx * laenge, y)
        c.line(x, y, x, y + dy * laenge)
    c.setStrokeGray(0)
