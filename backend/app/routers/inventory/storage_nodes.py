from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.audit import log_action

router = APIRouter(prefix="/api/v1/storage-nodes", tags=["storage-nodes"])

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
        parent = db.get(models.StorageNode, payload.parent_id)
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
    if not node.code:
        node.code = f"LO{node.id}"
        db.commit()
        db.refresh(node)
    log_action(db, user, "create_storage_node", "storage_node", node.id, {"name": name, "level": level})
    return node


@router.get("/by-code/{code}", response_model=schemas.StorageNodeOut)
def node_by_code(code: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Lagerort anhand seines Codes (QR/Barcode) finden – für die Lagerort-Inventur."""
    c = (code or "").strip()
    n = db.query(models.StorageNode).filter(models.StorageNode.code.ilike(c)).first()
    if not n and c.isdigit():
        n = db.get(models.StorageNode, int(c))
    if not n:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    return n


@router.post("/{node_id}/inventory")
def node_inventory(node_id: int, payload: schemas.NodeInventoryRequest, db: Session = Depends(get_db),
                   user=Depends(security.require_capability("inventory"))):
    """Lagerort-Inventur: gescannte/eingetippte Artikel diesem Lagerort zuordnen und als
    inventarisiert markieren. Gibt eine Zusammenfassung zurück."""
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    now = __import__("datetime").datetime.utcnow()
    assigned, moved, not_found = [], [], []
    seen = set()
    for raw in payload.artikelnummern or []:
        num = (raw or "").strip()
        if not num or num in seen:
            continue
        seen.add(num)
        a = db.query(models.Article).filter(models.Article.artikelnummer == num).first()
        if not a:
            not_found.append(num)
            continue
        if payload.move and a.storage_node_id != node_id:
            a.storage_node_id = node_id
            moved.append(num)
        a.last_inventoried_at = now
        assigned.append(num)
    db.commit()
    log_action(db, user, "node_inventory", "storage_node", node_id,
               {"assigned": len(assigned), "moved": len(moved), "not_found": len(not_found)})
    return {"node_id": node_id, "node_name": node.name, "assigned": assigned, "moved": moved, "not_found": not_found}


@router.put("/{node_id}", response_model=schemas.StorageNodeOut)
def update_node(node_id: int, payload: schemas.StorageNodeUpdate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Knoten nicht gefunden")
    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is not None and data["name"].strip():
        node.name = data["name"].strip()
    if "parent_id" in data:
        new_parent_id = data["parent_id"]
        if new_parent_id == node.id:
            raise HTTPException(status_code=400, detail="Knoten kann nicht sein eigener Elternknoten sein")
        # Zyklus verhindern: neuer Elternknoten darf kein Nachfahre sein
        if new_parent_id:
            cur = db.get(models.StorageNode, new_parent_id)
            seen = set()
            while cur is not None and cur.id not in seen:
                if cur.id == node.id:
                    raise HTTPException(status_code=400, detail="Ungültiges Verschieben (Zyklus)")
                seen.add(cur.id)
                cur = cur.parent
            parent = db.get(models.StorageNode, new_parent_id)
            node.parent_id = new_parent_id
            node.level = node.level if node.node_article_id else _child_level(parent)
        else:
            node.parent_id = None
            node.level = node.level if node.node_article_id else "standort"
    for f in ("description", "address", "contact_name", "contact_phone", "contact_fax", "contact_email"):
        if data.get(f) is not None:
            setattr(node, f, data[f])
    # Name des zugehörigen Schließanlagen-Objekts (Standort) mitziehen.
    if data.get("name") is not None:
        obj = db.query(models.LockObject).filter(models.LockObject.storage_node_id == node.id).first()
        if obj:
            obj.name = node.name
    db.commit()
    db.refresh(node)
    log_action(db, user, "update_storage_node", "storage_node", node.id, {"name": node.name})
    return node


@router.get("/{node_id}/cylinder-count")
def node_cylinder_count(node_id: int, db: Session = Depends(get_db),
                        user=Depends(security.require_roles("admin", "verwalter"))):
    """Anzahl Schließzylinder, die beim Löschen dieses Lagerorts betroffen wären
    (für die Rückfrage 'als unabhängig behalten?')."""
    node = db.get(models.StorageNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Knoten nicht gefunden")
    n = db.query(models.Lock).filter(models.Lock.storage_node_id == node_id).count()
    for o in db.query(models.LockObject).filter(models.LockObject.storage_node_id == node_id).all():
        n += db.query(models.Lock).filter(models.Lock.object_id == o.id,
                                          models.Lock.storage_node_id.is_(None)).count()
    return {"count": n}


@router.post("/migrate-legacy")
def migrate_legacy_locations(db: Session = Depends(get_db),
                              user=Depends(security.require_roles("admin"))):
    """Migriert die alten Freitext-Lagerort-Felder (etage, raum, schrank, fach)
    der Artikel in die neue StorageNode-Baumstruktur."""
    # Alle Knoten laden für schnellen Lookup
    all_nodes = db.query(models.StorageNode).all()
    by_id = {n.id: n for n in all_nodes}
    by_key = {}  # (parent_id, level, name_lower) -> node
    for n in all_nodes:
        key = (n.parent_id, n.level, n.name.lower().strip())
        by_key[key] = n

    def get_or_create(parent_id, level, name):
        name = (name or "").strip()
        if not name:
            return None
        key = (parent_id, level, name.lower())
        if key in by_key:
            return by_key[key]
        node = models.StorageNode(
            parent_id=parent_id,
            level=level,
            name=name,
        )
        db.add(node)
        db.flush()
        if not node.code:
            node.code = f"LO{node.id}"
        by_id[node.id] = node
        by_key[key] = node
        return node

    # Basis-Standort: StorageLocation -> StorageNode (level='standort')
    # Wir nutzen vorhandene StorageLocations als Wurzelknoten
    loc_map = {}
    for sl in db.query(models.StorageLocation).all():
        key = (None, "standort", sl.name.lower().strip())
        if key in by_key:
            loc_map[sl.id] = by_key[key]
        else:
            node = models.StorageNode(
                parent_id=None, level="standort", name=sl.name,
                address=sl.address, contact_name=sl.contact_name,
                contact_phone=sl.contact_phone, contact_fax=sl.contact_fax,
                contact_email=sl.contact_email,
            )
            db.add(node)
            db.flush()
            if not node.code:
                node.code = f"LO{node.id}"
            loc_map[sl.id] = node
            by_key[key] = node
            by_id[node.id] = node

    # Artikel mit alten Feldern aber ohne storage_node_id finden
    articles = db.query(models.Article).filter(
        models.Article.storage_node_id.is_(None),
        (models.Article.etage != "") | (models.Article.raum != "") |
        (models.Article.schrank != "") | (models.Article.fach != ""),
    ).all()

    migrated = 0
    skipped = 0
    for a in articles:
        # Wurzelknoten bestimmen: storage_location_id -> StorageNode
        root = None
        if a.storage_location_id and a.storage_location_id in loc_map:
            root = loc_map[a.storage_location_id]
        else:
            # Fallback: ersten Standort nehmen oder neuen "Unbekannt" erstellen
            if not loc_map:
                root = get_or_create(None, "standort", "Unbekannt")
            else:
                root = next(iter(loc_map.values()))

        # Ebene für Ebene durchgehen
        current = root
        for level, value in [
            ("etage", a.etage),
            ("raum", a.raum),
            ("schrank", a.schrank),
            ("fach", a.fach),
        ]:
            if not value or not value.strip():
                continue
            nxt = get_or_create(current.id, level, value)
            if nxt:
                current = nxt

        if current and current != root:
            a.storage_node_id = current.id
            migrated += 1
        else:
            skipped += 1

    db.commit()
    return {"migrated": migrated, "skipped": skipped, "message": f"{migrated} Artikel migriert, {skipped} übersprungen"}


@router.delete("/{node_id}")
def delete_node(node_id: int, force: bool = False, keep_cylinders: bool = False,
                db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    node = db.get(models.StorageNode, node_id)
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
    # Schließzylinder dieses Lagerorts (abgeleitet + ggf. manuelle unter dem
    # Standort-Objekt) entweder als unabhängig behalten oder mit entfernen.
    from ..keys.keys import independent_object
    std_objs = db.query(models.LockObject).filter(models.LockObject.storage_node_id == node_id).all()
    affected = list(db.query(models.Lock).filter(models.Lock.storage_node_id == node_id).all())
    for o in std_objs:
        affected += db.query(models.Lock).filter(models.Lock.object_id == o.id,
                                                 models.Lock.storage_node_id.is_(None)).all()
    if keep_cylinders and affected:
        indep = independent_object(db)
        for lk in affected:
            lk.storage_node_id = None
            lk.object_id = indep.id
    else:
        for lk in affected:
            db.delete(lk)
    db.flush()
    for o in std_objs:
        db.delete(o)
    db.delete(node)
    db.commit()
    log_action(db, user, "delete_storage_node", "storage_node", node_id, {"force": force})
    return {"ok": True}
