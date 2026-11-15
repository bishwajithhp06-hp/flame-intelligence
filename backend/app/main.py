import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.migrations import apply_additive_migrations
from app.services.data_collector import DataCollector
from app.services.nasa_data_ingestion_service import NasaDataIngestionService
from app.routes import (
    dashboard,
    investigations,
    search,
    analytics,
    ai,
    sources,
    mission,
    experiments,
    reports,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("flame_intelligence")
logger = logging.getLogger("flame_intelligence")

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed local research records if empty.
    logger.info("Initializing FLAME INTELLIGENCE database schema...")
    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    
    db = SessionLocal()
    try:
        DataCollector.seed_initial_verified_records(db)
        # Source-register setup is independent of legacy investigation seeding;
        # existing databases may already contain investigations and skip seed.
        NasaDataIngestionService.ensure_source_register(db)
        db.commit()
    except Exception as e:
        logger.error(f"Error during initial seed: {e}")
    finally:
        db.close()
    
    yield
    # Shutdown
    logger.info("FLAME INTELLIGENCE backend shutting down.")

development_mode = settings.ENVIRONMENT.strip().lower() in {"development", "dev", "local"}

app = FastAPI(
    title="FLAME INTELLIGENCE API",
    description="Backend API for NASA Microgravity Combustion Research & Spacecraft Fire Safety Dashboard",
    version=settings.APP_VERSION,
    docs_url="/docs" if development_mode else None,
    redoc_url="/redoc" if development_mode else None,
    openapi_url="/openapi.json" if development_mode else None,
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)
# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(dashboard.router)
app.include_router(investigations.router)
app.include_router(search.router)
app.include_router(analytics.router)
app.include_router(ai.router)
app.include_router(sources.router)
app.include_router(mission.router)
app.include_router(experiments.router)
app.include_router(reports.router)

@app.get("/")
def root():
    return {
        "app": "FLAME INTELLIGENCE",
        "description": "NASA Microgravity Combustion Data & Spacecraft Fire Safety Platform",
        "version": settings.APP_VERSION,
        "status": "Operational",
        "docs": "/docs" if development_mode else None,
        "investigations_investigated": ["FLEX", "SAFFIRE", "SPICE", "BASS", "ACME"]
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "gemini_configured": bool(settings.GEMINI_API_KEY)
    }
