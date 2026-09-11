import datetime as dt
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DamageReportCreate(BaseModel):
    article_id: int
    kind: str = "damage"
    description: str = ""
    incident_at: Optional[dt.datetime] = None
    incident_location: str = ""
    is_theft: bool = False
    police_reference: str = ""
    estimated_value: str = ""
    witnesses: str = ""
    reporter_contact: str = ""


class DamageReportUpdate(BaseModel):
    description: Optional[str] = None
    incident_at: Optional[dt.datetime] = None
    incident_location: Optional[str] = None
    is_theft: Optional[bool] = None
    police_reference: Optional[str] = None
    estimated_value: Optional[str] = None
    witnesses: Optional[str] = None
    reporter_contact: Optional[str] = None


class DamageReportResolve(BaseModel):
    resolution_note: str = ""


class DamageReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    artikelnummer: Optional[str] = None
    type_name: Optional[str] = None
    kind: str = "damage"
    reporter_name: Optional[str] = None
    description: str = ""
    incident_at: Optional[dt.datetime] = None
    incident_location: str = ""
    is_theft: bool = False
    police_reference: str = ""
    estimated_value: str = ""
    witnesses: str = ""
    reporter_contact: str = ""
    complete: bool = False
    has_photo: bool = False
    status: str = "open"
    handled_by_name: Optional[str] = None
    handled_at: Optional[dt.datetime] = None
    resolution_note: str = ""
    created_at: dt.datetime