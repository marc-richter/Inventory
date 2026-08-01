import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action
from ..permissions import user_capabilities

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# --------------------------- Hilfen -----------------------------------------

def _has_inventory_cap(db: Session, user) -> bool:
    return "inventory" in user_capabilities(db, user)


def _participant(db: Session, campaign_id: int, user_id: int):
    return db.query(models.InventoryParticipant).filter(
        models.InventoryParticipant.campaign_id == campaign_id,
        models.InventoryParticipant.user_id == user_id,
    ).first()


def _can_manage(db: Session, user, c: models.InventoryCampaign) -> bool:
    if _has_inventory_cap(db, user):
        return True
    p = _participant(db, c.id, user.id)
    return bool(p and p.role == "lead")


def _can_participate(db: Session, user, c: models.InventoryCampaign) -> bool:
    return _has_inventory_cap(db, user) or _participant(db, c.id, user.id) is not None


def _get_campaign(db: Session, campaign_id: int) -> models.InventoryCampaign:
    c = db.query(models.InventoryCampaign).get(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Inventur nicht gefunden")
    return c


def _ignore_set(c: models.InventoryCampaign) -> set:
    return {s.strip() for s in (c.ignore_status or "").split(",") if s.strip()}


def _children_map(db: Session):
    """parent_id -> Liste Kind-IDs; einmalig aus einem Query aufgebaut."""
    children = {}
    for nid, pid in db.query(models.StorageNode.id, models.StorageNode.parent_id).all():
        children.setdefault(pid, []).append(nid)
    return children


def _subtree_ids(root_ids, children):
    out, stack = set(), list(root_ids)
    while stack:
        nid = stack.pop()
        if nid in out:
            continue
        out.add(nid)
        stack.extend(children.get(nid, []))
    return out


def _descendant_node_ids(db: Session, root_ids):
    return _subtree_ids(root_ids, _children_map(db))


def _scope_query(db: Session, c: models.InventoryCampaign):
    """Alle Artikel im Geltungsbereich der Kampagne (ohne vorlaeufige)."""
    q = db.query(models.Article).filter(models.Article.provisional == False)  # noqa: E712
    if c.scope_type == "nodes":
        roots = [s.node_id for s in c.scope_nodes]
        ids = _descendant_node_ids(db, roots) if roots else set()
        q = q.filter(models.Article.storage_node_id.in_(list(ids) if ids else [-1]))
    elif c.scope_type == "categories":
        cats = [s.category_id for s in c.scope_categories]
        q = q.filter(models.Article.category_id.in_(cats if cats else [-1]))
    return q


def _found_set(c: models.InventoryCampaign) -> set:
    return {f.article_id for f in c.found}


def _node_path(node) -> str:
    parts, seen = [], set()
    n = node
    while n is not None and n.id not in seen:
        seen.add(n.id)
        parts.append(n.name)
        n = n.parent
    return " › ".join(reversed(parts))


def _add_months(d: dt.datetime, months: int) -> dt.datetime:
    """Monatsarithmetik ohne externe Bibliothek (dateutil nicht verfuegbar)."""
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    # Tag auf gueltigen Monatsletzten begrenzen
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def _advance(d: dt.datetime, interval: int, unit: str) -> dt.datetime:
    interval = max(1, int(interval or 1))
    if unit == "day":
        return d + dt.timedelta(days=interval)
    if unit == "week":
        return d + dt.timedelta(weeks=interval)
    return _add_months(d, interval)


def _progress(db: Session, c: models.InventoryCampaign) -> dict:
    rows = _scope_query(db, c).with_entities(models.Article.id, models.Article.status).all()
    found = _found_set(c)
    ignore = _ignore_set(c)
    expected = len(rows)
    found_n = sum(1 for i, _ in rows if i in found)
    open_n = sum(1 for i, st in rows if i not in found and st not in ignore)
    ignored_n = sum(1 for i, st in rows if i not in found and st in ignore)
    return {"expected_count": expected, "found_count": found_n,
            "open_count": open_n, "ignored_count": ignored_n}


def _user_name(u) -> str:
    if not u:
        return None
    return u.full_name or u.username


def _campaign_out(db, c, user=None, with_progress=False) -> schemas.InventoryCampaignOut:
    out = schemas.InventoryCampaignOut(
        id=c.id, name=c.name, scope_type=c.scope_type, status=c.status,
        ignore_status=c.ignore_status or "",
        planned_start=c.planned_start, planned_end=c.planned_end,
        started_at=c.started_at, ended_at=c.ended_at, notes=c.notes or "",
        created_by_id=c.created_by_id, created_by_name=_user_name(c.created_by),
        scope_node_ids=[s.node_id for s in c.scope_nodes],
        scope_category_ids=[s.category_id for s in c.scope_categories],
        participants=[schemas.InventoryParticipantOut(
            id=p.id, user_id=p.user_id, role=p.role, user_name=_user_name(p.user)
        ) for p in c.participants],
    )
    if user is not None:
        out.can_manage = _can_manage(db, user, c)
    if with_progress:
        for k, v in _progress(db, c).items():
            setattr(out, k, v)
    return out


# --------------------------- Kampagnen ---------------------------------------

@router.get("/campaigns", response_model=list[schemas.InventoryCampaignOut])
def list_campaigns(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    manage = _has_inventory_cap(db, user)
    campaigns = db.query(models.InventoryCampaign).order_by(
        models.InventoryCampaign.created_at.desc()).all()
    result = []
    for c in campaigns:
        if manage or _participant(db, c.id, user.id):
            result.append(_campaign_out(db, c, user=user, with_progress=True))
    return result


@router.post("/campaigns", response_model=schemas.InventoryCampaignOut)
def create_campaign(payload: schemas.InventoryCampaignCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    c = models.InventoryCampaign(
        name=(payload.name or "").strip() or "Inventur",
        scope_type=payload.scope_type if payload.scope_type in ("full", "nodes", "categories") else "full",
        ignore_status=",".join(s.strip() for s in (payload.ignore_status or []) if s.strip()),
        planned_start=payload.planned_start, planned_end=payload.planned_end,
        notes=payload.notes or "", status="planned", created_by_id=user.id,
    )
    db.add(c)
    db.flush()
    for nid in (payload.scope_node_ids or []):
        db.add(models.InventoryScopeNode(campaign_id=c.id, node_id=nid))
    for cid in (payload.scope_category_ids or []):
        db.add(models.InventoryScopeCategory(campaign_id=c.id, category_id=cid))
    # Ersteller automatisch als Leiter aufnehmen.
    db.add(models.InventoryParticipant(campaign_id=c.id, user_id=user.id, role="lead"))
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_create", "inventory_campaign", c.id, {"name": c.name})
    return _campaign_out(db, c, user=user, with_progress=True)


@router.get("/campaigns/{campaign_id}", response_model=schemas.InventoryCampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    return _campaign_out(db, c, user=user, with_progress=True)


@router.put("/campaigns/{campaign_id}", response_model=schemas.InventoryCampaignOut)
def update_campaign(campaign_id: int, payload: schemas.InventoryCampaignUpdate,
                    db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen das ändern")
    data = payload.dict(exclude_unset=True)
    if data.get("name"):
        c.name = data["name"].strip()
    if data.get("scope_type") in ("full", "nodes", "categories"):
        c.scope_type = data["scope_type"]
    if "ignore_status" in data and data["ignore_status"] is not None:
        c.ignore_status = ",".join(s.strip() for s in data["ignore_status"] if s.strip())
    for f in ("planned_start", "planned_end", "notes"):
        if f in data:
            setattr(c, f, data[f])
    if "scope_node_ids" in data and data["scope_node_ids"] is not None:
        c.scope_nodes.clear()
        db.flush()
        for nid in data["scope_node_ids"]:
            db.add(models.InventoryScopeNode(campaign_id=c.id, node_id=nid))
    if "scope_category_ids" in data and data["scope_category_ids"] is not None:
        c.scope_categories.clear()
        db.flush()
        for cid in data["scope_category_ids"]:
            db.add(models.InventoryScopeCategory(campaign_id=c.id, category_id=cid))
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_update", "inventory_campaign", c.id)
    return _campaign_out(db, c, user=user, with_progress=True)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen das löschen")
    db.delete(c)
    db.commit()
    log_action(db, user, "inventory_delete", "inventory_campaign", campaign_id)
    return {"ok": True}


_TRANSITIONS = {
    "start": ("running", {"planned", "paused"}),
    "pause": ("paused", {"running"}),
    "resume": ("running", {"paused"}),
    "cancel": ("cancelled", {"planned", "running", "paused"}),
    "finish": ("done", {"running", "paused"}),
}


@router.post("/campaigns/{campaign_id}/status", response_model=schemas.InventoryCampaignOut)
def set_status(campaign_id: int, action: str, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen das steuern")
    if action not in _TRANSITIONS:
        raise HTTPException(status_code=400, detail="Unbekannte Aktion")
    new_status, allowed = _TRANSITIONS[action]
    if c.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Aktion '{action}' aus Status '{c.status}' nicht möglich")
    c.status = new_status
    if action == "start" and not c.started_at:
        c.started_at = dt.datetime.utcnow()
    if action in ("cancel", "finish"):
        c.ended_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_status", "inventory_campaign", c.id, {"action": action, "status": new_status})
    from .. import telegram
    if action == "start":
        telegram.notify_event(db, "inventory", f"📋 Inventur „{c.name}“ wurde gestartet.")
    elif action == "finish":
        prog = _progress(db, c)
        telegram.notify_event(db, "inventory",
                              f"✅ Inventur „{c.name}“ abgeschlossen. Offen/fehlend: {prog['open_count']}.")
    return _campaign_out(db, c, user=user, with_progress=True)


# --------------------------- Teilnehmer --------------------------------------

@router.post("/campaigns/{campaign_id}/participants", response_model=schemas.InventoryCampaignOut)
def add_participant(campaign_id: int, payload: schemas.InventoryParticipantAdd,
                    db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Teilnehmer freischalten")
    target = db.query(models.User).get(payload.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    role = payload.role if payload.role in ("helper", "lead") else "helper"
    existing = _participant(db, c.id, payload.user_id)
    if existing:
        existing.role = role
    else:
        db.add(models.InventoryParticipant(campaign_id=c.id, user_id=payload.user_id, role=role))
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_add_participant", "inventory_campaign", c.id,
               {"user_id": payload.user_id, "role": role})
    return _campaign_out(db, c, user=user, with_progress=True)


@router.delete("/campaigns/{campaign_id}/participants/{user_id}", response_model=schemas.InventoryCampaignOut)
def remove_participant(campaign_id: int, user_id: int, db: Session = Depends(get_db),
                       user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Teilnehmer entfernen")
    p = _participant(db, c.id, user_id)
    if p:
        db.delete(p)
        db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_remove_participant", "inventory_campaign", c.id, {"user_id": user_id})
    return _campaign_out(db, c, user=user, with_progress=True)


# --------------------------- Scannen / Offen ---------------------------------

@router.post("/campaigns/{campaign_id}/scan")
def scan(campaign_id: int, payload: schemas.InventoryScanRequest, db: Session = Depends(get_db),
         user=Depends(security.get_current_user)):
    """Gescannte Artikel als gefunden verbuchen und (optional) einem Standort-Knoten
    zuordnen. Zulaessig fuer Teilnehmer der laufenden Kampagne oder Inventur-Rechte."""
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    if c.status != "running":
        raise HTTPException(status_code=400, detail="Die Inventur läuft nicht (bitte zuerst starten).")
    if not payload.article_ids:
        return {"ok": True, "updated": 0, "found_total": len(_found_set(c))}
    arts = db.query(models.Article).filter(models.Article.id.in_(payload.article_ids)).all()
    already = _found_set(c)
    now = dt.datetime.utcnow()
    for a in arts:
        if payload.storage_node_id is not None:
            a.storage_node_id = payload.storage_node_id
        if a.id not in already:
            db.add(models.InventoryFound(campaign_id=c.id, article_id=a.id,
                                         node_id=payload.storage_node_id, found_at=now,
                                         found_by_id=user.id))
            already.add(a.id)
    db.commit()
    log_action(db, user, "inventory_scan", "inventory_campaign", c.id,
               {"count": len(arts), "node_id": payload.storage_node_id})
    db.refresh(c)
    return {"ok": True, "updated": len(arts), "found_total": len(_found_set(c))}


@router.get("/campaigns/{campaign_id}/open")
def open_list(campaign_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Noch nicht erfasste Artikel im Geltungsbereich, getrennt in `missing`
    (relevant) und `ignored` (Status wird ignoriert)."""
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    found = _found_set(c)
    ignore = _ignore_set(c)
    arts = _scope_query(db, c).order_by(models.Article.artikelnummer).all()
    missing, ignored = [], []
    for a in arts:
        if a.id in found:
            continue
        (ignored if a.status in ignore else missing).append(schemas.ArticleOut.model_validate(a))
    return {"missing": missing, "ignored": ignored, "ignore_status": sorted(ignore)}


def _campaign_report_data(db: Session, c: models.InventoryCampaign):
    """Sammelt die Daten fuer den Abschlussbericht: Kopfdaten, Kennzahlen sowie die
    Listen gefunden / fehlend / ignoriert (jeweils als schlichte dicts)."""
    from .articles import _warm_node_cache
    _warm_node_cache(db)
    labels = {d.key: d.label for d in db.query(models.StatusDef).all()}
    found_ids = _found_set(c)
    found_node = {f.article_id: f.node_id for f in c.found}
    ignore = _ignore_set(c)
    node_by_id = {n.id: n for n in db.query(models.StorageNode).all()}

    def npath(nid):
        n = node_by_id.get(nid)
        return _node_path(n) if n else ""

    found, missing, ignored = [], [], []
    for a in _scope_query(db, c).order_by(models.Article.artikelnummer).all():
        row = {"artikelnummer": a.artikelnummer, "typ": a.type.name if a.type else "",
               "size": a.size or "", "status": labels.get(a.status, a.status),
               "location": a.location_path or ""}
        if a.id in found_ids:
            row["found_at"] = npath(found_node.get(a.id)) or (a.location_path or "")
            found.append(row)
        elif a.status in ignore:
            ignored.append(row)
        else:
            missing.append(row)

    stats = _progress(db, c)
    exp = stats.get("expected_count") or 0
    pct = int(round(100 * (stats.get("found_count") or 0) / exp)) if exp else 0

    def fmt(d):
        return d.strftime("%d.%m.%Y") if d else "—"
    zeitraum = f"{fmt(c.started_at)} – {fmt(c.ended_at)}" if (c.started_at or c.ended_at) else "—"
    if c.scope_type == "nodes":
        scope = "Lagerorte: " + ", ".join(npath(s.node_id) for s in c.scope_nodes) or "Lagerorte"
    elif c.scope_type == "categories":
        cats = {cat.id: cat.name for cat in db.query(models.Category).all()}
        scope = "Klassen: " + ", ".join(cats.get(s.category_id, "?") for s in c.scope_categories)
    else:
        scope = "Gesamtbestand"
    meta = {
        "name": c.name, "zeitraum": zeitraum, "scope": scope,
        "created_by": _user_name(c.created_by) or "—",
        "participants": ", ".join(_user_name(p.user) for p in c.participants) or "—",
        "generated_at": dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "progress": f"{pct} %",
    }
    return meta, found, missing, ignored, stats


@router.get("/campaigns/{campaign_id}/report")
def campaign_report(campaign_id: int, format: str = "pdf", db: Session = Depends(get_db),
                    user=Depends(security.get_current_user)):
    """Abschlussbericht einer Inventur als PDF (Standard) oder CSV (`?format=csv`)."""
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    meta, found, missing, ignored, stats = _campaign_report_data(db, c)
    from .export import build_campaign_report_pdf, build_campaign_report_csv
    safe = "".join(ch if ch.isalnum() else "_" for ch in (c.name or "inventur"))[:40]
    if format == "csv":
        data = build_campaign_report_csv(meta, found, missing, ignored, stats)
        return Response(content=data, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="Inventurbericht_{safe}.csv"'})
    pdf = build_campaign_report_pdf(db, meta, found, missing, ignored, stats)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Inventurbericht_{safe}.pdf"'})


@router.get("/assignable-users")
def assignable_users(db: Session = Depends(get_db),
                     user=Depends(security.require_capability("inventory"))):
    """Schlanke Benutzerliste zur Auswahl von Inventur-Teilnehmern (auch fuer
    Verantwortliche ohne volle Benutzerverwaltung)."""
    return [{"id": u.id, "name": _user_name(u), "username": u.username}
            for u in db.query(models.User).filter(models.User.active == True)  # noqa: E712
            .order_by(models.User.username).all()]


# --------------------------- Gefuehrter Rundgang: Stationen ------------------

def _step_progress_map(db: Session, c: models.InventoryCampaign):
    """Je Station (Knoten) die Kennzahlen im zugehoerigen Teilbaum berechnen.
    Ein einziger Scan ueber die Artikel im Geltungsbereich, danach Zuordnung."""
    found = _found_set(c)
    ignore = _ignore_set(c)
    # Artikel im Scope mit ihrem aktuellen Knoten
    rows = _scope_query(db, c).with_entities(
        models.Article.id, models.Article.status, models.Article.storage_node_id).all()
    # je Station: Menge der Knoten-IDs im Teilbaum (Kind-Map nur EINMAL aufbauen)
    node_ids = [s.node_id for s in c.steps if s.node_id]
    children = _children_map(db)
    subtrees = {nid: _subtree_ids([nid], children) for nid in node_ids}
    out = {}
    for s in c.steps:
        if not s.node_id:
            out[s.id] = {"expected_count": None, "found_count": None, "open_count": None}
            continue
        tree = subtrees.get(s.node_id, {s.node_id})
        exp = fnd = opn = 0
        for aid, st, snid in rows:
            if snid in tree:
                exp += 1
                if aid in found:
                    fnd += 1
                elif st not in ignore:
                    opn += 1
        out[s.id] = {"expected_count": exp, "found_count": fnd, "open_count": opn}
    return out


def _step_out(db, c, s, progress) -> schemas.InventoryStepOut:
    p = progress.get(s.id, {})
    return schemas.InventoryStepOut(
        id=s.id, position=s.position, node_id=s.node_id, label=s.label or "",
        status=s.status, note=s.note or "",
        node_path=_node_path(s.node) if s.node_id else None,
        done_by_name=_user_name(s.done_by), done_at=s.done_at,
        expected_count=p.get("expected_count"), found_count=p.get("found_count"),
        open_count=p.get("open_count"),
    )


@router.get("/campaigns/{campaign_id}/steps", response_model=list[schemas.InventoryStepOut])
def list_steps(campaign_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s, prog) for s in c.steps]


@router.post("/campaigns/{campaign_id}/steps", response_model=list[schemas.InventoryStepOut])
def add_step(campaign_id: int, payload: schemas.InventoryStepCreate,
             db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Stationen ändern")
    pos = (max([s.position for s in c.steps], default=-1)) + 1
    db.add(models.InventoryStep(campaign_id=c.id, position=pos,
                                node_id=payload.node_id, label=(payload.label or "").strip()))
    db.commit()
    db.refresh(c)
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s, prog) for s in c.steps]


@router.post("/campaigns/{campaign_id}/steps/generate", response_model=list[schemas.InventoryStepOut])
def generate_steps(campaign_id: int, payload: schemas.InventoryStepsGenerate,
                   db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Stationen aus einer Knotenliste (oder dem Geltungsbereich) erzeugen."""
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Stationen ändern")
    node_ids = list(payload.node_ids or [])
    if not node_ids:
        node_ids = [s.node_id for s in c.scope_nodes]
    # nach Pfad sortieren, damit ein sinnvoller Rundgang entsteht
    nodes = {n.id: n for n in db.query(models.StorageNode).filter(models.StorageNode.id.in_(node_ids)).all()} if node_ids else {}
    ordered = sorted([nid for nid in node_ids if nid in nodes],
                     key=lambda nid: _node_path(nodes[nid]).lower())
    if payload.replace:
        c.steps.clear()
        db.flush()
    base = (max([s.position for s in c.steps], default=-1)) + 1
    for i, nid in enumerate(ordered):
        db.add(models.InventoryStep(campaign_id=c.id, position=base + i, node_id=nid))
    db.commit()
    db.refresh(c)
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s, prog) for s in c.steps]


@router.put("/campaigns/{campaign_id}/steps/reorder", response_model=list[schemas.InventoryStepOut])
def reorder_steps(campaign_id: int, payload: schemas.InventoryStepReorder,
                  db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Stationen ändern")
    by_id = {s.id: s for s in c.steps}
    pos = 0
    for sid in payload.ordered_ids:
        s = by_id.get(sid)
        if s:
            s.position = pos
            pos += 1
    # nicht genannte ans Ende
    for s in c.steps:
        if s.id not in set(payload.ordered_ids):
            s.position = pos
            pos += 1
    db.commit()
    db.refresh(c)
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s, prog) for s in c.steps]


@router.post("/campaigns/{campaign_id}/steps/{step_id}/status", response_model=list[schemas.InventoryStepOut])
def set_step_status(campaign_id: int, step_id: int, payload: schemas.InventoryStepStatus,
                    db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_participate(db, user, c):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Inventur")
    s = next((x for x in c.steps if x.id == step_id), None)
    if not s:
        raise HTTPException(status_code=404, detail="Station nicht gefunden")
    if payload.status not in ("pending", "done", "skipped"):
        raise HTTPException(status_code=400, detail="Unbekannter Status")
    s.status = payload.status
    if payload.note is not None:
        s.note = payload.note
    if payload.status in ("done", "skipped"):
        s.done_at = dt.datetime.utcnow()
        s.done_by_id = user.id
    else:
        s.done_at = None
        s.done_by_id = None
    db.commit()
    db.refresh(c)
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s2, prog) for s2 in c.steps]


@router.delete("/campaigns/{campaign_id}/steps/{step_id}", response_model=list[schemas.InventoryStepOut])
def delete_step(campaign_id: int, step_id: int, db: Session = Depends(get_db),
                user=Depends(security.get_current_user)):
    c = _get_campaign(db, campaign_id)
    if not _can_manage(db, user, c):
        raise HTTPException(status_code=403, detail="Nur Inventur-Verantwortliche dürfen Stationen ändern")
    s = next((x for x in c.steps if x.id == step_id), None)
    if s:
        db.delete(s)
        db.commit()
        db.refresh(c)
    prog = _step_progress_map(db, c)
    return [_step_out(db, c, s2, prog) for s2 in c.steps]


# --------------------------- Vorlagen ----------------------------------------

def _template_out(t) -> schemas.InventoryTemplateOut:
    return schemas.InventoryTemplateOut(
        id=t.id, name=t.name, ignore_status=t.ignore_status or "", notes=t.notes or "",
        created_by_name=_user_name(t.created_by),
        steps=[schemas.InventoryTemplateStepOut(
            id=s.id, position=s.position, node_id=s.node_id, label=s.label or "",
            node_path=_node_path(s.node) if s.node_id else None) for s in t.steps],
    )


@router.get("/templates", response_model=list[schemas.InventoryTemplateOut])
def list_templates(db: Session = Depends(get_db),
                   user=Depends(security.require_capability("inventory"))):
    return [_template_out(t) for t in db.query(models.InventoryTemplate)
            .order_by(models.InventoryTemplate.name).all()]


@router.post("/templates", response_model=schemas.InventoryTemplateOut)
def create_template(payload: schemas.InventoryTemplateCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    t = models.InventoryTemplate(
        name=(payload.name or "").strip() or "Vorlage",
        ignore_status=",".join(s.strip() for s in (payload.ignore_status or []) if s.strip()),
        notes=payload.notes or "", created_by_id=user.id,
    )
    db.add(t)
    db.flush()
    for i, st in enumerate(payload.steps or []):
        db.add(models.InventoryTemplateStep(template_id=t.id, position=i,
                                            node_id=st.node_id, label=(st.label or "").strip()))
    db.commit()
    db.refresh(t)
    log_action(db, user, "inventory_template_create", "inventory_template", t.id, {"name": t.name})
    return _template_out(t)


@router.post("/templates/from-campaign/{campaign_id}", response_model=schemas.InventoryTemplateOut)
def template_from_campaign(campaign_id: int, name: str = "", db: Session = Depends(get_db),
                           user=Depends(security.require_capability("inventory"))):
    c = _get_campaign(db, campaign_id)
    t = models.InventoryTemplate(
        name=(name or c.name or "Vorlage").strip(),
        ignore_status=c.ignore_status or "", notes=c.notes or "", created_by_id=user.id)
    db.add(t)
    db.flush()
    for i, s in enumerate(c.steps):
        db.add(models.InventoryTemplateStep(template_id=t.id, position=i,
                                            node_id=s.node_id, label=s.label or ""))
    db.commit()
    db.refresh(t)
    log_action(db, user, "inventory_template_create", "inventory_template", t.id, {"from_campaign": c.id})
    return _template_out(t)


@router.put("/templates/{template_id}", response_model=schemas.InventoryTemplateOut)
def update_template(template_id: int, payload: schemas.InventoryTemplateUpdate,
                    db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    t = db.query(models.InventoryTemplate).get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name"):
        t.name = data["name"].strip()
    if "ignore_status" in data and data["ignore_status"] is not None:
        t.ignore_status = ",".join(s.strip() for s in data["ignore_status"] if s.strip())
    if "notes" in data and data["notes"] is not None:
        t.notes = data["notes"]
    if "steps" in data and data["steps"] is not None:
        t.steps.clear()
        db.flush()
        for i, st in enumerate(data["steps"]):
            db.add(models.InventoryTemplateStep(template_id=t.id, position=i,
                                                node_id=st.get("node_id"), label=(st.get("label") or "").strip()))
    db.commit()
    db.refresh(t)
    log_action(db, user, "inventory_template_update", "inventory_template", t.id)
    return _template_out(t)


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    t = db.query(models.InventoryTemplate).get(template_id)
    if t:
        db.delete(t)
        db.commit()
        log_action(db, user, "inventory_template_delete", "inventory_template", template_id)
    return {"ok": True}


# --------------------------- Kampagne aus Vorlage(n) -------------------------

def create_campaign_from_templates(db: Session, name: str, template_ids, planned_start,
                                   created_by_id, ignore_override=None, participant_specs=None):
    """Erzeugt eine geplante Kampagne durch Zusammenfuehren einer oder mehrerer
    Vorlagen. Wiederverwendet vom Zeitplan-Scheduler und vom API-Endpunkt."""
    templates = []
    for tid in (template_ids or []):
        t = db.query(models.InventoryTemplate).get(tid)
        if t:
            templates.append(t)
    # Stationen zusammenfuehren: Knoten deduplizieren (erste Reihenfolge behalten),
    # freie Label-Stationen alle behalten.
    merged, seen_nodes = [], set()
    for t in templates:
        for s in t.steps:
            if s.node_id is not None:
                if s.node_id in seen_nodes:
                    continue
                seen_nodes.add(s.node_id)
            merged.append((s.node_id, s.label or ""))
    if ignore_override is not None:
        ignore_csv = ",".join(x.strip() for x in ignore_override if x.strip())
    else:
        parts = set()
        for t in templates:
            for x in (t.ignore_status or "").split(","):
                if x.strip():
                    parts.add(x.strip())
        ignore_csv = ",".join(sorted(parts))
    c = models.InventoryCampaign(
        name=(name or "Inventur").strip(), scope_type="nodes",
        ignore_status=ignore_csv, planned_start=planned_start,
        status="planned", created_by_id=created_by_id)
    db.add(c)
    db.flush()
    for nid in seen_nodes:
        db.add(models.InventoryScopeNode(campaign_id=c.id, node_id=nid))
    for i, (nid, label) in enumerate(merged):
        db.add(models.InventoryStep(campaign_id=c.id, position=i, node_id=nid, label=label))
    # Teilnehmer
    have = set()
    for uid, role in (participant_specs or []):
        if uid in have:
            continue
        have.add(uid)
        db.add(models.InventoryParticipant(campaign_id=c.id, user_id=uid,
                                           role=role if role in ("helper", "lead") else "helper"))
    if created_by_id and created_by_id not in have:
        db.add(models.InventoryParticipant(campaign_id=c.id, user_id=created_by_id, role="lead"))
    db.flush()
    return c


@router.post("/campaigns/from-templates", response_model=schemas.InventoryCampaignOut)
def campaign_from_templates(payload: schemas.InventoryCampaignFromTemplates,
                            db: Session = Depends(get_db),
                            user=Depends(security.require_capability("inventory"))):
    if not payload.template_ids:
        raise HTTPException(status_code=400, detail="Bitte mindestens eine Vorlage auswählen")
    specs = [(uid, "helper") for uid in (payload.participant_ids or [])]
    c = create_campaign_from_templates(db, payload.name, payload.template_ids,
                                       payload.planned_start, user.id, participant_specs=specs)
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_create", "inventory_campaign", c.id,
               {"name": c.name, "from_templates": payload.template_ids})
    return _campaign_out(db, c, user=user, with_progress=True)


# --------------------------- Zeitplaene (wiederkehrend) ----------------------

def _schedule_out(s) -> schemas.InventoryScheduleOut:
    return schemas.InventoryScheduleOut(
        id=s.id, name=s.name, active=s.active, interval=s.interval, unit=s.unit,
        next_run=s.next_run, last_run=s.last_run, ignore_status=s.ignore_status or "",
        notes=s.notes or "",
        template_ids=[t.template_id for t in s.templates],
        template_names=[t.template.name for t in s.templates if t.template],
        participant_ids=[p.user_id for p in s.schedule_participants],
    )


@router.get("/schedules", response_model=list[schemas.InventoryScheduleOut])
def list_schedules(db: Session = Depends(get_db),
                   user=Depends(security.require_capability("inventory"))):
    return [_schedule_out(s) for s in db.query(models.InventorySchedule)
            .order_by(models.InventorySchedule.name).all()]


@router.post("/schedules", response_model=schemas.InventoryScheduleOut)
def create_schedule(payload: schemas.InventoryScheduleCreate, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    unit = payload.unit if payload.unit in ("day", "week", "month") else "month"
    s = models.InventorySchedule(
        name=(payload.name or "").strip() or "Zeitplan", active=True,
        interval=max(1, int(payload.interval or 1)), unit=unit,
        next_run=payload.start_date or dt.datetime.utcnow(),
        ignore_status=",".join(x.strip() for x in (payload.ignore_status or []) if x.strip())
        if payload.ignore_status is not None else "ausgegeben,reparatur,ausgemustert",
        notes=payload.notes or "", created_by_id=user.id)
    db.add(s)
    db.flush()
    for i, tid in enumerate(payload.template_ids or []):
        db.add(models.InventoryScheduleTemplate(schedule_id=s.id, template_id=tid, position=i))
    for uid in (payload.participant_ids or []):
        db.add(models.InventoryScheduleParticipant(schedule_id=s.id, user_id=uid, role="helper"))
    db.commit()
    db.refresh(s)
    log_action(db, user, "inventory_schedule_create", "inventory_schedule", s.id, {"name": s.name})
    return _schedule_out(s)


@router.put("/schedules/{schedule_id}", response_model=schemas.InventoryScheduleOut)
def update_schedule(schedule_id: int, payload: schemas.InventoryScheduleUpdate,
                    db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    s = db.query(models.InventorySchedule).get(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Zeitplan nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name"):
        s.name = data["name"].strip()
    if "active" in data and data["active"] is not None:
        s.active = bool(data["active"])
    if data.get("interval"):
        s.interval = max(1, int(data["interval"]))
    if data.get("unit") in ("day", "week", "month"):
        s.unit = data["unit"]
    if "next_run" in data and data["next_run"] is not None:
        s.next_run = data["next_run"]
    if "notes" in data and data["notes"] is not None:
        s.notes = data["notes"]
    if "ignore_status" in data and data["ignore_status"] is not None:
        s.ignore_status = ",".join(x.strip() for x in data["ignore_status"] if x.strip())
    if "template_ids" in data and data["template_ids"] is not None:
        s.templates.clear()
        db.flush()
        for i, tid in enumerate(data["template_ids"]):
            db.add(models.InventoryScheduleTemplate(schedule_id=s.id, template_id=tid, position=i))
    if "participant_ids" in data and data["participant_ids"] is not None:
        s.schedule_participants.clear()
        db.flush()
        for uid in data["participant_ids"]:
            db.add(models.InventoryScheduleParticipant(schedule_id=s.id, user_id=uid, role="helper"))
    db.commit()
    db.refresh(s)
    log_action(db, user, "inventory_schedule_update", "inventory_schedule", s.id)
    return _schedule_out(s)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db),
                    user=Depends(security.require_capability("inventory"))):
    s = db.query(models.InventorySchedule).get(schedule_id)
    if s:
        db.delete(s)
        db.commit()
        log_action(db, user, "inventory_schedule_delete", "inventory_schedule", schedule_id)
    return {"ok": True}


@router.post("/schedules/{schedule_id}/run-now", response_model=schemas.InventoryCampaignOut)
def run_schedule_now(schedule_id: int, db: Session = Depends(get_db),
                     user=Depends(security.require_capability("inventory"))):
    s = db.query(models.InventorySchedule).get(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Zeitplan nicht gefunden")
    tids = [t.template_id for t in s.templates]
    specs = [(p.user_id, p.role) for p in s.schedule_participants]
    ignore = [x for x in (s.ignore_status or "").split(",") if x.strip()]
    c = create_campaign_from_templates(
        db, f"{s.name} {dt.date.today().isoformat()}", tids, dt.datetime.utcnow(),
        user.id, ignore_override=ignore, participant_specs=specs)
    s.last_run = dt.datetime.utcnow()
    db.commit()
    db.refresh(c)
    log_action(db, user, "inventory_schedule_run", "inventory_schedule", s.id, {"campaign_id": c.id})
    return _campaign_out(db, c, user=user, with_progress=True)


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Fuer die Glocke: laufende/geplante Inventuren, die den Nutzer betreffen."""
    manage = _has_inventory_cap(db, user)
    out = []
    for c in db.query(models.InventoryCampaign).filter(
            models.InventoryCampaign.status.in_(["planned", "running", "paused"])).all():
        is_part = _participant(db, c.id, user.id) is not None
        if not (manage or is_part):
            continue
        prog = _progress(db, c)
        out.append({"id": c.id, "name": c.name, "status": c.status,
                    "planned_start": c.planned_start.isoformat() if c.planned_start else None,
                    "open_count": prog["open_count"], "is_participant": is_part})
    return out
