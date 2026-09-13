from .maintenance import router as maintenance_router
from .logbook import router as logbook_router
from .reports import router as reports_router
from .tires import router as tires_router

__all__ = ["maintenance_router", "logbook_router", "reports_router", "tires_router"]
