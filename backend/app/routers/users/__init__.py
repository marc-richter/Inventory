from .users import router as users_router
from .persons import router as persons_router
from .groups import router as groups_router

__all__ = ["users_router", "persons_router", "groups_router"]