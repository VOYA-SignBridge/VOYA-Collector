FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -c "from pathlib import Path; src = Path('/tmp/requirements.txt').read_text().splitlines(); Path('/tmp/requirements.base.txt').write_text('\n'.join(line for line in src if not line.strip().startswith('torch')) + '\n')" && \
    python -m pip install --no-cache-dir -r /tmp/requirements.base.txt && \
    python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/realtime_service \
    NORMALIZATION_PY_PATH=/app/processed/shared/normalization.py

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]