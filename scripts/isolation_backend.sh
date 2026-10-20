#!/usr/bin/env sh
# Dựng một backend RIÊNG trỏ vào cơ sở dữ liệu TEST, để chạy bộ đo đối kháng
# cách ly tenant mà không chạm một byte nào của `signdb`.
#
# Vì sao phải là một backend riêng chứ không phải backend đang chạy
# -----------------------------------------------------------------
# Bộ đo đối kháng cố tình phát DELETE tenant, DELETE mẫu, DELETE lớp. Cả ba
# PHẢI bị chặn — nhưng phép đo tồn tại chính vì ta chưa chứng minh được điều
# đó. Nếu cách ly thủng, phép đo sẽ chứng minh bằng cách xoá thật. Đặt thí
# nghiệm an ninh vào đúng môi trường của nó là điều kiện để kết quả có giá trị:
# một câu "chúng tôi thử xoá dữ liệu sản xuất và may là không xoá được" thì
# không bảo vệ được trước hội đồng.
#
# Điều kiện để con số đo được có nghĩa
# ------------------------------------
# Vai runtime phải TƯƠNG ĐƯƠNG sản xuất, nếu không thì đo một hệ thống khác:
#   * `voya_test_app`  — NOSUPERUSER, NOBYPASSRLS, chỉ SELECT/INSERT/UPDATE/DELETE
#   * `voya_test_owner`— chỉ dùng cho DSN migration, không phục vụ request nào
# Hai vai này KHÔNG CONNECT được vào `signdb` (đã bỏ CONNECT khỏi PUBLIC ở
# `provision_test_db_roles.sh`), nên một DSN viết sai bị chính PostgreSQL chặn
# chứ không phải bị một lớp mã nào đó bắt được.
#
# RLS là RLS THẬT trên lược đồ thật. Không mock, không cắt policy — mock RLS thì
# phép đo mất toàn bộ giá trị.
#
# Giới hạn tần suất: nới TRONG MÔI TRƯỜNG TEST, không bao giờ trên sản xuất.
# Lý do kỹ thuật, không phải để lấy số đẹp: 429 rơi vào nhóm KHÔNG KẾT LUẬN
# ĐƯỢC, và nguyên tắc công bố là chỉ ghi CTIVR khi số ca không kết luận bằng 0.
# Để nguyên trần 300/giờ thì 510 phép thử sẽ ra 510 ca mờ và không đo được gì.
#
# Dùng:
#   sh scripts/isolation_backend.sh up      # dựng, đợi healthy
#   sh scripts/isolation_backend.sh down    # xoá
#   sh scripts/isolation_backend.sh logs
set -eu

export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO/.env"
ENV_FILE_MOUNT="$(cd "$REPO" && { pwd -W 2>/dev/null || pwd; })/.env"

NAME="${VOYA_ISO_CONTAINER:-voya_backend_iso}"
PORT="${VOYA_ISO_PORT:-8020}"
TEST_DB="${VOYA_TEST_DATABASE:-signdb_test}"
NETWORK="${VOYA_TEST_NETWORK:-voya-collector_voya_network}"
IMAGE="${VOYA_ISO_IMAGE:-voya_backend:latest}"
# Một chỉ số Redis RIÊNG: bộ đếm tần suất và bộ nhớ đệm của lượt đo không được
# trộn vào chỗ mà `signdb` đang dùng.
REDIS_DB="${VOYA_ISO_REDIS_DB:-9}"

[ -f "$ENV_FILE" ] || { echo "khong thay $ENV_FILE"; exit 2; }

case "$TEST_DB" in
  signdb|postgres|template0|template1)
    echo "TU CHOI: '$TEST_DB' khong phai co so du lieu test."; exit 2;;
esac

read_env() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r'; }

OWNER_PW=$(read_env VOYA_TEST_OWNER_PASSWORD)
APP_PW=$(read_env VOYA_TEST_APP_PASSWORD)
CONTROL_PW=$(read_env VOYA_TEST_CONTROL_PASSWORD)
if [ -z "$OWNER_PW" ] || [ -z "$APP_PW" ]; then
  echo "Chua cap phat role test. Chay truoc:  bash scripts/provision_test_db_roles.sh"
  exit 2
fi
# Vai DIEU KHIEN (15/08/2026). Khong bat buoc o day: anh `voya_backend:latest`
# co the con la ban TRUOC khi mat phang dieu khien ra doi, va no bo qua bien nay.
# Nhung mot lan do chay tren anh MOI ma thieu bien se lam moi thao tac dieu
# khien nem loi — va no se trong nhu mot ket qua do, chu khong nhu mot loi cau
# hinh. Truyen vao khi co, canh bao khi khong.
if [ -n "$CONTROL_PW" ]; then
  CONTROL_DSN="postgresql://voya_test_control:${CONTROL_PW}@postgres:5432/${TEST_DB}"
