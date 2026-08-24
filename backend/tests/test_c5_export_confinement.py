"""C5 — mặt phẳng tệp: gốc thư mục của tenant bootstrap là cha của mọi tenant khác.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_c5_export_confinement.py -q -s

Hình dạng của lỗi
=================
`dataset_manager.tenant_features_root` cố ý bất đối xứng:

```
default -> FEATURES_ROOT
iso_a   -> FEATURES_ROOT / "_tenants" / "iso_a"
```

Bất đối xứng ấy có lý do tốt, và docstring của nó giải thích đầy đủ: đổi bố cục
của tenant gốc thì hai mươi caller của `hierarchy_path()` phải mọc thêm nhánh
"mới-rồi-cũ", và 8.784 tệp `.npz` sẵn có nằm sau nhánh đó vĩnh viễn.

Nhưng nó tạo ra một hệ quả mà mọi hàm ĐI BỘ trên cây đều thừa hưởng:

    tenant_features_root("iso_a").is_relative_to(tenant_features_root("default"))

là ĐÚNG. Nên `root.rglob("*")` của tenant gốc quét luôn dữ liệu của mọi tenant
khác. Phạm vi vẫn được truyền đúng, hàm vẫn nhận đúng tenant — chỉ là phạm vi
của một tenant lại chứa phạm vi của những tenant còn lại.

Vì sao đây không phải "quét toàn bộ hệ tệp"
--------------------------------------------
Cách mô tả đó dẫn tới bản vá sai. Không có caller nào thiếu tham số tenant, và
thêm tham số tenant vào chúng sẽ không sửa được gì cả. Cái sai nằm ở phép bao
hàm giữa hai thư mục, không nằm ở việc truyền phạm vi.

Ba caller đi bộ trên cây, guard chỉ có ở một
---------------------------------------------
```
_remove_tenant_files  (xoá)     CÓ guard, kèm docstring nêu đúng vấn đề này
_add_feature_files    (export)  KHÔNG  -> đọc chéo tổ chức
tenant_storage_mb     (kế toán) KHÔNG  -> số byte của `default` cộng cả người khác
```

Sự bất đối xứng đã được hiểu, và chỉ được chặn ở đường phá huỷ. Đó là lý do các
ca dưới đây đo cả ba đường chứ không riêng đường export: một guard viết ở một
chỗ là một guard sẽ bị quên ở chỗ thứ tư.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import dataset_manager, tenant_lifecycle  # noqa: E402

A = "iso_a"
B = "iso_b"
GOC = "default"


MB = 1024 * 1024
CO_GOC, CO_A, CO_B = 1 * MB, 3 * MB, 3 * MB


def _tao(path: Path, co: int) -> None:
    """Tệp thưa: `st_size` báo đủ `co` byte mà đĩa không thực sự ghi ngần ấy.

    `tenant_storage_mb` chia cho 1024², nên ca C5-5 cần cỡ MB mới phân biệt được
    tổ chức này với tổ chức kia. Ghi 7 MB thật vào thư mục tạm chỉ để so hai số
    nguyên là lãng phí; `truncate` cho đúng con số mà phép đo đọc.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(co)


@pytest.fixture
def cay_gia(tmp_path, monkeypatch):
    """Cây `features/` giả, mô phỏng bố cục thật: gốc phẳng + `_tenants/` bên trong.

    KHÔNG dùng `dataset/` thật. Ràng buộc thường trực của đợt này là không chạm
    dữ liệu phương ngữ có sẵn, và một bài đo ghi vào kho thật sẽ vi phạm điều đó
    ngay cả khi nó chỉ đọc — vì `_remove_tenant_files` trong ca C5-4 có xoá.
    """
    goc = tmp_path / "features"

    # Tenant gốc: bố cục lịch sử, nằm thẳng ở gốc.
    _tao(goc / "vn" / "common" / "class_0001_cam-on" / "sample_goc.npz", CO_GOC)

    # Hai tenant khác: nằm dưới `_tenants/`, tức là BÊN TRONG gốc ở trên.
    for t, co in ((A, CO_A), (B, CO_B)):
        _tao(goc / "_tenants" / t / "vn" / "common" / "class_0001_cam-on"
             / f"sample_{t}.npz", co)

    monkeypatch.setattr(dataset_manager, "FEATURES_ROOT", goc)
    return goc


