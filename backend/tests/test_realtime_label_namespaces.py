"""Tên lớp hiển thị phải là TÊN, không phải khoá thô.

Sự cố 12/09/2026
================
Trang nhận diện thời gian thực hiện `vn/alphabet/y` ở chỗ đáng lẽ là `Y`.

Không tầng nào đỏ. Mô hình đoán đúng lớp, độ tin cậy đúng, hợp đồng checkpoint
hợp lệ, dịch vụ khởi động sạch. Chỉ riêng cái tên là thô — nên lỗi này không
thể phát hiện bằng bất cứ phép kiểm nào KHÔNG nhìn vào chuỗi hiển thị.

Nguyên nhân: kho có HAI cách gọi tên cùng một lớp, và chúng không trùng nhau.

    vn/bang-chu-cai/y    khoá theo PHƯƠNG NGỮ. `processed/analysis/export_labels.py`
                         dựng `f"{language}/{dialect}/{slug}"`, và đó là thứ nằm
                         trong `index_to_label.json` — bảng tra DUY NHẤT mà dịch
                         vụ thời gian thực có.
    vn/alphabet/y        khoá theo PROFILE. `processed/shared/vocabulary.label_key_v2`
                         dựng `f"{lang}/{profile}/{slug}"`, và đó là thứ nằm
                         trong checkpoint huấn luyện theo lược đồ v2.

Ánh xạ thật, đọc từ `dataset/labels.csv`: `bang-chu-cai -> alphabet` (30 lớp),
`hoa-de -> hoa_de` (8 lớp). Chú ý cả dấu gạch: phương ngữ dùng gạch NỐI, profile
dùng gạch DƯỚI — nên `hoa-de` và `hoa_de` cũng là hai chuỗi khác nhau.

Vì sao hoa-đê KHÔNG hỏng còn bảng chữ cái thì có
================================================
Checkpoint hoa-đê mang `idx_to_label` là DICT ĐẦY ĐỦ (có sẵn `label_original`),
nên nó không cần tra bảng. Checkpoint bảng chữ cái mang KHOÁ TRẦN, nên nó phải
tra — và tra thì trượt. Hai checkpoint cùng sai một chỗ; chỉ một cái lộ ra.

Đó là lý do các bài kiểm dưới đây soi CẢ HAI dạng `idx_to_label`, không chỉ dạng
đang hỏng.
"""

from __future__ import annotations

import pytest

from realtime_service.app.model_loader import (
    _label_lookup_by_key,
    normalize_idx_to_label,
)

#: Một lát cắt của `index_to_label.json` thật, giữ nguyên hình dạng.
LOOKUP = {
    "vn/bang-chu-cai/y": {
        "slug": "y", "label_original": "Y", "language": "vn",
        "dialect": "bang-chu-cai", "label_key": "vn/bang-chu-cai/y",
    },
    "vn/hoa-de/rang-muoi": {
        "slug": "rang-muoi", "label_original": "rang muối", "language": "vn",
        "dialect": "hoa-de", "label_key": "vn/hoa-de/rang-muoi",
    },
    # `dia-chi` có ở HAI phương ngữ — đây là lý do không được lùi về riêng slug.
    "vn/bac/dia-chi": {
        "slug": "dia-chi", "label_original": "Địa chỉ (Bắc)", "language": "vn",
        "dialect": "bac", "label_key": "vn/bac/dia-chi",
    },
    "vn/nam/dia-chi": {
        "slug": "dia-chi", "label_original": "Địa chỉ (Nam)", "language": "vn",
        "dialect": "nam", "label_key": "vn/nam/dia-chi",
    },
}


# ---------------------------------------------------------------------------
# 1. Khoá theo profile phải tra ra được
# ---------------------------------------------------------------------------

def test_khoa_profile_tra_ra_ten_that():
    """`vn/alphabet/y` phải tìm thấy mục `vn/bang-chu-cai/y`."""
    got = _label_lookup_by_key(
        LOOKUP, "vn/alphabet/y", language="vn", dialect="bang-chu-cai")
    assert got.get("label_original") == "Y"


def test_gach_duoi_va_gach_noi_khong_lam_truot():
    """`vn/hoa_de/...` (gạch dưới) phải tìm thấy `vn/hoa-de/...` (gạch nối).

    Chỗ lệch này bị che suốt vì checkpoint hoa-đê mang nhãn đầy đủ nên không cần
    tra. Khi nào có một checkpoint hoa-đê mang khoá trần, nó sẽ hỏng y hệt bảng
    chữ cái — nên khoá lại ngay bây giờ.
    """
    got = _label_lookup_by_key(
        LOOKUP, "vn/hoa_de/rang-muoi", language="vn", dialect="hoa-de")
    assert got.get("label_original") == "rang muối"


def test_khoa_dung_khong_gian_ten_van_tra_binh_thuong():
    got = _label_lookup_by_key(
        LOOKUP, "vn/bang-chu-cai/y", language="vn", dialect="bang-chu-cai")
    assert got.get("label_original") == "Y"


# ---------------------------------------------------------------------------
# 2. Phép dịch phải CHÍNH XÁC, không được đoán
# ---------------------------------------------------------------------------

def test_khong_lui_ve_rieng_slug():
    """Thiếu phương ngữ thì TRƯỢT, chứ không được đoán theo slug.

    `dia-chi` có ở cả `bac` lẫn `nam` và là hai lớp khác nhau. Một phép lùi theo
    riêng slug sẽ trả về một trong hai — đúng 50% thời gian, và sai theo cách
    không ai phát hiện được vì cả hai đều hiện ra một cái tên hợp lý.
    """
    got = _label_lookup_by_key(LOOKUP, "vn/mien-la/dia-chi", language="vn", dialect=None)
    assert got == {}


