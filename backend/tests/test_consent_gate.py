"""Cổng đồng thuận: thứ quyết định dữ liệu của ai được đi tới đâu.

Bộ test này cố ý ghim cả những hành vi TRÔNG NHƯ lỗ hổng — kế thừa mức nội bộ,
mẫu vô danh vẫn huấn luyện được — vì chúng là những đánh đổi có chủ ý, và một
đánh đổi không có test là một đánh đổi sẽ bị ai đó "sửa" vào tháng sau.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import consent_gate as cg


# --------------------------------------------------------------------------- helpers

def _row(sample_uid: str, signer: str | None = None) -> dict:
    return {"sample_uid": sample_uid, "signer_id": signer}


def _consent(highest: str | None, *, has_record: bool = True) -> cg.SignerConsent:
    return cg.SignerConsent(
        highest_live_rank=None if highest is None else cg.scope_rank(highest),
        has_any_record=has_record,
    )


NO_ALIASES: dict = {}


# --------------------------------------------------------------------------- thang

class TestBaMucLaMotCaiThang:
    """Đồng ý mức cao bao hàm mức thấp; mức thấp KHÔNG kéo theo mức cao."""

    def test_thu_tu_thang_dung_nhu_luoc_do_mo_ta(self):
        assert cg.SCOPE_LADDER == (
            "internal_training", "research_release", "public_library")

    def test_ten_pham_vi_la_khong_doan(self):
        with pytest.raises(cg.ConsentScopeError):
            cg.scope_rank("public")          # gần đúng, và gần đúng là sai

    def test_dong_y_cong_khai_thi_dung_duoc_o_moi_muc_thap_hon(self):
        consents = {"S1": _consent("public_library")}
        for scope in cg.SCOPE_LADDER:
            out = cg.filter_rows([_row("a", "S1")], scope=scope,
                                 consents=consents, aliases=NO_ALIASES)
            assert len(out.kept) == 1, f"phải qua được ở mức {scope}"

    def test_chi_dong_y_noi_bo_thi_KHONG_vao_ban_phat_hanh(self):
        # Đây chính là lỗ hổng module này ra đời để bịt.
        consents = {"S1": _consent("internal_training")}
        out = cg.filter_rows([_row("a", "S1")], scope="research_release",
                             consents=consents, aliases=NO_ALIASES)
        assert out.kept == []
        assert out.reasons == {cg.REASON_SCOPE_TOO_LOW: 1}


# --------------------------------------------------------------------------- rút

class TestRutLaRut:
    def test_rut_het_thi_chan_o_MOI_muc_ke_ca_noi_bo(self, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        consents = {"S1": _consent(None, has_record=True)}
        for scope in cg.SCOPE_LADDER:
            out = cg.filter_rows([_row("a", "S1")], scope=scope,
                                 consents=consents, aliases=NO_ALIASES)
            assert out.kept == [], f"đã rút mà vẫn lọt ở mức {scope}"
            assert out.reasons == {cg.REASON_WITHDRAWN: 1}

    def test_co_ke_thua_bat_cung_khong_cuu_duoc_nguoi_da_rut(self, monkeypatch):
        """Kế thừa dành cho người CHƯA TỪNG được hỏi, không phải người đã từ chối.

        Phân biệt này là toàn bộ lý do `has_any_record` tồn tại — nếu không,
        "đã rút" và "chưa từng ký" trông giống hệt nhau (cả hai đều không có
        dòng nào còn hiệu lực) và cờ kế thừa sẽ lặng lẽ dựng lại đồng thuận đã
        bị rút.
        """
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        withdrawn = cg.filter_rows([_row("a", "S1")], scope="internal_training",
                                   consents={"S1": _consent(None, has_record=True)},
                                   aliases=NO_ALIASES)
        never_asked = cg.filter_rows([_row("b", "S2")], scope="internal_training",
                                     consents={}, aliases=NO_ALIASES)
        assert withdrawn.kept == []
        assert len(never_asked.kept) == 1

    def test_rut_muc_cao_van_giu_muc_thap_da_cap_rieng(self):
        """Hai dòng riêng: cấp nội bộ, cấp rồi rút công khai → còn nội bộ."""
        consents = {"S1": _consent("internal_training", has_record=True)}
        assert len(cg.filter_rows([_row("a", "S1")], scope="internal_training",
                                  consents=consents, aliases=NO_ALIASES).kept) == 1
        assert cg.filter_rows([_row("a", "S1")], scope="public_library",
                              consents=consents, aliases=NO_ALIASES).kept == []


# --------------------------------------------------------------------------- kế thừa

class TestKeThuaMucNoiBo:
    def test_chua_tung_ky_thi_huan_luyen_noi_bo_duoc(self, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        out = cg.filter_rows([_row("a", "S1")], scope="internal_training",
                             consents={}, aliases=NO_ALIASES)
        assert len(out.kept) == 1

    def test_chua_tung_ky_thi_KHONG_phat_hanh_duoc(self, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        for scope in ("research_release", "public_library"):
            out = cg.filter_rows([_row("a", "S1")], scope=scope,
                                 consents={}, aliases=NO_ALIASES)
            assert out.kept == []
            assert out.reasons == {cg.REASON_NO_CONSENT: 1}

    def test_tat_co_ke_thua_thi_chat_tuyet_doi(self, monkeypatch):
        """`CONSENT_GRANDFATHER_INTERNAL=0` phải thật sự đóng cả cửa nội bộ.

        Với dữ liệu sản xuất hôm nay (0 dòng đồng thuận) điều đó nghĩa là tập
        huấn luyện rỗng. Đó là hành vi ĐÚNG và test này ghim nó, để không ai
        đọc cờ này như một công tắc trang trí.
        """
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "0")
        out = cg.filter_rows([_row("a", "S1"), _row("b", None)],
                             scope="internal_training",
                             consents={}, aliases=NO_ALIASES)
        assert out.kept == []

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
    def test_cac_cach_viet_tat_deu_hieu(self, monkeypatch, value):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", value)
        assert cg.grandfather_internal_enabled() is False


# --------------------------------------------------------------------------- vô danh

class TestMauKhongTruyDuocNguoiKy:
    """56,6% kho dữ liệu nằm ở đây. Con số đó giờ tự nó chặn đường phát hành."""

    @pytest.mark.parametrize("signer", [None, "", "   "])
    def test_moi_kieu_trong_deu_tinh_la_vo_danh(self, signer, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        out = cg.filter_rows([_row("a", signer)], scope="research_release",
                             consents={}, aliases=NO_ALIASES)
        assert out.kept == []
        assert out.reasons == {cg.REASON_UNATTRIBUTED: 1}

    def test_vo_danh_khong_bao_gio_phat_hanh_duoc_du_co_dong_thuan_cua_nguoi_khac(self):
        """Một kho đầy đồng thuận cũng không hợp thức hoá được mẫu vô danh."""
        consents = {"S1": _consent("public_library")}
        out = cg.filter_rows([_row("a", None)], scope="public_library",
                             consents=consents, aliases=NO_ALIASES)
        assert out.kept == []


# --------------------------------------------------------------------------- bí danh

class TestGopNguoiKyKhongLamMatDongThuan:
    def test_mau_tro_toi_id_cu_van_doc_duoc_dong_thuan_cua_id_moi(self):
        """Bỏ bước này thì một lần gộp người ký âm thầm huỷ đồng thuận của họ."""
        out = cg.filter_rows([_row("a", "OLD")], scope="public_library",
                             consents={"NEW": _consent("public_library")},
                             aliases={"OLD": "NEW"})
        assert len(out.kept) == 1

    def test_chuoi_gop_nhieu_buoc_van_di_toi_cuoi(self):
        out = cg.filter_rows([_row("a", "A")], scope="research_release",
                             consents={"C": _consent("research_release")},
                             aliases=cg._resolve_chain({"A": "B", "B": "C"}))
        assert len(out.kept) == 1


# --------------------------------------------------------------------------- báo cáo

class TestKetQuaNoiDuocChoNguoiDoc:
    def test_summary_dem_du_va_neu_ly_do(self, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        rows = [_row("a", "S1"), _row("b", None), _row("c", "S2")]
        out = cg.filter_rows(rows, scope="research_release",
                             consents={"S1": _consent("public_library")},
                             aliases=NO_ALIASES)
        assert out.total == 3
        assert len(out.kept) == 1
        text = out.summary()
        assert "1/3" in text
        assert "research_release" in text

    def test_require_all_chan_han_khi_co_mau_bi_giu_lai(self):
        out = cg.filter_rows([_row("a", None)], scope="public_library",
                             consents={}, aliases=NO_ALIASES)
        with pytest.raises(cg.ConsentGateBlocked):
            cg.require_all(out)

    def test_require_all_cho_qua_khi_sach(self):
        out = cg.filter_rows([_row("a", "S1")], scope="public_library",
                             consents={"S1": _consent("public_library")},
                             aliases=NO_ALIASES)
        assert cg.require_all(out) is out


# --------------------------------------------------------------------------- run purpose

class TestMucDichChayQuyetDinhMucPhamVi:
    @pytest.mark.parametrize("purpose,expected", [
        (None, "internal_training"),
        ("", "internal_training"),
        ("normal", "internal_training"),
        ("research", "research_release"),
        ("RESEARCH", "research_release"),
        ("release", "public_library"),
    ])
    def test_anh_xa(self, purpose, expected):
        assert cg.scope_for_run_purpose(purpose) == expected


# --------------------------------------------------------------------------- ảnh chụp

class TestAnhChup:
    def _write(self, tmp_path: Path, **overrides) -> Path:
        """Dựng một ảnh chụp hợp lệ, băm ĐÚNG cách `build_snapshot` băm."""
        import hashlib
        from datetime import datetime, timezone

        body = {
            "snapshot_version": cg.SNAPSHOT_VERSION,
            "tenant_id": "default",
            "scope_ladder": list(cg.SCOPE_LADDER),
            "signers": {"S1": {"highest_live_rank": 2, "has_any_record": True}},
            "aliases": {"OLD": "S1"},
        }
        body.update({k: v for k, v in overrides.items()
                     if k not in ("content_hash", "generated_at")})
        body["content_hash"] = overrides.get("content_hash") or hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        body["generated_at"] = overrides.get(
            "generated_at", datetime.now(timezone.utc).isoformat())
        path = tmp_path / "consent_snapshot.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def test_doc_lai_duoc_dung_trang_thai(self, tmp_path):
        consents, aliases, meta = cg.load_snapshot(self._write(tmp_path))
        assert consents["S1"].highest_live_rank == 2
        assert aliases == {"OLD": "S1"}
        assert len(meta["content_hash"]) == 64

    def test_sua_tay_thi_bi_bat(self, tmp_path):
        """Ảnh chụp đi qua ổ đĩa chia sẻ. Sửa một dòng để tự cấp quyền phát hành
        là cách rẻ nhất để mở toang cổng, nên mã băm phải được đối chiếu."""
        path = self._write(tmp_path)
        body = json.loads(path.read_text(encoding="utf-8"))
        body["signers"]["S9"] = {"highest_live_rank": 2, "has_any_record": True}
        path.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(cg.SnapshotUnusable) as exc:
            cg.load_snapshot(path)
        assert "content_hash" in str(exc.value)

    def test_anh_chup_that_tu_build_snapshot_doc_lai_duoc(self, monkeypatch, tmp_path):
        """Vòng tròn khép kín: thứ `build_snapshot` ghi ra phải là thứ
        `load_snapshot` đọc vào. Hai hàm băm cùng một phần thân theo cùng một
        cách, và test này là chỗ duy nhất chứng minh điều đó."""
        monkeypatch.setattr(cg, "load_consents",
                            lambda _t: {"S1": _consent("research_release")})
        monkeypatch.setattr(cg, "_resolve_aliases", lambda _t: {"OLD": "S1"})
        data = cg.build_snapshot("default")

        path = tmp_path / "consent_snapshot.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        consents, aliases, _meta = cg.load_snapshot(path)
        assert consents["S1"].highest_live_rank == cg.scope_rank("research_release")
        assert aliases == {"OLD": "S1"}

    def test_vang_mat_thi_TU_CHOI_chu_khong_cho_qua(self, tmp_path):
        """Mặc định-từ chối. Quên xuất ảnh chụp ≠ 'không lọc gì cả'."""
        with pytest.raises(cg.SnapshotUnusable) as exc:
            cg.load_snapshot(tmp_path / "khong-co.json")
        assert "consent_snapshot" in str(exc.value)

    def test_qua_han_thi_tu_choi(self, tmp_path):
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(days=cg.SNAPSHOT_MAX_AGE_DAYS + 1))
        path = self._write(tmp_path, generated_at=old.isoformat())
        with pytest.raises(cg.SnapshotUnusable) as exc:
            cg.load_snapshot(path)
        assert "ngay tuoi" in str(exc.value) or "ngày tuổi" in str(exc.value)

    def test_thang_pham_vi_khac_thi_tu_choi_dien_giai(self, tmp_path):
        """Thang đổi thì thứ hạng đổi nghĩa — diễn giải bừa là nâng quyền hàng loạt."""
        path = self._write(tmp_path, scope_ladder=["internal_training", "public_library"])
        with pytest.raises(cg.SnapshotUnusable):
            cg.load_snapshot(path)

    def test_phien_ban_khac_thi_tu_choi(self, tmp_path):
        path = self._write(tmp_path, snapshot_version=cg.SNAPSHOT_VERSION + 1)
        with pytest.raises(cg.SnapshotUnusable):
            cg.load_snapshot(path)

    def test_tep_hong_thi_tu_choi_chu_khong_ne(self, tmp_path):
        path = tmp_path / "consent_snapshot.json"
        path.write_text("{ khong phai json", encoding="utf-8")
        with pytest.raises(cg.SnapshotUnusable):
            cg.load_snapshot(path)


# --------------------------------------------------------------------------- tệp split

class TestSoiTepSplitDaDungSan:
    def _csv(self, path: Path, signers: list) -> Path:
        import csv

        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["sample_uid", "signer_id"])
            w.writeheader()
            for i, s in enumerate(signers):
                w.writerow({"sample_uid": f"s{i}", "signer_id": s or ""})
        return path

    def test_gop_nhieu_tep_va_dem_dung(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        train = self._csv(tmp_path / "train.csv", ["S1", "S2"])
        val = self._csv(tmp_path / "val.csv", ["S1"])
        out = cg.audit_csv_files([train, val], scope="internal_training",
                                 consents={}, aliases=NO_ALIASES)
        assert out.total == 3

    def test_tep_khong_ton_tai_thi_BO_QUA_chu_khong_coi_la_sach(self, tmp_path):
        """Một cổng trả 'sạch' cho đường dẫn gõ sai là một cổng không có."""
        train = self._csv(tmp_path / "train.csv", ["S1"])
        out = cg.audit_csv_files([train, tmp_path / "khong-co.csv"],
                                 scope="public_library",
                                 consents={}, aliases=NO_ALIASES)
        # Chỉ đếm tệp có thật; và S1 chưa có đồng thuận nên bị giữ lại.
        assert out.total == 1
        assert out.kept == []


# --------------------------------------------------------------------------- huấn luyện

class TestCongChanTruocKhiHuanLuyen:
    """Chặn ở lúc dựng split là CHƯA ĐỦ.

    Trình huấn luyện không đọc `samples.csv` — nó đọc `train/val/test.csv` đã
    đóng băng, có thể từ nhiều tuần trước. Một người rút đồng thuận hôm nay
    không làm những tệp đó đổi một byte nào, nên phải hỏi lại ngay trước khi
    chạy.
    """

    def test_lay_dung_ba_tep_split_tu_chinh_dong_lenh(self):
        from app.training_tasks import _split_csvs_of

        cmd = ["python", "-m", "x", "--epochs=5",
               "--train_csv=/a/train.csv", "--val_csv=/a/val.csv",
               "--test_csv=/a/test.csv", "--dialect=hoa-de"]
        assert _split_csvs_of(cmd) == ["/a/train.csv", "/a/val.csv", "/a/test.csv"]

    def test_khong_co_tep_split_thi_cong_khong_ket_luan_gi(self):
        """Nhánh dialect/language chạy bằng mặc định của trainer — không có
        đường dẫn nào trên dòng lệnh để soi, và đoán bừa một đường dẫn còn tệ
        hơn không soi."""
        from app.training_tasks import _consent_preflight

        assert _consent_preflight({}, ["python", "-m", "x", "--epochs=5"]) is None

    def test_muc_phat_hanh_chan_mau_vo_danh(self, tmp_path, monkeypatch):
        import csv as _csv

        from app import training_tasks

        train = tmp_path / "train.csv"
        with train.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["sample_uid", "signer_id"])
            w.writeheader()
            w.writerow({"sample_uid": "s0", "signer_id": ""})

        # Không giả lập cổng: để nó chạy thật qua `audit_csv_files`, chỉ chặn
        # đường đọc CSDL. Giả lập chính thứ đang được kiểm là cách chắc chắn
        # nhất để một cổng hỏng vẫn cho test màu xanh.
        monkeypatch.setattr(cg, "load_consents", lambda _tid: {})
        monkeypatch.setattr(cg, "_resolve_aliases", lambda _tid: {})
        monkeypatch.setattr(cg, "_default_tenant", lambda: "default")

        msg = training_tasks._consent_preflight(
            {"run_purpose": "research"}, [f"--train_csv={train}"])
        assert msg is not None
        assert "Cổng đồng thuận chặn" in msg
        assert "research_release" in msg

    def test_muc_noi_bo_cho_cung_mau_do_di_qua(self, tmp_path, monkeypatch):
        """Cùng một tệp, đổi mục đích chạy → đổi kết luận. Đó là toàn bộ ý nghĩa
        của việc phạm vi phụ thuộc `run_purpose`."""
        import csv as _csv

        from app import training_tasks

        train = tmp_path / "train.csv"
        with train.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["sample_uid", "signer_id"])
            w.writeheader()
            w.writerow({"sample_uid": "s0", "signer_id": ""})

        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")
        monkeypatch.setattr(cg, "load_consents", lambda _tid: {})
        monkeypatch.setattr(cg, "_resolve_aliases", lambda _tid: {})
        monkeypatch.setattr(cg, "_default_tenant", lambda: "default")

        assert training_tasks._consent_preflight(
            {"run_purpose": "normal"}, [f"--train_csv={train}"]) is None

    def test_cong_hong_thi_KHONG_giet_moi_luot_huan_luyen(self, monkeypatch, caplog):
        """Đánh đổi có ý thức: một lượt chạy không được soi còn hơn không
        huấn luyện được gì. Dấu vết phải đủ to để phát hiện điều đó đã xảy ra."""
        import logging

        from app import training_tasks

        def _boom(*_a, **_k):
            raise RuntimeError("cong hong")

        monkeypatch.setattr(cg, "audit_csv_files", _boom)
        with caplog.at_level(logging.ERROR):
            assert training_tasks._consent_preflight(
                {}, ["--train_csv=/khong/co.csv"]) is None
        assert any("pre-flight FAILED" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- cầu nối

class TestChapThuanTaiKhoanNoiSangNguoiKy:
    """"Đồng ý rồi thì nó cứ ở đó" — và nó phải tới được đường dữ liệu.

    Đo 2026-08-09: 10 tài khoản đã ký `terms` và `privacy`, và `signer_consents`
    có **0 dòng**. Người dùng bấm đồng ý, hệ thống ghi nhận, rồi cổng dữ liệu
    vẫn đọc ra "chưa ai cho phép gì".
    """

    def test_chi_data_contribution_moi_cap_pham_vi(self):
        """`terms` và `privacy` là điều kiện dùng dịch vụ, không phải giấy phép
        dùng dữ liệu sinh trắc của một con người. Ký chúng không được cấp gì."""
        assert cg.CONSENT_DOCUMENT_SCOPE == {"data_contribution": "internal_training"}
        for kind in ("terms", "privacy", "guardian"):
            assert cg.sync_signer_consent("bat-ky-ai", kind) is None

    def test_muc_cap_dung_bang_muc_ban_van_hua(self):
        """Bản `data_contribution` 2026-08-08 mục 4 tách rõ:

            Có:  huấn luyện mô hình; đo chất lượng; dựng bộ dữ liệu CỦA TỔ CHỨC.
            Chỉ khi đồng ý riêng bằng văn bản:  công bố cùng bài báo; chia sẻ
                                                RA NGOÀI tổ chức.

        Ranh giới "chỉ khi đồng ý riêng" nằm đúng giữa `internal_training` và
        `research_release`. Nâng mức tự động từ một văn bản duy nhất sẽ biến một
        lần bấm "tôi đồng ý đóng góp" thành giấy phép công bố khuôn mặt người ta.
        """
        assert cg.CONSENT_DOCUMENT_SCOPE["data_contribution"] == "internal_training"
        granted = cg.scope_rank(cg.CONSENT_DOCUMENT_SCOPE["data_contribution"])
        assert granted < cg.scope_rank("research_release")
        assert granted < cg.scope_rank("public_library")

    def test_khong_co_ho_so_nguoi_ky_thi_bo_qua_chu_khong_no(self, monkeypatch):
        """Ký trước, đóng góp sau — thứ tự thật. Lúc ký chưa có hàng `signers`
        nào để gắn vào, và điều đó không được làm hỏng việc ký."""
        monkeypatch.setattr(cg, "_sync_signer_consent_inner",
                            lambda *_a, **_k: None)
        assert cg.sync_signer_consent("chua-dong-gop", "data_contribution") is None

    def test_loi_o_ban_phan_chieu_khong_lam_hong_viec_ky(self, monkeypatch, caplog):
        """Chấp thuận của tài khoản là BẢN GỐC và đã ghi xong. Bảng người ký là
        bản phản chiếu; trục trặc ở đó không được cuốn theo bản gốc."""
        import logging

        def _boom(*_a, **_k):
            raise RuntimeError("bang hong")

        monkeypatch.setattr(cg, "_sync_signer_consent_inner", _boom)
        with caplog.at_level(logging.ERROR):
            assert cg.sync_signer_consent("ai-do", "data_contribution") is None
        assert any("backfill_signer_consents" in r.message or
                   "khong phan chieu duoc" in r.message for r in caplog.records)


class TestChuoiDayDu:
    """Từ lúc bấm đồng ý tới lúc mẫu được phép vào tập huấn luyện.

    Bốn mắt xích, và bộ test ở trên kiểm từng mắt riêng. Cái này kiểm chúng
    NỐI được với nhau — chỗ mà mọi cầu nối thường đứt.

    Không đi qua `signers.resolve_signer_for_user`: hàm đó ghi vào
    `dataset/signers.csv` THẬT (bộ test chạy trên bản sao CSDL, không phải bản
    sao hệ tệp). Hàng người ký được chèn thẳng rồi gỡ.
    """

    @pytest.fixture
    def signer_with_account(self):
        import uuid as _uuid

        from app.auth import create_user
        from app.storage.metadata_db import _execute, _fetch_all
        from app.tenant_context import system_scope
        from conftest import purge_registered_account

        name = f"cg{_uuid.uuid4().hex[:8]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        signer_id = f"CGT{_uuid.uuid4().hex[:6].upper()}"
        with system_scope("test setup: dung ho so nguoi ky"):
            rows = _fetch_all("SELECT tenant_id FROM users WHERE id = %s",
                              (str(user["id"]),))
            tenant = rows[0]["tenant_id"]
            _execute(
                "INSERT INTO signers (tenant_id, signer_id, display_name, "
                "external_user_id, is_active) VALUES (%s, %s, %s, %s, TRUE)",
                (tenant, signer_id, name, str(user["id"])))
        yield {"user_id": str(user["id"]), "signer_id": signer_id, "tenant": tenant}
        with system_scope("test cleanup"):
            _execute("DELETE FROM signer_consents WHERE signer_id = %s", (signer_id,))
            _execute("DELETE FROM signers WHERE signer_id = %s", (signer_id,))
        purge_registered_account(name)

    def test_ky_xong_thi_mau_di_duoc_vao_huan_luyen_noi_bo(self, signer_with_account,
                                                           monkeypatch):
        from app import legal
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        doc = legal.current_document("data_contribution")
        if doc is None:
            pytest.skip("chua cong bo data_contribution tren ban sao nay")

        legal.record_consent(signer_with_account["user_id"], "data_contribution",
                             str(doc["version"]))

        with system_scope("test read"):
            rows = _fetch_all(
                "SELECT scope, withdrawn_at FROM signer_consents WHERE signer_id = %s",
                (signer_with_account["signer_id"],))
        assert len(rows) == 1, "phai co dung mot dong dong thuan"
        assert rows[0]["scope"] == "internal_training"
        assert rows[0]["withdrawn_at"] is None

        # Và cổng phải THẤY nó.
        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "0")   # tắt kế thừa
        rows_in = [_row("a", signer_with_account["signer_id"])]
        out = cg.filter_rows(rows_in, scope="internal_training",
                             tenant_id=signer_with_account["tenant"])
        assert len(out.kept) == 1, "dong thuan da ghi ma cong khong thay"

    def test_ky_mot_lan_khong_nang_len_muc_phat_hanh(self, signer_with_account,
                                                     monkeypatch):
        from app import legal

        doc = legal.current_document("data_contribution")
        if doc is None:
            pytest.skip("chua cong bo data_contribution tren ban sao nay")
        legal.record_consent(signer_with_account["user_id"], "data_contribution",
                             str(doc["version"]))

        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "0")
        out = cg.filter_rows([_row("a", signer_with_account["signer_id"])],
                             scope="research_release",
                             tenant_id=signer_with_account["tenant"])
        assert out.kept == []
        assert out.reasons == {cg.REASON_SCOPE_TOO_LOW: 1}

    def test_ky_hai_lan_van_mot_dong_va_giu_nguyen_moc_thoi_gian(self,
                                                                 signer_with_account):
        """"Đồng ý rồi thì nó cứ ở đó" — không sinh dòng thứ hai, không dời mốc."""
        from app import legal
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        doc = legal.current_document("data_contribution")
        if doc is None:
            pytest.skip("chua cong bo data_contribution tren ban sao nay")

        legal.record_consent(signer_with_account["user_id"], "data_contribution",
                             str(doc["version"]))
        with system_scope("test read"):
            first = _fetch_all("SELECT consent_id, granted_at FROM signer_consents "
                               "WHERE signer_id = %s",
                               (signer_with_account["signer_id"],))
        legal.record_consent(signer_with_account["user_id"], "data_contribution",
                             str(doc["version"]))
        with system_scope("test read"):
            second = _fetch_all("SELECT consent_id, granted_at FROM signer_consents "
                                "WHERE signer_id = %s",
                                (signer_with_account["signer_id"],))

        assert len(second) == 1
        assert second[0]["consent_id"] == first[0]["consent_id"]
        assert second[0]["granted_at"] == first[0]["granted_at"]

    def test_rut_thi_cong_chan_ngay_o_muc_noi_bo(self, signer_with_account, monkeypatch):
        """Rút phải TỚI ĐƯỢC đường dữ liệu — đúng cái lỗ hổng module này bịt."""
        from app import legal

        doc = legal.current_document("data_contribution")
        if doc is None:
            pytest.skip("chua cong bo data_contribution tren ban sao nay")
        legal.record_consent(signer_with_account["user_id"], "data_contribution",
                             str(doc["version"]))
        legal.withdraw_consent(signer_with_account["user_id"], "data_contribution")

        monkeypatch.setenv("CONSENT_GRANDFATHER_INTERNAL", "1")  # kế thừa BẬT
        out = cg.filter_rows([_row("a", signer_with_account["signer_id"])],
                             scope="internal_training",
                             tenant_id=signer_with_account["tenant"])
        assert out.kept == [], "da rut ma van lot, ke ca khi ke thua dang bat"
        assert out.reasons == {cg.REASON_WITHDRAWN: 1}
