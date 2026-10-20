#!/usr/bin/env bash
# Dựng / gỡ môi trường thử. Cách ly khỏi sản xuất bằng TÊN DỰ ÁN compose.
#
#   ./scripts/staging.sh up       dựng và chờ khoẻ
#   ./scripts/staging.sh down     dừng, GIỮ dữ liệu
#   ./scripts/staging.sh reset    xoá sạch cả volume rồi dựng lại từ số không
#   ./scripts/staging.sh logs     bám log backend
#   ./scripts/staging.sh check    kiểm lược đồ + liệt kê trạng thái
#
# Vì sao là một script chứ không phải một dòng lệnh trong README: lệnh đúng cần
# BA cờ (`-p`, và hai `-f`), và bỏ sót `-p` là lệnh chạm thẳng vào stack sản
# xuất — cùng tên container, cùng volume. Một script là chỗ để cái ràng buộc đó
# không phụ thuộc vào trí nhớ.
set -euo pipefail

PROJECT="voya-staging"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Chỉ những dịch vụ staging thật sự cần. KHÔNG có `trainer` (không huấn luyện ở
# đây), không có Prometheus/Grafana/Loki (giám sát là việc của sản xuất), không
# có `pg-backup` (không có gì để sao lưu).
#
# `sot-init` và `realtime_service` nằm trong danh sách dù không ai gọi trực
# tiếp: `backend` phụ thuộc cả hai qua `depends_on`, nên compose kéo chúng vào
# dù có liệt kê hay không. Viết ra để danh sách này nói đúng những gì sẽ chạy —
# một danh sách nói thiếu là một danh sách người đọc sẽ tin nhầm.
SERVICES=(postgres redis sot-init realtime_service backend worker celery-beat frontend nginx)

compose() {
  docker compose -p "$PROJECT" \
    -f docker-compose.yml -f docker-compose.staging.yml "$@"
}

# Chốt an toàn: nếu vì lý do gì đó tên dự án bị đổi thành tên của sản xuất thì
# dừng ngay. Rẻ, và nó canh đúng thao tác không hoàn tác được.
guard() {
  if [[ "$PROJECT" == "voya-collector" || "$PROJECT" == "voya" ]]; then
    echo "TỪ CHỐI: tên dự án staging trùng tên dự án sản xuất." >&2
    exit 2
  fi
}

case "${1:-}" in
  up)
    guard
    compose up -d --build "${SERVICES[@]}"
    echo
    echo "Đang chờ backend khoẻ…"
    for _ in $(seq 1 60); do
      state="$(compose ps --format json backend 2>/dev/null | grep -o '"Health":"[a-z]*"' | head -1 || true)"
      [[ "$state" == *healthy* ]] && { echo "backend: healthy"; break; }
      sleep 2
    done
    compose ps
    echo
    echo "Mở: http://127.0.0.1:${STAGING_HTTP_PORT:-8080}"
    ;;

  down)
    guard
    compose down
    echo "Đã dừng. Volume GIỮ NGUYÊN — dùng 'reset' nếu muốn xoá."
    ;;

  reset)
    guard
    # `-v` xoá volume của DỰ ÁN NÀY. Tên dự án là thứ duy nhất ngăn nó chạm vào
    # volume sản xuất, nên `guard` ở trên không phải trang trí.
    read -r -p "Xoá sạch toàn bộ dữ liệu staging? [nhập 'xoa' để tiếp tục] " ans
    [[ "$ans" == "xoa" ]] || { echo "Huỷ."; exit 1; }
    compose down -v
    compose up -d --build "${SERVICES[@]}"
    echo "Đã dựng lại từ số không."
    ;;

  logs)
    compose logs -f backend
    ;;

  check)
    guard
    echo "=== trạng thái ==="
    compose ps
    echo
    echo "=== nợ lược đồ (phải rỗng) ==="
    # Đây là phép kiểm đáng giá nhất ở staging: nó chạy trên một CSDL dựng từ số
    # không, đúng kịch bản "máy thứ hai" từng hỏng trong im lặng.
    compose exec -T backend python -c "
from app.storage.metadata_db import schema_debt
from app.tenant_context import system_scope
with system_scope('staging: kiem no luoc do'):
    debt = schema_debt()
print(debt)
raise SystemExit(0 if not any(debt.values()) else 1)
"
    ;;

  *)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac
