import csv
import io
import datetime as dt
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .. import models, security
from ..database import get_db
from ..settings_helper import get_setting
from ..config import BRANDING_DIR

router = APIRouter(prefix="/api/export", tags=["export"])


def _logo_flowable(db, max_h_mm: float = 16):
    """Liefert das hinterlegte Logo als reportlab-Image (fuer den PDF-Kopf) oder
    None. Vektor-Logos (SVG) werden uebersprungen, da reportlab.Image nur
    Rasterbilder (PNG/JPG) laedt."""
    name = get_setting(db, "logo_filename", "")
    if not name or name.lower().endswith(".svg"):
        return None
    path = BRANDING_DIR / name
    if not path.exists():
        return None
    try:
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(str(path)).getSize()
        if not iw or not ih:
            return None
        h = max_h_mm * mm
        w = h * (iw / ih)
        return Image(str(path), width=w, height=h)
    except Exception:
        return None


def _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id=None, model=None):
    query = db.query(models.Article).options(
        joinedload(models.Article.category), joinedload(models.Article.type),
        joinedload(models.Article.organization), joinedload(models.Article.storage_location),
        joinedload(models.Article.storage_node), joinedload(models.Article.created_by),
    )
    # Standort-Baum einmal laden -> location_path ohne N+1 (Eltern-Kette).
    db.query(models.StorageNode).all()
    if id:
        query = query.filter(models.Article.id.in_(id))
    if category_id:
        query = query.filter(models.Article.category_id.in_(category_id))
    if type_id:
        query = query.filter(models.Article.type_id.in_(type_id))
    if organization_id:
        query = query.filter(models.Article.organization_id.in_(organization_id))
    if storage_location_id:
        query = query.filter(models.Article.storage_location_id.in_(storage_location_id))
    if status:
        query = query.filter(models.Article.status.in_(status))
    if size:
        query = query.filter(models.Article.size.ilike(size))
    if model:
        query = query.filter(models.Article.model.ilike(model))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Article.artikelnummer.ilike(like)) |
            (models.Article.remarks.ilike(like)) |
            (models.Article.condition_notes.ilike(like))
        )
    return query.order_by(models.Article.artikelnummer).all()


# Vollstaendiger Satz fuer den CSV-Export (keine Breitenbegrenzung).
CSV_HEADERS = ["Artikelnummer", "Kategorie", "Typ", "Modell", "Groesse", "Eigenschaften",
               "Abteilung", "Standort (Pfad)", "Aktuell bei", "Status", "Reparaturgrund",
               "Voraussichtl. Rueckgabe", "Aussonderungsgrund", "Erstinventarisierung",
               "Beschaedigungen", "Bemerkungen", "Angelegt von"]


def _loc_path(a: models.Article) -> str:
    # Nutzt den verwalteten Standort-Baum, faellt sonst auf die Freitext-Ebenen zurueck.
    return a.location_path


def _csv_row(a: models.Article):
    return [
        a.artikelnummer,
        a.category.name if a.category else "",
        a.type.name if a.type else "",
        a.model or "",
        a.size or "",
        a.properties or "",
        a.organization.name if a.organization else "",
        _loc_path(a),
        a.current_location or "",
        a.status,
        a.repair_reason or "",
        a.repair_expected_return.strftime("%d.%m.%Y") if a.repair_expected_return else "",
        a.retire_reason or "",
        a.first_entry_date.strftime("%d.%m.%Y") if a.first_entry_date else "",
        a.condition_notes or "",
        a.remarks or "",
        a.created_by_name or "",
    ]


# Fokussierter Satz fuer den PDF-Export (mit relativer Spaltenbreite, damit die
# Tabelle auf A4-Querformat passt und lange Texte umbrechen).
# (Ueberschrift, Breitenanteil, Wert-Funktion)
PDF_COLUMNS = [
    ("Artikelnr.", 0.085, lambda a: a.artikelnummer or ""),
    ("Typ", 0.085, lambda a: a.type.name if a.type else ""),
    ("Modell", 0.075, lambda a: a.model or ""),
    ("Größe", 0.045, lambda a: a.size or ""),
    ("Eigenschaften", 0.11, lambda a: a.properties or ""),
    ("Abteilung", 0.075, lambda a: a.organization.name if a.organization else ""),
    ("Standort", 0.085, lambda a: _loc_path(a)),
    ("Aktuell bei", 0.085, lambda a: a.current_location or ""),
    ("Status", 0.065, lambda a: a.status or ""),
    ("Ersteintr.", 0.06, lambda a: a.first_entry_date.strftime("%d.%m.%Y") if a.first_entry_date else ""),
    ("Beschädigungen", 0.10, lambda a: a.condition_notes or ""),
    ("Bemerkungen", 0.095, lambda a: a.remarks or ""),
]


