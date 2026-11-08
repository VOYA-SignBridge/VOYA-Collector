# Ảnh gốc ghim theo DIGEST, không chỉ theo tag. Tag `3.11-slim` di chuyển vài lần mỗi
# tháng; mỗi lần nó di chuyển thì mọi lớp phía sau (torch/CUDA, 4,3 GB nén) bị dựng lại
# với digest mới, và máy chạy web phải tải lại cả khối thay vì vài chục MB mã.
# Dependabot (.github/dependabot.yml) mở PR khi có digest mới: cập nhật có chủ ý.
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -c "from pathlib import Path; src = Path('/tmp/requirements.txt').read_text().splitlines(); Path('/tmp/requirements.base.txt').write_text('\n'.join(line for line in src if not line.strip().startswith('torch')) + '\n')" && \
    python -m pip install --no-cache-dir --retries 10 --timeout 180 -r /tmp/requirements.base.txt && \
    python -m pip install --no-cache-dir --retries 10 --timeout 180 --index-url https://download.pytorch.org/whl/cpu torch

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/realtime_service \
    NORMALIZATION_PY_PATH=/app/processed/shared/normalization.py

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]