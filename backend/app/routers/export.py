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
from reportlab.lib.styles import getSampleStyleSheet

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


def _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id=None):
    query = db.query(models.Article).options(
        joinedload(models.Article.category), joinedload(models.Article.type),
        joinedload(models.Article.organization), joinedload(models.Article.storage_location),
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
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Article.artikelnummer.ilike(like)) |
            (models.Article.remarks.ilike(like)) |
            (models.Article.condition_notes.ilike(like))
        )
    return query.order_by(models.Article.artikelnummer).all()


HEADERS = ["Artikelnummer", "Kategorie", "Typ", "Groesse", "Abteilung", "Lagerort", "Status",
           "Erstinventarisierung", "Beschaedigungen", "Bemerkungen"]


def _row(a: models.Article):
    return [
        a.artikelnummer,
        a.category.name if a.category else "",
        a.type.name if a.type else "",
        a.size or "",
        a.organization.name if a.organization else "",
        a.storage_location.name if a.storage_location else "",
        a.status,
        a.first_entry_date.strftime("%d.%m.%Y") if a.first_entry_date else "",
        a.condition_notes or "",
        a.remarks or "",
    ]


@router.get("/csv")
def export_csv(
    db: Session = Depends(get_db), user=Depends(security.get_current_user),
    q: Optional[str] = None,
    id: Optional[List[int]] = Query(None),
    category_id: Optional[List[int]] = Query(None), type_id: Optional[List[int]] = Query(None),
    organization_id: Optional[List[int]] = Query(None), storage_location_id: Optional[List[int]] = Query(None),
    status: Optional[List[str]] = Query(None), size: Optional[str] = None,
):
    articles = _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(HEADERS)
    for a in articles:
        writer.writerow(_row(a))
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
    status: Optional[List[str]] = Query(None), size: Optional[str] = None,
):
    articles = _query_articles(db, q, category_id, type_id, organization_id, storage_location_id, status, size, id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []
    logo = _logo_flowable(db)
    if logo is not None:
        elements.append(logo)
        elements.append(Spacer(1, 6))
    org_name = get_setting(db, "org_name", "")
    title = f"Inventarliste – {org_name}" if org_name else "Inventarliste"
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Paragraph(
        f"Erstellt am {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} von {user.full_name or user.username}",
        styles["Normal"]))
    elements.append(Spacer(1, 8))

    data = [HEADERS] + [_row(a) for a in articles]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    filename = f"inventar_export_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
