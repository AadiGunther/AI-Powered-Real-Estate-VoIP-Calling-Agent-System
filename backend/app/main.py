"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import routers
from app.api.admin import router as admin_router
from app.api.appointments import router as appointments_router
from app.api.auth import router as auth_router
from app.api.calls import router as calls_router
from app.api.dashboard import router as dashboard_router
from app.api.elevenlabs_calls import router as elevenlabs_calls_router
from app.api.elevenlabs_conversation_init import router as elevenlabs_conversation_init_router
from app.api.elevenlabs_webhook import router as elevenlabs_router
from app.api.leads import router as leads_router
from app.api.notifications import router as notifications_router
from app.api.products import router as products_router
from app.api.properties import router as properties_router
from app.api.reports import router as reports_router
from app.config import settings
from app.database import lifespan_db
from app.utils.logging import setup_logging

# Setup logging
setup_logging(debug=settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Ensure recordings directory exists
    os.makedirs(settings.recordings_dir, exist_ok=True)
    
    async with lifespan_db():
        yield


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Real Estate VoIP Calling Agent System",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("BASE_URL:", settings.base_url)
print("WEBSOCKET_URL:", settings.websocket_url)
print("CORS_ORIGINS:", settings.cors_origins)

# Mount static files for recordings
app.mount("/recordings", StaticFiles(directory=settings.recordings_dir), name="recordings")

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(properties_router, prefix="/properties", tags=["Properties"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(leads_router, prefix="/leads", tags=["Leads"])
app.include_router(calls_router, prefix="/calls", tags=["Calls"])
app.include_router(reports_router, prefix="/reports", tags=["Reports"])
app.include_router(dashboard_router)
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(appointments_router, prefix="/appointments", tags=["Appointments"])
app.include_router(elevenlabs_router, tags=["ElevenLabs"])
app.include_router(elevenlabs_conversation_init_router)
app.include_router(elevenlabs_calls_router, tags=["ElevenLabs Calls"])
app.include_router(notifications_router)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    mongodb_status = "disabled" if not settings.mongodb_url else "configured"
    return {
        "status": "healthy",
        "database": "connected",
        "mongodb": mongodb_status,
    }
