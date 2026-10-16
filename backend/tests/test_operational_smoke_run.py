"""Phép thử THẬT đầu tiên của cả chuỗi ngữ nghĩa, trên một hiện vật vứt đi được.

Mọi thứ tới giờ được kiểm ở mức đơn vị và hợp đồng. Tệp này chạy `train_tcn`
thật, một epoch, trên một hiện vật vận hành dựng riêng trong tmp — và mang đúng
hình dạng nguy hiểm mà việc nhập QIPEDC sẽ tạo ra:

    UID_A | an     | smoke | bac
    UID_B | an     | smoke | nam      ← cùng slug, cùng dialect, khác vùng
    UID_C | cam-on | smoke | common

Dưới khoá cũ `vn/<dialect>/<slug>` thì A và B là MỘT lớp. Nếu chuỗi mới có chỗ
nào còn rơi về khoá cũ, `num_classes` sẽ ra 2 thay vì 3 — không ngoại lệ, không
cảnh báo, và độ chính xác vẫn ra một con số trông hợp lý.

Đặc điểm - đây là hiện vật TỔNG HỢP trên đặc trưng THẬT: các hàng trỏ vào npz
có thật trên đĩa, nhưng `class_uid`/`slug`/`region` là bịa. Dữ liệu thật hiện
chưa có slug nào mang nhiều vùng cùng dialect (đo trên `signdb` ngày
14/08/2026), nên không thể lấy hình dạng này từ dữ liệu có sẵn. Vứt đi được sau
khi chạy, và đó là chủ ý: lỗi wiring nên lộ ra trên 3 lớp bỏ đi, không phải sau
khi đã sinh hiện vật chính thức.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SPLITS = REPO / "processed" / "splits"
# Chế độ subset tự dò `features` từ đường dẫn split (`parents[2]`); hiện vật
# của test nằm trong tmp nên phải chỉ tường minh, nếu không trainer dừng với
# "Subset mode requires locating the 'features' folder".
FEATURES = REPO / "dataset" / "features"

try:
    import sklearn  # noqa: F401
    import torch  # noqa: F401
    _DEPS = True
except Exception:
    _DEPS = False

_HAVE = (SPLITS / "train.csv").exists() and FEATURES.is_dir() and _DEPS

pytestmark = pytest.mark.skipif(
    not _HAVE, reason="cần processed/splits/*.csv + dataset/features + torch + scikit-learn")

BA_LOP = [("UID_SMOKE_A", "an", "bac"),
          ("UID_SMOKE_B", "an", "nam"),
          ("UID_SMOKE_C", "cam-on", "common")]
MOI_LOP = 12  # đủ để 70/15/15 cho ra cả ba phần không rỗng

#: Ranh giới của fixture này, và là chỗ hai lượt trước làm sai.
#:
#: `_resolve_feature_path` dựng đường dẫn bằng
#: `root / language / dialect / folder_name / file`. Bịa `dialect` ra là mọi
#: npz biến mất và trainer dừng với "train split became empty after removing
#: missing feature files" — một lỗi FIXTURE trông y hệt lỗi wiring.
#:
#: Nên: giữ nguyên mọi trường định vị VẬT LÝ, chỉ ghi đè phần NGỮ NGHĨA.
DINH_VI_VAT_LY = ("language", "dialect", "folder_name", "file", "file_path",
                  "storage_key")
NGU_NGHIA = ("class_uid", "slug", "label_slug", "region", "target_idx")


def _hang_that():
    """Ba lớp THẬT cùng MỘT dialect, mỗi lớp đủ mẫu. Trả (dialect, lớp, cột).

    Cùng một dialect vì `--dialect` là thứ đưa trainer vào chế độ subset, và
    vì đường dẫn đặc trưng phụ thuộc dialect — ba lớp khác dialect sẽ không
    lọc chung được.
    """
    theo_pn = defaultdict(lambda: defaultdict(list))
    with (SPLITS / "train.csv").open(encoding="utf-8") as f:
        doc = csv.DictReader(f)
        cot = list(doc.fieldnames or [])
        for r in doc:
            k = (r.get("class_uid") or "").strip()
            d = (r.get("dialect") or "").strip()
            if k and d:
                theo_pn[d][k].append(r)
    for pn, lop in sorted(theo_pn.items()):
        du = [v for v in lop.values() if len(v) >= MOI_LOP]
        if len(du) >= len(BA_LOP):
            return pn, du[:len(BA_LOP)], cot
    return "", [], cot


@pytest.fixture(scope="module")
def hien_vat(tmp_path_factory):
    """Dựng hiện vật vận hành trong tmp. KHÔNG đụng processed/splits/."""
    from processed.train_utils.label_mapping import canonical_mapping_hash
    from processed.train_utils.split_artifact import file_hashes

    dialect, nguon, cot = _hang_that()
    if len(nguon) < len(BA_LOP):
        pytest.skip(f"cần {len(BA_LOP)} lớp cùng một dialect có ≥{MOI_LOP} mẫu")

    goc = tmp_path_factory.mktemp("op_splits")
    d = goc / "operational" / "smoke-region"
    d.mkdir(parents=True)

    for c in ("class_uid", "slug", "label_slug", "dialect", "region",
              "target_idx", "label_key"):
        if c not in cot:
            cot.append(c)

    anh_xa = {uid: i for i, (uid, _s, _v) in enumerate(BA_LOP)}
    phan = {"train": [], "val": [], "test": []}
    for (uid, slug, vung), hang_lop in zip(BA_LOP, nguon):
        h = [dict(r) for r in hang_lop[:MOI_LOP]]
        for r in h:
            r.update({"class_uid": uid, "slug": slug, "label_slug": slug,
                      # CHỈ ngữ nghĩa: language/dialect/folder_name/file/
                      # file_path giữ nguyên bản THẬT, nếu không npz biến mất.
                      "region": vung, "target_idx": str(anh_xa[uid]),
                      # khoá CŨ dựng theo dialect THẬT, nên A và B va chạm
                      "label_key": f"vn/{dialect}/{slug}"})
        phan["train"] += h[:8]
        phan["val"] += h[8:10]
        phan["test"] += h[10:12]

    for ten, hang in phan.items():
        with (d / f"{ten}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cot, extrasaction="ignore")
            w.writeheader()
            w.writerows(hang)

    meta = {
        "schema_version": 2,
        "purpose": "operational",
        "split_id": "smoke-region",
        "policy": {"min_samples_per_class": 0, "min_classes": 2},
        "classes": [
            {"class_uid": uid, "target_idx": anh_xa[uid], "class_idx": 900 + i,
             "slug": slug, "dialect": dialect, "region": vung}
            for i, (uid, slug, vung) in enumerate(BA_LOP)
        ],
        "class_mapping_hash": canonical_mapping_hash(anh_xa),
        "files": file_hashes(d),
    }
    (d / "split_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return d, anh_xa, dialect


class TestBangChung4_TrainerThayBaLopRieng:
    def test_khoa_cu_THAT_SU_va_cham(self, hien_vat):
        """Chốt hiệu lực của cả tệp: fixture phải CÒN mang va chạm.

        Chỉ khẳng định `num_classes == 3` là chưa đủ. Một ngày nào đó ai đó sửa
        fixture khiến `label_key` cũng thành ba giá trị khác nhau — ca kia vẫn
        xanh nhưng không còn bảo vệ lỗi QIPEDC nữa. Đó đúng kiểu đột biến vô
        hiệu đã gặp ba lần trong phiên này.
        """
        d, _, _ = hien_vat
        with (d / "train.csv").open(encoding="utf-8") as f:
            hang = list(csv.DictReader(f))
        khoa_cu = {(r.get("label_key") or "").strip() for r in hang}
        uid = {(r.get("class_uid") or "").strip() for r in hang}

        assert len(khoa_cu) == 2, f"3 lớp phải va chạm còn 2 khoá cũ, nhận {khoa_cu}"
        assert len(uid) == 3, f"phải có 3 class_uid riêng, nhận {uid}"

    def test_chay_that_va_ra_dung_3_lop(self, hien_vat, tmp_path):
        d, anh_xa, dialect = hien_vat
        out = tmp_path / "out"
        out.mkdir()

        proc = subprocess.run(
            [sys.executable, "-m", "processed.train_utils.train_tcn",
             "--epochs=1", "--batch_size=4", "--device=cpu",
             f"--dialect={dialect}",
             f"--train_csv={d / 'train.csv'}", f"--val_csv={d / 'val.csv'}",
             f"--test_csv={d / 'test.csv'}", f"--features_root={FEATURES}",
             f"--out_dir={out}", f"--metrics_file={out / 'm.jsonl'}"],
            cwd=str(REPO), capture_output=True, text=True, timeout=900)

        assert proc.returncode == 0, (
            f"huấn luyện hỏng:\n{proc.stdout[-2500:]}\n{proc.stderr[-2500:]}")
        assert "[OPERATIONAL]" in proc.stdout, (
            f"trainer KHÔNG vào nhánh vận hành — nó vẫn đi đường cũ.\n"
            f"{proc.stdout[-2000:]}")

        ckpts = list(out.glob("*.pt"))
        assert ckpts, f"không có checkpoint:\n{proc.stdout[-1500:]}"

        import torch

        ck = torch.load(ckpts[0], map_location="cpu", weights_only=False)
        assert ck["num_classes"] == 3, (
            f"num_classes={ck['num_classes']}, mong 3. Bằng 2 nghĩa là hai vùng "
            f"của `an` đã bị gộp — chuỗi còn chỗ rơi về label_key.")
        self._ck = ck

    def test_checkpoint_mang_dung_anh_xa(self, hien_vat, tmp_path):
        """Bằng chứng 5: đi trọn vòng trên một lượt chạy THẬT."""
        d, anh_xa, dialect = hien_vat
        out = tmp_path / "out2"
        out.mkdir()
        proc = subprocess.run(
            [sys.executable, "-m", "processed.train_utils.train_tcn",
             "--epochs=1", "--batch_size=4", "--device=cpu",
             f"--dialect={dialect}",
             f"--train_csv={d / 'train.csv'}", f"--val_csv={d / 'val.csv'}",
             f"--test_csv={d / 'test.csv'}", f"--features_root={FEATURES}",
             f"--out_dir={out}", f"--metrics_file={out / 'm.jsonl'}"],
            cwd=str(REPO), capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2500:]

        import torch

        from processed.train_utils.label_mapping import consume_checkpoint_mapping

        ck = torch.load(list(out.glob("*.pt"))[0], map_location="cpu",
                        weights_only=False)

        idx_to_uid = consume_checkpoint_mapping(ck)
        assert {u: i for i, u in idx_to_uid.items()} == anh_xa, (
            "ánh xạ sau khi nạp checkpoint khác ánh xạ trước khi huấn luyện")
        assert idx_to_uid[anh_xa["UID_SMOKE_A"]] != idx_to_uid[anh_xa["UID_SMOKE_B"]]

        # tên hiển thị không được sập về UID thô
        hien_thi = ck.get("idx_to_label") or {}
        gia_tri = [hien_thi[k] if isinstance(hien_thi[k], dict) else {}
                   for k in hien_thi]
        nhan = {str(v.get("label_original") or "") for v in gia_tri}
        assert "an [bac]" in nhan and "an [nam]" in nhan, (
            f"nhãn hiển thị sập về UID thô: {nhan}")
