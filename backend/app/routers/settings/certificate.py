"""Eigenes HTTPS-Zertifikat hinterlegen (nur Administrator)."""

import datetime as dt
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import security, zertifikat
from app.audit import log_action
from app.config import CERTS_DIR, CONTROL_DIR
from app.database import get_db
from app.logging_config import get_logger

router = APIRouter(prefix="/api/v1/settings/certificate", tags=["settings"])
log = get_logger("zertifikat")

ZERT_DATEI = "cert.pem"
SCHLUESSEL_DATEI = "key.pem"
MAX_BYTES = 512 * 1024      # ein Zertifikat ist wenige Kilobyte gross


def _pfad(name: str):
    return CERTS_DIR / name


def _eingebunden() -> bool:
    """Ist der Zertifikatsordner ueberhaupt beschreibbar eingebunden?

    Auf einer Installation, die noch mit der alten docker-compose.yml laeuft,
    sieht das Backend den Ordner nicht - dann soll die Oberflaeche das sagen
    statt einen Fehler zu werfen.
    """
    try:
        CERTS_DIR.mkdir(parents=True, exist_ok=True)
        probe = CERTS_DIR / ".schreibtest"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


@router.get("")
def zertifikat_info(user=Depends(security.require_roles("admin"))):
    """Was liegt gerade als HTTPS-Zertifikat vor?"""
    if not _eingebunden():
        return {"available": False,
                "hint": ("Der Zertifikats-Ordner ist nicht beschreibbar eingebunden. "
                         "Nach einem Update der Programmdateien ist dafür ein Neustart "
                         "über die Verwaltungs-App nötig.")}
    pfad = _pfad(ZERT_DATEI)
    if not pfad.exists():
        return {"available": True, "installed": False,
                "hint": "Es ist noch kein Zertifikat hinterlegt."}
    try:
        daten = zertifikat.pruefen(pfad.read_bytes(), _pfad(SCHLUESSEL_DATEI).read_bytes()
                                   if _pfad(SCHLUESSEL_DATEI).exists() else b"")
    except zertifikat.ZertifikatFehler as exc:
        return {"available": True, "installed": True, "readable": False, "error": str(exc)}
    daten.update({"available": True, "installed": True, "readable": True})
    return daten


@router.post("/pruefen")
async def zertifikat_pruefen(
    cert: UploadFile = File(...),
    key: Optional[UploadFile] = File(None),
    chain: Optional[UploadFile] = File(None),
    user=Depends(security.require_roles("admin")),
):
    """Prueft die hochgeladenen Dateien, ohne etwas zu aendern.

    Damit laesst sich vor dem Umschalten sehen, ob alles zusammenpasst - ein
    unpassendes Zertifikat wuerde den Web-Teil sonst beim Neustart lahmlegen.
    """
    zert_pem, schluessel_pem, kette_pem = await _lesen(cert, key, chain)
    try:
        return {"ok": True, **zertifikat.pruefen(zert_pem, schluessel_pem, kette_pem)}
    except zertifikat.ZertifikatFehler as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("")
async def zertifikat_speichern(
    cert: UploadFile = File(...),
    key: Optional[UploadFile] = File(None),
    chain: Optional[UploadFile] = File(None),
    reload_web: bool = True,
    db: Session = Depends(get_db),
    user=Depends(security.require_roles("admin")),
):
    """Zertifikat uebernehmen und (auf Wunsch) den Web-Teil neu laden.

    Das bisherige Zertifikat wird vorher zur Seite gelegt - laesst sich das neue
    wider Erwarten nicht laden, ist der alte Stand noch da.
    """
    if not _eingebunden():
        raise HTTPException(
            status_code=400,
            detail="Der Zertifikats-Ordner ist nicht beschreibbar eingebunden. Bitte die "
                   "Programmdateien aktualisieren und über die Verwaltungs-App neu starten.")

    zert_pem, schluessel_pem, kette_pem = await _lesen(cert, key, chain)
    try:
        info = zertifikat.pruefen(zert_pem, schluessel_pem, kette_pem)
    except zertifikat.ZertifikatFehler as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Schluessel kann auch in der Zertifikatsdatei stecken - dann von dort nehmen.
    if not schluessel_pem:
        _zerts, schluessel_pem = zertifikat.teile_pem(zert_pem)

    stempel = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in (ZERT_DATEI, SCHLUESSEL_DATEI):
        alt = _pfad(name)
        if alt.exists():
            try:
                shutil.copy2(alt, _pfad(f"{name}.vorher-{stempel}"))
            except OSError as exc:
                log.warning("Sicherung von %s nicht moeglich: %s", name, exc)

    try:
        _pfad(ZERT_DATEI).write_bytes(zertifikat.zusammenbauen(zert_pem, kette_pem))
        _pfad(SCHLUESSEL_DATEI).write_bytes(schluessel_pem)
        # Der private Schluessel geht niemanden sonst etwas an.
        _pfad(SCHLUESSEL_DATEI).chmod(0o600)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Zertifikat konnte nicht gespeichert werden: {exc}")

    log_action(db, user, "certificate_upload", "system", None,
               {"subject": info.get("subject"), "valid_to": info.get("valid_to")})

    neu_geladen = False
    if reload_web:
        neu_geladen = _web_neu_laden()

    return {"ok": True, **info, "reload_requested": neu_geladen,
            "message": ("Zertifikat gespeichert. Der Web-Teil startet in wenigen Sekunden neu – "
                        "die Seite ist dabei kurz nicht erreichbar."
                        if neu_geladen else
                        "Zertifikat gespeichert. Damit es greift, muss der Web-Teil neu gestartet "
                        "werden – in der Verwaltungs-App „Stoppen“ und „Starten“.")}


@router.post("/reload")
def web_neu_laden(db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin"))):
    """Nur den Web-Teil neu starten (z.B. nachdem das Zertifikat getauscht wurde)."""
    ok = _web_neu_laden()
    log_action(db, user, "frontend_reload", "system", None)
    return {"ok": ok,
            "message": ("Neustart des Web-Teils angefordert - die Seite ist gleich kurz "
                        "nicht erreichbar."
                        if ok else
                        "Der Neustart konnte nicht angefordert werden. Bitte in der "
                        "Verwaltungs-App „Stoppen“ und „Starten“ wählen.")}


def _web_neu_laden() -> bool:
    """Legt eine Signaldatei ab, die der Watcher auf dem Rechner auswertet.

    Das Backend kann den Web-Container nicht selbst neu starten - es hat (aus
    gutem Grund) keinen Zugriff auf Docker. Der Watcher der Verwaltungs-App
    erledigt das; ist er nicht eingerichtet, sagt die Antwort das.
    """
    try:
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        (CONTROL_DIR / "frontend-reload.request").write_text(
            dt.datetime.now().isoformat(), encoding="utf-8")
        return True
    except OSError as exc:
        log.warning("Neustart des Web-Teils konnte nicht angefordert werden: %s", exc)
        return False


async def _lesen(cert: UploadFile, key: Optional[UploadFile], chain: Optional[UploadFile]):
    async def inhalt(datei: Optional[UploadFile]) -> bytes:
        if datei is None:
            return b""
        roh = await datei.read()
        if len(roh) > MAX_BYTES:
            raise HTTPException(status_code=400,
                                detail=f"Die Datei {datei.filename} ist zu groß für ein Zertifikat.")
        return roh
    return await inhalt(cert), await inhalt(key), await inhalt(chain)
