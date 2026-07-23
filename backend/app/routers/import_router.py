import csv
import io
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/import", tags=["import"])

# Muss zur Spaltenreihenfolge/-benennung von routers/export.py (HEADERS) passen,
# damit zuvor exportierte CSV-Dateien 1:1 wieder eingelesen werden koennen.
HEADER_MAP = {
    "Artikelnummer": "artikelnummer",
    "Kategorie": "category_name",
    "Typ": "type_name",
    "Groesse": "size",
    "Abteilung": "organization_name",
    "Lagerort": "storage_location_name",
    "Status": "status",
    "Erstinventarisierung": "first_entry_date",
    "Beschaedigungen": "condition_notes",
    "Bemerkungen": "remarks",
}

VALID_STATUS = {s.value for s in models.ArticleStatus}


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="Zeichenkodierung der Datei konnte nicht erkannt werden")


def _parse_csv(content: bytes) -> list:
    text = _decode(content)
    # Trennzeichen automatisch erkennen (Standard-Export nutzt ";", Excel exportiert
    # je nach Ländereinstellung manchmal auch "," oder Tab)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Die Datei enthaelt keine erkennbare Kopfzeile")

    missing = [h for h in HEADER_MAP if h not in reader.fieldnames]
    if "Artikelnummer" in missing:
        raise HTTPException(
            status_code=400,
            detail="Spalte 'Artikelnummer' fehlt - bitte eine zuvor mit diesem Programm "
                   "exportierte CSV-Datei verwenden (Einstellungen bzw. Übersicht -> CSV Export).",
        )

    rows = []
    for raw in reader:
        row = {}
        for header, field in HEADER_MAP.items():
            row[field] = (raw.get(header) or "").strip()
        if row.get("artikelnummer"):
            rows.append(row)
    return rows


def _article_to_fieldset(a: models.Article) -> schemas.ImportFieldSet:
    return schemas.ImportFieldSet(
        category_name=a.category.name if a.category else "",
        type_name=a.type.name if a.type else "",
        size=a.size or "",
        organization_name=a.organization.name if a.organization else "",
        storage_location_name=a.storage_location.name if a.storage_location else "",
        status=a.status,
        first_entry_date=a.first_entry_date.strftime("%d.%m.%Y") if a.first_entry_date else "",
        condition_notes=a.condition_notes or "",
        remarks=a.remarks or "",
    )


