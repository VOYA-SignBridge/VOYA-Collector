"""READ-5 ở tầng HELPER — không rơi về tenant mặc định.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_read_scope_fail_closed.py -v -s

Vì sao không đủ nếu chỉ kiểm qua HTTP
=====================================
`TenantScopeMiddleware` đặt phạm vi cho mọi request, nên một phép thử đi qua HTTP
sẽ LUÔN có phạm vi và không bao giờ chạm tới nhánh "không có phạm vi". Nhưng
đường gọi thật không chỉ có request:

    tác vụ Celery      chạy trong `system_scope`, không có request
    lệnh CLI           không có request
    tác vụ định kỳ     không có request
    mã nội bộ          gọi helper trực tiếp

Bất kỳ đường nào trong số đó gọi helper mà quên phạm vi thì phải NỔ, không được
lặng lẽ trả về dữ liệu của tenant khởi tạo.

Bẫy cụ thể đang canh
====================
`normalize_tenant_id(value, fallback=DEFAULT_TENANT_ID)` trả `"default"` cho cả
`None` lẫn `""`. Đó là hành vi ĐÚNG của nó — nó phục vụ các hàng CSV có trước khi
tenant tồn tại. Nhưng nó biến mọi phép kiểm viết SAU khi chuẩn hoá thành mã chết:

    scope = normalize_tenant_id(tenant_id)
    if not scope:          # không bao giờ đúng
        raise

`sync_reassign_sample` mắc đúng lỗi này và chỉ bị bắt bởi một ca `tenant_id=""`
ngày 16/08/2026. Các ca dưới đây tồn tại để nó không tái diễn ở helper nào khác.

Ba giá trị `None` / `""` / `"   "` được kiểm RIÊNG chứ không gộp: chúng đi qua
các nhánh khác nhau (`value is None` trả sớm; chuỗi rỗng và chuỗi trắng đi tiếp
tới `.strip()`), nên một ca đại diện có thể xanh trong khi hai ca kia hỏng.
"""

from __future__ import annotations

import pytest

from app.dataset_manager import load_labels, list_classes
from app.dataset_samples import TenantScopeRequired, find_sample, list_samples
from app.tenant_context import no_scope


#: Ba dạng "không có phạm vi" mà mã thật sự gặp.
TRONG = [None, "", "   "]


@pytest.mark.parametrize("gia_tri", TRONG)
def test_list_samples_tu_choi_pham_vi_rong(gia_tri):
    with pytest.raises(TenantScopeRequired):
        list_samples(gia_tri)


@pytest.mark.parametrize("gia_tri", TRONG)
def test_load_labels_tu_choi_pham_vi_rong(gia_tri):
    with pytest.raises(TenantScopeRequired):
        load_labels(gia_tri)


@pytest.mark.parametrize("gia_tri", TRONG)
def test_list_classes_tu_choi_pham_vi_rong(gia_tri):
    with pytest.raises(TenantScopeRequired):
        list_classes(tenant_id=gia_tri)


@pytest.mark.parametrize("gia_tri", TRONG)
def test_find_sample_tu_choi_pham_vi_rong(gia_tri):
    """`find_sample` phải nổ TRƯỚC khi tra cứu, không trả `None`.

    Trả `None` sẽ khiến người gọi đọc thành "không tìm thấy mẫu" — một câu trả
    lời nghe hợp lý cho một lượt gọi thật ra chưa bao giờ được phép chạy. Lỗi
    phải phân biệt được với sự vắng mặt.
    """
    with pytest.raises(TenantScopeRequired):
        find_sample("bat_ky_uid", gia_tri)


def test_khong_co_ngu_canh_thi_KHONG_tu_suy_ra_default():
    """Không ngữ cảnh nào được biến thành `default` một cách ngầm định.

    `no_scope()` mô phỏng đúng thứ một tác vụ nền quên đặt phạm vi sẽ thấy. Nếu
    helper tự suy ra `default`, ca này sẽ trả về dữ liệu của tenant khởi tạo và
    không ai biết.
    """
    with no_scope():
        for goi in (lambda: list_samples(None),
                    lambda: load_labels(None),
                    lambda: list_classes(tenant_id=None)):
            with pytest.raises(TenantScopeRequired):
                goi()


