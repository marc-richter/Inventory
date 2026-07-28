import datetime as dt
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..config import IMAGES_DIR

router = APIRouter(prefix="/api/articles", tags=["articles"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

# Status-Uebergaenge, die zusaetzliche Pflichtangaben erfordern
STATUS_REQUIRED_FIELDS = {
    models.ArticleStatus.reparatur.value: ["repair_reason"],
}


def _gen_artikelnummer(db: Session, reserved: set = None) -> str:
    """Erzeugt eine neue, fortlaufende Artikelnummer (Format JAHR-00001).
    `reserved` kann eine Menge bereits in derselben (noch nicht committeten)
    Anfrage vergebener Nummern enthalten, damit z.B. bei der Mengenerfassung
    keine Nummer doppelt vergeben wird, bevor sie in der DB steht."""
    reserved = reserved or set()
    year = dt.datetime.utcnow().year
    prefix = f"{year}-"
    count = db.query(models.Article).filter(models.Article.artikelnummer.like(f"{prefix}%")).count()
    for _ in range(10000):
        count += 1
        candidate = f"{prefix}{count:05d}"
        if candidate in reserved:
            continue
        if not db.query(models.Article).filter(models.Article.artikelnummer == candidate).first():
            return candidate
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _article_query(db: Session):
    return db.query(models.Article).options(
        joinedload(models.Article.images),
        joinedload(models.Article.issues),
        joinedload(models.Article.created_by),
    )


def _is_eigen_only(user) -> bool:
    """True, wenn der Nutzer nur eingeschraenkte Rechte hat ('eigen' oder 'lesend')
    und keine hoehere Rolle - er darf dann nur die an ihn ausgegebenen (aktuellen
    und vergangenen) Artikel sehen. 'lesend' und 'eigen' sind damit auf die eigenen
    Ausgaben beschraenkt; 'helfer'/'verwalter'/'admin' sehen den gesamten Bestand."""
    roles = user.roles or []
    privileged = {"admin", "verwalter", "helfer"}
    restricted = {"eigen", "lesend"}
    return any(r in restricted for r in roles) and not any(r in privileged for r in roles)


def _eigen_article_ids(db: Session, user) -> list:
    if not user.person_id:
        return []
    rows = db.query(models.IssueRecord.article_id).filter(
        models.IssueRecord.person_id == user.person_id
    ).distinct().all()
    return [r[0] for r in rows]


@router.get("", response_model=List[schemas.ArticleOut])
def list_articles(
    db: Session = Depends(get_db),
    user=Depends(security.get_current_user),
    q: Optional[str] = None,
    id: Optional[List[int]] = Query(None),
    category_id: Optional[List[int]] = Query(None),
    type_id: Optional[List[int]] = Query(None),
    organization_id: Optional[List[int]] = Query(None),
    storage_location_id: Optional[List[int]] = Query(None),
    status: Optional[List[str]] = Query(None),
    size: Optional[str] = None,
    model: Optional[str] = None,
):
    query = _article_query(db)
    if _is_eigen_only(user):
        allowed = _eigen_article_ids(db, user)
        if not allowed:
            return []
        query = query.filter(models.Article.id.in_(allowed))
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
    return query.order_by(models.Article.artikelnummer.desc()).all()


@router.get("/by-number/{artikelnummer}", response_model=schemas.ArticleOut)
def get_article_by_number(artikelnummer: str, db: Session = Depends(get_db),
                           user=Depends(security.get_current_user)):
    """Schnellzugriff nach dem Scannen eines QR-/Barcodes mit der Artikelnummer."""
    a = _article_query(db).filter(models.Article.artikelnummer == artikelnummer.strip()).first()
    if not a:
        raise HTTPException(status_code=404, detail="Kein Artikel mit dieser Nummer gefunden")
    if _is_eigen_only(user) and a.id not in _eigen_article_ids(db, user):
        raise HTTPException(status_code=404, detail="Kein Artikel mit dieser Nummer gefunden")
    return a


# --- Vorlaeufige Inventarisierung + Genehmigung ---------------------------------

@router.post("/provisional", response_model=schemas.ArticleOut)
def create_provisional(payload: schemas.ArticleCreate, db: Session = Depends(get_db),
                       user=Depends(security.require_capability("issues"))):
    """Schnelle, VORLAEUFIGE Inventarisierung (z.B. bei der Ausgabe). Darf auch von
    Nutzern ohne Artikel-Recht angelegt werden; ein Berechtigter genehmigt/aendert
    sie spaeter. Optional an einen Nutzer zur Pruefung zuweisen."""
    artikelnummer = (payload.artikelnummer or "").strip() or _gen_artikelnummer(db)
    if db.query(models.Article).filter(models.Article.artikelnummer == artikelnummer).first():
        raise HTTPException(status_code=400, detail="Artikelnummer bereits vergeben")
    a = models.Article(
        artikelnummer=artikelnummer,
        category_id=payload.category_id,
        type_id=payload.type_id,
        size=payload.size, model=payload.model, properties=payload.properties,
        organization_id=payload.organization_id,
        storage_location_id=payload.storage_location_id,
        condition_notes=payload.condition_notes, remarks=payload.remarks,
        first_entry_date=payload.first_entry_date or dt.datetime.utcnow(),
        created_by_id=user.id,
        provisional=True, provisional_by_id=user.id,
        review_assignee_id=payload.review_assignee_id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(db, user, "create_provisional", "article", a.id, {"artikelnummer": a.artikelnummer})
    return a


@router.get("/provisional", response_model=List[schemas.ArticleOut])
def list_provisional(assigned_to_me: bool = False, db: Session = Depends(get_db),
                     user=Depends(security.require_capability("articles"))):
    q = _article_query(db).filter(models.Article.provisional == True)  # noqa: E712
    if assigned_to_me:
        q = q.filter(models.Article.review_assignee_id == user.id)
    return q.order_by(models.Article.created_at.desc()).all()


@router.get("/provisional/count")
def provisional_count(db: Session = Depends(get_db),
                      user=Depends(security.require_capability("articles"))):
    total = db.query(models.Article).filter(models.Article.provisional == True).count()  # noqa: E712
    mine = db.query(models.Article).filter(
        models.Article.provisional == True,  # noqa: E712
        models.Article.review_assignee_id == user.id,
    ).count()
    return {"total": total, "assigned_to_me": mine}


@router.post("/{article_id}/approve", response_model=schemas.ArticleOut)
def approve_provisional(article_id: int, db: Session = Depends(get_db),
                        user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.provisional = False
    a.review_assignee_id = None
    db.commit()
    db.refresh(a)
    log_action(db, user, "approve_provisional", "article", a.id)
    return a


@router.post("/{article_id}/skip")
def skip_provisional(article_id: int, db: Session = Depends(get_db),
                     user=Depends(security.require_capability("articles"))):
    """Ueberspringen: der Artikel bleibt vorlaeufig, die Zuweisung wird aber
    aufgehoben, damit ein anderer Berechtigter ihn spaeter pruefen kann."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.review_assignee_id = None
    db.commit()
    log_action(db, user, "skip_provisional", "article", a.id)
    return {"ok": True}


@router.post("/{article_id}/assign", response_model=schemas.ArticleOut)
def assign_review(article_id: int, payload: schemas.AssignReviewRequest, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.review_assignee_id = payload.user_id or None
    db.commit()
    db.refresh(a)
    log_action(db, user, "assign_review", "article", a.id, {"user_id": payload.user_id})
    return a


@router.get("/{article_id}", response_model=schemas.ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    a = _article_query(db).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if _is_eigen_only(user) and a.id not in _eigen_article_ids(db, user):
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return a


@router.post("", response_model=schemas.ArticleOut)
def create_article(payload: schemas.ArticleCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("articles"))):
    artikelnummer = (payload.artikelnummer or "").strip() or _gen_artikelnummer(db)
    if db.query(models.Article).filter(models.Article.artikelnummer == artikelnummer).first():
        raise HTTPException(status_code=400, detail="Artikelnummer bereits vergeben")
    a = models.Article(
        artikelnummer=artikelnummer,
        category_id=payload.category_id,
        type_id=payload.type_id,
        size=payload.size,
        model=payload.model,
        properties=payload.properties,
        organization_id=payload.organization_id,
        storage_location_id=payload.storage_location_id,
        condition_notes=payload.condition_notes,
        remarks=payload.remarks,
        first_entry_date=payload.first_entry_date or dt.datetime.utcnow(),
        created_by_id=user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(db, user, "create_article", "article", a.id, {"artikelnummer": a.artikelnummer})
    return a


@router.post("/bulk", response_model=List[schemas.ArticleOut])
def create_articles_bulk(payload: schemas.BulkArticleCreate, db: Session = Depends(get_db),
                          user=Depends(security.require_capability("articles"))):
    """Mengenerfassung: legt mehrere baugleiche Artikel (gleiche Kategorie/Typ/
    Groesse/Abteilung/Lagerort) auf einmal an - entweder mit automatisch
    fortlaufend vergebenen Artikelnummern (quantity) oder mit einer Liste
    manuell eingegebener bzw. eingescannter Nummern (artikelnummern)."""
    manual = [n.strip() for n in (payload.artikelnummern or []) if n.strip()]

    if manual and payload.quantity:
        raise HTTPException(status_code=400, detail="Bitte entweder eine Anzahl oder eine Liste von Artikelnummern angeben, nicht beides")
    if not manual and not payload.quantity:
        raise HTTPException(status_code=400, detail="Bitte eine Anzahl oder eine Liste von Artikelnummern angeben")

    if manual:
        # Duplikate innerhalb der eingegebenen Liste abfangen
        seen = set()
        duplicates_in_input = {n for n in manual if n in seen or seen.add(n)}
        if duplicates_in_input:
            raise HTTPException(status_code=400, detail=f"Artikelnummer(n) mehrfach in der Liste: {', '.join(sorted(duplicates_in_input))}")
        already_existing = [
            n for n in manual
            if db.query(models.Article).filter(models.Article.artikelnummer == n).first()
        ]
        if already_existing:
            raise HTTPException(status_code=400, detail=f"Artikelnummer(n) bereits vergeben: {', '.join(already_existing)}")
        numbers = manual
    else:
        if payload.quantity <= 0:
            raise HTTPException(status_code=400, detail="Anzahl muss groesser als 0 sein")
        if payload.quantity > 500:
            raise HTTPException(status_code=400, detail="Maximal 500 Artikel pro Mengenerfassung")
        numbers = []
        reserved = set()
        for _ in range(payload.quantity):
            n = _gen_artikelnummer(db, reserved)
            reserved.add(n)
            numbers.append(n)

    created = []
    for n in numbers:
        a = models.Article(
            artikelnummer=n,
            category_id=payload.category_id,
            type_id=payload.type_id,
            size=payload.size,
            model=payload.model,
            properties=payload.properties,
            organization_id=payload.organization_id,
            storage_location_id=payload.storage_location_id,
            condition_notes=payload.condition_notes,
            remarks=payload.remarks,
            first_entry_date=payload.first_entry_date or dt.datetime.utcnow(),
            created_by_id=user.id,
        )
        db.add(a)
        created.append(a)
    db.commit()
    for a in created:
        db.refresh(a)
    log_action(db, user, "create_articles_bulk", "article", None, {
        "count": len(created), "artikelnummern": [a.artikelnummer for a in created],
    })
    return created


@router.put("/{article_id}", response_model=schemas.ArticleOut)
def update_article(article_id: int, payload: schemas.ArticleUpdate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    log_action(db, user, "update_article", "article", a.id, data)
    return a


@router.put("/{article_id}/status", response_model=schemas.ArticleOut)
def change_status(article_id: int, payload: schemas.StatusChangeRequest, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    status_def = db.query(models.StatusDef).filter(models.StatusDef.key == payload.status).first()
    valid_keys = {s.key for s in db.query(models.StatusDef).filter(models.StatusDef.active == True).all()}  # noqa: E712
    # Eingebaute Status als Fallback zulassen, falls (noch) nicht geseedet
    valid_keys |= {s.value for s in models.ArticleStatus}
    if payload.status not in valid_keys:
        raise HTTPException(status_code=400, detail="Unbekannter Status")

    required = STATUS_REQUIRED_FIELDS.get(payload.status, [])
    for field in required:
        if not getattr(payload, field, None):
            raise HTTPException(status_code=400, detail=f"Feld '{field}' ist fuer diesen Status erforderlich")

    # Status mit Pflicht-Beschreibung (z.B. "Beschädigt"): condition_note ist Pflicht
    # und wird in die Beschaedigungs-Notizen des Artikels uebernommen.
    if status_def and status_def.require_note:
        note_text = (payload.condition_note or "").strip()
        if not note_text:
            raise HTTPException(status_code=400,
                                detail=f"Fuer den Status '{status_def.label}' ist eine Beschreibung erforderlich")
        a.condition_notes = note_text
    elif (payload.condition_note or "").strip():
        # Freiwillig mitgegebene Beschreibung trotzdem uebernehmen
        a.condition_notes = payload.condition_note.strip()

    # Beim Aussondern ist ein Grund (Freitext) Pflicht
    if payload.status == models.ArticleStatus.ausgemustert.value:
        if not (payload.reason or "").strip():
            raise HTTPException(status_code=400, detail="Beim Aussondern muss ein Grund angegeben werden")
        a.retire_reason = payload.reason.strip()
    else:
        a.retire_reason = ""

    a.status = payload.status
    if payload.status == models.ArticleStatus.reparatur.value:
        a.repair_reason = payload.repair_reason or ""
        a.repair_expected_return = payload.repair_expected_return
        # Reparaturort erfassen -> als aktueller Standort vermerken und als Lagerort
        # anlegen/zuordnen ("wo ist es gerade").
        loc = (payload.repair_location or "").strip()
        if loc:
            a.current_location = loc
            sl = db.query(models.StorageLocation).filter(models.StorageLocation.name == loc).first()
            if not sl:
                sl = models.StorageLocation(name=loc)
                db.add(sl)
                db.flush()
            a.storage_location_id = sl.id
    else:
        # Reparaturangaben nur relevant, solange der Artikel tatsaechlich in Reparatur ist
        a.repair_reason = ""
        a.repair_expected_return = None

    db.commit()
    db.refresh(a)
    log_action(db, user, "change_status", "article", a.id, {
        "status": payload.status, "note": payload.note,
        "repair_reason": payload.repair_reason, "repair_location": payload.repair_location,
        "repair_expected_return": str(payload.repair_expected_return),
    })
    return a


@router.delete("/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    db.delete(a)
    db.commit()
    log_action(db, user, "delete_article", "article", article_id)
    return {"ok": True}


@router.post("/{article_id}/images", response_model=schemas.ImageOut)
async def upload_image(article_id: int, file: UploadFile = File(...), kind: str = "normal",
                        db: Session = Depends(get_db),
                        user=Depends(security.require_capability("articles"))):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    ext = Path(file.filename).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        ext = ".jpg"
    fname = f"{a.artikelnummer}_{uuid.uuid4().hex[:8]}{ext}"
    dest = IMAGES_DIR / fname
    content = await file.read()
    dest.write_bytes(content)
    kind = "damage" if kind == "damage" else "normal"
    img = models.ArticleImage(article_id=a.id, filepath=fname, kind=kind)
    db.add(img)
    db.commit()
    db.refresh(img)
    log_action(db, user, "upload_image", "article", a.id, {"file": fname, "kind": kind})
    return img


@router.get("/images/{filename}")
def get_image(filename: str):
    # Bewusst ohne Auth-Pruefung, damit <img src="..."> im Frontend ohne
    # Zusatzaufwand funktioniert. Anwendung laeuft nur im lokalen Netz.
    path = IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    return FileResponse(path)


@router.delete("/images/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("articles"))):
    img = db.query(models.ArticleImage).get(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    if img.kind == "damage":
        raise HTTPException(
            status_code=400,
            detail="Dokumentationsbild (z.B. Beschädigung) kann aus Nachweisgründen nicht gelöscht werden.",
        )
    path = IMAGES_DIR / img.filepath
    if path.exists():
        path.unlink()
    db.delete(img)
    db.commit()
    log_action(db, user, "delete_image", "article", img.article_id, {"file": img.filepath})
    return {"ok": True}
