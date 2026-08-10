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
                s.next_run = _advance(s.next_run or now, s.interval, s.unit, s.weekday, s.week_of_month)
                continue
            specs = [(p.user_id, p.role) for p in s.schedule_participants]
            ignore = [x for x in (s.ignore_status or "").split(",") if x.strip()]
            due_date = s.next_run or now
            c = create_campaign_from_templates(
                db, f"{s.name} {now.date().isoformat()}", tids, due_date,
                s.created_by_id, ignore_override=ignore, participant_specs=specs,
                reminder_days_before=s.reminder_days_before)
            s.last_run = now
            s.next_run = _advance(s.next_run or now, s.interval, s.unit, s.weekday, s.week_of_month)
            db.commit()
            try:
                from . import telegram
                telegram.notify_event(db, "inventory",
                                      f"🗓️ Geplante Inventur „{c.name}“ steht an und wurde angelegt.")
                # Nur EIN Termin: die (gleiche) ICS jetzt mit dem NEUEN nächsten Termin
                # senden – stabile UID, daher aktualisiert sich der Kalendereintrag.
                telegram.send_schedule_ics(db, s)
            except Exception:
                pass
        db.commit()
    finally:
        db.close()


def _run_inventory_reminders():
    """Verschickt vor geplanten Inventuren einmalig eine Telegram-Erinnerung. Die
    Vorlaufzeit ergibt sich je Empfaenger aus seiner persoenlichen Einstellung
    (falls gesetzt) oder dem Standardwert der Inventur. Doppelte Erinnerungen werden
    ueber ein Log (Kampagne+Chat) verhindert."""
    db = SessionLocal()
    try:
        from . import models, telegram
        if not telegram.is_enabled(db):
            return
        now = dt.datetime.utcnow()
        campaigns = db.query(models.InventoryCampaign).filter(
            models.InventoryCampaign.status == "planned",
            models.InventoryCampaign.planned_start != None,   # noqa: E711
            models.InventoryCampaign.planned_start > now,
        ).all()
        if not campaigns:
            return
        targets = list(telegram.resolve_targets(db, "inventory"))
        for c in campaigns:
            default_lead = c.reminder_days_before if c.reminder_days_before is not None else 3
            for chat_id in targets:
                u = telegram.linked_user(db, chat_id)
                lead = default_lead
                if u is not None and u.reminder_days_before is not None:
                    lead = u.reminder_days_before
                if lead is None or lead < 0:
                    continue
                remind_at = c.planned_start - dt.timedelta(days=lead)
                if now < remind_at:
                    continue   # noch zu frueh
                already = db.query(models.InventoryReminderLog).filter(
                    models.InventoryReminderLog.campaign_id == c.id,
                    models.InventoryReminderLog.chat_id == str(chat_id)).first()
                if already:
                    continue
                when = c.planned_start.strftime("%d.%m.%Y")
                telegram.send_reminder_message(
                    db, chat_id,
                    f"⏰ Erinnerung: Die Inventur „{c.name}“ ist für den {when} geplant.",
                    campaign=c)
                db.add(models.InventoryReminderLog(campaign_id=c.id, chat_id=str(chat_id), sent_at=now))
        db.commit()
    finally:
        db.close()


