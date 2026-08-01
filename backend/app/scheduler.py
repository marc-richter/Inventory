import datetime as dt
from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .settings_helper import get_setting
from .backup import create_backup

scheduler = BackgroundScheduler(timezone="Europe/Berlin")


def _run_auto_backup_check():
    db = SessionLocal()
    try:
        enabled = get_setting(db, "backup_auto_enabled", "false") == "true"
        if not enabled:
            return
        target_time = get_setting(db, "backup_auto_time", "02:00")
        now = dt.datetime.now()
        try:
            hh, mm = [int(x) for x in target_time.split(":")]
        except Exception:
            hh, mm = 2, 0
        # Job laeuft jede Minute; nur im passenden Minutenfenster taeglich sichern
        if now.hour == hh and now.minute == mm:
            create_backup(db, kind="auto")
    finally:
        db.close()


def _run_audit_purge():
    """DSGVO: altes Pruefprotokoll gemaess eingestellter Aufbewahrungsfrist loeschen."""
    db = SessionLocal()
    try:
        from .audit import purge_old
        try:
            days = int(get_setting(db, "audit_retention_days", "0") or "0")
        except (ValueError, TypeError):
            days = 0
        if days > 0:
            purge_old(db, days)
    finally:
        db.close()


def _run_inventory_schedules():
    """Faellige wiederkehrende Inventur-Zeitplaene in geplante Kampagnen umwandeln
    und den naechsten Termin fortschreiben."""
    db = SessionLocal()
    try:
        from . import models
        from .routers.inventory import create_campaign_from_templates, _advance
        now = dt.datetime.utcnow()
        due = db.query(models.InventorySchedule).filter(
            models.InventorySchedule.active == True,           # noqa: E712
            models.InventorySchedule.next_run != None,          # noqa: E711
            models.InventorySchedule.next_run <= now,
        ).all()
        for s in due:
            tids = [t.template_id for t in s.templates]
            if not tids:
                # ohne Vorlage nichts zu tun – trotzdem Termin fortschreiben
                s.next_run = _advance(s.next_run or now, s.interval, s.unit)
                continue
            specs = [(p.user_id, p.role) for p in s.schedule_participants]
            ignore = [x for x in (s.ignore_status or "").split(",") if x.strip()]
            c = create_campaign_from_templates(
                db, f"{s.name} {now.date().isoformat()}", tids, s.next_run,
                s.created_by_id, ignore_override=ignore, participant_specs=specs)
            s.last_run = now
            s.next_run = _advance(s.next_run or now, s.interval, s.unit)
            db.commit()
            try:
                from . import telegram
                telegram.notify_event(db, "inventory",
                                      f"🗓️ Geplante Inventur „{c.name}“ wurde automatisch angelegt.")
            except Exception:
                pass
        db.commit()
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(_run_auto_backup_check, "interval", minutes=1, id="auto_backup_check", replace_existing=True)
        scheduler.add_job(_run_audit_purge, "interval", hours=6, id="audit_purge", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_inventory_schedules, "interval", minutes=30, id="inventory_schedules", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.start()
