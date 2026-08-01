"""Telegram-Anbindung: ausgehende Benachrichtigungen und ein interaktiver Bot
(nur lesende Abfragen). Bewusst ohne Zusatzbibliothek - reine urllib-Aufrufe der
Telegram-Bot-API. Der interaktive Teil laeuft als Long-Polling-Hintergrundthread.

Einrichtung (Telegram-Seite): Der Administrator legt in Telegram per @BotFather
einen Bot an, kopiert den Token in die Einstellungen und aktiviert die Anbindung.
Danach schreibt er dem Bot eine Nachricht; der Bot antwortet mit der Chat-ID, die
der Administrator dann freischaltet.
"""
import os
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
    {"key": "low_stock", "label": "Mindestbestand unterschritten"},
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


def send_message(token, chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup)
    return _call(token, "sendMessage", params, timeout=15)


# --------------------------- Versand-Warteschlange --------------------------
# Ausgehende Ereignis-Benachrichtigungen werden nicht mehr direkt im Request-
# Ablauf verschickt, sondern in eine Warteschlange gelegt und von einem
# Hintergrund-Worker mit Wiederholung zugestellt. Das macht Aktionen fuer den
# Nutzer schnell und die Zustellung robust gegen kurze Telegram-/Netzstoerungen.
import queue as _queue  # noqa: E402

_send_q = _queue.Queue()
_sender_started = False
_sender_lock = threading.Lock()
_MAX_ATTEMPTS = 4


def _sender_worker():
    while True:
        try:
            token, chat_id, text, attempt = _send_q.get()
        except Exception:
            continue
        try:
            r = send_message(token, chat_id, text)
            ok = bool(r and r.get("ok"))
            if not ok and attempt < _MAX_ATTEMPTS:
                # Exponentielles Backoff (gedeckelt), dann erneut einreihen.
                time.sleep(min(60, 5 * attempt))
                _send_q.put((token, chat_id, text, attempt + 1))
        except Exception:
            if attempt < _MAX_ATTEMPTS:
                time.sleep(min(60, 5 * attempt))
                _send_q.put((token, chat_id, text, attempt + 1))
        finally:
            try:
                _send_q.task_done()
            except Exception:
                pass


def _ensure_sender():
    global _sender_started
    with _sender_lock:
        if not _sender_started:
            threading.Thread(target=_sender_worker, daemon=True).start()
            _sender_started = True


def queue_message(token, chat_id, text):
    """Eine Nachricht in die Versand-Warteschlange legen (nicht blockierend)."""
    if not token or chat_id is None:
        return
    _ensure_sender()
    _send_q.put((token, chat_id, text, 1))


def answer_callback_query(token, callback_query_id):
    return _call(token, "answerCallbackQuery", {"callback_query_id": callback_query_id}, timeout=10)


def send_document(token, chat_id, filename, data: bytes, caption=None, mime="application/pdf"):
    """Sendet eine Datei (z.B. PDF) als Dokument - manuell zusammengesetzter
    multipart/form-data-Upload (ohne Zusatzbibliothek)."""
    if not token:
        return None
    boundary = "----inv" + os.urandom(8).hex()
    crlf = "\r\n"
    parts = []

    def field(name, value):
        parts.append(("--" + boundary + crlf).encode())
        parts.append((f'Content-Disposition: form-data; name="{name}"' + crlf + crlf).encode())
        parts.append((str(value) + crlf).encode())

    field("chat_id", chat_id)
    if caption:
        field("caption", caption)
    parts.append(("--" + boundary + crlf).encode())
    parts.append((f'Content-Disposition: form-data; name="document"; filename="{filename}"' + crlf).encode())
    parts.append((f"Content-Type: {mime}" + crlf + crlf).encode())
    parts.append(data)
    parts.append((crlf + "--" + boundary + "--" + crlf).encode())
    body = b"".join(parts)
    req = urllib.request.Request(_API.format(token=token, method="sendDocument"), data=body)
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def send_report_pdf(db, chat_id):
    """Erzeugt die Inventarlisten-PDF und schickt sie an den Chat."""
    from .routers.export import build_inventory_pdf
    arts = db.query(models.Article).filter(models.Article.provisional == False)  # noqa: E712
    arts = arts.order_by(models.Article.artikelnummer).all()
    try:
        pdf = build_inventory_pdf(db, arts, by_name="Telegram")
    except Exception:
        return None
    return send_document(token_of(db), chat_id, "inventarliste.pdf", pdf,
                         caption=f"Inventarliste ({len(arts)} Artikel)")