@router.get("/csv")
def export_csv(
    db: Session = Depends(get_db), user=Depends(security.get_current_user),
    q: Optional[str] = None,
    id: Optional[List[int]] = Query(None),
    category_id: Optional[List[int]] = Query(None), type_id: Optional[List[int]] = Query(None),
    organization_id: Optional[List[int]] = Query(None), storage_location_id: Optional[List[int]] = Query(None),
    status: Optional[List[str]] = Query(None), size: Optional[str] = None, model: Optional[str] = None,
):
    articles = _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id, model)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(CSV_HEADERS)
    for a in articles:
        writer.writerow(_csv_row(a))
    buf.seek(0)
    filename = f"inventar_export_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def build_inventory_pdf(db, articles, by_name: str = "") -> bytes:
    """Baut die Inventarlisten-PDF (Bytes) - wiederverwendbar fuer den Web-Export und
    fuer den Versand per Telegram."""
    buf = io.BytesIO()
    left = right = 12 * mm
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=12 * mm, bottomMargin=12 * mm,
                            leftMargin=left, rightMargin=right)
    page_w = landscape(A4)[0]
    avail_w = page_w - left - right
    styles = getSampleStyleSheet()
    elements = []

    org_name = get_setting(db, "org_name", "")
    title = f"Inventarliste – {org_name}" if org_name else "Inventarliste"
    who = f" von {by_name}" if by_name else ""
    subtitle = f"Erstellt am {dt.datetime.now().strftime('%d.%m.%Y %H:%M')}{who} · {len(articles)} Artikel"
    title_block = [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Normal"])]

    # Logo NEBEN die Ueberschrift (spart vertikalen Platz).
    logo = _logo_flowable(db, max_h_mm=18)
    if logo is not None:
        header = Table([[logo, title_block]], colWidths=[26 * mm, avail_w - 26 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(header)
    else:
        elements.extend(title_block)
    elements.append(Spacer(1, 8))

    # Zellen als Paragraphen (Umbruch langer Texte) + relative Spaltenbreiten.
    header_style = ParagraphStyle("th", parent=styles["Normal"], fontSize=7, leading=8,
                                  textColor=colors.white, fontName="Helvetica-Bold")
    cell_style = ParagraphStyle("td", parent=styles["Normal"], fontSize=6.5, leading=7.5)

    col_widths = [frac * avail_w for (_, frac, _) in PDF_COLUMNS]
    head = [Paragraph(h, header_style) for (h, _, _) in PDF_COLUMNS]
    data = [head]
    for a in articles:
        data.append([Paragraph(str(getter(a)).replace("\n", "<br/>"), cell_style)
                     for (_, _, getter) in PDF_COLUMNS])

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf.read()


def build_campaign_report_pdf(db, meta: dict, found: list, missing: list, ignored: list, stats: dict) -> bytes:
    """Abschlussbericht einer Inventur als PDF (Bytes). `meta` enthaelt Kopfdaten,
    die Listen enthalten dicts mit Feldern artikelnummer/typ/size/status/location
    (found zusaetzlich found_at). Rein aus den uebergebenen Daten gerendert."""
    buf = io.BytesIO()
    left = right = 14 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=left, rightMargin=right)
    avail_w = A4[0] - left - right
    styles = getSampleStyleSheet()
    els = []

    title_block = [Paragraph("Inventur-Abschlussbericht", styles["Title"]),
                   Paragraph(meta.get("name", ""), styles["Heading2"])]
    logo = _logo_flowable(db, max_h_mm=18)
    if logo is not None:
        header = Table([[logo, title_block]], colWidths=[26 * mm, avail_w - 26 * mm])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        els.append(header)
    else:
        els.extend(title_block)
    els.append(Spacer(1, 6))

    info = []
    for label, key in [("Zeitraum", "zeitraum"), ("Geltungsbereich", "scope"),
                       ("Leitung/Ersteller", "created_by"), ("Teilnehmer", "participants"),
                       ("Erstellt am", "generated_at")]:
        v = meta.get(key)
        if v:
            info.append(f"<b>{label}:</b> {v}")
    if info:
        els.append(Paragraph(" &nbsp;·&nbsp; ".join(info), styles["Normal"]))
        els.append(Spacer(1, 8))

    # Kennzahlen
    stat_rows = [["Erwartet", "Gefunden", "Fehlend", "Ignoriert", "Fortschritt"],
                 [str(stats.get("expected_count", 0)), str(stats.get("found_count", 0)),
                  str(stats.get("open_count", 0)), str(stats.get("ignored_count", 0)),
                  meta.get("progress", "")]]
    st = Table(stat_rows, colWidths=[avail_w / 5] * 5)
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    els.append(st)
    els.append(Spacer(1, 10))

    hstyle = ParagraphStyle("th", parent=styles["Normal"], fontSize=8, leading=9,
                            textColor=colors.white, fontName="Helvetica-Bold")
    cstyle = ParagraphStyle("td", parent=styles["Normal"], fontSize=8, leading=9)

    def section(title, rows, cols):
        els.append(Paragraph(f"{title} ({len(rows)})", styles["Heading3"]))
        if not rows:
            els.append(Paragraph("– keine –", cstyle))
            els.append(Spacer(1, 6))
            return
        head = [Paragraph(h, hstyle) for (h, _, _) in cols]
        data = [head]
        for r in rows:
            data.append([Paragraph(str(r.get(key, "") or "").replace("\n", "<br/>"), cstyle)
                         for (_, key, _) in cols])
        widths = [frac * avail_w for (_, _, frac) in cols]
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        els.append(t)
        els.append(Spacer(1, 10))

    miss_cols = [("Artikelnr.", "artikelnummer", 0.22), ("Typ", "typ", 0.30),
                 ("Größe", "size", 0.12), ("Status", "status", 0.16), ("Lagerort", "location", 0.20)]
    found_cols = [("Artikelnr.", "artikelnummer", 0.22), ("Typ", "typ", 0.34),
                  ("Größe", "size", 0.14), ("Erfasst an", "found_at", 0.30)]
    section("Fehlende Artikel", missing, miss_cols)
    section("Gefundene / erfasste Artikel", found, found_cols)
    section("Ignorierte Artikel (Status ausgeblendet)", ignored, miss_cols)

    doc.build(els)
    buf.seek(0)
    return buf.read()


def build_campaign_report_csv(meta: dict, found: list, missing: list, ignored: list, stats: dict) -> bytes:
    """Abschlussbericht einer Inventur als CSV (Bytes, UTF-8 mit BOM)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Inventur-Abschlussbericht", meta.get("name", "")])
    w.writerow(["Zeitraum", meta.get("zeitraum", "")])
    w.writerow(["Geltungsbereich", meta.get("scope", "")])
    w.writerow(["Erwartet", stats.get("expected_count", 0), "Gefunden", stats.get("found_count", 0),
                "Fehlend", stats.get("open_count", 0), "Ignoriert", stats.get("ignored_count", 0)])
    w.writerow([])
    w.writerow(["Kategorie", "Artikelnummer", "Typ", "Groesse", "Status", "Lagerort / Erfasst an"])
    for r in missing:
        w.writerow(["FEHLEND", r.get("artikelnummer", ""), r.get("typ", ""), r.get("size", ""), r.get("status", ""), r.get("location", "")])
    for r in found:
        w.writerow(["GEFUNDEN", r.get("artikelnummer", ""), r.get("typ", ""), r.get("size", ""), r.get("status", ""), r.get("found_at", "")])
    for r in ignored:
        w.writerow(["IGNORIERT", r.get("artikelnummer", ""), r.get("typ", ""), r.get("size", ""), r.get("status", ""), r.get("location", "")])
    return buf.getvalue().encode("utf-8-sig")


def build_person_pdf(db, person, rows) -> bytes:
    """PDF-Liste der aktuell an eine Person ausgegebenen Artikel. `rows` ist eine
    Liste von dicts (artikelnummer/typ/size/location/issued_at)."""
    buf = io.BytesIO()
    left = right = 14 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=left, rightMargin=right)
    avail_w = A4[0] - left - right
    styles = getSampleStyleSheet()
    els = []

    name = f"{person.first_name} {person.last_name}".strip() if person else "—"
    title_block = [Paragraph("Materialliste", styles["Title"]),
                   Paragraph(name, styles["Heading2"]),
                   Paragraph(f"Stand {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} · {len(rows)} Artikel", styles["Normal"])]
    logo = _logo_flowable(db, max_h_mm=18)
    if logo is not None:
        header = Table([[logo, title_block]], colWidths=[26 * mm, avail_w - 26 * mm])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        els.append(header)
    else:
        els.extend(title_block)
    els.append(Spacer(1, 8))

    hstyle = ParagraphStyle("th", parent=styles["Normal"], fontSize=8, leading=9,
                            textColor=colors.white, fontName="Helvetica-Bold")
    cstyle = ParagraphStyle("td", parent=styles["Normal"], fontSize=8.5, leading=10)
    cols = [("Artikelnr.", "artikelnummer", 0.20), ("Typ", "typ", 0.28), ("Größe", "size", 0.12),
            ("Lagerort", "location", 0.24), ("Ausgegeben", "issued_at", 0.16)]
    data = [[Paragraph(h, hstyle) for (h, _, _) in cols]]
    for r in rows:
        data.append([Paragraph(str(r.get(k, "") or ""), cstyle) for (_, k, _) in cols])
    if not rows:
        data.append([Paragraph("– keine ausgegebenen Artikel –", cstyle), "", "", "", ""])
    t = Table(data, colWidths=[f * avail_w for (_, _, f) in cols], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    els.append(t)
    els.append(Spacer(1, 16))
    els.append(Paragraph("Unterschrift: ______________________________", styles["Normal"]))
    doc.build(els)
    buf.seek(0)
    return buf.read()


def _sig_image(datauri, w_mm=55, h_mm=16):
    """Baut aus einer (data-)Base64-PNG eine reportlab-Grafik fuer die Unterschrift."""
    if not datauri:
        return None
    try:
        import base64
        b64 = datauri.split(",", 1)[1] if "," in datauri else datauri
        raw = base64.b64decode(b64)
        return Image(io.BytesIO(raw), width=w_mm * mm, height=h_mm * mm)
    except Exception:
        return None


def build_receipt_pdf(db, person, kind, received, remaining, issuer_name, copies=1,
                      sig_issuer=None, sig_recipient=None) -> bytes:
    """Ausgabe-/Rueckgabe-Quittung als PDF. `received`/`remaining` sind Listen von
    dicts (artikelnummer/typ/size). Unterschriften optional als Base64-PNG eingebettet;
    sonst Unterschriftslinien. `copies`=2 erzeugt zwei Ausfertigungen (intern + Mitgeben)."""
    buf = io.BytesIO()
    left = right = 16 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=left, rightMargin=right)
    avail_w = A4[0] - left - right
    styles = getSampleStyleSheet()
    hstyle = ParagraphStyle("th", parent=styles["Normal"], fontSize=8, leading=9,
                            textColor=colors.white, fontName="Helvetica-Bold")
    cstyle = ParagraphStyle("td", parent=styles["Normal"], fontSize=8.5, leading=10)
    title = "Ausgabe-Quittung" if kind == "issue" else "Rückgabe-Quittung"
    name = f"{person.first_name} {person.last_name}".strip() if person else "—"
    org = get_setting(db, "org_name", "")
    copies = 2 if int(copies or 1) >= 2 else 1

    def table(title_txt, rows):
        els = [Paragraph(f"{title_txt} ({len(rows)})", styles["Heading4"])]
        if not rows:
            els.append(Paragraph("– keine –", cstyle))
            els.append(Spacer(1, 4))
            return els
        cols = [("Artikelnr.", "artikelnummer", 0.28), ("Typ", "typ", 0.44), ("Größe", "size", 0.28)]
        data = [[Paragraph(h, hstyle) for (h, _, _) in cols]]
        for r in rows:
            data.append([Paragraph(str(r.get(k, "") or ""), cstyle) for (_, k, _) in cols])
        t = Table(data, colWidths=[f * avail_w for (_, _, f) in cols], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        els.append(t)
        els.append(Spacer(1, 8))
        return els

    def sig_cell(role, who, img):
        inner = [Paragraph(f"<b>{role}</b>: {who or ''}", cstyle)]
        s = _sig_image(img)
        if s is not None:
            inner.append(s)
        else:
            inner.append(Spacer(1, 16 * mm))
        inner.append(Paragraph("Unterschrift / Datum", ParagraphStyle("sig", parent=cstyle, fontSize=7,
                     textColor=colors.grey, borderColor=colors.grey)))
        return inner

    elements = []
    for i in range(copies):
        logo = _logo_flowable(db, max_h_mm=16)
        head = [Paragraph(title, styles["Title"]),
                Paragraph(f"{org + ' · ' if org else ''}{name}", styles["Heading3"]),
                Paragraph("Stand " + dt.datetime.now().strftime("%d.%m.%Y %H:%M")
                          + (f" · {issuer_name}" if issuer_name else ""), styles["Normal"])]
        if logo is not None:
            hdr = Table([[logo, head]], colWidths=[24 * mm, avail_w - 24 * mm])
            hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            elements.append(hdr)
        else:
            elements.extend(head)
        if copies == 2:
            elements.append(Paragraph("Ausfertigung " + ("1 – intern" if i == 0 else "2 – für den Empfänger"),
                                      ParagraphStyle("copy", parent=cstyle, textColor=colors.grey)))
        elements.append(Spacer(1, 6))
        if kind == "issue":
            elements += table("Erhaltene Artikel", received)
        else:
            elements += table("Zurückgegebene Artikel", received)
            elements += table("Verbleibt beim Helfer", remaining)
        elements.append(Spacer(1, 10))
        sig = Table([[sig_cell("Ausgebende Person", issuer_name, sig_issuer),
                      sig_cell("Empfänger", name, sig_recipient)]],
                    colWidths=[avail_w / 2, avail_w / 2])
        sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
        elements.append(sig)
        if i < copies - 1:
            elements.append(PageBreak())
    doc.build(elements)
    buf.seek(0)
    return buf.read()


@router.get("/person/{person_id}/pdf")
def export_person_pdf(person_id: int, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("issues"))):
    """Liste der aktuell an eine Person ausgegebenen Artikel als PDF (zum Drucken)."""
    person = db.query(models.Person).get(person_id)
    if not person:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    db.query(models.StorageNode).all()   # Standort-Baum vorladen (location_path ohne N+1)
    open_issues = db.query(models.IssueRecord).filter(
        models.IssueRecord.person_id == person_id,
        models.IssueRecord.return_date.is_(None),
    ).order_by(models.IssueRecord.issue_date).all()
    rows = []
    for i in open_issues:
        a = i.article
        if not a:
            continue
        rows.append({
            "artikelnummer": a.artikelnummer, "typ": a.type.name if a.type else "",
            "size": a.size or "", "location": a.location_path or "",
            "issued_at": i.issue_date.strftime("%d.%m.%Y") if i.issue_date else "",
        })
    pdf_bytes = build_person_pdf(db, person, rows)
    safe = "".join(ch if ch.isalnum() else "_" for ch in f"{person.first_name}_{person.last_name}")[:40]
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Materialliste_{safe}.pdf"'},
    )


@router.get("/pdf")
def export_pdf(
    db: Session = Depends(get_db), user=Depends(security.get_current_user),
    q: Optional[str] = None,
    id: Optional[List[int]] = Query(None),
    category_id: Optional[List[int]] = Query(None), type_id: Optional[List[int]] = Query(None),
    organization_id: Optional[List[int]] = Query(None), storage_location_id: Optional[List[int]] = Query(None),
    status: Optional[List[str]] = Query(None), size: Optional[str] = None, model: Optional[str] = None,
):
    articles = _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id, model)
    pdf_bytes = build_inventory_pdf(db, articles, by_name=(user.full_name or user.username))
    filename = f"inventar_export_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
