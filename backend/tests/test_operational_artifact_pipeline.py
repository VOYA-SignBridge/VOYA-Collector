"""Hiện vật vận hành: từ `make_splits` tới `consume_declared`, không hở khớp.

Vì sao tệp này tồn tại, viết ra vì đó là bài học đắt nhất của lượt 15/08:

`make_splits.class_mapping_checksum` băm `uid=idx`, còn
`label_mapping.canonical_mapping_hash` — hàm mà bên TIÊU THỤ dùng — băm
`uid<TAB>idx`. Hai bản cài đặt của cùng một quy ước, lệch nhau đúng một ký tự
phân tách. Hậu quả: MỌI hiện vật vận hành do `make_splits` ghi ra đều bị
`consume_declared` từ chối, với thông báo "hiện vật đã bị sửa sau khi ghi" —
trong khi không ai sửa gì cả.

Bộ kiểm cũ không thấy được, và lý do đáng nhớ hơn cả lỗi:

  - `test_split_class_floor` kiểm bên SẢN XUẤT bằng chính hàm của bên sản xuất
    (`rep[...] == class_mapping_checksum(...)`);
  - `test_label_identity` và `test_operational_smoke_run` kiểm bên TIÊU THỤ
    bằng fixture TỰ TÍNH metadata bằng `canonical_mapping_hash`.

Mỗi phía tự nhất quán với chính mình, nên cả hai xanh. Không ca nào bắt hai
phía nói chuyện với nhau. Đó là loại xanh-giả thứ bảy: **hai nửa của một hợp
đồng, mỗi nửa được kiểm bằng định nghĩa của riêng nó.**

Nên mọi ca ở đây đều đi qua CLI thật của `make_splits` rồi đưa kết quả cho
hàm tiêu thụ thật. Không fixture nào được tự tay dựng `split_metadata.json`.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.splits import make_splits as ms  # noqa: E402
from processed.train_utils.label_mapping import (  # noqa: E402
    canonical_mapping_hash,
    consume_declared,
    partitions_agree,
)
from processed.train_utils.split_artifact import (  # noqa: E402
    PURPOSE_OPERATIONAL,
    resolve_split_artifact,
)

#: Ba lớp đủ mẫu ở `pn-a`, một lớp thiếu, và một lớp ở phương ngữ khác. Lớp
#: thiếu và lớp phương ngữ khác đều phải biến mất khỏi hiện vật của `pn-a`,
#: nhưng vì hai lý do KHÁC nhau — và test phân biệt được hai lý do đó.
DU_MAU = 30
THIEU_MAU = 5

LOP = [
    # (class_uid, class_idx, slug, dialect, region, so_mau)
    ("U-AAA", 1, "an", "pn-a", "bac", DU_MAU),
    ("U-BBB", 7, "cam-on", "pn-a", "nam", DU_MAU),
    ("U-CCC", 42, "xin-chao", "pn-a", "nam", DU_MAU),
    ("U-YEU", 9, "lay-chi", "pn-a", "nam", THIEU_MAU),
    ("U-KHAC", 3, "khac", "pn-b", "nam", DU_MAU),
]

COT_LABELS = ["class_uid", "class_idx", "slug", "label_original", "language",
              "dialect", "folder_name", "region"]
# `review_status` phải có mặt, và giá trị phải là `approved`.
#
# Corpus tổng hợp này mô hình hoá một kho ĐANG DÙNG ĐƯỢC — `make_splits` rót từ
# nó ra split, nên nó tương ứng với `dataset/samples.csv` thật, nơi cả 3.862
# dòng mang `approved` sau lượt migration.
#
# Bỏ cột đi thì cổng kiểm duyệt đọc sự im lặng thành "chưa duyệt" (đúng như
# thiết kế: im lặng nghĩa là chưa biết) và loại sạch mọi dòng, rồi `make_splits`
# dừng với "Khong con mau nao sau cong kiem duyet" — 41 bài đỏ vì một lý do
# chẳng liên quan gì tới thứ chúng đang kiểm.
COT_SAMPLES = ["sample_uid", "class_uid", "slug", "label_original", "language",
               "dialect", "file_path", "signer_id", "user_id", "review_status"]


def _viet(path: Path, cot, hang):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cot)
        w.writeheader()
        w.writerows(hang)


@pytest.fixture
def kho(tmp_path, monkeypatch):
    """Một kho dữ liệu tí hon, và `make_splits` bị trỏ vào đúng nó.

    Trỏ bằng monkeypatch chứ không bằng biến môi trường: `make_splits` phân
    giải đường dẫn lúc NẠP MODULE, nên đặt biến môi trường sau đó không có tác
    dụng — và một test tưởng mình đang ghi vào tmp mà thật ra ghi vào
    `dataset/samples.csv` là đúng sự cố đã xảy ra ngày 13/08.
    """
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _viet(dataset / "labels.csv", COT_LABELS, [
        {"class_uid": uid, "class_idx": ci, "slug": slug,
         "label_original": slug.replace("-", " "), "language": "vn",
         "dialect": pn, "folder_name": slug, "region": vung}
        for uid, ci, slug, pn, vung, _n in LOP
    ])
    _viet(dataset / "samples.csv", COT_SAMPLES, [
        {"sample_uid": f"{uid}-{i:03d}", "class_uid": uid, "slug": slug,
         "label_original": slug, "language": "vn", "dialect": pn,
         "file_path": f"{slug}/{uid}_{i:03d}.npz",
         # Nhiều người ký, nếu không thì các chế độ chia theo nhóm không có
         # gì để phân bổ.
         "signer_id": f"S{i % 3}", "user_id": f"S{i % 3}",
         "review_status": "approved"}
        for uid, _ci, slug, pn, _vung, n in LOP for i in range(n)
    ])

    goc_splits = tmp_path / "processed" / "splits"
    goc_splits.mkdir(parents=True)
    monkeypatch.setattr(ms, "SAMPLES_CSV", dataset / "samples.csv")
    monkeypatch.setattr(ms, "LABELS_CSV", dataset / "labels.csv")
    monkeypatch.setattr(ms, "OUT_DIR", goc_splits)
    return goc_splits


def _chay(kho, monkeypatch, *co, split_id="op-test", tenant_id="iso_a"):
    """Gọi CLI thật của make_splits. Trả về thư mục hiện vật.

    Đặt lại `OUT_DIR` về gốc trước MỖI lượt, và đó không phải chi tiết vụn:
    `main()` dời `OUT_DIR` sang `<gốc>/operational/<id>` rồi để nguyên đó. Ngoài
    đời không sao — mỗi lượt chạy là một tiến trình mới. Trong một tiến trình
    thì lượt thứ hai dời tiếp thành `operational/<id>/operational/<id>`, một
    đường dẫn chưa tồn tại, nên phép kiểm "chỉ-tạo-mới" im lặng mất tác dụng.

    Dòng này là thứ làm cho ca kiểm tính bất biến kiểm đúng cái nó nói.
    """
    monkeypatch.setattr(ms, "OUT_DIR", kho)
    argv = ["make_splits.py", f"--operational_split_id={split_id}", *co]
    # Hiện vật vận hành phải có chủ (C2b). Truyền ở đây để các ca cũ vẫn kiểm
    # đúng thứ chúng sinh ra để kiểm; ca "thiếu chủ thì DỪNG" nằm riêng ở
    # `test_split_owner_metadata.py` và gọi CLI KHÔNG có cờ này.
    if tenant_id is not None:
        argv.append(f"--tenant_id={tenant_id}")
    monkeypatch.setattr(sys, "argv", argv)
    ms.main()
    # `main()` dời OUT_DIR sang thư mục hiện vật; đọc lại từ chính module để
    # không có bản cài đặt thứ hai của quy tắc đặt tên.
    return ms.OUT_DIR


class TestHopDongSanXuatTieuThu:
    """Nửa ghi và nửa đọc phải dùng CÙNG MỘT định nghĩa."""

    def test_hai_ham_bam_la_mot_quy_uoc_duy_nhat(self):
        """Ca rẻ nhất bắt được lỗi 15/08, và nó đã không tồn tại.

        `class_mapping_checksum` giờ uỷ quyền cho `canonical_mapping_hash`.
        Ai đó gỡ uỷ quyền và tự băm lại — dù bằng quy ước "hợp lý" nào — thì ca
        này đỏ ngay, thay vì để lỗi hiện ra ở một lượt huấn luyện thật.
        """
        anh_xa = {"U-B": 1, "U-A": 0, "U-C": 2}
        assert ms.class_mapping_checksum(anh_xa.items()) == \
            canonical_mapping_hash(anh_xa)

    def test_hien_vat_that_duoc_ben_tieu_thu_chap_nhan(self, kho, monkeypatch):
        """Ca chính: đi qua CLI thật, rồi đưa cho hàm tiêu thụ thật.

        Không fixture nào ở đây tự dựng `split_metadata.json`. Đó là điều kiện
        để ca này có ý nghĩa — mọi ca tự dựng metadata đều chỉ kiểm bên tiêu
        thụ nói chuyện với chính nó.
        """
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")

        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))
        anh_xa = consume_declared(meta)      # đỏ nếu hai bản băm lệch nhau

        assert len(anh_xa) == 3
        assert sorted(anh_xa.values()) == [0, 1, 2]

    def test_resolver_xac_minh_duoc_hien_vat_vua_ghi(self, kho, monkeypatch):
        """Băm từng tệp phải được tính SAU khi ba CSV đã ghi xong.

        Tính trước thì `files` mô tả một trạng thái chưa từng tồn tại, và
        resolver sẽ từ chối chính hiện vật vừa được sinh ra hợp lệ.
        """
        _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")

        art = resolve_split_artifact(purpose=PURPOSE_OPERATIONAL,
                                     splits_root=kho, split_id="op-test",
                                     tenant_id="iso_a")
        assert art.split_id == "op-test"
        assert art.purpose == PURPOSE_OPERATIONAL

    def test_ba_phan_dong_y_voi_ban_khai(self, kho, monkeypatch):
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))
        anh_xa = consume_declared(meta)

        theo_phan = {
            ten: list(csv.DictReader((d / f"{ten}.csv").open(encoding="utf-8")))
            for ten in ("train", "val", "test")
        }
        partitions_agree(theo_phan, anh_xa)   # ném MappingError nếu lệch

        for ten, hang in theo_phan.items():
            assert hang, f"{ten} rỗng"
            assert {r["class_uid"] for r in hang} == set(anh_xa), ten


class TestPhamViPhuongNgu:
    """`--dialects` không phải tiện nghi; thiếu nó thì `num_classes` sai."""

    def test_lop_phuong_ngu_khac_khong_lot_vao(self, kho, monkeypatch):
        """Trainer lọc lại theo `--dialect` lúc chạy, nhưng bản khai thì không.

        `consume_declared` lấy `num_classes` từ mục `classes`, còn
        `partitions_agree` chỉ từ chối class_uid LẠ chứ không đòi mọi lớp đã
        khai phải có mặt. Nên một hiện vật khai cả hai phương ngữ mà trainer
        chỉ đọc một sẽ dựng tầng đầu ra thừa chiều — chạy trót lọt, không
        cảnh báo.
        """
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        assert "U-KHAC" not in {c["class_uid"] for c in meta["classes"]}
        assert meta["num_classes"] == 3

    def test_san_tinh_TRONG_pham_vi_chu_khong_tren_toan_bo(self, kho, monkeypatch):
        """Thứ tự lọc-rồi-mới-áp-sàn là thứ quyết định `can-tho` có FAIL không.

        Áp sàn trên toàn bộ từ vựng rồi mới cắt phương ngữ thì
        `enforce_min_classes` đếm số lớp của CẢ KHO và cho qua, kể cả khi
        phương ngữ được chọn chỉ còn một lớp.
        """
        with pytest.raises(SystemExit) as loi:
            _chay(kho, monkeypatch, "--dialects=pn-b", "--min_samples_per_class=25",
                  split_id="op-chi-mot-lop")

        assert "còn 1 lớp" in str(loi.value)

    def test_go_sai_ten_phuong_ngu_thi_dung(self, kho, monkeypatch):
        """Im lặng cho qua sẽ cho ra một hiện vật rỗng hoặc sai tập con."""
        with pytest.raises(SystemExit) as loi:
            _chay(kho, monkeypatch, "--dialects=pn-khong-co-that",
                  split_id="op-sai-ten")

        assert "pn-khong-co-that" in str(loi.value)
        assert "pn-a" in str(loi.value), "phải liệt kê phương ngữ có thật"

    def test_pham_vi_nam_trong_ban_khai(self, kho, monkeypatch):
        """Đọc lại sau ba tháng, "3 lớp" một mình không nói được là 3 lớp gì."""
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        assert meta["scope"] == {"dialects": ["pn-a"]}


class TestLopYeuBienMatKhoiHienVat:
    """Không phải "trainer bỏ qua lớp yếu" — lớp yếu KHÔNG TỒN TẠI ở đây."""

    def test_khong_co_o_bat_ky_dau(self, kho, monkeypatch):
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        assert "U-YEU" not in {c["class_uid"] for c in meta["classes"]}
        assert "U-YEU" not in consume_declared(meta)
        for ten in ("train", "val", "test"):
            hang = list(csv.DictReader((d / f"{ten}.csv").open(encoding="utf-8")))
            assert "U-YEU" not in {r["class_uid"] for r in hang}, ten

    def test_nhung_van_duoc_ghi_lai_la_da_bi_loai(self, kho, monkeypatch):
        """Biến mất KHÁC với chưa từng có. Hiện vật phải phân biệt được.

        Người đọc sau cần biết lớp này đang thu dở chứ không phải bị xoá — đó
        là cơ sở cho phân biệt "lớp bị tắt" và "chưa đủ dữ liệu huấn luyện"
        ở giao diện.
        """
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        da_loai = {x["class"]: x for x in meta["excluded_below_floor"]}
        assert da_loai["U-YEU"]["samples"] == THIEU_MAU

    def test_target_idx_lien_tuc_sau_khi_loai(self, kho, monkeypatch):
        """`class_idx` thưa (1, 7, 42) nhưng `target_idx` phải kín 0..K-1."""
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        assert sorted(int(c["class_idx"]) for c in meta["classes"]) == [1, 7, 42]
        assert sorted(c["target_idx"] for c in meta["classes"]) == [0, 1, 2]


class TestNhanDocDiKemAnhXa:
    """Danh tính là `class_uid`; nhãn đọc phải đi kèm, không thay thế."""

    def test_ban_khai_mang_du_slug_dialect_region(self, kho, monkeypatch):
        """Thiếu chúng thì màn hình thời gian thực hiện UID thô.

        `normalize_idx_to_label` tra từ vựng theo `label_key`, mà một UID thì
        không khớp mục nào — nên nhãn rỗng chứ không phải nhãn cũ.
        """
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        lop = {c["class_uid"]: c for c in meta["classes"]}
        assert lop["U-AAA"]["slug"] == "an"
        assert lop["U-AAA"]["region"] == "bac"
        assert lop["U-BBB"]["region"] == "nam"
        assert lop["U-AAA"]["dialect"] == "pn-a"

    def test_region_di_theo_tung_lop_chu_khong_theo_phuong_ngu(self, kho, monkeypatch):
        """Đây chính là hình dạng va chạm mà QIPEDC sẽ tạo ra.

        `U-AAA` và `U-BBB` cùng `language` + `dialect`, khác `region`. Khoá cũ
        `vn/<dialect>/<slug>` không chứa region, nên nếu hiện vật cũng đánh mất
        region thì không còn gì phân biệt được hai vùng của một từ.
        """
        d = _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))

        vung = {c["class_uid"]: c["region"] for c in meta["classes"]}
        assert set(vung.values()) == {"bac", "nam"}


class TestBatBienVaChiTaoMoi:
    def test_ghi_de_hien_vat_da_co_thi_dung(self, kho, monkeypatch):
        """Checkpoint cũ trỏ vào `split_id` này sẽ nói sai nguồn gốc."""
        _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")

        with pytest.raises(SystemExit) as loi:
            _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")

        assert "BẤT" in str(loi.value) or "đã tồn tại" in str(loi.value)

    def test_cong_chan_thi_KHONG_de_lai_thu_muc(self, kho, monkeypatch):
        """Thư mục rỗng vẫn là một hiện vật với người đọc sau.

        Bản đầu tạo thư mục ngay lúc phân giải `--operational_split_id`, trước
        mọi cổng. `can-tho` bị chặn đúng nhưng vẫn để lại
        `operational/can-tho-.../` rỗng — nó qua được phép kiểm "chỉ-tạo-mới"
        (rỗng nên không tính là đã tồn tại) và làm resolver báo "có hiện vật
        nhưng thiếu bản khai".
        """
        with pytest.raises(SystemExit):
            _chay(kho, monkeypatch, "--dialects=pn-b", "--min_samples_per_class=25",
                  split_id="op-bi-chan")

        assert not (kho / "operational" / "op-bi-chan").exists()

    def test_khong_dung_toi_ba_tep_nghien_cuu_o_goc(self, kho, monkeypatch):
        """`--operational_split_id` phải chuyển hướng, không ghi song song."""
        _chay(kho, monkeypatch, "--dialects=pn-a", "--min_samples_per_class=25")

        for ten in ("train.csv", "val.csv", "test.csv"):
            assert not (kho / ten).exists(), f"{ten} bị ghi ở gốc"
