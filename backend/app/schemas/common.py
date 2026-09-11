from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


class LookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class RenameRequest(BaseModel):
    name: str