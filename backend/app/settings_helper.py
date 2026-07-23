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
    "org_name": "Meine Organisation",
    "logo_filename": "",
    "printer_connection_type": "none",   # "none" | "network" | "usb"
    "printer_ip": "",
    "printer_model": "",
}


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
