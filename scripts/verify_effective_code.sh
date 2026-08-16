#!/usr/bin/env sh
# Chứng minh mã ĐANG ĐƯỢC IMPORT trong container đúng là snapshot đã đóng băng.
#
#   sh scripts/verify_effective_code.sh voya_backend_iso .measurement/code-snapshots/C-...
#   sh scripts/verify_effective_code.sh voya_worker      .measurement/code-snapshots/C-...
#
# Vì sao "tệp có mặt trong container" là CHƯA ĐỦ
# ==============================================
# Bind-mount đặt tệp vào `/app/app/`. Nhưng Python import theo `sys.path`, và
# `sys.path` có thể trỏ tới một bản khác — một bản đã cài trong `site-packages`,
# một `.egg-link`, hay một thư mục đứng trước trong đường tìm kiếm. Khi đó:
#
#     sha256 /app/app/catalog_sync.py   khớp snapshot     <- kiểm "tệp có mặt"
#     app.catalog_sync.__file__         trỏ chỗ KHÁC      <- mã thật sự chạy
#
# Phép kiểm duy nhất có nghĩa là hỏi CHÍNH MODULE ĐÃ IMPORT nó đến từ đâu, rồi
# băm đúng tệp ở `module.__file__`.
#
# Với Celery còn nghiêm hơn
# =========================
# Nếu backend chạy snapshot mới còn worker chạy ảnh cũ thì một lượt đo có HAI
# phiên bản mã, và kết quả không diễn giải được:
#
#     HTTP producer  = mã mới
#     Celery worker  = mã cũ
#
# Nên bất biến của một lượt đo là:
#
#     CodeSnapshot(backend) = CodeSnapshot(worker) = CodeSnapshot(beat)
#
# Chạy kịch bản này cho TỪNG process tham gia, và chỉ đo khi tất cả trả về cùng
# một `tree_sha256`.
set -eu

export MSYS_NO_PATHCONV=1

CONTAINER="${1:?can ten container}"
SNAPSHOT="${2:?can duong dan snapshot}"

MONG="$(python -c "import json,sys; print(json.load(open(sys.argv[1]+'/SNAPSHOT.json'))['tree_sha256'])" "$SNAPSHOT" 2>/dev/null \
        || grep -o '"tree_sha256": *"[a-f0-9]*"' "$SNAPSHOT/SNAPSHOT.json" | cut -d'"' -f4)"

echo "==> container : $CONTAINER"
echo "==> snapshot  : $SNAPSHOT"
echo "==> mong doi  : $MONG"

docker exec -i "$CONTAINER" python - <<'PY'
import hashlib, importlib, json, os, sys

# Các module QUYẾT ĐỊNH hành vi đang đo. Thêm vào đây khi phạm vi mở rộng —
# một module thiếu ở đây là một biến không kiểm soát.
MODULES = [
    "app.catalog_sync", "app.dataset_samples", "app.dataset_manager",
    "app.preview_render", "app.preview_tasks", "app.tenant_context",
    "app.tenant_middleware", "app.auth", "app.quota_deps",
    "app.training_tasks", "app.export_tasks", "app.storage.metadata_db",
]

ra = {}
loi = []
for ten in MODULES:
    try:
        m = importlib.import_module(ten)
    except Exception as e:                                   # noqa: BLE001
        loi.append(f"{ten}: khong import duoc ({type(e).__name__})")
        continue
    # `__file__` của module ĐÃ IMPORT — đây mới là mã thật sự chạy.
    duong = getattr(m, "__file__", None)
    if not duong or not os.path.exists(duong):
        loi.append(f"{ten}: khong co __file__")
        continue
    with open(duong, "rb") as fh:
        bam = hashlib.sha256(fh.read()).hexdigest()
    ra[ten] = {"file": duong, "sha256": bam[:16]}

import app
print(json.dumps({"app_package": app.__file__,
                  "sys_path_dau": sys.path[:4],
                  "modules": ra, "loi": loi},
                 ensure_ascii=False, indent=2))
PY

echo
echo "==> bam CAY ma trong container (so voi tree_sha256 cua snapshot)"
docker exec "$CONTAINER" sh -c '
cd /app 2>/dev/null || exit 1
find ./app -type f ! -name "*.pyc" ! -path "*__pycache__*" -print0 \
  | sort -z | xargs -0 sha256sum | sha256sum | cut -d" " -f1'
echo
echo "LUU Y: bam cay tren chi phu ./app trong container; tree_sha256 cua snapshot"
echo "phu backend/app + backend/tests + scripts. So sanh TUNG MODULE o tren moi la"
echo "phep kiem chinh — no bat duoc ca truong hop sys.path tro cho khac."
