import datetime as dt
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


class ReturnCreate(BaseModel):
    condition_at_return: str = ""
    notes: str = ""
    return_date: Optional[dt.datetime] = None


class ChecklistItemIn(BaseModel):
    label: str


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    label: str


class ChecklistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    items: List[ChecklistItemOut] = []


class ChecklistCreate(BaseModel):
    name: str
    items: List[ChecklistItemIn] = []


class ChecklistUpdate(BaseModel):
    name: Optional[str] = None
    items: Optional[List[ChecklistItemIn]] = None


class InspectionRuleCreate(BaseModel):
    type_id: int
    trigger: str = "return"
    threshold: int = 1
    checklist_id: Optional[int] = None


class ArticleRuleCreate(BaseModel):
    trigger: str = "return"
    threshold: int = 1
    checklist_id: Optional[int] = None


class OverrideToggle(BaseModel):
    enabled: bool = False


class InspectionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type_id: int
    type_name: Optional[str] = None
    article_id: Optional[int] = None
    trigger: str
    threshold: int = 1
    checklist_id: Optional[int] = None
    checklist_name: Optional[str] = None


class InspectionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    label: str
    ok: Optional[bool] = None
    note: str = ""


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    artikelnummer: Optional[str] = None
    checklist_name: str = ""
    status: str = "open"
    result: str = ""
    overall_note: str = ""
    has_document: bool = False
    started_by_name: Optional[str] = None
    finished_by_name: Optional[str] = None
    started_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    maintenance_id: Optional[int] = None
    field_values: Dict[str, str] = {}
    results: List[InspectionItemOut] = []

    @field_validator("field_values", mode="before")
    @classmethod
    def _fv(cls, v):
        return v or {}


class InspectionStart(BaseModel):
    article_id: int


class InspectionItemUpdate(BaseModel):
    item_id: int
    ok: Optional[bool] = None
    note: Optional[str] = None


class InspectionFinish(BaseModel):
    result: str = "passed"
    target_status: Optional[str] = None
    overall_note: str = ""