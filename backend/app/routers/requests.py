import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _uname(u):
    return (u.full_name or u.username) if u else None


def _type_cat(db, type_id):
    if not type_id:
        return None
    t = db.query(models.ArticleType).get(type_id)
    return t.category_id if t else None


def is_responsible(db, user, category_id):
    """Zustaendig ist ein Administrator oder ein Materialverwalter, dessen Klassen-
    Zustaendigkeit die Klasse dieses Typs abdeckt (oder 'alle Klassen')."""
    if "admin" in (user.roles or []):
        return True
    rows = db.query(models.MaterialManager).filter(models.MaterialManager.user_id == user.id).all()
    for r in rows:
        if r.category_id is None or r.category_id == category_id:
            return True
    return False


def _out(r) -> schemas.MaterialRequestOut:
    return schemas.MaterialRequestOut(
        id=r.id, requester_user_id=r.requester_user_id, requester_name=_uname(r.requester),
        type_id=r.type_id, type_name=r.type.name if r.type else None, size=r.size or "",
        quantity=r.quantity or 1, desired_from=r.desired_from, desired_until=r.desired_until,
        note=r.note or "", status=r.status, handled_by_name=_uname(r.handled_by),
        handled_at=r.handled_at, decision_note=r.decision_note or "", created_at=r.created_at)


@router.post("", response_model=schemas.MaterialRequestOut)
def create_request(payload: schemas.MaterialRequestCreate, db: Session = Depends(get_db),
                   user=Depends(security.get_current_user)):
    r = models.MaterialRequest(
        requester_user_id=user.id, type_id=payload.type_id, size=(payload.size or "").strip(),
        quantity=max(1, int(payload.quantity or 1)), desired_from=payload.desired_from,
        desired_until=payload.desired_until, note=payload.note or "", status="open")
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "material_request_create", "material_request", r.id)
    try:
        from .. import telegram
        tname = r.type.name if r.type else "Material"
        sz = f" Gr. {r.size}" if r.size else ""
        telegram.notify_event(db, "request",
                              f"📝 Neue Materialanfrage von {_uname(user)}: {r.quantity}× {tname}{sz}.")
    except Exception:
        pass
    return _out(r)


@router.get("", response_model=list[schemas.MaterialRequestOut])
def list_requests(mine: bool = False, inbox: bool = False, include_done: bool = False,
                  db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    q = db.query(models.MaterialRequest).order_by(models.MaterialRequest.created_at.desc())
    if mine:
        q = q.filter(models.MaterialRequest.requester_user_id == user.id)
        rows = q.all()
    elif inbox:
        rows = [r for r in q.all() if is_responsible(db, user, _type_cat(db, r.type_id))]
        if not include_done:
            rows = [r for r in rows if r.status == "open"]
    else:
        # Standard: eigene Anfragen
        rows = q.filter(models.MaterialRequest.requester_user_id == user.id).all()
    return [_out(r) for r in rows]


@router.get("/inbox-count")
def inbox_count(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    open_reqs = db.query(models.MaterialRequest).filter(models.MaterialRequest.status == "open").all()
    n = sum(1 for r in open_reqs if is_responsible(db, user, _type_cat(db, r.type_id)))
    return {"count": n}


@router.post("/{request_id}/decision", response_model=schemas.MaterialRequestOut)
def decide(request_id: int, payload: schemas.MaterialRequestDecision, db: Session = Depends(get_db),
           user=Depends(security.get_current_user)):
    r = db.query(models.MaterialRequest).get(request_id)
    if not r:
        raise HTTPException(status_code=404, detail="Anfrage nicht gefunden")
    if not is_responsible(db, user, _type_cat(db, r.type_id)):
        raise HTTPException(status_code=403, detail="Nur zuständige Materialverwalter dürfen entscheiden")
    if payload.status not in ("approved", "rejected", "done"):
        raise HTTPException(status_code=400, detail="Unbekannter Status")
    r.status = payload.status
    r.decision_note = payload.decision_note or ""
    r.handled_by_user_id = user.id
    r.handled_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(r)
    log_action(db, user, "material_request_decision", "material_request", r.id, {"status": r.status})
    return _out(r)


@router.delete("/{request_id}")
def delete_request(request_id: int, db: Session = Depends(get_db),
                   user=Depends(security.get_current_user)):
    r = db.query(models.MaterialRequest).get(request_id)
    if not r:
        return {"ok": True}
    if r.requester_user_id != user.id and "admin" not in (user.roles or []):
        raise HTTPException(status_code=403, detail="Nur der Ersteller oder ein Admin darf löschen")
    db.delete(r)
    db.commit()
    log_action(db, user, "material_request_delete", "material_request", request_id)
    return {"ok": True}
