from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..settings_helper import (
    get_all_settings, set_setting, get_setting, pending_personalization,
)
from ..config import BRANDING_DIR

router = APIRouter(prefix="/api/settings", tags=["settings"])

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
LOGO_EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg", "image/webp": ".webp"}


@router.get("")
def read_settings(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    return get_all_settings(db)


@router.get("/public")
def public_settings(db: Session = Depends(get_db)):
    """Oeffentlich lesbare Anzeige-Einstellungen (ohne Auth), damit z.B. der
    Organisationsname bereits im Anmeldebildschirm angezeigt werden kann."""
    try:
        idle = int(get_setting(db, "session_idle_timeout_minutes", "0") or "0")
    except (ValueError, TypeError):
        idle = 0
    return {
        "org_name": get_setting(db, "org_name", ""),
        "session_idle_timeout_minutes": idle,
    }


@router.get("/personalization/pending")
def personalization_pending(db: Session = Depends(get_db),
                            user=Depends(security.require_roles("admin"))):
    """Liefert die noch nicht hinterlegten Personalisierungs-Einstellungen
    (z.B. Organisationsname, Logo). Das Frontend erinnert den Administrator nach
    dem Login so lange per Popup, bis diese Liste leer ist."""
    return {"pending": pending_personalization(db)}


@router.get("/roles")
def get_role_permissions_endpoint(db: Session = Depends(get_db),
                                  user=Depends(security.require_roles("admin"))):
    """Liefert die verfuegbaren Faehigkeiten, Rollen und die aktuelle
    Rechte-Zuordnung (in den Einstellungen konfigurierbar)."""
    from ..permissions import CAPABILITIES, ALL_ROLES, get_role_permissions
    return {"capabilities": CAPABILITIES, "roles": ALL_ROLES, "permissions": get_role_permissions(db)}


@router.put("/roles")
def set_role_permissions_endpoint(payload: schemas.RolePermissionsUpdate, db: Session = Depends(get_db),
                                  user=Depends(security.require_roles("admin"))):
    import json
    from ..permissions import get_role_permissions, CAP_KEYS, ALL_ROLES
    clean = {r: [c for c in (payload.permissions.get(r, []) or []) if c in CAP_KEYS] for r in ALL_ROLES}
    set_setting(db, "role_permissions", json.dumps(clean))
    log_action(db, user, "update_role_permissions", "settings", None, clean)
    return get_role_permissions(db)


@router.put("")
def update_settings(payload: schemas.SettingsUpdate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin"))):
    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        set_setting(db, k, str(v))
    log_action(db, user, "update_settings", "settings", None, data)
    return get_all_settings(db)


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db),
                       user=Depends(security.require_roles("admin"))):
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="Nur PNG, JPEG, WEBP oder SVG erlaubt")
    ext = LOGO_EXT_BY_TYPE[file.content_type]

    # Alte Logo-Datei entfernen, falls eine mit anderer Endung existiert
    old_name = get_setting(db, "logo_filename", "")
    if old_name:
        old_path = BRANDING_DIR / old_name
        if old_path.exists():
            old_path.unlink()

    filename = f"logo{ext}"
    dest = BRANDING_DIR / filename
    content = await file.read()
    dest.write_bytes(content)

    set_setting(db, "logo_filename", filename)
    log_action(db, user, "upload_logo", "settings", None, {"filename": filename})
    return {"ok": True, "filename": filename}


@router.get("/logo")
def get_logo(db: Session = Depends(get_db)):
    # Bewusst ohne Auth-Pruefung, damit das Logo im Login-Screen (vor dem
    # Einloggen) angezeigt werden kann.
    name = get_setting(db, "logo_filename", "")
    if not name:
        raise HTTPException(status_code=404, detail="Kein Logo hinterlegt")
    path = BRANDING_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo-Datei nicht gefunden")
    return FileResponse(path)


@router.delete("/logo")
def delete_logo(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    name = get_setting(db, "logo_filename", "")
    if name:
        path = BRANDING_DIR / name
        if path.exists():
            path.unlink()
    set_setting(db, "logo_filename", "")
    log_action(db, user, "delete_logo", "settings", None)
    return {"ok": True}


def _entity_label(db: Session, entity_type: str, entity_id) -> str:
    """Menschenlesbare Bezeichnung fuer ein Protokoll-Objekt (statt 'user #1'):
    Artikel -> Inventarnummer, Benutzer -> Benutzername, Person -> Name."""
    if not entity_id:
        return ""
    if entity_type == "article":
        a = db.query(models.Article).get(entity_id)
        return a.artikelnummer if a else f"#{entity_id}"
    if entity_type == "user":
        u = db.query(models.User).get(entity_id)
        return u.username if u else f"#{entity_id}"
    if entity_type == "person":
        p = db.query(models.Person).get(entity_id)
        return f"{p.first_name} {p.last_name}" if p else f"#{entity_id}"
    return f"#{entity_id}"


@router.get("/audit-log")
def audit_log(limit: int = 200, db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    rows = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {"id": r.id, "username": r.username, "action": r.action, "entity_type": r.entity_type,
         "entity_id": r.entity_id, "entity_label": _entity_label(db, r.entity_type, r.entity_id),
         "details": r.details, "timestamp": r.timestamp.isoformat()}
        for r in rows
    ]
