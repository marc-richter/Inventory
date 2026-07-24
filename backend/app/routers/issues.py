import datetime as dt
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.post("/issue", response_model=schemas.IssueOut)
def issue_article(payload: schemas.IssueCreate, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("issues"))):
    article = db.query(models.Article).get(payload.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if article.status == models.ArticleStatus.ausgegeben.value:
        raise HTTPException(status_code=400, detail="Artikel ist bereits ausgegeben")
    if not payload.person_id and not payload.recipient_name_freetext.strip():
        raise HTTPException(status_code=400, detail="Empfaenger fehlt")

    rec = models.IssueRecord(
        article_id=article.id,
        person_id=payload.person_id,
        recipient_name_freetext=payload.recipient_name_freetext,
        issue_date=payload.issue_date or dt.datetime.utcnow(),
        notes=payload.notes,
        issued_by_user_id=user.id,
    )
    article.status = models.ArticleStatus.ausgegeben.value

    # Aktueller Standort wird der Name der Empfaenger-Person (bzw. Freitext-Name).
    # Der stammdaten-Lagerort (storage_location_id) bleibt als Rueckgabeort erhalten.
    recipient_display = ""
    if payload.person_id:
        person = db.query(models.Person).get(payload.person_id)
        if person:
            recipient_display = f"{person.first_name} {person.last_name}".strip()
    if not recipient_display:
        recipient_display = (payload.recipient_name_freetext or "").strip()
    article.current_location = recipient_display

    db.add(rec)
    db.commit()
    db.refresh(rec)
    log_action(db, user, "issue_article", "article", article.id, {"issue_record_id": rec.id})
    return rec


@router.post("/{issue_id}/return", response_model=schemas.IssueOut)
def return_article(issue_id: int, payload: schemas.ReturnCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("issues"))):
    rec = db.query(models.IssueRecord).get(issue_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Ausgabevorgang nicht gefunden")
    if rec.return_date:
        raise HTTPException(status_code=400, detail="Artikel wurde bereits zurueckgenommen")
    rec.return_date = payload.return_date or dt.datetime.utcnow()
    rec.condition_at_return = payload.condition_at_return
    rec.notes = (rec.notes + "\n" + payload.notes).strip() if payload.notes else rec.notes
    rec.returned_by_user_id = user.id

    article = db.query(models.Article).get(rec.article_id)
    article.status = models.ArticleStatus.verfuegbar.value
    # Aktueller Standort zurueckgesetzt - Artikel ist wieder am stammdaten-Lagerort.
    article.current_location = ""
    if payload.condition_at_return:
        article.condition_notes = payload.condition_at_return

    db.commit()
    db.refresh(rec)
    log_action(db, user, "return_article", "article", article.id, {"issue_record_id": rec.id})
    return rec


@router.post("/return-by-article/{article_id}", response_model=schemas.IssueOut)
def return_by_article(article_id: int, payload: schemas.ReturnCreate, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("issues"))):
    """Nimmt einen Artikel anhand seiner ID zurueck (fuer die Scan-/Schnellausgabe:
    man scannt den Artikel, ohne den konkreten Ausgabevorgang zu kennen). Sucht den
    offenen Ausgabevorgang und schliesst ihn ab."""
    rec = db.query(models.IssueRecord).filter(
        models.IssueRecord.article_id == article_id,
        models.IssueRecord.return_date.is_(None),
    ).order_by(models.IssueRecord.issue_date.desc()).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Kein offener Ausgabevorgang fuer diesen Artikel")
    rec.return_date = payload.return_date or dt.datetime.utcnow()
    rec.condition_at_return = payload.condition_at_return
    rec.notes = (rec.notes + "\n" + payload.notes).strip() if payload.notes else rec.notes
    rec.returned_by_user_id = user.id

    article = db.query(models.Article).get(rec.article_id)
    article.status = models.ArticleStatus.verfuegbar.value
    article.current_location = ""
    if payload.condition_at_return:
        article.condition_notes = payload.condition_at_return

    db.commit()
    db.refresh(rec)
    log_action(db, user, "return_article", "article", article.id, {"issue_record_id": rec.id})
    return rec


