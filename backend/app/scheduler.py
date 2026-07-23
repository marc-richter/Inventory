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


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(_run_auto_backup_check, "interval", minutes=1, id="auto_backup_check", replace_existing=True)
        scheduler.start()
