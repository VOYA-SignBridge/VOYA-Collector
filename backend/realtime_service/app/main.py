from __future__ import annotations

import os

from fastapi import FastAPI

from .health import router as health_router
from .predict import router as predict_router
from .reload import router as reload_router
from .startup import register_startup


def create_app() -> FastAPI:
    app = FastAPI(title="VOYA Realtime Inference Service (Step 1)")

    app.include_router(health_router)
    app.include_router(predict_router)
    app.include_router(reload_router)

    default_registry_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config", "models.json")
    )
    registry_path = os.getenv("MODEL_REGISTRY_PATH", default_registry_path)
    normalization_py_path = (os.getenv("NORMALIZATION_PY_PATH", "") or "").strip()
    label_index_path = os.getenv("LABEL_INDEX_PATH", "processed/analysis/index_to_label.json")
    backend_url = (os.getenv("BACKEND_URL", "") or "").strip()

    if not normalization_py_path:
        # Hard requirement: inference service must use processed/shared/normalization.py.
        # We require explicit path to avoid importing backend code.
        raise RuntimeError("NORMALIZATION_PY_PATH must be set to processed/shared/normalization.py")

    register_startup(
        app,
        registry_path=registry_path,
        normalization_py_path=normalization_py_path,
        label_index_path=label_index_path,
        backend_url=backend_url,
    )

    return app


app = create_app()
