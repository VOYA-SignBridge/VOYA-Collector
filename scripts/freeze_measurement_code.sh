#!/usr/bin/env sh
# Đóng băng mã ứng dụng thành một SNAPSHOT BẤT BIẾN để đo.
#
#   sh scripts/freeze_measurement_code.sh C
#   -> .measurement/code-snapshots/C-20260816T093000-a1b2c3/
#
# Vì sao KHÔNG gắn thẳng cây làm việc
# ===================================
# Gắn cây đang sống vào container đo tạo ra một lỗ không sửa được bằng cách kiểm
# kỹ hơn ở đầu lượt:
#
#     fingerprint_truoc = X
#     request 1         = X
#     (sửa một tệp cho nhóm sau)
#     request 2         = X+1
#
# Cả hai request nằm trong CÙNG một run ID, và báo cáo không thể phân biệt.
# Snapshot cắt đứt điều đó: từ thời điểm chụp, mã của lượt đo không đổi được nữa.
#
# Hai danh tính ĐỘC LẬP cho một lượt đo
# =====================================
#     phụ thuộc runtime  ->  digest của ảnh nền
#     mã ứng dụng        ->  digest của snapshot
#
# Tách hai thứ này ra còn TRUY NGUYÊN TỐT HƠN một tag ảnh: tag bị dùng lại, và
# một lượt dựng bị đẩy cache có thể cho ra nội dung khác dưới cùng một cái tên.
# Đã gặp đúng chuyện đó ngày 16/08/2026 — container báo `Up`, tag đúng, mã cũ.
#
# Snapshot là READ-ONLY khi mount. Ứng dụng không được sửa chính thứ đang dùng
# làm bằng chứng; `PYTHONDONTWRITEBYTECODE=1` để nó khỏi cần ghi `__pycache__`.
set -eu

export MSYS_NO_PATHCONV=1

NHOM="${1:-run}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GOC="$REPO/.measurement/code-snapshots"

case "$NHOM" in
  [A-Za-z0-9_-]*) ;;
  *) echo "ten nhom khong hop le: $NHOM"; exit 2;;
esac

mkdir -p "$GOC"
STAMP="$(date -u +%Y%m%dT%H%M%S)"
TMP="$GOC/.dang-tao-$STAMP"
rm -rf "$TMP"; mkdir -p "$TMP"

# Chỉ chép thứ THAM GIA hành vi. Không chép `.git`, `.measurement`, dataset,
# hay `node_modules`: chúng làm băm đổi vì lý do không liên quan tới mã, và một
# băm đổi vô cớ thì không ai còn đọc nó nữa.
echo "==> chup ma tu cay lam viec"
tar -C "$REPO" -cf - \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
    backend/app backend/tests scripts \
  | tar -C "$TMP" -xf -

# Băm CÂY, không băm từng tệp rời: thứ tự ổn định, nội dung ổn định, nên cùng
# một cây logic luôn cho cùng một băm dù chụp lại bao nhiêu lần.
BAM_CAY="$(cd "$TMP" && find . -type f -print0 | sort -z \
           | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"

DICH="$GOC/$NHOM-$STAMP-$(printf '%s' "$BAM_CAY" | cut -c1-6)"
mv "$TMP" "$DICH"

# Trạng thái git ghi lại CẢ phần chưa commit. `HEAD` một mình nói dối khi cây
# bẩn — và cây ở đây gần như luôn bẩn giữa một đợt vá.
HEAD_SHA="$(cd "$REPO" && git rev-parse HEAD)"
DIFF_SHA="$(cd "$REPO" && git diff HEAD | sha256sum | cut -d' ' -f1)"
BAN="$(cd "$REPO" && git status --porcelain | wc -l | tr -d ' ')"

cat > "$DICH/SNAPSHOT.json" <<EOF
{
  "nhom": "$NHOM",
  "thoi_diem": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tree_sha256": "$BAM_CAY",
  "git": {
    "head": "$HEAD_SHA",
    "dirty": $([ "$BAN" -gt 0 ] && echo true || echo false),
    "dirty_files": $BAN,
    "diff_sha256": "$DIFF_SHA"
  }
}
EOF

# `.retain` để không lệnh dọn nào xoá một snapshot đang là bằng chứng.
printf 'Snapshot ma BAT BIEN cho phep do nhom %s.\nKHONG sua truc tiep. Sua ma thi chup snapshot MOI.\n' \
    "$NHOM" > "$DICH/.retain"
chmod -R a-w "$DICH" 2>/dev/null || true

echo "==> snapshot: $DICH"
echo "    tree_sha256 = $BAM_CAY"
echo "    git HEAD    = $HEAD_SHA  (dirty=$BAN tep)"
echo
echo "Mount READ-ONLY vao MOI process tham gia phep do:"
echo "  -v \"$(cd "$DICH" && { pwd -W 2>/dev/null || pwd; })/backend/app:/app/app:ro\""
echo "  -e PYTHONDONTWRITEBYTECODE=1"
echo
echo "Roi xac minh bang:  sh scripts/verify_effective_code.sh <container> $DICH"
printf '%s\n' "$DICH"
