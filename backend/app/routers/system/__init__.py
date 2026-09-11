from .system_router import router as system_router
from .stats_router import router as stats_router
from .search import router as search_router
from .receipts import router as receipts_router
from .requests import router as requests_router

__all__ = ["system_router", "stats_router", "search_router", "receipts_router", "requests_router"]