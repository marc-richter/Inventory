import datetime as dt
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, security
from ..database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])

ONLINE_WINDOW_MINUTES = 5


@router.get("/by-type")
def by_type(category_id: Optional[List[int]] = Query(None),
            group_model: bool = False, group_size: bool = False,
            group_org: bool = False, group_loc: bool = False,
            db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Uebersicht je Artikeltyp - wahlweise zusaetzlich nach Modell/Groesse/
    Abteilung/Lagerort gruppiert - mit Mengen je Status."""
    q = db.query(models.Article).options(
        joinedload(models.Article.type),
        joinedload(models.Article.organization),
        joinedload(models.Article.storage_location),
    )
    if category_id:
        q = q.filter(models.Article.category_id.in_(category_id))
    articles = q.all()

    defs = db.query(models.StatusDef).order_by(models.StatusDef.sort_order, models.StatusDef.id).all()
    status_labels = {d.key: d.label for d in defs}
    status_keys = [d.key for d in defs]

    columns = ["Typ"]
    if group_model:
        columns.append("Modell")
    if group_size:
        columns.append("Größe")
    if group_org:
        columns.append("Abteilung")
    if group_loc:
        columns.append("Lagerort")

    groups = {}
    for a in articles:
        parts = [a.type.name if a.type else "—"]
        if group_model:
            parts.append(a.model or "—")
        if group_size:
            parts.append(a.size or "—")
        if group_org:
            parts.append(a.organization.name if a.organization else "—")
        if group_loc:
            parts.append(a.storage_location.name if a.storage_location else "—")
        gk = tuple(parts)
        g = groups.setdefault(gk, {"counts": {}, "total": 0})
        g["counts"][a.status] = g["counts"].get(a.status, 0) + 1
        g["total"] += 1
        if a.status not in status_keys:
            status_keys.append(a.status)
            status_labels.setdefault(a.status, a.status)

    rows = [{"key": list(gk), "total": g["total"], "counts": g["counts"]}
            for gk, g in sorted(groups.items())]
    return {
        "columns": columns,
        "statuses": [{"key": k, "label": status_labels.get(k, k)} for k in status_keys],
        "rows": rows,
    }


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
