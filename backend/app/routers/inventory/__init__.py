from .inventory import router as inventory_router
from .storage_nodes import router as storage_nodes_router
from .inspection_router import router as inspection_router

__all__ = ["inventory_router", "storage_nodes_router", "inspection_router"]