def test_phuong_ngu_sai_thi_truot_chu_khong_tra_bua():
    got = _label_lookup_by_key(
        LOOKUP, "vn/alphabet/y", language="vn", dialect="khong-ton-tai")
    assert got == {}


def test_dich_dung_phuong_ngu_da_khai_cho_dia_chi():
    """Cùng một slug, hai phương ngữ — mỗi bên ra đúng tên của mình."""
    bac = _label_lookup_by_key(LOOKUP, "vn/x/dia-chi", language="vn", dialect="bac")
    nam = _label_lookup_by_key(LOOKUP, "vn/x/dia-chi", language="vn", dialect="nam")
    assert bac.get("label_original") == "Địa chỉ (Bắc)"
    assert nam.get("label_original") == "Địa chỉ (Nam)"


# ---------------------------------------------------------------------------
# 3. Đường thật: `normalize_idx_to_label`, cả hai dạng idx_to_label
# ---------------------------------------------------------------------------

def test_khoa_tran_ra_ten_chu_khong_ra_khoa():
    """Dạng checkpoint bảng chữ cái: `idx_to_label` là chuỗi trần."""
    out = normalize_idx_to_label(
        {0: "vn/alphabet/y"},
        label_lookup=LOOKUP, default_language="vn", default_dialect="bang-chu-cai")
    assert out[0]["label_original"] == "Y", (
        "vẫn đang hiện khoá thô thay vì tên lớp — đúng lỗi người dùng báo 12/09")
    assert out[0]["label_slug"] == "y"


def test_dict_day_du_khong_bi_bang_tra_ghi_de_sai():
    """Dạng checkpoint hoa-đê: `idx_to_label` đã mang sẵn tên.

    Bảng tra vẫn được hỏi (nó là nguồn mới hơn), nhưng phải tra ra ĐÚNG mục —
    một phép dịch sai ở đây sẽ ghi đè một cái tên đang đúng bằng một cái tên của
    lớp khác, và đó là hỏng theo chiều tệ hơn cả khoá thô.
    """
    out = normalize_idx_to_label(
        {0: {"label_key": "vn/hoa_de/rang-muoi", "label_original": "rang muối",
             "label_slug": "rang-muoi", "language": "vn", "dialect": "hoa-de"}},
        label_lookup=LOOKUP, default_language="vn", default_dialect="hoa-de")
    assert out[0]["label_original"] == "rang muối"


def test_khong_co_bang_tra_thi_khong_no():
    """Thiếu `index_to_label.json` là trạng thái hợp lệ — nó bị gitignore.

    Khi ấy tên hiển thị lùi về chính khoá. Xấu, nhưng phải CHẠY: dịch vụ không
    được từ chối phục vụ chỉ vì một tệp trang trí vắng mặt.
    """
    out = normalize_idx_to_label(
        {0: "vn/alphabet/y"},
        label_lookup=None, default_language="vn", default_dialect="bang-chu-cai")
    assert out[0]["label_key"] == "vn/alphabet/y"
    assert out[0]["label_slug"] == "y"


# ---------------------------------------------------------------------------
# 4. Hai không gian tên phải khớp với DỮ LIỆU THẬT
# ---------------------------------------------------------------------------

def test_moi_lop_co_profile_deu_tra_duoc_tu_khoa_v2():
    """Với mọi lớp thật trong `labels.csv`, khoá v2 phải tra ra khoá phương ngữ.

    Đây là bài kiểm nối phép dịch với dữ liệu: hai bài trên dùng bảng tra rút
    gọn, bài này đi hết `dataset/labels.csv`. Nếu có một cặp
    (profile, dialect) mới ra đời mà phép dịch không phủ, nó đỏ ở đây.
    """
    import csv
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    labels = repo / "dataset" / "labels.csv"
    if not labels.exists():
        pytest.skip("labels.csv không có trên máy này")

    rows = [r for r in csv.DictReader(labels.open(encoding="utf-8-sig"))
            if (r.get("recognition_profile") or "").strip()
            not in ("", "legacy_unassigned")]
    if not rows:
        pytest.skip("không có lớp nào gán profile")

    tra = {}
    for r in rows:
        lang = (r.get("language") or "vn").strip()
        dialect = (r.get("dialect") or "").strip()
        slug = (r.get("slug") or "").strip()
        tra[f"{lang}/{dialect}/{slug}"] = {
            "slug": slug, "label_original": (r.get("label_original") or "").strip(),
            "language": lang, "dialect": dialect,
            "label_key": f"{lang}/{dialect}/{slug}",
        }

    truot = []
    for r in rows:
        lang = (r.get("language") or "vn").strip()
        profile = (r.get("recognition_profile") or "").strip()
        dialect = (r.get("dialect") or "").strip()
        slug = (r.get("slug") or "").strip()
        khoa_v2 = f"{lang}/{profile}/{slug}"
        got = _label_lookup_by_key(tra, khoa_v2, language=lang, dialect=dialect)
        if not got.get("label_original"):
            truot.append(khoa_v2)

    assert not truot, (
        f"{len(truot)} khoá v2 không tra ra tên lớp: {truot[:10]} — giao diện "
        f"thời gian thực sẽ hiện khoá thô cho những lớp này")
