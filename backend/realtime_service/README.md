# VOYA Realtime Inference Service (Step 0)

This folder is an **isolated** FastAPI service intended to run as a separate container.

Step 0 scope:
- Load a **versioned registry** (`config/models.json`)
- Load + validate **checkpoint contracts** and **embedded labels**
- Build model objects and run **warmup** (fail-fast)
- Provide `GET /health` and `GET /models`
- **No** prediction endpoint yet

## Required env vars

- `NORMALIZATION_PY_PATH` (required)
  - Absolute path to `processed/shared/normalization.py`
  - Service refuses to boot without this (prevents importing backend normalization utils)

Optional:
- `MODEL_REGISTRY_PATH` (default: `config/models.json`)

## Run (dev)

From `backend/realtime_service`:

```bash
pip install -r requirements.txt

# Example paths; adjust for your machine/container
set NORMALIZATION_PY_PATH=E:\path\to\processed\shared\normalization.py

uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Endpoints:
- `GET /health`
- `GET /models`
