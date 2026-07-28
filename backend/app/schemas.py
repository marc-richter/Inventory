import datetime as dt
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class LookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CategoryCreate(BaseModel):
    name: str


class TypeCreate(BaseModel):
    name: str
    category_id: int


class OrganizationCreate(BaseModel):
    name: str


class StorageLocationCreate(BaseModel):
    name: str


class RenameRequest(BaseModel):
    name: str


class TypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category_id: int


# --- Users / Auth ---

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


# --- Person ---

class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    organization_id: Optional[int] = None
    notes: str = ""


class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_id: Optional[int] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    organization_id: Optional[int] = None
    notes: str = ""
    active: bool = True


# --- Article ---

class ArticleCreate(BaseModel):
    artikelnummer: Optional[str] = None
    category_id: int
    type_id: int
    size: str = ""
    model: str = ""
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    condition_notes: str = ""
    remarks: str = ""
    first_entry_date: Optional[dt.datetime] = None


class ArticleUpdate(BaseModel):
    # Bewusst NICHT enthalten (nachtraeglich unveraenderbar): first_entry_date,
    # created_by, artikelnummer.
    type_id: Optional[int] = None
    size: Optional[str] = None
    model: Optional[str] = None
    properties: Optional[str] = None
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    condition_notes: Optional[str] = None
    remarks: Optional[str] = None


class ImportFieldSet(BaseModel):
    """Ein Satz von Artikel-Feldern in Klartext (Namen statt IDs), wie er aus
    einer CSV-Datei gelesen bzw. fuer den Vergleich mit einem bestehenden
    Artikel aufbereitet wird."""
    category_name: str = ""
    type_name: str = ""
    size: str = ""
    organization_name: str = ""
    storage_location_name: str = ""
    status: str = ""
    first_entry_date: str = ""
    condition_notes: str = ""
    remarks: str = ""


class ImportPreviewRow(BaseModel):
    artikelnummer: str
    is_duplicate: bool
    imported: ImportFieldSet
    existing: Optional[ImportFieldSet] = None
    existing_article_id: Optional[int] = None
    error: Optional[str] = None


class ImportPreviewOut(BaseModel):
    total_rows: int
    new_count: int
    duplicate_count: int
    error_count: int
    rows: List[ImportPreviewRow]


class ImportCommitRow(BaseModel):
    artikelnummer: str
    resolution: str  # "create_new" | "keep_existing" | "keep_imported"
    imported: ImportFieldSet


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str] = []


class BulkArticleCreate(BaseModel):
    """Mengenerfassung: legt mehrere baugleiche Artikel auf einmal an.

    Entweder `quantity` angeben (Anzahl automatisch fortlaufend vergebener
    Artikelnummern), oder `artikelnummern` mit einer Liste manuell
    eingegebener bzw. eingescannter Nummern - es muss genau eines von
    beidem befuellt sein."""
    category_id: int
    type_id: int
    size: str = ""
    model: str = ""
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    condition_notes: str = ""
    remarks: str = ""
    first_entry_date: Optional[dt.datetime] = None
    quantity: Optional[int] = None
    artikelnummern: Optional[List[str]] = None


class StatusChangeRequest(BaseModel):
    status: str
    note: str = ""
    repair_expected_return: Optional[dt.datetime] = None
    repair_reason: Optional[str] = None
    repair_location: Optional[str] = None   # Reparaturort -> wird neuer Standort/Lagerort
    reason: Optional[str] = None            # z.B. Grund beim Aussondern (Pflicht)
    condition_note: Optional[str] = None    # Pflicht-Beschreibung bei require_note-Status (z.B. Beschädigung)


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filepath: str
    kind: str = "normal"
    uploaded_at: dt.datetime


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    issue_date: dt.datetime
    return_date: Optional[dt.datetime] = None
    condition_at_return: str = ""
    notes: str = ""
    issued_by_user_id: Optional[int] = None
    returned_by_user_id: Optional[int] = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    artikelnummer: str
    category_id: int
    type_id: int
    size: str
    model: str = ""
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    current_location: str = ""
    status: str
    condition_notes: str
    remarks: str
    repair_expected_return: Optional[dt.datetime] = None
    repair_reason: str = ""
    retire_reason: str = ""
    first_entry_date: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    images: List[ImageOut] = []
    issues: List[IssueOut] = []


class IssueCreate(BaseModel):
    article_id: int
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    issue_date: Optional[dt.datetime] = None
    notes: str = ""


class ReturnCreate(BaseModel):
    condition_at_return: str = ""
    notes: str = ""
    return_date: Optional[dt.datetime] = None


# --- Status (konfigurierbar) ---

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


class StatusDefCreate(BaseModel):
    key: Optional[str] = None          # leer -> automatisch aus label erzeugt
    label: str
    sort_order: int = 100
    category_ids: List[int] = []
    require_note: bool = False
    allow_image: bool = False


class StatusDefUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    category_ids: Optional[List[int]] = None
    require_note: Optional[bool] = None
    allow_image: Optional[bool] = None


# --- Selbstregistrierung ---

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
    permissions: dict   # {rolle: [capability, ...]}


class MergePersonsRequest(BaseModel):
    source_id: int   # wird in target zusammengefuehrt und entfernt/deaktiviert
    target_id: int


class MergeUsersRequest(BaseModel):
    source_id: int   # Quell-Benutzer, wird in target zusammengefuehrt und geloescht
    target_id: int


class UpdateInstallRequest(BaseModel):
    ref: str   # Release-Tag (z.B. "v1.9.0") oder Branch (z.B. "dev")


class SettingsUpdate(BaseModel):
    pin_length_default: Optional[int] = None
    backup_dir: Optional[str] = None
    backup_auto_enabled: Optional[bool] = None
    backup_auto_time: Optional[str] = None
    backup_retention: Optional[int] = None
    label_width_mm: Optional[int] = None
    label_height_mm: Optional[int] = None
    label_code_format: Optional[str] = None   # "qr" | "code128" | "code39"
    label_fields: Optional[str] = None        # kommagetrennte Feldschluessel (Reihenfolge = Druckreihenfolge)
    label_maxlen: Optional[str] = None        # JSON {feld: max_zeichen}
    org_name: Optional[str] = None
    printer_connection_type: Optional[str] = None   # "network" oder "usb"
    printer_ip: Optional[str] = None
    printer_model: Optional[str] = None
    selfreg_enabled: Optional[bool] = None
    selfreg_pin_length: Optional[int] = None
    selfreg_require_password: Optional[bool] = None
    selfreg_require_fullname: Optional[bool] = None
    selfreg_role: Optional[str] = None
    selfreg_match_existing: Optional[bool] = None
