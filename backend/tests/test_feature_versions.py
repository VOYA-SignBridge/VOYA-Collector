"""Các phiên bản đặc trưng phải thật sự đổi dữ liệu, và v1 phải KHÔNG đổi gì.

Vì sao có tệp này
-----------------
`processed/shared/features_v2.py` và tham số `feature_version` của
`NPZSignDataset` vào kho ngày 11-12/09/2026 mà **không kèm bài kiểm nào**. Bộ
test backend vẫn xanh sau khi chúng vào, nhưng đó là vì không có gì chạm tới
đường mới: 2764 lượt đạt đều đi qua `v1`, đúng đường đã có từ trước.

Một tính năng chưa ai chạy thì không phải "chưa được kiểm" — nó là một khẳng
định chưa ai đối chiếu. Và lớp lỗi nguy hiểm nhất ở đây không làm chương trình
chết: nó cho ra một con số. `test_features_root_override.py` tồn tại vì đúng
chuyện đó từng xảy ra — hai nhánh của một thí nghiệm đọc CÙNG một cây đặc trưng
và báo "thay đổi không tạo khác biệt", phát hiện được chỉ vì hai seed trùng nhau
tới mười sáu chữ số thập phân. Cùng cái bẫy ấy đang mở ở đây: nếu `v1z` lặng lẽ
trả về đúng dữ liệu `v1`, lượt ablation ba nhánh sẽ chạy trót lọt và kết luận
độ sâu không quan trọng.

Nên bài kiểm trung tâm của tệp này không phải "v1z có chạy không" mà là
**"v1z có RA KHÁC v1 không"**.

Ba nhóm khẳng định:

  1. Bảng số chiều và đường dẫn xuất — mỗi phiên bản lấy dữ liệu từ đâu.
  2. `v1` bất biến từng byte. Đây là điều kiện để mọi hiện vật đã đóng băng còn
     tái lập được; hỏng nó là hỏng mọi con số đã công bố.
  3. Thiếu `landmarks_raw` phải nổ ra thành `MissingRawLandmarks`, và KHÔNG
     được rơi vào đường "tệp hỏng" — đường ấy thay thầm bằng mẫu kế bên, nên
     nuốt ngoại lệ này sẽ nhân bản và gán sai nhãn 9% train / 62% test của
     root_strict_v13 mà không nêu gì.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "processed"))

from processed.shared import features_v2 as fv2  # noqa: E402
from processed.train_utils.dataset_loader import (  # noqa: E402
    MissingRawLandmarks,
    NPZSignDataset,
)

SEQ_LEN = 8
BASE = 126


def _loader(feature_version: str) -> NPZSignDataset:
    """Dựng đối tượng mà không chạy `__init__` (nó đòi đọc một CSV).

    Chỉ đặt đúng những thuộc tính mà `_choose_array_from_npz` dùng tới. Giống
    cách `test_features_root_override.py` làm, và vì cùng một lý do: hành vi
    cần kiểm nằm ở việc chọn mảng, không phải ở việc phân tích cú pháp CSV.
    """
    ds = NPZSignDataset.__new__(NPZSignDataset)
    ds.feature_version = feature_version
    ds._base_version = (
        "v1z" if feature_version == "v1g"
        else "v2" if feature_version == "v2g"
        else feature_version
    )
    ds.feature_key_priority = ["sequence", "landmarks_normalized"]
    return ds


@pytest.fixture
def stored():
    """Một mẫu như nó nằm trên đĩa: `sequence` đã chuẩn hoá, kèm `landmarks_raw`."""
    rng = np.random.RandomState(20260912)
    return {
        "sequence": rng.rand(SEQ_LEN, BASE).astype(np.float32),
        "landmarks_raw": rng.rand(SEQ_LEN, BASE).astype(np.float32),
    }


# ---------------------------------------------------------------------------
# 1. Bảng phiên bản
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "version, dim, needs_raw, has_geometry",
    [
        ("v1", 126, False, False),
        ("v1z", 126, False, False),
        ("v1g", 182, False, True),
        ("v2", 126, True, False),
        ("v2g", 172, True, True),
    ],
)
def test_bang_phien_ban(version, dim, needs_raw, has_geometry):
    """Số chiều và nguồn dữ liệu của từng phiên bản.

    Ghim ở đây vì `feature_dim` quyết định `expected_feature_dim` của loader,
    và loader TỪ CHỐI mọi mẫu có shape khác. Một con số sai ở đây không làm sai
    kết quả — nó làm cả lượt chạy không khởi động được, nhưng với thông báo nói
    về shape của tệp .npz chứ không nói về bảng này.
    """
    assert fv2.feature_dim(version) == dim
    assert fv2.needs_raw(version) is needs_raw
    assert fv2.has_geometry(version) is has_geometry


def test_phien_ban_la_tu_choi_chu_khong_doan():
    """Một phiên bản không biết phải NỔ, không được lặng lẽ lùi về v1."""
    with pytest.raises(ValueError, match="unknown feature version"):
        fv2.feature_dim("v3")


# ---------------------------------------------------------------------------
# 2. v1 bất biến, các phiên bản khác PHẢI khác
# ---------------------------------------------------------------------------

def test_v1_tra_ve_dung_mang_da_luu(stored):
    """`v1` không được đụng vào gì.

    Đây là điều kiện để các hiện vật nghiên cứu đã đóng băng còn tái lập được.
    So sánh bằng `is`-tương-đương chứ không chỉ `allclose`: một phép sao chép
    vô hại hôm nay là chỗ cho một phép biến đổi lẻn vào ngày mai.
    """
    out = _loader("v1")._choose_array_from_npz(stored)
    assert np.array_equal(out, stored["sequence"])
    assert out.dtype == stored["sequence"].dtype


def test_v1z_that_su_doi_du_lieu(stored):
    """Bài kiểm trung tâm: v1z phải RA KHÁC v1.

    Nếu v1z lặng lẽ trả về dữ liệu v1 thì lượt ablation ba nhánh trong
    `scripts/run_feature_ablation.sh` vẫn chạy trót lọt, ba nhánh ra ba con số
    gần nhau, và kết luận rút ra sẽ là "độ sâu không quan trọng" — trong khi
    thật ra chưa nhánh nào từng thấy một phép biến đổi nào.

    Đúng cái cách lượt z-fix ablation đầu tiên cho hai seed trùng nhau tới mười
    sáu chữ số thập phân, và đó là thứ duy nhất làm lộ ra chuyện.
    """
    v1 = _loader("v1")._choose_array_from_npz(stored)
    v1z = _loader("v1z")._choose_array_from_npz(stored)

    assert v1z.shape == v1.shape, "v1z giữ nguyên số chiều, chỉ đổi giá trị"
    assert not np.array_equal(v1z, v1), (
        "v1z trả về đúng dữ liệu v1 — phép quy chiếu lại độ sâu không chạy. "
        "Mọi lượt ablation dùng nó sẽ so một thứ với chính nó."
    )


def test_v1g_doc_cung_nen_voi_v1z(stored):
    """v1g lấy đúng khối 126 chiều của v1z làm nền.

    Hình học KHÔNG được nối ở đây. `_base_version` ánh xạ v1g -> v1z và
    v2g -> v2, nên mảng đi qua `_choose_array_from_npz` luôn là khối điểm mốc
    126 chiều; phần hình học nối thêm ở `_finalize`, SAU augmentation. Xem
    `test_hinh_hoc_noi_sau_augmentation` về lý do thứ tự đó là bắt buộc.
    """
    v1z = _loader("v1z")._choose_array_from_npz(stored)
    nen_cua_v1g = _loader("v1g")._choose_array_from_npz(stored)

    assert nen_cua_v1g.shape == (SEQ_LEN, BASE)
    assert np.array_equal(nen_cua_v1g, v1z), (
        "nền của v1g phải đúng bằng v1z; khác đi thì chênh lệch v1z -> v1g "
        "không còn quy về riêng phần hình học được"
    )


def test_hinh_hoc_lam_rong_dung_so_chieu(stored):
    """`append_geometry` đưa 126 -> số chiều đã khai, và giữ nguyên 126 cột đầu.

    Bài kiểm này bắt được một lỗi có thật khi được viết ra: `append_geometry`
    không nhận tham số phiên bản và luôn dùng bộ mô tả planar (28/tay), nên
    `v2g` cho 126 + 56 = 182 cột trong khi `feature_dim("v2g")` khai
    126 + GEOM_DIM = 172. Mọi lượt chạy v2g dừng ở phép kiểm lô đầu của
    `train_tcn` với một thông báo nói về shape, không nói về nguyên nhân.

    Hai bộ mô tả KHÔNG thay nhau được: `geometric_features` tính pháp tuyến
    lòng bàn tay 3-D, chỉ có nghĩa khi z cùng đơn vị với x/y (chỉ v2, dựng từ
    raw). Bộ planar cố ý tránh độ lớn của z vì v1z quy chiếu z theo chính nó.
    """
    for version in ("v1g", "v2g"):
        nen = _loader(version)._choose_array_from_npz(stored)
        rong = fv2.append_geometry(nen, version)
        assert rong.shape == (SEQ_LEN, fv2.feature_dim(version)), (
            f"{version}: append_geometry cho {rong.shape[-1]} cột nhưng "
            f"feature_dim khai {fv2.feature_dim(version)}"
        )
        assert np.allclose(rong[:, :BASE], nen), (
            "phần hình học chỉ được NỐI THÊM, không được sửa khối điểm mốc"
        )


def test_hai_bo_mo_ta_thuc_su_khac_nhau(stored):
    """v1g và v2g phải dùng HAI bộ mô tả khác nhau, không phải cùng một bộ.

    Nếu chúng trùng nhau thì một trong hai phiên bản đang dùng bộ mô tả sai cho
    ngữ nghĩa độ sâu của nó, và chênh lệch đo được giữa hai nhánh sẽ bị quy sai
    nguyên nhân.
    """
    nen = _loader("v1g")._choose_array_from_npz(stored)
    v1g_geom = fv2.append_geometry(nen, "v1g")[:, BASE:]
    v2g_geom = fv2.append_geometry(nen, "v2g")[:, BASE:]
    assert v1g_geom.shape[1] != v2g_geom.shape[1], (
        "hai phiên bản đang nhận cùng một bộ mô tả hình học"
    )


def test_append_geometry_tu_choi_phien_ban_khong_co_hinh_hoc(stored):
    """Gọi với v1/v1z/v2 phải NỔ, không được lặng lẽ nối bừa một bộ."""
    nen = _loader("v1z")._choose_array_from_npz(stored)
    for version in ("v1", "v1z", "v2"):
        with pytest.raises(ValueError, match="không phải phiên bản có hình học"):
            fv2.append_geometry(nen, version)


def test_hinh_hoc_noi_sau_augmentation():
    """Thứ tự trong `_finalize` phải là augment TRƯỚC, hình học SAU.

    Không phải chuyện văn phong. Augmentation (lật gương, xoay, co giãn) định
    nghĩa trên toạ độ điểm mốc. Nối hình học trước rồi augment sẽ đem các phép
    biến đổi toạ độ áp lên khoảng cách, góc gập và véc-tơ pháp tuyến của lòng
    bàn tay — những đại lượng không biến đổi theo cùng quy tắc. Kết quả vẫn là
    một mảng đúng số chiều, vẫn huấn luyện được, và vẫn ra một con số.

    Ngược lại, dựng hình học TỪ điểm mốc đã augment là điều đúng: bàn tay đã
    lật gương thì các mô tả của nó cũng phải là của bàn tay đã lật.
    """
    import inspect

    src = inspect.getsource(NPZSignDataset._finalize)
    i_augment = src.index("self.augment_fn(x)")
    i_hinh_hoc = src.index("append_geometry")
    assert i_augment < i_hinh_hoc, (
        "hình học đang được nối TRƯỚC augmentation; các phép biến đổi toạ độ "
        "sẽ bị áp lên khoảng cách và góc, vốn không biến đổi theo cùng quy tắc"
    )


def test_v2_dung_landmarks_raw_chu_khong_dung_sequence(stored):
    """v2 phải đọc `landmarks_raw`, không phải `sequence`.

    Kiểm bằng cách cho hai mảng khác hẳn nhau rồi xem kết quả bám theo cái nào.
    Đọc nhầm `sequence` sẽ không nổ — nó chỉ dựng lại đặc trưng từ dữ liệu ĐÃ
    chuẩn hoá một lần, tức là áp phép biến đổi hai lần, và vẫn ra một con số.
    """
    chi_raw = dict(stored, sequence=np.zeros((SEQ_LEN, BASE), dtype=np.float32))
    out = _loader("v2")._choose_array_from_npz(chi_raw)
    tu_sequence = fv2.build_sequence(chi_raw["sequence"], "v2")
    tu_raw = fv2.build_sequence(chi_raw["landmarks_raw"], "v2")

    assert np.array_equal(out, tu_raw)
    assert not np.array_equal(out, tu_sequence)


def test_v2g_doc_cung_nen_voi_v2(stored):
    v2 = _loader("v2")._choose_array_from_npz(stored)
    nen_cua_v2g = _loader("v2g")._choose_array_from_npz(stored)
    assert nen_cua_v2g.shape == (SEQ_LEN, BASE)
    assert np.array_equal(nen_cua_v2g, v2)


# ---------------------------------------------------------------------------
# 3. Thiếu dữ liệu phải ồn, không được im
# ---------------------------------------------------------------------------

def test_thieu_landmarks_raw_thi_no_ra_MissingRawLandmarks(stored):
    """Chỉ 37,9% hàng của tập kiểm root_strict_v13 còn giữ `landmarks_raw`."""
    khong_raw = {"sequence": stored["sequence"]}
    for version in ("v2", "v2g"):
        with pytest.raises(MissingRawLandmarks):
            _loader(version)._choose_array_from_npz(khong_raw)


def test_v1z_v1g_khong_can_raw(stored):
    """Nửa còn lại của lý do v1z/v1g tồn tại: chúng chạy trên 100% mẫu."""
    khong_raw = {"sequence": stored["sequence"]}
    for version in ("v1z", "v1g"):
        out = _loader(version)._choose_array_from_npz(khong_raw)
        # 126 ở tầng này với CẢ HAI: hình học nối sau, trong `_finalize`.
        assert out.shape == (SEQ_LEN, BASE)
        assert fv2.append_geometry(out).shape[-1] == fv2.feature_dim(version)             if fv2.has_geometry(version) else out.shape[-1] == fv2.feature_dim(version)


def test_MissingRawLandmarks_khong_bi_duong_tep_hong_nuot():
    """Ngoại lệ này KHÔNG được là con của cái mà `except Exception` bắt để thay mẫu.

    `__getitem__` bắt `MissingRawLandmarks` rồi `raise` lại, TRƯỚC mệnh đề
    `except Exception` thay bằng mẫu kế bên. Trật tự ấy là thứ giữ cho một mẫu
    thiếu raw không lặng lẽ biến thành bản sao của mẫu bên cạnh, mang nhãn của
    mẫu bên cạnh.

    Bài kiểm này ghim chính trật tự đó: đảo hai mệnh đề `except` sẽ không làm
    hỏng bất kỳ bài kiểm nào khác, và hậu quả chỉ hiện ra dưới dạng một tập
    huấn luyện có 9% hàng bị nhân bản sai nhãn.
    """
    import inspect

    src = inspect.getsource(NPZSignDataset.__getitem__)
    i_missing = src.index("except MissingRawLandmarks")
    i_chung = src.index("except Exception")
    assert i_missing < i_chung, (
        "`except MissingRawLandmarks` phải đứng TRƯỚC `except Exception`; "
        "đảo lại là mẫu thiếu raw bị thay thầm bằng mẫu kế bên"
    )
    assert "raise" in src[i_missing:i_chung], (
        "mệnh đề MissingRawLandmarks phải `raise` lại, không được nuốt"
    )


# ---------------------------------------------------------------------------
# 4. Đường trả-về-nguyên-xi phải bị tầng trên chặn
# ---------------------------------------------------------------------------

def test_build_sequence_tra_ve_nguyen_xi_khi_shape_la(stored):
    """`build_sequence` trả về đầu vào không đổi nếu shape không phải (T, 126).

    Ghi lại ở đây như một tính chất ĐÃ BIẾT, không phải một tính chất mong
    muốn: bản thân nó là một đường cho ra dữ liệu sai mà không báo. Thứ làm nó
    vô hại là phép kiểm shape ở `_load_and_check` — xem bài kiểm ngay dưới.
    Nếu ai đó nới phép kiểm ấy, bài kiểm này thành lời nhắc rằng đường im lặng
    vẫn còn đó.
    """
    sai_bo_cuc = np.random.RandomState(0).rand(SEQ_LEN, 2, 21, 3).astype(np.float32)
    out = fv2.build_sequence(sai_bo_cuc, "v2g")
    assert out.shape == sai_bo_cuc.shape
    assert out.shape[-1] != fv2.feature_dim("v2g")


def test_loader_van_con_phep_kiem_shape_truoc_hinh_hoc():
    """Phép kiểm chặn đường trả-về-nguyên-xi nằm ở `__getitem__`.

    Ở tầng ấy mảng CHƯA nối hình học, nên nó đối chiếu với hằng 126 chứ không
    với `expected_feature_dim`. Một lượt `build_sequence` trả về nguyên xi sẽ
    cho shape khác 126 và bị chặn ngay tại đây.
    """
    import inspect

    src = inspect.getsource(NPZSignDataset.__getitem__)
    assert "_EXPECTED_FEATURE_DIM" in src, (
        "phép kiểm shape đã biến mất; đường trả-về-nguyên-xi của "
        "build_sequence không còn gì chặn"
    )


def test_chieu_rong_cuoi_cung_duoc_doi_chieu():
    """Và chiều rộng SAU khi nối hình học phải được đối chiếu với phiên bản.

    `self.expected_feature_dim` từng là phép kiểm ở `__getitem__`; khi hình học
    chuyển ra sau augmentation, phép kiểm ấy đổi sang hằng 126 và thuộc tính
    này thành mã chết — tính ra, không ai đọc. `train_tcn` có kiểm, nhưng chỉ
    trên lô đầu tiên và chỉ khi đi qua trainer; loader còn phục vụ suy luận và
    `compute_pooled_confusion.py`.
    """
    import inspect

    src = inspect.getsource(NPZSignDataset._finalize)
    assert "expected_feature_dim" in src, (
        "không còn gì đối chiếu chiều rộng cuối cùng với feature_version đã khai"
    )
