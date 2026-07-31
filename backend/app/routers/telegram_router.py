from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import security
from ..database import get_db
from ..audit import log_action
from ..settings_helper import get_setting, set_setting
from .. import telegram

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramConfig(BaseModel):
    enabled: Optional[bool] = None
    bot_token: Optional[str] = None       # nur setzen, wenn mitgegeben (leer = unveraendert)
    notify_events: Optional[List[str]] = None
    self_link_enabled: Optional[bool] = None


class ChatAdd(BaseModel):
    chat_id: str


class TestRequest(BaseModel):
    text: Optional[str] = None       # leer -> Standardtext
    chat_id: Optional[str] = None    # leer -> an alle freigeschalteten Chats


DEFAULT_TEST_TEXT = "✅ Testnachricht vom Inventarprogramm – die Telegram-Anbindung funktioniert."


def _chats(db):
    return telegram.chats(db)


@router.get("/status")
def status(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    token = telegram.token_of(db)
    bot = telegram.get_me(token) if token else None
    return {
        "enabled": telegram.is_enabled(db),
        "has_token": bool(token),
        "bot_username": bot.get("username") if bot else None,
        "token_valid": bool(bot),
        "chats": _chats(db),
        "notify_events": sorted(telegram.events(db)),
        "available_events": telegram.AVAILABLE_EVENTS,
        "self_link_enabled": telegram.self_link_enabled(db),
        "default_test_text": DEFAULT_TEST_TEXT,
        "chat_names": telegram.names_map(db),
        "pending": telegram.pending_list(db),
        "paused": telegram.paused(db),
        "blacklist": telegram.blacklist(db),
        "chat_links": _chat_links(db),
    }


def _chat_links(db):
    """Je freigeschaltetem Chat: verknuepfter Benutzer + ob dessen Konto aktiv ist
    (Telegram-Zugriff ist an das Konto gekoppelt)."""
    from .. import models
    out = {}
    for cid in _chats(db):
        u = db.query(models.User).filter(models.User.telegram_chat_id == cid).first()
        if u:
            out[cid] = {"user": u.full_name or u.username, "active": bool(u.active)}
    return out


@router.post("/config")
def config(payload: TelegramConfig, db: Session = Depends(get_db),
           user=Depends(security.require_roles("admin"))):
    if payload.bot_token is not None and payload.bot_token.strip():
        set_setting(db, "telegram_bot_token", payload.bot_token.strip())
    if payload.enabled is not None:
        set_setting(db, "telegram_enabled", "true" if payload.enabled else "false")
    if payload.notify_events is not None:
        valid = {e["key"] for e in telegram.AVAILABLE_EVENTS}
        vals = ",".join(e for e in payload.notify_events if e in valid)
        set_setting(db, "telegram_notify_events", vals)
    if payload.self_link_enabled is not None:
        set_setting(db, "telegram_self_link_enabled", "true" if payload.self_link_enabled else "false")
    log_action(db, user, "telegram_config", "settings", None)
    return status(db, user)


@router.post("/chats")
def add_chat(payload: ChatAdd, db: Session = Depends(get_db),
             user=Depends(security.require_roles("admin"))):
    cid = (payload.chat_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="Chat-ID fehlt")
    current = _chats(db)
    if cid not in current:
        current.append(cid)
        set_setting(db, "telegram_chats", ",".join(current))
        log_action(db, user, "telegram_add_chat", "settings", None, {"chat_id": cid})
    telegram.remove_pending(db, cid)   # aus der Warteliste nehmen, falls vorhanden
    return {"chats": _chats(db), "pending": telegram.pending_list(db)}


@router.delete("/pending/{chat_id}")
def dismiss_pending(chat_id: str, db: Session = Depends(get_db),
                    user=Depends(security.require_roles("admin"))):
    telegram.remove_pending(db, chat_id)
    return {"pending": telegram.pending_list(db)}


@router.post("/blacklist")
def add_to_blacklist(payload: ChatAdd, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin"))):
    cid = (payload.chat_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="Chat-ID fehlt")
    telegram.add_blacklist(db, cid)
    log_action(db, user, "telegram_blacklist_add", "settings", None, {"chat_id": cid})
    return {"blacklist": telegram.blacklist(db), "pending": telegram.pending_list(db), "chats": _chats(db)}


@router.delete("/blacklist/{chat_id}")
def remove_from_blacklist(chat_id: str, db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin"))):
    telegram.remove_blacklist(db, chat_id)
    return {"blacklist": telegram.blacklist(db)}


class TargetsRequest(BaseModel):
    event_key: str
    all: bool = False
    groups: List[int] = []
    roles: List[str] = []
    users: List[int] = []


@router.get("/targets")
def get_targets(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    from .. import models
    from ..permissions import ALL_ROLES
    groups = [{"id": g.id, "name": g.name}
              for g in db.query(models.UserGroup).order_by(models.UserGroup.name).all()]
    users = [{"id": u.id, "name": (u.full_name or u.username), "linked": bool(u.telegram_chat_id)}
             for u in db.query(models.User).filter(models.User.active == True)  # noqa: E712
             .order_by(models.User.username).all()]
    return {
        "events": telegram.AVAILABLE_EVENTS,
        "targets": telegram.event_targets(db),
        "groups": groups,
        "roles": ALL_ROLES,
        "users": users,
    }


@router.post("/targets")
def set_targets(payload: TargetsRequest, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin"))):
    valid = {e["key"] for e in telegram.AVAILABLE_EVENTS}
    if payload.event_key not in valid:
        raise HTTPException(status_code=400, detail="Unbekanntes Ereignis")
    cfg = {"all": bool(payload.all), "groups": payload.groups, "roles": payload.roles, "users": payload.users}
    telegram.set_event_targets(db, payload.event_key, cfg)
    log_action(db, user, "telegram_set_targets", "settings", None, {"event": payload.event_key})
    return {"targets": telegram.event_targets(db)}


class PauseRequest(BaseModel):
    paused: bool = True


@router.post("/chats/{chat_id}/pause")
def pause_chat(chat_id: str, payload: PauseRequest, db: Session = Depends(get_db),
               user=Depends(security.require_roles("admin"))):
    telegram.set_paused(db, chat_id, bool(payload.paused))
    log_action(db, user, "telegram_pause_chat", "settings", None, {"chat_id": chat_id, "paused": payload.paused})
    return {"paused": telegram.paused(db)}


@router.delete("/chats/{chat_id}")
def remove_chat(chat_id: str, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin"))):
    current = [c for c in _chats(db) if c != chat_id.strip()]
    set_setting(db, "telegram_chats", ",".join(current))
    log_action(db, user, "telegram_remove_chat", "settings", None, {"chat_id": chat_id})
    return {"chats": current}


# --------------------------- Selbstverknuepfung (persoenlich) ---------------

@router.get("/link/status")
def link_status(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Verknuepfungsstatus des angemeldeten Nutzers + ob die Selbstverknuepfung
    freigegeben ist und wie der Bot heisst (fuer die Anleitung)."""
    token = telegram.token_of(db)
    bot = telegram.get_me(token) if token else None
    return {
        "self_link_enabled": telegram.self_link_enabled(db),
        "linked": bool(user.telegram_chat_id),
        "chat_id": user.telegram_chat_id,
        "bot_username": bot.get("username") if bot else None,
        "pending_code": user.telegram_link_code or None,
    }


@router.post("/link/start")
def link_start(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Erzeugt einen Verknuepfungscode fuer den angemeldeten Nutzer."""
    import secrets
    if not telegram.self_link_enabled(db):
        raise HTTPException(status_code=403, detail="Selbstverknüpfung ist nicht freigegeben")
    code = secrets.token_hex(3).upper()   # 6 Zeichen
    user.telegram_link_code = code
    db.commit()
    token = telegram.token_of(db)
    bot = telegram.get_me(token) if token else None
    return {"code": code, "bot_username": bot.get("username") if bot else None}


@router.post("/link/remove")
def link_remove(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    user.telegram_chat_id = None
    user.telegram_link_code = None
    db.commit()
    return {"linked": False}


@router.post("/test")
def send_test(payload: TestRequest = TestRequest(), db: Session = Depends(get_db),
              user=Depends(security.require_roles("admin"))):
    token = telegram.token_of(db)
    if not token:
        raise HTTPException(status_code=400, detail="Kein Bot-Token hinterlegt")
    if payload and payload.chat_id and payload.chat_id.strip():
        targets = [payload.chat_id.strip()]
    else:
        targets = _chats(db)
    if not targets:
        raise HTTPException(status_code=400, detail="Kein freigeschalteter Chat vorhanden")
    text = ((payload.text if payload else "") or "").strip() or DEFAULT_TEST_TEXT
    sent = 0
    for c in targets:
        r = telegram.send_message(token, c, text)
        if r and r.get("ok"):
            sent += 1
    return {"sent": sent, "chats": len(targets)}
