#!/usr/bin/env sh
# Backend RIÊNG cho benchmark độ trễ. Không dùng chung với thí nghiệm cách ly.
#
# Vì sao phải tách khỏi `voya_backend_iso`
# ----------------------------------------
# Không phải để phòng xa — dữ liệu thật đã chứng minh hai lần trong cùng một
# buổi:
#
#   1. `voya_backend_iso` bị dựng lại lúc 16:54:14 giữa một lượt benchmark kết
#      thúc lúc 16:57:37. Toàn bộ 213 lượt lỗi truyền rơi vào đúng lượt chạy của
#      điểm cuối đang đo khi ấy.
#
#   2. Khi cây fixture cách ly được mount, `/classes/list` nhảy từ 22 byte lên
#      2.154 byte. Cùng một URL, cùng một bảng kết quả, KHỐI LƯỢNG CÔNG VIỆC
#      khác hẳn — và không có gì trong bảng nói cho người đọc biết điều đó.
#
# Trường hợp 2 nguy hiểm hơn trường hợp 1: một container sập thì thấy ngay, còn
# một workload bị đổi thì cho ra con số hoàn toàn "đẹp". Thí nghiệm này thay đổi
# dữ liệu là ĐÚNG NHIỆM VỤ của nó; vấn đề là để nó thay đổi dữ liệu của phép đo
# khác.
#
# Nên: cấu hình bất biến, không seed, không xoá fixture, không restart trong
# suốt lượt đo.
#
#   sh scripts/perf_backend.sh up|down|fingerprint
set -eu

export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.env"
ENV_FILE_MOUNT="$(cd "$REPO" && { pwd -W 2>/dev/null || pwd; })/.env"

NAME="${VOYA_PERF_CONTAINER:-voya_backend_perf}"
PORT="${VOYA_PERF_PORT:-8030}"
TEST_DB="${VOYA_TEST_DATABASE:-signdb_test}"
NETWORK="${VOYA_TEST_NETWORK:-voya-collector_voya_network}"
IMAGE="${VOYA_PERF_IMAGE:-voya_backend:latest}"
REDIS_DB="${VOYA_PERF_REDIS_DB:-10}"
WORKERS="${VOYA_PERF_WORKERS:-2}"

read_env() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r'; }

case "${1:-up}" in
  down)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    echo "da xoa $NAME"; exit 0 ;;
  fingerprint)
    # Vân tay dùng để so TRƯỚC và SAU lượt đo. Chỉ gồm những thứ mà một lần
    # dựng lại hoặc một lần đổi cấu hình sẽ làm đổi; KHÔNG gồm giờ hiện tại.
    docker inspect "$NAME" --format \
'{{.Id}}|{{.State.StartedAt}}|{{.Image}}|{{range .Config.Env}}{{if or (hasPrefix . "DATASET_ROOT=") (hasPrefix . "DATABASE_URL=") (hasPrefix . "RATE_LIMIT_CATALOG_PER_HOUR=")}}{{.}};{{end}}{{end}}|{{.Config.Cmd}}'
    exit 0 ;;
  up) ;;
  *) echo "dung: sh scripts/perf_backend.sh [up|down|fingerprint]"; exit 2 ;;
esac

OWNER_PW=$(read_env VOYA_TEST_OWNER_PASSWORD)
APP_PW=$(read_env VOYA_TEST_APP_PASSWORD)
[ -n "$APP_PW" ] || { echo "chua cap phat role test"; exit 2; }

docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "==> dung $NAME -> ${TEST_DB} (cong ${PORT}, ${WORKERS} worker)"

# KHÔNG mount cây dataset nào. Backend tự tạo một cây rỗng, và cây rỗng ấy là
# CỐ ĐỊNH suốt lượt đo — quan trọng hơn việc nó có bao nhiêu dữ liệu. Điểm cuối
# nào phụ thuộc dataset thì artifact phải ghi lại quy mô nó nhìn thấy
# (`preflight` trong measure_api_latency.py), để "12 ms" luôn đi kèm "cho danh
# sách bao nhiêu lớp".
docker run -d --name "$NAME" \
  --network "$NETWORK" \
  -p "127.0.0.1:${PORT}:8000" \
  --env-file "$ENV_FILE_MOUNT" \
  -e DATABASE_URL="postgresql://voya_test_app:${APP_PW}@postgres:5432/${TEST_DB}" \
  -e MIGRATION_DATABASE_URL="postgresql://voya_test_owner:${OWNER_PW}@postgres:5432/${TEST_DB}" \
  -e EXPECTED_DATABASE="$TEST_DB" \
  -e POSTGRES_DB="$TEST_DB" \
  -e REDIS_URL="redis://redis:6379/${REDIS_DB}" \
  -e CELERY_BROKER_URL="redis://redis:6379/${REDIS_DB}" \
  -e TTS_REDIS_URL="redis://redis:6379/${REDIS_DB}" \
  -e RATE_LIMIT_UPLOAD_PER_HOUR=1000000 \
  -e RATE_LIMIT_TRAINING_PER_HOUR=1000000 \
  -e RATE_LIMIT_CATALOG_PER_HOUR=1000000 \
  -e RATE_LIMIT_PREDICT_PER_MINUTE=1000000 \
  -e REGISTER_REQUESTS_PER_MINUTE=1000000 \
  -e REALTIME_SERVICE_URL="http://realtime_service:8010" \
  "$IMAGE" \
  gunicorn app.main:app -w "$WORKERS" -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 \
  >/dev/null

printf "==> doi healthy"
if curl -sf -o /dev/null --retry 60 --retry-delay 1 --retry-connrefused \
        --max-time 120 "http://127.0.0.1:${PORT}/health" 2>/dev/null; then
  echo " — OK"
else
  echo " — KHONG LEN DUOC"; docker logs --tail 40 "$NAME"; exit 1
fi

echo "==> van tay:"
sh "$0" fingerprint
echo
echo "san sang: http://127.0.0.1:${PORT}   (KHONG seed, KHONG restart trong luc do)"
