import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DocTemplateCreate(BaseModel):
    use_case: Optional[str] = None
    name: str = ""
    active: bool = True
    header_height_mm: int = 28
    footer_height_mm: int = 14
    elements: List[dict] = []


class DocTemplateUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    header_height_mm: Optional[int] = None
    footer_height_mm: Optional[int] = None
    elements: Optional[List[dict]] = None


class DocTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    use_case: Optional[str] = None
    name: str = ""
    active: bool = True
    header_height_mm: int = 28
    footer_height_mm: int = 14
    elements: List[dict] = []
    background_kind: str = ""