@router.get("/article/{article_id}", response_model=list[schemas.IssueOut])
def issue_history(article_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.IssueRecord).filter(models.IssueRecord.article_id == article_id) \
        .order_by(models.IssueRecord.issue_date.desc()).all()


def _serialize_open(rec: models.IssueRecord) -> dict:
    a = rec.article
    return {
        "id": rec.id,
        "issue_date": rec.issue_date.isoformat() if rec.issue_date else None,
        "notes": rec.notes,
        "person_id": rec.person_id,
        "recipient_name_freetext": rec.recipient_name_freetext,
        "recipient_display": (
            f"{rec.person.first_name} {rec.person.last_name}" if rec.person else rec.recipient_name_freetext
        ),
        "article_id": a.id if a else None,
        "artikelnummer": a.artikelnummer if a else None,
        "category_id": a.category_id if a else None,
        "type_id": a.type_id if a else None,
        "type_name": a.type.name if a and a.type else None,
        "size": a.size if a else None,
        "organization_id": a.organization_id if a else None,
        "organization_name": a.organization.name if a and a.organization else None,
        "storage_location_id": a.storage_location_id if a else None,
        "storage_location_name": a.storage_location.name if a and a.storage_location else None,
    }


@router.get("/open")
def open_issues(
    db: Session = Depends(get_db), user=Depends(security.get_current_user),
    q: Optional[str] = None,
    type_id: Optional[List[int]] = Query(None),
    organization_id: Optional[List[int]] = Query(None),
    storage_location_id: Optional[List[int]] = Query(None),
):
    query = db.query(models.IssueRecord).options(
        joinedload(models.IssueRecord.article).joinedload(models.Article.type),
        joinedload(models.IssueRecord.article).joinedload(models.Article.organization),
        joinedload(models.IssueRecord.article).joinedload(models.Article.storage_location),
        joinedload(models.IssueRecord.person),
    ).join(models.Article).filter(models.IssueRecord.return_date.is_(None))

    # Eingeschraenkte Rollen (lesend/eigen) sehen nur die an sie selbst ausgegebenen
    # Materialien - konsistent zur Artikel-Uebersicht.
    roles = user.roles or []
    restricted = (any(r in {"eigen", "lesend"} for r in roles)
                  and not any(r in {"admin", "verwalter", "helfer"} for r in roles))
    if restricted:
        if not user.person_id:
            return []
        query = query.filter(models.IssueRecord.person_id == user.person_id)

    if type_id:
        query = query.filter(models.Article.type_id.in_(type_id))
    if organization_id:
        query = query.filter(models.Article.organization_id.in_(organization_id))
    if storage_location_id:
        query = query.filter(models.Article.storage_location_id.in_(storage_location_id))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Article.artikelnummer.ilike(like)) |
            (models.IssueRecord.recipient_name_freetext.ilike(like))
        )

    records = query.order_by(models.IssueRecord.issue_date.desc()).all()
    return [_serialize_open(r) for r in records]


@router.get("/mine")
def my_open_issues(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Aktuell an den eingeloggten Benutzer (ueber verknuepfte Person) ausgegebene Artikel."""
    if not user.person_id:
        return []
    records = db.query(models.IssueRecord).options(
        joinedload(models.IssueRecord.article).joinedload(models.Article.type),
        joinedload(models.IssueRecord.article).joinedload(models.Article.organization),
        joinedload(models.IssueRecord.article).joinedload(models.Article.storage_location),
        joinedload(models.IssueRecord.person),
    ).filter(
        models.IssueRecord.person_id == user.person_id,
        models.IssueRecord.return_date.is_(None),
    ).order_by(models.IssueRecord.issue_date.desc()).all()
    return [_serialize_open(r) for r in records]
