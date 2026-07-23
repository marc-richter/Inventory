from sqlalchemy.orm import Session
from . import models


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
