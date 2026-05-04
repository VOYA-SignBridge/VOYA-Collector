# VOYA-Collector Setup & Deployment Guide

## 🚀 Quick Start (Choose Your OS)

### Windows (PowerShell)
```powershell
# Open PowerShell in the project root directory
# Copy template configuration
Copy-Item .env.example .env

# Edit configuration (optional, but recommended for production)
notepad .env

# Run setup
.\scripts\init.ps1

# Optional: Clean start (delete all data)
.\scripts\init.ps1 -Command clean

# Optional: Fresh rebuild
.\scripts\init.ps1 -Command rebuild
```

### macOS / Linux / WSL
```bash
# Copy template configuration
cp .env.example .env

# Edit configuration (optional, but recommended for production)
nano .env  # or vi, code, etc.

# Make script executable
chmod +x scripts/init.sh

# Run setup
./scripts/init.sh

# Optional: Clean start
./scripts/init.sh clean

# Optional: Fresh rebuild  
./scripts/init.sh rebuild
```

## ✅ What the Setup Does

The initialization script automatically:

1. **Prerequisites Check**
   - Verifies Docker is installed
   - Verifies Docker Compose is installed
   - Checks configuration file exists

2. **Configuration Validation**
   - Confirms required environment variables are set
   - Validates database credentials
   - Checks PostgreSQL database name

3. **Docker Setup**
   - Builds Docker images from Dockerfile
   - Creates volumes for persistent data

4. **Service Startup**
   - Starts PostgreSQL database
   - Starts Redis message broker
   - Starts MinIO object storage
   - Starts FastAPI backend
   - Starts Celery worker
   - Starts React frontend
   - Starts Nginx reverse proxy

5. **Health Verification**
   - Waits for all services to be healthy
   - Verifies database connectivity
   - Initializes database tables

6. **Final Checks**
   - Tests backend API responsiveness
   - Displays service URLs

## 📍 Service Access

After successful startup, services are available at:

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:8080 | Main application interface |
| **Backend API** | http://localhost:8000 | REST API server |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **Health Check** | http://localhost:8000/health | System health status |
| **PgAdmin** | http://localhost:5050 | Database management (user: admin@admin.com, pass: admin) |
| **MinIO** | http://localhost:9001 | Object storage console (user: minioadmin, pass: minioadmin) |

## 🔧 Common Commands

### View Service Status
```bash
docker compose ps
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f worker
docker compose logs -f postgres
```

### Stop Services
```bash
docker compose down
```

### Completely Reset (Delete All Data)
```bash
# Remove containers and volumes
docker compose down -v

# Restart fresh
docker compose up -d
```

### Access Backend Shell
```bash
docker compose exec backend bash
```

### Run Database Migrations
```bash
docker compose exec backend python -m alembic upgrade head
```

## 🎥 Camera Setup & Troubleshooting

### Camera Permission Issues

**Symptom**: "Camera bị từ chối" (Camera permission denied)

**Fix:**
- **Chrome/Edge**: Settings → Privacy → Camera → Allow localhost:8080
- **Firefox**: about:preferences → Privacy → Permissions → Camera → Allow
- **Safari**: System Preferences → Security & Privacy → Camera → Allow

### Camera Not Detected

**Symptom**: "Không tìm thấy camera" (Camera not found)

**Fixes**:
1. Ensure camera is physically connected
2. Close other applications using camera (Zoom, Meet, Teams, etc.)
3. On Windows: Check Device Manager for camera under "Imaging devices"
4. On Mac: System Preferences → Security & Privacy → Camera permissions
5. Try a different browser if camera still doesn't work

### Camera in Use by Another App

**Symptom**: "Không thể khởi động camera" (Cannot start camera)

**Fixes**:
1. Close all video conference applications
2. Close other browser tabs with video access
3. Restart the browser
4. Check Task Manager (Windows) or Activity Monitor (Mac) for camera access

### HTTPS Security Error

**Symptom**: "Lỗi bảo mật" (Security error)

**Fix**: Ensure you're accessing over HTTP (localhost:8080), not HTTPS. Production deployments require HTTPS.

## 🗄️ Database

### Database Credentials
- **Username**: signuser
- **Password**: signpass
- **Database**: signdb
- **Host**: localhost (or `postgres` from Docker containers)
- **Port**: 5432

