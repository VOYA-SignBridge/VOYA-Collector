#!/usr/bin/env bash
# Bring the stack up, using the GPU only when this host can actually run it.
#
# The GPU reservation lives in docker-compose.gpu.yml because `driver: nvidia`
# is resolved when the container is created: include it on a host without the
# NVIDIA Container Toolkit and the trainer dies with "could not select device
# driver", taking the deploy with it. Remembering to add or drop one -f flag per
# machine is exactly the kind of thing that gets forgotten, so probe instead.
#
#   ./scripts/deploy.sh              # up -d --build
#   ./scripts/deploy.sh --no-build   # up -d
#   ./scripts/deploy.sh --cpu        # force CPU even where a GPU exists
#
set -euo pipefail
cd "$(dirname "$0")/.."

FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
BUILD=(--build)
FORCE_CPU=0
SAVE_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=() ;;
    --cpu)      FORCE_CPU=1 ;;
    # Cất đường lùi rồi dừng, không dựng, không đụng stack. Có hai công dụng:
    # bảo đảm một bản lưu ngoài kho ảnh khi chưa định triển khai, và cho phép
    # kiểm chính đoạn mã ấy bằng đường chạy THẬT thay vì một bản sao logic
    # trong bài kiểm — hai nửa của một hợp đồng mà mỗi nửa tự kiểm bằng định
    # nghĩa riêng thì cả hai cùng xanh trong khi hợp đồng đã gãy.
    --save-rollback-only) SAVE_ONLY=1; BUILD=() ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

gpu_usable() {
  [ "$FORCE_CPU" -eq 1 ] && return 1
  # Not "is there a driver" but "can a container actually claim the GPU" —
  # the toolkit can be missing, or present and broken, and only the real
  # request tells them apart.
  docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 \
    nvidia-smi >/dev/null 2>&1
}

# Per-machine allowlist of public hostnames. It is gitignored (the tunnel name
# here is not the tunnel name there), so a fresh clone has none — and a missing
# file means an empty allowlist, which is safe but silent: reset-password mails
# quietly fall back to FRONTEND_BASE_URL and nobody notices until a user clicks
# a link pointing at the wrong host. Seed it from the example instead.
if [ ! -f deploy/public_hosts.txt ] && [ -f deploy/public_hosts.example.txt ]; then
  cp deploy/public_hosts.example.txt deploy/public_hosts.txt
  echo "==> Seeded deploy/public_hosts.txt from the example."
  echo "    Add this machine's public hostname to it — it is re-read per request,"
  echo "    so no restart is needed after an edit."
fi

# ---------------------------------------------------------------------------
# Pre-flight: catch the machine-specific failures BEFORE a 15-minute build.
#
# Every check below is something that already fails today — just later, and with
# a message that points somewhere else. The app refuses to start with weak
# secrets when APP_ENV=production, but only after the image is rebuilt and the
# container is up; `env_file: .env` fails with a compose error that reads like a
# YAML problem. Two seconds here beats a quarter of an hour there.
# ---------------------------------------------------------------------------
preflight_fail=0
note() { echo "    $*"; }
fail() { echo "    [FAIL] $*" >&2; preflight_fail=1; }

echo "==> Pre-flight…"

if [ ! -f .env ]; then
  fail ".env is missing. Copy .env.example and fill it in:  cp .env.example .env"
else
  # Read without sourcing: .env is not a shell script and may hold values with
  # spaces, '#', or quotes that would execute or truncate under `source`.
  env_get() { sed -n "s/^$1=//p" .env | tail -1 | tr -d '\r'; }

  app_env=$(env_get APP_ENV)
  for key in SECRET_KEY AUTH_TOKEN_SECRET_KEY; do
    value=$(env_get "$key")
    if [ -z "$value" ]; then
      fail "$key is not set in .env"
    elif [ "${#value}" -lt 32 ]; then
      if [ "$app_env" = "production" ]; then
        fail "$key is only ${#value} chars and APP_ENV=production — the backend "\
