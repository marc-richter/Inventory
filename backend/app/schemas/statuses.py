from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class StatusDefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    label: str
    sort_order: int = 100
    is_builtin: bool = False
    active: bool = True
    category_ids: List[int] = []
    require_note: bool = False
    allow_image: bool = False
    issue_policy: str = "confirm"


class StatusDefCreate(BaseModel):
    key: Optional[str] = None
    label: str
    sort_order: int = 100
    category_ids: List[int] = []
    require_note: bool = False
    allow_image: bool = False
    issue_policy: str = "confirm"


class StatusDefUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    category_ids: Optional[List[int]] = None
    require_note: Optional[bool] = None
    allow_image: Optional[bool] = None
    issue_policy: Optional[str] = None