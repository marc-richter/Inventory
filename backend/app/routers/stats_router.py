import datetime as dt
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/stats", tags=["stats"])

ONLINE_WINDOW_MINUTES = 5


# --------------------------- Zugriff / Zustaendigkeit ------------------------

def _is_admin(user):
    return "admin" in (user.roles or [])


def material_scopes(db, user):
    """Liste (organization_id, category_id) der Materialverwalter-Zustaendigkeiten
    eines Nutzers. Ein None-Wert bedeutet jeweils "alle". Leere Liste = keine.
    Eine Zustaendigkeit fuer eine Oberkategorie deckt auch deren Unterkategorien ab."""
    rows = db.query(models.MaterialManager).filter(models.MaterialManager.user_id == user.id).all()
    # Kind-Kategorien je Oberkategorie (eine Ebene).
    children = {}
    for cid, pid in db.query(models.Category.id, models.Category.parent_id).filter(
            models.Category.parent_id.isnot(None)).all():
        children.setdefault(pid, []).append(cid)
    out = []
    for r in rows:
        out.append((r.organization_id, r.category_id))
        if r.category_id is not None:
            for child in children.get(r.category_id, []):
                out.append((r.organization_id, child))
    return out


def can_view_analytics(db, user):
    return _is_admin(user) or bool(material_scopes(db, user))


def _scope_match(org_id, cat_id, scopes):
    for org, cat in scopes:
        if (org is None or org_id == org) and (cat is None or cat_id == cat):
            return True
    return False


