"""Frei definierbare Zusatzfelder für Artikel (je Kategorie oder Typ).

Eine Unterkategorie erbt die Felder ihrer Oberkategorie. Werte werden je Artikel
in Article.custom_values ({feld_id: wert}) abgelegt.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/custom-fields", tags=["custom-fields"])

FIELD_TYPES = ("text", "number", "select", "bool", "date")


def _out(f) -> schemas.CustomFieldOut:
    return schemas.CustomFieldOut(
        id=f.id, label=f.label, field_type=f.field_type, options=f.options or [],
        category_id=f.category_id, article_type_id=f.article_type_id,
        required=bool(f.required), sort_order=f.sort_order or 100, active=bool(f.active))


def resolve_for(db, category_id, type_id):
    """Aktive Felder, die für (Kategorie inkl. Oberkategorie) oder Typ gelten."""
    cat_ids = set()
    if category_id:
        cat_ids.add(category_id)
        c = db.query(models.Category).get(category_id)
        if c and c.parent_id:
            cat_ids.add(c.parent_id)
    q = db.query(models.CustomFieldDef).filter(models.CustomFieldDef.active == True)  # noqa: E712
    rows = [f for f in q.all()
            if (f.category_id in cat_ids) or (type_id and f.article_type_id == type_id)]
    rows.sort(key=lambda f: (f.sort_order or 100, f.label.lower()))
    return rows


@router.get("", response_model=list[schemas.CustomFieldOut])
def list_fields(category_id: int = None, article_type_id: int = None, include_inactive: bool = False,
                db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    q = db.query(models.CustomFieldDef)
    if category_id:
        q = q.filter(models.CustomFieldDef.category_id == category_id)
    if article_type_id:
        q = q.filter(models.CustomFieldDef.article_type_id == article_type_id)
    if not include_inactive:
        q = q.filter(models.CustomFieldDef.active == True)  # noqa: E712
    rows = q.order_by(models.CustomFieldDef.sort_order, models.CustomFieldDef.label).all()
    return [_out(f) for f in rows]


@router.get("/resolve", response_model=list[schemas.CustomFieldOut])
def resolve(category_id: int = None, article_type_id: int = None,
            db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return [_out(f) for f in resolve_for(db, category_id, article_type_id)]


@router.get("/for-article/{article_id}", response_model=list[schemas.CustomFieldOut])
def for_article(article_id: int, db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    a = db.query(models.Article).get(article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return [_out(f) for f in resolve_for(db, a.category_id, a.type_id)]


@router.post("", response_model=schemas.CustomFieldOut)
def create_field(payload: schemas.CustomFieldCreate, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin", "verwalter"))):
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Bezeichnung fehlt")
    if bool(payload.category_id) == bool(payload.article_type_id):
        raise HTTPException(status_code=400, detail="Genau ein Ziel (Kategorie ODER Typ) angeben")
    ft = payload.field_type if payload.field_type in FIELD_TYPES else "text"
    opts = [str(o).strip() for o in (payload.options or []) if str(o).strip()] if ft == "select" else []
    nxt = (db.query(models.CustomFieldDef).count() + 1) * 10
    f = models.CustomFieldDef(
        label=label, field_type=ft, options=opts, category_id=payload.category_id,
        article_type_id=payload.article_type_id, required=bool(payload.required),
        sort_order=nxt, active=True)
    db.add(f)
    db.commit()
    db.refresh(f)
    log_action(db, user, "custom_field_create", "custom_field", f.id, {"label": label})
    return _out(f)


@router.put("/{field_id}", response_model=schemas.CustomFieldOut)
def update_field(field_id: int, payload: schemas.CustomFieldUpdate, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin", "verwalter"))):
    f = db.query(models.CustomFieldDef).get(field_id)
    if not f:
        raise HTTPException(status_code=404, detail="Feld nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("label"):
        f.label = data["label"].strip()
    if "field_type" in data and data["field_type"] in FIELD_TYPES:
        f.field_type = data["field_type"]
    if "options" in data and data["options"] is not None:
        f.options = [str(o).strip() for o in data["options"] if str(o).strip()]
    if "required" in data and data["required"] is not None:
        f.required = bool(data["required"])
    if "active" in data and data["active"] is not None:
        f.active = bool(data["active"])
    if "sort_order" in data and data["sort_order"] is not None:
        f.sort_order = int(data["sort_order"])
    db.commit()
    db.refresh(f)
    log_action(db, user, "custom_field_update", "custom_field", f.id)
    return _out(f)


@router.delete("/{field_id}")
def delete_field(field_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin", "verwalter"))):
    f = db.query(models.CustomFieldDef).get(field_id)
    if f:
        db.delete(f)
        db.commit()
        log_action(db, user, "custom_field_delete", "custom_field", field_id)
    return {"ok": True}
