# syntax=docker/dockerfile:1.4
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install PyTorch first, from the CUDA 11.7 wheel index. This "+cu117" build is
# self-contained: it bundles the CUDA libraries it needs, so it does NOT drag in
# the ~2.6 GB of separate `nvidia-*` pip packages that the default PyPI torch
# wheel declares as dependencies. Net effect: ~1.5–2 GB smaller image while
# keeping full GPU training support (verified: torch.cuda.is_available()).
#
# The `--mount=type=cache` keeps pip's downloaded wheels in a BuildKit cache that
# is NOT baked into the image — so a rebuild reuses the ~1.8 GB torch wheel from
# disk instead of re-downloading it over a slow link (the pain we hit before).
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install --user --retries 10 --timeout 180 \
        --index-url https://download.pytorch.org/whl/cu117 \
        torch==2.0.0+cu117

# Everything else from PyPI. `torch==2.0.0` in requirements.txt is already
# satisfied by the +cu117 build above (PEP 440: `==2.0.0` matches `2.0.0+cu117`),
# so pip won't re-fetch torch or its CUDA deps here.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --user --retries 10 --timeout 180 \
        -r requirements.txt

# Activity-monitor geolocation (offline MaxMind GeoLite2 reader). Separate layer
# so it never invalidates the heavy requirements cache above. Non-blocking: a
# short timeout + `|| true` means a slow/offline PyPI can't hang or fail the
# build — the app imports geoip2 lazily and degrades to "no location" without it.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --user --retries 2 --timeout 30 geoip2==4.8.0 \
    || echo "[build][warn] geoip2 install skipped (offline) — geolocation disabled at runtime"

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