"will refuse to start. Generate one:  openssl rand -hex 32"
      else
        note "[warn] $key is only ${#value} chars (tolerated: APP_ENV=${app_env:-unset})"
      fi
    fi
  done

  for key in POSTGRES_PASSWORD VOYA_APP_DB_PASSWORD; do
    [ -n "$(env_get "$key")" ] || fail "$key is not set in .env"
  done

  # MAT PHANG DIEU KHIEN (15/08/2026).
  #
  # `tenant_purges` khong con nam trong tam voi cua vai ung dung; duong ghi so
  # cai purge di qua `CONTROL_DATABASE_URL`. Va `control_dsn()` CO Y khong lui
  # ve DATABASE_URL — thieu bien nay thi lenh purge nem loi.
  #
  # Bat o day chu khong de no lo ra luc co nguoi bam nut xoa mot to chuc: mot
  # thao tac khong hoan tac duoc khong phai cho de phat hien loi cau hinh.
  control_dsn=$(env_get CONTROL_DATABASE_URL)
  if [ -z "$control_dsn" ]; then
    fail "CONTROL_DATABASE_URL is not set in .env. Cap phat vai dieu khien truoc:
    1)  echo \"VOYA_CONTROL_DB_PASSWORD=\$(openssl rand -hex 24)\" >> .env
    2)  docker compose run --rm -e VOYA_CONTROL_DB_PASSWORD=... backend \\
            python -m app.cli.provision_db_roles
    3)  them CONTROL_DATABASE_URL=postgresql://voya_control:...@postgres:5432/<db>
Xem app/storage/control_plane.py ve vi sao duong nay khong duoc lui ve voya_app."
  fi

  # Kiem RE o day; kiem THAT nam o `_assert_control_identity`, chay moi lan mo
  # ket noi va hoi chinh co so du lieu xem no la ai. Cai nay chi bat loi dan
  # nhat truoc khi dung anh.
  case "$control_dsn" in
    *//voya_control:*) : ;;
    *//admin:*|*//voya_app:*)
      fail "CONTROL_DATABASE_URL tro vao vai ung dung/quan tri — ranh gioi tin
cay bien mat trong im lang. Phai la voya_control." ;;
    *) note "[warn] CONTROL_DATABASE_URL khong dung vai voya_control — backend se
    tu choi khi chay thao tac dieu khien" ;;
  esac

  # FRONTEND_BASE_URL must match the URL people actually open, or password-reset
  # and invitation links point at the wrong host on this machine.
  base_url=$(env_get FRONTEND_BASE_URL)
  [ -n "$base_url" ] || note "[warn] FRONTEND_BASE_URL is empty — mail links will be relative"
fi

docker info >/dev/null 2>&1 || fail "cannot talk to the Docker daemon — is Docker Desktop running?"

# ---------------------------------------------------------------------------
# Room on the drive that holds Docker's disk. Checked HERE, on the host, because
# nothing inside Docker can see it.
#
# On WSL2 the whole engine lives in one growing .vhdx file. That file only ever
# gets bigger — deleting images and cache frees space INSIDE it and returns
# nothing to the host — so `docker system df` can report tens of GB reclaimable
# while the host drive is at 99%. Measured 2026-08-13: 45.87 GB pruned, host
# free space unchanged at 2.6 GB, vhdx still 123.3 GB.
#
# Why it is a FAIL and not a warning: on 2026-08-05 a `docker compose build`
# started with ~1 GB free and killed `dockerd` outright, while Docker Desktop
# kept drawing containers in the UI as if nothing had happened.
#
# These two numbers are "free space needed before a CLEAN build", not the space
# this stack needs to RUN. A running stack needs almost nothing; a build with a
# cold cache is what eats the drive.
#
# Where 55 comes from: the cache-less rebuild on 2026-08-12 grew the vhdx from
# 24.4 GB to 67.5 GB — 43 GB for one build. The first draft of this guard said
# 20 GB, which is under half of a single measured build. 55 GB is that 43 GB
# times 1.28, i.e. one full build plus room to be wrong.
#
# When more clean builds get measured, replace this with `worst observed x 1.25`
# rather than nudging the number by feel. One measurement with a margin is
# honest; a number that drifts because it "felt tight" is not.
# ---------------------------------------------------------------------------
DISK_FAIL_GB=55
DISK_WARN_GB=65

