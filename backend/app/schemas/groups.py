from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupOut(BaseModel):
    id: int
    name: str
    description: str = ""
    member_count: int = 0
    members: List[dict] = []