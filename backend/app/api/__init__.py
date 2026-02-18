"""API package initialization."""

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.calls import router as calls_router
from app.api.leads import router as leads_router
from app.api.properties import router as properties_router
from app.api.reports import router as reports_router

__all__ = [
    "auth_router",
    "properties_router",
    "leads_router",
    "calls_router",
    "reports_router",
    "admin_router",
]
