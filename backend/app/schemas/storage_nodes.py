from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class StorageNodeCreate(BaseModel):
    parent_id: Optional[int] = None
    level: Optional[str] = None
    name: str
    description: str = ""
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_fax: str = ""
    contact_email: str = ""


class VehicleNodeRequest(BaseModel):
    parent_id: Optional[int] = None


class StorageNodeUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_fax: Optional[str] = None
    contact_email: Optional[str] = None


class StorageNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: Optional[int] = None
    level: str
    name: str
    description: str = ""
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_fax: str = ""
    contact_email: str = ""
    sort_order: int = 100
    vehicle_article_id: Optional[int] = None
    code: Optional[str] = None
    is_lock: bool = False
    cylinders: List["CylinderOut"] = []


class CylinderOut(BaseModel):
    id: int
    name: str
    note: str = ""


class CylinderCreate(BaseModel):
    name: str
    note: str = ""


class NodeInventoryRequest(BaseModel):
    artikelnummern: List[str] = []
    move: bool = True


# Vorwärtsreferenzen auflösen.
StorageNodeOut.model_rebuild()