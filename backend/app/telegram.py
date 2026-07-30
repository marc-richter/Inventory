"""Telegram-Anbindung: ausgehende Benachrichtigungen und ein interaktiver Bot
(nur lesende Abfragen). Bewusst ohne Zusatzbibliothek - reine urllib-Aufrufe der
Telegram-Bot-API. Der interaktive Teil laeuft als Long-Polling-Hintergrundthread.

Einrichtung (Telegram-Seite): Der Administrator legt in Telegram per @BotFather
einen Bot an, kopiert den Token in die Einstellungen und aktiviert die Anbindung.
Danach schreibt er dem Bot eine Nachricht; der Bot antwortet mit der Chat-ID, die
der Administrator dann freischaltet.
"""
import json
import time
import threading
import urllib.request
import urllib.parse
from collections import Counter

from sqlalchemy import or_

from . import models
from .database import SessionLocal
from .settings_helper import get_setting, set_setting

_API = "https://api.telegram.org/bot{token}/{method}"

# Welche Ereignisse ausgehend gemeldet werden koennen (fuer die Oberflaeche).
AVAILABLE_EVENTS = [
    {"key": "provisional", "label": "Neue vorläufige Artikel"},
    {"key": "inventory", "label": "Inventur gestartet / abgeschlossen"},
]


# --------------------------- Low-Level-API ----------------------------------

def _call(token, method, params=None, timeout=35):
    if not token:
        return None
    url = _API.format(token=token, method=method)
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_me(token):
    r = _call(token, "getMe", {}, timeout=10)
    return r["result"] if r and r.get("ok") else None


