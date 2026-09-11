# Router packages - import from sub-packages
from .auth import auth_router, telegram_router
from .users import users_router, persons_router, groups_router
from .articles import (
    articles_router, lookups_router, issues_router, import_router,
    export_router, labels_router, statuses_router,
)
from .inventory import inventory_router, storage_nodes_router, inspection_router
from .maintenance import maintenance_router, logbook_router, reports_router
from .keys import keys_router, printers_router, doc_templates_router
from .settings import settings_router, backup_router, custom_fields_router, update_router
from .system import system_router, stats_router, search_router, receipts_router, requests_router

__all__ = [
    "auth_router", "telegram_router",
    "users_router", "persons_router", "groups_router",
    "articles_router", "lookups_router", "issues_router", "import_router",
    "export_router", "labels_router", "statuses_router",
    "inventory_router", "storage_nodes_router", "inspection_router",
    "maintenance_router", "logbook_router", "reports_router",
    "keys_router", "printers_router", "doc_templates_router",
    "settings_router", "backup_router", "custom_fields_router", "update_router",
    "system_router", "stats_router", "search_router", "receipts_router", "requests_router",
]