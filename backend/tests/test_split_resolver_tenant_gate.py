"""C2c — resolver cưỡng chế quyền sở hữu hiện vật chia dữ liệu.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_split_resolver_tenant_gate.py -v -s

Bất biến
========
```
operational + owned + chủ == người hỏi   ->  TRẢ VỀ
operational + owned + chủ != người hỏi   ->  TỪ CHỐI, giống hệt "không tồn tại"
operational + unknown                    ->  TỪ CHỐI (fail-closed)
research    + not_applicable             ->  hợp đồng riêng, KHÔNG áp luật chủ
```

Vì sao ba trạng thái ở C2b là điều kiện cần cho tệp này
=======================================================
Nếu chủ sở hữu chỉ là `Optional[str]` thì `None` của nghiên cứu và `None` của
một hiện vật vận hành mất chủ trông y hệt nhau ở đây. Hai cách xử đúng lại trái
ngược — một cái phải cho qua, một cái phải chặn — nên người viết sẽ phải chọn
một, và lựa chọn "xử như nhau" duy nhất còn khả thi là CHO QUA. Đó chính là con
bug mà `owner_state` sinh ra để chặn.

Vì sao ba câu trả lời gộp làm một
=================================
"không tồn tại", "thuộc tổ chức khác" và "không rõ chủ" phải giống hệt nhau với
người gọi. Ba câu trả lời khác nhau biến `split_id` thành máy đoán: một tenant dò
tên và biết được cái gì tồn tại bên trong tổ chức khác. Đây là đúng lớp rò rỉ
"existence oracle" đã kiểm ở A2, chỉ khác mặt phẳng lưu trữ. Lý do thật đi vào
nhật ký máy chủ ở mức ERROR — người vận hành đọc được, người gọi thì không.

Hai hiện vật lịch sử
====================
`hoa-de-…` và `bang-chu-cai-…` giữ nguyên trạng thái `unknown` và từ đây không
dùng được nữa. Cách gọi đúng KHÔNG phải "dữ liệu hỏng" mà là:

```
nội dung hợp lệ, provenance không đủ để chứng minh phạm vi tenant
```

Không backfill khi không có chứng cứ. Chọn đại một tenant rồi dựng lại chính là
điều C2b vừa cấm — chỉ khác là người tự cấp quyền sẽ là chúng ta thay vì job
đang gọi; về provenance thì vẫn không hợp lệ.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.split_artifact import (  # noqa: E402
    OWNER_BINDING_KEY,
    OWNER_KEY,
    OWNER_NOT_APPLICABLE,
    PURPOSE_OPERATIONAL,
    PURPOSE_RESEARCH,
    SplitArtifactError,
    file_hashes,
    owner_binding,
    resolve_split_artifact,
)

from test_operational_artifact_pipeline import _chay, kho  # noqa: E402,F401

CO = ("--dialects=pn-a", "--min_samples_per_class=25")
A = "iso_a"
B = "iso_b"


def _meta_path(kho, split_id):
    return kho / "operational" / split_id / "split_metadata.json"


def _bo_chu(kho, split_id):
    """Biến một hiện vật hợp lệ thành hiện vật lịch sử: mất lời khai chủ.

    Dựng bằng cách GỠ khai báo khỏi một hiện vật thật, không bằng cách viết tay
    một tệp JSON: hiện vật lịch sử khác hiện vật hợp lệ đúng ở hai khoá này và
    không khác ở chỗ nào khác. Tự tay dựng cả bản khai sẽ dễ vô tình tạo ra một
    hiện vật hỏng theo kiểu khác, rồi ca kiểm xanh vì lý do sai.
    """
    p = _meta_path(kho, split_id)
    meta = json.loads(p.read_text(encoding="utf-8"))
    meta.pop(OWNER_KEY, None)
    meta.pop(OWNER_BINDING_KEY, None)
    p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _giai(kho, split_id, tenant):
    return resolve_split_artifact(purpose=PURPOSE_OPERATIONAL, splits_root=kho,
                                  split_id=split_id, tenant_id=tenant)


# =========================================================================
# C2-1 / C2-2 / C2-3 — ba câu hỏi, và hai trong ba phải có CÙNG câu trả lời
# =========================================================================

class TestC2_1_2_3_ChuKhopThiQuaChuLechThiKhong:

    def test_C2_1_chu_khop_thi_TRA_VE(self, kho, monkeypatch):
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id=A)
        hv = _giai(kho, "op-a", A)
        print(f"\n[evidence] tenant_id={hv.tenant_id!r} state={hv.owner_state}")
        assert hv.tenant_id == A
        assert hv.train_csv.exists()

    def test_C2_2_chu_lech_thi_TU_CHOI(self, kho, monkeypatch):
        """★ Bất biến trung tâm của C2c: A không đọc được split của B."""
        _chay(kho, monkeypatch, *CO, split_id="op-cua-b", tenant_id=B)
        with pytest.raises(SplitArtifactError) as loi:
            _giai(kho, "op-cua-b", A)
        print(f"\n[evidence] {loi.value}")
        # Câu trả lời cho người gọi KHÔNG được nhắc tới tổ chức chủ.
        assert B not in str(loi.value), "lộ tên tenant sở hữu"

    def test_C2_3_hien_vat_cua_B_va_hien_vat_khong_ton_tai_NOI_GIONG_NHAU(
            self, kho, monkeypatch):
        """Nếu hai câu trả lời khác nhau thì `split_id` là một máy đoán.

        Ca này so hai chuỗi lỗi sau khi bỏ đúng phần `split_id` mà chính người
        gọi đã cung cấp — phần đó dĩ nhiên khác nhau và nó không rò rỉ gì.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-cua-b", tenant_id=B)

        with pytest.raises(SplitArtifactError) as ngoai:
            _giai(kho, "op-cua-b", A)
        with pytest.raises(SplitArtifactError) as khong_co:
            _giai(kho, "op-khong-he-ton-tai", A)

        def _chuan_hoa(msg, sid):
            return msg.replace(sid, "<ID>")

        a = _chuan_hoa(str(ngoai.value), "op-cua-b")
        b = _chuan_hoa(str(khong_co.value), "op-khong-he-ton-tai")
        print(f"\n[evidence] ngoai   = {a}")
        print(f"[evidence] khong co = {b}")
        assert a == b, "hai trạng thái phải nói GIỐNG HỆT nhau với người gọi"

    def test_ly_do_that_van_vao_nhat_ky_may_chu(self, kho, monkeypatch, caplog):
        """Im lặng với người gọi, KHÔNG im lặng với người vận hành.

        Nếu lý do thật cũng biến mất thì ta đổi một lỗ rò lấy một sự cố không
        chẩn đoán được — và người trực sẽ đi tìm hiện vật bị xoá.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-cua-b", tenant_id=B)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SplitArtifactError):
                _giai(kho, "op-cua-b", A)
        ghi = " ".join(r.getMessage() for r in caplog.records)
        print(f"\n[evidence] {ghi}")
        assert B in ghi and A in ghi
        assert any(r.levelno >= logging.ERROR for r in caplog.records)


# =========================================================================
# C2-4 — hiện vật lịch sử: nội dung hợp lệ, provenance không đủ
# =========================================================================

class TestC2_4_KhongRoChuThiFailClosed:

    def test_C2_4_khong_ro_chu_thi_TU_CHOI(self, kho, monkeypatch):
        _chay(kho, monkeypatch, *CO, split_id="op-cu", tenant_id=A)
        _bo_chu(kho, "op-cu")

        with pytest.raises(SplitArtifactError) as loi:
            _giai(kho, "op-cu", A)
        print(f"\n[evidence] {loi.value}")

    def test_khong_ro_chu_thi_KHONG_ai_doc_duoc_ke_ca_moi_tenant(
            self, kho, monkeypatch):
        """"Của không ai" KHÔNG có nghĩa "của tất cả".

        Đây là chỗ một bản vá "cho tiện" hay chui vào: hiện vật không chủ trông
        như dữ liệu chung. Nhưng nó không được công bố cho ai cả — nó chỉ chưa
        chứng minh được nó thuộc về ai.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-cu", tenant_id=A)
        _bo_chu(kho, "op-cu")
        for ai in (A, B, "default", "community"):
            with pytest.raises(SplitArtifactError):
                _giai(kho, "op-cu", ai)

    def test_khong_ro_chu_noi_GIONG_nhu_khong_ton_tai(self, kho, monkeypatch):
        _chay(kho, monkeypatch, *CO, split_id="op-cu", tenant_id=A)
        _bo_chu(kho, "op-cu")

        with pytest.raises(SplitArtifactError) as x:
            _giai(kho, "op-cu", A)
        with pytest.raises(SplitArtifactError) as y:
            _giai(kho, "op-khong-co", A)
        assert str(x.value).replace("op-cu", "<ID>") == \
            str(y.value).replace("op-khong-co", "<ID>")

    def test_ly_do_that_goi_dung_ten_van_de(self, kho, monkeypatch, caplog):
        """"Không đủ chứng cứ về chủ" ≠ "dữ liệu hỏng".

        Phân biệt này không phải chuyện chữ nghĩa: một bên cần dựng lại hiện
        vật, một bên cần tìm lại nguồn gốc. Nhật ký phải đủ để người đọc chọn
        đúng việc.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-cu", tenant_id=A)
        _bo_chu(kho, "op-cu")
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SplitArtifactError):
                _giai(kho, "op-cu", A)
        ghi = " ".join(r.getMessage() for r in caplog.records)
        print(f"\n[evidence] {ghi}")
        assert OWNER_KEY in ghi


# =========================================================================
# C2-5 — không biết người hỏi là ai thì DỪNG, trước cả khi tìm hiện vật
# =========================================================================

class TestC2_5_KhongCoTenantThiDungTruoc:

    @pytest.mark.parametrize("thieu", ["", "   ", None])
    def test_C2_5_thieu_tenant_thi_TU_CHOI(self, kho, monkeypatch, thieu):
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id=A)
        with pytest.raises(SplitArtifactError) as loi:
            _giai(kho, "op-a", thieu)
        print(f"\n[evidence] {loi.value}")
        assert "không biết tenant" in str(loi.value).lower()

    def test_thieu_tenant_chan_TRUOC_khi_nhin_toi_hien_vat(self, kho):
        """Thứ tự kiểm là nội dung, không phải chi tiết.

        Kiểm tenant SAU khi tìm hiện vật thì một lượt gọi thiếu phạm vi nhắm
        vào `split_id` không tồn tại sẽ báo "không có hiện vật" — che mất lỗi
        thật, và che luôn việc phạm vi đang bị bỏ trống ở đâu đó phía trên.
        """
        with pytest.raises(SplitArtifactError) as loi:
            _giai(kho, "op-khong-he-co", "")
        assert "không biết tenant" in str(loi.value).lower()

    def test_quen_truyen_tenant_la_TypeError_chu_khong_phai_duoc_mien_kiem(self, kho):
        """★ Không có giá trị mặc định, và đó là cả điểm.

        Một mặc định — kể cả `None` — biến "quên truyền" thành "được miễn kiểm",
        im lặng. Đúng hình dạng của `normalize_tenant_id("")` trả `"default"`:
        hàng rào còn nguyên, chỉ là không ai đi qua nó nữa.
        """
        with pytest.raises(TypeError):
            resolve_split_artifact(purpose=PURPOSE_OPERATIONAL, splits_root=kho,
                                   split_id="op-a")


# =========================================================================
# C2-6 / C2-7 — hai hợp đồng, không nhánh nào rơi sang nhánh kia
# =========================================================================

class TestC2_6_7_HaiHopDongKhongLan:

    def test_C2_6_van_hanh_bi_tu_choi_thi_KHONG_roi_ve_nghien_cuu(
            self, kho, monkeypatch):
        """Rơi về được nghĩa là A bị chặn đọc split của B, rồi lặng lẽ học trên
        mốc nghiên cứu đóng băng — và checkpoint sẽ khai một nguồn gốc không có
        thật. Bị chặn phải là DỪNG, không phải chuyển hướng."""
        for ten in ("train", "val", "test"):
            (kho / f"{ten}.csv").write_text("a\n1\n", encoding="utf-8")
        (kho / "FROZEN_RESEARCH_SPLITS.json").write_text(
            json.dumps({"purpose": "research", "files": file_hashes(kho)}),
            encoding="utf-8")
        _chay(kho, monkeypatch, *CO, split_id="op-cua-b", tenant_id=B)

        with pytest.raises(SplitArtifactError):
            _giai(kho, "op-cua-b", A)

    def test_C2_7_nghien_cuu_KHONG_chiu_luat_chu_so_huu(self, kho):
        """Ba tệp đóng băng không có chủ tenant, và đó là hợp đồng chứ không
        phải thiếu sót. Ép chúng theo luật vận hành sẽ chặn oan mọi lượt lặp
        lại kết quả luận văn."""
        for ten in ("train", "val", "test"):
            (kho / f"{ten}.csv").write_text("a\n1\n", encoding="utf-8")
        (kho / "FROZEN_RESEARCH_SPLITS.json").write_text(
            json.dumps({"purpose": "research", "files": file_hashes(kho)}),
            encoding="utf-8")

        hv = resolve_split_artifact(purpose=PURPOSE_RESEARCH, splits_root=kho,
                                    tenant_id=A)
        print(f"\n[evidence] owner_state={hv.owner_state} tenant_id={hv.tenant_id!r}")
        assert hv.owner_state == OWNER_NOT_APPLICABLE
        assert hv.tenant_id is None

    def test_nghien_cuu_khong_bi_anh_huong_boi_tenant_dang_hoi(self, kho):
        """Hai tenant khác nhau phải nhận CÙNG một hiện vật nghiên cứu."""
        for ten in ("train", "val", "test"):
            (kho / f"{ten}.csv").write_text("a\n1\n", encoding="utf-8")
        (kho / "FROZEN_RESEARCH_SPLITS.json").write_text(
            json.dumps({"purpose": "research", "files": file_hashes(kho)}),
            encoding="utf-8")

        x = resolve_split_artifact(purpose=PURPOSE_RESEARCH, splits_root=kho,
                                   tenant_id=A)
        y = resolve_split_artifact(purpose=PURPOSE_RESEARCH, splits_root=kho,
                                   tenant_id=B)
        assert x.train_csv == y.train_csv
        assert x.owner_state == y.owner_state == OWNER_NOT_APPLICABLE


# =========================================================================
# C2-X — resolver thật sự TIÊU THỤ hợp đồng ràng buộc của C2b
# =========================================================================

class TestC2_X_ResolverTieuThuRangBuoc:

    def test_C2_X_sua_tay_chu_thanh_B_ma_khong_sua_rang_buoc_thi_TU_CHOI(
            self, kho, monkeypatch):
        """C2b đã kiểm ở tầng `read_owner`. Ca này kiểm ở tầng resolver.

        Hai tầng, hai ca, và ca này mới trả lời được câu "resolver có thật sự
        gọi tới hợp đồng đó không, hay nó chỉ đọc `tenant_id` trần". Gỡ lượt gọi
        `read_owner` ra khỏi resolver thì ca ở C2b vẫn xanh — chỉ ca này đỏ.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id=A)
        p = _meta_path(kho, "op-a")
        meta = json.loads(p.read_text(encoding="utf-8"))
        meta[OWNER_KEY] = B                      # đổi chủ, giữ nguyên ràng buộc
        p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            _giai(kho, "op-a", B)                # hỏi với đúng chủ vừa "tự phong"
        print(f"\n[evidence] {loi.value}")
        assert OWNER_BINDING_KEY in str(loi.value), (
            "phải nổ vì ràng buộc lệch, không phải vì tenant lệch — nếu không, "
            "ca này không chứng minh resolver có tiêu thụ ràng buộc")

    def test_rang_buoc_tinh_lai_dung_thi_van_khong_qua_duoc_cong_tenant(
            self, kho, monkeypatch):
        """Kẻ sửa tay biết cách tính lại ràng buộc thì vẫn còn cổng thứ hai.

        Đây là lý do `owner_binding` được gọi là bằng chứng-chống-sửa chứ không
        phải ranh giới thẩm quyền: nó bắt sửa cẩu thả. Ranh giới thật là quyền
        ghi trên hệ tệp — và cổng tenant, thứ vẫn chặn khi ràng buộc đã khớp.
        """
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id=A)
        p = _meta_path(kho, "op-a")
        meta = json.loads(p.read_text(encoding="utf-8"))
        meta[OWNER_KEY] = B
        meta[OWNER_BINDING_KEY] = owner_binding(
            split_id="op-a", tenant_id=B, files=meta["files"])
        p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        # Ràng buộc giờ KHỚP, nên hiện vật "hợp lệ" — và thuộc về B.
        assert _giai(kho, "op-a", B).tenant_id == B
        # …nhưng A vẫn không đọc được. Sửa tay đổi được chủ trên đĩa; nó không
        # cấp cho A quyền đọc thứ giờ đã khai là của B.
        with pytest.raises(SplitArtifactError):
            _giai(kho, "op-a", A)