def _min_stock_status(db, articles, allowed_cats=None):
    """Bewertet alle Mindestbestand-Regeln gegen die (ggf. bereits gefilterte)
    Artikelliste. Liefert je Regel den verfuegbaren Bestand im jeweiligen Geltungs-
    bereich (Gesamt oder Lagerplatz-Teilbaum) und ob die Schwelle unterschritten ist."""
    from .inventory import _children_map, _subtree_ids, _node_path
    rules = db.query(models.MinStockRule).filter(models.MinStockRule.min_stock > 0).all()
    if not rules:
        return []
    types = {t.id: t for t in db.query(models.ArticleType).all()}
    nodes = {n.id: n for n in db.query(models.StorageNode).all()}
    children = _children_map(db)
    avail = [a for a in articles if a.status == "verfuegbar"]
    subtrees = {}
    out = []
    for r in rules:
        t = types.get(r.type_id)
        if allowed_cats is not None and (t.category_id if t else None) not in allowed_cats:
            continue
        tree = None
        if r.node_id:
            tree = subtrees.get(r.node_id)
            if tree is None:
                tree = _subtree_ids([r.node_id], children)
                subtrees[r.node_id] = tree
        cnt = 0
        for a in avail:
            if a.type_id != r.type_id:
                continue
            if r.size and (a.size or "").strip() != r.size:
                continue
            if tree is not None and a.storage_node_id not in tree:
                continue
            cnt += 1
        out.append({
            "rule": r, "type": t.name if t else "?", "size": r.size or "",
            "node_path": _node_path(nodes[r.node_id]) if (r.node_id and r.node_id in nodes) else "",
            "available": cnt, "min_stock": r.min_stock, "breached": cnt < r.min_stock,
        })
    return out


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
    """Kennzahlen fuer die Auswertung. Zugriff nur fuer Administratoren und
    Materialverwalter; letztere sehen ausschliesslich ihre Abteilung(en) und
    Materialklasse(n)."""
    from fastapi import HTTPException
    if not can_view_analytics(db, user):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für die Auswertung")
    scopes = None if _is_admin(user) else material_scopes(db, user)
    allowed_cats = None
    if scopes is not None:
        cats = {cat for _org, cat in scopes}
        allowed_cats = None if None in cats else cats   # None => alle Klassen

    # Standort-Baum einmal laden (location_path ohne N+1)
    db.query(models.StorageNode).all()
    arts = db.query(models.Article).options(
        joinedload(models.Article.type), joinedload(models.Article.organization),
        joinedload(models.Article.storage_node),
    ).filter(models.Article.provisional == False).all()  # noqa: E712
    prov = db.query(models.Article.id, models.Article.organization_id, models.Article.category_id) \
        .filter(models.Article.provisional == True).all()  # noqa: E712
    if scopes is not None:
        arts = [a for a in arts if _scope_match(a.organization_id, a.category_id, scopes)]
        provisional = sum(1 for _i, o, c in prov if _scope_match(o, c, scopes))
    else:
        provisional = len(prov)
    scoped_ids = {a.id for a in arts}

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
    top_q = db.query(models.IssueRecord.article_id, func.count(models.IssueRecord.id).label("n"))
    if scopes is not None:
        top_q = top_q.filter(models.IssueRecord.article_id.in_(scoped_ids or [-1]))
    top = top_q.group_by(models.IssueRecord.article_id).order_by(func.count(models.IssueRecord.id).desc()).limit(10).all()
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

    now = dt.datetime.utcnow()

    # --- Monatsaktivitaet (letzte 12 Monate): Zugaenge / Ausgaben / Ruecknahmen ---
    def month_key(d):
        return f"{d.year:04d}-{d.month:02d}"
    months = []
    y, m = now.year, now.month
    for _ in range(12):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months = list(reversed(months))
    add_c = Counter(month_key(a.first_entry_date) for a in arts if a.first_entry_date)
    since = now - dt.timedelta(days=400)
    iss_q = db.query(models.IssueRecord.issue_date, models.IssueRecord.return_date,
                     models.IssueRecord.article_id).filter(models.IssueRecord.issue_date >= since)
    if scopes is not None:
        iss_q = iss_q.filter(models.IssueRecord.article_id.in_(scoped_ids or [-1]))
    iss = iss_q.all()
    issue_c = Counter(month_key(i) for i, _r, _a in iss if i)
    return_c = Counter(month_key(r) for _i, r, _a in iss if r)
    monthly = [{"month": mo, "additions": add_c.get(mo, 0),
                "issues": issue_c.get(mo, 0), "returns": return_c.get(mo, 0)} for mo in months]

    # --- Auslastung/Umschlag je Typ (Top nach Gesamtzahl) ---
    per_type = {}
    for a in arts:
        name = a.type.name if a.type else "—"
        d = per_type.setdefault(name, {"type": name, "available": 0, "issued": 0, "total": 0})
        d["total"] += 1
        if a.status == "verfuegbar":
            d["available"] += 1
        elif a.status == "ausgegeben":
            d["issued"] += 1
    utilization = sorted(per_type.values(), key=lambda x: -x["total"])[:12]

    # --- Ueberfaellige Rueckgaben (vereinbartes Rueckdatum ueberschritten) ---
    overdue_q = db.query(models.IssueRecord).options(
        joinedload(models.IssueRecord.article), joinedload(models.IssueRecord.person)).filter(
        models.IssueRecord.return_date.is_(None),
        models.IssueRecord.expected_return_date.isnot(None),
        models.IssueRecord.expected_return_date < now,
    )
    if scopes is not None:
        overdue_q = overdue_q.filter(models.IssueRecord.article_id.in_(scoped_ids or [-1]))
    overdue_q = overdue_q.order_by(models.IssueRecord.expected_return_date).limit(25).all()
    overdue = []
    for r in overdue_q:
        a = r.article
        who = (f"{r.person.first_name} {r.person.last_name}".strip() if r.person
               else (r.recipient_name_freetext or "unbekannt"))
        overdue.append({
            "article_id": a.id if a else None,
            "artikelnummer": a.artikelnummer if a else "?",
            "who": who,
            "due": r.expected_return_date.strftime("%d.%m.%Y"),
            "days": (now.date() - r.expected_return_date.date()).days,
        })

    # --- Groessen-Matrix je Typ (verfuegbare Stueck je Groesse) ---
    size_map = {}
    for a in arts:
        if a.status != "verfuegbar" or not (a.size or "").strip():
            continue
        name = a.type.name if a.type else "—"
        size_map.setdefault(name, Counter())[a.size.strip()] += 1
    size_matrix = []
    for name, c in size_map.items():
        if len(c) < 2:
            continue
        size_matrix.append({"type": name,
                            "sizes": [{"size": s, "count": n} for s, n in sorted(c.items(), key=lambda x: x[0])]})
    size_matrix = sorted(size_matrix, key=lambda x: -sum(s["count"] for s in x["sizes"]))[:12]

    # --- Mindestbestand-Unterschreitungen (Regeln: Typ+Groesse, optional Lagerplatz) ---
    low_stock = []
    for s in _min_stock_status(db, arts, allowed_cats):
        if s["breached"]:
            low_stock.append({"type": s["type"], "size": s["size"], "node_path": s["node_path"],
                              "available": s["available"], "min_stock": s["min_stock"]})
    low_stock.sort(key=lambda x: x["available"] - x["min_stock"])

    # --- Fundquote je Inventur (aus dem Bericht-Archiv, neueste zuerst) ---
    find_rate = []
    for r in db.query(models.InventoryReportArchive).order_by(
            models.InventoryReportArchive.created_at.desc()).limit(12).all():
        st = r.stats or {}
        exp = st.get("expected_count") or 0
        fnd = st.get("found_count") or 0
        find_rate.append({"name": r.campaign_name,
                          "date": r.created_at.strftime("%d.%m.%Y") if r.created_at else "",
                          "pct": int(round(100 * fnd / exp)) if exp else 0,
                          "found": fnd, "expected": exp, "open": st.get("open_count") or 0})

    return {
        "total": len(arts), "provisional": provisional,
        "by_status": status_rows,
        "by_location": topn(by_loc), "by_org": topn(by_org),
        "top_issued": top_issued,
        "monthly": monthly,
        "utilization": utilization,
        "overdue": overdue,
        "size_matrix": size_matrix,
        "low_stock": low_stock,
        "find_rate": find_rate,
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


@router.get("/access")
def analytics_access(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Ob der Nutzer die Auswertung sehen darf (Admin oder Materialverwalter)."""
    return {"can_view": can_view_analytics(db, user), "is_admin": _is_admin(user)}


# --------------------------- Materialverwalter-Zustaendigkeiten --------------

def _mm_out(m):
    return schemas.MaterialManagerOut(
        id=m.id, user_id=m.user_id,
        user_name=(m.user.full_name or m.user.username) if m.user else None,
        organization_id=m.organization_id,
        organization_name=m.organization.name if m.organization else None,
        category_id=m.category_id,
        category_name=m.category.name if m.category else None,
    )


@router.get("/material-managers", response_model=list[schemas.MaterialManagerOut])
def list_material_managers(db: Session = Depends(get_db),
                           user=Depends(security.require_roles("admin"))):
    return [_mm_out(m) for m in db.query(models.MaterialManager).all()]


@router.post("/material-managers", response_model=schemas.MaterialManagerOut)
def add_material_manager(payload: schemas.MaterialManagerCreate, db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin"))):
    if not db.query(models.User).get(payload.user_id):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    existing = db.query(models.MaterialManager).filter(
        models.MaterialManager.user_id == payload.user_id,
        models.MaterialManager.organization_id.is_(payload.organization_id) if payload.organization_id is None else models.MaterialManager.organization_id == payload.organization_id,
        models.MaterialManager.category_id.is_(payload.category_id) if payload.category_id is None else models.MaterialManager.category_id == payload.category_id,
    ).first()
    if existing:
        return _mm_out(existing)
    m = models.MaterialManager(user_id=payload.user_id, organization_id=payload.organization_id,
                               category_id=payload.category_id)
    db.add(m)
    db.commit()
    db.refresh(m)
    log_action(db, user, "add_material_manager", "user", payload.user_id,
               {"org": payload.organization_id, "cat": payload.category_id})
    return _mm_out(m)


@router.delete("/material-managers/{mm_id}")
def delete_material_manager(mm_id: int, db: Session = Depends(get_db),
                            user=Depends(security.require_roles("admin"))):
    m = db.query(models.MaterialManager).get(mm_id)
    if m:
        db.delete(m)
        db.commit()
        log_action(db, user, "delete_material_manager", "material_manager", mm_id)
    return {"ok": True}


# --------------------------- Mindestbestand-Regeln --------------------------

def _rule_out(db, r, type_cat=None, node_map=None):
    from .inventory import _node_path
    t = r.type
    path = ""
    if r.node_id and node_map is not None:
        n = node_map.get(r.node_id)
        path = _node_path(n) if n else ""
    return schemas.MinStockRuleOut(
        id=r.id, type_id=r.type_id, type_name=t.name if t else None,
        category_id=t.category_id if t else None, size=r.size or "",
        node_id=r.node_id, node_path=path, min_stock=r.min_stock)


@router.get("/min-stock-rules", response_model=list[schemas.MinStockRuleOut])
def list_min_stock_rules(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    node_map = {n.id: n for n in db.query(models.StorageNode).all()}
    rules = db.query(models.MinStockRule).all()
    return [_rule_out(db, r, node_map=node_map) for r in rules]


@router.post("/min-stock-rules", response_model=schemas.MinStockRuleOut)
def upsert_min_stock_rule(payload: schemas.MinStockRuleCreate, db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin", "verwalter"))):
    if not db.query(models.ArticleType).get(payload.type_id):
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    size = (payload.size or "").strip()
    r = db.query(models.MinStockRule).filter(
        models.MinStockRule.type_id == payload.type_id,
        models.MinStockRule.size == size,
        models.MinStockRule.node_id.is_(None) if payload.node_id is None else models.MinStockRule.node_id == payload.node_id,
    ).first()
    val = max(0, int(payload.min_stock or 0))
    if r:
        r.min_stock = val
        r.notified = False
    else:
        r = models.MinStockRule(type_id=payload.type_id, size=size, node_id=payload.node_id, min_stock=val)
        db.add(r)
    db.commit()
    db.refresh(r)
    node_map = {n.id: n for n in db.query(models.StorageNode).all()}
    log_action(db, user, "set_min_stock_rule", "article_type", payload.type_id,
               {"size": size, "node_id": payload.node_id, "min_stock": val})
    return _rule_out(db, r, node_map=node_map)


@router.delete("/min-stock-rules/{rule_id}")
def delete_min_stock_rule(rule_id: int, db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin", "verwalter"))):
    r = db.query(models.MinStockRule).get(rule_id)
    if r:
        db.delete(r)
        db.commit()
        log_action(db, user, "delete_min_stock_rule", "min_stock_rule", rule_id)
    return {"ok": True}


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
