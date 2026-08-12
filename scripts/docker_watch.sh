#!/usr/bin/env bash
# Canh chừng dung lượng Docker, chạy không người trực (Task Scheduler, hằng tuần).
#
# Vì sao cần, khi đã có pre-flight của deploy.sh
# ==============================================
# Pre-flight chỉ chạy khi có người triển khai. Nhưng vhdx phình cả khi không ai
# build: Loki, Prometheus và nhật ký container ghi liên tục, và trên WSL2 thì
# **không byte nào tự quay về ổ đĩa** — đã kiểm 13/08/2026, `wsl --manage
# --set-sparse` bị Microsoft tắt vì nguy cơ hỏng dữ liệu, nên cơ chế tự thu hồi
# không dùng được. Tức là không có gì tự sửa; chỉ có người sửa, và người thì cần
# được nhắc.
#
# Tín hiệu: KHOẢNG CÁCH, không phải chỗ trống
# ===========================================
# "Ổ D còn 40 GB" nói lên rất ít. Câu hỏi đúng là **nén sẽ lấy lại được bao
# nhiêu**, và nó bằng:
#
#     vhdx trên đĩa  -  dung lượng Docker thật sự dùng
#
# Ngày 13/08/2026 con số đó là 123.3 - 17 = ~106 GB, và nén lấy về đúng 99.1 GB.
# Khoảng cách nhỏ nghĩa là nén vô ích dù ổ có chật; khoảng cách lớn nghĩa là có
# sẵn hàng chục GB chỉ chờ một lượt nén. Chỗ trống thuần tuý không phân biệt
# được hai tình huống đó.
#
# Cách dùng
# =========
#     bash scripts/docker_watch.sh              # don an toan + do + canh bao neu can
#     bash scripts/docker_watch.sh --dry-run    # chi do va in, khong don, khong gui thu
#     bash scripts/docker_watch.sh --install    # dang ky Task Scheduler chay hang tuan
#
# Nó KHÔNG bao giờ tự nén: nén phải dừng cả stack và cần bấm UAC, nên nó là việc
# của người, vào lúc người chọn. Script này chỉ nói "đã đến lúc".

set -u
cd "$(dirname "$0")/.."

DRY=0; INSTALL=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --install) INSTALL=1 ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "tham so la: $a" >&2; exit 2 ;;
  esac
done

FREE_WARN_GB=40      # duoi muc nay: nhac truoc, con nhieu thoi gian
FREE_CRIT_GB=20      # duoi muc nay: deploy.sh se CHAN, khong build duoc nua
GAP_GB=30            # nen se lay lai duoc chung nay tro len -> dang cong suc

LOG="${VOYA_WATCH_LOG:-/e/CTU_ProjectOutside/voya_backups/docker_watch.log}"

# ---------------------------------------------------------------------------
# Đăng ký Task Scheduler. Chạy dưới tài khoản hiện tại, KHÔNG cần quyền admin —
# nó chỉ dọn cache và gửi thư, không đụng gì cần elevation.
# ---------------------------------------------------------------------------
if [ "$INSTALL" -eq 1 ]; then
  # Trỏ vào `docker_watch.cmd`, KHÔNG trỏ thẳng vào `bash <duong dan>`.
  #
  # Task Scheduler chèn thêm một dấu backslash vào đầu tham số, nên đăng ký
  # trực tiếp cho ra `bash: \E:/.../docker_watch.sh": No such file or directory`.
  # Kiểu hỏng này im lặng đúng cách tệ nhất: `schtasks /Create` báo SUCCESS,
  # `/Query` báo Ready, và chỉ có `Last Result: 1` cùng một tệp log không bao
  # giờ dài thêm mới tố cáo. Đã mắc 13/08/2026.
  here=$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)
  wrapper=$(printf '%s\\scripts\\docker_watch.cmd' "${here//\//\\}")
  schtasks //Create //TN "VOYA Docker disk watch" //TR "$wrapper" \
           //SC WEEKLY //D SUN //ST 09:00 //F 2>&1 | tail -2
  echo
  echo "Kiem lai:  schtasks //Query //TN \"VOYA Docker disk watch\""
  echo "Chay thu:  schtasks //Run   //TN \"VOYA Docker disk watch\""
  echo "Go bo:     schtasks //Delete //TN \"VOYA Docker disk watch\" //F"
  exit 0
fi

# ---------------------------------------------------------------------------
# Đo
# ---------------------------------------------------------------------------
host_disk() {
  command -v powershell >/dev/null 2>&1 || return 1
  powershell -NoProfile -Command '
    $s = "$env:APPDATA\Docker\settings-store.json"
    $dir = if (Test-Path $s) { (Get-Content $s -Raw | ConvertFrom-Json).CustomWslDistroDir } else { $null }
    if (-not $dir) { $dir = "$env:LOCALAPPDATA\Docker\wsl" }
    if (-not (Test-Path $dir)) { exit 1 }
    $drive = (Get-Item $dir).PSDrive.Name
    $free  = (Get-PSDrive $drive).Free / 1GB
    $vhdx  = (Get-ChildItem $dir -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue |
              Measure-Object -Property Length -Sum).Sum / 1GB
    "{0:N1} {1:N1} {2}" -f $free, $vhdx, $drive
  ' 2>/dev/null | tr -d '\r'
}

