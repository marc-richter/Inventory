"""Hilfsfunktionen fuer die Einheit von Person und Benutzer.

Personen und Benutzer sind dasselbe: Beim Anlegen einer Person (in beliebigem
Menue/Aktion, z.B. bei der Ausgabe) wird automatisch ein Benutzerkonto mit der
Standardrolle (Standard: "lesend") und einem automatisch erzeugten Benutzernamen
angelegt.
"""
import re
from sqlalchemy.orm import Session

from . import models


def slug_username(first: str, last: str) -> str:
    base = f"{(first or '').strip()}.{(last or '').strip()}".strip(".").lower()
    base = base.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    base = re.sub(r"[^a-z0-9.]+", "", base).strip(".")
    return base or "nutzer"


def unique_username(db: Session, first: str, last: str) -> str:
    base = slug_username(first, last)
    candidate = base
    n = 1
    while db.query(models.User).filter(models.User.username == candidate).first():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def ensure_user_for_person(db: Session, person, role: str = None, pin: str = None,
                           password: str = None, pin_length: int = None):
    """Legt - falls noch nicht vorhanden - ein Benutzerkonto zu einer Person an
    (automatischer Benutzername, Standardrolle). Gibt den (ggf. bestehenden)
    Benutzer zurueck."""
    from . import security
    from .settings_helper import get_setting

    existing = db.query(models.User).filter(models.User.person_id == person.id).first()
    if existing:
        return existing

    role = role or (get_setting(db, "selfreg_role", "lesend") or "lesend")
    pl = pin_length or int(get_setting(db, "selfreg_pin_length", "8") or 8)
    username = unique_username(db, person.first_name, person.last_name)
    u = models.User(
        username=username,
        full_name=f"{person.first_name} {person.last_name}".strip(),
        roles=[role], pin_length=pl, active=True, person_id=person.id,
    )
    if pin:
        u.pin_hash = security.hash_secret(pin)
    if password:
        u.password_hash = security.hash_secret(password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
