#!/bin/sh
# Chạy ma trận giả mạo SOT và ghi artifact, KÈM vân tay nguồn đầy đủ.
#
# Vì sao cần wrapper thay vì gọi thẳng run_tests.sh
# =================================================
# Container test KHÔNG cài `git`. Bản thân phép đo tự băm được nội dung cây mã
# (`source_tree_sha256` — thứ định danh implementation thực sự bị đo), nhưng nó
# không tự biết cây có SẠCH so với HEAD hay không.
#
# `HEAD = f882414` chỉ chứng minh commit NỀN. Với một cây làm việc còn thay đổi
# chưa commit — đúng trạng thái kho này hôm nay — hai lượt đo cùng HEAD có thể
# chạy trên hai implementation khác nhau. Host có `git`, nên trạng thái đó lấy ở
# đây rồi truyền vào bằng biến môi trường.
#
# Cây bẩn mà báo sạch còn tệ hơn không báo: phép đo tự bịa ra một mức xác thực
# mà nó không có. Nên khi thiếu biến, phép đo ghi "unknown".
set -eu
export MSYS_NO_PATHCONV=1

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

if git diff --quiet HEAD 2>/dev/null; then
  DIRTY=0
else
  DIRTY=1
fi
# Băm một biểu diễn TẤT ĐỊNH của diff so với HEAD. Cùng HEAD + cùng diff hash
# => cùng implementation, kể cả khi chưa commit.
DIFF_SHA=$(git diff HEAD 2>/dev/null | sha256sum | cut -d' ' -f1)

echo "==> commit nen : $(git rev-parse HEAD 2>/dev/null || echo '?')"
echo "==> worktree   : $([ "$DIRTY" = 1 ] && echo 'BAN (co thay doi chua commit)' || echo 'sach')"
echo "==> diff sha256: ${DIFF_SHA%% *}"

# Truyền qua TỆP, không qua biến môi trường: `run_tests.sh` dựng lệnh `docker
# run` với danh sách `-e` cố định và không chuyển tiếp biến lạ. Sửa nó là chạm
# vào bộ chạy test dùng chung; cây làm việc thì đã được mount sẵn ở /src.
mkdir -p .measurement
cat > .measurement/source_fingerprint.json <<EOF
{
  "source_commit_base": "$(git rev-parse HEAD 2>/dev/null || echo null)",
  "worktree_dirty": $([ "$DIRTY" = 1 ] && echo true || echo false),
  "worktree_diff_sha256": "$DIFF_SHA"
}
EOF

sh scripts/run_tests.sh backend/tests/test_sot_tamper_matrix.py "$@"