def _chat_can_inventory(db, chat_id):
    """True, wenn der mit diesem Chat verknuepfte Benutzer Inventur-Rechte hat.
    Nur so werden Chronik und Berichts-PDFs herausgegeben ("von Berechtigten")."""
    u = linked_user(db, chat_id)
    if not u or not u.active:
        return False
    if "admin" in (u.roles or []):
        return True
    try:
        from .permissions import user_capabilities
        return "inventory" in user_capabilities(db, u)
    except Exception:
        return False


def _chronik_menu(db, limit=10):
    """Text + Buttons fuer die Inventur-Chronik (zuletzt archivierte Berichte)."""
    rows = db.query(models.InventoryReportArchive).order_by(
        models.InventoryReportArchive.created_at.desc()).limit(limit).all()
    if not rows:
        return ("Noch keine abgeschlossenen Inventuren in der Chronik.", _back_menu())
    lines = ["📚 Inventur-Chronik (neueste zuerst) – tippe auf einen Eintrag für den Bericht als PDF:"]
    kb = []
    for r in rows:
        st = r.stats or {}
        d = r.created_at.strftime("%d.%m.%Y") if r.created_at else ""
        lines.append(f"• {r.campaign_name} ({d}) – fehlend {st.get('open_count', 0)}, "
                     f"gefunden {st.get('found_count', 0)}/{st.get('expected_count', 0)}")
        kb.append([{"text": f"📄 {r.campaign_name[:40]} ({d})", "callback_data": f"rep:{r.id}"}])
    kb.append([{"text": "‹ Menü", "callback_data": "menu"}])
    return ("\n".join(lines), {"inline_keyboard": kb})


def send_report_archive_pdf(db, chat_id, report_id):
    """Den archivierten Abschlussbericht als PDF an den Chat senden (Datei bevorzugt,
    sonst aus dem gespeicherten Snapshot neu gebaut)."""
    r = db.query(models.InventoryReportArchive).get(report_id)
    if not r:
        send_message(token_of(db), chat_id, "Bericht nicht gefunden.")
        return None
    pdf = None
    try:
        from .config import INVENTORY_REPORTS_DIR
        if r.pdf_filename:
            p = INVENTORY_REPORTS_DIR / os.path.basename(r.pdf_filename)
            if p.exists():
                pdf = p.read_bytes()
        if pdf is None:
            from .routers.export import build_campaign_report_pdf
            d = r.data or {}
            pdf = build_campaign_report_pdf(db, d.get("meta", {}), d.get("found", []),
                                            d.get("missing", []), d.get("ignored", []), r.stats or {})
    except Exception:
        pdf = None
    if pdf is None:
        send_message(token_of(db), chat_id, "Bericht konnte nicht erstellt werden.")
        return None
    return send_document(token_of(db), chat_id, "inventurbericht.pdf", pdf,
                         caption=f"Inventurbericht: {r.campaign_name}")


