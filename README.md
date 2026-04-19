# VOYA-Collector

Sign language data collection and processing system for Vietnamese Sign Language.

---

## Architecture Diagram

### System Overview
![System Architecture](assets/system_architecture.jpg)

### Processing Pipeline (Inside Celery Worker)

![Processing Pipeline](assets/processing_pipeline.png)

---

## Project Overview

VOYA-Collector captures sign language gesture data from:
- **Live camera** (MediaPipe Holistic hand tracking)
- **Video files** (MP4, MOV)

Processed data is stored for training sign language recognition models.

---

## Tech Stack

### Frontend
- **React 19** + TypeScript
- **Vite** (build tool)
- **Tailwind CSS v4**
- **MediaPipe Holistic** (client-side hand tracking)
- **Axios** (API client)

### Backend
- **FastAPI** (Python web framework)
- **Celery** (async task queue)
- **PostgreSQL** (metadata storage)
- **Redis** (Celery broker)
- **MinIO** (S3-compatible object storage)
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
USE_MINIO=1
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=sign-dataset
```

---

## Directory Structure

```
VOYA-Collector/
├── voya-frontend/          # React frontend
│   └── src/
│       ├── api/           # API layer
│       ├── components/    # React components
│       └── pages/         # Page components
├── voya-backend/backend/  # FastAPI backend
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
