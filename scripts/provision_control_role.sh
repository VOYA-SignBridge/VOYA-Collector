#!/usr/bin/env bash
# Cấp phát vai ĐIỀU KHIỂN `voya_control` và ghi `CONTROL_DATABASE_URL` vào .env.
#
# Vì sao cần một script riêng
# ---------------------------
# `deploy.sh` chặn khi thiếu `CONTROL_DATABASE_URL` và in ra ba bước làm tay.
# Ba bước đó dễ sai đúng ở chỗ tốn kém nhất:
#
#   * bước 2 phải truyền LẠI mật khẩu vai ứng dụng hiện có. Quên nó thì
#     `provision_db_roles` ĐỔI mật khẩu `voya_app`, và cả stack mất kết nối
#     ngay lượt khởi động sau — mà thông báo lỗi lúc đó là "authentication
#     failed", không hề nhắc tới lượt cấp phát vừa chạy.
#   * bước 3 gõ tay một DSN. Gõ nhầm tên cơ sở dữ liệu thì mặt phẳng điều khiển
#     trỏ sang một cơ sở dữ liệu khác, và thao tác xoá tổ chức chạy nhầm đích.
#
# Script này lấy mật khẩu ứng dụng và tên cơ sở dữ liệu TỪ `DATABASE_URL` đang
# có, nên hai chỗ trên không còn là chỗ để sai.
#
# Chạy lại được nhiều lần: đã có `CONTROL_DATABASE_URL` thì thoát 0 và không
# đụng gì.
#
#     bash scripts/provision_control_role.sh
#     bash scripts/provision_control_role.sh --force   # cấp lại mật khẩu mới
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=".env"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

[ -f "$ENV_FILE" ] || { echo "error: khong thay $ENV_FILE" >&2; exit 2; }

env_get() { sed -n "s/^$1=//p" "$ENV_FILE" | head -1 | tr -d '\r'; }

if [ -n "$(env_get CONTROL_DATABASE_URL)" ] && [ "$FORCE" -eq 0 ]; then
  echo "CONTROL_DATABASE_URL da co trong .env — khong lam gi. Dung --force de cap lai."
  exit 0
fi

DB_URL="$(env_get DATABASE_URL)"
[ -n "$DB_URL" ] || { echo "error: DATABASE_URL rong trong .env" >&2; exit 2; }

# Tách mật khẩu vai ứng dụng ra khỏi DSN. KHÔNG in ra, và KHÔNG truyền qua dòng
# lệnh của `docker` — nó sẽ nằm trong danh sách tiến trình của mọi người dùng
# khác trên máy. Đi qua tệp env của `docker compose run --env-file`.
APP_PW="$(printf '%s' "$DB_URL" | sed -E 's#^[a-z]+://[^:]+:([^@]*)@.*#\1#')"
[ -n "$APP_PW" ] || { echo "error: khong doc duoc mat khau tu DATABASE_URL" >&2; exit 2; }

# Máy mới thường bắt đầu từ .env.example, nên DATABASE_URL vẫn chứa CHANGE_ME.
# Ở chế độ --force (đã là yêu cầu xoay credential), tự sinh bí mật đủ mạnh thay
# vì tạo role bằng placeholder hoặc buộc người vận hành chép bí mật ra terminal.
if [ "${#APP_PW}" -lt 16 ]; then
  if [ "$FORCE" -ne 1 ]; then
    echo "error: mat khau trong DATABASE_URL phai co it nhat 16 ky tu" >&2
    echo "       dung --force de sinh credential moi va dong bo lai .env" >&2
    exit 2
  fi
  APP_PW="$(openssl rand -hex 24)"
fi

CTRL_PW="$(openssl rand -hex 24)"

SECRETS="$(mktemp)"
trap 'rm -f "$SECRETS"' EXIT
{
  printf 'VOYA_APP_DB_PASSWORD=%s\n' "$APP_PW"
  printf 'VOYA_CONTROL_DB_PASSWORD=%s\n' "$CTRL_PW"
} > "$SECRETS"

echo "==> cap phat vai voya_app / voya_control"
# Gắn mã nguồn CLI vào container: ảnh có thể còn cũ hơn cây mã, và lượt cấp
# phát này phải chạy đúng bản vừa sửa chứ không phải bản đã nướng vào ảnh.
docker compose run --rm --no-deps \
  --env-from-file "$SECRETS" \
  -v "$(pwd)/backend/app/cli/provision_db_roles.py:/app/app/cli/provision_db_roles.py:ro" \
  backend python -m app.cli.provision_db_roles

# DSN dựng bằng chính hàm của ứng dụng, không nối chuỗi ở shell: host, cổng và
# tên cơ sở dữ liệu lấy nguyên từ DSN hiện có.
URLS="$(
  docker compose run --rm --no-deps -T \
    --env-from-file "$SECRETS" \
    -v "$(pwd)/backend/app/cli/provision_db_roles.py:/app/app/cli/provision_db_roles.py:ro" \
    backend python -c '
import os
from app.cli.provision_db_roles import app_database_url, control_database_url
print("DATABASE_URL=" + app_database_url(os.environ["VOYA_APP_DB_PASSWORD"]))
print("CONTROL_DATABASE_URL=" + control_database_url(os.environ["VOYA_CONTROL_DB_PASSWORD"]))
' 2>/dev/null | tr -d '\r' | grep '_URL=postgresql'
)"

APP_URL="$(printf '%s\n' "$URLS" | sed -n 's/^DATABASE_URL=//p' | head -1)"
CTRL_URL="$(printf '%s\n' "$URLS" | sed -n 's/^CONTROL_DATABASE_URL=//p' | head -1)"

[ -n "$APP_URL" ] || { echo "error: khong dung duoc DATABASE_URL" >&2; exit 3; }
[ -n "$CTRL_URL" ] || { echo "error: khong dung duoc CONTROL_DATABASE_URL" >&2; exit 3; }

# Ghi vào .env: thay dòng cũ nếu có, không thì nối thêm. Cả DSN và biến
# provision phải cùng một bí mật để lần chạy lại không vô tình xoay lệch role.
env_set() {
  key="$1"
  value="$2"
  tmp="$(mktemp)"
  grep -v "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
}

env_set DATABASE_URL "$APP_URL"
env_set CONTROL_DATABASE_URL "$CTRL_URL"
env_set VOYA_APP_DB_PASSWORD "$APP_PW"
env_set VOYA_CONTROL_DB_PASSWORD "$CTRL_PW"

echo "==> da dong bo DATABASE_URL / CONTROL_DATABASE_URL trong .env"
echo "    kiem lai:  docker compose run --rm --no-deps backend python -m app.cli.provision_db_roles --check"
