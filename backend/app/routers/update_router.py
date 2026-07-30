import re
import json
import time
import datetime as dt
import urllib.request
import urllib.error

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import security, schemas
from ..database import get_db
from ..audit import log_action
from ..config import CONTROL_DIR, GITHUB_REPO, UPDATE_DEV_BRANCH, get_app_version

router = APIRouter(prefix="/api/update", tags=["update"])

_CACHE = {"ts": 0.0, "data": None}
_CACHE_TTL = 600  # 10 Minuten


def _parse_ver(s: str):
    nums = re.findall(r"\d+", (s or "").lstrip("vV"))
    nums = [int(x) for x in nums[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def _gh(path: str):
    """Ruft die GitHub-REST-API fuer das konfigurierte Repo auf (oeffentlich, ohne
    Token). Gibt das geparste JSON zurueck oder None bei Fehler/Timeout."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}{path}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Inventarprogramm-Update",
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None


def _release_brief(r: dict) -> dict:
    body = (r.get("body") or "").strip()
    if len(body) > 800:
        body = body[:800] + "…"
    return {
        "tag": r.get("tag_name"),
        "name": r.get("name") or r.get("tag_name"),
        "prerelease": bool(r.get("prerelease")),
        "published_at": r.get("published_at"),
        "url": r.get("html_url"),
        "body": body,
    }


def _compute_status() -> dict:
    current = get_app_version()
    latest = _gh("/releases/latest")   # neuestes STABILES Release (ohne Prereleases)
    releases = _gh("/releases?per_page=20") or []
    dev = _gh(f"/branches/{UPDATE_DEV_BRANCH}")

    latest_brief = _release_brief(latest) if isinstance(latest, dict) and latest.get("tag_name") else None
    update_available = bool(latest_brief and _parse_ver(latest_brief["tag"]) > _parse_ver(current))

    dev_info = None
    if isinstance(dev, dict) and dev.get("commit"):
        c = dev["commit"]
        commit_date = None
        try:
            commit_date = c["commit"]["author"]["date"]
        except (KeyError, TypeError):
            pass
        dev_info = {
            "branch": UPDATE_DEV_BRANCH,
            "sha": (c.get("sha") or "")[:7],
            "date": commit_date,
            "url": c.get("html_url"),
        }

    return {
        "current": current,
        "repo": GITHUB_REPO,
        "latest": latest_brief,
        "update_available": update_available,
        "releases": [_release_brief(r) for r in releases if isinstance(r, dict)],
        "dev": dev_info,
        "checked_at": dt.datetime.utcnow().isoformat(),
    }


def _status(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] and (now - _CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["data"]
    data = _compute_status()
    _CACHE["data"] = data
    _CACHE["ts"] = now
    return data


@router.get("/status")
def update_status(refresh: bool = False,
                  user=Depends(security.require_capability("software_update"))):
    return _status(force=refresh)


@router.get("/check")
def update_check(user=Depends(security.require_capability("software_update"))):
    """Leichte Abfrage fuer die Glocke: ist ein Update verfuegbar?"""
    s = _status()
    return {
        "update_available": s["update_available"],
        "current": s["current"],
        "latest": s["latest"]["tag"] if s["latest"] else None,
    }


@router.get("/log")
def update_log(user=Depends(security.require_capability("software_update"))):
    """Liefert das Protokoll des letzten Host-Update-Laufs (falls der Update-Dienst
    eingerichtet ist). So ist sichtbar, ob/warum ein Update fehlgeschlagen ist."""
    path = CONTROL_DIR / "update.log"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"exists": False, "log": "", "hint": (
            "Kein Update-Protokoll gefunden. Entweder wurde noch kein Update ausgeloest, "
            "oder der Host-Update-Dienst ist nicht eingerichtet (Verwaltungs-App -> "
            "'Software-Update per Web aktivieren')."
        )}
    return {"exists": True, "log": text[-8000:]}


@router.post("/install")
def update_install(payload: schemas.UpdateInstallRequest, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("software_update"))):
    """Loest die Installation eines Releases (Tag) oder des dev-Branches aus. Das
    eigentliche Update (git checkout + Neubau) fuehrt ein Host-Dienst aus (siehe
    installer/), der die Signaldatei auswertet - der Container selbst hat dazu
    keine Rechte."""
    ref = (payload.ref or "").strip()
    if not ref:
        raise HTTPException(status_code=400, detail="Keine Version angegeben")

    # Nur bekannte Tags oder den dev-Branch zulassen.
    s = _status()
    known_tags = {r["tag"] for r in s["releases"] if r.get("tag")}
    if s["latest"]:
        known_tags.add(s["latest"]["tag"])
    allowed = ref in known_tags or (s["dev"] and ref == s["dev"]["branch"]) or ref == UPDATE_DEV_BRANCH
    if not allowed:
        raise HTTPException(status_code=400, detail="Unbekannte Version/Branch")

    experimental = ref == UPDATE_DEV_BRANCH or (s["dev"] and ref == s["dev"]["branch"])
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    (CONTROL_DIR / "update.request").write_text(ref + "\n", encoding="utf-8")
    log_action(db, user, "software_update", "system", None, {"ref": ref, "experimental": experimental})
    return {"ok": True, "message": (
        f"Update auf '{ref}' wurde ausgeloest. Der Server holt die Version und baut sie neu auf; "
        "das kann einige Minuten dauern, danach ist die Anwendung wieder erreichbar "
        "(sofern der Update-Dienst in der Verwaltungs-App eingerichtet ist)."
    )}
