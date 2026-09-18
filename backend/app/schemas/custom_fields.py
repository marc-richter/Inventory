from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from .leerwerte import leeres_dict, leere_liste


class CustomFieldCreate(BaseModel):
    label: str
    field_type: str = "text"
    options: List[str] = []
    category_id: Optional[int] = None
    article_type_id: Optional[int] = None
    required: bool = False


class CustomFieldUpdate(BaseModel):
    label: Optional[str] = None
    field_type: Optional[str] = None
    options: Optional[List[str]] = None
    required: Optional[bool] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class CustomFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    field_type: str = "text"
    options: List[str] = []
    category_id: Optional[int] = None
    article_type_id: Optional[int] = None
    required: bool = False
    sort_order: int = 100
    active: bool = True
    # Gesetzt bei mitgelieferten Standardfeldern: umbenennbar und ausblendbar,
    # aber nicht loeschbar - sonst zeigten erfasste Werte ins Leere.
    system_key: Optional[str] = None

    @field_validator("options", mode="before")
    @classmethod
    def _co(cls, v):
        return v or []
    _leer_options = leere_liste('options')
