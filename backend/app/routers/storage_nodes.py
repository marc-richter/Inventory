from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/storage-nodes", tags=["storage-nodes"])

LEVELS = models.StorageNode.LEVELS
# Lineare Ebenen-Kette (ohne die Sonderebene „fahrzeug", die separat behandelt wird).
LEVELS_LINEAR = ["standort", "etage", "raum", "schrank", "fach", "tasche"]


def _child_level(parent: models.StorageNode) -> str:
    if parent is None:
        return "standort"
    # Ein Fahrzeug enthält Schränke/Fächer/Taschen.
    if parent.level == "fahrzeug":
        return "schrank"
    try:
        i = LEVELS_LINEAR.index(parent.level)
    except ValueError:
        i = 0
    if i + 1 >= len(LEVELS_LINEAR):
        raise HTTPException(status_code=400, detail="Unter der untersten Ebene können keine weiteren Ebenen liegen.")
    return LEVELS_LINEAR[i + 1]


@router.get("", response_model=list[schemas.StorageNodeOut])
def list_nodes(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.StorageNode).order_by(
        models.StorageNode.sort_order, models.StorageNode.name).all()


@router.get("/overview")
def nodes_overview(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Je Knoten: direkte Artikel, Artikel im gesamten Teilbaum, Anzahl Unterknoten.
    Z.B. „wie viele Artikel im Fach/Schrank" und „wie viele Fächer hat ein Schrank"."""
    nodes = db.query(models.StorageNode).all()
    children = {}
    for n in nodes:
        children.setdefault(n.parent_id, []).append(n.id)
    # direkte Artikelzahl je Knoten
    direct = {}
    for node_id, cnt in db.query(models.Article.storage_node_id, func.count(models.Article.id)) \
            .filter(models.Article.storage_node_id.isnot(None)) \
            .group_by(models.Article.storage_node_id).all():
        direct[node_id] = cnt

    total_cache = {}

    def subtree_total(nid):
        if nid in total_cache:
            return total_cache[nid]
        t = direct.get(nid, 0)
        for c in children.get(nid, []):
            t += subtree_total(c)
        total_cache[nid] = t
        return t

    return [{
        "id": n.id,
        "article_count": direct.get(n.id, 0),
        "article_count_total": subtree_total(n.id),
        "child_count": len(children.get(n.id, [])),
    } for n in nodes]


@router.post("", response_model=schemas.StorageNodeOut)
def create_node(payload: schemas.StorageNodeCreate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")
    parent = None
    if payload.parent_id:
        parent = db.query(models.StorageNode).get(payload.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Übergeordneter Knoten nicht gefunden")
    level = (payload.level or "").strip().lower() or _child_level(parent)
    if level not in LEVELS:
        raise HTTPException(status_code=400, detail="Unbekannte Ebene")
    # Doppelte Namen unter demselben Elternknoten wiederverwenden.
    existing = db.query(models.StorageNode).filter(
        models.StorageNode.parent_id == (parent.id if parent else None),
        models.StorageNode.name.ilike(name),
    ).first()
    if existing:
        return existing
    node = models.StorageNode(
        parent_id=parent.id if parent else None, level=level, name=name,
        description=payload.description or "",
        address=payload.address or "", contact_name=payload.contact_name or "",
        contact_phone=payload.contact_phone or "", contact_fax=payload.contact_fax or "",
        contact_email=payload.contact_email or "",
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    log_action(db, user, "create_storage_node", "storage_node", node.id, {"name": name, "level": level})
    return node


@router.put("/{node_id}", response_model=schemas.StorageNodeOut)
def update_node(node_id: int, payload: schemas.StorageNodeUpdate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    node = db.query(models.StorageNode).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Knoten nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name") is not None and data["name"].strip():
        node.name = data["name"].strip()
    if "parent_id" in data:
        new_parent_id = data["parent_id"]
        if new_parent_id == node.id:
            raise HTTPException(status_code=400, detail="Knoten kann nicht sein eigener Elternknoten sein")
        # Zyklus verhindern: neuer Elternknoten darf kein Nachfahre sein
        if new_parent_id:
            cur = db.query(models.StorageNode).get(new_parent_id)
            seen = set()
            while cur is not None and cur.id not in seen:
                if cur.id == node.id:
                    raise HTTPException(status_code=400, detail="Ungültiges Verschieben (Zyklus)")
                seen.add(cur.id)
                cur = cur.parent
            parent = db.query(models.StorageNode).get(new_parent_id)
            node.parent_id = new_parent_id
            node.level = "fahrzeug" if node.vehicle_article_id else _child_level(parent)
        else:
            node.parent_id = None
            node.level = "fahrzeug" if node.vehicle_article_id else "standort"
    for f in ("description", "address", "contact_name", "contact_phone", "contact_fax", "contact_email"):
        if data.get(f) is not None:
            setattr(node, f, data[f])
    db.commit()
    db.refresh(node)
    log_action(db, user, "update_storage_node", "storage_node", node.id, {"name": node.name})
    return node


@router.delete("/{node_id}")
def delete_node(node_id: int, force: bool = False, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    node = db.query(models.StorageNode).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Knoten nicht gefunden")
    kids = db.query(models.StorageNode).filter(models.StorageNode.parent_id == node_id).count()
    if kids:
        raise HTTPException(status_code=400, detail="Knoten enthält Unterebenen – diese zuerst entfernen.")
    in_use = db.query(models.Article).filter(models.Article.storage_node_id == node_id).count()
    if in_use and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Knoten wird noch von {in_use} Artikel(n) verwendet. Zum Löschen die Verknüpfung lösen (force).",
        )
    if force and in_use:
        db.query(models.Article).filter(models.Article.storage_node_id == node_id) \
            .update({models.Article.storage_node_id: None})
    db.delete(node)
    db.commit()
    log_action(db, user, "delete_storage_node", "storage_node", node_id, {"force": force})
    return {"ok": True}
