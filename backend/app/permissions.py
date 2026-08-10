"""Konfigurierbare Rollen-Rechte (Capabilities).

Statt fest verdrahteter Rollenpruefungen wird pro Rolle eine Menge von
Faehigkeiten (Capabilities) hinterlegt, die der Administrator in den
Einstellungen anpassen kann. Die Standardwerte spiegeln die gewuenschte
Rollen-Definition wider:
  - admin:      alles
  - verwalter (Materialverwalter): Artikel anlegen/bearbeiten/aussondern,
                aus-/zurueckgeben, Export/Import
  - helfer:     nur lesend
  - lesend:     nur lesend
  - eigen:      nur eigene Artikel (Sonderfall, im Artikel-Router erzwungen)
"""
import json
from sqlalchemy.orm import Session

from .settings_helper import get_setting

# Verfuegbare Faehigkeiten (Reihenfolge = Anzeige-Reihenfolge)
CAPABILITIES = [
    {"key": "articles", "label": "Artikel anlegen / bearbeiten / aussondern"},
    {"key": "issues", "label": "Ausgeben / Zurücknehmen"},
    {"key": "requests", "label": "Materialanfragen stellen"},
    {"key": "report_damage", "label": "Schaden / Verlust melden"},
    {"key": "persons", "label": "Personen / Benutzer verwalten"},
    {"key": "users", "label": "Benutzerkonten & Rollen verwalten"},
    {"key": "settings", "label": "Einstellungen / Stammdaten / Status"},
    {"key": "export", "label": "Export / Import"},
    {"key": "inventory", "label": "Inventuren planen & leiten"},
    {"key": "server_power", "label": "Server herunterfahren / neu starten"},
    {"key": "software_update", "label": "Software-Updates prüfen / installieren"},
]
CAP_KEYS = [c["key"] for c in CAPABILITIES]

ALL_ROLES = ["admin", "verwalter", "helfer", "lesend", "eigen"]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": list(CAP_KEYS),
    "verwalter": ["articles", "issues", "requests", "report_damage", "export", "inventory"],
    "helfer": ["requests", "report_damage"],
    "lesend": ["requests", "report_damage"],
    "eigen": ["requests", "report_damage"],
}


def get_role_permissions(db: Session) -> dict:
    raw = get_setting(db, "role_permissions", "")
    result = {r: list(DEFAULT_ROLE_PERMISSIONS.get(r, [])) for r in ALL_ROLES}
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for r in ALL_ROLES:
                    if r in data and isinstance(data[r], list):
                        result[r] = [c for c in data[r] if c in CAP_KEYS]
        except (ValueError, TypeError):
            pass
    return result


def user_capabilities(db: Session, user) -> set:
    perms = get_role_permissions(db)
    roles = user.roles or []
    caps = set()
    for r in roles:
        caps |= set(perms.get(r, []))
    if "admin" in roles:
        caps |= set(CAP_KEYS)  # Administrator hat implizit alle Rechte
    # Persoenlich entzogene Rechte abziehen (unabhaengig von der Rolle).
    revoked = set(getattr(user, "revoked_capabilities", None) or [])
    return caps - revoked