@router.post("/preview", response_model=schemas.ImportPreviewOut)
async def import_preview(file: UploadFile = File(...), db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin", "verwalter"))):
    """Liest eine (typischerweise zuvor exportierte) CSV-Datei ein und stellt
    fest, welche Artikelnummern bereits existieren (Duplikate) und welche neu
    waeren - ohne dabei schon irgendetwas in der Datenbank zu veraendern."""
    content = await file.read()
    parsed = _parse_csv(content)
    if not parsed:
        raise HTTPException(status_code=400, detail="Keine verwertbaren Zeilen in der Datei gefunden")

    numbers = [r["artikelnummer"] for r in parsed]
    existing_articles = db.query(models.Article).options(
        joinedload(models.Article.category), joinedload(models.Article.type),
        joinedload(models.Article.organization), joinedload(models.Article.storage_location),
    ).filter(models.Article.artikelnummer.in_(numbers)).all()
    existing_by_number = {a.artikelnummer: a for a in existing_articles}

    out_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    seen_in_file = set()

    for r in parsed:
        number = r["artikelnummer"]
        error = None
        if number in seen_in_file:
            error = "Artikelnummer mehrfach in der Datei enthalten"
        seen_in_file.add(number)

        imported = schemas.ImportFieldSet(
            category_name=r["category_name"], type_name=r["type_name"], size=r["size"],
            organization_name=r["organization_name"], storage_location_name=r["storage_location_name"],
            status=r["status"] if r["status"] in VALID_STATUS else "verfuegbar",
            first_entry_date=r["first_entry_date"], condition_notes=r["condition_notes"], remarks=r["remarks"],
        )

        existing = existing_by_number.get(number)
        if existing is None and not error and not imported.category_name:
            error = "Spalte 'Kategorie' ist leer - fuer neue Artikel erforderlich"
        if existing is None and not error and not imported.type_name:
            error = "Spalte 'Typ' ist leer - fuer neue Artikel erforderlich"

        if error:
            error_count += 1
        elif existing is not None:
            duplicate_count += 1
        else:
            new_count += 1

        out_rows.append(schemas.ImportPreviewRow(
            artikelnummer=number,
            is_duplicate=existing is not None,
            imported=imported,
            existing=_article_to_fieldset(existing) if existing else None,
            existing_article_id=existing.id if existing else None,
            error=error,
        ))

    return schemas.ImportPreviewOut(
        total_rows=len(out_rows), new_count=new_count,
        duplicate_count=duplicate_count, error_count=error_count, rows=out_rows,
    )


def _get_or_create_category(db: Session, name: str) -> Optional[models.Category]:
    name = (name or "").strip()
    if not name:
        return None
    existing = db.query(models.Category).filter(models.Category.name.ilike(name)).first()
    if existing:
        return existing
    c = models.Category(name=name)
    db.add(c)
    db.flush()
    return c


def _get_or_create_type(db: Session, name: str, category_id: int) -> Optional[models.ArticleType]:
    name = (name or "").strip()
    if not name or not category_id:
        return None
    existing = db.query(models.ArticleType).filter(
        models.ArticleType.category_id == category_id, models.ArticleType.name.ilike(name),
    ).first()
    if existing:
        return existing
    t = models.ArticleType(name=name, category_id=category_id)
    db.add(t)
    db.flush()
    return t


def _get_or_create_organization(db: Session, name: str) -> Optional[models.Organization]:
    name = (name or "").strip()
    if not name:
        return None
    existing = db.query(models.Organization).filter(models.Organization.name.ilike(name)).first()
    if existing:
        return existing
    o = models.Organization(name=name)
    db.add(o)
    db.flush()
    return o


def _get_or_create_storage_location(db: Session, name: str) -> Optional[models.StorageLocation]:
    name = (name or "").strip()
    if not name:
        return None
    existing = db.query(models.StorageLocation).filter(models.StorageLocation.name.ilike(name)).first()
    if existing:
        return existing
    loc = models.StorageLocation(name=name)
    db.add(loc)
    db.flush()
    return loc


def _parse_date(value: str) -> Optional[dt.datetime]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@router.post("/commit", response_model=schemas.ImportCommitResult)
def import_commit(payload: schemas.ImportCommitRequest, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin", "verwalter"))):
    """Fuehrt einen zuvor per /preview begutachteten Import aus. Fuer jede
    Zeile wird per `resolution` entschieden:
      - create_new: legt einen neuen Artikel an
      - keep_existing: bestehender Datensatz bleibt unveraendert (wird uebersprungen)
      - keep_imported: bestehender Datensatz wird mit den importierten Werten ueberschrieben
    """
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for row in payload.rows:
        try:
            if row.resolution == "keep_existing":
                skipped += 1
                continue

            imp = row.imported
            category = _get_or_create_category(db, imp.category_name)
            article_type = _get_or_create_type(db, imp.type_name, category.id) if category else None
            organization = _get_or_create_organization(db, imp.organization_name)
            storage_location = _get_or_create_storage_location(db, imp.storage_location_name)
            status_value = imp.status if imp.status in VALID_STATUS else models.ArticleStatus.verfuegbar.value
            first_entry_date = _parse_date(imp.first_entry_date) or dt.datetime.utcnow()

            if row.resolution == "create_new":
                if not category or not article_type:
                    errors.append(f"{row.artikelnummer}: Kategorie/Typ fehlt, Artikel wurde nicht angelegt")
                    skipped += 1
                    continue
                existing = db.query(models.Article).filter(models.Article.artikelnummer == row.artikelnummer).first()
                if existing:
                    errors.append(f"{row.artikelnummer}: existiert bereits, wurde uebersprungen (bitte Duplikatsbehandlung waehlen)")
                    skipped += 1
                    continue
                a = models.Article(
                    artikelnummer=row.artikelnummer, category_id=category.id, type_id=article_type.id,
                    size=imp.size, organization_id=organization.id if organization else None,
                    storage_location_id=storage_location.id if storage_location else None,
                    status=status_value, condition_notes=imp.condition_notes, remarks=imp.remarks,
                    first_entry_date=first_entry_date, created_by_id=user.id,
                )
                db.add(a)
                created += 1

            elif row.resolution == "keep_imported":
                a = db.query(models.Article).filter(models.Article.artikelnummer == row.artikelnummer).first()
                if not a:
                    errors.append(f"{row.artikelnummer}: bestehender Artikel nicht gefunden, wurde uebersprungen")
                    skipped += 1
                    continue
                if category:
                    a.category_id = category.id
                if article_type:
                    a.type_id = article_type.id
                a.size = imp.size
                a.organization_id = organization.id if organization else None
                a.storage_location_id = storage_location.id if storage_location else None
                a.status = status_value
                a.condition_notes = imp.condition_notes
                a.remarks = imp.remarks
                a.first_entry_date = first_entry_date
                updated += 1
            else:
                errors.append(f"{row.artikelnummer}: unbekannte Aktion '{row.resolution}'")
                skipped += 1
        except Exception as exc:  # robust gegen einzelne fehlerhafte Zeilen
            errors.append(f"{row.artikelnummer}: {exc}")
            skipped += 1

    db.commit()
    log_action(db, user, "import_csv", "article", None, {
        "created": created, "updated": updated, "skipped": skipped, "error_count": len(errors),
    })
    return schemas.ImportCommitResult(created=created, updated=updated, skipped=skipped, errors=errors)
