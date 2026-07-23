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
    u = models.User(
        username=payload.username,
        full_name=payload.full_name,
        roles=payload.roles or ["helfer"],
        person_id=payload.person_id,
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
    u.active = False
    db.commit()
    log_action(db, admin, "deactivate_user", "user", u.id)
    return {"ok": True}
