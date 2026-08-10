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
    # Eager-Load der 1:1-/n:1-Beziehungen, die bei der Serialisierung (ArticleOut)
    # gebraucht werden – vermeidet N+1-Abfragen pro Artikel.
    return db.query(models.Article).options(
        joinedload(models.Article.images),
        joinedload(models.Article.issues),
        joinedload(models.Article.created_by),
        joinedload(models.Article.provisional_by),
        joinedload(models.Article.review_assignee),
        joinedload(models.Article.storage_node),
    )


def _warm_node_cache(db: Session):
    """Den gesamten (kleinen) Standort-Baum einmalig in die Session laden. Danach
    liest die `location_path`-Eigenschaft die Eltern-Kette aus dem Identity-Map,
    ohne pro Artikel/Ebene eine eigene DB-Abfrage auszuloesen."""
    db.query(models.StorageNode).all()


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
        query = query.filter(models.Article.size.ilike(f"%{size}%"))
    if model:
        query = query.filter(models.Article.model.ilike(f"%{model}%"))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Article.artikelnummer.ilike(like)) |
            (models.Article.remarks.ilike(like)) |
            (models.Article.condition_notes.ilike(like)) |
            (models.Article.model.ilike(like)) |
            (models.Article.size.ilike(like)) |
            (models.Article.properties.ilike(like)) |
            (models.Article.type.has(models.ArticleType.name.ilike(like)))
        )
    _warm_node_cache(db)
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
        etage=payload.etage, raum=payload.raum, schrank=payload.schrank, fach=payload.fach,
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
    from .. import telegram
    telegram.notify_event(db, "provisional",
                          f"🆕 Neuer vorläufiger Artikel {a.artikelnummer} von "
                          f"{telegram.actor_label(db, user)} – bitte prüfen.")
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


@router.post("/relocate")
def relocate_articles(payload: schemas.RelocateRequest, db: Session = Depends(get_db),
                      user=Depends(security.require_capability("articles"))):
    """Die uebergebenen Artikel einem verwalteten Standort-Knoten zuordnen (Umlagern
    ausserhalb einer Inventur). Fuer die Inventur siehe den Inventur-Router
    (/api/inventory/campaigns/{id}/scan)."""
    if not payload.article_ids:
        return {"ok": True, "updated": 0}
    arts = db.query(models.Article).filter(models.Article.id.in_(payload.article_ids)).all()
    for a in arts:
        a.storage_node_id = payload.storage_node_id
    db.commit()
    log_action(db, user, "relocate_articles", "storage_node", payload.storage_node_id,
               {"count": len(arts)})
    return {"ok": True, "updated": len(arts)}


