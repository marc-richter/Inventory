// Base types matching backend schemas

export interface LookupOut {
  id: number
  name: string
}

export interface CategoryOut {
  id: number
  name: string
  parent_id: number | null
  parent_name: string | null
  issuable_default: boolean
  key_system: boolean
}

export interface TypeOut {
  id: number
  name: string
  category_id: number
  min_stock: number
  issuable_default: boolean | null
  is_psa_default: boolean
}

export interface OrganizationOut {
  id: number
  name: string
}

export interface StorageLocationOut {
  id: number
  name: string
  address: string
  contact_name: string
  contact_phone: string
  contact_fax: string
  contact_email: string
  needs_review: boolean
}

export interface ArticleOut {
  id: number
  artikelnummer: string
  category_id: number
  type_id: number
  size: string
  model: string
  model_id: number | null
  properties: string
  organization_id: number | null
  storage_location_id: number | null
  storage_node_id: number | null
  location_path: string
  etage: string
  raum: string
  schrank: string
  fach: string
  current_location: string
  status: string
  condition_notes: string
  remarks: string
  repair_expected_return: string | null
  repair_reason: string
  retire_reason: string
  first_entry_date: string
  created_at: string
  updated_at: string
  created_by_id: number | null
  created_by_name: string | null
  provisional: boolean
  provisional_by_name: string | null
  review_assignee_id: number | null
  review_assignee_name: string | null
  issuable_override: boolean | null
  is_issuable: boolean
  is_psa: boolean
  loan_count: number
  wash_count: number
  last_inspection_at: string | null
  pending_checklist_id: number | null
  needs_inspection: boolean
  inspection_override: boolean
  is_vehicle: boolean
  license_plate: string
  vin: string
  first_registration: string | null
  vehicle_node_id: number | null
  key_type_id: number | null
  key_type_name: string | null
  key_serial: string
  is_key: boolean
  locks: KeyLockOut[]
  custom_values: Record<string, string>
  images: ImageOut[]
  issues: IssueOut[]
}

export interface ArticlePaginatedOut {
  items: ArticleOut[]
  total: number
  skip: number
  limit: number
}

export interface ImageOut {
  id: number
  filepath: string
  kind: string
  uploaded_at: string
}

export interface IssueOut {
  id: number
  article_id: number
  person_id: number | null
  recipient_name_freetext: string
  issue_date: string
  expected_return_date: string | null
  return_date: string | null
  condition_at_return: string
  notes: string
  issued_by_user_id: number | null
  returned_by_user_id: number | null
  issued_by_name: string | null
  returned_by_name: string | null
  deposit_amount: string
  deposit_returned: boolean
}

export interface PersonOut {
  id: number
  first_name: string
  last_name: string
  organization_id: number | null
  notes: string
  active: boolean
  hidden: boolean
  sizes: Record<string, string>
}

export interface UserOut {
  id: number
  username: string
  full_name: string
  roles: string[]
  person_id: number | null
  active: boolean
  pin_length: number
  has_password: boolean
  has_pin: boolean
  capabilities: string[]
  revoked_capabilities: string[]
  telegram_linked: boolean
  reminder_days_before: number | null
  analytics_access: boolean
}

export interface LoginRequest {
  username: string
  password?: string
  pin?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserOut
}

export interface KeyLockOut {
  lock_id: number
  name: string
  object_id: number
  object_name: string
}

export interface StatusDefOut {
  id: number
  key: string
  label: string
  sort_order: number
  is_builtin: boolean
  active: boolean
  category_ids: number[]
  require_note: boolean
  allow_image: boolean
  issue_policy: string
}

export interface InventoryCampaignOut {
  id: number
  name: string
  scope_type: string
  status: string
  ignore_status: string
  planned_start: string | null
  planned_end: string | null
  started_at: string | null
  ended_at: string | null
  notes: string
  reminder_days_before: number
  created_by_id: number | null
  created_by_name: string | null
  scope_node_ids: number[]
  scope_category_ids: number[]
  participants: InventoryParticipantOut[]
  expected_count: number | null
  found_count: number | null
  open_count: number | null
  ignored_count: number | null
  can_manage: boolean | null
}

export interface InventoryParticipantOut {
  id: number
  user_id: number
  role: string
  user_name: string | null
}

export interface StorageNodeOut {
  id: number
  parent_id: number | null
  level: string
  name: string
  description: string
  address: string
  contact_name: string
  contact_phone: string
  contact_fax: string
  contact_email: string
  sort_order: number
  node_article_id: number | null
  code: string | null
  is_lock: boolean
  cylinders: CylinderOut[]
}

export interface CylinderOut {
  id: number
  name: string
  note: string
}

export interface SettingsOut {
  pin_length_default: number
  backup_dir: string
  backup_auto_enabled: boolean
  backup_auto_time: string
  backup_retention: number
  label_width_mm: number
  label_height_mm: number
  label_code_format: string
  label_fields: string
  label_maxlen: string
  label_free_text: string
  org_name: string
  org_address: string
  org_vorstand: string
  org_contact: string
  org_registry: string
  printer_connection_type: string
  printer_ip: string
  printer_model: string
  printer_protocol: string
  ptouch_tape_mm: string
  ptouch_length_mm: string
  ptouch_cut: boolean
  ptouch_rotate180: boolean
  ptouch_mirror: boolean
  selfreg_enabled: boolean
  selfreg_pin_length: number
  selfreg_require_password: boolean
  selfreg_require_fullname: boolean
  selfreg_role: string
  selfreg_match_existing: boolean
  session_idle_timeout_minutes: number
  audit_retention_days: number
  image_resize_enabled: string
  image_resize_max_px: number
  image_resize_quality: number
}

export interface BackupRecordOut {
  id: number
  filename: string
  kind: string
  size_bytes: number
  created_at: string
}

export interface BackupVerifyResult {
  ok: boolean
  checks: BackupVerifyCheck[]
  summary: string
}

export interface BackupVerifyCheck {
  name: string
  ok: boolean
  detail: string
  severity: 'error' | 'warning'
}

export interface RegisterInfoOut {
  enabled: boolean
  pin_length: number
  require_password: boolean
  require_fullname: boolean
}

export interface UpdateCheckResponse {
  update_available: boolean
  latest?: string
}

export interface ProvisionalCountResponse {
  assigned_to_me: number
  total: number
}

export interface ReportsInboxCountResponse {
  count: number
  incomplete: number
}

export interface MaintenanceDueCountResponse {
  count: number
  overdue: number
}

export interface LoansCountResponse {
  count: number
  overdue: number
}

export interface LowStockCountResponse {
  count: number
}

export interface InventoryNotificationResponse {
  id: number
  name: string
  status: string
  open_count: number
  planned_start?: string
}

export interface SettingsPublicResponse {
  org_name: string
  session_idle_timeout_minutes: number
}

export interface UpdateCheckResponse {
  update_available: boolean
  latest?: string
}

export interface ProvisionalCountResponse {
  assigned_to_me: number
  total: number
}

export interface ReportsInboxCountResponse {
  count: number
  incomplete: number
}

export interface MaintenanceDueCountResponse {
  count: number
  overdue: number
}

export interface LoansCountResponse {
  count: number
  overdue: number
}

export interface LowStockCountResponse {
  count: number
}

export interface InventoryNotificationResponse {
  id: number
  name: string
  status: string
  open_count: number
  planned_start?: string
}

export interface SettingsPublicResponse {
  org_name: string
  session_idle_timeout_minutes: number
}