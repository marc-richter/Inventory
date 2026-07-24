import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import security
from ..database import get_db
from ..audit import log_action
from ..config import CONTROL_DIR

router = APIRouter(prefix="/api/system", tags=["system"])


def _write_signal(name: str):
    """Legt eine Signaldatei im (host-gemounteten) Steuer-Verzeichnis ab. Ein
    host-seitiger Watcher (systemd-Path-Unit, siehe installer/) fuehrt daraufhin
    das eigentliche Herunterfahren/Neustarten aus."""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / name).write_text(dt.datetime.utcnow().isoformat() + "\n", encoding="utf-8")


@router.post("/shutdown")
def shutdown(db: Session = Depends(get_db),
             user=Depends(security.require_capability("server_power"))):
    _write_signal("shutdown.request")
    log_action(db, user, "server_shutdown", "system", None)
    return {"ok": True, "message": (
        "Herunterfahren wurde ausgeloest. Der Server schaltet sich in Kuerze aus "
        "(sofern der Host-Watcher eingerichtet ist - siehe Verwaltungs-App, Punkt "
        "'Server-Aus/Neustart per Web')."
    )}


@router.post("/reboot")
def reboot(db: Session = Depends(get_db),
           user=Depends(security.require_capability("server_power"))):
    _write_signal("reboot.request")
    log_action(db, user, "server_reboot", "system", None)
    return {"ok": True, "message": (
        "Neustart wurde ausgeloest. Der Server startet in Kuerze neu (sofern der "
        "Host-Watcher eingerichtet ist)."
    )}