@router.get("/{article_id}", response_model=schemas.ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    a = _article_query(db).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if _is_eigen_only(user) and a.id not in _eigen_article_ids(db, user):
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return a


@router.get("/{article_id}/revision")
def article_revision(article_id: int, db: Session = Depends(get_db),
                     user=Depends(security.get_current_user)):
    """Leichter Endpunkt fuer die Live-Aktualisierung: aktueller Aenderungsstand und
    wer zuletzt etwas geaendert hat. Wird von der Detailseite regelmaessig abgefragt,
    um Aenderungen anderer Nutzer sofort zu erkennen."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    last = db.query(models.AuditLog).filter(
        models.AuditLog.entity_type == "article",
        models.AuditLog.entity_id == article_id,
    ).order_by(models.AuditLog.timestamp.desc()).first()
    name = last.username if last else None
    if last and last.user_id:
        u = db.query(models.User).get(last.user_id)
        if u:
            name = u.full_name or u.username
    return {
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "last_by_id": last.user_id if last else None,
        "last_by_name": name,
        "last_action": last.action if last else None,
    }


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
        storage_node_id=payload.storage_node_id,
        etage=payload.etage, raum=payload.raum, schrank=payload.schrank, fach=payload.fach,
        condition_notes=payload.condition_notes,
        remarks=payload.remarks,
        issuable_override=payload.issuable_override,
        is_psa=payload.is_psa,
        is_vehicle=payload.is_vehicle,
        license_plate=(payload.license_plate or "").strip(),
        vin=(payload.vin or "").strip(),
        first_registration=payload.first_registration,
        first_entry_date=payload.first_entry_date or dt.datetime.utcnow(),
        created_by_id=user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(db, user, "create_article", "article", a.id, {"artikelnummer": a.artikelnummer})
    return a


@router.post("/{article_id}/vehicle-node", response_model=schemas.StorageNodeOut)
def set_vehicle_node(article_id: int, payload: schemas.VehicleNodeRequest, db: Session = Depends(get_db),
                     user=Depends(security.require_capability("articles"))):
    """Aktiviert das Fahrzeug als Lagerort-Knoten im Baum (bzw. verschiebt ihn unter
    einen anderen Standort). Der Knoten kann anschließend Schränke/Fächer/Taschen und
    Artikel enthalten."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    if not a.is_vehicle:
        raise HTTPException(status_code=400, detail="Artikel ist nicht als Fahrzeug gekennzeichnet")
    parent = None
    if payload.parent_id:
        parent = db.query(models.StorageNode).get(payload.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Übergeordneter Standort nicht gefunden")
        if parent.vehicle_article_id:
            raise HTTPException(status_code=400, detail="Ein Fahrzeug kann nicht unter einem Fahrzeug liegen")
    name = (a.license_plate or a.artikelnummer or f"Fahrzeug {a.id}").strip()
    node = db.query(models.StorageNode).filter(models.StorageNode.vehicle_article_id == a.id).first()
    if not node:
        node = models.StorageNode(level="fahrzeug", name=name, vehicle_article_id=a.id,
                                  parent_id=parent.id if parent else None)
        db.add(node)
    else:
        node.name = name
        node.parent_id = parent.id if parent else None
    db.commit()
    db.refresh(node)
    log_action(db, user, "vehicle_node", "article", a.id, {"node_id": node.id})
    return node


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
    prev_status = a.status
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

    # Verlaesst der Artikel den Status „zu prüfen" (Pruefung erledigt), Pruef-Zeitpunkt
    # merken und faellige Checkliste zuruecksetzen.
    if prev_status == "zu_pruefen" and a.status != "zu_pruefen":
        a.last_inspection_at = dt.datetime.utcnow()
        a.pending_checklist_id = None
        a.needs_inspection = False
    db.commit()
    db.refresh(a)
    # Wiederfund: war der Artikel verschollen und ist jetzt wieder verfuegbar,
    # benachrichtigen (z.B. per Telegram).
    if prev_status == "verschollen" and a.status != "verschollen":
        from .. import telegram
        telegram.notify_refind(db, a)
    log_action(db, user, "change_status", "article", a.id, {
        "status": payload.status, "note": payload.note,
        "repair_reason": payload.repair_reason, "repair_location": payload.repair_location,
        "repair_expected_return": str(payload.repair_expected_return),
    })
    return a


@router.post("/{article_id}/washed", response_model=schemas.ArticleOut)
def mark_washed(article_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_capability("articles"))):
    """Artikel als gewaschen markieren: Wasch-Zähler +1, aus „zu waschen" zurück auf
    „verfügbar", danach ggf. PSA-Prüfung fällig setzen."""
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.wash_count = (a.wash_count or 0) + 1
    if a.status == "zu_waschen":
        a.status = models.ArticleStatus.verfuegbar.value
    from .. import inspection
    inspection.flag_if_due(db, a, just_returned=False)
    db.commit()
    db.refresh(a)
    log_action(db, user, "mark_washed", "article", a.id, {"wash_count": a.wash_count})
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
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Bild ist zu groß (max. 20 MB)")
    # Sicherstellen, dass es wirklich ein Bild ist (verhindert Ablage beliebiger Dateien).
    try:
        import io as _io
        from PIL import Image as _Image
        _Image.open(_io.BytesIO(content)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Datei ist kein gültiges Bild")

    # Optionale, vom Administrator einstellbare Verkleinerung: spart Speicher auf dem
    # Pi und beschleunigt die Detailansicht. Bei Fehlern wird das Original behalten.
    from ..settings_helper import get_setting
    if (get_setting(db, "image_resize_enabled", "false") or "").lower() == "true":
        try:
            max_px = int(get_setting(db, "image_resize_max_px", "1600") or 1600)
        except (TypeError, ValueError):
            max_px = 1600
        try:
            quality = int(get_setting(db, "image_resize_quality", "85") or 85)
        except (TypeError, ValueError):
            quality = 85
        max_px = max(320, min(4000, max_px))
        quality = max(40, min(95, quality))
        try:
            import io as _io3
            from PIL import Image as _Img
            im = _Img.open(_io3.BytesIO(content)).convert("RGB")
            im.thumbnail((max_px, max_px))
            out = _io3.BytesIO()
            im.save(out, "JPEG", quality=quality)
            content = out.getvalue()
            ext = ".jpg"   # neu kodiert als JPEG
        except Exception:
            pass

    fname = f"{a.artikelnummer}_{uuid.uuid4().hex[:8]}{ext}"
    dest = IMAGES_DIR / fname
    dest.write_bytes(content)
    kind = "damage" if kind == "damage" else "normal"
    img = models.ArticleImage(article_id=a.id, filepath=fname, kind=kind)
    db.add(img)
    db.commit()
    db.refresh(img)
    log_action(db, user, "upload_image", "article", a.id, {"file": fname, "kind": kind})
    return img


@router.get("/images/{filename}")
def get_image(filename: str, w: int = None):
    # Bewusst ohne Auth-Pruefung, damit <img src="..."> im Frontend ohne
    # Zusatzaufwand funktioniert. Anwendung laeuft nur im lokalen Netz.
    # Mit ?w=<pixel> wird ein (gecachtes) verkleinertes Vorschaubild geliefert -
    # so laedt die Uebersicht mit vielen Mini-Bildern deutlich schneller.
    # Pfad-Traversal ausschliessen: nur einfache Dateinamen zulassen.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Ungültiger Dateiname")
    path = IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")
    if w and int(w) > 0:
        from PIL import Image
        size = min(int(w), 512)
        thumbs = IMAGES_DIR / ".thumbs"
        try:
            thumbs.mkdir(parents=True, exist_ok=True)
            tpath = thumbs / f"{size}_{filename}.jpg"
            if not tpath.exists() or tpath.stat().st_mtime < path.stat().st_mtime:
                img = Image.open(path)
                img = img.convert("RGB")
                img.thumbnail((size, size))
                img.save(tpath, "JPEG", quality=70)
            return FileResponse(tpath, media_type="image/jpeg")
        except Exception:
            return FileResponse(path)   # Fallback: Originalbild
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
