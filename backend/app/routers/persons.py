from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("", response_model=list[schemas.PersonOut])
def list_persons(q: str = None, include_inactive: bool = False,
                  db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    query = db.query(models.Person)
    if not include_inactive:
        query = query.filter(models.Person.active == True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Person.first_name.ilike(like)) | (models.Person.last_name.ilike(like))
        )
    return query.order_by(models.Person.last_name).all()


@router.get("/{person_id}", response_model=schemas.PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    p = db.query(models.Person).get(person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    return p


@router.post("", response_model=schemas.PersonOut)
def create_person(payload: schemas.PersonCreate, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("persons", "issues"))):
    p = models.Person(**payload.dict())
    db.add(p)
    db.commit()
    db.refresh(p)
    # Person = Benutzer: automatisch ein Benutzerkonto (Standardrolle) anlegen
    from ..usernames import ensure_user_for_person
    linked = ensure_user_for_person(db, p)
    log_action(db, user, "create_person", "person", p.id,
               {"name": f"{p.first_name} {p.last_name}", "username": linked.username})
    return p


@router.put("/{person_id}", response_model=schemas.PersonOut)
def update_person(person_id: int, payload: schemas.PersonUpdate, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin", "verwalter"))):
    p = db.query(models.Person).get(person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    log_action(db, user, "update_person", "person", p.id, data)
    return p


@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db),
                   user=Depends(security.require_roles("admin"))):
    p = db.query(models.Person).get(person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")
    in_use = db.query(models.IssueRecord).filter(models.IssueRecord.person_id == person_id).count()
    linked_user = db.query(models.User).filter(models.User.person_id == person_id).count()
    if in_use or linked_user:
        # Nicht endgueltig loeschen, da Verlauf erhalten bleiben soll - stattdessen deaktivieren
        p.active = False
        db.commit()
        log_action(db, user, "deactivate_person", "person", person_id)
        return {"ok": True, "deactivated": True,
                "message": "Person hat bereits Verlauf/ist mit einem Benutzerkonto verknuepft und wurde stattdessen deaktiviert."}
    db.delete(p)
    db.commit()
    log_action(db, user, "delete_person", "person", person_id)
    return {"ok": True, "deactivated": False}


@router.post("/merge")
def merge_persons(payload: schemas.MergePersonsRequest, db: Session = Depends(get_db),
                  user=Depends(security.require_capability("persons"))):
    """Fuehrt zwei Personen/Benutzer zusammen (z.B. wenn eine echte Person ein
    zweites Mal unter falschem Namen angelegt wurde): Alle Ausgaben/Verlauf der
    Quell-Person werden auf die Ziel-Person umgehaengt, die Quell-Person und ihr
    Benutzerkonto werden deaktiviert."""
    if payload.source_id == payload.target_id:
        raise HTTPException(status_code=400, detail="Quelle und Ziel duerfen nicht identisch sein")
    src = db.query(models.Person).get(payload.source_id)
    tgt = db.query(models.Person).get(payload.target_id)
    if not src or not tgt:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")

    db.query(models.IssueRecord).filter(models.IssueRecord.person_id == src.id) \
        .update({models.IssueRecord.person_id: tgt.id})
    for u in db.query(models.User).filter(models.User.person_id == src.id).all():
        u.active = False
        u.person_id = None
    src.active = False
    db.commit()
    log_action(db, user, "merge_persons", "person", tgt.id,
               {"source_id": src.id, "target_id": tgt.id})
    return {"ok": True, "message": f"'{src.first_name} {src.last_name}' wurde in '{tgt.first_name} {tgt.last_name}' zusammengefuehrt."}


@router.get("/{person_id}/issues")
def person_issues(person_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Liefert alle Ausgabevorgaenge dieser Person, getrennt nach aktuell (offen) und Vergangenheit."""
    p = db.query(models.Person).get(person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person nicht gefunden")

    records = db.query(models.IssueRecord).options(
        joinedload(models.IssueRecord.article).joinedload(models.Article.type)
    ).filter(models.IssueRecord.person_id == person_id).order_by(models.IssueRecord.issue_date.desc()).all()

    def serialize(rec):
        return {
            "id": rec.id,
            "article_id": rec.article_id,
            "artikelnummer": rec.article.artikelnummer if rec.article else None,
            "type_id": rec.article.type_id if rec.article else None,
            "type_name": rec.article.type.name if rec.article and rec.article.type else None,
            "issue_date": rec.issue_date.isoformat() if rec.issue_date else None,
            "return_date": rec.return_date.isoformat() if rec.return_date else None,
            "condition_at_return": rec.condition_at_return,
            "notes": rec.notes,
        }

    current = [serialize(r) for r in records if not r.return_date]
    past = [serialize(r) for r in records if r.return_date]
    return {"current": current, "past": past}
