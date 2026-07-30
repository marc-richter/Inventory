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
    # Format des maschinenlesbaren Codes der Inventarnummer auf dem Etikett:
    # "qr" (QR-Code, Standard), "code128" oder "code39" (Strichcodes).
    "label_code_format": "qr",
    # Welche Felder in welcher Reihenfolge als Text auf das Etikett gedruckt werden
    # (kommagetrennt). Moeglich: artikelnummer,type,model,size,organization,
    # storage_location,current_location,properties.
    "label_fields": "artikelnummer,type,size,model",
    # Maximale Zeichenzahl je Etikettfeld (JSON). Begrenzt NUR den Aufdruck aufs
    # Etikett, nicht die Feldlaenge im Artikel selbst.
    "label_maxlen": '{"artikelnummer":24,"type":28,"size":24,"model":10,"organization":24,"storage_location":24,"current_location":24,"properties":24}',
    # Freitext, der aufs Etikett gedruckt werden kann (wenn Feld "freetext" gewaehlt ist)
    "label_free_text": "",
    "org_name": "",
    "logo_filename": "",
    "printer_connection_type": "none",   # "none" | "network" | "usb"
    "printer_ip": "",
    "printer_model": "",
    # Netzwerk-Druckprotokoll: "pdf" (Rohes PDF an Port 9100 - fuer Drucker mit
    # PDF/AirPrint-Direktdruck) oder "ptouch" (natives Brother-P-touch-Raster fuer
    # PT-E550W/P750W/P710BT). Weitere P-touch-Parameter:
    "printer_protocol": "pdf",
    "ptouch_tape_mm": "24",
    "ptouch_length_mm": "40",
    "ptouch_cut": "true",
    "ptouch_rotate180": "false",
    "ptouch_mirror": "false",
    # Selbstregistrierung von Helfern auf der Anmeldemaske
    "selfreg_enabled": "true",
    "selfreg_pin_length": "8",           # Standard: 8-stellige PIN
    "selfreg_require_password": "false", # Passwort standardmaessig NICHT verpflichtend
    "selfreg_require_fullname": "true",  # Name wird fuer "Meine Artikel" benoetigt
    "selfreg_role": "lesend",            # zugewiesene Rolle fuer selbst/automatisch angelegte Nutzer
    # Bei Selbstregistrierung mit exakter Vor-/Nachname-Uebereinstimmung ein
    # bestehendes, per Ausgabe erzeugtes (passwortloses) Konto uebernehmen, damit
    # frueher ausgegebene Gueter sofort sichtbar sind. Abschaltbar.
    "selfreg_match_existing": "true",
    # Konfigurierbare Rollen-Rechte (JSON: {rolle: [capabilities]}); leer = Defaults
    "role_permissions": "",
    # Inventur: laufende Kampagne (ISO-Zeitpunkt, leer = keine) und die Status, die
    # bei der Fehlliste ignoriert werden (kommagetrennte Status-Werte). Diese Teile
    # sind physisch nicht am Lagerplatz (ausgegeben, in Reparatur, ausgemustert).
    "inventory_started_at": "",
    "inventory_ignore_status": "ausgegeben,reparatur,ausgemustert",
    # Telegram-Anbindung: Bot-Token, freigeschaltete Chats (kommagetrennt), ob
    # aktiv, welche Ereignisse ausgehend gemeldet werden, sowie der interne
    # getUpdates-Offset des Bots.
    "telegram_enabled": "false",
    "telegram_bot_token": "",
    "telegram_chats": "",
    "telegram_notify_events": "provisional,inventory",
    "telegram_offset": "0",
    # Duerfen Nutzer ihr Telegram-Konto selbst verknuepfen (in ihren Kontoeinstellungen)?
    "telegram_self_link_enabled": "false",
    # Automatischer Logout nach Inaktivitaet in Minuten (0 = deaktiviert).
    "session_idle_timeout_minutes": "0",
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
