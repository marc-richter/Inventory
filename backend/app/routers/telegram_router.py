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


class ChatAdd(BaseModel):
    chat_id: str


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
    }


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
    return {"chats": _chats(db)}


@router.delete("/chats/{chat_id}")
def remove_chat(chat_id: str, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin"))):
    current = [c for c in _chats(db) if c != chat_id.strip()]
    set_setting(db, "telegram_chats", ",".join(current))
    log_action(db, user, "telegram_remove_chat", "settings", None, {"chat_id": chat_id})
    return {"chats": current}


@router.post("/test")
def send_test(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    if not telegram.token_of(db):
        raise HTTPException(status_code=400, detail="Kein Bot-Token hinterlegt")
    if not _chats(db):
        raise HTTPException(status_code=400, detail="Kein freigeschalteter Chat vorhanden")
    token = telegram.token_of(db)
    sent = 0
    for c in _chats(db):
        r = telegram.send_message(token, c, "✅ Testnachricht vom Inventarprogramm – die Telegram-Anbindung funktioniert.")
        if r and r.get("ok"):
            sent += 1
    return {"sent": sent, "chats": len(_chats(db))}