docker_disk_report() {
  # Windows/WSL2: find the vhdx, report its drive. Prints "<free_gb> <vhdx_gb>".
  command -v powershell >/dev/null 2>&1 || return 1
  powershell -NoProfile -Command '
    $dir = $null
    $s = "$env:APPDATA\Docker\settings-store.json"
    if (Test-Path $s) { $dir = (Get-Content $s -Raw | ConvertFrom-Json).CustomWslDistroDir }
    if (-not $dir) { $dir = "$env:LOCALAPPDATA\Docker\wsl" }
    if (-not (Test-Path $dir)) { exit 1 }
    $drive = (Get-Item $dir).PSDrive.Name
    $free  = (Get-PSDrive $drive).Free / 1GB
    $vhdx  = (Get-ChildItem $dir -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue |
              Measure-Object -Property Length -Sum).Sum / 1GB
    "{0:N1} {1:N1} {2}" -f $free, $vhdx, $drive
  ' 2>/dev/null | tr -d '\r'
}

disk_line=$(docker_disk_report || true)
if [ -n "$disk_line" ]; then
  set -- $disk_line
  free_gb="$1"; vhdx_gb="$2"; drive="$3"
  free_int=${free_gb%%.*}
  note "Docker disk: ${drive}: has ${free_gb} GB free, vhdx is ${vhdx_gb} GB"

  if [ "$free_int" -lt "$DISK_FAIL_GB" ] && [ "$SAVE_ONLY" -eq 1 ]; then
    # Ngưỡng này đo cho một lượt DỰNG ảnh, thứ làm vhdx phình. `--save-rollback-only`
    # không dựng gì và ghi ra ổ khác, nên áp ngưỡng ấy ở đây là chặn nhầm —
    # đúng lúc người ta cần cất đường lùi nhất, tức là khi đĩa đang chật.
    note "[warn] chi con ${free_gb} GB tren ${drive}: — bo qua vi --save-rollback-only khong dung anh"
  elif [ "$free_int" -lt "$DISK_FAIL_GB" ]; then
    fail "only ${free_gb} GB free on ${drive}: — one measured clean build grew "\
"the vhdx by 43 GB, and a build that runs out has killed dockerd here before. "\
"Reclaim space FIRST:  bash scripts/docker_gc.sh"
  elif [ "$free_int" -lt "$DISK_WARN_GB" ]; then
    note "[warn] under ${DISK_WARN_GB} GB free — run \`bash scripts/docker_gc.sh\` soon."
  fi
else
  note "[warn] could not measure the Docker disk (not Windows, or layout changed) — skipped"
fi

if [ "$preflight_fail" -ne 0 ]; then
  echo
  echo "Pre-flight failed. Nothing was built or started." >&2
  exit 3
fi
note "ok"

# `--save-rollback-only` KHÔNG dò GPU và KHÔNG ghi lại `COMPOSE_FILE`.
#
# Phép dò là một `docker run` thật, và nó trượt được vì lý do nhất thời. Khi ấy
# `upsert_env` bên dưới sẽ ghi một `COMPOSE_FILE` KHÔNG có `docker-compose.gpu.yml`
# vào `.env` — và theo đúng chú thích ở khối đó, mọi lệnh compose sau này trong
# thư mục này sẽ mất overlay GPU mà không có gì báo. Một thao tác chỉ-đọc-và-lưu
# thì không được phép để lại hậu quả đó.
if [ "$SAVE_ONLY" -eq 1 ]; then
  echo "==> --save-rollback-only: bo qua do GPU va khong ghi .env"
else

