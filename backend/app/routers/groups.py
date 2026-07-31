from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _user_name(u):
    return (u.full_name or u.username) if u else ""


def _members(db, group_id):
    rows = db.query(models.UserGroupMember, models.User).join(
        models.User, models.User.id == models.UserGroupMember.user_id
    ).filter(models.UserGroupMember.group_id == group_id).all()
    return [{"user_id": u.id, "name": _user_name(u), "active": bool(u.active)} for _, u in rows]


def _out(db, g, with_members=False):
    members = _members(db, g.id)
    return schemas.GroupOut(id=g.id, name=g.name, description=g.description or "",
                            member_count=len(members), members=members if with_members else [])


@router.get("", response_model=list[schemas.GroupOut])
def list_groups(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    groups = db.query(models.UserGroup).order_by(models.UserGroup.name).all()
    return [_out(db, g) for g in groups]


@router.get("/assignable-users")
def assignable_users(db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    return [{"id": u.id, "name": _user_name(u), "username": u.username}
            for u in db.query(models.User).filter(models.User.active == True)  # noqa: E712
            .order_by(models.User.username).all()]


@router.post("", response_model=schemas.GroupOut)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")
    if db.query(models.UserGroup).filter(models.UserGroup.name.ilike(name)).first():
        raise HTTPException(status_code=400, detail="Gruppe existiert bereits")
    g = models.UserGroup(name=name, description=payload.description or "")
    db.add(g)
    db.commit()
    db.refresh(g)
    log_action(db, user, "create_group", "user_group", g.id, {"name": name})
    return _out(db, g, with_members=True)


@router.get("/{group_id}", response_model=schemas.GroupOut)
def get_group(group_id: int, db: Session = Depends(get_db), user=Depends(security.require_roles("admin"))):
    g = db.query(models.UserGroup).get(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    return _out(db, g, with_members=True)


@router.put("/{group_id}", response_model=schemas.GroupOut)
def update_group(group_id: int, payload: schemas.GroupUpdate, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    g = db.query(models.UserGroup).get(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name") and data["name"].strip():
        g.name = data["name"].strip()
    if "description" in data and data["description"] is not None:
        g.description = data["description"]
    db.commit()
    db.refresh(g)
    log_action(db, user, "update_group", "user_group", g.id)
    return _out(db, g, with_members=True)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db),
                 user=Depends(security.require_roles("admin"))):
    g = db.query(models.UserGroup).get(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    db.query(models.UserGroupMember).filter(models.UserGroupMember.group_id == group_id).delete()
    db.delete(g)
    db.commit()
    log_action(db, user, "delete_group", "user_group", group_id)
    return {"ok": True}


@router.post("/{group_id}/members", response_model=schemas.GroupOut)
def add_member(group_id: int, payload: schemas.GroupMemberAdd, db: Session = Depends(get_db),
               user=Depends(security.require_roles("admin"))):
    g = db.query(models.UserGroup).get(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    if not db.query(models.User).get(payload.user_id):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    exists = db.query(models.UserGroupMember).filter(
        models.UserGroupMember.group_id == group_id,
        models.UserGroupMember.user_id == payload.user_id).first()
    if not exists:
        db.add(models.UserGroupMember(group_id=group_id, user_id=payload.user_id))
        db.commit()
        log_action(db, user, "group_add_member", "user_group", group_id, {"user_id": payload.user_id})
    db.refresh(g)
    return _out(db, g, with_members=True)


@router.delete("/{group_id}/members/{user_id}", response_model=schemas.GroupOut)
def remove_member(group_id: int, user_id: int, db: Session = Depends(get_db),
                  user=Depends(security.require_roles("admin"))):
    g = db.query(models.UserGroup).get(group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    db.query(models.UserGroupMember).filter(
        models.UserGroupMember.group_id == group_id,
        models.UserGroupMember.user_id == user_id).delete()
    db.commit()
    log_action(db, user, "group_remove_member", "user_group", group_id, {"user_id": user_id})
    db.refresh(g)
    return _out(db, g, with_members=True)
