# VOYA-Collector

Sign language data collection and processing system for Vietnamese Sign Language.

---

## Architecture Diagram

### System Overview
<img src="assets/system_architecture.png" alt="System Architecture" width="500" height="800"/>

### Processing Pipeline (Inside Celery Worker)

![Processing Pipeline](assets/processing_pipeline.png)

---

## Project Overview

VOYA-Collector captures sign language gesture data from:
- **Live camera** (MediaPipe Hands landmark tracking, client-side)
- **Video files** (MP4, MOV)

Processed data is stored for training sign language recognition models.

---

## Tech Stack

### Frontend
- **React 19** + TypeScript
- **Vite** (build tool)
- **Tailwind CSS v4**
- **MediaPipe Hands** (client-side hand tracking)
- **Axios** (API client)

### Backend
- **FastAPI** (Python web framework)
- **Celery** (async task queue)
- **PostgreSQL** (metadata storage)
- **Redis** (Celery broker)
- **Google Drive** (when `USE_GOOGLE_DRIVE=1`)
- **MediaPipe Hands** (landmark extraction)

---

## Data Pipeline

```
Video/Camera -> MediaPipe -> Hand Landmarks (126-dim) -> Sliding Window (T=60)
    |
    v
Augment (8x) -> Save to dataset/features/{class_uid}/{uuid}.npz
    |
    v
Update samples.csv + PostgreSQL
```

### Feature Dimensions
- **21 hand landmarks x 3 coordinates (x,y,z) x 2 hands = 126 features/frame**
- **60 frames/sequence** (configurable)

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for frontend dev)

### Docker Deployment
```bash
# Start all services
docker-compose up --build -d

# View logs
docker-compose logs -f backend worker
```

### Production Deployment (docker-compose.prod.yml)

```bash
# 1. Copy the template and fill in real values — do NOT deploy with the
#    placeholder secrets/passwords as-is (see .env.example comments)
cp .env.example .env

# 2. Build and start
docker compose -f docker-compose.prod.yml up --build -d
```

Before going live, make sure `.env` has:
- Real `SECRET_KEY` / `AUTH_TOKEN_SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
- A real `POSTGRES_PASSWORD` / `ADMIN_PASSWORD` (not `admin`/`change-me`)
- `FRONTEND_BASE_URL` set to the server's real domain/IP
- `VITE_API_URL` left **empty** unless the frontend is served from a different origin than the nginx gateway (empty = same-origin, proxied by `nginx.conf`)

#### GPU (training on a CUDA machine)

`processed/train_utils/train_tcn.py` already auto-selects `cuda` when available — no code or `requirements.txt` change needed, `torch` from PyPI ships CUDA support by default. `docker-compose.prod.yml`'s `trainer` service reserves a GPU:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

For this to work, the **host** (school server) needs, one-time:

1. An up-to-date NVIDIA driver (`nvidia-smi` must work on the host itself).
2. The [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed and Docker restarted:
   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```
3. Verify before trusting compose: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` should print the GPU info.

If the toolkit isn't installed yet, `docker compose -f docker-compose.prod.yml up` will fail to start `trainer` with a device-request error — that's expected; install the toolkit above, or remove the `deploy:` block from the `trainer` service in `docker-compose.prod.yml` to fall back to CPU-only training.

Only `trainer` requests a GPU (training is CPU/GPU-heavy and runs one job at a time). `backend`'s real-time inference endpoint intentionally stays on CPU (single-sequence prediction is cheap, and this avoids VRAM contention with an in-progress training job).

### Frontend Development
```bash
cd voya-frontend
npm install
npm run dev    # http://localhost:5173
```

### Backend Development
```bash
cd voya-backend/backend
uv add -r requirements.txt
uv run -m uvicorn app.main:app --reload  # http://localhost:8000
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /upload/video | POST | Upload video for processing |
| /upload/camera | POST | Submit camera capture data |
| /classes/register | POST | Register new sign class |
| /classes/list | GET | List all classes |
| /dataset/samples | GET | List all samples |

---

## Configuration

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql://admin:admin@postgres:5432/signdb

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Processing
FEATURE_DIM=126
SEQ_LEN=60
STRIDE=2
FPS_TARGET=30
RESIZE_W=480
RESIZE_H=480
AUG_PER_SEQ=2
VIDEO_AUG_PER_SEQ=8
VIDEO_COMPLETENESS=0.4
SPEED_VARIANTS=1.0
MAX_SAMPLES_PER_CLASS=2000

# Storage
- **Local filesystem** (default)
- **Google Drive** (when `USE_GOOGLE_DRIVE=1`)
```

---

## Directory Structure

```
VOYA-Collector/
├── frontend/          # React frontend
│   └── src/
│       ├── api/           # API layer
│       ├── components/    # React components
│       └── pages/         # Page components
├── backend/  # FastAPI backend
│   ├── app/
│   │   ├── routers/       # API endpoints
│   │   ├── processing/    # Image processing
│   │   ├── storage/       # Data persistence
│   │   ├── config.py      # Settings singleton
│   │   ├── main.py        # FastAPI app
│   │   └── tasks.py       # Celery wrappers
│   └── dataset/           # Output data
│       ├── raw_videos/    # Original uploads
│       └── features/      # Processed NPZ files
└── .github/workflows/     # CI/CD
```

---

## Dialect Support

Vietnamese Sign Language dialects supported:
- **Bắc** (North)
- **Trung** (Central)
- **Nam** (South)
- **Cần Thơ** (Southwest)

---

## License

MIT
