from typing import Optional, Dict, List
from pydantic import BaseModel, ConfigDict, field_validator


class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    # Haupt-Abteilung (steht auf Etiketten und in Listen, wo nur eine hinpasst)
    organization_id: Optional[int] = None
    # Weitere Abteilungen, in denen die Person ebenfalls ist
    organization_ids: Optional[List[int]] = None
    notes: str = ""


class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_id: Optional[int] = None
    organization_ids: Optional[List[int]] = None
    notes: Optional[str] = None
    active: Optional[bool] = None
    hidden: Optional[bool] = None
    sizes: Optional[Dict[str, str]] = None


class SizesUpdate(BaseModel):
    sizes: Dict[str, str] = {}


class SizeFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    sort_order: int = 100
    active: bool = True
    options: List[str] = []

    @field_validator("options", mode="before")
    @classmethod
    def _opts(cls, v):
        return v or []


class SizeFieldCreate(BaseModel):
    label: str
    options: List[str] = []


class SizeFieldUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    options: Optional[List[str]] = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    organization_id: Optional[int] = None
    organization_ids: List[int] = []
    organization_names: List[str] = []
    notes: str = ""
    active: bool = True
    hidden: bool = False
    sizes: Dict[str, str] = {}

    @field_validator("sizes", mode="before")
    @classmethod
    def _sizes_none_to_dict(cls, v):
        return v or {}