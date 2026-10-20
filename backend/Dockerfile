# syntax=docker/dockerfile:1.4
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install PyTorch first, from the CUDA 12.8 wheel index.
#
# Was cu117 / torch 2.0.0, whose kernels stop at sm_86. That covers Ampere
# (RTX 30xx) and nothing newer: on an Ada (RTX 40xx, sm_89) or Blackwell
# (RTX 50xx, sm_120) card, torch.cuda.is_available() still returns True and the
# first kernel launch then fails with "no kernel image is available for
# execution on the device". cu128 / 2.7.1 reports
#   ['sm_75','sm_80','sm_86','sm_90','sm_100','sm_120','compute_120']
# so one build serves both the RTX 3050 (sm_86) and the RTX 5060 Ti (sm_120).
# train_tcn.pick_device() still guards the case, in case a future card outruns
# this wheel too.
#
# The "+cu128" build stays self-contained: it bundles the CUDA libraries it
# needs rather than dragging in the separate ~2.6 GB of `nvidia-*` pip packages
# that the default PyPI wheel declares.
#
# The `--mount=type=cache` keeps pip's downloaded wheels in a BuildKit cache that
# is NOT baked into the image — so a rebuild reuses the large torch wheel from
# disk instead of re-downloading it over a slow link (the pain we hit before).
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && \
    python -m pip install --user --retries 10 --timeout 180 \
        --index-url https://download.pytorch.org/whl/cu128 \
        torch==2.7.1+cu128

# Everything else from PyPI. `torch==2.7.1` in requirements.txt is already
# satisfied by the +cu128 build above (PEP 440: `==2.7.1` matches `2.7.1+cu128`),
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
