import logging

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dataset, upload, jobs, classes, inference
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
    logger.info(f"[CONFIG] dataset_root={settings.dataset_root}")
    init_db()

app.include_router(dataset.router)
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(classes.router)
app.include_router(inference.router)

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "healthy", "event": "startup"}

# Versioned API (do not remove unversioned endpoints; FE may depend on them)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(dataset.router)
api_v1.include_router(upload.router)
api_v1.include_router(jobs.router)
api_v1.include_router(classes.router)
api_v1.include_router(inference.router)
app.include_router(api_v1)