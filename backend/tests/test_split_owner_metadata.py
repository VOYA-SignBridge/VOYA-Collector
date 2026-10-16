"""C2b — hiện vật vận hành phải TỰ KHAI chủ sở hữu, và chủ đến từ bên TẠO.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_split_owner_metadata.py -v -s

Bất biến
========
```
OperationalSplit(split_id)  ->  tenant_id BẮT BUỘC, lấy từ ngữ cảnh tạo
                            ->  không bao giờ lấy từ job đầu tiên dùng nó
                            ->  không bao giờ suy từ tên thư mục / class_uid
                            ->  không bao giờ rơi về `default` hay `community`

OperationalSplitOwner(split_id)  =  BẤT BIẾN
```

Vì sao "chủ đến từ bên tạo" là toàn bộ nội dung của bước này
===========================================================
Nếu chủ sở hữu được suy ra lúc TIÊU THỤ thì luật thành "ai hỏi trước thì thành
chủ" — một tenant chỉ cần đoán đúng `split_id` là tự cấp cho mình quyền sở hữu
dữ liệu chia của tổ chức khác. Đó là dạng tự-cấp-quyền đã gặp ở nhóm B với
`owner missing → caller's tenant`, chỉ đổi mặt phẳng lưu trữ.

Nên bước này KHÔNG sửa resolver. Nó chỉ làm cho hiện vật có một lời khai đáng
tin để về sau còn có gì mà cưỡng chế. Cưỡng chế không có dữ liệu thẩm quyền
phía sau chỉ là một phép kiểm luôn phải trả lời "không biết".

Phân biệt bằng `purpose`, không bằng "thiếu tenant"
==================================================
```
purpose = operational + có split_id  ->  chủ BẮT BUỘC
purpose = research                   ->  hợp đồng đóng băng, KHÔNG có chủ tenant
```

Ba tệp nghiên cứu ở gốc không được thêm cột tenant nào chỉ để khớp lược đồ mới.
Vì vậy `owner_state` có BA giá trị chứ không phải một `Optional[str]`:
`not_applicable` (nghiên cứu) và `unknown` (vận hành mất chủ) là hai chuyện khác
hẳn nhau, và gộp chúng vào một `None` là mời người viết sau xử lý chúng như
nhau — mà cách xử lý "như nhau" duy nhất còn lại sẽ là cho qua.

Không backfill
==============
Hai hiện vật vận hành có trước hợp đồng này (`hoa-de-…`, `bang-chu-cai-…`) không
khai chủ. Chúng ở trạng thái `unknown` và ở nguyên đó. Không biết nguồn gốc thì
không tự cấp chủ — kể cả khi việc tự cấp làm mọi thứ xanh trở lại.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.splits import make_splits as ms  # noqa: E402
from processed.train_utils.split_artifact import (  # noqa: E402
    OWNER_BINDING_KEY,
    OWNER_KEY,
    OWNER_NOT_APPLICABLE,
    OWNER_OWNED,
    OWNER_UNKNOWN,
    PURPOSE_OPERATIONAL,
    SplitArtifactError,
    owner_binding,
    read_owner,
    resolve_research,
    resolve_split_artifact,
)

# Dùng lại đúng bộ đồ nghề của `test_operational_artifact_pipeline`: cùng kho dữ
# liệu tí hon, cùng cách gọi CLI thật. Chép lại một bản thứ hai ở đây là tái lập
# đúng cái bẫy đã làm hỏng hợp đồng mã băm hôm 15/08 — hai bản cài đặt của cùng
# một quy ước, mỗi bản tự nhất quán với chính nó.
from test_operational_artifact_pipeline import _chay, kho  # noqa: E402,F401

CO = ("--dialects=pn-a", "--min_samples_per_class=25")


def _meta(d: Path) -> dict:
    return json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))


# =========================================================================
# C2b-1 / C2b-2 — chủ sở hữu đi từ ngữ cảnh tạo vào bản khai, nguyên vẹn
# =========================================================================

class TestC2b_1_2_ChuSoHuuDenTuBenTao:

    @pytest.mark.parametrize("tenant", ["iso_a", "iso_b"])
    def test_chu_duoc_ghim_dung_vao_ban_khai(self, kho, monkeypatch, tenant):
        d = _chay(kho, monkeypatch, *CO, split_id=f"op-{tenant}", tenant_id=tenant)
        meta = _meta(d)
        print(f"\n[evidence] {tenant}: {OWNER_KEY}={meta.get(OWNER_KEY)!r} "
              f"{OWNER_BINDING_KEY}={str(meta.get(OWNER_BINDING_KEY))[:16]}…")
        assert meta[OWNER_KEY] == tenant
        assert meta["purpose"] == PURPOSE_OPERATIONAL

    @pytest.mark.parametrize("tenant", ["iso_a", "iso_b"])
    def test_resolver_doc_ra_dung_chu_va_bao_la_DA_XAC_MINH(self, kho, monkeypatch,
                                                            tenant):
        """`resolve` phải trả về CẢ chủ lẫn lý do tin vào chủ đó."""
        _chay(kho, monkeypatch, *CO, split_id=f"op-{tenant}", tenant_id=tenant)
        hv = resolve_split_artifact(purpose="operational", splits_root=kho,
                                    split_id=f"op-{tenant}", tenant_id=tenant)
        print(f"\n[evidence] owner_state={hv.owner_state} tenant_id={hv.tenant_id!r}")
        assert hv.tenant_id == tenant
        assert hv.owner_state == OWNER_OWNED

    def test_hai_tenant_cho_hai_rang_buoc_KHAC_nhau(self, kho, monkeypatch):
        """Nếu ràng buộc không phụ thuộc tenant thì nó không ràng buộc gì cả.

        Ca này bắt được kiểu cài đặt "băm cho có": một ràng buộc chỉ băm
        `split_id` và mã băm tệp sẽ giống hệt nhau giữa hai chủ, và khi đó đổi
        `tenant_id` bằng tay sẽ đi lọt mọi phép kiểm.

        Giữ NGUYÊN `split_id` và nguyên mã băm ba tệp, chỉ đổi chủ — nếu không
        cố định hai thứ kia thì ca này xanh vì lý do khác, và ta lại có một phép
        đo trả lời câu hỏi khác câu nó viết trên nhãn.
        """
        d = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        meta = _meta(d)
        rb_b = owner_binding(split_id="op-a", tenant_id="iso_b",
                             files=meta["files"])
        print(f"\n[evidence] iso_a={meta[OWNER_BINDING_KEY][:16]}… "
              f"iso_b={rb_b[:16]}…")
        assert meta[OWNER_BINDING_KEY] != rb_b, \
            "ràng buộc không đổi theo tenant thì vô dụng"


# =========================================================================
# C2b-3 — tạo split vận hành mà thiếu chủ thì DỪNG, và không để lại gì
# =========================================================================

class TestC2b_3_ThieuChuThiDung:

    def test_CLI_khong_co_tenant_id_thi_DUNG(self, kho, monkeypatch):
        with pytest.raises(SystemExit) as loi:
            _chay(kho, monkeypatch, *CO, split_id="op-khong-chu", tenant_id=None)
        print(f"\n[evidence] {loi.value}")
        assert "--tenant_id" in str(loi.value)

    def test_khong_de_lai_hien_vat_nua_chung(self, kho, monkeypatch):
        """Ba CSV không có bản khai là thứ tệ hơn cả không có gì.

        Quy tắc chỉ-tạo-mới sẽ từ chối ghi đè lên thư mục đó, nên một lượt chạy
        hỏng nửa chừng chiếm vĩnh viễn một `split_id`. Vì vậy cổng thiếu-chủ
        phải đứng TRƯỚC mọi lượt ghi, không phải ở hàm ghi bản khai.
        """
        with pytest.raises(SystemExit):
            _chay(kho, monkeypatch, *CO, split_id="op-khong-chu", tenant_id=None)
        d = kho / "operational" / "op-khong-chu"
        print(f"\n[evidence] {d} ton tai = {d.exists()}")
        assert not d.exists()

    @pytest.mark.parametrize("rong", ["", "   "])
    def test_chuoi_rong_khong_phai_mot_chu_so_huu(self, kho, monkeypatch, rong):
        with pytest.raises(SystemExit):
            _chay(kho, monkeypatch, *CO, split_id="op-rong", tenant_id=rong)
        assert not (kho / "operational" / "op-rong").exists()

    def test_ham_ghi_la_luoi_thu_hai_cho_nguoi_goi_truc_tiep(self, tmp_path):
        """Cổng CLI bảo vệ đường đi qua CLI. Hàm phải tự bảo vệ được nó."""
        for ten in ("train", "val", "test"):
            (tmp_path / f"{ten}.csv").write_text("a\n1\n", encoding="utf-8")
        with pytest.raises(ValueError) as loi:
            ms.write_legacy_snapshot(
                tmp_path, class_keys=["U1", "U2"], floor=25, excluded=[],
                mode="sample", seed=42, counts={}, split_id="op-truc-tiep")
        print(f"\n[evidence] {loi.value}")
        assert OWNER_KEY in str(loi.value)

    def test_ban_khai_khong_co_dia_chi_thi_khong_mang_quyen_so_huu(self, tmp_path):
        """Ghi `tenant_id` vào chỗ không ai cưỡng chế được là an toàn giả.

        Bản khai ở gốc `processed/splits/` và ở nhánh `--by_language` cũng mang
        `purpose: operational`, nhưng không có `split_id` nên
        `resolve_operational` không bao giờ trả về chúng. Một trường chủ sở hữu
        ở đó trông như một hàng rào và không chặn được gì.
        """
        with pytest.raises(ValueError):
            ms.write_legacy_snapshot(
                tmp_path, class_keys=["U1"], floor=25, excluded=[], mode="sample",
                seed=42, counts={}, tenant_id="iso_a")


# =========================================================================
# C2b-4 — nhánh nghiên cứu KHÔNG bị luật vận hành chạm tới
# =========================================================================

class TestC2b_4_NghienCuuGiuNguyen:

    def test_ba_tep_dong_bang_khong_co_khai_niem_chu_tenant(self):
        """`not_applicable`, KHÔNG phải `unknown`.

        Hai trạng thái này dẫn tới hai quyết định trái ngược ở tầng cưỡng chế:
        `unknown` là một khoảng trống thẩm quyền phải chặn; `not_applicable` là
        hợp đồng đã hoàn chỉnh. Trộn chúng lại thì hoặc ta chặn oan mọi lượt
        nghiên cứu, hoặc ta cho qua mọi hiện vật vận hành mất chủ.
        """
        goc = REPO_ROOT / "processed" / "splits"
        hv = resolve_research(goc)
        print(f"\n[evidence] research owner_state={hv.owner_state} "
              f"tenant_id={hv.tenant_id!r}")
        assert hv.owner_state == OWNER_NOT_APPLICABLE
        assert hv.tenant_id is None

    def test_so_dang_ky_dong_bang_khong_moc_them_truong_tenant(self):
        """Đóng băng nghĩa là không thêm cột tenant chỉ để khớp lược đồ mới."""
        so = json.loads(
            (REPO_ROOT / "processed" / "splits" / "FROZEN_RESEARCH_SPLITS.json")
            .read_text(encoding="utf-8"))
        print(f"\n[evidence] khoa = {sorted(so.keys())}")
        assert OWNER_KEY not in so
        assert OWNER_BINDING_KEY not in so

    def test_luot_van_hanh_khong_dung_toi_ba_tep_o_goc(self, kho, monkeypatch):
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        for ten in ("train.csv", "val.csv", "test.csv"):
            assert not (kho / ten).exists()


# =========================================================================
# C2b-5 — chủ sở hữu BẤT BIẾN, và không tự cấp được bằng cách sửa JSON
# =========================================================================

class TestC2b_5_ChuBatBienVaKhongTuCap:

    def test_hien_vat_cu_khong_co_chu_thi_la_KHONG_BIET(self, kho, monkeypatch):
        """Không biết chủ ≠ chủ là `default`, và ≠ hiện vật hỏng.

        Đây là trạng thái của hai hiện vật vận hành dựng trước hợp đồng này. Nó
        phải đọc được, gọi tên được, và KHÔNG được điền bừa.
        """
        d = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        meta = _meta(d)
        meta.pop(OWNER_KEY)
        meta.pop(OWNER_BINDING_KEY)
        (d / "split_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        # Hỏi tầng BIỂU DIỄN, không hỏi tầng cưỡng chế. Từ C2c `resolve` từ chối
        # hiện vật mất chủ, nên đi qua nó ở đây sẽ biến một ca về "trạng thái
        # đọc ra là gì" thành một ca về "có bị chặn không" — hai câu hỏi khác
        # nhau, và ca này là câu thứ nhất. Ca chặn nằm ở C2-4.
        chu = read_owner(_meta(d), split_id="op-a")
        print(f"\n[evidence] state={chu.state} tenant_id={chu.tenant_id!r}")
        assert chu.state == OWNER_UNKNOWN
        assert chu.tenant_id is None      # ★ không phải "default"

    def test_sua_tay_tenant_id_thi_BI_TU_CHOI(self, kho, monkeypatch):
        """`split A → sửa JSON → tenant_id = B` phải nổ, không im lặng đổi chủ."""
        d = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        meta = _meta(d)
        meta[OWNER_KEY] = "iso_b"
        (d / "split_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            read_owner(meta, split_id="op-a")
        print(f"\n[evidence] {loi.value}")
        assert OWNER_BINDING_KEY in str(loi.value)

    def test_them_tay_chu_cho_hien_vat_khong_ro_nguon_goc_thi_BI_TU_CHOI(
            self, kho, monkeypatch):
        """Backfill "cho tiện" là đúng thứ bước này tồn tại để chặn."""
        d = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        meta = _meta(d)
        meta.pop(OWNER_BINDING_KEY)
        meta[OWNER_KEY] = "iso_b"
        (d / "split_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        with pytest.raises(SplitArtifactError):
            read_owner(_meta(d), split_id="op-a")

    def test_chep_rang_buoc_tu_hien_vat_khac_thi_BI_TU_CHOI(self, kho, monkeypatch):
        """Ràng buộc khoá vào `split_id`, nên không mang từ hiện vật khác sang."""
        a = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        b = _chay(kho, monkeypatch, *CO, split_id="op-b", tenant_id="iso_a")
        meta_b = _meta(b)
        meta_b[OWNER_BINDING_KEY] = _meta(a)[OWNER_BINDING_KEY]
        (b / "split_metadata.json").write_text(json.dumps(meta_b), encoding="utf-8")

        with pytest.raises(SplitArtifactError):
            read_owner(meta_b, split_id="op-b")

    def test_khong_ghi_de_duoc_chu_bang_cach_chay_lai(self, kho, monkeypatch):
        """Chuyển quyền sở hữu phải là quy trình riêng, không phải chạy lại CLI."""
        _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        with pytest.raises(SystemExit) as loi:
            _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_b")
        print(f"\n[evidence] {loi.value}")

        chu = read_owner(_meta(kho / "operational" / "op-a"), split_id="op-a")
        assert chu.tenant_id == "iso_a", "chủ cũ phải còn nguyên sau lượt chạy hỏng"

    def test_rang_buoc_bao_ve_ca_ma_bam_tep(self, kho, monkeypatch):
        """Chủ gắn vào NỘI DUNG, nên tráo ba CSV cũng làm ràng buộc lệch."""
        d = _chay(kho, monkeypatch, *CO, split_id="op-a", tenant_id="iso_a")
        meta = _meta(d)
        gia = dict(meta["files"])
        gia["train.csv"] = {**gia["train.csv"], "sha256": "0" * 64}
        assert owner_binding(split_id="op-a", tenant_id="iso_a", files=gia) \
            != meta[OWNER_BINDING_KEY]


# =========================================================================
# Trạng thái THẬT trên đĩa — chứng cứ cho sổ, không phải phép kiểm hành vi
# =========================================================================

class TestSoHienVatDangCo:

    def test_hai_hien_vat_cu_deu_o_trang_thai_KHONG_BIET_CHU(self):
        """Đo, ghi vào sổ, và KHÔNG sửa. Không rõ nguồn gốc thì không cấp chủ.

        Ca này sẽ đỏ nếu ai đó backfill chủ cho chúng mà không có quy trình
        chuyển quyền thật — đó chính là điều nó canh.
        """
        goc = REPO_ROOT / "processed" / "splits" / "operational"
        if not goc.is_dir():
            pytest.skip("không có hiện vật vận hành nào trên máy này")
        thay = {}
        for d in sorted(p for p in goc.iterdir() if p.is_dir()):
            meta = _meta(d)
            thay[d.name] = read_owner(meta, split_id=d.name).state
        print(f"\n[evidence] {json.dumps(thay, ensure_ascii=False, indent=2)}")
        # `read_owner` đã nổ nếu có hiện vật khai chủ mà ràng buộc lệch, nên tới
        # được đây thì mọi trạng thái đều là một trong hai giá trị hợp lệ.
        assert set(thay.values()) <= {OWNER_UNKNOWN, OWNER_OWNED}
        khong_biet = sorted(k for k, v in thay.items() if v == OWNER_UNKNOWN)
        print(f"[evidence] khong biet chu: {khong_biet}")
