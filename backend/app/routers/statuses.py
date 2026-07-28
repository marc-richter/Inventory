import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/statuses", tags=["statuses"])


def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "status"


@router.get("", response_model=list[schemas.StatusDefOut])
def list_statuses(category_id: Optional[int] = None, include_inactive: bool = False,
                  db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    """Liste der Status. Optional auf eine Artikelklasse (category_id) einschraenken -
    ein Status gilt fuer eine Klasse, wenn seine category_ids leer sind (= alle) oder
    die Klasse enthalten."""
    q = db.query(models.StatusDef)
    if not include_inactive:
        q = q.filter(models.StatusDef.active == True)  # noqa: E712
    items = q.order_by(models.StatusDef.sort_order, models.StatusDef.id).all()
    if category_id is not None:
        items = [s for s in items if not s.category_ids or category_id in s.category_ids]
    return items


@router.post("", response_model=schemas.StatusDefOut)
def create_status(payload: schemas.StatusDefCreate, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin"))):
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Bezeichnung fehlt")
    key = _slugify(payload.key or label)
    if db.query(models.StatusDef).filter(models.StatusDef.key == key).first():
        raise HTTPException(status_code=400, detail="Ein Status mit diesem Schluessel existiert bereits")
    policy = payload.issue_policy if payload.issue_policy in ("direct", "confirm", "blocked") else "confirm"
    s = models.StatusDef(
        key=key, label=label, sort_order=payload.sort_order,
        is_builtin=False, active=True, category_ids=payload.category_ids or [],
        require_note=bool(payload.require_note), allow_image=bool(payload.allow_image),
        issue_policy=policy,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    log_action(db, user, "create_status", "status_def", s.id, {"key": key, "label": label})
    return s


@router.put("/{status_id}", response_model=schemas.StatusDefOut)
def update_status(status_id: int, payload: schemas.StatusDefUpdate, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin"))):
    s = db.query(models.StatusDef).get(status_id)
    if not s:
        raise HTTPException(status_code=404, detail="Status nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("label") is not None:
        s.label = data["label"].strip() or s.label
    if data.get("sort_order") is not None:
        s.sort_order = data["sort_order"]
    if data.get("category_ids") is not None:
        s.category_ids = data["category_ids"]
    if data.get("require_note") is not None:
        s.require_note = bool(data["require_note"])
    if data.get("allow_image") is not None:
        s.allow_image = bool(data["allow_image"])
    if data.get("issue_policy") is not None:
        if data["issue_policy"] in ("direct", "confirm", "blocked"):
            # "Ausgemustert" bleibt immer gesperrt.
            s.issue_policy = "blocked" if s.key == "ausgemustert" else data["issue_policy"]
    if data.get("active") is not None:
        if s.is_builtin and not data["active"]:
            raise HTTPException(status_code=400, detail="Eingebaute Status koennen nicht deaktiviert werden")
        s.active = data["active"]
    db.commit()
    db.refresh(s)
    log_action(db, user, "update_status", "status_def", s.id, data)
    return s


@router.delete("/{status_id}")
def delete_status(status_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin"))):
    s = db.query(models.StatusDef).get(status_id)
    if not s:
        raise HTTPException(status_code=404, detail="Status nicht gefunden")
    if s.is_builtin:
        raise HTTPException(status_code=400, detail="Eingebaute Status koennen nicht geloescht werden")
    in_use = db.query(models.Article).filter(models.Article.status == s.key).count()
    if in_use:
        raise HTTPException(status_code=400, detail=f"Status wird noch von {in_use} Artikel(n) verwendet")
    db.delete(s)
    db.commit()
    log_action(db, user, "delete_status", "status_def", status_id)
    return {"ok": True}
