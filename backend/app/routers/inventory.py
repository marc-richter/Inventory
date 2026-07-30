import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
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


def _descendant_node_ids(db: Session, root_ids):
    children = {}
    for nid, pid in db.query(models.StorageNode.id, models.StorageNode.parent_id).all():
        children.setdefault(pid, []).append(nid)
    out, stack = set(), list(root_ids)
    while stack:
        nid = stack.pop()
        if nid in out:
            continue
        out.add(nid)
        stack.extend(children.get(nid, []))
    return out


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


@router.get("/assignable-users")
def assignable_users(db: Session = Depends(get_db),
                     user=Depends(security.require_capability("inventory"))):
    """Schlanke Benutzerliste zur Auswahl von Inventur-Teilnehmern (auch fuer
    Verantwortliche ohne volle Benutzerverwaltung)."""
    return [{"id": u.id, "name": _user_name(u), "username": u.username}
            for u in db.query(models.User).filter(models.User.active == True)  # noqa: E712
            .order_by(models.User.username).all()]


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
