import datetime as dt
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    article_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    filename: str = ""
    signed: bool = False
    created_at: dt.datetime


class ReceiptDigital(BaseModel):
    person_id: int
    kind: str = "issue"
    copies: int = 1
    include_existing: bool = False
    sig_issuer: Optional[str] = None
    sig_recipient: Optional[str] = None
    note: str = ""


class KeyDocDigital(BaseModel):
    article_id: int
    sig_issuer: Optional[str] = None
    sig_recipient: Optional[str] = None
    note: str = ""