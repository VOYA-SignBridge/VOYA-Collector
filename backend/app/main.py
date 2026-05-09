import logging
import time

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dataset, upload, jobs, classes, inference, health, auth
from app.logging_config import configure_logging
from app.db import init_db

app = FastAPI(title="Sign Dataset Backend")

# Enable CORS for local dev (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init DB tables (dev). In prod, use migrations (alembic).
@app.on_event("startup")
def startup():
    configure_logging()
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    started_at = time.time()
    logger.info(
        "[STARTUP] app_env=%s dataset_root=%s database_url=%s",
        getattr(settings, "app_env", "unknown"),
        settings.dataset_root,
        settings.database_url,
    )
    db_ready = init_db()
    
    # Bootstrap admin user if configured
    if db_ready:
        from app.db import bootstrap_admin_user
        bootstrap_admin_user()
    
    logger.info(
        "[STARTUP][DB_INIT] status=%s duration_ms=%.1f",
        "ready" if db_ready else "warning",
        (time.time() - started_at) * 1000,
    )

# Include routers
app.include_router(health.router)
app.include_router(dataset.router)
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(classes.router)
app.include_router(inference.router)

# Versioned API (do not remove unversioned endpoints; FE may depend on them)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(dataset.router)
api_v1.include_router(upload.router)
api_v1.include_router(jobs.router)
api_v1.include_router(classes.router)
api_v1.include_router(inference.router)
api_v1.include_router(auth.router)
app.include_router(api_v1)

# test