import datetime as dt
import socket
import time
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, WebSocket, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app import security
from app.database import get_db, engine
from app.audit import log_action
from app.config import CONTROL_DIR, DATA_DIR
from app.realtime import websocket_endpoint
from app import telegram

router = APIRouter(prefix="/api/v1/system", tags=["system"])


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


@router.websocket("/ws")
async def websocket_route(
    websocket: WebSocket,
    user=Depends(security.get_current_user_ws),
):
    await websocket_endpoint(websocket, user)


# ----- Health Checks per Component -----

def _check_database(db: Session) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        db.execute(text("PRAGMA quick_check"))
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": "healthy", "latency_ms": round(elapsed, 2), "details": "SQLite OK"}
    except Exception as e:
        return {"status": "unhealthy", "latency_ms": round((time.perf_counter() - start) * 1000, 2), "error": str(e)}


def _check_disk_space() -> Dict[str, Any]:
    try:
        stat = os.statvfs(DATA_DIR)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        total_gb = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)
        used_pct = ((total_gb - free_gb) / total_gb) * 100
        status = "healthy" if used_pct < 85 else "warning" if used_pct < 95 else "unhealthy"
        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_percent": round(used_pct, 1),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def _check_telegram() -> Dict[str, Any]:
    try:
        bot = telegram.get_bot()
        if not bot:
            return {"status": "not_configured", "details": "No bot token configured"}
        # Could add a getMe call here if needed
        return {"status": "configured", "details": f"Bot: @{bot.get('username', 'unknown')}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_certificates() -> Dict[str, Any]:
    try:
        cert_path = DATA_DIR / "certs" / "cert.pem"
        key_path = DATA_DIR / "certs" / "key.pem"
        if not cert_path.exists() or not key_path.exists():
            return {"status": "missing", "details": "Certificate files not found"}
        # Check expiry
        import subprocess
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return {"status": "healthy", "details": "Certificates present"}
        return {"status": "warning", "details": "Could not verify certificate"}
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


def _check_memory() -> Dict[str, Any]:
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])  # kB
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0) + mem.get("Buffers", 0) + mem.get("Cached", 0))
        used_pct = ((total - available) / total * 100) if total else 0
        status = "healthy" if used_pct < 80 else "warning" if used_pct < 90 else "unhealthy"
        return {
            "status": status,
            "total_mb": round(total / 1024),
            "available_mb": round(available / 1024),
            "used_percent": round(used_pct, 1),
        }
    except Exception:
        # Rueckfall fuer Nicht-Linux-Systeme. psutil ist bewusst keine
        # Pflicht-Abhaengigkeit (im Container greift immer der /proc-Weg
        # darueber); fehlt es, wird der Speicher schlicht nicht gemeldet.
        try:
            import psutil
        except ImportError:
            return {"status": "unknown", "detail": "Speicherdaten auf diesem System nicht verfuegbar"}
        mem = psutil.virtual_memory()
        status = "healthy" if mem.percent < 80 else "warning" if mem.percent < 90 else "unhealthy"
        return {
            "status": status,
            "total_mb": round(mem.total / (1024**2)),
            "available_mb": round(mem.available / (1024**2)),
            "used_percent": mem.percent,
        }


@router.get("/health/detailed")
def detailed_health(db: Session = Depends(get_db)):
    """Detaillierte Health-Checks pro Komponente."""
    checks = {
        "database": _check_database(db),
        "disk": _check_disk_space(),
        "memory": _check_memory(),
        "telegram": _check_telegram(),
        "certificates": _check_certificates(),
    }
    overall = "healthy" if all(c.get("status") in ("healthy", "configured", "not_configured") for c in checks.values()) else "degraded"
    if any(c.get("status") == "unhealthy" for c in checks.values()):
        overall = "unhealthy"
    return {"overall": overall, "checks": checks, "timestamp": dt.datetime.utcnow().isoformat()}


@router.get("/health/live")
def liveness_probe():
    """Kubernetes-style liveness probe - nur Prozess lebt."""
    return {"status": "alive"}


@router.get("/health/ready")
def readiness_probe(db: Session = Depends(get_db)):
    """Kubernetes-style readiness probe - alle kritischen Komponenten bereit."""
    db_check = _check_database(db)
    if db_check["status"] != "healthy":
        raise HTTPException(status_code=503, detail={"ready": False, "reason": "database_unhealthy"})
    return {"ready": True}
