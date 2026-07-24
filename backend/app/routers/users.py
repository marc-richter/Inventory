from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..settings_helper import get_setting

router = APIRouter(prefix="/api/users", tags=["users"])


def _out(u: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=u.id, username=u.username, full_name=u.full_name, roles=u.roles or [],
        person_id=u.person_id, active=u.active, pin_length=u.pin_length,
        has_password=bool(u.password_hash), has_pin=bool(u.pin_hash),
    )


def _split_name(name: str):
    parts = (name or "").strip().split()
    if not parts:
        return ("Benutzer", "-")
    if len(parts) == 1:
        return (parts[0], "-")
    return (parts[0], " ".join(parts[1:]))


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db),
               user: models.User = Depends(security.require_roles("admin"))):
    return [_out(u) for u in db.query(models.User).order_by(models.User.username).all()]


@router.post("", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db),
                 admin: models.User = Depends(security.require_roles("admin"))):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Benutzername bereits vergeben")
    pin_length = payload.pin_length or int(get_setting(db, "pin_length_default", "4"))

    # Person = Benutzer: Ist keine bestehende Person ausgewaehlt, wird automatisch
    # ein Personen-Datensatz aus dem Namen (bzw. Benutzernamen) angelegt und
    # verknuepft - so funktionieren "Meine Artikel" und die Empfaenger-Zuordnung
    # auch fuer manuell angelegte Konten.
    person_id = payload.person_id
    if not person_id:
        first, last = _split_name(payload.full_name or payload.username)
        person = models.Person(first_name=first, last_name=last, active=True)
        db.add(person)
        db.commit()
        db.refresh(person)
        person_id = person.id

    u = models.User(
        username=payload.username,
        full_name=payload.full_name,
        roles=payload.roles or ["helfer"],
        person_id=person_id,
        pin_length=pin_length,
    )
    if payload.password:
        u.password_hash = security.hash_secret(payload.password)
    if payload.pin:
        if len(payload.pin) != pin_length or not payload.pin.isdigit():
            raise HTTPException(status_code=400, detail=f"PIN muss genau {pin_length} Ziffern haben")
        u.pin_hash = security.hash_secret(payload.pin)
    db.add(u)
    db.commit()
    db.refresh(u)
    log_action(db, admin, "create_user", "user", u.id, {"username": u.username})
    return _out(u)


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db),
                 admin: models.User = Depends(security.require_roles("admin"))):
    u = db.query(models.User).get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="Benutzername darf nicht leer sein")
        if new_username != u.username:
            clash = db.query(models.User).filter(
                models.User.username == new_username, models.User.id != u.id
            ).first()
            if clash:
                raise HTTPException(status_code=400,
                                    detail=f"Benutzername '{new_username}' ist bereits vergeben")
            u.username = new_username
    if payload.full_name is not None:
        u.full_name = payload.full_name
    if payload.roles is not None:
        if not payload.roles:
            raise HTTPException(status_code=400, detail="Mindestens eine Rolle erforderlich")
        u.roles = payload.roles
    if payload.person_id is not None:
        u.person_id = payload.person_id if payload.person_id != 0 else None
    if payload.active is not None:
        u.active = payload.active
    if payload.pin_length is not None:
        u.pin_length = payload.pin_length
    if payload.password:
        u.password_hash = security.hash_secret(payload.password)
    if payload.pin:
        length = payload.pin_length or u.pin_length
        if len(payload.pin) != length or not payload.pin.isdigit():
            raise HTTPException(status_code=400, detail=f"PIN muss genau {length} Ziffern haben")
        u.pin_hash = security.hash_secret(payload.pin)
    db.commit()
    db.refresh(u)
    log_action(db, admin, "update_user", "user", u.id)
    return _out(u)


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                 admin: models.User = Depends(security.require_roles("admin"))):
    u = db.query(models.User).get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if u.id == admin.id:
        raise HTTPException(status_code=400, detail="Eigenen Account nicht loeschen")

    # Fehlermeldung, wenn der Benutzer (ueber seine verknuepfte Person) noch Material
    # ausgegeben hat - dieses muss erst zurueckgenommen werden.
    if u.person_id:
        open_cnt = db.query(models.IssueRecord).filter(
            models.IssueRecord.person_id == u.person_id,
            models.IssueRecord.return_date.is_(None),
        ).count()
        if open_cnt:
            raise HTTPException(
                status_code=400,
                detail=(f"Benutzer '{u.username}' hat noch {open_cnt} ausgegebene(s) Material. "
                        "Bitte zuerst zurücknehmen, dann kann das Konto gelöscht werden."),
            )

    # Referenzen entkoppeln, damit eine echte Loeschung moeglich ist (Verlauf bleibt
    # erhalten, verliert nur die Verknuepfung zum ausfuehrenden/anlegenden Benutzer).
    db.query(models.IssueRecord).filter(models.IssueRecord.issued_by_user_id == u.id) \
        .update({models.IssueRecord.issued_by_user_id: None})
    db.query(models.IssueRecord).filter(models.IssueRecord.returned_by_user_id == u.id) \
        .update({models.IssueRecord.returned_by_user_id: None})
    db.query(models.Article).filter(models.Article.created_by_id == u.id) \
        .update({models.Article.created_by_id: None})

    uname = u.username
    db.delete(u)
    db.commit()
    log_action(db, admin, "delete_user", "user", None, {"username": uname})
    return {"ok": True, "deleted": True}


