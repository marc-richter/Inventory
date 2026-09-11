import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class InventoryParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    role: str
    user_name: Optional[str] = None


class InventoryCampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    scope_type: str
    status: str
    ignore_status: str = ""
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    started_at: Optional[dt.datetime] = None
    ended_at: Optional[dt.datetime] = None
    notes: str = ""
    reminder_days_before: int = 3
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    scope_node_ids: List[int] = []
    scope_category_ids: List[int] = []
    participants: List[InventoryParticipantOut] = []
    expected_count: Optional[int] = None
    found_count: Optional[int] = None
    open_count: Optional[int] = None
    ignored_count: Optional[int] = None
    can_manage: Optional[bool] = None


class InventoryCampaignCreate(BaseModel):
    name: str
    scope_type: str = "full"
    ignore_status: List[str] = ["ausgegeben", "reparatur", "ausgemustert"]
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    notes: str = ""
    reminder_days_before: Optional[int] = None
    scope_node_ids: List[int] = []
    scope_category_ids: List[int] = []


class InventoryCampaignUpdate(BaseModel):
    name: Optional[str] = None
    scope_type: Optional[str] = None
    ignore_status: Optional[List[str]] = None
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    notes: Optional[str] = None
    reminder_days_before: Optional[int] = None
    scope_node_ids: Optional[List[int]] = None
    scope_category_ids: Optional[List[int]] = None


class InventoryParticipantAdd(BaseModel):
    user_id: int
    role: str = "helper"


class InventoryScanRequest(BaseModel):
    article_ids: List[int] = []
    storage_node_id: Optional[int] = None


class InventoryStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    node_id: Optional[int] = None
    label: str = ""
    status: str = "pending"
    note: str = ""
    node_path: Optional[str] = None
    done_by_name: Optional[str] = None
    done_at: Optional[dt.datetime] = None
    expected_count: Optional[int] = None
    found_count: Optional[int] = None
    open_count: Optional[int] = None


class InventoryStepCreate(BaseModel):
    node_id: Optional[int] = None
    label: str = ""


class InventoryStepReorder(BaseModel):
    ordered_ids: List[int] = []


class InventoryStepStatus(BaseModel):
    status: str = "done"
    note: Optional[str] = None


class InventoryStepsGenerate(BaseModel):
    node_ids: List[int] = []
    replace: bool = True


class InventoryTemplateStepIn(BaseModel):
    node_id: Optional[int] = None
    label: str = ""


class InventoryTemplateStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    node_id: Optional[int] = None
    label: str = ""
    node_path: Optional[str] = None


class InventoryTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    ignore_status: str = ""
    notes: str = ""
    created_by_name: Optional[str] = None
    steps: List[InventoryTemplateStepOut] = []


class InventoryTemplateCreate(BaseModel):
    name: str
    ignore_status: List[str] = ["ausgegeben", "reparatur", "ausgemustert"]
    notes: str = ""
    steps: List[InventoryTemplateStepIn] = []


class InventoryTemplateUpdate(BaseModel):
    name: Optional[str] = None
    ignore_status: Optional[List[str]] = None
    notes: Optional[str] = None
    steps: Optional[List[InventoryTemplateStepIn]] = None


class InventoryCampaignFromTemplates(BaseModel):
    name: str
    template_ids: List[int] = []
    planned_start: Optional[dt.datetime] = None
    participant_ids: List[int] = []
    reminder_days_before: Optional[int] = None


class InventoryScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    active: bool = True
    interval: int = 1
    unit: str = "month"
    next_run: Optional[dt.datetime] = None
    last_run: Optional[dt.datetime] = None
    ignore_status: str = ""
    notes: str = ""
    reminder_days_before: int = 3
    weekday: Optional[int] = None
    week_of_month: Optional[int] = None
    template_ids: List[int] = []
    template_names: List[str] = []
    participant_ids: List[int] = []


class InventoryScheduleCreate(BaseModel):
    name: str
    template_ids: List[int] = []
    interval: int = 1
    unit: str = "month"
    weekday: Optional[int] = None
    week_of_month: Optional[int] = None
    start_date: Optional[dt.datetime] = None
    ignore_status: Optional[List[str]] = None
    participant_ids: List[int] = []
    reminder_days_before: Optional[int] = None
    notes: str = ""


class InventoryScheduleUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    template_ids: Optional[List[int]] = None
    interval: Optional[int] = None
    unit: Optional[str] = None
    weekday: Optional[int] = None
    week_of_month: Optional[int] = None
    next_run: Optional[dt.datetime] = None
    ignore_status: Optional[List[str]] = None
    participant_ids: Optional[List[int]] = None
    reminder_days_before: Optional[int] = None
    notes: Optional[str] = None