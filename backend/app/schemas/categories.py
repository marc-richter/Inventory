from typing import Optional
from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    issuable_default: bool = True
    key_system: bool = False
    # Vom Programm mitgeliefert: nicht umbenennbar, nicht loeschbar, nur ausblendbar.
    system_key: Optional[str] = None
    is_system: bool = False
    active: bool = True
    # Schliessanlagen-Kennzeichen einschliesslich Vererbung von der Oberkategorie.
    effective_key_system: bool = False


class IssuableRequest(BaseModel):
    issuable: bool = True


class TypeCreate(BaseModel):
    name: str
    category_id: int


class TypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category_id: int
    min_stock: int = 0
    issuable_default: Optional[bool] = None
    is_psa_default: bool = False


class MinStockRequest(BaseModel):
    min_stock: int = 0


class TypeDefaults(BaseModel):
    issuable_default: Optional[bool] = None
    is_psa_default: bool = False


class ModelCreate(BaseModel):
    name: str
    type_id: int


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type_id: int
    active: bool = True


class OrganizationCreate(BaseModel):
    name: str


class StorageLocationCreate(BaseModel):
    name: str
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_fax: str = ""
    contact_email: str = ""


class StandortUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_fax: Optional[str] = None
    contact_email: Optional[str] = None


class StandortOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_fax: str = ""
    contact_email: str = ""
    needs_review: bool = False


class ClassifyStandortRequest(BaseModel):
    level: str
    parent_standort_id: Optional[int] = None
    parent_standort_name: Optional[str] = None
    above: dict = {}


class MaterialManagerCreate(BaseModel):
    user_id: int
    organization_id: Optional[int] = None
    category_id: Optional[int] = None


class MaterialManagerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    user_name: Optional[str] = None
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None


class MinStockRuleCreate(BaseModel):
    type_id: int
    size: str = ""
    node_id: Optional[int] = None
    min_stock: int = 0


class MinStockRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type_id: int
    type_name: Optional[str] = None
    category_id: Optional[int] = None
    size: str = ""
    node_id: Optional[int] = None
    node_path: Optional[str] = None
    min_stock: int = 0