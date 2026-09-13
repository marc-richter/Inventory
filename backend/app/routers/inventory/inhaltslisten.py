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

from app import models, pdf_layout, security
from app.database import get_db

router = APIRouter(prefix="/api/v1/inhaltslisten", tags=["inhaltslisten"])

FORMATE = {
    "a4": ("DIN A4 hoch", A4),
    "a4quer": ("DIN A4 quer", landscape(A4)),
    "a5": ("DIN A5 hoch", A5),
    "a5quer": ("DIN A5 quer", landscape(A5)),
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


def _teilbaum(db: Session, node_id: int) -> List[int]:
    ids, offen = [], [node_id]
    while offen:
        ids.extend(offen)
        offen = [k.id for k in db.query(models.StorageNode.id)
                 .filter(models.StorageNode.parent_id.in_(offen)).all() if k.id not in ids]
    return ids


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
    zeilen.sort(key=lambda z: (z["bezeichnung"].lower(), z["groesse"]))
    return zeilen


@router.get("/{node_id}")
def inhalt_vorschau(node_id: int, db: Session = Depends(get_db),
                    user=Depends(security.get_current_user)):
    """Der Soll-Ist-Vergleich als Daten - fuer die Anzeige vor dem Drucken."""
    node = _knoten(db, node_id)
    zeilen = soll_und_ist(db, node)
    return {
        "node_id": node.id,
        "name": node.name,
        "path": _pfad(db, node),
        "label_width_mm": node.label_width_mm,
        "label_height_mm": node.label_height_mm,
        "rows": zeilen,
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
    """
    node = _knoten(db, node_id)
    if format not in FORMATE:
        raise HTTPException(status_code=400, detail=f"Unbekanntes Format. Möglich: {', '.join(FORMATE)}")
    zeilen = soll_und_ist(db, node)

    puffer = io.BytesIO()
    oben, unten, eigener_kopf, canvasmaker = pdf_layout.doc_setup(
        db, "content_list", "Inhaltsliste", _pfad(db, node))
    doc = SimpleDocTemplate(puffer, pagesize=FORMATE[format][1],
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=oben, bottomMargin=unten, title="Inhaltsliste")
    stile = getSampleStyleSheet()
    inhalt = []
    if eigener_kopf:
        inhalt.append(Paragraph("Inhaltsliste", stile["Title"]))
        inhalt.append(Paragraph(_pfad(db, node), stile["Normal"]))
        inhalt.append(Spacer(1, 8))

    kopf = ["Bezeichnung", "Größe", "Soll", "Ist", "Differenz"]
    daten = [kopf]
    for z in zeilen:
        daten.append([
            z["bezeichnung"], z["groesse"] or "–", str(z["soll"]),
            str(z["ist"]) if ist_ausfuellen else "",
            str(z["ist"] - z["soll"]) if ist_ausfuellen else "",
        ])
    if not zeilen:
        daten.append(["(kein Soll-Bestand hinterlegt)", "", "", "", ""])
    # Fuenf Leerzeilen zum handschriftlichen Nachtragen - es fehlt immer etwas.
    for _ in range(5):
        daten.append(["", "", "", "", ""])

    tabelle = Table(daten, repeatRows=1,
                    colWidths=[None, 22 * mm, 18 * mm, 18 * mm, 22 * mm])
    tabelle.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]))
    inhalt.append(tabelle)
    inhalt.append(Spacer(1, 10))
    inhalt.append(Paragraph(
        "Geprüft am ____________________ durch ____________________________",
        stile["Normal"]))

    doc.build(inhalt, canvasmaker=canvasmaker)
    rohdaten = pdf_layout.finalize(db, "content_list", puffer.getvalue())
    return StreamingResponse(io.BytesIO(rohdaten), media_type="application/pdf",
                             headers={"Content-Disposition": 'inline; filename="inhaltsliste.pdf"'})


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

    puffer = io.BytesIO()
    c = pdfcanvas.Canvas(puffer, pagesize=(breite * mm, hoehe * mm))
    _schildchen_zeichnen(c, breite * mm, hoehe * mm, node.name, _pfad(db, node), zeilen)
    c.save()
    puffer.seek(0)
    return StreamingResponse(puffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'inline; filename="einschiebeschild.pdf"'})


def _schildchen_zeichnen(c, breite, hoehe, name, pfad, zeilen):
    rand = 4 * mm
    _schnittecken(c, breite, hoehe)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(rand, hoehe - rand - 7, name[:40])
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
