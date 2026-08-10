import datetime as dt
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


class LookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CategoryCreate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    issuable_default: bool = True


class IssuableRequest(BaseModel):
    issuable: bool = True


class TypeCreate(BaseModel):
    name: str
    category_id: int


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
    level: str                              # 'standort'|'etage'|'raum'|'schrank'|'fach'
    parent_standort_id: Optional[int] = None
    parent_standort_name: Optional[str] = None
    above: dict = {}                        # Werte fuer die Ebenen OBERHALB der gewaehlten


class RenameRequest(BaseModel):
    name: str


class TypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category_id: int
    min_stock: int = 0


class MinStockRequest(BaseModel):
    min_stock: int = 0


class MaterialManagerCreate(BaseModel):
    user_id: int
    organization_id: Optional[int] = None   # None = alle Abteilungen
    category_id: Optional[int] = None        # None = alle Klassen


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
    size: str = ""                           # "" = alle Groessen
    node_id: Optional[int] = None            # None = Gesamtbestand
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
    revoked_capabilities: List[str] = []
    telegram_linked: bool = False
    reminder_days_before: Optional[int] = None
    analytics_access: bool = False


class RevokedCapabilities(BaseModel):
    revoked: List[str] = []


class ReminderSetting(BaseModel):
    days: Optional[int] = None   # None = Standardwert der Inventur verwenden


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
    sizes: Optional[Dict[str, str]] = None


class SizesUpdate(BaseModel):
    sizes: Dict[str, str] = {}


class SizeFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    sort_order: int = 100
    active: bool = True


class SizeFieldCreate(BaseModel):
    label: str


class SizeFieldUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    organization_id: Optional[int] = None
    notes: str = ""
    active: bool = True
    sizes: Dict[str, str] = {}

    @field_validator("sizes", mode="before")
    @classmethod
    def _sizes_none_to_dict(cls, v):
        return v or {}


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
    storage_node_id: Optional[int] = None
    etage: str = ""
    raum: str = ""
    schrank: str = ""
    fach: str = ""
    condition_notes: str = ""
    remarks: str = ""
    issuable_override: Optional[bool] = None
    is_psa: bool = False
    first_entry_date: Optional[dt.datetime] = None
    review_assignee_id: Optional[int] = None   # nur fuer vorlaeufige Anlage


class ArticleUpdate(BaseModel):
    # Bewusst NICHT enthalten (nachtraeglich unveraenderbar): first_entry_date,
    # created_by, artikelnummer.
    type_id: Optional[int] = None
    size: Optional[str] = None
    model: Optional[str] = None
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
    expected_return_date: Optional[dt.datetime] = None
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
    images: List[ImageOut] = []
    issues: List[IssueOut] = []


class IssueCreate(BaseModel):
    article_id: int
    person_id: Optional[int] = None
    recipient_name_freetext: str = ""
    issue_date: Optional[dt.datetime] = None
    expected_return_date: Optional[dt.datetime] = None
    notes: str = ""
    confirm: bool = False   # Bestaetigung fuer Status mit issue_policy="confirm"
    reissue: bool = False   # bereits ausgegebenen Artikel zuruecknehmen + neu ausgeben


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
    user_id: Optional[int] = None   # None = Zuweisung entfernen


class RelocateRequest(BaseModel):
    """Inventur: die gescannten Artikel einem Standort-Knoten zuordnen. Optional wird
    die Zuordnung als Fund einer laufenden Kampagne verbucht."""
    storage_node_id: Optional[int] = None
    campaign_id: Optional[int] = None
    article_ids: List[int] = []


class InventoryConfigRequest(BaseModel):
    """Inventur-Einstellung: Status-Werte, die bei der Fehlliste ignoriert werden."""
    ignore_status: List[str] = []


# ---------- Benutzer-Gruppen / Funktionsrollen ----------

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


# ---------- Fest verwaltete Standort-Objekte (Baum) ----------

class StorageNodeCreate(BaseModel):
    parent_id: Optional[int] = None
    level: Optional[str] = None            # leer -> automatisch aus Elternebene ableiten
    name: str
    description: str = ""
    address: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_fax: str = ""
    contact_email: str = ""


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


# ---------- Inventur-Kampagnen ----------

class InventoryParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    role: str
    user_name: Optional[str] = None


class InventoryCampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    scope_type: str
    status: str
    ignore_status: str = ""
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    started_at: Optional[dt.datetime] = None
    ended_at: Optional[dt.datetime] = None
    notes: str = ""
    reminder_days_before: int = 3
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    scope_node_ids: List[int] = []
    scope_category_ids: List[int] = []
    participants: List[InventoryParticipantOut] = []
    # Fortschritt (bei Detail-/Statusabfrage gefuellt)
    expected_count: Optional[int] = None
    found_count: Optional[int] = None
    open_count: Optional[int] = None
    ignored_count: Optional[int] = None
    can_manage: Optional[bool] = None


class InventoryCampaignCreate(BaseModel):
    name: str
    scope_type: str = "full"               # full | nodes | categories
    ignore_status: List[str] = ["ausgegeben", "reparatur", "ausgemustert"]
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    notes: str = ""
    reminder_days_before: Optional[int] = None
    scope_node_ids: List[int] = []
    scope_category_ids: List[int] = []


class InventoryCampaignUpdate(BaseModel):
    name: Optional[str] = None
    scope_type: Optional[str] = None
    ignore_status: Optional[List[str]] = None
    planned_start: Optional[dt.datetime] = None
    planned_end: Optional[dt.datetime] = None
    notes: Optional[str] = None
    reminder_days_before: Optional[int] = None
    scope_node_ids: Optional[List[int]] = None
    scope_category_ids: Optional[List[int]] = None


class InventoryParticipantAdd(BaseModel):
    user_id: int
    role: str = "helper"                   # helper | lead


class InventoryScanRequest(BaseModel):
    """Einen gescannten/erfassten Artikel einem Knoten zuordnen und als Fund der
    Kampagne verbuchen."""
    article_ids: List[int] = []
    storage_node_id: Optional[int] = None


# --- Gefuehrter Rundgang: Stationen (Steps) ---
class InventoryStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    node_id: Optional[int] = None
    label: str = ""
    status: str = "pending"
    note: str = ""
    node_path: Optional[str] = None
    done_by_name: Optional[str] = None
    done_at: Optional[dt.datetime] = None
    # Fortschritt je Station (im Knoten-Teilbaum)
    expected_count: Optional[int] = None
    found_count: Optional[int] = None
    open_count: Optional[int] = None


class InventoryStepCreate(BaseModel):
    node_id: Optional[int] = None
    label: str = ""


class InventoryStepReorder(BaseModel):
    ordered_ids: List[int] = []


class InventoryStepStatus(BaseModel):
    status: str = "done"                    # pending | done | skipped
    note: Optional[str] = None


class InventoryStepsGenerate(BaseModel):
    """Stationen automatisch aus einer Knotenliste erzeugen (in gegebener
    Reihenfolge). Leere Liste = aus dem Geltungsbereich der Kampagne ableiten."""
    node_ids: List[int] = []
    replace: bool = True


# --- Vorlagen (Templates) ---
class InventoryTemplateStepIn(BaseModel):
    node_id: Optional[int] = None
    label: str = ""


class InventoryTemplateStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    node_id: Optional[int] = None
    label: str = ""
    node_path: Optional[str] = None


class InventoryTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    ignore_status: str = ""
    notes: str = ""
    created_by_name: Optional[str] = None
    steps: List[InventoryTemplateStepOut] = []


class InventoryTemplateCreate(BaseModel):
    name: str
    ignore_status: List[str] = ["ausgegeben", "reparatur", "ausgemustert"]
    notes: str = ""
    steps: List[InventoryTemplateStepIn] = []


class InventoryTemplateUpdate(BaseModel):
    name: Optional[str] = None
    ignore_status: Optional[List[str]] = None
    notes: Optional[str] = None
    steps: Optional[List[InventoryTemplateStepIn]] = None


class InventoryCampaignFromTemplates(BaseModel):
    name: str
    template_ids: List[int] = []
    planned_start: Optional[dt.datetime] = None
    participant_ids: List[int] = []
    reminder_days_before: Optional[int] = None


