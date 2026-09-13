"""Reifen eines Fahrzeugs oder Anhaengers.

Bewusst eine Zeile je Reifen statt vier feste Felder: es gibt Fahrzeuge mit
Zwillingsbereifung (sechs Raeder), Anhaenger mit zweien und ueberall
Reserveraeder. Die Position ist deshalb Freitext.
"""

import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app import models, security
from app.audit import log_action
from app.database import get_db

router = APIRouter(prefix="/api/v1/tires", tags=["tires"])

# Uebliche Positionen als Vorschlag - frei ueberschreibbar.
VORSCHLAEGE = ["vorne links", "vorne rechts", "hinten links", "hinten rechts",
               "hinten links außen", "hinten rechts außen", "Reserve"]


class TireIn(BaseModel):
    position: str
    target_pressure: str = ""
    dot: str = ""
    size: str = ""
    changed_at: Optional[dt.datetime] = None
    note: str = ""
    sort_order: int = 100


class TireUpdate(BaseModel):
    position: Optional[str] = None
    target_pressure: Optional[str] = None
    dot: Optional[str] = None
    size: Optional[str] = None
    changed_at: Optional[dt.datetime] = None
    note: Optional[str] = None
    sort_order: Optional[int] = None


class TireOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    position: str
    target_pressure: str = ""
    dot: str = ""
    size: str = ""
    changed_at: Optional[dt.datetime] = None
    note: str = ""
    sort_order: int = 100
    # Aus der DOT-Nummer errechnet; None, wenn keine oder eine unplausible
    # Nummer hinterlegt ist.
    age_years: Optional[float] = None


def _fahrzeug(db: Session, article_id: int) -> models.Article:
    a = db.get(models.Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return a


@router.get("/suggestions")
def positions_vorschlaege(user=Depends(security.get_current_user)):
    return {"positions": VORSCHLAEGE}


@router.get("/{article_id}", response_model=List[TireOut])
def list_tires(article_id: int, db: Session = Depends(get_db),
               user=Depends(security.get_current_user)):
    _fahrzeug(db, article_id)
    return (db.query(models.VehicleTire)
            .filter(models.VehicleTire.article_id == article_id)
            .order_by(models.VehicleTire.sort_order, models.VehicleTire.position).all())


@router.post("/{article_id}", response_model=TireOut)
def add_tire(article_id: int, payload: TireIn, db: Session = Depends(get_db),
             user=Depends(security.require_capability("maintenance", "articles"))):
    a = _fahrzeug(db, article_id)
    reifen = models.VehicleTire(article_id=a.id, **payload.model_dump())
    db.add(reifen)
    db.commit()
    db.refresh(reifen)
    log_action(db, user, "tire_add", "article", a.id, {"position": reifen.position})
    return reifen


@router.put("/{tire_id}", response_model=TireOut)
def update_tire(tire_id: int, payload: TireUpdate, db: Session = Depends(get_db),
                user=Depends(security.require_capability("maintenance", "articles"))):
    reifen = db.get(models.VehicleTire, tire_id)
    if not reifen:
        raise HTTPException(status_code=404, detail="Reifen nicht gefunden")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(reifen, k, v)
    db.commit()
    db.refresh(reifen)
    log_action(db, user, "tire_update", "article", reifen.article_id, {"tire_id": tire_id})
    return reifen


@router.delete("/{tire_id}")
def delete_tire(tire_id: int, db: Session = Depends(get_db),
                user=Depends(security.require_capability("maintenance", "articles"))):
    reifen = db.get(models.VehicleTire, tire_id)
    if reifen:
        article_id = reifen.article_id
        db.delete(reifen)
        db.commit()
        log_action(db, user, "tire_delete", "article", article_id, {"tire_id": tire_id})
    return {"ok": True}


@router.post("/{article_id}/standard", response_model=List[TireOut])
def create_standard_set(article_id: int, achsen: int = 2, db: Session = Depends(get_db),
                        user=Depends(security.require_capability("maintenance", "articles"))):
    """Legt einen ueblichen Satz an (zwei Achsen = vier Reifen), damit nicht jeder
    Reifen einzeln eingetippt werden muss. Vorhandene bleiben unberuehrt."""
    a = _fahrzeug(db, article_id)
    achsen = max(1, min(4, int(achsen)))
    vorhanden = {r.position for r in db.query(models.VehicleTire)
                 .filter(models.VehicleTire.article_id == a.id).all()}
    order = 10
    for achse in range(1, achsen + 1):
        for seite in ("links", "rechts"):
            pos = f"Achse {achse} {seite}"
            if pos not in vorhanden:
                db.add(models.VehicleTire(article_id=a.id, position=pos, sort_order=order))
            order += 10
    db.commit()
    log_action(db, user, "tire_standard_set", "article", a.id, {"achsen": achsen})
    return (db.query(models.VehicleTire)
            .filter(models.VehicleTire.article_id == a.id)
            .order_by(models.VehicleTire.sort_order, models.VehicleTire.position).all())
