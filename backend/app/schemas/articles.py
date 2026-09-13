import datetime as dt
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


class ArticleCreate(BaseModel):
    artikelnummer: Optional[str] = None
    category_id: int
    type_id: int
    size: str = ""
    model: str = ""
    model_id: Optional[int] = None
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    storage_node_id: Optional[int] = None
    etage: str = ""
    raum: str = ""
    schrank: str = ""
    fach: str = ""
    condition_notes: str = ""
    remarks: str = ""
    issuable_override: Optional[bool] = None
    is_psa: bool = False
    is_vehicle: bool = False
    license_plate: str = ""
    vin: str = ""
    first_registration: Optional[dt.datetime] = None
    key_type_id: Optional[int] = None
    key_serial: str = ""
    key_alias: str = ""
    key_group: str = ""
    custom_values: Dict[str, str] = {}
    first_entry_date: Optional[dt.datetime] = None
    review_assignee_id: Optional[int] = None


class ArticleUpdate(BaseModel):
    type_id: Optional[int] = None
    size: Optional[str] = None
    model: Optional[str] = None
    model_id: Optional[int] = None
    properties: Optional[str] = None
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    storage_node_id: Optional[int] = None
    etage: Optional[str] = None
    raum: Optional[str] = None
    schrank: Optional[str] = None
    fach: Optional[str] = None
    condition_notes: Optional[str] = None
    remarks: Optional[str] = None
    issuable_override: Optional[bool] = None
    is_psa: Optional[bool] = None
    is_vehicle: Optional[bool] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    first_registration: Optional[dt.datetime] = None
    key_type_id: Optional[int] = None
    key_serial: Optional[str] = None
    key_alias: Optional[str] = None
    key_group: Optional[str] = None
    custom_values: Optional[Dict[str, str]] = None


class ImportFieldSet(BaseModel):
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
    resolution: str
    imported: ImportFieldSet


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str] = []


class BulkArticleCreate(BaseModel):
    category_id: int
    type_id: int
    size: str = ""
    model: str = ""
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    condition_notes: str = ""
    remarks: str = ""
    is_psa: Optional[bool] = None
    custom_values: Dict[str, str] = {}
    first_entry_date: Optional[dt.datetime] = None
    quantity: Optional[int] = None
    artikelnummern: Optional[List[str]] = None


class StatusChangeRequest(BaseModel):
    status: str
    note: str = ""
    repair_expected_return: Optional[dt.datetime] = None
    repair_reason: Optional[str] = None
    repair_location: Optional[str] = None
    reason: Optional[str] = None
    condition_note: Optional[str] = None


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
    expected_return_date: Optional[dt.datetime] = None
    return_date: Optional[dt.datetime] = None
    condition_at_return: str = ""
    notes: str = ""
    issued_by_user_id: Optional[int] = None
    returned_by_user_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    returned_by_name: Optional[str] = None
    deposit_amount: str = ""
    deposit_returned: bool = False


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    artikelnummer: str
    category_id: int
    type_id: int
    size: str
    model: str = ""
    model_id: Optional[int] = None
    properties: str = ""
    organization_id: Optional[int] = None
    storage_location_id: Optional[int] = None
    storage_node_id: Optional[int] = None
    location_path: str = ""
    etage: str = ""
    raum: str = ""
    schrank: str = ""
    fach: str = ""
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
    provisional: bool = False
    provisional_by_name: Optional[str] = None
    review_assignee_id: Optional[int] = None
    review_assignee_name: Optional[str] = None
    issuable_override: Optional[bool] = None
    is_issuable: bool = True
    is_psa: bool = False
    loan_count: int = 0
    wash_count: int = 0
    last_inspection_at: Optional[dt.datetime] = None
    pending_checklist_id: Optional[int] = None
    needs_inspection: bool = False
    inspection_override: bool = False
    is_vehicle: bool = False
    license_plate: str = ""
    vin: str = ""
    first_registration: Optional[dt.datetime] = None
    vehicle_node_id: Optional[int] = None
    key_type_id: Optional[int] = None
    key_type_name: Optional[str] = None
    key_serial: str = ""
    key_alias: str = ""
    key_group: str = ""
    is_key: bool = False
    locks: List["KeyLockOut"] = []
    custom_values: Dict[str, str] = {}
    images: List[ImageOut] = []
    issues: List[IssueOut] = []

    @field_validator("custom_values", mode="before")
    @classmethod
    def _cv(cls, v):
        return {str(k): ("" if x is None else str(x)) for k, x in (v or {}).items()}


class IssueCreate(BaseModel):
    article_id: int
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    issue_date: Optional[dt.datetime] = None
    expected_return_date: Optional[dt.datetime] = None
    notes: str = ""
    deposit_amount: str = ""
    confirm: bool = False
    reissue: bool = False


class BatchIssueItem(BaseModel):
    article_id: int
    confirm: bool = False
    reissue: bool = False


class BatchIssueRequest(BaseModel):
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    issue_date: Optional[dt.datetime] = None
    expected_return_date: Optional[dt.datetime] = None
    notes: str = ""
    items: List[BatchIssueItem] = []


class AssignReviewRequest(BaseModel):
    user_id: Optional[int] = None


class RelocateRequest(BaseModel):
    storage_node_id: Optional[int] = None
    campaign_id: Optional[int] = None
    article_ids: List[int] = []


class InventoryConfigRequest(BaseModel):
    ignore_status: List[str] = []


class ArticlePaginatedOut(BaseModel):
    items: List[ArticleOut]
    total: int
    skip: int
    limit: int


# Forward reference resolution - import at the end to avoid circular imports
from app.schemas.keys import KeyLockOut

# Vorwärtsreferenzen auflösen.
ArticleOut.model_rebuild()
IssueOut.model_rebuild()