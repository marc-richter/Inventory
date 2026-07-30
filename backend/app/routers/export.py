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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
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
        joinedload(models.Article.created_by),
    )
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
    subtitle = f"Erstellt am {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} von {user.full_name or user.username} · {len(articles)} Artikel"
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
    filename = f"inventar_export_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
