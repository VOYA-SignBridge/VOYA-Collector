#!/bin/sh
# Chạy seed_cross_store.py trong container, trên mạng compose.
#
# Vì sao phải qua container: PostgreSQL KHÔNG publish ra host (`5432/tcp` không
# có binding), nên kịch bản chạy thẳng trên Windows không nối được cơ sở dữ liệu.
# Cây fixture thì lại phải nằm trên host để `isolation_backend.sh` mount vào.
# Nên: mount cây làm việc vào /src, ghi cây ở /src/.measurement, chạy trong mạng.
#
# Dùng ĐÚNG bộ biến mà scripts/run_tests.sh dùng — cùng vai runtime, cùng CSDL
# test. Một fixture gieo bằng vai khác vai của phép đo là một fixture khác.
set -eu

# Git Bash trên Windows dịch mọi đối số trông như đường dẫn POSIX: `-w /src`
# thành `C:/Program Files/Git/src`. Đã mất giờ vì đúng lỗi này tám lần trong kho
# này — `run_tests.sh` và `isolation_backend.sh` đều mở đầu bằng dòng dưới.
export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
REPO_MOUNT="$(cd "$REPO" && { pwd -W 2>/dev/null || pwd; })"
ENV_FILE="$REPO/.env"
ENV_FILE_MOUNT="$REPO_MOUNT/.env"
TEST_DB="${VOYA_TEST_DATABASE:-signdb_test}"
IMAGE="${VOYA_TEST_IMAGE:-voya_backend_test:latest}"
NETWORK="${VOYA_TEST_NETWORK:-voya-collector_voya_network}"

[ -f "$ENV_FILE" ] || { echo "khong thay $ENV_FILE"; exit 2; }

app_dsn=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
test_pw=$(grep -E '^VOYA_TEST_APP_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$app_dsn" ] || { echo "khong doc duoc DATABASE_URL"; exit 2; }

# Cùng phép viết lại DSN như run_tests.sh: vai ứng dụng (NOSUPERUSER,
# NOBYPASSRLS) trên CSDL test. Gieo bằng vai owner sẽ đi vòng qua RLS và tạo ra
# một fixture mà chính ứng dụng không đọc được.
rewrite_dsn() {
  printf '%s' "$1" | sed -E "s#://[^:]+:[^@]+@#://$2:$3@#; s#/[^/?]+(\?|\$)#/$TEST_DB\1#"
}
app_dsn=$(rewrite_dsn "$app_dsn" voya_test_app "$test_pw")

exec docker run --rm \
  --network "$NETWORK" \
  --env-file "$ENV_FILE_MOUNT" \
  -e DATABASE_URL="$app_dsn" \
  -e POSTGRES_DB="$TEST_DB" \
  -v "$REPO_MOUNT:/src" -w /src \
  "$IMAGE" \
  python scripts/seed_cross_store.py "$@"