def _ten_trong_zip(tenant: str, dich: Path,
                   muc_dich: str = tenant_lifecycle.EXPORT_PURPOSE_PORTABILITY) -> list:
    with zipfile.ZipFile(dich, "w") as bundle:
        tenant_lifecycle._add_feature_files(bundle, tenant, export_purpose=muc_dich)
    with zipfile.ZipFile(dich) as bundle:
        return sorted(bundle.namelist())


# --------------------------------------------------------------- C5-1 cấu trúc

def test_c5_1_goc_cua_tenant_khac_nam_trong_goc_cua_bootstrap(cay_gia):
    """Sự thật cấu trúc, có chủ ý — ca này chốt nó để bản vá không xoá nhầm.

    Nếu ai đó sau này "sửa" bằng cách đưa `default` xuống `_tenants/default/`,
    ca này đỏ và buộc người sửa đọc docstring của `tenant_features_root` trước.
    Bản vá đúng cho C5 KHÔNG đụng vào phép ánh xạ này.
    """
    r_goc = dataset_manager.tenant_features_root(GOC)
    r_a = dataset_manager.tenant_features_root(A)
    assert r_goc == cay_gia
    assert r_a.is_relative_to(r_goc), (
        "bố cục đã đổi — C5 được viết cho bố cục lồng nhau, hãy đọc lại trước khi sửa")


# ------------------------------------------------------------- C5-2 export ★

def test_c5_2_export_cua_bootstrap_KHONG_duoc_chua_tep_cua_tenant_khac(cay_gia, tmp_path):
    """★ Ca trung tâm. Đỏ ở đây = rò rỉ đọc chéo tổ chức trên endpoint đang sống.

    Đường đi: POST /api/tenants/default/exports?scope=full
              -> require_tenant_admin('default')     (quản trị tenant gốc là ĐỦ)
              -> run_export -> _add_feature_files(bundle, 'default')
              -> FEATURES_ROOT.rglob('*')            -> nuốt cả `_tenants/*`
              -> GET .../download                    -> zip tên `default-export.zip`

    Không cần quyền vận hành nền tảng, không cần đoán id, không cần lỗi phụ nào.
    """
    ten = _ten_trong_zip(GOC, tmp_path / "goc.zip")
    ro_ri = [n for n in ten if "_tenants/" in n]
    print(f"\n[evidence] zip cua `{GOC}` co {len(ten)} muc, {len(ro_ri)} thuoc tenant khac")
    for n in ro_ri:
        print(f"           RO RI: {n}")
    assert ro_ri == [], (
        f"gói xuất của tenant gốc chứa {len(ro_ri)} tệp của tổ chức khác: {ro_ri}")


def test_c5_2b_export_cua_bootstrap_van_phai_co_tep_cua_chinh_no(cay_gia, tmp_path):
    """Chốt hiệu lực. "Không rò rỉ" một mình cũng đúng với một bản vá xuất ra zip rỗng."""
    ten = _ten_trong_zip(GOC, tmp_path / "goc.zip")
    assert any("sample_goc.npz" in n for n in ten), (
        "vá quá tay: tenant gốc không xuất được dữ liệu của chính mình")


def test_c5_3_export_cua_tenant_thuong_van_kin(cay_gia, tmp_path):
    """Hướng ngược lại đã kín sẵn — ca này giữ cho nó kín sau bản vá."""
    ten = _ten_trong_zip(A, tmp_path / "a.zip")
    la = [n for n in ten if f"sample_{B}" in n or "sample_goc" in n]
    print(f"\n[evidence] zip cua `{A}`: {ten}")
    assert la == [], f"gói xuất của {A} chứa dữ liệu lạ: {la}"
    assert any(f"sample_{A}.npz" in n for n in ten)


# ---------------------------------------------------------------- C5-4 xoá

def test_c5_4_duong_xoa_da_co_guard(cay_gia):
    """Đường phá huỷ ĐÃ được chặn từ trước — ca này ghi lại bằng chứng đó.

    Giá trị của ca này không phải là bắt lỗi. Nó ghi rằng cùng một sự bất đối
    xứng đã được nhận ra ở đường xoá và không được mang sang đường đọc; đó là
    lập luận cho việc bản vá phải là MỘT helper dùng chung, chứ không phải hai
    câu `if` chép ở hai nơi và chờ một nơi thứ ba quên.
    """
    n, byte = tenant_lifecycle._remove_tenant_files(GOC)
    assert (n, byte) == (0, 0)
    assert (cay_gia / "_tenants" / A).exists(), "xoá tenant gốc đã cuốn theo tenant khác"
    assert (cay_gia / "vn").exists(), "guard đúng nhưng đã xoá dữ liệu của chính tenant gốc"


