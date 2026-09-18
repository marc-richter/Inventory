from datetime import datetime
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


# --------------------------- Schlüsselbünde ---------------------------------

class KeyRingCreate(BaseModel):
    name: str
    code: Optional[str] = None
    note: str = ""
    # Schlüssel, die gleich an den Bund gehängt werden sollen.
    article_ids: List[int] = []


class KeyRingUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    note: Optional[str] = None
    active: Optional[bool] = None


class KeyRingMemberOut(BaseModel):
    article_id: int
    artikelnummer: str
    key_alias: str = ""
    key_serial: str = ""
    key_type_name: Optional[str] = None
    key_group: str = ""
    status: str = ""
    holder: Optional[str] = None
    locks: List[KeyLockOut] = []


class KeyRingOut(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    note: str = ""
    active: bool = True
    keys: List[KeyRingMemberOut] = []
    # Zusammenfassung über alle Schlüssel am Bund.
    schluessel_anzahl: int = 0
    oeffnet: List[KeyLockOut] = []
    # Wer den Bund gerade hat - nur gesetzt, wenn ALLE Schlüssel bei derselben
    # Person sind. Sonst ist der Bund auseinandergerissen und das soll auffallen.
    holder: Optional[str] = None
    vollstaendig_da: bool = True


class KeyRingMembersSet(BaseModel):
    article_ids: List[int] = []


class KeyRingIssue(BaseModel):
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    notes: str = ""
    expected_return_date: Optional[datetime] = None
    deposit_amount: str = ""
    confirm: bool = False


# Vorwärtsreferenzen auflösen.
LockObjectOut.model_rebuild()
KeyLockOut.model_rebuild()