echo "==> Probing for a usable GPU…"
if gpu_usable; then
  NAME=$(docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 \
           nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
  echo "    GPU available: ${NAME:-unknown} — adding docker-compose.gpu.yml"
  FILES+=(-f docker-compose.gpu.yml)
else
  if [ "$FORCE_CPU" -eq 1 ]; then
    echo "    --cpu given; skipping the GPU overlay."
  else
    echo "    No usable GPU (no card, or the NVIDIA Container Toolkit is missing)."
    echo "    Starting CPU-only — training still runs, just slower."
  fi
fi

# ---------------------------------------------------------------------------
# Persist the file list into .env as COMPOSE_FILE.
#
# THIS is why the GPU kept disappearing. The probe above is correct and the
# deploy that follows it is correct — but the overlay only lives in this
# script's argv. Anything else that touches the stack loses it:
#
#     docker compose up -d              # bare, no -f  -> trainer without GPU
#     docker compose restart trainer    # ditto
#     the Restart button in Docker Desktop
#     a copy-pasted command from an older note
#
# and none of them fail. The trainer comes up perfectly healthy with
# DeviceRequests=null and quietly trains on CPU, which is why it took a
# screenshot of the monitoring page to notice.
#
# Compose reads COMPOSE_FILE from the .env file in the project directory, so
# writing it there makes the plain `docker compose` command in this folder mean
# the right thing for everyone — including tools that never heard of this
# script. COMPOSE_PATH_SEPARATOR is pinned because its default differs by
# platform (';' on Windows, ':' elsewhere) and this repo is deployed on both.
# ---------------------------------------------------------------------------
compose_file_value=""
for f in "${FILES[@]}"; do
  [ "$f" = "-f" ] && continue
  compose_file_value="${compose_file_value:+$compose_file_value:}$f"
done

upsert_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    # In-place with a temp file: `sed -i` differs between GNU and BSD.
    sed "s|^${key}=.*|${key}=${value}|" .env > .env.tmp && mv .env.tmp .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

upsert_env COMPOSE_PATH_SEPARATOR ":"
upsert_env COMPOSE_FILE "$compose_file_value"
echo "==> .env: COMPOSE_FILE=$compose_file_value"
echo "    (a bare \`docker compose up -d\` in this folder now keeps the same overlays)"

fi  # kết thúc nhánh "không phải --save-rollback-only"

# ---------------------------------------------------------------------------
# Migration, as its own step, BEFORE the application comes up.
#
# Until 2026-08-12 this step did not exist: `ensure_tables()` ran the whole DDL
# — including dropping tables and copying data into new shapes — on every
# backend start. Every `docker compose up` was therefore an unannounced
# migration, and on 12/08 a harmless-looking verification command used that
# path to reshape the production schema.
#
# The backend now REFUSES to start when the schema version does not match the
# image, so this step is not optional politeness — skip it on a database that
# needs migrating and the stack will not come up. That is the intended failure:
# loud, immediate, and before anything writes.
#
# Order: build -> Postgres only -> migrate -> everything.
# ---------------------------------------------------------------------------

# Build FIRST, as its own command.
#
# `up -d --build postgres redis` would not do it: with service names given,
# compose builds only those services, and postgres/redis are pulled images with
# no build context. The migration step below then runs `docker compose run
# backend` against the PREVIOUS image — which is the image whose schema
# expectations we are trying to move away from. That is the exact skew this
# whole step exists to prevent, so it must not be reintroduced by the step.
# ---------------------------------------------------------------------------
# Cất đường lùi RA NGOÀI kho ảnh của Docker, TRƯỚC khi ảnh mới đè lên tag cũ.
#
# Vì sao không phải một cái tag
# ------------------------------
# Ngày 15/08/2026 đường lùi được chuẩn bị đúng cách — `voya_backend:pre-f882414`
# và `voya_frontend:pre-f882414` — rồi biến mất trước khi kịp dùng: một lượt
# `docker_gc.sh` dọn sâu đã xoá chúng, vì lúc đó chúng không còn container nào
# tham chiếu. Cả hai việc đều "đúng" theo cách nhìn của mình, và kết quả là
# lượt triển khai rủi ro nhất trong tuần chạy mà không có đường lùi nhanh.
#
# Bài học không phải "đừng dọn rác", mà là: **một tag trong cùng daemon mà
# script GC đang quét thì không phải bản lưu.** Tệp .tar nằm ngoài kho ảnh thì
# `docker image prune -a` không với tới được.
#
# Ghi bằng chuyển hướng của shell chứ không truyền đường dẫn cho `docker -o`:
# Git Bash dịch tham số trông giống đường dẫn POSIX, và chính lớp dịch đó đã
# làm hỏng phép tự kiểm sao lưu lẫn bước nén vhdx trong `docker_gc.sh`. Shell
# tự mở tệp thì không có gì để dịch sai.
# ---------------------------------------------------------------------------
ROLLBACK_DIR="${ROLLBACK_DIR:-E:/CTU_ProjectOutside/voya_backups/rollback}"
ROLLBACK_KEEP="${ROLLBACK_KEEP:-2}"

save_rollback() {
  local img="$1" name="$2" out size_bytes free_bytes
  docker image inspect "$img" >/dev/null 2>&1 || {
    note "[skip] chua co $img — may nay chua tung trien khai, khong co gi de lui ve"
    return 0
  }

  mkdir -p "$ROLLBACK_DIR" || { fail "khong tao duoc $ROLLBACK_DIR"; return 1; }

  # Tên tệp mang ID CỦA CHÍNH ẢNH, không mang "phiên bản sắp triển khai".
  #
  # Bản đầu đặt tên `${name}_pre_${new_rev}` với nghĩa "ảnh đang sống TRƯỚC khi
  # triển khai <rev>". Đúng khi chạy đúng luồng, nhưng sai ngay khi chạy
  # `--save-rollback-only` sau lúc đã triển khai: tệp chứa ảnh f882414 mà tên
  # lại ghi `pre_f882414`. Một hiện vật cứu hộ mà nội dung phụ thuộc vào việc
  # ai đó chạy lệnh lúc nào thì không dùng được lúc đang hoảng.
  #
  # `image_id` thì tự nó nói ra nó là ai, bất kể chạy khi nào.
  img_id=$(docker image inspect "$img" --format '{{.Id}}' 2>/dev/null | sed 's/^sha256://' | cut -c1-12)
  out="$ROLLBACK_DIR/${name}_${img_id}_${stamp}.tar"

  # Hệ số 3, và nó không phải cho chắc ăn — hai nguồn số trên chính máy này
  # KHÔNG khớp nhau. Đo 15/08/2026 với `voya_backend:latest`:
  #
  #     docker images        -> 13.3 GB   (đã bung)
  #     inspect .Size        ->  4.53 GB  (đã nén)
  #
  # Kho ảnh containerd báo hai con số khác nhau cho cùng một ảnh, và không có
  # gì hứa `docker save` sẽ ra con số nào. Đoán trúng bên nhỏ rồi hết đĩa giữa
  # chừng thì để lại một tệp .tar cụt — đúng loại "bản lưu có mà không dùng
  # được" mà cả tệp này đang cố tránh. Lấy dư 3 lần là rẻ hơn nhiều.
  size_bytes=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null || echo 0)
  need_bytes=$((size_bytes * 3))
  free_bytes=$(df -P "$ROLLBACK_DIR" 2>/dev/null | awk 'NR==2 {print $4 * 1024}')
  if [ -n "$free_bytes" ] && [ "$free_bytes" -lt "$need_bytes" ]; then
    fail "$ROLLBACK_DIR chi con $((free_bytes / 1024 / 1024 / 1024)) GB, can "\
"$((need_bytes / 1024 / 1024 / 1024)) GB cho $img"
    return 1
  fi

  note "luu $img -> $(basename "$out") ($((size_bytes / 1024 / 1024 / 1024)) GB)…"
  if ! docker save "$img" > "$out"; then
    rm -f "$out"
    fail "docker save $img that bai"
    return 1
  fi

  # Đọc HẾT tệp, không chỉ liếc phần đầu. `pg_restore --list` từng cho một bản
  # sao lưu cụt điểm "đạt" vì mục lục nằm ở đầu tệp; tệp .tar cũng vậy. Một
  # đường lùi chưa từng được đọc trọn thì chưa phải đường lùi.
  #
  # `--force-local` là BẮT BUỘC, không phải cho chắc. `$out` bắt đầu bằng
  # `E:/…`, và `tar` đọc `host:path` theo cú pháp kho lưu từ xa — nó đi phân
  # giải tên máy `E:` rồi trả `Cannot connect to E: resolve failed` (exit 128).
  # Đo 15/08/2026: một tệp .tar HOÀN TOÀN LÀNH bị phép kiểm này báo hỏng, và
  # script đã xoá nó đi rồi từ chối triển khai.
  #
  # Đây là lần thứ BA trong một ngày cùng một hình dạng — `pg_restore` với
  # `/b/…`, `-File` với `/tmp/…`, và giờ là `tar` với `E:/…`. Lớp dịch đường
  # dẫn của Git Bash làm hỏng đúng những bước KIỂM CHỨNG, và cách sai để "sửa"
  # là nới phép kiểm ra cho nó xanh.
  if ! tar --force-local -tf "$out" >/dev/null 2>&1; then
    rm -f "$out"
    fail "$(basename "$out") khong doc het duoc — da xoa, KHONG giu ban luu hong"
    return 1
  fi
  note "  DAT — doc tron tep"

  # Tệp kèm: tên tệp nói ảnh nào, tệp này nói bối cảnh. Không có nó thì sáu
  # tháng sau `backend_a1b2c3d4e5f6_20260815.tar` là một chuỗi hex vô nghĩa.
  {
    printf 'image_ref=%s\n' "$img"
    printf 'image_id=%s\n' "$img_id"
    printf 'saved_at=%s\n' "$(date -Iseconds)"
    printf 'git_head_when_saved=%s\n' "$new_rev"
    printf 'khoi_phuc=docker load -i %s\n' "$(basename "$out")"
  } > "${out%.tar}.meta"

  # Dọn bản cũ SAU khi bản mới đã được xác minh, không bao giờ trước.
  # `|| true` ở cuối: khi chưa có bản cũ nào thì `ls` thoát khác 0, và dưới
  # `set -e` một hàm kết thúc bằng đường ống hỏng sẽ bị coi là hỏng — tức là
  # lượt lưu ĐÚNG lại bị báo thất bại chỉ vì không có gì để dọn.
  ls -1t "$ROLLBACK_DIR/${name}_"*.tar 2>/dev/null | tail -n +$((ROLLBACK_KEEP + 1)) \
    | while read -r old; do
        note "  go ban cu: $(basename "$old")"
        rm -f "$old"
      done || true
}

if [ ${#BUILD[@]} -gt 0 ] || [ "$SAVE_ONLY" -eq 1 ]; then
  new_rev=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  stamp=$(date +%Y%m%d_%H%M%S)

  echo "==> Cat duong lui (ngoai kho anh Docker)…"
  rollback_fail=0
  save_rollback voya_backend:latest  backend  || rollback_fail=1
  save_rollback voya_frontend:latest frontend || rollback_fail=1

  if [ "$rollback_fail" -ne 0 ]; then
    echo >&2
    echo "    [FAIL] khong cat duoc duong lui. NOTHING WAS BUILT." >&2
    echo "           Trien khai khong co duong lui la dieu 15/08 da tra gia." >&2
    echo "           Bo qua co y:  ROLLBACK_DIR=... hoac sua cho chua." >&2
    exit 3
  fi

  if [ "$SAVE_ONLY" -eq 1 ]; then
    echo "==> --save-rollback-only: da cat duong lui, khong dung gi, khong dung stack."
    ls -1t "$ROLLBACK_DIR"/*.tar 2>/dev/null | head -6 || true
    exit 0
  fi
fi

if [ ${#BUILD[@]} -gt 0 ]; then
  echo "==> docker compose ${FILES[*]} build"
  docker compose "${FILES[@]}" build
fi

# ---------------------------------------------------------------------------
# DỪNG ứng dụng TRƯỚC khi migration chạy. Đây là bước 15/08/2026 thêm vào, và
# nó sửa một cuộc đua có thật chứ không phải phòng xa.
#
# Thứ tự cũ là `build -> migrate -> up`, nghĩa là lượt migration chạy trong khi
# ẢNH CŨ vẫn đang phục vụ. Bản cũ vẫn giữ quyền đổi lược đồ: `ensure_tables()`
# chạy ở mỗi lần một tiến trình ứng dụng khởi động, và `docker-compose.yml`
# cho gunicorn `--max-requests 1000 --max-requests-jitter 100` — worker được
# thay định kỳ, mỗi worker mới chạy lại `ensure_tables()`.
#
# Hệ quả đo được ngày 15/08: `migrate --to 5` gỡ
# `uq_classes_tenant_slug_lang_dialect` lúc 04:01:21; đến 04:03 chỉ mục ĐÃ QUAY
# LẠI. Chạy đúng lệnh đó lúc 04:07, khi chỉ còn ảnh mới, thì nó gỡ sạch và khởi
# động lại không dựng lại nữa. Cơ chế chính xác không tái dựng được (ảnh cũ đã
# bị xoá) nên ghi là **cơ chế nhiều khả năng, chưa tái hiện** — nhưng cuộc đua
# thì không cần đo mới biết: hai bản mã cùng có quyền ghi lược đồ trong cùng
# một cửa sổ thời gian.
#
# Vì sao `stop` TẤT CẢ chứ không liệt kê service:
# năm service dùng chung ảnh backend (`backend`, `worker`, `trainer`,
# `celery_beat`, `sot_init`) và danh sách đó đã từng bị quên đúng một mục —
# `celery_beat`. Một danh sách phải nhớ là một danh sách sẽ sai; "dừng hết rồi
# bật lại đúng hai cái cần" thì không có gì để quên.
#
# Cái giá: thời gian ngừng dịch vụ dài hơn, tính từ đây thay vì từ `up -d`.
# Đó là đánh đổi có chủ ý — lượt triển khai vốn đã làm gián đoạn khi thay
# container; điều thay đổi là bây giờ nó trung thực về việc đó.
echo "==> Dung ung dung truoc khi migration chay…"
docker compose "${FILES[@]}" stop >/dev/null 2>&1 || true

echo "==> Starting Postgres…"
docker compose "${FILES[@]}" up -d postgres redis

echo "==> Waiting for Postgres…"
until [ "$(docker compose "${FILES[@]}" ps -q postgres | xargs -r docker inspect \
          -f '{{.State.Health.Status}}' 2>/dev/null)" = "healthy" ]; do
  sleep 2
done

# The target database name comes from the DSN, NOT from POSTGRES_DB.
#
# This is the incident in one line. The command that migrated production said
# `-e POSTGRES_DB=authz_v5` and believed that aimed it at a clone; the
# application resolves MIGRATION_DATABASE_URL/DATABASE_URL and ignored it. So
# the guard is fed from the same string the application actually connects with.
dsn=$(env_get MIGRATION_DATABASE_URL)
[ -n "$dsn" ] || dsn=$(env_get DATABASE_URL)
expected_db=$(printf '%s' "$dsn" | sed -n 's#.*/\([^/?]*\)\(?.*\)\?$#\1#p')

if [ -z "$expected_db" ]; then
  echo "    [FAIL] cannot read the database name out of MIGRATION_DATABASE_URL/DATABASE_URL." >&2
  echo "           Migration will not run blind. Fix the DSN in .env." >&2
  exit 3
fi

# Ask the IMAGE which schema version it writes, rather than hardcoding it here.
# A number in this script would drift from the code the moment someone bumps
# APP_SCHEMA_VERSION, and it would drift silently.
target_version=$(docker compose "${FILES[@]}" run --rm --no-deps -T backend \
  python -c "from app.storage.schema_version import APP_SCHEMA_VERSION; print(APP_SCHEMA_VERSION)" \
  2>/dev/null | tr -d '\r' | tail -1)

if ! printf '%s' "$target_version" | grep -qE '^[0-9]+$'; then
  echo "    [FAIL] could not read APP_SCHEMA_VERSION out of the backend image." >&2
  exit 3
fi

echo "==> Migration: $expected_db -> schema v$target_version"
if ! docker compose "${FILES[@]}" run --rm --no-deps -T \
     -e EXPECTED_DATABASE="$expected_db" backend \
     python -m app.cli.migrate --to "$target_version"; then
  echo >&2
  echo "    [FAIL] migration did not complete. NOTHING ELSE WAS STARTED." >&2
  echo "           The old containers are still running the old code; the" >&2
  echo "           deployment is not half-applied." >&2
  echo "           Diagnose with:  docker compose run --rm backend \\" >&2
  echo "                             python -m app.cli.migrate --status" >&2
  exit 4
fi

# ---------------------------------------------------------------------------
# Hợp đồng lược đồ có HAI tập, và `--status` hỏi cả hai:
#
#     required_objects   phải CÓ MẶT
#     retired_objects    phải VẮNG MẶT
#
# Migration thoát 0 chỉ nói "các câu đã chạy xong", không nói "lược đồ đã ở
# trạng thái đích". Ngày 15/08 hai điều đó khác nhau: migration thoát 0 và chỉ
# mục đáng lẽ đã retire vẫn nằm đó. Nên đây là một CỔNG riêng, không phải một
# dòng in cho vui.
# ---------------------------------------------------------------------------
schema_status() {
  docker compose "${FILES[@]}" run --rm --no-deps -T \
    -e EXPECTED_DATABASE="$expected_db" backend \
    python -m app.cli.migrate --status 2>&1 | grep -v MIGRATION-TARGET
}

echo "==> Kiem lai luoc do TRUOC khi bat ung dung…"
if ! schema_status; then
  echo >&2
  echo "    [FAIL] luoc do KHONG o trang thai dich sau migration." >&2
  echo "           NOTHING ELSE WAS STARTED — ung dung van dang dung." >&2
  exit 4
fi

# No `--build` here: the build already happened above, before the migration.
# Passing it again re-exports every image layer for no benefit — measured at
# several minutes on this machine during the 12/08 deploy, all of it after the
# schema had already changed. `--no-build` still works: it empties BUILD, the
# build step above is skipped, and this line uses the existing images.
echo "==> docker compose ${FILES[*]} up -d"
docker compose "${FILES[@]}" up -d

echo "==> Waiting for health checks to settle…"
until [ "$(docker ps --filter health=starting --format '{{.Names}}' | wc -l)" -eq 0 ]; do
  sleep 5
done

docker compose "${FILES[@]}" ps -a --format "{{.Name}}\t{{.Status}}"

# ---------------------------------------------------------------------------
# Kiểm lại lược đồ SAU khi ứng dụng mới đã lên. Đây là nửa còn lại của bài học
# 15/08, và nó hỏi một câu mà lần kiểm trước không hỏi được:
#
#     "vòng đời khởi động của ảnh MỚI có dựng lại thứ gì migration vừa gỡ không?"
#
# Lần kiểm trước chạy khi chưa có tiến trình ứng dụng nào sống, nên nó không
# thể trả lời câu đó. `ensure_tables()` chạy ở mỗi lần một tiến trình lên, và
# gunicorn còn thay worker giữa chừng — nên "lược đồ đúng lúc migration xong"
# và "lược đồ đúng khi hệ thống đang chạy" là hai khẳng định khác nhau.
#
# Đây là CẢNH BÁO chứ không phải lỗi dừng máy: tới đây stack đã lên và đang
# phục vụ, nên tự ý dừng lại không lấy lại được gì. Nhưng nó phải ồn, vì trạng
# thái này có nghĩa là đường khởi động đang hoàn tác việc của migration — đúng
# thứ đã âm thầm xảy ra hai lần trước khi có phép kiểm này.
# ---------------------------------------------------------------------------
echo "==> Kiem lai luoc do SAU khi ung dung da len…"
if schema_status; then
  echo "    luoc do van o trang thai dich sau khi ung dung khoi dong."
else
  echo >&2
  echo "    [WARN] LUOC DO LECH SAU KHI UNG DUNG LEN." >&2
  echo "           Migration da dat trang thai dich, roi duong KHOI DONG doi no." >&2
  echo "           Nghi truoc tien: mot cau CREATE cua doi tuong vua retire van" >&2
  echo "           con trong duong khoi dong — retire thi phai GO cau tao, them" >&2
  echo "           cau xoa la chua du. Xem metadata_db.retired_indexes()." >&2
fi

# The trainer picks the device itself (train_tcn.pick_device) and refuses a GPU
# whose compute capability this torch build has no kernels for, so this line is
# the ground truth for whether training will really use the card.
echo "==> Trainer device:"
TRAINER=$(docker ps -qf name=_trainer | head -1)
docker exec "$TRAINER" python -c "
import sys; sys.path.insert(0,'/workspace')
from processed.train_utils.train_tcn import pick_device
import torch
print('   ', pick_device(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA device')
" 2>/dev/null || echo "    (trainer not up yet)"

# The probe said this host has a GPU, so the container must have been given one.
# Without this check the two outcomes are indistinguishable from the outside: a
# GPU trainer and a CPU trainer are both "Up (healthy)", and the difference only
# shows up as a training run that takes ten times longer than it should.
if [ -n "$TRAINER" ] && printf '%s' "$compose_file_value" | grep -q "docker-compose.gpu.yml"; then
  if [ "$(docker inspect "$TRAINER" --format '{{len .HostConfig.DeviceRequests}}' 2>/dev/null)" = "0" ]; then
    echo
    echo "    [WARN] The GPU overlay is in COMPOSE_FILE but this trainer container has" >&2
    echo "           no device reservation — it predates the overlay and was not" >&2
    echo "           recreated. \`restart\` does not re-read compose; force it:" >&2
    echo "               docker compose up -d --force-recreate trainer" >&2
  fi
fi