# ------------------------------------------------------------- C5-5 kế toán

def test_c5_5_ke_toan_dung_luong_KHONG_duoc_cong_byte_cua_nguoi_khac(cay_gia, monkeypatch):
    """Không phải rò rỉ, nhưng là một con số SAI đi thẳng vào hoá đơn.

    `tenant_storage_mb` nạp `tenants` từ CSDL. Ở đây ta thay bằng danh sách cố
    định: bài đo này hỏi về phép đi bộ trên thư mục, không hỏi về CSDL, và kéo
    theo một CSDL thật sẽ làm ca đỏ vì lý do không liên quan.
    """
    from app import usage
    from app.storage import metadata_db

    # Vá vào `metadata_db`, KHÔNG vào `usage`: `tenant_storage_mb` nhập
    # `_fetch_all` bên trong thân hàm, nên tên đó được tra cứu ở module nguồn
    # tại thời điểm gọi. Đặt một thuộc tính cùng tên lên `usage` sẽ không bao
    # giờ được nhìn tới, và ca này sẽ "xanh" trong khi đo danh sách tenant thật
    # của CSDL kiểm thử — một ca xanh không đo gì cả.
    monkeypatch.setattr(
        metadata_db, "_fetch_all",
        lambda *a, **k: [{"tenant_id": GOC}, {"tenant_id": A}, {"tenant_id": B}])

    so = usage.tenant_storage_mb()

    print(f"\n[evidence] MB theo tenant: {so} (dat: {GOC}=1, {A}=3, {B}=3)")
    assert so.get(A) == CO_A // MB and so.get(B) == CO_B // MB, (
        "phép đo hỏng ở chỗ khác — hai tenant thường đã sai số trước khi xét tenant gốc")
    assert so.get(GOC) == CO_GOC // MB, (
        f"dung lượng của tenant gốc là {so.get(GOC)} MB thay vì {CO_GOC // MB} MB: "
        f"phép đi bộ đã cộng cả byte của tổ chức khác")


# ============================================================================
# C5-7..C5-13 — mục đích của gói quyết định cổng đồng thuận
# ============================================================================
#
# `scope` nói CÁI GÌ nằm trong gói. `export_purpose` nói gói dựng ĐỂ LÀM GÌ.
# Bản trước chỉ có vế đầu, nên cùng một endpoint vừa hoàn trả dữ liệu cho tổ
# chức vừa có thể phát hành nó — và cổng đồng thuận không biết mình gác cái nào.
#
# Chính sách:
#
# ```
# tenant_portability   ĐƯA ĐỦ + đánh dấu hạn chế   | đủ tư cách làm điều kiện purge
# internal_training  ┐
# research_release   ├ LỌC fail-closed theo thang  | KHÔNG đủ tư cách làm purge
# public_library     ┘
# ```
#
# Vì sao gói phát hành không được làm điều kiện trước khi xoá: nó ĐÃ bị lọc, nên
# nó không phải bản sao dữ liệu của tổ chức. Nhận nó rồi cho xoá vĩnh viễn nghĩa
# là phần bị lọc biến mất mà chưa từng được hoàn trả — và phần dễ mất nhất theo
# đường đó đúng là mẫu của người đã rút đồng thuận.


