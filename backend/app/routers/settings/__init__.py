from .settings_router import router as settings_router
from .backup_router import router as backup_router
from .custom_fields import router as custom_fields_router
from .update_router import router as update_router

__all__ = ["settings_router", "backup_router", "custom_fields_router", "update_router"]