def send_message(token, chat_id, text):
    return _call(token, "sendMessage",
                 {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"},
                 timeout=15)


def get_updates(token, offset, timeout=30):
    return _call(token, "getUpdates", {"offset": offset, "timeout": timeout}, timeout=timeout + 10)


# --------------------------- Konfiguration ----------------------------------

def is_enabled(db):
    return (get_setting(db, "telegram_enabled", "false") or "").lower() == "true"


def token_of(db):
    return (get_setting(db, "telegram_bot_token", "") or "").strip()


def chats(db):
    return [c.strip() for c in (get_setting(db, "telegram_chats", "") or "").split(",") if c.strip()]


def events(db):
    raw = get_setting(db, "telegram_notify_events", "provisional,inventory")
    return {e.strip() for e in (raw or "").split(",") if e.strip()}


# --------------------------- Senden -----------------------------------------

def broadcast(db, text):
    if not is_enabled(db):
        return 0
    token = token_of(db)
    if not token:
        return 0
    n = 0
    for c in chats(db):
        r = send_message(token, c, text)
        if r and r.get("ok"):
            n += 1
    return n


def notify_event(db, event_key, text):
    """Nicht-blockierend eine Ereignis-Benachrichtigung verschicken (in eigenem
    Thread mit eigener DB-Session). Loest nie eine Ausnahme im Aufrufer aus."""
    try:
        if not is_enabled(db) or event_key not in events(db):
            return
    except Exception:
        return

    def worker():
        s = SessionLocal()
        try:
            broadcast(s, text)
        except Exception:
            pass
        finally:
            s.close()

    threading.Thread(target=worker, daemon=True).start()


# --------------------------- Abfragen (nur lesend) --------------------------

HELP = (
    "Inventar-Bot – nur Abfragen, keine Änderungen.\n\n"
    "/artikel <Nummer> – Details zu einem Artikel\n"
    "/wer <Nummer> – wer hat den Artikel gerade\n"
    "/bestand <Typ> [Größe] – verfügbarer Bestand + Lagerorte\n"
    "/suche <Text> – Artikel suchen\n"
    "/offen – aktuell ausgegebene Artikel\n"
    "/helfer <Name> – was hat diese Person gerade\n\n"
    "Beispiele: „/bestand tshirt s“, „/wer 2026-00042“, „/helfer Mustermann“"
)


def _holder(article):
    for iss in article.issues:
        if not iss.return_date:
            if iss.person:
                return f"{iss.person.first_name} {iss.person.last_name}".strip()
            return iss.recipient_name_freetext or "unbekannt"
    return None


def q_artikel(db, nr):
    a = db.query(models.Article).filter(models.Article.artikelnummer == nr.strip()).first()
    if not a:
        return f"Kein Artikel mit Nummer {nr}."
    h = _holder(a)
    return "\n".join([
        f"{a.artikelnummer}",
        f"Typ: {a.type.name if a.type else '-'}",
        f"Größe: {a.size or '-'}",
        f"Modell: {a.model or '-'}",
        f"Status: {a.status}",
        f"Lagerort: {a.location_path or '-'}",
        f"Aktuell bei: {h or 'im Lager'}",
    ])


def q_wer(db, nr):
    a = db.query(models.Article).filter(models.Article.artikelnummer == nr.strip()).first()
    if not a:
        return f"Kein Artikel mit Nummer {nr}."
    h = _holder(a)
    if h:
        return f"{a.artikelnummer} ist ausgegeben an: {h}."
    return f"{a.artikelnummer} ist im Lager (Status: {a.status}, Lagerort: {a.location_path or '-'})."


def q_bestand(db, typ, size):
    base = db.query(models.Article).join(models.ArticleType).filter(
        models.ArticleType.name.ilike(f"%{typ}%"))
    if size:
        base = base.filter(models.Article.size.ilike(size))
    avail = base.filter(models.Article.status == "verfuegbar").all()
    issued = base.filter(models.Article.status == "ausgegeben").count()
    label = f"{typ}" + (f" Größe {size.upper()}" if size else "")
    if not avail:
        extra = f" ({issued} ausgegeben)" if issued else ""
        return f"Kein verfügbarer Bestand für „{label}“.{extra}"
    loc = Counter(a.location_path or "ohne Lagerort" for a in avail)
    lines = [f"{label}: {len(avail)} verfügbar" + (f", zusätzlich {issued} ausgegeben" if issued else "")]
    for path, cnt in sorted(loc.items(), key=lambda x: -x[1])[:25]:
        lines.append(f"• {path}: {cnt}")
    return "\n".join(lines)


def q_suche(db, text):
    like = f"%{text.strip()}%"
    arts = db.query(models.Article).join(models.ArticleType).filter(or_(
        models.Article.artikelnummer.ilike(like),
        models.ArticleType.name.ilike(like),
        models.Article.model.ilike(like),
        models.Article.size.ilike(like),
    )).order_by(models.Article.artikelnummer).limit(20).all()
    if not arts:
        return f"Keine Treffer für „{text}“."
    lines = [f"Treffer für „{text}“ (max. 20):"]
    for a in arts:
        lines.append(f"• {a.artikelnummer} · {a.type.name if a.type else ''} {a.size or ''} · {a.status} · {a.location_path or '-'}")
    return "\n".join(lines)


def q_offen(db):
    issues = db.query(models.IssueRecord).filter(
        models.IssueRecord.return_date.is_(None)).order_by(
        models.IssueRecord.issue_date.desc()).limit(30).all()
    if not issues:
        return "Aktuell sind keine Artikel ausgegeben."
    lines = [f"Aktuell ausgegeben ({len(issues)}, max. 30):"]
    for iss in issues:
        a = iss.article
        who = (f"{iss.person.first_name} {iss.person.last_name}".strip()
               if iss.person else iss.recipient_name_freetext or "unbekannt")
        lines.append(f"• {a.artikelnummer if a else '?'} → {who}")
    return "\n".join(lines)


def q_helfer(db, name):
    name = name.strip()
    tokens = [t for t in name.split() if t]
    conds = []
    for t in tokens:
        conds.append(models.Person.first_name.ilike(f"%{t}%"))
        conds.append(models.Person.last_name.ilike(f"%{t}%"))
    persons = db.query(models.Person).filter(or_(*conds)).all() if conds else []
    person_ids = [p.id for p in persons]
    like = f"%{name}%"
    q = db.query(models.IssueRecord).filter(models.IssueRecord.return_date.is_(None))
    if person_ids:
        q = q.filter(or_(models.IssueRecord.person_id.in_(person_ids),
                         models.IssueRecord.recipient_name_freetext.ilike(like)))
    else:
        q = q.filter(models.IssueRecord.recipient_name_freetext.ilike(like))
    issues = q.limit(40).all()
    if not issues:
        return f"Für „{name}“ sind aktuell keine Artikel ausgegeben."
    lines = [f"Aktuell ausgegeben an „{name}“ ({len(issues)}):"]
    for iss in issues:
        a = iss.article
        lines.append(f"• {a.artikelnummer if a else '?'} · {a.type.name if a and a.type else ''} {a.size if a else ''}".rstrip())
    return "\n".join(lines)


def handle_command(db, text):
    text = (text or "").strip()
    if not text:
        return None
    if not text.startswith("/"):
        return q_suche(db, text)
    parts = text.split(maxsplit=1)
    cmd = parts[0].lstrip("/").split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if cmd in ("start", "help"):
        return HELP
    if cmd == "artikel":
        return q_artikel(db, arg) if arg else "Nutzung: /artikel <Nummer>"
    if cmd == "wer":
        return q_wer(db, arg) if arg else "Nutzung: /wer <Nummer>"
    if cmd == "bestand":
        if not arg:
            return "Nutzung: /bestand <Typ> [Größe]  – z.B. /bestand tshirt s"
        toks = arg.split()
        if len(toks) >= 2 and len(toks[-1]) <= 4:
            return q_bestand(db, " ".join(toks[:-1]), toks[-1])
        return q_bestand(db, arg, None)
    if cmd == "suche":
        return q_suche(db, arg) if arg else "Nutzung: /suche <Text>"
    if cmd == "offen":
        return q_offen(db)
    if cmd == "helfer":
        return q_helfer(db, arg) if arg else "Nutzung: /helfer <Name>"
    return "Unbekannter Befehl. /help für die Übersicht."


# --------------------------- Long-Polling-Bot -------------------------------

_stop = threading.Event()
_thread = None


def _poller_loop():
    while not _stop.is_set():
        s = SessionLocal()
        try:
            enabled = is_enabled(s)
            token = token_of(s)
            offset = int(get_setting(s, "telegram_offset", "0") or "0")
        except Exception:
            enabled, token, offset = False, "", 0
        finally:
            s.close()

        if not enabled or not token:
            time.sleep(5)
            continue

        resp = get_updates(token, offset, timeout=30)
        if not resp or not resp.get("ok"):
            time.sleep(3)
            continue

        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = str((msg.get("chat") or {}).get("id", ""))
            text = msg.get("text", "")
            if not chat_id:
                continue
            s2 = SessionLocal()
            try:
                allowed = set(chats(s2))
                if chat_id not in allowed:
                    send_message(token, chat_id,
                                 "Dieser Chat ist noch nicht freigeschaltet.\n"
                                 f"Chat-ID: {chat_id}\n"
                                 "Bitte den Administrator, diese ID in den Einstellungen "
                                 "(Telegram) freizuschalten.")
                else:
                    reply = handle_command(s2, text)
                    if reply:
                        send_message(token, chat_id, reply)
            except Exception:
                pass
            finally:
                s2.close()

        s3 = SessionLocal()
        try:
            set_setting(s3, "telegram_offset", str(offset))
        except Exception:
            pass
        finally:
            s3.close()


def start_poller():
    """Startet den Bot-Thread (falls nicht bereits aktiv). Der Thread laeuft immer,
    idlet aber, solange die Anbindung deaktiviert oder kein Token gesetzt ist - so
    wirkt das Aktivieren in den Einstellungen ohne Neustart."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_poller_loop, daemon=True, name="telegram-bot")
    _thread.start()