def test_thong_diep_loi_chi_duong_toi_helper_dung():
    """Thông điệp phải nói ra lối đi hợp lệ, nếu không người sửa sẽ nới phạm vi.

    Một lỗi chỉ nói "thiếu tenant_id" mời người đọc truyền đại một giá trị cho
    hết đỏ. Nói thẳng tên hàm không-phạm-vi dành cho bảo trì thì lựa chọn đúng
    nằm ngay trước mắt, và lựa chọn ấy có tên tự tố cáo nó là toàn cục.
    """
    with pytest.raises(TenantScopeRequired) as ei:
        list_samples("")
    assert "_load_all_samples_unscoped" in str(ei.value)

    with pytest.raises(TenantScopeRequired) as ei:
        load_labels("")
    assert "_load_all_labels_unscoped" in str(ei.value)


# --------------------------------------------------- caller: quét cây cú pháp

def _goi_khong_tham_so(ten_ham: set[str]):
    """Mọi lời gọi `ten_ham()` KHÔNG tham số trong `backend/app/`.

    Trả về [(đường dẫn tương đối, số dòng, tên hàm)].
    """
    import ast
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1] / "app"
    ket_qua = []
    for tep in sorted(goc.rglob("*.py")):
        try:
            cay = ast.parse(tep.read_text(encoding="utf-8"), filename=str(tep))
        except SyntaxError:  # pragma: no cover - tệp hỏng thì để lỗi khác bắt
            continue
        for nut in ast.walk(cay):
            if not isinstance(nut, ast.Call):
                continue
            f = nut.func
            ten = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if ten in ten_ham and not nut.args and not nut.keywords:
                ket_qua.append((tep.relative_to(goc.parent).as_posix(),
                                nut.lineno, ten))
    return ket_qua


def test_khong_noi_nao_goi_helper_co_pham_vi_ma_bo_trong_tham_so():
    """Hai ca đỏ ở trên canh HELPER; ca này canh NGƯỜI GỌI.

    `list_samples()` và `load_labels()` đều bắt buộc `tenant_id`, nên gọi chúng
    KHÔNG tham số là sai trong mọi hoàn cảnh — hoặc thiếu phạm vi, hoặc đây là
    đường bảo trì và phải gọi biến thể `_load_all_*_unscoped()`. Không có
    trường hợp thứ ba, nên luật này không có ngoại lệ hợp lệ nào để phải liệt kê.

    Vì sao cần một phép kiểm TĨNH khi đã có phép kiểm hành vi
    ---------------------------------------------------------
    Lỗi thật ngày 17/08/2026: `db.sync_missing_data_on_startup` đọc nhãn bằng
    `_load_all_labels_unscoped()` nhưng dòng NGAY DƯỚI vẫn gọi `list_samples()`
    — một nơi gọi bị bỏ sót giữa đợt chuyển sang đọc fail-closed. Đường đó chạy
    lúc khởi động, trước khi có bất kỳ phạm vi nào, nên nó ném `TenantScopeRequired`
    và đồng bộ đầu vòng đời chết.

    Ba ca kiểm thử của `test_startup_sync.py` KHÔNG bắt được, vì cả ba đều vá
    `list_samples` bằng mock — hàm thật không bao giờ chạy, chốt chặn không bao
    giờ nổ. Đó là giới hạn cố hữu của phép kiểm hành vi ở đây: thứ cần canh là
    *hàm nào được gọi*, và mock xoá đúng thông tin ấy đi.
    """
    vi_pham = _goi_khong_tham_so({"list_samples", "load_labels"})
    assert not vi_pham, (
        "gọi helper có phạm vi mà bỏ trống tham số:\n  "
        + "\n  ".join(f"{t}:{d} -> {n}()" for t, d, n in vi_pham)
        + "\nĐường bảo trì đọc toàn kho phải gọi _load_all_*_unscoped(); "
          "đường theo tổ chức phải truyền tenant_id."
    )
