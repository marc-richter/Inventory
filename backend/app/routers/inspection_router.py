from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..audit import log_action

router = APIRouter(prefix="/api/inspection", tags=["inspection"])

TRIGGERS = ("return", "loans", "washes", "months")


# --------------------------- Checklisten -------------------------------------

def _cl_out(c) -> schemas.ChecklistOut:
    return schemas.ChecklistOut(
        id=c.id, name=c.name,
        items=[schemas.ChecklistItemOut(id=i.id, position=i.position, label=i.label) for i in c.items])


@router.get("/checklists", response_model=list[schemas.ChecklistOut])
def list_checklists(db: Session = Depends(get_db), user=Depends(security.get_current_user)):
    return [_cl_out(c) for c in db.query(models.InspectionChecklist).order_by(models.InspectionChecklist.name).all()]


@router.post("/checklists", response_model=schemas.ChecklistOut)
def create_checklist(payload: schemas.ChecklistCreate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = models.InspectionChecklist(name=(payload.name or "").strip() or "Checkliste")
    db.add(c)
    db.flush()
    for i, it in enumerate(payload.items or []):
        if (it.label or "").strip():
            db.add(models.InspectionChecklistItem(checklist_id=c.id, position=i, label=it.label.strip()))
    db.commit()
    db.refresh(c)
    log_action(db, user, "checklist_create", "inspection_checklist", c.id, {"name": c.name})
    return _cl_out(c)


@router.put("/checklists/{cid}", response_model=schemas.ChecklistOut)
def update_checklist(cid: int, payload: schemas.ChecklistUpdate, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = db.query(models.InspectionChecklist).get(cid)
    if not c:
        raise HTTPException(status_code=404, detail="Checkliste nicht gefunden")
    data = payload.dict(exclude_unset=True)
    if data.get("name"):
        c.name = data["name"].strip()
    if "items" in data and data["items"] is not None:
        c.items.clear()
        db.flush()
        for i, it in enumerate(data["items"]):
            label = (it.get("label") or "").strip()
            if label:
                db.add(models.InspectionChecklistItem(checklist_id=c.id, position=i, label=label))
    db.commit()
    db.refresh(c)
    log_action(db, user, "checklist_update", "inspection_checklist", c.id)
    return _cl_out(c)


@router.delete("/checklists/{cid}")
def delete_checklist(cid: int, db: Session = Depends(get_db),
                     user=Depends(security.require_roles("admin", "verwalter"))):
    c = db.query(models.InspectionChecklist).get(cid)
    if c:
        db.delete(c)
        db.commit()
        log_action(db, user, "checklist_delete", "inspection_checklist", cid)
    return {"ok": True}


# --------------------------- Prüfregeln je Typ -------------------------------

def _rule_out(r) -> schemas.InspectionRuleOut:
    return schemas.InspectionRuleOut(
        id=r.id, type_id=r.type_id, type_name=r.type.name if r.type else None,
        trigger=r.trigger, threshold=r.threshold or 1,
        checklist_id=r.checklist_id, checklist_name=r.checklist.name if r.checklist else None)


@router.get("/rules", response_model=list[schemas.InspectionRuleOut])
def list_rules(type_id: int = None, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    q = db.query(models.InspectionRule)
    if type_id:
        q = q.filter(models.InspectionRule.type_id == type_id)
    return [_rule_out(r) for r in q.all()]


@router.post("/rules", response_model=schemas.InspectionRuleOut)
def create_rule(payload: schemas.InspectionRuleCreate, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    if not db.query(models.ArticleType).get(payload.type_id):
        raise HTTPException(status_code=404, detail="Typ nicht gefunden")
    trig = payload.trigger if payload.trigger in TRIGGERS else "return"
    r = models.InspectionRule(type_id=payload.type_id, trigger=trig,
                              threshold=max(1, int(payload.threshold or 1)),
                              checklist_id=payload.checklist_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    log_action(db, user, "inspection_rule_create", "article_type", payload.type_id,
               {"trigger": trig, "threshold": r.threshold})
    return _rule_out(r)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_roles("admin", "verwalter"))):
    r = db.query(models.InspectionRule).get(rule_id)
    if r:
        db.delete(r)
        db.commit()
        log_action(db, user, "inspection_rule_delete", "inspection_rule", rule_id)
    return {"ok": True}
