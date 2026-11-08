#!/usr/bin/env sh
# Chạy TRONG container test: dựng backend tạm từ mã đang có trong repo.
#
# Mỗi biến dưới đây chặn một đường ra dữ liệu thật. `run_tests.sh` truyền nguyên
# `.env` sản xuất vào đây, nên thiếu một dòng là backend tạm đi thẳng vào đích thật.
set -eu

export USE_GOOGLE_DRIVE=0                                # không ghi lên Drive
export GOOGLE_DRIVE_CREDENTIALS=/nonexistent/credentials.json
export GOOGLE_DRIVE_TOKEN=/nonexistent/token.json
export GOOGLE_DRIVE_ROOT_FOLDER_ID=
export GOOGLE_SHEETS_LABELS_SPREADSHEET_ID=              # không ghi lên Sheets
export GOOGLE_SHEETS_SAMPLES_SPREADSHEET_ID=
export GOOGLE_SHEETS_API_KEY=
export DATASET_ROOT=/tmp/dataset                         # labels.csv, samples.csv là BẢN SAO
export LEGAL_STORE_ROOT=/tmp/legal
export COOKIE_SECURE=0                                   # chạy http://127.0.0.1
export TTS_PREWARM_ON_STARTUP=0                          # không gọi dịch vụ đọc ngoài
export FEATURES_ROOT=/tmp/dataset/features                # trainer đọc mẫu từ bản sao

mkdir -p /tmp/dataset/features/vn /tmp/legal /workspace/backend /workspace/processed
cp /src/dataset/labels.csv /src/dataset/samples.csv /tmp/dataset/
# Bản sao, không phải symlink: mẫu thu mới và tệp chia ghi vào đây, đích thật không
# bị đụng. Chỉ `hoa-de` để lượt chạy không phải chép cả kho.
cp -r /src/dataset/features/vn/hoa-de /tmp/dataset/features/vn/
ln -sfn /tmp/dataset /workspace/dataset
(cd /src/processed && tar --exclude=outputs --exclude=__pycache__ --exclude='*.pt' \
  --exclude=splits/versions --exclude=splits/prepare_runs -cf - .) | tar -xf - -C /workspace/processed
# `routers/training.py` ghi cứng /workspace; đây là bản sao ở _tmp/, dùng chung
# với dịch vụ realtime tạm.
ln -sfn /src/_tmp/kiem-thu/realtime_service /workspace/backend/realtime_service

python /src/scripts/kiem_thu_env/gieo_du_lieu.py

# Cùng lệnh với docker-compose: worker xử lý video và chia tập, trainer huấn luyện.
cd /src/backend
celery -A app.worker.celery_app worker -c 2 --loglevel=WARNING &
celery -A app.worker.celery_app worker -Q training -c 1 --max-tasks-per-child=1 -n trainer@%h --loglevel=WARNING &

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
