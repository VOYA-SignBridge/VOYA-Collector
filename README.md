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

### Docker Deployment (Recommended)

#### On Windows (PowerShell)
```powershell
# Copy template configuration
Copy-Item .env.example .env

# Edit .env with your settings (see Configuration section)
notepad .env

# Run setup script
.\scripts\init.ps1

# Or rebuild from scratch
.\scripts\init.ps1 -Command rebuild

# Stop services
docker compose down
```

#### On macOS / Linux / Windows (WSL)
```bash
# Copy template configuration
cp .env.example .env

# Edit .env with your settings
nano .env  # or vim, or your favorite editor

# Run setup script
chmod +x scripts/init.sh
./scripts/init.sh

# Or rebuild from scratch
./scripts/init.sh rebuild

# Stop services
docker compose down
```

#### What the Setup Script Does
1. ✅ Validates Docker and Docker Compose installation
2. ✅ Checks configuration file (.env)
3. ✅ Builds Docker images
4. ✅ Starts all services (PostgreSQL, Redis, MinIO, Backend, Worker, Frontend, Nginx)
5. ✅ Waits for services to be healthy
6. ✅ Verifies database connectivity
7. ✅ Initializes database tables
8. ✅ Runs health checks
9. ✅ Displays service URLs

#### Accessing Services After Startup
- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **PgAdmin**: http://localhost:5050
- **MinIO Console**: http://localhost:9001

#### Useful Docker Commands
```bash
# View all running services
docker compose ps

# View logs for specific service
docker compose logs backend
docker compose logs -f worker

# Access backend shell
docker compose exec backend bash

# Run database migrations (if needed)
docker compose exec backend python -m alembic upgrade head

# Stop all services
docker compose down

# Remove all data and restart fresh
docker compose down -v  # -v removes volumes
docker compose up -d
```

### Frontend Development (Local)

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

### Backend Development (Local)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload  # http://localhost:8000
```

---

## Troubleshooting

### Camera Not Opening
**Error**: "Camera bị từ chối" (Camera permission denied)

**Solutions**:
1. Check browser camera permissions:
   - Chrome/Edge: Settings → Privacy → Camera → Allow for this site
   - Firefox: Privacy & Security → Permissions → Camera → Allow
   - Safari: System Preferences → Security & Privacy → Camera

2. Ensure camera is not in use:
   - Close other video apps (Zoom, Meet, Teams, etc.)
   - Check if another process is using the camera
   
3. Try a different browser if the camera still doesn't work

4. On Windows, check Settings → Privacy & Security → Camera → ensure app permission is granted

### Connection Issues Between Frontend and Backend
**Error**: "GET http://localhost:8000/upload: Failed to fetch"

**Solutions**:
1. Verify backend is running:
   ```bash
   docker compose ps backend
   curl http://localhost:8000/health
   ```

2. Check frontend configuration - ensure `.env` has:
   ```
   VITE_API_URL=http://localhost:8000
   ```

3. Verify Nginx is routing correctly:
   ```bash
   docker compose logs nginx
   ```

4. If using Docker, make sure services can communicate:
   ```bash
   docker compose exec backend curl http://localhost:8000/health
   ```

### Database Connection Errors
**Error**: "password authentication failed for user 'signuser'"

**Solution**: Ensure `.env` has matching credentials:
```
POSTGRES_USER=signuser
POSTGRES_PASSWORD=signpass
POSTGRES_DB=signdb
DATABASE_URL=postgresql://signuser:signpass@postgres:5432/signdb
```

Then restart the services:
```bash
docker compose down
docker compose up -d
```

### Services Not Starting
**Symptom**: Some services remain in "restarting" state

**Solution**: Check service logs for errors:
```bash
# Check all services
docker compose logs

# Check specific service
docker compose logs postgres
docker compose logs backend

# Check health endpoints
docker compose exec backend curl http://localhost:8000/health/ready
```

### Fresh Deployment on New Machine
To deploy on a machine without prior setup:

```bash
# 1. Clone repository
git clone <repo-url>
cd VOYA-Collector

# 2. Copy template configuration
cp .env.example .env

# 3. Edit configuration (CRITICAL)
# - Set POSTGRES_PASSWORD to a secure value
# - Check other settings match your environment
nano .env

# 4. Run setup script
./scripts/init.sh

# 5. Verify everything works
curl http://localhost:8000/health
curl http://localhost:8080/  # Should see frontend
```

### Resetting Database
To clear all data and restart fresh:

```bash
# Stop services and remove all volumes
docker compose down -v

# Rebuild and restart
docker compose up -d

# Or use setup script
./scripts/init.sh clean
```

---

## Frontend Development
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

# Optional hybrid media storage
CLOUDINARY_ENABLED=1
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
CLOUDINARY_UPLOAD_PRESET=optional_unsigned_preset
CLOUDINARY_DEBUG_RESPONSES=0
STORAGE_DOWNLOAD_WORKERS=4
```

### Storage Policy

- Raw video uploads go to Cloudinary only.
- Training artifacts (`.npz`) go to MinIO only.
- All stored assets follow deterministic paths based on `language/dialect/class_folder`, so downloads, reprocessing, and training exports can resolve files without guessing.
- Batch export and training materialization download remote files in parallel into a local cache before validation and memmap merge.

Recommended setup for this project:
- Use Cloudinary for public-facing raw media and short-lived video previews.
- Use MinIO for training artifacts, `.npz` samples, and bulk dataset export.
- Keep Cloudinary credentials configured in `.env` before enabling raw-video uploads.
- Set `CLOUDINARY_DEBUG_RESPONSES=1` in development if you want `/upload/video` to write the Cloudinary payload or structured error details to the backend log only.

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