# --- Zeitplaene (wiederkehrend) ---
class InventoryScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    active: bool = True
    interval: int = 1
    unit: str = "month"
    next_run: Optional[dt.datetime] = None
    last_run: Optional[dt.datetime] = None
    ignore_status: str = ""
    notes: str = ""
    reminder_days_before: int = 3
    weekday: Optional[int] = None
    week_of_month: Optional[int] = None
    template_ids: List[int] = []
    template_names: List[str] = []
    participant_ids: List[int] = []


class InventoryScheduleCreate(BaseModel):
    name: str
    template_ids: List[int] = []
    interval: int = 1
    unit: str = "month"                     # day | week | month | month_weekday
    weekday: Optional[int] = None           # nur month_weekday: 0=Mo..6=So
    week_of_month: Optional[int] = None     # nur month_weekday: 1..4, 5=letzter
    start_date: Optional[dt.datetime] = None
    ignore_status: Optional[List[str]] = None
    participant_ids: List[int] = []
    reminder_days_before: Optional[int] = None
    notes: str = ""


class InventoryScheduleUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    template_ids: Optional[List[int]] = None
    interval: Optional[int] = None
    unit: Optional[str] = None
    weekday: Optional[int] = None
    week_of_month: Optional[int] = None
    next_run: Optional[dt.datetime] = None
    ignore_status: Optional[List[str]] = None
    participant_ids: Optional[List[int]] = None
    reminder_days_before: Optional[int] = None
    notes: Optional[str] = None


class ReturnCreate(BaseModel):
    condition_at_return: str = ""
    notes: str = ""
    return_date: Optional[dt.datetime] = None


class ChecklistItemIn(BaseModel):
    label: str


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    label: str


class ChecklistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    items: List[ChecklistItemOut] = []


class ChecklistCreate(BaseModel):
    name: str
    items: List[ChecklistItemIn] = []


class ChecklistUpdate(BaseModel):
    name: Optional[str] = None
    items: Optional[List[ChecklistItemIn]] = None


class InspectionRuleCreate(BaseModel):
    type_id: int
    trigger: str = "return"           # return | loans | washes | months
    threshold: int = 1
    checklist_id: Optional[int] = None


class ArticleRuleCreate(BaseModel):
    trigger: str = "return"           # + return_once (einmalig bei Rückgabe)
    threshold: int = 1
    checklist_id: Optional[int] = None


class OverrideToggle(BaseModel):
    enabled: bool = False


class InspectionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type_id: int
    type_name: Optional[str] = None
    article_id: Optional[int] = None
    trigger: str
    threshold: int = 1
    checklist_id: Optional[int] = None
    checklist_name: Optional[str] = None


class InspectionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    label: str
    ok: Optional[bool] = None
    note: str = ""


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    artikelnummer: Optional[str] = None
    checklist_name: str = ""
    status: str = "open"
    result: str = ""
    overall_note: str = ""
    has_document: bool = False
    started_by_name: Optional[str] = None
    finished_by_name: Optional[str] = None
    started_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    results: List[InspectionItemOut] = []


class InspectionStart(BaseModel):
    article_id: int


class InspectionItemUpdate(BaseModel):
    item_id: int
    ok: Optional[bool] = None
    note: Optional[str] = None


class InspectionFinish(BaseModel):
    result: str = "passed"                 # passed | failed
    target_status: Optional[str] = None    # bei failed: reparatur | ausgemustert
    overall_note: str = ""


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    issued_by_name: Optional[str] = None
    filename: str = ""
    signed: bool = False
    created_at: dt.datetime


class MaterialRequestCreate(BaseModel):
    type_id: Optional[int] = None
    size: str = ""
    quantity: int = 1
    desired_from: Optional[dt.datetime] = None
    desired_until: Optional[dt.datetime] = None
    note: str = ""


class MaterialRequestDecision(BaseModel):
    status: str                       # approved | rejected | done
    decision_note: str = ""


class MaterialRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requester_user_id: int
    requester_name: Optional[str] = None
    type_id: Optional[int] = None
    type_name: Optional[str] = None
    size: str = ""
    quantity: int = 1
    desired_from: Optional[dt.datetime] = None
    desired_until: Optional[dt.datetime] = None
    note: str = ""
    status: str = "open"
    handled_by_name: Optional[str] = None
    handled_at: Optional[dt.datetime] = None
    decision_note: str = ""
    created_at: dt.datetime