def build_ics(summary: str, when, description: str = "", uid: str = None, rrule: str = None) -> bytes:
    """Baut eine einfache iCalendar-Datei (Ganztagestermin) fuer eine Inventur.
    `when` ist ein date/datetime; mit `rrule` wird ein Serientermin erzeugt. Ohne
    Zusatzbibliothek, mit CRLF-Zeilenenden."""
    import datetime as _dt
    if isinstance(when, _dt.datetime):
        day = when.date()
    elif isinstance(when, _dt.date):
        day = when
    else:
        day = _dt.date.today()
    dstamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dstart = day.strftime("%Y%m%d")
    dend = (day + _dt.timedelta(days=1)).strftime("%Y%m%d")
    uid = uid or f"inventur-{dstart}-{abs(hash(summary)) % 100000}@drk-inventar"

    def esc(t):
        return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DRK Inventar//DE",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{uid}", f"DTSTAMP:{dstamp}",
        f"DTSTART;VALUE=DATE:{dstart}", f"DTEND;VALUE=DATE:{dend}",
        f"SUMMARY:{esc(summary)}",
    ]
    if rrule:
        lines.append(f"RRULE:{rrule}")
    if description:
        lines.append(f"DESCRIPTION:{esc(description)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def send_schedule_ics(db, schedule):
    """EINE Termin-ICS (Einzeltermin, KEINE Wiederholungsregel) fuer den naechsten
    Termin eines Zeitplans an die Inventur-Empfaenger schicken. Bewusst nur ein
    Termin - bei jeder Aenderung/Erinnerung wird die (gleiche) Datei mit dem dann
    naechsten Termin neu geschickt. Die stabile UID sorgt dafuer, dass im Kalender
    genau EIN Eintrag entsteht, der jeweils auf den naechsten Termin rueckt."""
    try:
        if not is_enabled(db):
            return
        token = token_of(db)
        if not token or not schedule.next_run:
            return
        uid = f"inv-schedule-{schedule.id}@drk-inventar"
        ics = build_ics(f"Inventur: {schedule.name}", schedule.next_run,
                        "Nächster Inventur-Termin", uid=uid)
        when = schedule.next_run.strftime("%d.%m.%Y")
        for c in resolve_targets(db, "inventory"):
            send_document(token, c, "inventur-termin.ics", ics,
                          caption=f"📅 Nächster Termin „{schedule.name}“: {when}",
                          mime="text/calendar")
    except Exception:
        pass


def send_reminder_message(db, chat_id, text, campaign=None):
    """Eine Erinnerung an genau einen Chat schicken. Der Text laeuft ueber die
    Warteschlange; ist eine Kampagne angegeben, wird zusaetzlich EIN Termin als
    .ics-Datei mitgeschickt (Einzeltermin, stabile UID je Kampagne)."""
    token = token_of(db)
    if not token or chat_id is None:
        return
    queue_message(token, chat_id, text)
    if campaign is not None and campaign.planned_start:
        try:
            ics = build_ics(f"Inventur: {campaign.name}", campaign.planned_start,
                            "Inventur-Termin", uid=f"inv-campaign-{campaign.id}@drk-inventar")
            send_document(token, chat_id, "inventur-termin.ics", ics,
                          caption=None, mime="text/calendar")
        except Exception:
            pass


def send_inventory_ics(db, campaign_name: str, when, description: str = ""):
    """Verschickt eine Termin-Datei (.ics) fuer eine Inventur an alle Empfaenger des
    Inventur-Ereignisses - z.B. als Erinnerung zu einer geplanten/anstehenden Inventur."""
    try:
        if not is_enabled(db):
            return
        token = token_of(db)
        if not token:
            return
        ics = build_ics(f"Inventur: {campaign_name}", when, description or "Inventur-Termin")
        for c in resolve_targets(db, "inventory"):
            send_document(token, c, "inventur.ics", ics,
                          caption=f"📅 Termin: Inventur „{campaign_name}“", mime="text/calendar")
    except Exception:
        pass


def get_updates(token, offset, timeout=30):
    return _call(token, "getUpdates", {"offset": offset, "timeout": timeout}, timeout=timeout + 10)


# --------------------------- Konfiguration ----------------------------------

def is_enabled(db):
    return (get_setting(db, "telegram_enabled", "false") or "").lower() == "true"


def token_of(db):
    return (get_setting(db, "telegram_bot_token", "") or "").strip()


def _csv(db, key):
    return [c.strip() for c in (get_setting(db, key, "") or "").split(",") if c.strip()]


def chats(db):
    return _csv(db, "telegram_chats")


def blacklist(db):
    return _csv(db, "telegram_blacklist")


def paused(db):
    return _csv(db, "telegram_paused")


def is_blacklisted(db, chat_id):
    return str(chat_id) in set(blacklist(db))


def is_paused(db, chat_id):
    return str(chat_id) in set(paused(db))


def self_link_enabled(db):
    return (get_setting(db, "telegram_self_link_enabled", "false") or "").lower() == "true"


def linked_user(db, chat_id):
    """Der Benutzer, dessen Telegram-Konto mit dieser Chat-ID verknuepft ist (oder None)."""
    return db.query(models.User).filter(models.User.telegram_chat_id == str(chat_id)).first()


def is_allowed(db, chat_id):
    """Ein Chat darf abfragen/Benachrichtigungen erhalten, wenn er weder gesperrt
    (Blacklist) noch pausiert ist UND entweder vom Admin freigeschaltet ist ODER mit
    einem AKTIVEN Benutzerkonto verknuepft ist (Kopplung an den Account)."""
    cid = str(chat_id)
    if is_blacklisted(db, cid) or is_paused(db, cid):
        return False
    if cid in set(chats(db)):
        return True
    u = linked_user(db, cid)
    return bool(u and u.active)


def _get_json(db, key):
    try:
        val = json.loads(get_setting(db, key, "") or "")
        return val
    except (ValueError, TypeError):
        return None


def names_map(db):
    m = _get_json(db, "telegram_chat_names")
    return m if isinstance(m, dict) else {}


def chat_name(db, chat_id):
    return names_map(db).get(str(chat_id))


def record_seen(db, chat_id, name):
    """Merkt sich den Anzeigenamen zu einer Chat-ID (fuer die Anzeige der
    freigeschalteten/wartenden Chats)."""
    name = (name or "").strip()
    if not name:
        return
    m = names_map(db)
    cid = str(chat_id)
    if m.get(cid) == name:
        return
    m[cid] = name
    set_setting(db, "telegram_chat_names", json.dumps(m))


def pending_list(db):
    lst = _get_json(db, "telegram_pending")
    return lst if isinstance(lst, list) else []


def record_pending(db, chat_id, name, username):
    """Sammelt Verbindungsversuche noch nicht freigeschalteter Chats, damit der Admin
    sie mit einem Klick bestaetigen kann."""
    cid = str(chat_id)
    if is_allowed(db, cid):
        return
    lst = pending_list(db)
    for e in lst:
        if str(e.get("chat_id")) == cid:
            e["name"] = name or e.get("name")
            e["username"] = username or e.get("username")
            set_setting(db, "telegram_pending", json.dumps(lst))
            return
    lst.append({"chat_id": cid, "name": name or "", "username": username or ""})
    set_setting(db, "telegram_pending", json.dumps(lst[-50:]))


def remove_pending(db, chat_id):
    cid = str(chat_id)
    lst = [e for e in pending_list(db) if str(e.get("chat_id")) != cid]
    set_setting(db, "telegram_pending", json.dumps(lst))


def add_blacklist(db, chat_id):
    """Sperrt einen Chat dauerhaft: er wird ignoriert (keine Antwort mehr) und aus
    Warteliste, freigeschalteten Chats und Pause entfernt."""
    cid = str(chat_id)
    bl = blacklist(db)
    if cid not in bl:
        bl.append(cid)
        set_setting(db, "telegram_blacklist", ",".join(bl))
    remove_pending(db, cid)
    set_setting(db, "telegram_chats", ",".join(c for c in chats(db) if c != cid))
    set_setting(db, "telegram_paused", ",".join(c for c in paused(db) if c != cid))


def remove_blacklist(db, chat_id):
    cid = str(chat_id)
    set_setting(db, "telegram_blacklist", ",".join(c for c in blacklist(db) if c != cid))


def set_paused(db, chat_id, value: bool):
    cid = str(chat_id)
    p = [c for c in paused(db) if c != cid]
    if value:
        p.append(cid)
    set_setting(db, "telegram_paused", ",".join(p))


def _display_name(msg):
    frm = msg.get("from") or {}
    chat = msg.get("chat") or {}
    if chat.get("title"):
        return chat["title"]
    name = " ".join(p for p in [frm.get("first_name"), frm.get("last_name")] if p).strip()
    return name or frm.get("username") or chat.get("username") or ""


def try_link(db, chat_id, code):
    """Verknuepft die Chat-ID mit dem Benutzer, dessen Link-Code passt. Gibt den
    Benutzer zurueck oder None. Nur wenn die Selbstverknuepfung freigegeben ist."""
    code = (code or "").strip()
    if not code or not self_link_enabled(db):
        return None
    u = db.query(models.User).filter(models.User.telegram_link_code == code).first()
    if not u:
        return None
    u.telegram_chat_id = str(chat_id)
    u.telegram_link_code = None
    db.commit()
    return u


def events(db):
    raw = get_setting(db, "telegram_notify_events", "provisional,inventory,low_stock")
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
        if not is_allowed(db, c):   # pausierte/gesperrte/deaktivierte Chats auslassen
            continue
        r = send_message(token, c, text)
        if r and r.get("ok"):
            n += 1
    return n


def event_targets(db):
    d = _get_json(db, "telegram_event_targets")
    return d if isinstance(d, dict) else {}


def set_event_targets(db, event_key, cfg):
    all_t = event_targets(db)
    all_t[event_key] = cfg
    set_setting(db, "telegram_event_targets", json.dumps(all_t))


def _linked_chat(db, uid):
    u = db.query(models.User).get(uid)
    return u.telegram_chat_id if (u and u.telegram_chat_id) else None


def resolve_targets(db, event_key):
    """Ermittelt die Ziel-Chat-IDs fuer ein Ereignis anhand der Empfaenger-Konfiguration
    (alle Chats / Gruppen / Rollen / Einzelpersonen). Ohne Konfiguration: an alle
    freigeschalteten Chats (Standardverhalten)."""
    cfg = event_targets(db).get(event_key) or {"all": True}
    out = set()
    if cfg.get("all"):
        out |= set(chats(db))
    for gid in cfg.get("groups", []) or []:
        for m in db.query(models.UserGroupMember).filter(models.UserGroupMember.group_id == gid).all():
            cid = _linked_chat(db, m.user_id)
            if cid:
                out.add(cid)
    roles = set(cfg.get("roles", []) or [])
    if roles:
        for u in db.query(models.User).filter(models.User.telegram_chat_id.isnot(None)).all():
            if set(u.roles or []) & roles:
                out.add(u.telegram_chat_id)
    for uid in cfg.get("users", []) or []:
        cid = _linked_chat(db, uid)
        if cid:
            out.add(cid)
    return {c for c in out if is_allowed(db, c)}


def notify_refind(db, article):
    """Meldung, dass ein zuvor als verschollen markierter Artikel wieder aufgetaucht
    ist. Nutzt das Inventur-Ereignis (funktioniert ohne zusaetzliche Konfiguration)."""
    try:
        typ = article.type.name if getattr(article, "type", None) else ""
        loc = article.location_path or "-"
        notify_event(db, "inventory",
                     f"🔎 Wiedergefunden: {article.artikelnummer} {typ} – war als „verschollen“ "
                     f"markiert und ist jetzt wieder da. Aktueller Ort: {loc}.")
    except Exception:
        pass


def notify_event(db, event_key, text):
    """Eine Ereignis-Benachrichtigung an alle Ziel-Chats zustellen. Die Ziele werden
    sofort (schnelle DB-Lesezugriffe) ermittelt, der eigentliche Versand laeuft ueber
    die Warteschlange mit Wiederholung. Loest nie eine Ausnahme im Aufrufer aus."""
    try:
        if not is_enabled(db) or event_key not in events(db):
            return
        token = token_of(db)
        if not token:
            return
        targets = list(resolve_targets(db, event_key))
    except Exception:
        return
    for c in targets:
        queue_message(token, c, text)


# --------------------------- Abfragen (nur lesend) --------------------------

HELP = (
    "Inventar-Bot – nur Abfragen, keine Änderungen.\n\n"
    "Am einfachsten per Menü: /menu – Typ wählen, dann optional nach Größe, Modell, "
    "Eigenschaft (z.B. Farbe) und Lagerort einschränken. Jedes Kriterium lässt sich mit "
    "„alle“ überspringen (z.B. alle T-Shirts statt nur orange).\n\n"
    "Oder direkt per Befehl:\n"
    "/artikel <Nummer> – Details zu einem Artikel\n"
    "/wer <Nummer> – wer hat den Artikel gerade\n"
    "/bestand <Typ> [Größe] – verfügbarer Bestand + Lagerorte\n"
    "/suche <Text> – Artikel suchen\n"
    "/offen – aktuell ausgegebene Artikel\n"
    "/helfer <Name> – was hat diese Person gerade\n"
    "/pdf – Inventarliste als PDF\n"
    "/chronik – Chronik vergangener Inventuren + Bericht als PDF (nur Berechtigte)\n\n"
    "Beispiele: „/bestand tshirt s“, „/wer 2026-00042“, „/helfer Mustermann“"
)


def minimize_pii(db):
    return (get_setting(db, "telegram_minimize_pii", "false") or "").lower() == "true"


def actor_label(db, user):
    """Anzeigename fuer Meldungen - oder neutral, wenn Datenminimierung aktiv ist."""
    if minimize_pii(db):
        return "einem Nutzer"
    return (user.full_name or user.username) if user else "einem Nutzer"


def _holder(article):
    for iss in article.issues:
        if not iss.return_date:
            if iss.person:
                return f"{iss.person.first_name} {iss.person.last_name}".strip()
            return iss.recipient_name_freetext or "unbekannt"
    return None


def _holder_label(db, article):
    h = _holder(article)
    if h and minimize_pii(db):
        return "(vergeben)"
    return h


def q_artikel(db, nr):
    a = db.query(models.Article).filter(models.Article.artikelnummer == nr.strip()).first()
    if not a:
        return f"Kein Artikel mit Nummer {nr}."
    h = _holder_label(db, a)
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
    h = _holder_label(db, a)
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
    minimize = minimize_pii(db)
    lines = [f"Aktuell ausgegeben ({len(issues)}, max. 30):"]
    for iss in issues:
        a = iss.article
        if minimize:
            who = "(vergeben)"
        else:
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


# --------------------------- Menü / facettierte Suche -----------------------
# Geführte Suche über Buttons: Typ wählen, dann beliebig nach Größe, Modell,
# Eigenschaft (z.B. Farbe) und Lagerort einschränken – jedes Kriterium ist
# optional und kann mit "alle" übersprungen werden. Der Filterzustand wird kompakt
# in den callback_data kodiert als  t:s:m:p:l  (jeweils "*" = alle, sonst Index in
# der deterministisch sortierten Werteliste dieser Facette).

WELCOME = "Inventar-Bot – wähle eine Aktion oder tippe /help für alle Befehle."

FACET_FIELDS = ["size", "model", "properties", "location"]
FACET_LABEL = {"size": "Größe", "model": "Modell", "properties": "Eigenschaft", "location": "Lagerort"}
FACET_PREFIX = {"s": "size", "m": "model", "p": "properties", "l": "location"}


def _main_menu():
    return {"inline_keyboard": [
        [{"text": "🔎 Suchen / Bestand", "callback_data": "bt"}],
        [{"text": "📤 Offene Ausgaben", "callback_data": "offen"}],
        [{"text": "📄 PDF-Auswertung", "callback_data": "pdf"}],
        [{"text": "📚 Inventur-Chronik", "callback_data": "chronik"}],
        [{"text": "❓ Hilfe", "callback_data": "help"}],
    ]}


def _back_menu():
    return {"inline_keyboard": [[{"text": "‹ Menü", "callback_data": "menu"}]]}


def _rows(buttons, per_row=2):
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def _type_menu(db):
    type_ids = [tid for (tid,) in db.query(models.Article.type_id).distinct().all() if tid]
    types = db.query(models.ArticleType).filter(models.ArticleType.id.in_(type_ids)) \
        .order_by(models.ArticleType.name).all() if type_ids else []
    btns = [{"text": t.name, "callback_data": f"bt:{t.id}"} for t in types[:40]]
    kb = _rows(btns, 2)
    kb.append([{"text": "‹ Menü", "callback_data": "menu"}])
    return {"inline_keyboard": kb}


def _type_articles(db, type_id):
    return db.query(models.Article).filter(models.Article.type_id == type_id)


def _facet_options(db, type_id, field):
    """Deterministisch sortierte, eindeutige Werte einer Facette unter den Artikeln
    dieses Typs (Basis für stabile Index-Kodierung)."""
    vals = set()
    for a in _type_articles(db, type_id).all():
        v = a.location_path if field == "location" else (getattr(a, field, "") or "")
        v = (v or "").strip()
        if v:
            vals.add(v)
    return sorted(vals, key=lambda s: s.lower())


def _enc(t, sel):
    return f"{t}:" + ":".join(str(sel[f]) for f in FACET_FIELDS)


def _dec(rest):
    parts = rest.split(":")
    t = int(parts[0])
    sel = {}
    for i, f in enumerate(FACET_FIELDS):
        sel[f] = parts[i + 1] if i + 1 < len(parts) else "*"
    return t, sel


def _sel_value(db, t, field, code):
    if not code or code == "*":
        return None
    try:
        idx = int(code)
    except ValueError:
        return None
    opts = _facet_options(db, t, field)
    return opts[idx] if 0 <= idx < len(opts) else None


def _type_name(db, t):
    tt = db.query(models.ArticleType).get(t)
    return tt.name if tt else "?"


def _facet_menu(db, t, sel):
    rows = []
    for f in FACET_FIELDS:
        val = _sel_value(db, t, f, sel[f])
        rows.append([{"text": f"{FACET_LABEL[f]}: {val if val else 'alle'}",
                      "callback_data": f"f{f[0]}:{_enc(t, sel)}"}])
    rows.append([{"text": "✅ Ergebnis anzeigen", "callback_data": f"fr:{_enc(t, sel)}"}])
    rows.append([{"text": "‹ Typen", "callback_data": "bt"}, {"text": "‹ Menü", "callback_data": "menu"}])
    return {"inline_keyboard": rows}


def _facet_submenu(db, t, sel, field):
    opts = _facet_options(db, t, field)
    btns = []
    for i, v in enumerate(opts[:40]):
        s2 = dict(sel); s2[field] = str(i)
        btns.append({"text": v[:24], "callback_data": f"bf:{_enc(t, s2)}"})
    kb = _rows(btns, 2)
    s_all = dict(sel); s_all[field] = "*"
    kb.append([{"text": f"alle {FACET_LABEL[field]}", "callback_data": f"bf:{_enc(t, s_all)}"}])
    kb.append([{"text": "‹ zurück", "callback_data": f"bf:{_enc(t, sel)}"}])
    return {"inline_keyboard": kb}


def q_facets(db, t, sel):
    name = _type_name(db, t)
    size = _sel_value(db, t, "size", sel["size"])
    model = _sel_value(db, t, "model", sel["model"])
    props = _sel_value(db, t, "properties", sel["properties"])
    loc = _sel_value(db, t, "location", sel["location"])
    q = _type_articles(db, t)
    if size:
        q = q.filter(models.Article.size == size)
    if model:
        q = q.filter(models.Article.model == model)
    if props:
        q = q.filter(models.Article.properties == props)
    arts = q.all()
    if loc:
        arts = [a for a in arts if (a.location_path or "") == loc]
    avail = [a for a in arts if a.status == "verfuegbar"]
    issued = sum(1 for a in arts if a.status == "ausgegeben")
    crit = [name]
    for f, v in [("size", size), ("model", model), ("properties", props), ("location", loc)]:
        if v:
            crit.append(f"{FACET_LABEL[f]} {v}")
    label = ", ".join(crit)
    if not avail:
        extra = f" ({issued} ausgegeben)" if issued else ""
        return f"Kein verfügbarer Bestand für {label}.{extra}"
    by_loc = Counter(a.location_path or "ohne Lagerort" for a in avail)
    lines = [f"{label}: {len(avail)} verfügbar" + (f", zusätzlich {issued} ausgegeben" if issued else "")]
    for path, cnt in sorted(by_loc.items(), key=lambda x: -x[1])[:25]:
        lines.append(f"• {path}: {cnt}")
    return "\n".join(lines)


def dispatch_callback(db, data):
    """Verarbeitet einen Button-Klick. Gibt (text, reply_markup) zurueck."""
    data = data or ""
    if data == "menu":
        return WELCOME, _main_menu()
    if data == "help":
        return HELP, _back_menu()
    if data == "offen":
        return q_offen(db), _back_menu()
    if data == "bt":
        return "Wähle einen Typ:", _type_menu(db)
    if data.startswith("bt:"):
        t = int(data.split(":", 1)[1])
        sel = {f: "*" for f in FACET_FIELDS}
        return (f"{_type_name(db, t)}: Kriterien wählen (jedes optional) oder direkt „Ergebnis anzeigen“.",
                _facet_menu(db, t, sel))
    if data.startswith("bf:"):
        t, sel = _dec(data[3:])
        return "Kriterien (jedes optional):", _facet_menu(db, t, sel)
    if data[:3] in ("fs:", "fm:", "fp:", "fl:"):
        field = FACET_PREFIX[data[1]]
        t, sel = _dec(data[3:])
        return f"{FACET_LABEL[field]} wählen (oder „alle“):", _facet_submenu(db, t, sel, field)
    if data.startswith("fr:"):
        t, sel = _dec(data[3:])
        return q_facets(db, t, sel), _back_menu()
    return WELCOME, _main_menu()


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

_MENU_CMDS = {"/start", "/menu", "/menü"}


def _not_allowed_text(chat_id):
    return ("Dieser Chat ist noch nicht freigeschaltet.\n"
            f"Chat-ID: {chat_id}\n"
            "Entweder der Administrator schaltet diese ID frei, oder du verknüpfst dich "
            "selbst: in der Anwendung unter „Mein Konto“ einen Code erzeugen und ihn hier "
            "als „/link CODE“ senden (sofern freigegeben).")


def _process_update(token, upd):
    cq = upd.get("callback_query")
    if cq:
        m = cq.get("message") or {}
        chat_id = str((m.get("chat") or {}).get("id", ""))
        answer_callback_query(token, cq.get("id"))
        if not chat_id:
            return
        s = SessionLocal()
        try:
            if is_blacklisted(s, chat_id):
                return
            if not is_allowed(s, chat_id):
                send_message(token, chat_id, _not_allowed_text(chat_id))
                return
            cdata = cq.get("data") or ""
            if cdata == "pdf":
                send_message(token, chat_id, "Erstelle die PDF-Auswertung …")
                send_report_pdf(s, chat_id)
                send_message(token, chat_id, "Fertig.", reply_markup=_back_menu())
                return
            if cdata == "chronik":
                if not _chat_can_inventory(s, chat_id):
                    send_message(token, chat_id,
                                 "Die Inventur-Chronik ist nur für berechtigte Nutzer (mit Inventur-Recht). "
                                 "Bitte verknüpfe dein Konto unter „Mein Konto“.",
                                 reply_markup=_back_menu())
                    return
                text, markup = _chronik_menu(s)
                send_message(token, chat_id, text, reply_markup=markup)
                return
            if cdata.startswith("rep:"):
                if not _chat_can_inventory(s, chat_id):
                    send_message(token, chat_id, "Nur für berechtigte Nutzer (Inventur-Recht).",
                                 reply_markup=_back_menu())
                    return
                try:
                    rid = int(cdata.split(":", 1)[1])
                except ValueError:
                    return
                send_message(token, chat_id, "Erstelle den Berichts-PDF …")
                send_report_archive_pdf(s, chat_id, rid)
                send_message(token, chat_id, "Fertig.", reply_markup=_back_menu())
                return
            text, markup = dispatch_callback(s, cq.get("data", ""))
            send_message(token, chat_id, text, reply_markup=markup)
        finally:
            s.close()
        return

    msg = upd.get("message") or upd.get("edited_message")
    if not msg:
        return
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text", "")
    if not chat_id:
        return
    name = _display_name(msg)
    username = (msg.get("from") or {}).get("username")
    s = SessionLocal()
    try:
        if is_blacklisted(s, chat_id):
            return   # gesperrt: still ignorieren, keine Antwort
        record_seen(s, chat_id, name or username or chat_id)
        low = (text or "").strip().lower().split("@")[0]
        # Verknuepfung ist auch aus einem noch nicht freigeschalteten Chat moeglich.
        if low == "/link" or low.startswith("/link "):
            parts = (text or "").strip().split(maxsplit=1)
            code = parts[1].strip() if len(parts) > 1 else ""
            u = try_link(s, chat_id, code)
            if u:
                send_message(token, chat_id,
                             f"✅ Verknüpft mit dem Konto „{u.full_name or u.username}“. "
                             "Du kannst den Bot jetzt nutzen – tippe /menu.",
                             reply_markup=_main_menu())
            else:
                send_message(token, chat_id,
                             "Verknüpfung fehlgeschlagen: Code ungültig/abgelaufen oder "
                             "Selbstverknüpfung ist nicht freigegeben. Bitte in den "
                             "Kontoeinstellungen einen neuen Code erzeugen.")
            return
        if not is_allowed(s, chat_id):
            record_pending(s, chat_id, name, username)
            send_message(token, chat_id, _not_allowed_text(chat_id))
            return
        if low in _MENU_CMDS:
            send_message(token, chat_id, WELCOME, reply_markup=_main_menu())
        elif low == "/pdf":
            send_message(token, chat_id, "Erstelle die PDF-Auswertung …")
            send_report_pdf(s, chat_id)
            send_message(token, chat_id, "Fertig.", reply_markup=_back_menu())
        elif low in ("/chronik", "/inventuren"):
            if not _chat_can_inventory(s, chat_id):
                send_message(token, chat_id,
                             "Die Inventur-Chronik ist nur für berechtigte Nutzer (mit Inventur-Recht). "
                             "Bitte verknüpfe dein Konto unter „Mein Konto“.", reply_markup=_back_menu())
            else:
                text, markup = _chronik_menu(s)
                send_message(token, chat_id, text, reply_markup=markup)
        else:
            reply = handle_command(s, text)
            if reply:
                # Nach einer Antwort das Menü als schnelle Weiterführung anbieten.
                send_message(token, chat_id, reply, reply_markup=_back_menu())
    finally:
        s.close()


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
            try:
                _process_update(token, upd)
            except Exception:
                pass

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
