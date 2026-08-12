#!/usr/bin/env bash
# Thu hồi dung lượng Docker — và nói rõ chỗ nào thật sự trả tiền về ổ đĩa.
#
# Vì sao có tệp này
# =================
# Ngày 13/08/2026, ổ D còn 2.6 GB / 159 GB. Dọn bên trong Docker được 45.87 GB
# và ổ đĩa nhận về **đúng 0 byte**. Nén vhdx xong thì 123.3 GB → 24.2 GB, ổ D
# lên 102 GB trống — trong 73 giây.
#
# Bài học nằm ở khoảng cách giữa hai con số đó: `docker system prune` KHÔNG giải
# quyết vấn đề "hết ổ đĩa" trên WSL2. Nó chỉ tạo chỗ trống bên trong một tệp mà
# bản thân tệp đó không bao giờ co lại. Ai chỉ chạy prune rồi thấy Docker báo
# "reclaimed 45 GB" sẽ tưởng đã xong, trong khi ổ đĩa vẫn nguyên 99%.
#
# Nên script này chia làm hai giai đoạn rõ ràng, và giai đoạn 2 mới là giai đoạn
# thật:
#
#     giai đoạn 1  prune          — không cần dừng gì, trả 0 byte cho ổ đĩa
#     giai đoạn 2  nén vhdx       — phải dừng Docker, trả TOÀN BỘ về ổ đĩa
#
# Cách dùng
# =========
#     bash scripts/docker_gc.sh            # giai đoạn 1, và in ra cần nén không
#     bash scripts/docker_gc.sh --deep     # giai đoạn 1 mức sâu (bỏ cả ảnh không dùng)
#     bash scripts/docker_gc.sh --compact  # cả hai giai đoạn (DỪNG STACK, cần UAC)
#
# KHÔNG BAO GIỜ dùng `--volumes`
# ==============================
# Đo 13/08/2026 trên chính máy này: ba volume mồ côi đều **0 B**, toàn bộ volume
# cộng lại 403 MB, `postgres_data` chỉ 178 MB. Tức `--volumes` lãi 0 byte trong
# khi vấn đề là 123 GB.
#
# Và nó gài bẫy: nó xoá volume "không container nào tham chiếu". Bình thường
# container còn tồn tại nên dữ liệu được che — nhưng giai đoạn 2 bắt buộc dừng
# Docker, và nếu ở đó ai dùng `docker compose down` (xoá container) thay vì
# `stop`, thì mọi volume thành mồ côi và cùng lệnh ấy giết cơ sở dữ liệu sản
# xuất. Muốn dọn volume mồ côi thì xoá THEO TÊN, và script này in ra danh sách
# kèm dung lượng để nhìn trước khi quyết.

set -u

cd "$(dirname "$0")/.."

DEEP=0
COMPACT=0
for arg in "$@"; do
  case "$arg" in
    --deep)    DEEP=1 ;;
    --compact) COMPACT=1; DEEP=1 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "tham so la: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }

host_disk() {
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

before=$(host_disk || true)
say "TRUOC"
docker system df
[ -n "$before" ] && { set -- $before; echo "   o $3: con $1 GB trong · vhdx $2 GB"; }

# ---------------------------------------------------------------------------
# Giai đoạn 1 — prune. An toàn, không dừng gì.
# ---------------------------------------------------------------------------
say "GIAI DOAN 1 — don ben trong Docker"

echo "-- build cache khong con dung"
docker builder prune -f 2>&1 | tail -1

if [ "$DEEP" -eq 1 ]; then
  echo "-- build cache CON LAI (lan build sau se lau hon mot lan)"
  docker builder prune -a -f 2>&1 | tail -1
  echo "-- anh khong container nao tham chieu"
  # `-a` bo moi anh khong duoc container nao (ke ca da Exited) tham chieu. Anh
  # test `voya_backend_test` nam trong so do — no chi duoc chay ad-hoc — nen dung
  # `--deep` co nghia la phai dung lai anh test truoc lan chay suite ke tiep:
  #     docker build -f backend/Dockerfile.test -t voya_backend_test:latest backend
  docker image prune -a -f 2>&1 | tail -1
fi

# Volume mồ côi: CHỈ liệt kê, không xoá. Xem phần đầu tệp về vì sao.
say "VOLUME MO COI (chi liet ke — xoa theo TEN neu chac chan)"
found=0
for v in $(docker volume ls -q); do
  if [ "$(docker ps -a --filter volume="$v" -q | wc -l)" -eq 0 ]; then
    size=$(docker system df -v 2>/dev/null | awk -v n="$v" '$1==n {print $NF}')
    echo "   $v   ${size:-?}"
    found=1
  fi
done
[ "$found" -eq 0 ] && echo "   (khong co)"

after=$(host_disk || true)
say "SAU GIAI DOAN 1"
docker system df
[ -n "$after" ] && { set -- $after; echo "   o $3: con $1 GB trong · vhdx $2 GB"; free_now=$1; vhdx_now=$2; }

# ---------------------------------------------------------------------------
# Giai đoạn 2 — nén vhdx. Đây mới là chỗ ổ đĩa nhận lại dung lượng.
# ---------------------------------------------------------------------------
if [ "$COMPACT" -ne 1 ]; then
  echo
  echo "LUU Y: giai doan 1 KHONG tra byte nao cho o dia — vhdx chi phinh, khong tu co."
  echo "       Muon thu hoi that su:  bash scripts/docker_gc.sh --compact"
  echo "       (dung stack vai phut, va can bam Yes o hop thoai UAC)"
  exit 0
fi

say "GIAI DOAN 2 — nen vhdx (DUNG STACK)"

echo "-- sao luu co so du lieu ra o khac truoc da"
ts=$(date +%Y%m%d_%H%M%S)
bk="/e/CTU_ProjectOutside/voya_backups/signdb_PRE_gc_${ts}.dump"
if docker ps --format '{{.Names}}' | grep -q voya_postgres; then
  docker exec voya_postgres pg_dump -U admin -Fc signdb > "$bk" 2>/dev/null
  # `pg_restore --list` KHONG bat duoc tep cut (muc luc nam o DAU tep). Phai doc
  # het tep moi biet no lanh — xem docs/BACKUP_RESTORE.md.
  if docker run --rm -v "E:/CTU_ProjectOutside/voya_backups:/b" postgres:17-alpine \
       pg_restore -f /dev/null "/b/$(basename "$bk")" 2>/dev/null; then
    echo "   $bk — tu kiem DAT"
  else
    echo "   [FAIL] ban sao luu khong doc het duoc. DUNG LAI." >&2
    exit 4
  fi
else
  echo "   [warn] voya_postgres khong chay — bo qua sao luu"
fi

# `stop`, KHONG phai `down`: container phai con ton tai de volume con duoc tham
# chieu. Xem phan dau tep.
echo "-- dung stack (stop, khong phai down)"
docker compose stop >/dev/null 2>&1
echo "   container con lai: $(docker ps -a -q | wc -l)"

echo "-- tat Docker Desktop va WSL"
powershell -NoProfile -Command "
  Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 5; wsl --shutdown; Start-Sleep -Seconds 3" >/dev/null 2>&1

vhd=$(powershell -NoProfile -Command '
  $s = "$env:APPDATA\Docker\settings-store.json"
  $dir = if (Test-Path $s) { (Get-Content $s -Raw | ConvertFrom-Json).CustomWslDistroDir } else { "$env:LOCALAPPDATA\Docker\wsl" }
  (Get-ChildItem $dir -Recurse -Filter docker_data.vhdx | Select-Object -First 1).FullName' 2>/dev/null | tr -d '\r')

if [ -z "$vhd" ]; then
  echo "   [FAIL] khong tim thay docker_data.vhdx" >&2
  powershell -NoProfile -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1
  exit 5
fi

echo "-- nen $vhd  (BAM YES o hop thoai UAC)"
log="$(mktemp -d)/compact.ps1"
cat > "$log" <<PS1
\$ErrorActionPreference = 'Stop'
\$vhd = '$vhd'
"truoc: {0:N1} GB" -f ((Get-Item \$vhd).Length/1GB) | Out-File 'C:\Windows\Temp\voya_compact.log' -Encoding utf8
try {
    Optimize-VHD -Path \$vhd -Mode Full
    "sau  : {0:N1} GB" -f ((Get-Item \$vhd).Length/1GB) | Out-File 'C:\Windows\Temp\voya_compact.log' -Append -Encoding utf8
    "XONG" | Out-File 'C:\Windows\Temp\voya_compact.log' -Append -Encoding utf8
} catch {
    "LOI: \$(\$_.Exception.Message)" | Out-File 'C:\Windows\Temp\voya_compact.log' -Append -Encoding utf8
}
PS1
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$log'" 2>&1

echo "-- ket qua nen"
powershell -NoProfile -Command "Get-Content 'C:\Windows\Temp\voya_compact.log'" 2>/dev/null | tr -d '\r\0'

echo "-- bat lai Docker Desktop"
powershell -NoProfile -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1
until docker info >/dev/null 2>&1; do sleep 10; done
docker compose start >/dev/null 2>&1
until [ "$(docker ps --filter health=starting -q | wc -l)" -eq 0 ]; do sleep 10; done

say "SAU CUNG"
docker ps -a --format '{{.Names}}\t{{.Status}}' | sort
docker system df
final=$(host_disk || true)
[ -n "$final" ] && { set -- $final; echo "   o $3: con $1 GB trong · vhdx $2 GB"; }
echo
echo "Kiem tra lai stack:  docker exec voya_backend python -m app.cli.verify_deployment"
