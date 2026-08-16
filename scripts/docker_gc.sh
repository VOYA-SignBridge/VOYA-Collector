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
    # `--compact` KHÔNG còn kéo theo `--deep`, và đây là bản sửa cho một vòng
    # lặp tự nuôi mình, đo được ngày 15/08/2026:
    #
    #     đĩa đầy → gc --compact → dọn sâu XOÁ build cache → nén, lấy lại chỗ
    #     → lượt deploy kế dựng LẠI TỪ ĐẦU (cache rỗng) → vhdx +65 GB
    #     → đĩa đầy
    #
    # Phép đổi chác sai rõ ràng. Giữ build cache thì vhdx to thêm 6.6 GB; xoá
    # nó thì lượt dựng nguội sau đó tốn 43 GB. Gấp bảy lần, và phải trả ngay ở
    # lượt triển khai kế tiếp.
    #
    # Nén KHÔNG cần dọn sâu: nó thu hồi vùng chết trong tệp, mà vùng chết thì
    # đã có sẵn hàng chục GB. Sáng 15/08 nén được 65.7 GB trong khi phần dọn
    # sâu chỉ đóng góp 6.6 GB — và chính 6.6 GB ấy là thứ đắt nhất để dựng lại.
    #
    # Muốn cả hai thì nói cả hai:  bash scripts/docker_gc.sh --deep --compact
    --compact) COMPACT=1 ;;
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
  # het tep moi biet no lanh — xem docs/06-operations/BACKUP_RESTORE.md.
  # `MSYS_NO_PATHCONV` đặt cho ĐÚNG lời gọi này, không export toàn tệp.
  #
  # Git Bash dịch mọi tham số trông giống đường dẫn POSIX sang đường dẫn
  # Windows trước khi trao cho `docker.exe`, nên `/b/…dump` thành `B:/…dump` và
  # `pg_restore` luôn báo không mở được tệp. Hậu quả đúng kiểu tệ nhất: bản sao
  # lưu HOÀN TOÀN LÀNH mà phép kiểm báo "không đọc hết được", rồi script dừng
  # ngay trước bước nén. Đo 15/08/2026: cùng một tệp, thêm biến này thì
  # `pg_restore` đọc trọn không một lỗi.
  #
  # Và vì sao KHÔNG export toàn tệp — đã thử, đã hỏng: giai đoạn 2 truyền
  # `-File '$log'` với `$log` là đường dẫn MSYS (`/tmp/…/compact.ps1`), và nó
  # DỰA VÀO phép dịch đó để PowerShell mở được tệp. Tắt dịch toàn cục là script
  # nâng quyền không tìm thấy tệp, UAC coi như chạy rồi thoát ngay, không để
  # lại nhật ký nào — và bước nén im lặng không làm gì.
  if MSYS_NO_PATHCONV=1 docker run --rm -v "E:/CTU_ProjectOutside/voya_backups:/b" \
       postgres:17-alpine pg_restore -f /dev/null "/b/$(basename "$bk")" 2>/dev/null; then
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

# ---------------------------------------------------------------------------
# Hợp đồng của bước nâng quyền: KHÔNG bước nào được coi là bằng chứng, trừ một
# tệp kết quả mang đúng dấu của LƯỢT CHẠY NÀY.
#
# Ba thứ trước đây bị nhầm là bằng chứng, và cả ba đều không phải:
#
#   * "hộp thoại UAC đã hiện"   — hiện cả khi tiến trình nâng quyền không có
#                                 tệp nào để chạy.
#   * "Start-Process đã trả về" — nó trả về ngay cả khi tiến trình con chết
#                                 tức thì; `-Wait` chỉ đợi, không kiểm gì.
#   * "tệp nhật ký có nội dung" — nội dung có thể là của LƯỢT TRƯỚC.
#
# Cái thứ ba là bẫy tinh nhất và là lý do có `$run_id`. Không có dấu lượt chạy,
# một lượt nén thất bại đọc lại tệp "XONG" của hôm qua và báo đạt — cùng đúng
# hình dạng lỗi mà cả tệp này đang sửa, chỉ khác cửa vào.
#
# Nên: xoá tệp kết quả TRƯỚC, sinh một dấu lượt chạy, và chỉ chấp nhận tệp kết
# quả nào mang đúng dấu ấy. Thiếu tệp = HỎNG, không phải đạt.
# ---------------------------------------------------------------------------
run_id="$(date +%Y%m%d_%H%M%S)_$$"

