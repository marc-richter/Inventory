from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..settings_helper import get_setting

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/register-info", response_model=schemas.RegisterInfoOut)
def register_info(db: Session = Depends(get_db)):
    """Sagt der Anmeldemaske, ob Selbstregistrierung erlaubt ist und welche Angaben
    verpflichtend sind (vom Administrator in den Einstellungen festgelegt)."""
    return schemas.RegisterInfoOut(
        enabled=get_setting(db, "selfreg_enabled", "true") == "true",
        pin_length=int(get_setting(db, "selfreg_pin_length", "8") or 8),
        require_password=get_setting(db, "selfreg_require_password", "false") == "true",
        require_fullname=get_setting(db, "selfreg_require_fullname", "true") == "true",
    )


@router.post("/register")
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """Selbstregistrierung eines Helfers auf der Anmeldemaske. Vergibt automatisch
    die Rolle mit den geringsten Rechten (Standard 'eigen': sieht nur die an ihn
    ausgegebenen Artikel). Standardmaessig Nutzername + 8-stellige PIN; Passwort ist
    - sofern der Admin es nicht verlangt - optional."""
    if get_setting(db, "selfreg_enabled", "true") != "true":
        raise HTTPException(status_code=403, detail="Selbstregistrierung ist derzeit deaktiviert")

    username = (payload.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Benutzername fehlt")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Benutzername bereits vergeben")

    pin_length = int(get_setting(db, "selfreg_pin_length", "8") or 8)
    require_password = get_setting(db, "selfreg_require_password", "false") == "true"
    require_fullname = get_setting(db, "selfreg_require_fullname", "true") == "true"

    full_name = (payload.full_name or "").strip()
    if require_fullname and not full_name:
        raise HTTPException(status_code=400, detail="Name ist erforderlich")

    pin = (payload.pin or "").strip()
    if pin and (len(pin) != pin_length or not pin.isdigit()):
        raise HTTPException(status_code=400, detail=f"PIN muss genau {pin_length} Ziffern haben")

    password = payload.password or ""
    if require_password and not password:
        raise HTTPException(status_code=400, detail="Passwort ist erforderlich")
    if not pin and not password:
        raise HTTPException(status_code=400, detail="Bitte eine PIN oder ein Passwort festlegen")

    role = get_setting(db, "selfreg_role", "eigen") or "eigen"

    person_id = None
    if full_name:
        parts = full_name.split()
        first = parts[0]
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        person = models.Person(first_name=first, last_name=last, active=True)
        db.add(person)
        db.flush()
        person_id = person.id

    new_user = models.User(
        username=username, full_name=full_name, roles=[role],
        pin_length=pin_length, active=True, person_id=person_id,
    )
    if pin:
        new_user.pin_hash = security.hash_secret(pin)
    if password:
        new_user.password_hash = security.hash_secret(password)
    db.add(new_user)
    db.commit()
    log_action(db, new_user, "self_register", "user", new_user.id, {"username": username})
    return {"ok": True, "username": username}


@router.get("/pin-info", response_model=schemas.PinInfoOut)
def pin_info(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username, models.User.active == True).first()
    if not user:
        # Keine Existenz-Info preisgeben, aber sinnvolle Defaultlaenge liefern
        return schemas.PinInfoOut(pin_length=4, has_password=False, has_pin=False)
    return schemas.PinInfoOut(
        pin_length=user.pin_length,
        has_password=bool(user.password_hash),
        has_pin=bool(user.pin_hash),
    )


@router.post("/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Benutzername oder Zugangsdaten falsch")

    ok = False
    if payload.password is not None and user.password_hash:
        ok = security.verify_secret(payload.password, user.password_hash)
    elif payload.pin is not None and user.pin_hash:
        ok = security.verify_secret(payload.pin, user.pin_hash)

    if not ok:
        raise HTTPException(status_code=401, detail="Benutzername oder Zugangsdaten falsch")

    token = security.create_access_token({"sub": user.username, "roles": user.roles or []})
    log_action(db, user, "login")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": schemas.UserOut(
            id=user.id, username=user.username, full_name=user.full_name,
            roles=user.roles or [], person_id=user.person_id, active=user.active,
            pin_length=user.pin_length,
            has_password=bool(user.password_hash), has_pin=bool(user.pin_hash),
        ),
    }


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(security.get_current_user)):
    return schemas.UserOut(
        id=user.id, username=user.username, full_name=user.full_name,
        roles=user.roles or [], person_id=user.person_id, active=user.active,
        pin_length=user.pin_length,
        has_password=bool(user.password_hash), has_pin=bool(user.pin_hash),
    )


@router.post("/change-pin")
def change_pin(payload: schemas.ChangePinRequest, db: Session = Depends(get_db),
               user: models.User = Depends(security.get_current_user)):
    if len(payload.new_pin) != user.pin_length or not payload.new_pin.isdigit():
        raise HTTPException(status_code=400, detail=f"PIN muss genau {user.pin_length} Ziffern haben")
    if user.pin_hash and not security.verify_secret(payload.old_pin or "", user.pin_hash):
        raise HTTPException(status_code=400, detail="Alte PIN ist falsch")
    user.pin_hash = security.hash_secret(payload.new_pin)
    user.must_change_pin = False
    db.commit()
    log_action(db, user, "change_pin", "user", user.id)
    return {"ok": True}


@router.post("/change-password")
def change_password(payload: schemas.ChangePasswordRequest, db: Session = Depends(get_db),
                     user: models.User = Depends(security.get_current_user)):
    if user.password_hash and not security.verify_secret(payload.old_password or "", user.password_hash):
        raise HTTPException(status_code=400, detail="Altes Passwort ist falsch")
    if len(payload.new_password) < 4:
        raise HTTPException(status_code=400, detail="Passwort zu kurz")
    user.password_hash = security.hash_secret(payload.new_password)
    db.commit()
    log_action(db, user, "change_password", "user", user.id)
    return {"ok": True}
