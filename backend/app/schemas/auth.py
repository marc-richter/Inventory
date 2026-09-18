from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from .leerwerte import leeres_dict, leere_liste


class UserCreate(BaseModel):
    username: str
    full_name: str = ""
    roles: List[str] = ["helfer"]
    person_id: Optional[int] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    pin_length: Optional[int] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    roles: Optional[List[str]] = None
    person_id: Optional[int] = None
    active: Optional[bool] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    pin_length: Optional[int] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    roles: List[str] = []
    person_id: Optional[int] = None
    active: bool
    pin_length: int
    has_password: bool = False
    has_pin: bool = False
    capabilities: List[str] = []
    revoked_capabilities: List[str] = []
    telegram_linked: bool = False
    reminder_days_before: Optional[int] = None
    analytics_access: bool = False
    _leer_roles_revoked_capabilities = leere_liste('roles', 'revoked_capabilities')



class RevokedCapabilities(BaseModel):
    revoked: List[str] = []


class ReminderSetting(BaseModel):
    days: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    pin: Optional[str] = None


class ChangePinRequest(BaseModel):
    old_pin: Optional[str] = None
    new_pin: str


class ChangePasswordRequest(BaseModel):
    old_password: Optional[str] = None
    new_password: str


class PinInfoOut(BaseModel):
    pin_length: int
    has_password: bool
    has_pin: bool


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    pin: Optional[str] = None
    password: Optional[str] = None


class RegisterInfoOut(BaseModel):
    enabled: bool
    pin_length: int
    require_password: bool
    require_fullname: bool


class RolePermissionsUpdate(BaseModel):
    permissions: dict