docker_used_gb() {
  # Tổng Images + Containers + Volumes + Build Cache, quy về GB.
  #
  # Dùng `--format` chứ KHÔNG parse bảng: bảng có cột RECLAIMABLE kèm hậu tố
  # "(0%)" nên số cột thay đổi theo dòng, và bản đầu của hàm này lấy nhầm cột
  # trên mọi dòng trừ "Build Cache" — cho ra 4.5 GB thay vì 21.7 GB, tức báo
  # khoảng cách lớn hơn thực tế và giục nén sớm hơn cần thiết.
  docker system df --format '{{.Type}}|{{.Size}}' 2>/dev/null | awk -F'|' '
    function g(s) {
      if (s ~ /TB$/) return substr(s,1,length(s)-2) * 1024
      if (s ~ /GB$/) return substr(s,1,length(s)-2)
      if (s ~ /MB$/) return substr(s,1,length(s)-2) / 1024
      if (s ~ /kB$/) return substr(s,1,length(s)-2) / 1048576
      if (s ~ /B$/)  return substr(s,1,length(s)-1) / 1073741824
      return 0
    }
    NF == 2 { t += g($2) }
    END { printf "%.1f", t }'
}

if ! docker info >/dev/null 2>&1; then
  echo "$(date '+%F %T') KHONG NOI DUOC VOI DOCKER — bo qua luot nay" | tee -a "$LOG"
  exit 0
fi

if [ "$DRY" -eq 0 ]; then
  docker builder prune -f >/dev/null 2>&1
fi

line=$(host_disk || true)
if [ -z "$line" ]; then
  echo "$(date '+%F %T') khong do duoc o dia host — bo qua" | tee -a "$LOG"
  exit 0
fi
set -- $line
free_gb="$1"; vhdx_gb="$2"; drive="$3"
used_gb=$(docker_used_gb)
gap=$(awk -v v="$vhdx_gb" -v u="$used_gb" 'BEGIN{printf "%.1f", v-u}')

stamp=$(date '+%F %T')
summary="${drive}: free=${free_gb}GB vhdx=${vhdx_gb}GB docker=${used_gb}GB gap=${gap}GB"
echo "$stamp $summary" >> "$LOG"
echo "$summary"

# ---------------------------------------------------------------------------
# Quyết định
# ---------------------------------------------------------------------------
free_i=${free_gb%%.*}; gap_i=${gap%%.*}
level=""; why=""

if [ "$free_i" -lt "$FREE_CRIT_GB" ]; then
  level="NGUY CAP"
  why="O ${drive}: chi con ${free_gb} GB. deploy.sh se TU CHOI build (nguong ${FREE_CRIT_GB} GB), va mot lan build voi o dia chat da tung giet dockerd."
elif [ "$gap_i" -ge "$GAP_GB" ]; then
  level="NEN NEN VHDX"
  why="vhdx ${vhdx_gb} GB nhung Docker chi dung ${used_gb} GB — nen se lay lai khoang ${gap} GB. Chay: bash scripts/docker_gc.sh --compact"
elif [ "$free_i" -lt "$FREE_WARN_GB" ]; then
  level="CANH BAO"
  why="O ${drive}: con ${free_gb} GB, duoi nguong ${FREE_WARN_GB} GB. Chua gap, nhung nen xu ly truoc lan trien khai toi."
fi

if [ -z "$level" ]; then
  echo "OK — khong can lam gi."
  exit 0
fi

echo "[$level] $why"
echo "$stamp [$level] $why" >> "$LOG"
[ "$DRY" -eq 1 ] && exit 0

# Gửi thư QUA BACKEND, không tự cầm SMTP.
#
# Backend đã có cấu hình SMTP, đã được kiểm, và đã biết cách không ghi mật khẩu
# ra log. Chép cấu hình đó sang một script trên host nghĩa là có thêm một bản
# thông tin bí mật thứ hai để quên đồng bộ — và một đường gửi thư chưa ai kiểm.
to=$(sed -n 's/^ALERT_EMAIL=//p;s/^ADMIN_EMAIL=//p;s/^SMTP_FROM=//p' .env 2>/dev/null | head -1 | tr -d '\r')
if [ -z "$to" ]; then
  echo "(khong tim thay ALERT_EMAIL/ADMIN_EMAIL/SMTP_FROM trong .env — chi ghi log)"
  exit 0
fi

# `-i` la BAT BUOC: khong co no, `docker exec` khong chuyen stdin, `python -`
# doc duoc mot chuoi rong, khong lam gi va thoat 0 — canh bao bien mat khong mot
# tieng dong. Da mac dung mot lan khi viet ham nay.
docker exec -i voya_backend python - "$to" "$level" "$why" "$summary" <<'PY' 2>&1 | tail -2
import sys
to, level, why, summary = sys.argv[1:5]
from app.email_service import _send
_send(
    to,
    f"[VOYA] Dia Docker: {level}",
    f"{why}\n\n{summary}\n\n"
    f"Chi tiet quy trinh: docs/DEPLOY_SECOND_MACHINE.md, muc 'Dung luong Docker'.\n"
    f"Nhat ky: voya_backups/docker_watch.log\n",
    loggable=True,
)
print("da gui thu toi", to)
PY
