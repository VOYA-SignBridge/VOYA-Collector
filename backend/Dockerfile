# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# --retries/--timeout make the install resilient to slow mirrors and the
# IncompleteRead/"Connection broken" errors seen when large wheels
# (opencv, numpy, torch) get interrupted mid-download.
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir --user \
        --retries 10 --timeout 180 \
        -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create user first before copying files
RUN useradd -m -u 1000 appuser && \
    mkdir -p /dataset/raw_videos /dataset/features && \
    chown -R appuser:appuser /dataset

# Copy Python packages from builder with correct ownership
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy app files
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser requirements.txt .

ENV PATH=/home/appuser/.local/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    FONTCONFIG_PATH=/tmp/fontconfig

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
