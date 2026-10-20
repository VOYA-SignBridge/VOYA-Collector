"""Cưỡng chế ranh giới tenant trên MẶT PHẲNG LƯU TRỮ THỨ HAI (CSV + tệp).

Vì sao tệp này tồn tại
======================
RLS bảo vệ PostgreSQL. Nó không biết gì về `labels.csv` và `samples.csv`. Ngày
15/08/2026, phép đo cách ly đo được:

    iso_user_a (tenant iso_a) -> GET /api/v1/classes/<lớp của iso_b>/sessions
    HTTP 200, kèm label_original, session_id, sample_uid của iso_b

Bản vá đặt cổng ở HAI HÀM LÁ: `load_labels()` và `list_samples()` giờ đòi
`tenant_id` và ném `TenantScopeRequired` thay vì trả toàn kho. Nhưng một cổng ở
hàm lá chỉ có giá trị bằng danh sách người được phép đi vòng qua nó — nếu bất kỳ
đường request nào còn gọi biến thể `_unscoped`, lỗ hổng quay lại nguyên vẹn và
không ai biết.

Đó là việc của tệp này: biến "lập trình viên không được dùng `_unscoped`" từ một
quy ước thành một phép kiểm chạy được.

Ba mặt phẳng, ba luật
=====================
    A. Tenant-scoped   đường nghiệp vụ. PHẢI có tenant_id. Không có đường lùi.
    B. Community       mặt phẳng ngoại lệ ĐÃ CÔNG BỐ TƯỜNG MINH.
                       KHÔNG phải "đọc toàn bộ rồi cộng lại".
    C. System/bảo trì  mới được đọc rộng, và phải nêu lý do.

Luật B là luật hay bị hiểu nhầm nhất. `community` không phải một cửa sổ nhìn
xuyên mọi tenant. Một tài nguyên chỉ thuộc mặt phẳng community SAU một chuyển
tiếp tường minh (publish/contribute/approval). Cộng gộp toàn kho rồi trả về một
con số vẫn là vi phạm: request công khai đã đọc được tập riêng tư của mọi tenant
TRƯỚC khi cộng, và con số kết quả trở thành oracle để suy ra sự tồn tại và quy mô
của từng tenant.

Về các phép kiểm `xfail(strict=True)`
=====================================
Một số luật dưới đây MÔ TẢ HỢP ĐỒNG MONG MUỐN chứ chưa mô tả mã hiện tại. Chúng
được đánh dấu `xfail(strict=True)` kèm lý do, chứ KHÔNG bị nới lỏng cho xanh.

`strict=True` là phần quan trọng: khi caller được chuyển xong, phép kiểm bắt đầu
đạt, và pytest sẽ BÁO ĐỎ vì một `xfail` lại đạt. Nghĩa là không ai có thể sửa
xong mà quên gỡ đánh dấu, và không có luật nào lặng lẽ nằm mãi ở trạng thái
"sẽ làm sau".
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

#: Đường ĐỒNG BỘ / BẢO TRÌ được phép đọc toàn kho. Danh sách này là hợp đồng —
#: thêm tên vào đây là một quyết định kiến trúc, không phải một lần sửa cho xanh.
#:
#: Tiêu chí: thao tác chiếu CSV sang Postgres, đồng bộ danh mục, kiểm toàn vẹn,
#: sửa chữa quản trị. KHÔNG bao giờ là một đường phục vụ request của người dùng.
MODULE_BAO_TRI = {
    "catalog_sync.py",
    "db.py",
    "export_tasks.py",
    "balancer.py",
    "oversample_balance.py",
    "global_common_promoter.py",
    "dialect_mapping_reclassifier.py",
    "inference_loader.py",
    "validation/dataset_validator.py",
}

#: Đường REQUEST: mọi thứ phục vụ một lượt gọi HTTP. Đây là nơi thiếu tenant
#: context là một lỗ hổng, không phải một sự bất tiện.
DUONG_REQUEST = ("routers", "preview_render.py")

#: Hàm đọc toàn kho, không lọc tenant.
HAM_TOAN_KHO = ("_load_all_labels_unscoped", "_load_all_samples_unscoped")

#: Hàm nghiệp vụ đòi tenant_id.
HAM_CO_PHAM_VI = ("load_labels", "list_samples", "list_classes")


def _tep_python() -> list[Path]:
    return [p for p in APP.rglob("*.py") if "__pycache__" not in str(p)]


def _la_duong_request(p: Path) -> bool:
    rel = p.relative_to(APP).as_posix()
    return any(rel.startswith(d) or rel == d for d in DUONG_REQUEST)


def _goi_khong_tham_so(path: Path, ten_ham: tuple[str, ...]) -> list[tuple[str, int]]:
    """Các lần gọi `f()` KHÔNG truyền đối số nào — tức không truyền tenant_id.

    Dùng AST chứ không dùng regex: `list_samples()` và `list_samples(tenant_id=x)`
    khác nhau ở đúng chỗ quan trọng, và một phép quét theo dòng đã từng đếm nhầm
    trong kho này (212 nút không có `type` hoá ra là 0).
    """
    try:
        cay = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover
        return []
    ra = []
    for node in ast.walk(cay):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        ten = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        if ten in ten_ham and not node.args and not node.keywords:
            ra.append((ten, node.lineno))
    return ra


# --------------------------------------------------------------------------
# A. Mặt phẳng riêng tư — hàm lá phải fail-closed
# --------------------------------------------------------------------------

def test_load_labels_khong_co_tenant_thi_nem_loi():
    """Thiếu ngữ cảnh phải là LỖI, không phải "trả toàn bộ"."""
    from app.dataset_manager import load_labels
    from app.dataset_samples import TenantScopeRequired

    with pytest.raises(TenantScopeRequired):
        load_labels()


def test_list_samples_khong_co_tenant_thi_nem_loi():
    from app.dataset_samples import TenantScopeRequired, list_samples

    with pytest.raises(TenantScopeRequired):
        list_samples()


def test_chuoi_rong_khong_phai_duong_lui():
    """`""` và `"   "` không được coi là "toàn cục", và cũng không rơi về `default`.

    Nếu chuỗi rỗng lọt qua thì mọi caller quên truyền tenant sẽ im lặng đọc kho
    của tenant gốc, và `default` trở thành một super-tenant ngầm.
    """
    from app.dataset_manager import load_labels
    from app.dataset_samples import TenantScopeRequired, list_samples

    for gia_tri in ("", "   ", None):
        with pytest.raises(TenantScopeRequired):
            load_labels(gia_tri)
        with pytest.raises(TenantScopeRequired):
            list_samples(gia_tri)


def test_ham_toan_kho_van_ton_tai_va_ten_van_xau():
    """Tên `_load_all_*_unscoped` là một phần của bản vá, không phải chi tiết.

    Đổi nó thành một cái tên vô hại là gỡ mất tín hiệu mà người duyệt mã dựa vào.
    """
    import app.dataset_manager as dm
    import app.dataset_samples as ds

    assert callable(dm._load_all_labels_unscoped)
    assert callable(ds._load_all_samples_unscoped)


# --------------------------------------------------------------------------
# B. Danh sách caller — cổng ở hàm lá chỉ mạnh bằng danh sách đi vòng
# --------------------------------------------------------------------------

def test_chi_duong_bao_tri_moi_duoc_doc_toan_kho():
    """`_load_all_*_unscoped()` KHÔNG được xuất hiện trên đường request."""
    vi_pham = []
    for p in _tep_python():
        if not _la_duong_request(p):
            continue
        src = p.read_text(encoding="utf-8")
        for ten in HAM_TOAN_KHO:
            for m in re.finditer(rf"\b{ten}\s*\(", src):
                dong = src[: m.start()].count("\n") + 1
                vi_pham.append(f"{p.relative_to(APP).as_posix()}:{dong} {ten}()")
    assert not vi_pham, (
        "Doc toan kho tren duong request — RLS khong phu CSV, day la lo hong:\n  "
        + "\n  ".join(vi_pham))


def test_module_bao_tri_khong_tu_moc_them():
    """Ai đọc toàn kho phải nằm trong danh sách đã duyệt.

    Phép kiểm này không chặn việc mở rộng — nó chặn việc mở rộng IM LẶNG.
    """
    ngoai_danh_sach = []
    for p in _tep_python():
        rel = p.relative_to(APP).as_posix()
        if rel in MODULE_BAO_TRI or p.name in MODULE_BAO_TRI:
            continue
        if p.name in ("dataset_manager.py", "dataset_samples.py"):
            continue  # nơi định nghĩa
        src = p.read_text(encoding="utf-8")
        for ten in HAM_TOAN_KHO:
            if re.search(rf"\b{ten}\s*\(", src):
                ngoai_danh_sach.append(f"{rel} goi {ten}()")
    assert not ngoai_danh_sach, (
        "Module ngoai danh sach bao tri dang doc toan kho. Neu that su can, "
        "them vao MODULE_BAO_TRI kem ly do:\n  " + "\n  ".join(ngoai_danh_sach))


def test_duong_request_luon_truyen_tenant():
    """Mọi lần gọi hàm nghiệp vụ trên đường request phải kèm tenant.

    Phép kiểm này từng mang `xfail(strict=True)` trong suốt đợt di trú caller
    ngày 16/08. Nó đi từ 9 điểm gọi thiếu ngữ cảnh xuống 0, và `strict` là phần
    quan trọng: khi điểm cuối cùng được sửa, một `xfail` lại đạt sẽ làm bộ test
    BÁO ĐỎ, buộc phải gỡ đánh dấu ngay trong cùng thay đổi. Nhờ vậy không có
    luật nào lặng lẽ nằm mãi ở trạng thái "sẽ làm sau".

    Giữ nguyên phép kiểm này sau khi di trú xong: nó là hàng rào chặn một caller
    mới thiếu ngữ cảnh lọt vào đường request về sau.
    """
    thieu = []
    for p in _tep_python():
        if not _la_duong_request(p):
            continue
        for ten, dong in _goi_khong_tham_so(p, HAM_CO_PHAM_VI):
            thieu.append(f"{p.relative_to(APP).as_posix()}:{dong} {ten}()")
    assert not thieu, "Goi khong co tenant tren duong request:\n  " + "\n  ".join(thieu)


# --------------------------------------------------------------------------
# C. Mặt phẳng community — ngoại lệ ĐÃ CÔNG BỐ, không phải view toàn cục
# --------------------------------------------------------------------------

def test_community_plane_that_su_ton_tai():
    """Có một mặt phẳng community thật để mà đi qua.

    Nếu phép kiểm này hỏng thì các luật community bên dưới đang mô tả một thứ
    không tồn tại, và câu trả lời đúng là ghi lệch phạm vi — không phải dựng vội
    một implementation để test đi qua.
    """
    from app.authorization.catalog import COMMUNITY

    assert COMMUNITY == "COMMUNITY"


# Hợp đồng của `community_stats` đã được ba phép kiểm ở trên phủ theo cấu trúc
# (`..._doc_tenant_cong_khai_tuong_minh`, `..._khong_co_duong_lui`,
# `..._chi_tra_dai_luong_tong_hop`). Bản cũ ở đây làm cùng việc bằng cách CẮT
# CHUỖI và đã bị bỏ.
#
# Phần còn thiếu là ĐỐI CHỨNG HAI CHIỀU theo HÀNH VI, và nó KHÔNG thuộc bộ test
# này:
#
#     đổi dữ liệu riêng của A/B   ->  aggregate KHÔNG đổi
#     đổi dữ liệu Community       ->  aggregate CÓ đổi
#
# Vế thứ hai là bắt buộc: chỉ có vế đầu thì một endpoint luôn trả 0 cũng "đạt".
# Nhưng phép kiểm ấy phải GHI dữ liệu vào cả PostgreSQL lẫn `labels.csv`, mà bộ
# test này chạy trên kho tệp thật — đúng cái bẫy "test ghi vào CSV thật" đã gặp.
# Nên nó thuộc lớp 3 của P0-B, chạy trên cây fixture dùng-một-lần:
# xem `PROPOSAL_COMMITMENT_TRACEABILITY.md` §9.


def test_community_stats_chi_tra_dai_luong_tong_hop():
    """Không có capability lần ngược từ mặt phẳng công khai vào tenant.

    Luật đúng là **ngữ nghĩa**, không phải cấm chạm định danh một cách máy móc.
    Đọc `user_id` để ĐẾM số người đóng góp *trong phạm vi Community* là hợp lệ —
    đó là dữ liệu của chính mặt phẳng ấy. Cái không được phép là để định danh
    **thoát ra phản hồi**, vì khi đó một giá trị công khai trở thành đầu mối
    truy ngược vào namespace riêng của tenant nguồn.

    Nên phép kiểm đặt ở ĐẦU RA: mọi giá trị trả về phải là đại lượng tổng hợp.
    """
    than = _than_community_stats()
    for node in ast.walk(ast.parse(than)):
        if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)):
            continue
        for khoa, gia_tri in zip(node.value.keys, node.value.values):
            ten = khoa.value if isinstance(khoa, ast.Constant) else "?"
            # Chỉ chấp nhận `len(...)`, hằng số, hoặc phép đếm — không chấp nhận
            # một định danh hay một tập định danh đi thẳng ra ngoài.
            ok = (isinstance(gia_tri, ast.Constant)
                  or (isinstance(gia_tri, ast.Call)
                      and isinstance(gia_tri.func, ast.Name)
                      and gia_tri.func.id in ("len", "int", "sum")))
            assert ok, (
                f"community_stats tra '{ten}' khong phai dai luong tong hop — "
                "dinh danh khong duoc thoat ra phan hoi cong khai")


def _than_community_stats() -> str:
    """Thân hàm `community_stats`, cắt bằng AST chứ không bằng `str.index`.

    Bản đầu cắt chuỗi bằng `than.index("return {")` và bắt nhầm — docstring của
    hàm chứa chữ "Returns", còn thân hàm có hai câu `return` (một câu thoát sớm).
    Cùng loại lỗi với phép quét `<button` theo dòng từng đếm 212 nút thiếu
    `type` trong khi con số thật là 0.
    """
    src = (APP / "routers" / "classes.py").read_text(encoding="utf-8")
    cay = ast.parse(src)
    for node in ast.walk(cay):
        if isinstance(node, ast.FunctionDef) and node.name == "community_stats":
            return ast.get_source_segment(src, node) or ""
    raise AssertionError("khong tim thay community_stats")


def test_community_stats_doc_tenant_cong_khai_tuong_minh():
    """Hợp đồng: đọc **tenant công khai tường minh**, không phải ai khác.

    Ba đường sai, cả ba đều từng tồn tại hoặc suýt tồn tại::

        toàn kho unscoped   -> rò quy mô MỌI tổ chức qua một con số tổng
        phạm vi người gọi   -> tên là "community" nhưng số là của riêng tenant,
                               và với request ẩn danh thì `require_tenant()` ném
        tenant công khai    -> ĐÚNG

    Hệ quả kiểm được: thêm dữ liệu vào một tenant riêng KHÔNG làm bốn con số này
    đổi; thêm vào danh mục công khai thì có.
    """
    than = _than_community_stats()
    assert "settings.public_tenant_id" in than, (
        "community_stats phai lay pham vi tu tenant cong khai tuong minh")
    for cam in ("require_tenant(", "current_tenant("):
        assert cam not in than, (
            f"community_stats dung {cam} — do la pham vi NGUOI GOI, khong phai "
            "mat phang cong khai; va voi request an danh thi no nem loi")


def test_community_stats_khong_co_duong_lui():
    """Không có tenant công khai thì trả 0, KHÔNG rơi về người gọi hay toàn kho.

    Đây là chỗ một đường lùi "hợp lý" sẽ lặng lẽ mở lại đúng lỗ vừa bịt.
    """
    than = _than_community_stats()
    for ten in HAM_TOAN_KHO:
        assert ten not in than, f"community_stats goi {ten}() — doc toan kho"
    for ten in HAM_CO_PHAM_VI:
        assert f"{ten}()" not in than, f"community_stats goi {ten}() khong pham vi"


def test_endpoint_cong_khai_khong_tra_dinh_danh_noi_bo():
    """Không có capability quay ngược từ mặt phẳng công khai vào tenant.

    Phản hồi công khai không được mang `tenant_id`, khoá lưu trữ hay đường dẫn
    nội bộ — biết một giá trị công khai không được giúp truy cập namespace riêng
    tư của tenant nguồn.
    """
    than = _than_community_stats()
    # Lấy các câu `return` bằng AST: cắt chuỗi từ `"return {"` bắt nhầm chữ
    # "Returns" trong docstring, và hàm này có HAI câu return.
    khoa: list[str] = []
    for node in ast.walk(ast.parse(than)):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            khoa += [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    assert khoa, "khong doc duoc khoa cua phan hoi community_stats"
    for cam in ("tenant_id", "workspace_id", "project_id", "storage_key",
                "file_path", "storage_url", "sample_uid", "class_uid"):
        assert cam not in khoa, (
            f"phan hoi cong khai lo '{cam}' — dinh danh noi bo khong duoc "
            "xuat hien o mat phang community")
