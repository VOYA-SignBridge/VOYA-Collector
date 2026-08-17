#!/usr/bin/env sh
# Chạy bộ test backend trên cơ sở dữ liệu TEST, không bao giờ trên sản xuất.
#
# Vì sao có tệp này
# -----------------
# `.env` của kho này trỏ vào `signdb` — cơ sở dữ liệu SẢN XUẤT. Cách chạy test
# vẫn dùng là nạp thẳng `.env` vào container test, nên mỗi lượt chạy suite đều
# ghi vào sản xuất: `migrate_database()`, `ensure_tables()` ở ba mươi tệp, các
# fixture seed và dọn dẹp.
#
# Ngày 13/08/2026 chuyện phải đến đã đến. Một lượt chạy suite áp một phần
# Billing v6 chưa hoàn chỉnh lên `signdb` và đóng dấu `schema_migrations`
# version=6 — đủ để ảnh v5 đang chạy TỪ CHỐI khởi động ở lần restart kế tiếp.
# Phải khôi phục bằng một lượt sửa ngược có kiểm chứng chạy thử trên clone.
#
# Có HAI lớp chặn, và tệp này là lớp dễ chịu:
#
#   lớp 1 (tệp này)     đổi tên cơ sở dữ liệu trong DSN trước khi container lên
#   lớp 2 (conftest)    `_refuse_if_database_is_not_a_test_database()` — bộ test
#                       tự từ chối chạy nếu `current_database()` không nằm
#                       trong danh sách cho phép, mã thoát 3
#
# Lớp 1 làm cho đường đúng dễ đi. Lớp 2 làm cho đường sai đi không được. Chỉ có
# lớp 1 thì người vội sẽ gõ lại lệnh `docker run` cũ; chỉ có lớp 2 thì không ai
# chạy được test.
#
# Dùng:
#   sh scripts/run_tests.sh                       # cả suite
#   sh scripts/run_tests.sh backend/tests/test_x.py -q
set -eu

# Git Bash trên Windows dịch mọi tham số trông giống đường dẫn POSIX sang đường
# dẫn Windows trước khi trao cho `docker.exe`, nên `-w /src` tới nơi thành
# `C:/Program Files/Git/src`. Vô hại trên Linux, bắt buộc ở đây.
export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Docker Desktop nhận đường dẫn Windows cho `-v`, không nhận `/e/...` của MSYS.
# `pwd -W` chỉ có ở Git Bash; ở nơi khác nó lỗi và ta giữ nguyên đường dẫn.
REPO_MOUNT="$(cd "$REPO" && { pwd -W 2>/dev/null || pwd; })"
ENV_FILE="$REPO/.env"
# `--env-file` cũng do docker.exe đọc, nên cũng cần đường dẫn Windows.
ENV_FILE_MOUNT="$REPO_MOUNT/.env"
TEST_DB="${VOYA_TEST_DATABASE:-signdb_test}"
IMAGE="${VOYA_TEST_IMAGE:-voya_backend_test:latest}"
NETWORK="${VOYA_TEST_NETWORK:-voya-collector_voya_network}"

# Đường dẫn TUYỆT ĐỐI tới `.env`. Bản trước dùng `. ./.env`, và khi thư mục
# làm việc trôi sang `frontend/` thì nó nạp một tệp khác — mật khẩu cơ sở dữ
# liệu thành rỗng và cả suite đỏ vì một lý do không liên quan gì tới mã.
[ -f "$ENV_FILE" ] || { echo "khong thay $ENV_FILE"; exit 2; }

case "$TEST_DB" in
  signdb|postgres|template0|template1)
    echo "TU CHOI: '$TEST_DB' khong phai co so du lieu test."; exit 2;;
esac

# Đổi CẢ danh tính lẫn đích: `postgresql://ai:gì@host:cổng/db` -> role test +
# cơ sở dữ liệu test, giữ nguyên host và cổng.
#
# Đổi tên cơ sở dữ liệu không thôi là chưa đủ. Sau lượt cấp phát ở
# `provision_test_db_roles.sh`, hai role này KHÔNG có quyền CONNECT vào
# `signdb`, nên một DSN viết sai lần nữa sẽ bị chính PostgreSQL từ chối chứ
# không phải bị một lớp mã nào đó bắt được. Đó là điểm của lớp thứ ba.
rewrite_dsn() {
  printf '%s' "$1" | sed -E "s#://[^@]*@#://$2:$3@#; s#/[^/?]*(\?|\$)#/$TEST_DB\1#"
}