else
  CONTROL_DSN=""
  echo "[warn] chua co VOYA_TEST_CONTROL_PASSWORD — thao tac mat phang dieu khien"
  echo "       se nem loi neu anh nay da co mat phang dieu khien"
fi

APP_DSN="postgresql://voya_test_app:${APP_PW}@postgres:5432/${TEST_DB}"
MIG_DSN="postgresql://voya_test_owner:${OWNER_PW}@postgres:5432/${TEST_DB}"

# --------------------------------------------------------------------------
# Cây dataset DÙNG MỘT LẦN.
#
# Vì sao không mount `./dataset` của sản xuất
# -------------------------------------------
# Đường đọc lớp/mẫu KHÔNG thuần PostgreSQL: `list_classes()` gọi `load_labels()`
# và hàm đó đọc `labels.csv` TRÊN ĐĨA. Bộ thử đối kháng phát DELETE mẫu và
# DELETE lớp, nên mount cây thật là đặt CSV thật vào tầm bắn — đúng cái rủi ro
# mà việc rời khỏi `signdb` đang tránh, chỉ đổi từ hàng CSDL sang tệp.
#
# Vì sao phải SINH MỚI mỗi lượt chứ không giữ một thư mục test sống lâu
# ---------------------------------------------------------------------
# Bộ thử có DELETE. Nếu đối chứng dương chạy trước và xoá đúng đối tượng sau đó
# dùng làm mục tiêu đối kháng, ta lại được một loạt 404 "đẹp" mà vô nghĩa —
# cùng loại lỗi đã hai lần làm hỏng phép đo này, chỉ ở một tầng khác.
#
# Vì thế `control_*` và `target_*` là các đối tượng RIÊNG, và cả cây bị xoá sau
# mỗi lượt chạy.
#
# `DATASET_ROOT` là biến môi trường nên không cần mount đè lên `/dataset`.
# --------------------------------------------------------------------------
ISO_DATASET="${VOYA_ISO_DATASET:-}"
if [ -n "$ISO_DATASET" ]; then
  [ -d "$ISO_DATASET" ] || { echo "khong thay cay dataset: $ISO_DATASET"; exit 2; }
  case "$ISO_DATASET" in
    */dataset|*/dataset/) echo "TU CHOI: '$ISO_DATASET' trong nhu cay that."; exit 2;;
  esac
  ISO_DATASET_MOUNT="$(cd "$ISO_DATASET" && { pwd -W 2>/dev/null || pwd; })"
  DATASET_ARGS="-v ${ISO_DATASET_MOUNT}:/isodata -e DATASET_ROOT=/isodata"
  echo "==> cay dataset dung-mot-lan: $ISO_DATASET -> /isodata"
else
  DATASET_ARGS=""
  echo "[warn] khong co VOYA_ISO_DATASET — cac duong doc tu labels.csv se trong,"
  echo "       va doi chung duong cho lop/mau se TRUOT (dung nhu no phai the)"
fi

# --------------------------------------------------------------------------
# Mã ứng dụng ĐÃ ĐÓNG BĂNG.
#
# Vì sao không dựa vào tag ảnh
# ----------------------------
# Một tag bị dùng lại. Dựng lại `voya_backend:latest` để đo cũng có nghĩa là đổi
# thứ mà lần khởi động lại kế tiếp của sản xuất sẽ nạp — một tác dụng phụ không
# ai muốn ký tên vào. Và ngày 16/08/2026 đã gặp đúng ca xấu: container báo `Up`,
# tag đúng, mã cũ.
#
# `freeze_measurement_code.sh` tách hai danh tính ra:
#
#     phụ thuộc runtime  ->  digest của ẢNH NỀN (không đổi giữa các lượt đo)
#     mã ứng dụng        ->  tree_sha256 của SNAPSHOT (đổi theo từng lượt)
#
# Gắn snapshot đè lên `/app/app` READ-ONLY thì mã của lượt đo không đổi được nữa
# kể từ thời điểm chụp — kể cả khi cây làm việc chạy tiếp bên dưới, chuyện đã xảy
# ra bốn lần trong dự án này.
#
# READ-ONLY là bắt buộc: ứng dụng không được sửa chính thứ đang làm bằng chứng.
# `PYTHONDONTWRITEBYTECODE=1` để nó khỏi cần ghi `__pycache__` vào chỗ chỉ đọc.
# --------------------------------------------------------------------------
ISO_SNAPSHOT="${VOYA_ISO_SNAPSHOT:-}"
if [ -n "$ISO_SNAPSHOT" ]; then
  [ -f "$ISO_SNAPSHOT/SNAPSHOT.json" ] \
    || { echo "khong phai snapshot hop le: $ISO_SNAPSHOT"; exit 2; }
  SNAP_MOUNT="$(cd "$ISO_SNAPSHOT/backend/app" && { pwd -W 2>/dev/null || pwd; })"
  SNAPSHOT_ARGS="-v ${SNAP_MOUNT}:/app/app:ro -e PYTHONDONTWRITEBYTECODE=1"
  echo "==> ma dong bang: $ISO_SNAPSHOT -> /app/app (ro)"
