"""Prüfwesen (PSA): Auslöser-Auswertung. Setzt PSA-Artikel automatisch auf den
Status „zu prüfen", sobald eine Prüfregel des Artikeltyps fällig wird."""
import datetime as dt

from . import models

CHECK_STATUS = "zu_pruefen"


def flag_if_due(db, article, just_returned=False):
    """Prüft die Regeln des Artikeltyps und setzt bei Fälligkeit „zu prüfen".
    `just_returned` markiert den Auslöser „bei Rückgabe". Gibt die fällige Regel
    zurück (oder None)."""
    if not article or not article.is_psa:
        return None
    if article.status == CHECK_STATUS:
        return None
    rules = db.query(models.InspectionRule).filter(
        models.InspectionRule.type_id == article.type_id).all()
    now = dt.datetime.utcnow()
    due = None
    for r in rules:
        thr = int(r.threshold or 0)
        if r.trigger == "return" and just_returned:
            due = r
        elif r.trigger == "loans" and thr > 0 and (article.loan_count or 0) > 0 and (article.loan_count or 0) % thr == 0:
            due = r
        elif r.trigger == "washes" and thr > 0 and (article.wash_count or 0) > 0 and (article.wash_count or 0) % thr == 0:
            due = r
        elif r.trigger == "months" and thr > 0:
            base = article.last_inspection_at or article.first_entry_date
            if base and (now - base).days >= thr * 30:
                due = r
        if due:
            break
    if due:
        article.status = CHECK_STATUS
        article.pending_checklist_id = due.checklist_id
        _notify_due(db, article)
    return due


def _notify_due(db, article):
    """Benachrichtigt die Zuständigen (Ereignis-Ziele) sowie den zuletzt
    beteiligten Helfer (Rückgeber/Ausleiher) über die fällige Prüfung."""
    try:
        from . import telegram
        typ = article.type.name if getattr(article, "type", None) else ""
        text = f"🧪 PSA-Prüfung fällig: {article.artikelnummer} {typ}. Bitte prüfen, bevor der Artikel wieder ausgegeben wird."
        telegram.notify_event(db, "inspection_due", text)
        # zuletzt beteiligten Helfer direkt anschreiben (Rueckgeber, sonst Ausgeber)
        last = db.query(models.IssueRecord).filter(
            models.IssueRecord.article_id == article.id).order_by(
            models.IssueRecord.issue_date.desc()).first()
        uid = None
        if last:
            uid = last.returned_by_user_id or last.issued_by_user_id
        if uid:
            u = db.query(models.User).get(uid)
            if u and u.telegram_chat_id:
                telegram.send_reminder_message(db, u.telegram_chat_id, text)
    except Exception:
        pass
