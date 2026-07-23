import datetime as dt
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, security
from ..database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])

ONLINE_WINDOW_MINUTES = 5


@router.get("/overview")
def overview(category_id: Optional[List[int]] = Query(None),
             db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Mengenuebersicht: Gesamtzahl der Artikel sowie Anzahl je Status. Optional
    auf eine oder mehrere Artikelklassen (category_id) filterbar."""
    q = db.query(models.Article)
    if category_id:
        q = q.filter(models.Article.category_id.in_(category_id))
    total = q.count()
    rows = q.with_entities(models.Article.status, func.count(models.Article.id)) \
        .group_by(models.Article.status).all()
    per_status = {status: int(count) for status, count in rows}

    defs = db.query(models.StatusDef).order_by(models.StatusDef.sort_order, models.StatusDef.id).all()
    statuses = [{"key": d.key, "label": d.label, "count": per_status.get(d.key, 0)} for d in defs]
    known = {d.key for d in defs}
    for status, count in per_status.items():
        if status not in known:
            statuses.append({"key": status, "label": status, "count": count})
    return {"total": total, "statuses": statuses}


@router.get("/online-users")
def online_users(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    """Aktuell angemeldete/aktive Nutzer (Aktivitaet innerhalb des Zeitfensters),
    inkl. Namen - nur fuer Administratoren."""
    cutoff = dt.datetime.utcnow() - dt.timedelta(minutes=ONLINE_WINDOW_MINUTES)
    users = db.query(models.User).filter(
        models.User.last_seen.isnot(None), models.User.last_seen >= cutoff
    ).order_by(models.User.last_seen.desc()).all()
    return {
        "count": len(users),
        "window_minutes": ONLINE_WINDOW_MINUTES,
        "users": [
            {
                "id": u.id, "username": u.username, "full_name": u.full_name,
                "roles": u.roles or [],
                "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            }
            for u in users
        ],
    }


@router.get("/online-count")
def online_count(db: Session = Depends(get_db)):
    """Nur die Anzahl aktuell aktiver Nutzer - bewusst ohne Auth, damit die
    Verwaltungs-App (Uebersicht) diese Zahl im lokalen Netz anzeigen kann."""
    cutoff = dt.datetime.utcnow() - dt.timedelta(minutes=ONLINE_WINDOW_MINUTES)
    count = db.query(models.User).filter(
        models.User.last_seen.isnot(None), models.User.last_seen >= cutoff
    ).count()
    return {"count": count, "window_minutes": ONLINE_WINDOW_MINUTES}