# `C:\Users\Public`, KHÔNG phải `C:\Windows\Temp`.
#
# Kịch bản nâng quyền chạy dưới quyền Administrator nên ghi vào đâu cũng được.
# Nhưng script CHA chạy quyền thường, và `C:\Windows\Temp` từ chối cả việc đọc
# lẫn việc liệt kê:
#
#     Test-Path 'C:\Windows\Temp\voya_compact_result.txt'
#     -> False, kèm  PermissionDenied: Access is denied
#
# `Test-Path` trả về **False** chứ không ném lỗi ra ngoài, nên phép kiểm đọc ra
# "không có tệp kết quả" và kết luận bước nén thất bại — trong khi nó vừa chạy
# xong và thu hồi 65.7 GB. Đo 15/08/2026: vhdx 90.3 -> 24.6 GB, D: 35.6 ->
# 101.3 GB, mà script trả mã 7.
#
# Đây là cùng một họ lỗi với ba lần trước trong ngày, chỉ đổi chiều: phép KIỂM
# CHỨNG hỏng vì đường dẫn, chứ việc cần kiểm thì không sao. Lần này nó cho ra
# âm tính giả — an toàn hơn dương tính giả, nhưng vẫn là một công cụ nói dối.
#
# `C:\Users\Public` ghi được bởi admin và đọc được bởi mọi người, nên hai đầu
# của phép kiểm nhìn thấy cùng một tệp.
res_win='C:\Users\Public\voya_compact_result.txt'

# Kích thước TRƯỚC, đo từ chính script cha.
#
# Bản trước chỉ có con số `before_bytes` do kịch bản nâng quyền tự khai. Khi
# tệp kết quả không đọc được thì mất luôn cả mốc so sánh, và script không còn
# cách nào tự biết chuyện gì đã xảy ra. Một phép đo của riêng mình thì không
# phụ thuộc vào việc bên kia có nói được hay không.
before_host=$(powershell -NoProfile -Command "(Get-Item -LiteralPath '$vhd').Length" 2>/dev/null | tr -d '\r')

powershell -NoProfile -Command "Remove-Item -LiteralPath '$res_win' -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1
if powershell -NoProfile -Command "if (Test-Path '$res_win') { exit 1 } else { exit 0 }" >/dev/null 2>&1; then
  :
else
  echo "   [FAIL] khong xoa duoc tep ket qua cu ($res_win)." >&2
  echo "          Khong chay tiep: mot tep con sot se lam luot nay trong nhu dat." >&2
  powershell -NoProfile -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1
  exit 6
fi

ps1="$(mktemp -d)/compact.ps1"
cat > "$ps1" <<PS1
\$ErrorActionPreference = 'Stop'
\$vhd = '$vhd'
\$res = '$res_win'
\$runId = '$run_id'
\$before = (Get-Item \$vhd).Length
try {
    Optimize-VHD -Path \$vhd -Mode Full
    \$after = (Get-Item \$vhd).Length
    @("COMPACT_SUCCESS", "run_id=\$runId", "exit_code=0",
      "before_bytes=\$before", "after_bytes=\$after",
      "timestamp=\$((Get-Date).ToString('s'))") |
        Out-File -LiteralPath \$res -Encoding utf8
} catch {
    \$after = (Get-Item \$vhd).Length
    @("COMPACT_FAIL", "run_id=\$runId", "exit_code=1",
      "before_bytes=\$before", "after_bytes=\$after",
      "error=\$(\$_.Exception.Message -replace '\r?\n',' ')",
      "timestamp=\$((Get-Date).ToString('s'))") |
        Out-File -LiteralPath \$res -Encoding utf8
    exit 1
}
PS1

# Bước 2 của hợp đồng: tệp phải TỒN TẠI và không rỗng trước khi nâng quyền.
# Lượt 15/08 thất bại đúng ở đây — tiến trình nâng quyền khởi động với một
# đường dẫn không tồn tại và thoát ngay, không để lại gì.
if [ ! -s "$ps1" ]; then
  echo "   [FAIL] khong viet duoc kich ban nang quyen ($ps1)." >&2
  powershell -NoProfile -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1
  exit 6
fi
# Đường dẫn phải đổi sang dạng Windows TƯỜNG MINH.
#
# `$log` là đường dẫn MSYS (`/tmp/…/compact.ps1`). Nó nằm trong `-ArgumentList
# '…'` của một chuỗi `-Command`, nên Git Bash KHÔNG dịch nó — khác với tham số
# trần, chỗ đó có dịch. PowerShell nhận nguyên văn `/tmp/…` và trả:
#
#     The argument '/tmp/tmp.XXXX/compact.ps1' to the -File parameter does not exist.
#
# Hộp thoại UAC vẫn hiện, người dùng vẫn bấm Yes, tiến trình nâng quyền vẫn
# khởi động — rồi thoát ngay vì không có tệp để chạy. Không nhật ký, không lỗi
# nổi lên, và `-- ket qua nen` in ra rỗng. Đo 15/08/2026: đây là lý do bước nén
# CHƯA TỪNG chạy được từ Git Bash, và vì sao vhdx vẫn 98.9 GB sau một lượt
# `--compact` báo thành công.
ps1_win="$(cygpath -w "$ps1" 2>/dev/null || printf '%s' "$ps1")"

