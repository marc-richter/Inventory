import datetime as dt
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PrinterCreate(BaseModel):
    name: str
    kind: str = "paper"
    conn: str = "cups"
    cups_queue: str = ""
    host: str = ""
    port: int = 9100
    options: str = ""
    active: bool = True


class PrinterUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    conn: Optional[str] = None
    cups_queue: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    options: Optional[str] = None
    active: Optional[bool] = None


class PrinterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: str = "paper"
    conn: str = "cups"
    cups_queue: str = ""
    host: str = ""
    port: int = 9100
    options: str = ""
    active: bool = True
    last_status: str = ""
    last_status_at: Optional[dt.datetime] = None


class CupsInstallRequest(BaseModel):
    name: str
    uri: str
    ppd: str = ""
    kind: str = "paper"
    create_profile: bool = True


class PrinterAssignmentCreate(BaseModel):
    use_case: str
    printer_id: int
    format_options: str = ""
    sort_order: int = 100


class PrinterAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    use_case: str
    printer_id: int
    format_options: str = ""
    sort_order: int = 100
    printer: Optional[PrinterOut] = None