@pytest.fixture
def dong_thuan_gia(monkeypatch, cay_gia):
    """Hai người ký: một người còn hiệu lực tới `research_release`, một người đã rút.

    Vá `load_consents` và `_resolve_aliases` chứ không dựng dữ liệu thật: các ca
    này hỏi về CHÍNH SÁCH nối giữa mục đích và cổng, không hỏi về cách đọc bảng
    `signer_consents` — phần đó đã có bộ đo riêng.
    """
    from app import consent_gate, dataset_samples

    thang = consent_gate.scope_rank("research_release")
    monkeypatch.setattr(consent_gate, "load_consents", lambda *a, **k: {
        "signer-ok": consent_gate.SignerConsent(highest_live_rank=thang, has_any_record=True),
        "signer-rut": consent_gate.SignerConsent(highest_live_rank=None, has_any_record=True),
    })
    monkeypatch.setattr(consent_gate, "_resolve_aliases", lambda *a, **k: {})

    # Hai tệp có hàng mẫu, một tệp KHÔNG có hàng nào (mồ côi trên đĩa).
    goc_a = cay_gia / "_tenants" / A / "vn" / "common" / "class_0001_cam-on"
    _tao(goc_a / "sample_ok.npz", MB)
    _tao(goc_a / "sample_rut.npz", MB)
    _tao(goc_a / "sample_mo_coi.npz", MB)

    # `review_status` phai co: hai dong nay mo hinh hoa mot kho DANG DUNG DUOC.
    #
    # Cong kiem duyet doc o rong thanh "chua duyet" (co y — im lang nghia la
    # chua biet), nen bo cot di thi ca hai dong bi loai va bai test do vi mot ly
    # do chang lien quan gi toi dieu no dang kiem: dong thuan.
    monkeypatch.setattr(dataset_samples, "list_samples", lambda *a, **k: [
        {"sample_uid": "ok", "signer_id": "signer-ok", "file_path": "x/sample_ok.npz",
         "review_status": "approved"},
        {"sample_uid": "rut", "signer_id": "signer-rut", "file_path": "x/sample_rut.npz",
         "review_status": "approved"},
    ])
    return cay_gia


def _ten_tep(ten_muc: list) -> set:
    return {n.rsplit("/", 1)[-1] for n in ten_muc if n.startswith("files/")}


def test_c5_7_hoan_tra_dua_du_va_danh_dau_phan_bi_han_che(dong_thuan_gia, tmp_path):
    """Gói hoàn trả KHÔNG lọc — nhưng cũng không giao dữ liệu đã rút đi trần."""
    dich = tmp_path / "port.zip"
    with zipfile.ZipFile(dich, "w") as bundle:
        so, ban_ke = tenant_lifecycle._add_feature_files(
            bundle, A, export_purpose=tenant_lifecycle.EXPORT_PURPOSE_PORTABILITY)
    with zipfile.ZipFile(dich) as bundle:
        ten = _ten_tep(bundle.namelist())

    print(f"\n[evidence] hoan tra: {sorted(ten)}")
    print(f"[evidence] ban ke han che: {ban_ke.get('so_tep_bi_han_che')} tep")
    assert "sample_rut.npz" in ten, "gói hoàn trả đã lọc mất dữ liệu của chính tổ chức"
    assert "sample_ok.npz" in ten and "sample_mo_coi.npz" in ten
    assert ban_ke["so_tep_bi_han_che"] == 1
    assert any("sample_rut.npz" in t for t in ban_ke["tep_bi_han_che"])
    assert "han_che_su_dung" in ban_ke


def test_c5_8_phat_hanh_loai_mau_da_rut_dong_thuan(dong_thuan_gia, tmp_path):
    """★ Nửa còn lại. Cùng dữ liệu, khác mục đích, khác kết quả."""
    dich = tmp_path / "rel.zip"
    with zipfile.ZipFile(dich, "w") as bundle:
        so, ban_ke = tenant_lifecycle._add_feature_files(
            bundle, A, export_purpose="research_release")
    with zipfile.ZipFile(dich) as bundle:
        ten = _ten_tep(bundle.namelist())

    print(f"\n[evidence] phat hanh: {sorted(ten)}")
    print(f"[evidence] ban ke: {ban_ke}")
    assert "sample_rut.npz" not in ten, "mẫu đã rút đồng thuận lọt vào gói phát hành"
    assert "sample_ok.npz" in ten, "lọc quá tay: mẫu đủ điều kiện cũng bị loại"


def test_c5_9_phat_hanh_loai_ca_tep_khong_xac_dinh_duoc_nguoi_ky(dong_thuan_gia, tmp_path):
    """Fail-closed. Một tệp trên đĩa không khớp hàng mẫu nào thì không có đồng
    thuận nào để dựa vào, và "không biết" ở cổng phát hành phải nghĩa là KHÔNG.

    Cùng lập luận với `consent_gate._signer_of` khi nó từ chối lùi về `user_id`:
    thà coi là không phát hành được, còn hơn quy kết đồng thuận cho nhầm người.
    """
    dich = tmp_path / "rel.zip"
    with zipfile.ZipFile(dich, "w") as bundle:
        so, ban_ke = tenant_lifecycle._add_feature_files(
            bundle, A, export_purpose="public_library")
    with zipfile.ZipFile(dich) as bundle:
        ten = _ten_tep(bundle.namelist())

    print(f"\n[evidence] mo coi bi loai: {ban_ke.get('loai_vi_khong_xac_dinh_nguoi_ky')}")
    assert "sample_mo_coi.npz" not in ten
    assert ban_ke["loai_vi_khong_xac_dinh_nguoi_ky"] >= 1


def test_c5_10_ban_ke_phat_hanh_du_de_kiem_lai(dong_thuan_gia, tmp_path):
    """Bản kê phải nằm TRONG gói, không chỉ trong nhật ký máy chủ.

    Sáu tháng sau, một gói đã lọc và một gói đầy đủ trông giống hệt nhau nếu
    không có tệp này.
    """
    with zipfile.ZipFile(tmp_path / "rel.zip", "w") as bundle:
        so, ban_ke = tenant_lifecycle._add_feature_files(
            bundle, A, export_purpose="research_release")
    for khoa in ("export_purpose", "thoi_diem", "tong_mau_xet", "so_tep_dua_vao",
                 "muc_dong_thuan_yeu_cau", "loai_vi_dong_thuan",
                 "loai_vi_khong_xac_dinh_nguoi_ky", "ly_do", "tom_tat"):
        assert khoa in ban_ke, f"bản kê thiếu `{khoa}`"


def test_c5_11_quen_khai_muc_dich_la_loi_ngay_tai_cho():
    """Tham số bắt buộc, không mặc định — quên là `TypeError`, không phải im lặng.

    Cùng khuôn với `resolve_operational(..., *, tenant_id)`: một guard có giá trị
    mặc định là một guard sẽ có ngày không ai gọi tới mà vẫn xanh.
    """
    with pytest.raises(TypeError):
        tenant_lifecycle.request_export("iso_a")  # type: ignore[call-arg]


def test_c5_12_muc_dich_la_bi_tu_choi_422():
    with pytest.raises(tenant_lifecycle.LifecycleError) as e:
        tenant_lifecycle.request_export("iso_a", export_purpose="cho_vui")
    assert e.value.status_code == 422


# ------------------------------------------------------- C5-6 chốt chặn tĩnh

def test_c5_6_khong_caller_nao_duoc_tu_di_bo_tren_goc_tenant():
    """Caller THỨ TƯ. Ba caller đầu không phải kết thúc của vấn đề này.

    Hai ca ở trên đo hai caller đã biết. Nhưng cái sai không nằm ở hai hàm đó,
    nó nằm ở chỗ `tenant_features_root(x).rglob(...)` ĐỌC RẤT ĐÚNG mà lại sai —
    và bất kỳ ai viết caller mới cũng sẽ viết đúng câu đó, vì nó là câu hiển
    nhiên. Ca này bắt câu đó ở mức văn bản mã nguồn.

    Phép đo hành vi không thay được ca này: một caller chưa tồn tại thì không có
    hành vi để đo. Đây là loại chốt duy nhất chạy trước khi lỗi kịp sinh ra.

    Hai giới hạn, nói thẳng:

    1. Chỉ bắt hình dạng viết liền một dòng. Ai đó gán
       `r = tenant_features_root(t)` rồi `r.rglob()` ở dòng khác vẫn lọt.
    2. Bỏ qua dòng chú thích — vì lượt chạy đầu tiên nó bắt đúng câu
       `# KHÔNG tenant_features_root(tenant).rglob('*')` trong chính bản vá,
       tức là một dòng viết ra để CẤM đúng việc đó. Một công cụ đối chiếu văn
       bản không phân biệt được lệnh với lời cảnh báo về lệnh.

    Đổi lại: không âm tính giả trên hình dạng phổ biến, và không cần chạy gì.
    """
    import re

    app_dir = REPO_ROOT / "backend" / "app"
    mau = re.compile(
        r"(tenant_features_root|ambient_tenant_features_root)\([^)]*\)\s*\.\s*(rglob|glob|iterdir|walk)")
    vi_pham = []
    for tep in app_dir.rglob("*.py"):
        try:
            noi_dung = tep.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, dong in enumerate(noi_dung.splitlines(), 1):
            if dong.lstrip().startswith("#"):
                continue
            if mau.search(dong):
                vi_pham.append(f"{tep.relative_to(REPO_ROOT).as_posix()}:{i}: {dong.strip()}")

    assert vi_pham == [], (
        "đi bộ thẳng trên gốc thư mục của tenant — với tenant gốc, gốc đó chứa "
        "thư mục của mọi tenant khác. Dùng `dataset_manager.iter_tenant_feature_files`:\n  "
        + "\n  ".join(vi_pham))
