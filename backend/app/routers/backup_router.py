import os
import threading
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, security
from ..database import get_db
from ..audit import log_action
from ..backup import create_backup, restore_backup, _backup_dir
from ..config import DATA_DIR

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _schedule_restart(delay: float = 1.5):
    """Beendet den Prozess kurz verzoegert; der Container startet dank
    'restart: unless-stopped' automatisch neu und laedt die wiederhergestellte
    Datenbank sauber."""
    threading.Timer(delay, lambda: os._exit(0)).start()


@router.get("")
def list_backups(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    records = db.query(models.BackupRecord).order_by(models.BackupRecord.created_at.desc()).all()
    return [
        {"id": r.id, "filename": r.filename, "kind": r.kind, "size_bytes": r.size_bytes,
         "created_at": r.created_at.isoformat()}
        for r in records
    ]


@router.post("/run")
def run_backup(db: Session = Depends(get_db), user=Depends(security.require_roles("admin", "verwalter"))):
    record = create_backup(db, kind="manual")
    log_action(db, user, "manual_backup", "backup", record.id, {"filename": record.filename})
    return {"ok": True, "filename": record.filename}


@router.get("/{backup_id}/download")
def download_backup(backup_id: int, db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    rec = db.query(models.BackupRecord).get(backup_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")
    path = _backup_dir(db) / rec.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup-Datei nicht auf Datentraeger gefunden")
    return FileResponse(path, filename=rec.filename, media_type="application/zip")


@router.get("/export")
def export_backup(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    """Erzeugt ein frisches Komplett-Backup (ALLE Daten: Artikel, Personen/Benutzer,
    Einstellungen, Organisationsname, Status, Verlauf, Bilder und Logo) und gibt es
    direkt als Download zurueck."""
    record = create_backup(db, kind="manual")
    log_action(db, user, "export_full_backup", "backup", record.id, {"filename": record.filename})
    path = _backup_dir(db) / record.filename
    return FileResponse(path, filename=record.filename, media_type="application/zip")


@router.post("/restore")
async def upload_and_restore(file: UploadFile = File(...), db: Session = Depends(get_db),
                              user=Depends(security.require_roles("admin"))):
    tmp_path = DATA_DIR / f"_upload_restore_{file.filename}"
    content = await file.read()
    tmp_path.write_bytes(content)
    try:
        restore_backup(db, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    log_action(db, user, "restore_backup", "backup", None, {"file": file.filename})
    # Anwendung automatisch neu starten, damit die wiederhergestellte DB sauber laedt
    _schedule_restart()
    return {"ok": True, "message": "Komplett-Backup wiederhergestellt. Die Anwendung wird jetzt automatisch neu gestartet - bitte die Seite in ein paar Sekunden neu laden."}
