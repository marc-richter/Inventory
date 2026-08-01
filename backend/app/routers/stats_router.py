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
            group_org: bool = False, group_loc: bool = False, group_standort: bool = False,
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
    if group_standort:
        q = q.options(joinedload(models.Article.storage_node))
        # Standort-Baum einmal laden, damit location_path die Eltern-Kette ohne
        # N+1-Abfragen aus dem Identity-Map aufloest.
        db.query(models.StorageNode).all()
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
    if group_standort:
        columns.append("Standort")

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
        if group_standort:
            parts.append(a.location_path or "—")
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


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Kennzahlen fuer die Auswertung: Gesamtbestand, Verteilung nach Status,
    Top-Lagerorte, Verteilung nach Abteilung und die meistausgegebenen Artikel."""
    # Standort-Baum einmal laden (location_path ohne N+1)
    db.query(models.StorageNode).all()
    arts = db.query(models.Article).options(
        joinedload(models.Article.type), joinedload(models.Article.organization),
        joinedload(models.Article.storage_node),
    ).filter(models.Article.provisional == False).all()  # noqa: E712
    provisional = db.query(models.Article).filter(models.Article.provisional == True).count()  # noqa: E712

    defs = db.query(models.StatusDef).order_by(models.StatusDef.sort_order, models.StatusDef.id).all()
    labels = {d.key: d.label for d in defs}
    from collections import Counter
    by_status = Counter(a.status for a in arts)
    by_loc = Counter((a.location_path or "ohne Lagerort") for a in arts)
    by_org = Counter((a.organization.name if a.organization else "ohne Abteilung") for a in arts)

    status_rows = [{"key": d.key, "label": d.label, "count": by_status.get(d.key, 0)} for d in defs]
    for k, c in by_status.items():
        if k not in labels:
            status_rows.append({"key": k, "label": k, "count": c})

    # meistausgegebene Artikel (Anzahl Ausgabevorgaenge)
    top = db.query(models.IssueRecord.article_id, func.count(models.IssueRecord.id).label("n")) \
        .group_by(models.IssueRecord.article_id).order_by(func.count(models.IssueRecord.id).desc()).limit(10).all()
    amap = {a.id: a for a in arts}
    # Artikel, die evtl. nicht in arts sind (vorlaeufig o.ae.) nachladen
    missing_ids = [aid for aid, _ in top if aid not in amap]
    if missing_ids:
        for a in db.query(models.Article).options(joinedload(models.Article.type)).filter(models.Article.id.in_(missing_ids)).all():
            amap[a.id] = a
    top_issued = []
    for aid, n in top:
        a = amap.get(aid)
        if not a:
            continue
        top_issued.append({"id": a.id, "artikelnummer": a.artikelnummer,
                           "type": a.type.name if a.type else "", "size": a.size or "", "count": int(n)})

    def topn(counter, n=10):
        return [{"name": k, "count": v} for k, v in counter.most_common(n)]

    return {
        "total": len(arts), "provisional": provisional,
        "by_status": status_rows,
        "by_location": topn(by_loc), "by_org": topn(by_org),
        "top_issued": top_issued,
    }


@router.get("/data-quality")
def data_quality(db: Session = Depends(get_db), user=Depends(security.require_capability("articles"))):
    """Findet Auffaelligkeiten zum Aufraeumen: Artikel ohne Lagerort/Foto,
    vorlaeufige, verschollene sowie moegliche Doppelerfassungen."""
    db.query(models.StorageNode).all()
    LIMIT = 60

    def brief(a):
        return {"id": a.id, "artikelnummer": a.artikelnummer,
                "type": a.type.name if a.type else "", "size": a.size or ""}

    base = db.query(models.Article).options(joinedload(models.Article.type))

    # ohne Lagerort: weder Knoten, noch Stammdaten-Lagerort, noch Freitext-Ebenen
    no_loc_q = base.filter(
        models.Article.provisional == False,          # noqa: E712
        models.Article.storage_node_id.is_(None),
        models.Article.storage_location_id.is_(None),
        (models.Article.etage == ""), (models.Article.raum == ""),
        (models.Article.schrank == ""), (models.Article.fach == ""),
    )
    # ohne Foto
    no_photo_q = base.filter(models.Article.provisional == False,  # noqa: E712
                             ~models.Article.images.any())
    prov_q = base.filter(models.Article.provisional == True)       # noqa: E712
    missing_q = base.filter(models.Article.status == "verschollen")

    # moegliche Doppelerfassungen: identische Merkmale + gleicher Standort-Knoten
    dup_rows = db.query(
        models.Article.type_id, models.Article.size, models.Article.model,
        models.Article.properties, models.Article.storage_node_id,
        func.count(models.Article.id).label("n"),
    ).filter(models.Article.provisional == False).group_by(  # noqa: E712
        models.Article.type_id, models.Article.size, models.Article.model,
        models.Article.properties, models.Article.storage_node_id,
    ).having(func.count(models.Article.id) > 1).order_by(func.count(models.Article.id).desc()).limit(30).all()
    type_names = {t.id: t.name for t in db.query(models.ArticleType).all()}
    duplicates = []
    for type_id, size, model, props, node_id, n in dup_rows:
        parts = [type_names.get(type_id, "?")]
        if size:
            parts.append(size)
        if model:
            parts.append(model)
        ids = [aid for (aid,) in db.query(models.Article.id).filter(
            models.Article.type_id == type_id, models.Article.size == size,
            models.Article.model == model, models.Article.properties == props,
            models.Article.storage_node_id.is_(node_id) if node_id is None else models.Article.storage_node_id == node_id,
            models.Article.provisional == False,  # noqa: E712
        ).limit(20).all()]
        duplicates.append({"label": " · ".join(parts), "count": int(n), "ids": ids})

    def pack(q):
        return {"count": q.count(),
                "items": [brief(a) for a in q.order_by(models.Article.artikelnummer).limit(LIMIT).all()]}

    return {
        "no_location": pack(no_loc_q),
        "no_photo": pack(no_photo_q),
        "provisional": pack(prov_q),
        "missing": pack(missing_q),
        "duplicates": duplicates,
    }


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