else
  SNAPSHOT_ARGS=""
  echo "[warn] khong co VOYA_ISO_SNAPSHOT — dang do MA BAKED TRONG ANH '$IMAGE'."
  echo "       Ket qua chi quy thuoc duoc cho anh do, khong cho commit nao."
fi

cmd="${1:-up}"

case "$cmd" in
  down)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    echo "da xoa $NAME"
    exit 0
    ;;
  logs)
    exec docker logs --tail "${2:-80}" "$NAME"
    ;;
  up) ;;
  *) echo "dung: sh scripts/isolation_backend.sh [up|down|logs]"; exit 2;;
esac

docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "==> dung $NAME  ->  ${TEST_DB}  (vai voya_test_app, cong ${PORT})"

docker run -d --name "$NAME" \
  --network "$NETWORK" \
  -p "127.0.0.1:${PORT}:8000" \
  --env-file "$ENV_FILE_MOUNT" \
  -e DATABASE_URL="$APP_DSN" \
  -e MIGRATION_DATABASE_URL="$MIG_DSN" \
  -e CONTROL_DATABASE_URL="$CONTROL_DSN" \
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
  $DATASET_ARGS \
  $SNAPSHOT_ARGS \
  "$IMAGE" \
  gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 \
  >/dev/null

# Dùng cơ chế thử lại CỦA CURL thay cho vòng `while ... sleep 1`. Vòng lặp có
# `sleep` bị treo/chặn trong một số môi trường chạy lệnh không tương tác, và khi
# đó nó báo "quá hạn" cho một container thật ra đã phục vụ 200 từ giây thứ hai.
#
# KHÔNG dùng `-o /dev/null` ở tệp này. Dùng chuyển hướng của shell.
# ----------------------------------------------------------------------------
# Dòng `export MSYS_NO_PATHCONV=1` ở đầu tệp — thứ cần thiết để `-w /src` không
# bị dịch thành `C:/Program Files/Git/src` — cũng làm `/dev/null` được trao
# NGUYÊN VĂN cho `curl.exe` của Windows. Ở đó nó là một ĐƯỜNG DẪN TỆP không tồn
# tại, nên curl thoát **23 (write error)** dù máy chủ đã trả 200.
#
# Hai bản vá trong cùng một tệp đánh nhau, và hậu quả không hề giống nguyên nhân:
#
#   bản trước       -> 23 là lỗi vĩnh viễn -> bỏ thử lại -> hỏng sau 2 GIÂY
#   thêm retry-all  -> 23 thành lỗi tạm    -> thử đủ 60 lần -> hỏng sau 68 GIÂY
#                      trong khi nhật ký container ghi 60 dòng `GET /health 200`
#
# Cả hai đều báo "KHONG LEN DUOC" cho một container hoàn toàn khoẻ, và đều dừng
# cả trình tự đo. Chuyển hướng của shell do chính bash xử lý nên không đi qua
# phép dịch đường dẫn — đó mới là chỗ sửa đúng.
#
# `--retry-all-errors` vẫn giữ, nhưng vì một lý do KHÁC: Docker publish cổng
# ngay khi container start, nên vài giây trước lúc gunicorn bind, kết nối không
# bị *từ chối* mà được proxy của Docker **chấp nhận rồi reset** — một lỗi mà
# `--retry-connrefused` một mình không phủ.
printf "==> doi healthy"
if curl -sf --retry 60 --retry-delay 1 \
        --retry-connrefused --retry-all-errors \
        --connect-timeout 5 --max-time 120 \
        "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo " — OK"
else
  echo " — KHONG LEN DUOC"
  docker logs --tail 40 "$NAME"
  exit 1
fi

# Khẳng định lại từ BÊN TRONG: container phải thực sự nói chuyện với CSDL test
# bằng đúng vai không có đặc quyền. Đọc từ `current_database()`/`current_user`
# chứ không tin vào chuỗi DSN đã truyền vào.
echo "==> xac minh danh tinh runtime (hoi CSDL, khong doc lai DSN)"
docker exec "$NAME" python -c "
import psycopg2, os
c = psycopg2.connect(os.environ['DATABASE_URL']); cur = c.cursor()
cur.execute('''SELECT current_database(), current_user,
                      (SELECT rolsuper      FROM pg_roles WHERE rolname = current_user),
                      (SELECT rolbypassrls  FROM pg_roles WHERE rolname = current_user)''')
db, who, su, byp = cur.fetchone()
print(f'    database     = {db}')
print(f'    runtime_role = {who}')
print(f'    superuser    = {su}')
print(f'    bypass_rls   = {byp}')
assert db != 'signdb',  'DANG NOI CHUYEN VOI SAN XUAT'
assert su  is False,    'vai runtime la SUPERUSER'
assert byp is False,    'vai runtime co BYPASSRLS — moi phep do RLS se xanh gia'
print('    -> dat')
"
echo
echo "san sang:  http://127.0.0.1:${PORT}"
