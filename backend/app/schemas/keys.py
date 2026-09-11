from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class KeyTypeCreate(BaseModel):
    name: str


class KeyTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    active: bool = True


class LockCreate(BaseModel):
    name: str
    note: str = ""
    sort_order: int = 100


class LockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    object_id: int
    name: str
    note: str = ""
    sort_order: int = 100


class LockObjectCreate(BaseModel):
    name: str
    storage_location_id: Optional[int] = None
    vehicle_article_id: Optional[int] = None
    note: str = ""


class LockObjectUpdate(BaseModel):
    name: Optional[str] = None
    storage_location_id: Optional[int] = None
    vehicle_article_id: Optional[int] = None
    note: Optional[str] = None


class LockObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    storage_location_id: Optional[int] = None
    vehicle_article_id: Optional[int] = None
    storage_node_id: Optional[int] = None
    note: str = ""
    locks: List[LockOut] = []


class KeyLockOut(BaseModel):
    lock_id: int
    name: str
    object_id: int
    object_name: str


class KeyLocksSet(BaseModel):
    lock_ids: List[int] = []


class DepositReturn(BaseModel):
    deposit_returned: bool = True


# Vorwärtsreferenzen auflösen.
LockObjectOut.model_rebuild()
KeyLockOut.model_rebuild()