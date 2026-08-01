import datetime as dt

from sqlalchemy.orm import Session
from . import models


def purge_old(db: Session, retention_days: int) -> int:
    """Loescht Pruefprotokoll-Eintraege, die aelter als retention_days sind (DSGVO
    Speicherbegrenzung). retention_days <= 0 => keine Loeschung. Gibt Anzahl zurueck."""
    if not retention_days or retention_days <= 0:
        return 0
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=retention_days)
    n = db.query(models.AuditLog).filter(models.AuditLog.timestamp < cutoff).delete(synchronize_session=False)
    db.commit()
    return n


def log_action(db: Session, user, action: str, entity_type: str = "", entity_id: int = None, details: dict = None):
    entry = models.AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(entry)
    db.commit()