app_dsn=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
mig_dsn=$(grep -E '^MIGRATION_DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
owner_pw=$(grep -E '^VOYA_TEST_OWNER_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)
test_pw=$(grep -E '^VOYA_TEST_APP_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)
control_pw=$(grep -E '^VOYA_TEST_CONTROL_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$app_dsn" ] || { echo "khong doc duoc DATABASE_URL tu $ENV_FILE"; exit 2; }
[ -n "$mig_dsn" ] || mig_dsn="$app_dsn"
if [ -z "$owner_pw" ] || [ -z "$test_pw" ] || [ -z "$control_pw" ]; then
  echo "Chua cap phat role test. Chay truoc:  bash scripts/provision_test_db_roles.sh"
  exit 2
fi

# Vai ỨNG DỤNG cho DSN thường (bộ test RLS phải chạy dưới đúng vai này), vai
# CHỦ SỞ HỮU cho DSN migration (ALTER TABLE đòi quyền sở hữu, không phải GRANT).
app_dsn=$(rewrite_dsn "$app_dsn" voya_test_app "$test_pw")
mig_dsn=$(rewrite_dsn "$mig_dsn" voya_test_owner "$owner_pw")
# Vai ĐIỀU KHIỂN. Bộ test chạy đường điều khiển bằng vai THẬT, không giả lập
# bằng `admin`: một phép kiểm chạy dưới superuser sẽ xanh dù mọi GRANT đều sai.
control_dsn=$(rewrite_dsn "$app_dsn" voya_test_control "$control_pw")

# Che mật khẩu khi in ra: dòng này đi vào nhật ký CI và vào ảnh chụp màn hình.
echo "==> dich test: $(printf '%s' "$app_dsn" | sed -E 's#://([^:]+):[^@]*@#://\1:***@#')"

[ $# -gt 0 ] || set -- backend/tests -q

# --------------------------------------------------------------------------
# Hai phụ thuộc CÓ THÌ CHẠY, KHÔNG CÓ THÌ SKIP. Thiếu chúng là 14 ca bỏ qua —
# và đó là kiểu skip tệ nhất: đọc lên như "môi trường không hỗ trợ" trong khi
# máy này hỗ trợ được, chỉ là không ai đưa tệp vào container.
#
# Cả hai đều gắn theo ĐIỀU KIỆN chứ không cứng, để script còn chạy được trên
# máy khác — ở đó chúng skip, đúng như trước.
# --------------------------------------------------------------------------
extra=""

# 1) Google Drive. `gdrive_client` tìm ĐÚNG /gdrive/credentials.json; mount
#    read-only vì bộ test chỉ cần đọc chứng thư, không cần ghi đè nó.
if [ -f "$REPO/gdrive/credentials.json" ]; then
  extra="$extra -v ${REPO_MOUNT}/gdrive:/gdrive:ro"
else
  echo "==> khong co gdrive/credentials.json — 13 ca SOT se skip"
fi

# 2) Một clip thật để chạy trích đặc trưng đầu-đến-cuối. `skipif` bám vào BIẾN
#    MÔI TRƯỜNG chứ không vào sự tồn tại của thư mục, nên mount không thôi là
#    chưa đủ — phải đặt cả VOYA_TEST_VIDEO.
VIDEO_DIR="${VOYA_TEST_VIDEO_DIR:-E:/CTU_ProjectOutside/qipedc_mau}"
VIDEO_NAME="${VOYA_TEST_VIDEO_NAME:-D0001B.mp4}"
if [ -f "$VIDEO_DIR/$VIDEO_NAME" ]; then
  extra="$extra -v ${VIDEO_DIR}:/testvideos:ro -e VOYA_TEST_VIDEO=/testvideos/${VIDEO_NAME}"
else
  echo "==> khong thay $VIDEO_DIR/$VIDEO_NAME — ca trich xuat that se skip"
fi

# 3) Hạ trần chờ Google Drive CHO LƯỢT CHẠY TEST.
#
# Mặc định trong `config.py` là 180 giây × 5 lần thử = tối đa 900 giây cho MỘT
# lượt gọi không tới đích. Hợp lý cho tác vụ nền tải tệp lớn; vô lý ở đây — đo
# ngày 17/08/2026, một lượt chạy suite đứng yên ở 62% suốt hơn mười phút với
# CPU container ~0%, và nhìn nhật ký thì không thấy gì vì pytest ở chế độ `-q`
# chỉ in dấu chấm cho ca ĐÃ XONG: ca đang chờ không bao giờ hiện ra.
#
# Loại trừ từng tệp là chữa triệu chứng — thử rồi: bỏ `test_sot_integration.py`
# (tệp duy nhất TESTING.md cảnh báo) thì lượt chạy dừng ở ĐÚNG cùng mốc 62%, vì
# tệp khác cũng gọi ra ngoài, có tệp gọi gián tiếp qua module ứng dụng nên
# `grep` theo tên thư viện không phủ hết. Hạ trần thì phủ mọi đường gọi, kể cả
# đường viết sau này.
#
# 5 giây × 1 lần: đủ cho một lượt gọi thật khi mạng bình thường, và biến một
# lượt hụt đích thành một ca đỏ nhanh thay vì mười lăm phút im lặng.
extra="$extra -e GOOGLE_DRIVE_TIMEOUT_SECONDS=${VOYA_TEST_GDRIVE_TIMEOUT:-5}"
extra="$extra -e GOOGLE_DRIVE_NUM_RETRIES=${VOYA_TEST_GDRIVE_RETRIES:-1}"

exec docker run --rm \
  --network "$NETWORK" \
  --env-file "$ENV_FILE_MOUNT" \
  -e DATABASE_URL="$app_dsn" \
  -e MIGRATION_DATABASE_URL="$mig_dsn" \
  -e CONTROL_DATABASE_URL="$control_dsn" \
  -e POSTGRES_DB="$TEST_DB" \
  $extra \
  -v "$REPO_MOUNT:/src" -w /src \
  "$IMAGE" \
  python -m pytest "$@"
