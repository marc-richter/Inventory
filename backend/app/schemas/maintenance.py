import datetime as dt
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


class MaintenanceFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    position: int = 0


class MaintReminderIn(BaseModel):
    days_before: int = 7
    urgency: str = "normal"


class MaintReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    days_before: int = 7
    urgency: str = "normal"


class MaintenanceTypeCreate(BaseModel):
    name: str
    description: str = ""
    checklist_id: Optional[int] = None
    interval_months: Optional[int] = None
    interval_km: Optional[int] = None
    km_based: bool = False
    trigger_event: str = ""
    fields: List[str] = []
    reminders: List[MaintReminderIn] = []


class MaintenanceTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    checklist_id: Optional[int] = None
    interval_months: Optional[int] = None
    interval_km: Optional[int] = None
    km_based: Optional[bool] = None
    trigger_event: Optional[str] = None
    fields: Optional[List[str]] = None
    reminders: Optional[List[MaintReminderIn]] = None


class MaintenanceTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str = ""
    active: bool = True
    checklist_id: Optional[int] = None
    checklist_name: Optional[str] = None
    interval_months: Optional[int] = None
    interval_km: Optional[int] = None
    km_based: bool = False
    trigger_event: str = ""
    sort_order: int = 100
    fields: List[MaintenanceFieldOut] = []
    reminders: List[MaintReminderOut] = []


class MaintDueOut(BaseModel):
    schedule_id: int
    article_id: int
    artikelnummer: Optional[str] = None
    mtype_name: str
    due_date: Optional[dt.datetime] = None
    due_km: Optional[int] = None
    overdue: bool = False
    days_until: Optional[int] = None


class MaintenanceAssignmentCreate(BaseModel):
    mtype_id: int
    category_id: Optional[int] = None
    article_type_id: Optional[int] = None
    article_id: Optional[int] = None
    mode: str = "include"


class MaintenanceAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mtype_id: int
    mtype_name: Optional[str] = None
    category_id: Optional[int] = None
    article_type_id: Optional[int] = None
    article_id: Optional[int] = None
    mode: str = "include"


class ArticleMaintScheduleIn(BaseModel):
    mtype_id: int
    due_date: Optional[dt.datetime] = None
    due_km: Optional[int] = None
    note: str = ""
    # Abweichendes Intervall NUR fuer diesen Artikel (0 oder null = Intervall der
    # Pruefart verwenden). Damit laesst sich die HU je Fahrzeug auf 12 Monate oder
    # einen beliebigen anderen Wert stellen, und die SP je Fahrzeug abschalten.
    interval_months: Optional[int] = None
    interval_km: Optional[int] = None


class ArticleMaintOut(BaseModel):
    mtype_id: int
    mtype_name: str
    source: str
    km_based: bool = False
    interval_months: Optional[int] = None
    interval_km: Optional[int] = None
    # True, wenn das Intervall am Artikel abweichend hinterlegt ist (z.B. HU 12
    # statt 24 Monate) - damit die Oberflaeche das kenntlich machen kann.
    interval_overridden: bool = False
    schedule_id: Optional[int] = None
    due_date: Optional[dt.datetime] = None
    due_km: Optional[int] = None
    last_done_at: Optional[dt.datetime] = None
    last_done_km: Optional[int] = None
    note: str = ""


class MaintenanceFinishIn(BaseModel):
    result: str = "passed"
    overall_note: str = ""
    field_values: Dict[str, str] = {}
    done_date: Optional[dt.datetime] = None
    done_km: Optional[int] = None
    reschedule: str = "interval"
    next_due_date: Optional[dt.datetime] = None
    next_due_km: Optional[int] = None