### Accessing Database via PgAdmin

1. Go to http://localhost:5050
2. Login with:
   - Email: admin@admin.com
   - Password: admin
3. Register server:
   - Host: postgres
   - Username: signuser
   - Password: signpass

### Connecting Locally

```bash
# Using psql
psql -h localhost -U signuser -d signdb

# Or via Docker
docker compose exec postgres psql -U signuser -d signdb
```

## 🚨 Troubleshooting

### Services Won't Start

**Check service status**:
```bash
docker compose ps
```

**View logs for errors**:
```bash
docker compose logs backend
docker compose logs postgres
```

**Common fixes**:
- Ensure ports 5432, 6379, 9000, 8000, 80 are not in use
- Try `docker compose down -v` and restart
- Check firewall settings

### Frontend Can't Connect to Backend

**Verify backend is running**:
```bash
docker compose ps backend
curl http://localhost:8000/health
```

**Check configuration**:
```bash
# Should see success responses
curl http://localhost:8000/health/ready
```

**Check Nginx routing**:
```bash
docker compose logs nginx
```

### Database Connection Failed

**Check credentials in .env**:
```bash
# Should show:
POSTGRES_USER=signuser
POSTGRES_PASSWORD=signpass
POSTGRES_DB=signdb
```

**Verify database is ready**:
```bash
docker compose exec postgres pg_isready -U signuser
```

### Fresh Machine Setup Failure

1. Ensure `.env` is copied from `.env.example`
2. Check all required fields are set in `.env`
3. Verify Docker and Docker Compose versions are current
4. Try rebuilding images:
   ```bash
   docker compose build --no-cache
   docker compose up -d
   ```

## 📊 Health Checks

### Check System Health

**Quick health check**:
```bash
curl http://localhost:8000/health
```

**Detailed status**:
```bash
curl http://localhost:8000/health/status
```

**Configuration validation**:
```bash
curl http://localhost:8000/health/config
```

**Dependency check**:
```bash
curl http://localhost:8000/health/deps
```

**Readiness for requests**:
```bash
curl http://localhost:8000/health/ready
```

## 🔐 Security Notes

- **Never commit `.env` to version control**
- Change database password in production
- Enable HTTPS in production deployments
- Configure firewall to restrict access
- Regularly backup database volume: `docker compose exec postgres pg_dump -U signuser signdb > backup.sql`

## 📝 Environment Configuration

### Critical Variables

```bash
# Database (CRITICAL - required for operation)
POSTGRES_USER=signuser
POSTGRES_PASSWORD=signpass
POSTGRES_DB=signdb

# Redis (for Celery task queue)
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO (object storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=sign-dataset
```

### Optional Variables

```bash
# Cloudinary (for hybrid cloud storage)
CLOUDINARY_ENABLED=0
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key

# Processing configuration
FRAME_INTERVAL_MS=33
MAX_UPLOAD_MB=500
```

See `.env.example` for all available options with descriptions.

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs
- **Frontend Code**: `frontend/src/`
- **Backend Code**: `backend/app/`

## 🆘 Getting Help

If you encounter issues:

1. **Check the logs**: `docker compose logs -f`
2. **Run health checks**: `curl http://localhost:8000/health/config`
3. **Review this guide's troubleshooting section**
4. **Check browser console** for frontend errors (F12)
5. **Verify `.env` configuration** matches examples

## 🎓 Development

### Frontend Development (With Docker)

Backend and services run in Docker, frontend runs locally:

```bash
# Terminal 1: Start backend services
cd VOYA-Collector
docker compose up -d

# Terminal 2: Run frontend dev server
cd frontend
npm install
npm run dev
# Access at http://localhost:5173
```

### Backend Development (With Docker)

```bash
# Terminal 1: Start dependencies (database, redis, etc.)
cd VOYA-Collector
docker compose up postgres redis minio -d

# Terminal 2: Run backend dev server
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
# Access at http://localhost:8000
```

## ✨ Next Steps

1. **Run the setup script** for your OS
2. **Wait for all services to be healthy** (usually 30-60 seconds)
3. **Open** http://localhost:8080 in your browser
4. **Check** http://localhost:8000/docs for API documentation
5. **Test camera functionality** with a connected webcam

---

**Last Updated**: 2024
**Version**: 1.0 Enterprise Edition
