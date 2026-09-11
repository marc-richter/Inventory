import datetime as dt
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MaterialRequestCreate(BaseModel):
    type_id: Optional[int] = None
    size: str = ""
    quantity: int = 1
    desired_from: Optional[dt.datetime] = None
    desired_until: Optional[dt.datetime] = None
    note: str = ""


class MaterialRequestDecision(BaseModel):
    status: str
    decision_note: str = ""


class MaterialRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requester_user_id: int
    requester_name: Optional[str] = None
    type_id: Optional[int] = None
    type_name: Optional[str] = None
    size: str = ""
    quantity: int = 1
    desired_from: Optional[dt.datetime] = None
    desired_until: Optional[dt.datetime] = None
    note: str = ""
    status: str = "open"
    handled_by_name: Optional[str] = None
    handled_at: Optional[dt.datetime] = None
    decision_note: str = ""
    created_at: dt.datetime