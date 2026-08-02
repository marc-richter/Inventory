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
    return due
