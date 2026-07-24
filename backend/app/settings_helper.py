from sqlalchemy.orm import Session
from . import models

DEFAULTS = {
    "pin_length_default": "4",
    "backup_dir": "/app/data/backups",
    "backup_auto_enabled": "false",
    "backup_auto_time": "02:00",   # HH:MM taeglich
    "backup_retention": "30",       # Anzahl Backups die behalten werden
    "label_width_mm": "62",
    "label_height_mm": "29",
    "org_name": "",
    "logo_filename": "",
    "printer_connection_type": "none",   # "none" | "network" | "usb"
    "printer_ip": "",
    "printer_model": "",
    # Selbstregistrierung von Helfern auf der Anmeldemaske
    "selfreg_enabled": "true",
    "selfreg_pin_length": "8",           # Standard: 8-stellige PIN
    "selfreg_require_password": "false", # Passwort standardmaessig NICHT verpflichtend
    "selfreg_require_fullname": "true",  # Name wird fuer "Meine Artikel" benoetigt
    "selfreg_role": "lesend",            # zugewiesene Rolle fuer selbst/automatisch angelegte Nutzer
    # Konfigurierbare Rollen-Rechte (JSON: {rolle: [capabilities]}); leer = Defaults
    "role_permissions": "",
}

# Personalisierungs-Einstellungen. Diese werden bei der Erstinstallation abgefragt
# und - solange sie nicht gesetzt sind - dem Administrator nach dem Login per Popup
# in Erinnerung gerufen (siehe /api/settings/personalization/pending), bis sie
# hinterlegt sind. Kommt bei einem Update ein neuer Eintrag hinzu, ist er auf
# bestehenden Installationen automatisch leer und wird dadurch als "ausstehend"
# erkannt und beim naechsten Admin-Login abgefragt.
#
# required=True  -> Pflichtangabe (z.B. Organisationsname)
# required=False -> empfohlen (z.B. Logo); wird ebenfalls erinnert, ist aber optional
PERSONALIZATION_SETTINGS = [
    {
        "key": "org_name",
        "label": "Organisationsname",
        "required": True,
        "hint": "Erscheint im Anmeldebildschirm und in der Kopfzeile der Anwendung.",
    },
    {
        "key": "logo_filename",
        "label": "Logo",
        "required": False,
        "hint": "Eigenes Logo - erscheint im Anmeldebildschirm und in der Kopfzeile.",
    },
]


def pending_personalization(db: Session) -> list:
    """Liefert die Personalisierungs-Einstellungen, die noch nicht hinterlegt sind
    (leerer Wert). Wird verwendet, um den Administrator nach dem Login so lange
    per Popup zu erinnern, bis alle Werte gesetzt sind."""
    pending = []
    for item in PERSONALIZATION_SETTINGS:
        value = get_setting(db, item["key"], "")
        if not value or not str(value).strip():
            pending.append({
                "key": item["key"],
                "label": item["label"],
                "required": item["required"],
                "hint": item["hint"],
            })
    return pending


def get_setting(db: Session, key: str, default: str = None) -> str:
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    if row:
        return row.value
    return DEFAULTS.get(key, default)


def set_setting(db: Session, key: str, value: str):
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    if row:
        row.value = value
    else:
        row = models.Setting(key=key, value=value)
        db.add(row)
    db.commit()


def get_all_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    for row in db.query(models.Setting).all():
        result[row.key] = row.value
    return result


def ensure_defaults(db: Session):
    for k, v in DEFAULTS.items():
        if not db.query(models.Setting).filter(models.Setting.key == k).first():
            db.add(models.Setting(key=k, value=v))
    db.commit()
