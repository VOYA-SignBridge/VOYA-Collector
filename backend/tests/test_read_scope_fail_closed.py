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
