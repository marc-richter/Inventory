import datetime as dt
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LogEntryCreate(BaseModel):
    entry_date: Optional[dt.datetime] = None
    kind: str = "hinweis"
    title: str = ""
    note: str = ""
    km: Optional[int] = None


class LogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    entry_date: Optional[dt.datetime] = None
    kind: str = "hinweis"
    title: str = ""
    note: str = ""
    km: Optional[int] = None
    source: str = "manual"
    created_by_name: Optional[str] = None