from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api", tags=["lookups"])


# ---------- Kategorien ----------

@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.Category).order_by(models.Category.name).all()


@router.put("/categories/{category_id}/issuable", response_model=schemas.CategoryOut)
def set_category_issuable(category_id: int, payload: schemas.IssuableRequest, db: Session = Depends(get_db),
                          user=Depends(security.require_roles("admin", "verwalter"))):
    """Standard fuer die Materialklasse setzen, ob Artikel ausgegeben/persoenlich
    zugeordnet werden koennen (Einzelartikel koennen abweichen)."""
    c = db.query(models.Category).get(category_id)
    if not c:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    c.issuable_default = bool(payload.issuable)
    db.commit()
    db.refresh(c)
    log_action(db, user, "set_category_issuable", "category", c.id, {"issuable": c.issuable_default})
    return c


@router.get("/categories/check")
def check_category(name: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Prueft ob eine Kategorie mit diesem Namen existiert (fuer Neu-anlegen-Dialog)."""
    existing = db.query(models.Category).filter(models.Category.name.ilike(name.strip())).first()
    return {"exists": bool(existing), "match": existing.name if existing else None}


@router.post("/categories", response_model=schemas.LookupOut)
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    name = payload.name.strip()
    existing = db.query(models.Category).filter(models.Category.name.ilike(name)).first()
    if existing:
        return existing
    c = models.Category(name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    log_action(db, user, "create_category", "category", c.id, {"name": name})
    return c


@router.put("/categories/{category_id}", response_model=schemas.LookupOut)
def rename_category(category_id: int, payload: schemas.RenameRequest, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin"))):
    c = db.query(models.Category).get(category_id)
    if not c:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    c.name = payload.name.strip()
    db.commit()
    db.refresh(c)
    log_action(db, user, "rename_category", "category", c.id, {"name": c.name})
    return c


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin"))):
    c = db.query(models.Category).get(category_id)
    if not c:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    in_use = db.query(models.Article).filter(models.Article.category_id == category_id).count()
    if in_use:
        raise HTTPException(status_code=400, detail="Kategorie wird noch von Artikeln verwendet")
    has_types = db.query(models.ArticleType).filter(models.ArticleType.category_id == category_id).count()
    if has_types:
        raise HTTPException(status_code=400, detail="Kategorie enthaelt noch Typen - diese zuerst entfernen")
    db.delete(c)
    db.commit()
    log_action(db, user, "delete_category", "category", category_id)
    return {"ok": True}


# ---------- Groessenarten (Groessenprofil) ----------

@router.get("/size-fields", response_model=list[schemas.SizeFieldOut])
def list_size_fields(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.SizeField).order_by(models.SizeField.sort_order, models.SizeField.id).all()


@router.post("/size-fields", response_model=schemas.SizeFieldOut)
def create_size_field(payload: schemas.SizeFieldCreate, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin", "verwalter"))):
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Bezeichnung fehlt")
    nxt = (db.query(models.SizeField).count() + 1) * 10
    f = models.SizeField(label=label, sort_order=nxt, active=True)
    db.add(f)
    db.commit()
    db.refresh(f)
    log_action(db, user, "create_size_field", "size_field", f.id, {"label": label})
    return f


@router.put("/size-fields/{field_id}", response_model=schemas.SizeFieldOut)
def update_size_field(field_id: int, payload: schemas.SizeFieldUpdate, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin", "verwalter"))):
    f = db.query(models.SizeField).get(field_id)
    if not f:
        raise HTTPException(status_code=404, detail="Größenart nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("label"):
        f.label = data["label"].strip()
    if "sort_order" in data and data["sort_order"] is not None:
        f.sort_order = int(data["sort_order"])
    if "active" in data and data["active"] is not None:
        f.active = bool(data["active"])
    db.commit()
    db.refresh(f)
    log_action(db, user, "update_size_field", "size_field", f.id)
    return f


@router.delete("/size-fields/{field_id}")
def delete_size_field(field_id: int, db: Session = Depends(get_db),
                      user=Depends(security.require_roles("admin"))):
    f = db.query(models.SizeField).get(field_id)
    if f:
        db.delete(f)
        db.commit()
        log_action(db, user, "delete_size_field", "size_field", field_id)
    return {"ok": True}


# ---------- Typen ----------

@router.get("/types", response_model=list[schemas.TypeOut])
def list_types(category_id: int = None, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    q = db.query(models.ArticleType)
    if category_id:
        q = q.filter(models.ArticleType.category_id == category_id)
    return q.order_by(models.ArticleType.name).all()


@router.get("/types/check")
def check_type(name: str, category_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    existing = db.query(models.ArticleType).filter(
        models.ArticleType.category_id == category_id,
        models.ArticleType.name.ilike(name.strip())
    ).first()
    return {"exists": bool(existing), "match": existing.name if existing else None}


@router.post("/types", response_model=schemas.TypeOut)
def create_type(payload: schemas.TypeCreate, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin", "verwalter"))):
    name = payload.name.strip()
    existing = db.query(models.ArticleType).filter(
        models.ArticleType.category_id == payload.category_id,
        models.ArticleType.name.ilike(name)
    ).first()
    if existing:
        return existing
    t = models.ArticleType(name=name, category_id=payload.category_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    log_action(db, user, "create_type", "article_type", t.id, {"name": name})
    return t


@router.put("/types/{type_id}", response_model=schemas.TypeOut)
def rename_type(type_id: int, payload: schemas.RenameRequest, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    t = db.query(models.ArticleType).get(type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    t.name = payload.name.strip()
    db.commit()
    db.refresh(t)
    log_action(db, user, "rename_type", "article_type", t.id, {"name": t.name})
    return t


@router.put("/types/{type_id}/min-stock", response_model=schemas.TypeOut)
def set_type_min_stock(type_id: int, payload: schemas.MinStockRequest, db: Session = Depends(get_db),
                       user=Depends(security.require_roles("admin", "verwalter"))):
    """Mindestbestand eines Typs setzen (0 = aus). Steuert die Warnung bei
    Unterschreitung des verfuegbaren Bestands."""
    t = db.query(models.ArticleType).get(type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    t.min_stock = max(0, int(payload.min_stock or 0))
    db.commit()
    db.refresh(t)
    log_action(db, user, "set_min_stock", "article_type", t.id, {"min_stock": t.min_stock})
    return t


@router.delete("/types/{type_id}")
def delete_type(type_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    t = db.query(models.ArticleType).get(type_id)
    if not t:
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    in_use = db.query(models.Article).filter(models.Article.type_id == type_id).count()
    if in_use:
        raise HTTPException(status_code=400, detail="Typ wird noch von Artikeln verwendet")
    db.delete(t)
    db.commit()
    log_action(db, user, "delete_type", "article_type", type_id)
    return {"ok": True}


# ---------- Abteilung / Organisation ----------

@router.get("/organizations", response_model=list[schemas.LookupOut])
def list_organizations(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.Organization).order_by(models.Organization.name).all()


@router.get("/organizations/check")
def check_organization(name: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    existing = db.query(models.Organization).filter(models.Organization.name.ilike(name.strip())).first()
    return {"exists": bool(existing), "match": existing.name if existing else None}


@router.post("/organizations", response_model=schemas.LookupOut)
def create_organization(payload: schemas.OrganizationCreate, db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin", "verwalter"))):
    name = payload.name.strip()
    existing = db.query(models.Organization).filter(models.Organization.name.ilike(name)).first()
    if existing:
        return existing
    o = models.Organization(name=name)
    db.add(o)
    db.commit()
    db.refresh(o)
    log_action(db, user, "create_organization", "organization", o.id, {"name": name})
    return o


@router.put("/organizations/{org_id}", response_model=schemas.LookupOut)
def rename_organization(org_id: int, payload: schemas.RenameRequest, db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin"))):
    o = db.query(models.Organization).get(org_id)
    if not o:
        raise HTTPException(status_code=404, detail="Abteilung nicht gefunden")
    o.name = payload.name.strip()
    db.commit()
    db.refresh(o)
    log_action(db, user, "rename_organization", "organization", o.id, {"name": o.name})
    return o


@router.delete("/organizations/{org_id}")
def delete_organization(org_id: int, force: bool = False, db: Session = Depends(get_db),
                         user=Depends(security.require_roles("admin"))):
    o = db.query(models.Organization).get(org_id)
    if not o:
        raise HTTPException(status_code=404, detail="Abteilung nicht gefunden")
    in_use = db.query(models.Article).filter(models.Article.organization_id == org_id).count()
    in_use_person = db.query(models.Person).filter(models.Person.organization_id == org_id).count()
    if (in_use or in_use_person) and not force:
        raise HTTPException(
            status_code=400,
            detail=(f"Abteilung wird noch verwendet ({in_use} Artikel, {in_use_person} Person(en)). "
                    "Zum Löschen die Verknüpfung entfernen (force)."),
        )
    if force:
        # Verknuepfungen loesen (Feld ist optional) und dann loeschen.
        db.query(models.Article).filter(models.Article.organization_id == org_id) \
            .update({models.Article.organization_id: None})
        db.query(models.Person).filter(models.Person.organization_id == org_id) \
            .update({models.Person.organization_id: None})
    db.delete(o)
    db.commit()
    log_action(db, user, "delete_organization", "organization", org_id, {"force": force})
    return {"ok": True}


# ---------- Lagerort ----------

@router.get("/storage-locations", response_model=list[schemas.StandortOut])
def list_storage_locations(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return db.query(models.StorageLocation).order_by(models.StorageLocation.name).all()


@router.get("/storage-locations/check")
def check_storage_location(name: str, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    existing = db.query(models.StorageLocation).filter(models.StorageLocation.name.ilike(name.strip())).first()
    return {"exists": bool(existing), "match": existing.name if existing else None}


_SUB_LEVELS = ["etage", "raum", "schrank", "fach"]


@router.get("/storage-locations/pending-review")
def pending_storage_review(db: Session = Depends(get_db),
                           user=Depends(security.require_roles("admin"))):
    """Bestehende (aus aelterer Version uebernommene) Lagerorte, die der Admin noch
    einer Ebene zuordnen soll."""
    rows = db.query(models.StorageLocation).filter(
        models.StorageLocation.needs_review == True  # noqa: E712
    ).order_by(models.StorageLocation.name).all()
    return [
        {"id": r.id, "name": r.name,
         "article_count": db.query(models.Article).filter(models.Article.storage_location_id == r.id).count()}
        for r in rows
    ]


@router.post("/storage-locations/{loc_id}/classify")
def classify_storage_location(loc_id: int, payload: schemas.ClassifyStandortRequest,
                              db: Session = Depends(get_db),
                              user=Depends(security.require_roles("admin"))):
    """Ordnet einen bestehenden Lagerort einer Ebene zu. 'standort' = bleibt oberste
    Ebene. Sonst wird der Name als Unterebene (etage/raum/schrank/fach) an die Artikel
    geschrieben, sie werden unter den gewaehlten/neu angelegten Standort gehaengt, und
    die darueberliegenden Ebenen koennen gleich mitgesetzt werden."""
    loc = db.query(models.StorageLocation).get(loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")

    level = (payload.level or "").strip().lower()
    if level == "standort":
        loc.needs_review = False
        db.commit()
        log_action(db, user, "classify_standort", "storage_location", loc.id, {"level": "standort"})
        return {"ok": True}

    if level not in _SUB_LEVELS:
        raise HTTPException(status_code=400, detail="Unbekannte Ebene")

    # Ziel-Standort bestimmen (bestehend oder neu anlegen)
    parent = None
    if payload.parent_standort_id:
        parent = db.query(models.StorageLocation).get(payload.parent_standort_id)
    if not parent and (payload.parent_standort_name or "").strip():
        name = payload.parent_standort_name.strip()
        parent = db.query(models.StorageLocation).filter(models.StorageLocation.name.ilike(name)).first()
        if not parent:
            parent = models.StorageLocation(name=name, needs_review=False)
            db.add(parent)
            db.flush()
    if not parent:
        raise HTTPException(status_code=400, detail="Bitte einen Standort (oberste Ebene) wählen oder anlegen")

    # Artikel umhaengen: Name als gewaehlte Unterebene, oberhalb liegende Ebenen mitsetzen
    above = payload.above or {}
    articles = db.query(models.Article).filter(models.Article.storage_location_id == loc.id).all()
    for a in articles:
        a.storage_location_id = parent.id
        setattr(a, level, loc.name)
        for k in _SUB_LEVELS:
            if k == level:
                break
            if above.get(k) is not None:
                setattr(a, k, str(above[k]))

    moved = len(articles)
    if loc.id != parent.id:
        db.delete(loc)   # alter Lagerort ist jetzt eine Unterebene -> Datensatz entfernen
    db.commit()
    log_action(db, user, "classify_standort", "storage_location", parent.id,
               {"level": level, "moved": moved, "name": loc.name})
    return {"ok": True, "moved": moved}


@router.post("/storage-locations", response_model=schemas.StandortOut)
def create_storage_location(payload: schemas.StorageLocationCreate, db: Session = Depends(get_db),
                             user=Depends(security.require_roles("admin", "verwalter"))):
    name = payload.name.strip()
    existing = db.query(models.StorageLocation).filter(models.StorageLocation.name.ilike(name)).first()
    if existing:
        return existing
    loc = models.StorageLocation(
        name=name, address=payload.address, contact_name=payload.contact_name,
        contact_phone=payload.contact_phone, contact_fax=payload.contact_fax,
        contact_email=payload.contact_email,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    log_action(db, user, "create_storage_location", "storage_location", loc.id, {"name": name})
    return loc


@router.put("/storage-locations/{loc_id}", response_model=schemas.StandortOut)
def update_storage_location(loc_id: int, payload: schemas.StandortUpdate, db: Session = Depends(get_db),
                             user=Depends(security.require_roles("admin", "verwalter"))):
    loc = db.query(models.StorageLocation).get(loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name") is not None:
        loc.name = data["name"].strip() or loc.name
    for f in ("address", "contact_name", "contact_phone", "contact_fax", "contact_email"):
        if data.get(f) is not None:
            setattr(loc, f, data[f])
    db.commit()
    db.refresh(loc)
    log_action(db, user, "update_storage_location", "storage_location", loc.id, {"name": loc.name})
    return loc


@router.delete("/storage-locations/{loc_id}")
def delete_storage_location(loc_id: int, force: bool = False, db: Session = Depends(get_db),
                             user=Depends(security.require_roles("admin"))):
    loc = db.query(models.StorageLocation).get(loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    in_use = db.query(models.Article).filter(models.Article.storage_location_id == loc_id).count()
    if in_use and not force:
        raise HTTPException(
            status_code=400,
            detail=(f"Lagerort wird noch von {in_use} Artikel(n) verwendet. "
                    "Zum Löschen die Verknüpfung entfernen (force)."),
        )
    if force:
        db.query(models.Article).filter(models.Article.storage_location_id == loc_id) \
            .update({models.Article.storage_location_id: None})
    db.delete(loc)
    db.commit()
    log_action(db, user, "delete_storage_location", "storage_location", loc_id, {"force": force})
    return {"ok": True}