class DamageReportCreate(BaseModel):
    article_id: int
    kind: str = "damage"                # damage | loss
    description: str = ""               # Hergang / Umstände (Pflicht)
    incident_at: Optional[dt.datetime] = None      # Pflicht
    incident_location: str = ""         # Pflicht
    is_theft: bool = False
    police_reference: str = ""
    estimated_value: str = ""
    witnesses: str = ""
    reporter_contact: str = ""


class DamageReportUpdate(BaseModel):
    """Nachträgliches Ergänzen/Vervollständigen (durch Zuständige)."""
    description: Optional[str] = None
    incident_at: Optional[dt.datetime] = None
    incident_location: Optional[str] = None
    is_theft: Optional[bool] = None
    police_reference: Optional[str] = None
    estimated_value: Optional[str] = None
    witnesses: Optional[str] = None
    reporter_contact: Optional[str] = None


class DamageReportResolve(BaseModel):
    resolution_note: str = ""


class DamageReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    article_id: int
    artikelnummer: Optional[str] = None
    type_name: Optional[str] = None
    kind: str = "damage"
    reporter_name: Optional[str] = None
    description: str = ""
    incident_at: Optional[dt.datetime] = None
    incident_location: str = ""
    is_theft: bool = False
    police_reference: str = ""
    estimated_value: str = ""
    witnesses: str = ""
    reporter_contact: str = ""
    complete: bool = False
    has_photo: bool = False
    status: str = "open"
    handled_by_name: Optional[str] = None
    handled_at: Optional[dt.datetime] = None
    resolution_note: str = ""
    created_at: dt.datetime


class ReceiptDigital(BaseModel):
    person_id: int
    kind: str = "issue"                 # issue | return
    copies: int = 1
    sig_issuer: Optional[str] = None    # Base64-PNG
    sig_recipient: Optional[str] = None
    note: str = ""


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
    issue_policy: str = "confirm"


class StatusDefCreate(BaseModel):
    key: Optional[str] = None          # leer -> automatisch aus label erzeugt
    label: str
    sort_order: int = 100
    category_ids: List[int] = []
    require_note: bool = False
    allow_image: bool = False
    issue_policy: str = "confirm"


class StatusDefUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None
    category_ids: Optional[List[int]] = None
    require_note: Optional[bool] = None
    allow_image: Optional[bool] = None
    issue_policy: Optional[str] = None


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
    label_free_text: Optional[str] = None     # Freitext fuers Etikett (Feld "freetext")
    org_name: Optional[str] = None
    org_address: Optional[str] = None     # Anschrift (mehrzeilig) für Briefkopf/Meldungen
    org_vorstand: Optional[str] = None    # Vorstand / Vertretungsberechtigte
    org_contact: Optional[str] = None     # Telefon / E-Mail / Web
    org_registry: Optional[str] = None    # Vereinsregister / Steuernummer o.ä.
    printer_connection_type: Optional[str] = None   # "network" oder "usb"
    printer_ip: Optional[str] = None
    printer_model: Optional[str] = None
    printer_protocol: Optional[str] = None           # "pdf" | "ptouch"
    ptouch_tape_mm: Optional[str] = None
    ptouch_length_mm: Optional[str] = None
    ptouch_cut: Optional[bool] = None
    ptouch_rotate180: Optional[bool] = None
    ptouch_mirror: Optional[bool] = None
    selfreg_enabled: Optional[bool] = None
    selfreg_pin_length: Optional[int] = None
    selfreg_require_password: Optional[bool] = None
    selfreg_require_fullname: Optional[bool] = None
    selfreg_role: Optional[str] = None
    selfreg_match_existing: Optional[bool] = None
    # Automatischer Logout nach Inaktivitaet (Minuten; 0 = deaktiviert)
    session_idle_timeout_minutes: Optional[int] = None
    # DSGVO: Aufbewahrungsfrist Pruefprotokoll in Tagen (0 = unbegrenzt)
    audit_retention_days: Optional[int] = None
    # Bild-Verkleinerung beim Upload (als String "true"/"false", damit die
    # Speicherung eindeutig klein geschrieben bleibt)
    image_resize_enabled: Optional[str] = None
    image_resize_max_px: Optional[int] = None
    image_resize_quality: Optional[int] = None
