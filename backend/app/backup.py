import shutil
import sqlite3
import zipfile
import datetime as dt
from pathlib import Path
from sqlalchemy.orm import Session

from . import models
from .config import DATA_DIR, DB_PATH, IMAGES_DIR, BRANDING_DIR
from .settings_helper import get_setting


def _backup_dir(db: Session) -> Path:
    path = Path(get_setting(db, "backup_dir", str(DATA_DIR / "backups")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(db: Session, kind: str = "manual") -> models.BackupRecord:
    backup_dir = _backup_dir(db)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"inventar_backup_{timestamp}.zip"
    dest_zip = backup_dir / filename

    # Konsistente SQLite-Kopie ueber die Backup-API (funktioniert auch bei laufendem Betrieb)
    tmp_db = backup_dir / f"_tmp_{timestamp}.db"
    src_conn = sqlite3.connect(str(DB_PATH))
    dst_conn = sqlite3.connect(str(tmp_db))
    with dst_conn:
        src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    # Komplett-Backup: Datenbank (enthaelt ALLE Daten - Artikel, Personen/Benutzer,
    # Einstellungen, Organisationsname, Status, Verlauf), Bilder und Logo/Branding.
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_db, arcname="inventar.db")
        if IMAGES_DIR.exists():
            for img in IMAGES_DIR.glob("*"):
                if img.is_file():
                    zf.write(img, arcname=f"images/{img.name}")
        if BRANDING_DIR.exists():
            for f in BRANDING_DIR.glob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"branding/{f.name}")
    tmp_db.unlink(missing_ok=True)

    size = dest_zip.stat().st_size
    record = models.BackupRecord(filename=filename, kind=kind, size_bytes=size)
    db.add(record)
    db.commit()
    db.refresh(record)

    _apply_retention(db, backup_dir)
    return record


def _apply_retention(db: Session, backup_dir: Path):
    try:
        retention = int(get_setting(db, "backup_retention", "30"))
    except ValueError:
        retention = 30
    records = db.query(models.BackupRecord).order_by(models.BackupRecord.created_at.desc()).all()
    if len(records) <= retention:
        return
    for rec in records[retention:]:
        f = backup_dir / rec.filename
        if f.exists():
            f.unlink()
        db.delete(rec)
    db.commit()


def restore_backup(db: Session, zip_path: Path):
    """Stellt DB und Bilder aus einem Backup-Zip wieder her. Server-Neustart danach empfohlen."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        tmp_extract = DATA_DIR / "_restore_tmp"
        tmp_extract.mkdir(exist_ok=True)
        zf.extractall(tmp_extract)
        restored_db = tmp_extract / "inventar.db"
        if restored_db.exists():
            shutil.copy(restored_db, DB_PATH)
        restored_images = tmp_extract / "images"
        if restored_images.exists():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            for img in restored_images.glob("*"):
                shutil.copy(img, IMAGES_DIR / img.name)
        restored_branding = tmp_extract / "branding"
        if restored_branding.exists():
            BRANDING_DIR.mkdir(parents=True, exist_ok=True)
            for f in restored_branding.glob("*"):
                shutil.copy(f, BRANDING_DIR / f.name)
        shutil.rmtree(tmp_extract, ignore_errors=True)