def _run_low_stock_check():
    """Prueft die Mindestbestand-Regeln und meldet neue Unterschreitungen an die
    fuer das Ereignis 'low_stock' konfigurierten Ziele (Personen/Gruppen/Rollen).
    Dank Merker (rule.notified) wird je Unterschreitung nur einmal benachrichtigt."""
    db = SessionLocal()
    try:
        from . import models, telegram
        from sqlalchemy.orm import joinedload
        from .routers.stats_router import _min_stock_status
        arts = db.query(models.Article).options(joinedload(models.Article.type)) \
            .filter(models.Article.provisional == False).all()  # noqa: E712
        status = _min_stock_status(db, arts)
        changed = False
        for s in status:
            r = s["rule"]
            if s["breached"] and not r.notified:
                where = f" @ {s['node_path']}" if s["node_path"] else ""
                size = f" Gr. {s['size']}" if s["size"] else ""
                telegram.notify_event(
                    db, "low_stock",
                    f"⚠️ Mindestbestand unterschritten: {s['type']}{size}{where} – "
                    f"nur noch {s['available']} verfügbar (Minimum {s['min_stock']}).")
                r.notified = True
                changed = True
            elif not s["breached"] and r.notified:
                r.notified = False   # wieder aufgefuellt -> erneute Meldung spaeter moeglich
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _run_inspection_time_check():
    """Zeitbasierte PSA-Prüfungen: markiert verfügbare UND ausgegebene PSA-Artikel als
    prüfpflichtig, wenn eine Monats-Prüfregel ihres Typs fällig ist."""
    db = SessionLocal()
    try:
        from . import models, inspection
        arts = db.query(models.Article).filter(
            models.Article.is_psa == True,                     # noqa: E712
            models.Article.needs_inspection == False,          # noqa: E712
            models.Article.status.in_(["verfuegbar", "ausgegeben"])).all()
        changed = False
        for a in arts:
            if inspection.flag_if_due(db, a, just_returned=False):
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _run_maintenance_reminders():
    """Termin-/Wartungs-Erinnerungen: schickt je Prüfart konfigurierte Vor-Erinnerungen
    (X Tage vorher, mit Dringlichkeit) per Telegram, sobald ein Termin näher rückt.
    Merkt sich bereits verschickte Erinnerungen je Termin (kein Doppelversand)."""
    db = SessionLocal()
    try:
        from . import models, telegram
        now = dt.datetime.utcnow()
        rems_by_type = {}
        for r in db.query(models.MaintenanceReminder).all():
            rems_by_type.setdefault(r.type_id, []).append(r)
        if not rems_by_type:
            return
        ams = db.query(models.ArticleMaintenance).filter(
            models.ArticleMaintenance.active == True,              # noqa: E712
            models.ArticleMaintenance.due_date.isnot(None)).all()
        changed = False
        urgency_mark = {"low": "", "normal": "⏰ ", "high": "‼️ "}
        for am in ams:
            rems = rems_by_type.get(am.mtype_id, [])
            if not rems:
                continue
            done = set(str(x) for x in (am.reminded or []))
            fired = False
            for r in rems:
                key = str(r.days_before)
                if key in done:
                    continue
                trigger = am.due_date - dt.timedelta(days=r.days_before)
                if now >= trigger:
                    t = db.query(models.MaintenanceType).get(am.mtype_id)
                    a = db.query(models.Article).get(am.article_id)
                    if not a:
                        continue
                    overdue = am.due_date < now
                    when = am.due_date.strftime("%d.%m.%Y")
                    txt = (f"{urgency_mark.get(r.urgency, '⏰ ')}Termin fällig"
                           f"{' (ÜBERFÄLLIG)' if overdue else ''}: {a.artikelnummer} – "
                           f"{t.name if t else ''} am {when}.")
                    telegram.notify_event(db, "maintenance_due", txt)
                    done.add(key)
                    fired = True
            if fired:
                am.reminded = sorted(done, key=lambda x: -int(x))
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(_run_auto_backup_check, "interval", minutes=1, id="auto_backup_check", replace_existing=True)
        scheduler.add_job(_run_audit_purge, "interval", hours=6, id="audit_purge", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_inventory_schedules, "interval", minutes=30, id="inventory_schedules", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_inventory_reminders, "interval", minutes=30, id="inventory_reminders", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_low_stock_check, "interval", minutes=30, id="low_stock_check", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_inspection_time_check, "interval", hours=6, id="inspection_time_check", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.add_job(_run_maintenance_reminders, "interval", hours=6, id="maintenance_reminders", replace_existing=True, next_run_time=dt.datetime.now())
        scheduler.start()