# Và kiểm rằng PowerShell THẬT SỰ thấy đường dẫn đó, chứ không chỉ tin phép
# đổi. `cygpath` có thể thành công mà vẫn cho ra đường dẫn PowerShell không mở
# được; hỏi chính PowerShell thì hết chỗ đoán.
if ! powershell -NoProfile -Command "if (Test-Path -LiteralPath '$ps1_win') { exit 0 } else { exit 1 }" >/dev/null 2>&1; then
  echo "   [FAIL] PowerShell khong thay '$ps1_win'." >&2
  echo "          Day dung la loi da lam buoc nen im lang khong chay 15/08." >&2
  powershell -NoProfile -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1
  exit 6
fi

powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$ps1_win'" 2>&1

echo "-- ket qua nen"
COMPACT_FAILED=0

# Đo NGAY, trước mọi phép kiểm, và IN RA dù kết luận là gì.
#
# Lượt 15/08 kết luận "hỏng" trong khi vhdx vừa từ 90.3 xuống 24.6 GB, và
# không có dòng nào trong phần kết quả cho thấy điều đó — con số duy nhất nói
# ra sự thật nằm mãi ở bảng tổng kết cuối tệp. Hai phép đo độc lập luôn được
# in ra thì một kết luận sai cũng tự phơi ra ngay tại chỗ.
after_host=$(powershell -NoProfile -Command "(Get-Item -LiteralPath '$vhd').Length" 2>/dev/null | tr -d '\r')
echo "   host do: truoc=${before_host:-?} sau=${after_host:-?} bytes"

res="$(powershell -NoProfile -Command "if (Test-Path -LiteralPath '$res_win') { Get-Content -LiteralPath '$res_win' -Raw }" 2>/dev/null | tr -d '\r\0')"

if [ -z "$res" ]; then
  # THIẾU tệp kết quả = HỎNG. Đây là chỗ hợp đồng cũ nói dối: không có tệp thì
  # nó in ra một khoảng trắng rồi đi tiếp như không có chuyện gì.
  echo "   [FAIL] khong co tep ket qua. Buoc nang quyen CHUA CHAY XONG." >&2
  echo "          Co the ban da bam No o UAC, hoac tien trinh chet truoc khi ghi." >&2
  COMPACT_FAILED=1
elif ! printf '%s' "$res" | grep -q "run_id=$run_id"; then
  echo "   [FAIL] tep ket qua KHONG mang dau cua luot nay (run_id=$run_id)." >&2
  echo "          Day la ket qua con sot cua mot luot truoc — khong tinh." >&2
  printf '%s\n' "$res" | sed 's/^/          /' >&2
  COMPACT_FAILED=1
elif ! printf '%s' "$res" | grep -q '^COMPACT_SUCCESS'; then
  echo "   [FAIL] buoc nen bao that bai:" >&2
  printf '%s\n' "$res" | sed 's/^/          /' >&2
  COMPACT_FAILED=1
else
  printf '%s\n' "$res" | sed 's/^/   /'
  # Đo LẠI từ phía host, độc lập với lời khai của chính kịch bản nâng quyền.
  # Kịch bản báo thành công là một nguồn; kích thước tệp thật là nguồn khác, và
  # chỉ khi hai nguồn khớp nhau mới in ra chữ "đạt".
  claimed=$(printf '%s' "$res" | sed -n 's/^after_bytes=//p' | tr -d '\r')
  if [ -z "$after_host" ] || [ -z "$before_host" ]; then
    echo "   [FAIL] khong tu do duoc kich thuoc vhdx — khong xac nhan duoc gi." >&2
    COMPACT_FAILED=1
  elif [ "$after_host" -gt "$before_host" ]; then
    echo "   [FAIL] kich ban bao XONG nhung vhdx TO RA (khai bao: ${claimed:-?})." >&2
    COMPACT_FAILED=1
  elif [ "$after_host" -eq "$before_host" ]; then
    # KHÔNG phải lỗi. `Optimize-VHD` trên một tệp vốn đã gọn thì không thu hồi
    # được gì, và đó là kết quả đúng. Đòi "phải nhỏ đi" sẽ biến một lượt chạy
    # thành công thành báo động giả mỗi khi nén hai lần liên tiếp.
    echo "   DAT — vhdx da o trang thai gon, khong con gi de thu hoi ($((after_host / 1024 / 1024 / 1024)) GB)"
  else
    echo "   DAT — vhdx nho di: $((before_host / 1024 / 1024 / 1024)) GB -> $((after_host / 1024 / 1024 / 1024)) GB"
  fi
fi

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

# Mã thoát phải nói ra bước nén đã hỏng, và nó nằm SAU khi Docker đã lên lại —
# thoát sớm để lại một máy không có Docker thì tệ hơn hẳn một mã thoát.
#
# Ngày 15/08 lượt `--compact` thoát 0 trong khi vhdx không hề nhỏ đi, nên bất
# kỳ thứ gì đọc mã thoát này đều bị lừa. Đó là lý do dòng dưới tồn tại.
if [ "${COMPACT_FAILED:-0}" -ne 0 ]; then
  echo >&2
  echo "KET LUAN: buoc NEN KHONG thanh cong (stack da duoc bat lai)." >&2
  echo "          Dia CHUA duoc thu hoi — dung coi lenh nay la da xong." >&2
  exit 7
fi