@router.post("/merge")
def merge_users(payload: schemas.MergeUsersRequest, db: Session = Depends(get_db),
                admin: models.User = Depends(security.require_roles("admin"))):
    """Fuehrt zwei Benutzerkonten zusammen: Alle Bezuege (ausgegeben/zurueckgenommen/
    angelegt) sowie - bei verknuepften Personen - der Ausgabe-Verlauf werden auf das
    Zielkonto umgehaengt. Fehlende Zugangsdaten des Ziels werden vom Quellkonto
    uebernommen, Rollen vereinigt; das Quellkonto wird anschliessend geloescht."""
    if payload.source_id == payload.target_id:
        raise HTTPException(status_code=400, detail="Quelle und Ziel duerfen nicht identisch sein")
    src = db.query(models.User).get(payload.source_id)
    tgt = db.query(models.User).get(payload.target_id)
    if not src or not tgt:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if src.id == admin.id:
        raise HTTPException(status_code=400, detail="Der eigene Account kann nicht als Quelle zusammengefuehrt werden")

    # Ausfuehrende/anlegende Bezuege auf das Ziel umhaengen
    db.query(models.IssueRecord).filter(models.IssueRecord.issued_by_user_id == src.id) \
        .update({models.IssueRecord.issued_by_user_id: tgt.id})
    db.query(models.IssueRecord).filter(models.IssueRecord.returned_by_user_id == src.id) \
        .update({models.IssueRecord.returned_by_user_id: tgt.id})
    db.query(models.Article).filter(models.Article.created_by_id == src.id) \
        .update({models.Article.created_by_id: tgt.id})

    # Verknuepfte Person / Empfaenger-Verlauf zusammenfuehren
    if src.person_id:
        if tgt.person_id and tgt.person_id != src.person_id:
            db.query(models.IssueRecord).filter(models.IssueRecord.person_id == src.person_id) \
                .update({models.IssueRecord.person_id: tgt.person_id})
            srcp = db.query(models.Person).get(src.person_id)
            if srcp:
                srcp.active = False
        elif not tgt.person_id:
            tgt.person_id = src.person_id  # Ziel uebernimmt die Person
    src.person_id = None

    # Fehlende Zugangsdaten uebernehmen, Rollen vereinigen
    if not tgt.password_hash and src.password_hash:
        tgt.password_hash = src.password_hash
    if not tgt.pin_hash and src.pin_hash:
        tgt.pin_hash = src.pin_hash
        tgt.pin_length = src.pin_length
    tgt.roles = sorted(set(tgt.roles or []) | set(src.roles or []))

    src_name = src.username
    db.delete(src)
    db.commit()
    log_action(db, admin, "merge_users", "user", tgt.id, {"source": src_name, "target": tgt.username})
    return {"ok": True, "message": f"Benutzer '{src_name}' wurde in '{tgt.username}' zusammengefuehrt."}
