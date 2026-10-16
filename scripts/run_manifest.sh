#!/usr/bin/env sh
# Ghi lại CHÍNH XÁC phép đo sắp chạy trên phiên bản nào.
#
#   sh scripts/run_manifest.sh <container> <fixture_dir> > manifest.json
#
# Vì sao cần
# ==========
# Ngày 16/08/2026 một vòng đo phải huỷ giữa chừng vì môi trường trôi bên dưới:
# `git HEAD` đổi, ảnh backend đổi, cây fixture bị xoá và gieo lại, và một kịch
# bản gieo mới xuất hiện — tất cả trong khoảng thời gian dựng phép đo. Không có
# manifest thì mọi con số thu được sau đó không quy thuộc được cho phiên bản nào,
# và một kết quả không quy thuộc được thì không dùng để bảo vệ điều gì.
#
# Nguyên tắc: HỎI, ĐỪNG SUY
# =========================
# Băm mã đọc từ BÊN TRONG container đang chạy, không đọc từ cây làm việc rồi cho
# rằng ảnh khớp. Danh tính cơ sở dữ liệu hỏi PostgreSQL bằng `current_database()`
# / `current_user`, không đọc lại chuỗi DSN. Hai lần trong dự án này, thứ đang
# chạy khác thứ người ta tưởng đang chạy — và cả hai lần chỉ một phép băm bên
# trong container mới phát hiện ra.
set -eu

export MSYS_NO_PATHCONV=1

CONTAINER="${1:-voya_backend_iso}"
FIXTURE="${2:-}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# Các tệp quyết định hành vi đang được đo. Thêm tệp vào đây khi phạm vi đo mở
# rộng — một tệp thiếu ở đây là một biến không kiểm soát.
FILES="catalog_sync.py dataset_samples.py dataset_manager.py preview_render.py
       preview_tasks.py routers/label_sessions.py tenant_context.py
       tenant_middleware.py"

bam_trong_container() {
  docker exec "$CONTAINER" sha256sum "/app/app/$1" 2>/dev/null | cut -d' ' -f1
}
bam_host() {
  sha256sum "$REPO/backend/app/$1" 2>/dev/null | cut -d' ' -f1
}

printf '{\n'
printf '  "thoi_diem": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '  "git_head": "%s",\n' "$(cd "$REPO" && git rev-parse HEAD)"
printf '  "git_sach": %s,\n' \
  "$(cd "$REPO" && [ -z "$(git status --porcelain)" ] && echo true || echo false)"
printf '  "git_status_dem_dong": %s,\n' \
  "$(cd "$REPO" && git status --porcelain | wc -l | tr -d ' ')"
printf '  "container": "%s",\n' "$CONTAINER"
printf '  "container_id": "%s",\n' \
  "$(docker inspect "$CONTAINER" --format '{{.Id}}' | cut -c1-12)"
printf '  "image_tag": "%s",\n' "$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
printf '  "image_digest": "%s",\n' "$(docker inspect "$CONTAINER" --format '{{.Image}}')"

# Danh tính CSDL: hỏi máy chủ, không đọc DSN.
docker exec "$CONTAINER" python -c "
import psycopg2, os, json
c = psycopg2.connect(os.environ['DATABASE_URL']); cur = c.cursor()
cur.execute('''SELECT current_database(), current_user, session_user,
                      (SELECT rolsuper     FROM pg_roles WHERE rolname = current_user),
                      (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)''')
db, cu, su, sup, byp = cur.fetchone()
for k, v in (('database', db), ('current_user', cu), ('session_user', su)):
    print(f'  \"{k}\": {json.dumps(v)},')
print(f'  \"rolsuper\": {json.dumps(sup)},')
print(f'  \"rolbypassrls\": {json.dumps(byp)},')
"

printf '  "ma_trong_container": {\n'
first=1
for f in $FILES; do
  ct="$(bam_trong_container "$f")"; ht="$(bam_host "$f")"
  [ -n "$ct" ] || ct="KHONG_DOC_DUOC"
  if [ "$ct" = "$ht" ]; then khop=true; else khop=false; fi
  [ $first -eq 1 ] || printf ',\n'
  first=0
  printf '    "%s": {"container": "%s", "worktree": "%s", "khop": %s}' \
    "$f" "$ct" "$ht" "$khop"
done
printf '\n  },\n'

if [ -n "$FIXTURE" ] && [ -d "$FIXTURE" ]; then
  printf '  "fixture_dir": "%s",\n' "$FIXTURE"
  if [ -f "$FIXTURE/fixture.json" ]; then
    printf '  "fixture_json_sha256": "%s",\n' \
      "$(sha256sum "$FIXTURE/fixture.json" | cut -d' ' -f1)"
  fi
  printf '  "fixture_co_marker_ready": %s,\n' \
    "$([ -f "$FIXTURE/.tenant-isolation-fixture" ] && echo true || echo false)"
fi

printf '  "seed_scripts": {\n'
printf '    "seed_cross_store.py": "%s",\n' \
  "$(sha256sum "$REPO/scripts/seed_cross_store.py" | cut -d' ' -f1)"
printf '    "seed_isolation_fixture.py": "%s",\n' \
  "$(sha256sum "$REPO/scripts/seed_isolation_fixture.py" | cut -d' ' -f1)"
printf '    "measure_reassign_gate.py": "%s"\n' \
  "$(sha256sum "$REPO/scripts/measure_reassign_gate.py" | cut -d' ' -f1)"
printf '  }\n}\n'
