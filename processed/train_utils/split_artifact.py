"""Một cửa duy nhất để một lượt chạy biết nó đang tiêu thụ split nào.

Vì sao phải có, và vì sao chỉ được có MỘT:

Trước lượt này, mỗi nơi tự dựng đường dẫn. `train_tcn` có giá trị mặc định trỏ
vào `processed/splits/{train,val,test}.csv`; `training_tasks._build_cmd` chỉ
truyền đường dẫn tường minh ở nhánh nghiên cứu; `_split_csvs_of` đọc lại từ
`cmd` nên trả RỖNG cho nhánh legacy, khiến cổng đồng thuận không soi lượt
huấn luyện legacy nào. Ba cách hiểu khác nhau về cùng một câu hỏi "lượt này
đọc tệp nào", và chúng lệch nhau được mà không ai biết.

Hai không gian tên, KHÔNG trộn
------------------------------
`research`      `processed/splits/{train,val,test}.csv` — ba tệp ĐÓNG BĂNG.
                Không dựng lại. Đối chiếu với `FROZEN_RESEARCH_SPLITS.json`.
`operational`   `processed/splits/operational/<split_id>/` — hiện vật BẤT BIẾN,
                chỉ-tạo-mới. Không có khái niệm "split mới nhất": một lượt
                chạy ghim đúng một `split_id`, và `split_id` đó không bao giờ
                trỏ vào nội dung khác.

FAIL-CLOSED, và đây là bất biến quan trọng nhất của tệp này: một lượt chạy vận
hành KHÔNG có `split_id` thì DỪNG. Không rơi về ba tệp nghiên cứu. Rơi được
nghĩa là một lượt huấn luyện vận hành có thể lặng lẽ học trên mốc nghiên cứu
đóng băng, và checkpoint sẽ khai một nguồn gốc không đúng.

`resolve` không chỉ TÌM ĐƯỢC tệp — nó trả về hiện vật đã XÁC MINH. Chép ba CSV
từ hiện vật Y vào thư mục mang tên X sẽ bị từ chối, vì `split_id` và mã băm
từng tệp đều nằm trong bản khai.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

PURPOSE_RESEARCH = "research"
PURPOSE_OPERATIONAL = "operational"

OPERATIONAL_DIRNAME = "operational"
METADATA_NAME = "split_metadata.json"
FROZEN_REGISTRY_NAME = "FROZEN_RESEARCH_SPLITS.json"
PARTS = ("train", "val", "test")


class SplitArtifactError(Exception):
    """Không xác minh được hiện vật. Luôn là lý do để DỪNG."""


@dataclass(frozen=True)
class SplitArtifact:
    split_id: str
    purpose: str
    train_csv: Path
    val_csv: Path
    test_csv: Path
    metadata: Dict[str, object] = field(default_factory=dict)

    @property
    def csv_paths(self):
        return [self.train_csv, self.val_csv, self.test_csv]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_hashes(directory: Path) -> Dict[str, Dict[str, object]]:
    """`{'train.csv': {'sha256': …, 'bytes': …}}` cho ba tệp trong thư mục."""
    ra = {}
    for ten in PARTS:
        p = Path(directory) / f"{ten}.csv"
        ra[f"{ten}.csv"] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    return ra


def operational_root(splits_root: Path) -> Path:
    return Path(splits_root) / OPERATIONAL_DIRNAME


def _kiem_ba_tep(thu_muc: Path, khai_files, nhan: str) -> None:
    """Đối chiếu mã băm. Đây là chỗ bắt được việc chép tệp từ hiện vật khác."""
    if not isinstance(khai_files, dict) or not khai_files:
        raise SplitArtifactError(
            f"{nhan}: bản khai không có mục `files` — không xác minh được nội "
            f"dung, chỉ biết là tệp có tồn tại. Đó chưa phải xác minh.")
    for ten in PARTS:
        khoa = f"{ten}.csv"
        muc = khai_files.get(khoa)
        if not isinstance(muc, dict) or not str(muc.get("sha256") or "").strip():
            raise SplitArtifactError(f"{nhan}: bản khai thiếu sha256 cho {khoa}")
        p = thu_muc / khoa
        if not p.exists():
            raise SplitArtifactError(f"{nhan}: thiếu tệp {p}")
        that = sha256_file(p)
        if that != muc["sha256"]:
            raise SplitArtifactError(
                f"{nhan}: {khoa} không khớp mã băm đã khai. "
                f"khai={muc['sha256']} thật={that}. Hiện vật đã bị sửa, hoặc "
                f"ba tệp được chép vào đây từ một hiện vật khác.")


def resolve_operational(splits_root: Path, split_id: str) -> SplitArtifact:
    if not str(split_id or "").strip():
        raise SplitArtifactError(
            "lượt chạy vận hành phải ghim một `split_id`. KHÔNG có mặc định và "
            "KHÔNG rơi về processed/splits/*.csv — ba tệp đó là mốc nghiên cứu "
            "đóng băng, học trên chúng rồi khai là lượt vận hành là khai sai "
            "nguồn gốc.")

    thu_muc = operational_root(splits_root) / str(split_id).strip()
    if not thu_muc.is_dir():
        raise SplitArtifactError(
            f"không có hiện vật vận hành `{split_id}` tại {thu_muc}. "
            f"Dựng bằng make_splits.py --operational_split_id={split_id}.")

    p_meta = thu_muc / METADATA_NAME
    if not p_meta.exists():
        raise SplitArtifactError(f"{split_id}: thiếu {METADATA_NAME}")
    try:
        meta = json.loads(p_meta.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SplitArtifactError(f"{split_id}: {METADATA_NAME} không đọc được: {exc}")

    khai_purpose = str(meta.get("purpose") or "").strip()
    if khai_purpose != PURPOSE_OPERATIONAL:
        raise SplitArtifactError(
            f"{split_id}: hiện vật tự khai purpose={khai_purpose!r}, không phải "
            f"{PURPOSE_OPERATIONAL!r}. Không suy purpose từ tên thư mục.")

    khai_id = str(meta.get("split_id") or "").strip()
    if khai_id != str(split_id).strip():
        raise SplitArtifactError(
            f"tên thư mục là {split_id!r} nhưng bản khai bên trong nói "
            f"split_id={khai_id!r}. Hiện vật đã bị đổi tên hoặc chép nhầm chỗ.")

    _kiem_ba_tep(thu_muc, meta.get("files"), split_id)

    return SplitArtifact(
        split_id=str(split_id).strip(), purpose=PURPOSE_OPERATIONAL,
        train_csv=thu_muc / "train.csv", val_csv=thu_muc / "val.csv",
        test_csv=thu_muc / "test.csv", metadata=meta,
    )


def resolve_research(splits_root: Path) -> SplitArtifact:
    """Ba tệp đóng băng, đối chiếu với sổ đăng ký.

    Cố ý KHÔNG đòi `split_metadata.json`: các tệp này có từ trước hợp đồng và
    ép chúng theo lược đồ mới sẽ phá đúng tính lặp lại mà chúng tồn tại để giữ.
    """
    goc = Path(splits_root)
    so = goc / FROZEN_REGISTRY_NAME
    if not so.exists():
        raise SplitArtifactError(
            f"thiếu {FROZEN_REGISTRY_NAME} — không có gì để đối chiếu, nên "
            f"không phát hiện được nếu ba tệp đã bị dựng lại.")
    khai = json.loads(so.read_text(encoding="utf-8"))
    _kiem_ba_tep(goc, khai.get("files"), "frozen research")

    return SplitArtifact(
        split_id="frozen-research-legacy", purpose=PURPOSE_RESEARCH,
        train_csv=goc / "train.csv", val_csv=goc / "val.csv",
        test_csv=goc / "test.csv", metadata=khai,
    )


def resolve_split_artifact(
    *, purpose: str, splits_root: Path, split_id: Optional[str] = None,
) -> SplitArtifact:
    """Cửa duy nhất. Mọi nơi hỏi "lượt này đọc tệp nào" đều phải đi qua đây.

    Trả về cùng một object cho preflight, dựng lệnh, cổng đồng thuận và ghi
    nguồn gốc — nên không còn cảnh preflight soi tệp X trong khi trainer đọc
    tệp Y.
    """
    p = str(purpose or "").strip().lower()
    if p == PURPOSE_OPERATIONAL:
        return resolve_operational(splits_root, split_id or "")
    if p == PURPOSE_RESEARCH:
        return resolve_research(splits_root)
    raise SplitArtifactError(
        f"purpose không rõ: {purpose!r}. Chỉ có {PURPOSE_OPERATIONAL!r} và "
        f"{PURPOSE_RESEARCH!r}; đoán thêm là mở lại đúng chỗ mơ hồ vừa đóng.")
