import shutil
import sqlite3
import zipfile
import datetime as dt
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from . import models
from .logging_config import get_logger

log = get_logger("sicherung")
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
    log.info("Sicherung erstellt: %s (%s, %.1f MB)", filename, kind, size / (1024 * 1024))
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


def verify_backup(zip_path: Path) -> Dict[str, Any]:
    """Prueft ein Backup-Zip auf Vollstaendigkeit und Integritaet.
    Returns:
        Dict mit:
        - ok: bool (gesamt ok?)
        - checks: List[Dict] (Detail-Checks)
        - summary: str
    """
    checks = []
    overall_ok = True

    def add_check(name: str, ok: bool, detail: str = "", severity: str = "error"):
        nonlocal overall_ok
        checks.append({"name": name, "ok": ok, "detail": detail, "severity": severity})
        if not ok and severity == "error":
            overall_ok = False

    # 1. ZIP-Datei existiert und ist lesbar
    if not zip_path.exists():
        add_check("file_exists", False, "Backup-Datei nicht gefunden")
        return {"ok": False, "checks": checks, "summary": "Backup-Datei nicht gefunden"}

    # 2. ZIP ist valide und enthaelt erwartete Struktur
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Test ZIP integrity
            bad_file = zf.testzip()
            if bad_file:
                add_check("zip_integrity", False, f"Defekte Datei im Archiv: {bad_file}")
            else:
                add_check("zip_integrity", True, "ZIP-Archiv ist intakt")

            namelist = zf.namelist()

            # 3. Erwartete Kern-Dateien
            has_db = "inventar.db" in namelist
            add_check("has_database", has_db, "inventar.db im Archiv" if has_db else "inventar.db FEHLT")

            # 4. Bilder-Ordner (optional, aber erwartet)
            has_images = any(n.startswith("images/") for n in namelist)
            add_check("has_images", has_images, f"{sum(1 for n in namelist if n.startswith('images/'))} Bilder" if has_images else "Keine Bilder im Archiv", severity="warning")

            # 5. Branding-Ordner (optional)
            has_branding = any(n.startswith("branding/") for n in namelist)
            add_check("has_branding", has_branding, f"{sum(1 for n in namelist if n.startswith('branding/'))} Branding-Dateien" if has_branding else "Kein Branding im Archiv", severity="warning")

            # 6. Wenn DB da: SQLite-Integritaet & Schema-Check
            if has_db:
                tmp_extract = DATA_DIR / "_verify_tmp"
                tmp_extract.mkdir(exist_ok=True)
                try:
                    zf.extract("inventar.db", tmp_extract)
                    db_file = tmp_extract / "inventar.db"

                    # SQLite kann geoeffnet werden
                    try:
                        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                        cur = conn.cursor()

                        # PRAGMA integrity_check
                        cur.execute("PRAGMA integrity_check")
                        integrity = cur.fetchone()[0]
                        add_check("sqlite_integrity", integrity == "ok", f"SQLite integrity_check: {integrity}")

                        # Wichtige Tabellen vorhanden
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = {row[0] for row in cur.fetchall()}
                        expected_tables = {"articles", "users", "persons", "categories", "article_types", "organizations", "storage_locations", "issue_records", "settings"}
                        missing = expected_tables - tables
                        add_check("schema_tables", len(missing) == 0,
                                f"Fehlende Tabellen: {', '.join(sorted(missing))}" if missing else "Alle Kern-Tabellen vorhanden")

                        # Mindestens ein Admin-User
                        if "users" in tables:
                            cur.execute("SELECT COUNT(*) FROM users WHERE json_extract(roles, '$[0]') = 'admin' OR roles LIKE '%admin%'")
                            admin_count = cur.fetchone()[0]
                            add_check("has_admin_user", admin_count > 0,
                                    f"{admin_count} Admin-User(s) gefunden" if admin_count > 0 else "KEIN Admin-User in der DB!", severity="warning")

                        # Artikel-Count
                        if "articles" in tables:
                            cur.execute("SELECT COUNT(*) FROM articles")
                            art_count = cur.fetchone()[0]
                            add_check("article_count", True, f"{art_count} Artikel in der DB")

                        conn.close()
                    except sqlite3.Error as e:
                        add_check("sqlite_open", False, f"SQLite-Fehler: {e}")

                finally:
                    shutil.rmtree(tmp_extract, ignore_errors=True)

    except zipfile.BadZipFile:
        add_check("zip_valid", False, "Kein gueltiges ZIP-Archiv")
    except Exception as e:
        add_check("unexpected_error", False, f"Unerwarteter Fehler: {e}")

    summary = "Backup OK" if overall_ok else "Backup FEHLERHAFT"
    return {"ok": overall_ok, "checks": checks, "summary": summary}
