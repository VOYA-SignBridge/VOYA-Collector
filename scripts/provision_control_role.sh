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
  --env-file "$SECRETS" \
  -v "$(pwd)/backend/app/cli/provision_db_roles.py:/app/app/cli/provision_db_roles.py:ro" \
  backend python -m app.cli.provision_db_roles

# DSN dựng bằng chính hàm của ứng dụng, không nối chuỗi ở shell: host, cổng và
# tên cơ sở dữ liệu lấy nguyên từ DSN hiện có.
CTRL_URL="$(
  docker compose run --rm --no-deps -T \
    --env-file "$SECRETS" \
    -v "$(pwd)/backend/app/cli/provision_db_roles.py:/app/app/cli/provision_db_roles.py:ro" \
    backend python -c '
import os
from app.cli.provision_db_roles import control_database_url
print(control_database_url(os.environ["VOYA_CONTROL_DB_PASSWORD"]))
' 2>/dev/null | tr -d '\r' | grep '^postgresql' | head -1
)"

[ -n "$CTRL_URL" ] || { echo "error: khong dung duoc CONTROL_DATABASE_URL" >&2; exit 3; }

# Ghi vào .env: thay dòng cũ nếu có, không thì nối thêm.
if grep -q '^CONTROL_DATABASE_URL=' "$ENV_FILE"; then
  tmp="$(mktemp)"
  grep -v '^CONTROL_DATABASE_URL=' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
fi
printf 'CONTROL_DATABASE_URL=%s\n' "$CTRL_URL" >> "$ENV_FILE"

echo "==> da ghi CONTROL_DATABASE_URL vao .env (vai voya_control)"
echo "    kiem lai:  docker compose run --rm --no-deps backend python -m app.cli.provision_db_roles --check"
