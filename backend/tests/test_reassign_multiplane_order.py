"""T3 — thứ tự ghi hai mặt phẳng của `sync_reassign_sample`.

Chạy:
    bash scripts/run_tests.sh tests/test_reassign_multiplane_order.py -v -s

Lỗi được đo ngày 15/08/2026
===========================
Một lượt đổi nhãn xuyên tenant bị PostgreSQL từ chối (`fk_samples_class_tenant`)
vẫn để lại hệ thống ĐÃ THAY ĐỔI:

    HTTP 400          người gọi thấy "thất bại"
    PostgreSQL        không đổi
    samples.csv       ĐÃ ĐỔI, không hoàn nguyên
    tệp .npz          đã về chỗ cũ  -> `file_path` treo

Nguyên nhân là thứ tự: `_write_samples_csv()` chạy TRƯỚC `db_upsert_sample()`,
còn khối `except` chỉ hoàn nguyên phần TỆP. Và vì đường đọc lấy dữ liệu từ CSV,
tenant B nhìn thấy mẫu của A trong lớp của B — do một request đã báo lỗi.

Vì sao TIÊM LỖI chứ không dựng một ràng buộc thật
=================================================
Điều cần kiểm là VŨ ĐẠO, không phải một ràng buộc cụ thể:

    di chuyển tệp -> PostgreSQL từ chối -> hoàn nguyên tệp -> CSV KHÔNG bị chạm

Dựng một ràng buộc thật để nó từ chối sẽ trói phép thử vào đúng một ràng buộc
đang tồn tại. Đổi tên `fk_samples_class_tenant`, hay thêm một đường từ chối
khác, thì phép thử ngừng kiểm thứ nó tuyên bố kiểm — trong khi vẫn xanh. Tiêm
lỗi ở đúng chỗ PostgreSQL được gọi kiểm được bất biến cho MỌI lý do từ chối.

Điều phép thử này KHÔNG chứng minh
==================================
Không phải nguyên tử đầy đủ. Chiều ngược lại vẫn hở:

    PostgreSQL đã commit  -> ghi CSV hỏng  -> lệch theo chiều ngược

Đóng hẳn cần staging/bù trừ hoặc một nguồn chân lý duy nhất. Xem `test_..._ghi_
CSV_hong_SAU_khi_DB_commit_van_lech` ở cuối tệp: nó ĐẶC TẢ khoảng hở còn lại
thay vì giả vờ nó không tồn tại.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import catalog_sync as cs
from app import export_tasks as et
from app.catalog_sync import CatalogSyncError


TENANT = "ten_a"


def _meta_dich(tmp_path: Path):
    tgt = tmp_path / "features" / "vn" / "common" / "class_tgt_TARGET00"
    return SimpleNamespace(
        class_uid="TARGET", slug="tgt", label_original="Target",
        language="vn", dialect="common",
        folder_name=lambda: "class_tgt_TARGET00",
        hierarchy_path=lambda: tgt,
    )


def _dung_canh(monkeypatch, tmp_path, *, db_hong: Exception | None = None,
               csv_hong: Exception | None = None):
    """Bịt mọi mối nối ngoài, và ghi lại THỨ TỰ hai mặt phẳng được ghi.

    `nhat_ky` là bằng chứng trực tiếp: một phép thử chỉ khẳng định "CSV không bị
    gọi" sẽ xanh cả khi thứ tự vẫn sai mà DB tình cờ không từ chối.
    """
    nhat_ky: list[str] = []

    monkeypatch.setattr(cs, "_catalog_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(cs, "ensure_tables", lambda: None)
    monkeypatch.setattr(cs, "slog", MagicMock())
    monkeypatch.setattr(cs, "_build_class_meta_from_row",
                        lambda row: _meta_dich(tmp_path))
    monkeypatch.setattr(cs, "_update_sample_metadata_json", lambda *a, **k: None)
    monkeypatch.setattr(cs, "_sync_drive_and_sheets_versioned_tables",
                        lambda *a, **k: None)
    monkeypatch.setattr(cs, "_google_drive_configured", lambda: False)

    def _labels(tenant_id):
        assert tenant_id == TENANT, f"load_labels goi voi tenant {tenant_id!r}"
        return [{"class_uid": "TARGET", "class_idx": "2"}]
    monkeypatch.setattr(cs, "load_labels", _labels)

    def _db(row):
        nhat_ky.append("db")
        if db_hong is not None:
            raise db_hong
    monkeypatch.setattr(cs, "db_upsert_sample", _db)

    def _csv(rows):
        nhat_ky.append("csv")
        if csv_hong is not None:
            raise csv_hong
    monkeypatch.setattr(cs, "_write_samples_csv", _csv)

    return SimpleNamespace(nhat_ky=nhat_ky)


def _mau(tmp_path: Path, uid: str = "S1"):
    old = tmp_path / "features" / "vn" / "bang" / "class_src" / f"{uid}.npz"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"real-data")
    return old, {"sample_uid": uid, "class_uid": "SOURCE", "tenant_id": TENANT,
                 "storage_key": f"features/vn/bang/class_src/{uid}.npz",
                 "storage_url": "", "file_path": str(old)}


def _gan_mau(monkeypatch, row):
    monkeypatch.setattr(cs, "list_samples", lambda tenant_id: [row])
    monkeypatch.setattr(cs, "_load_all_samples_unscoped", lambda: [row])


# ===========================================================================
# T3 — PostgreSQL từ chối: KHÔNG mặt phẳng bền vững nào được đổi
# ===========================================================================

def test_T3_DB_tu_choi_thi_CSV_KHONG_BAO_GIO_bi_ghi(monkeypatch, tmp_path):
    """★ Hồi quy trực tiếp của lỗi đo được 15/08/2026."""
    env = _dung_canh(monkeypatch, tmp_path,
                     db_hong=RuntimeError("fk_samples_class_tenant"))
    old, row = _mau(tmp_path)
    _gan_mau(monkeypatch, row)
    moi = tmp_path / "features" / "vn" / "common" / "class_tgt_TARGET00" / "S1.npz"

    with pytest.raises(Exception) as ei:
        cs.sync_reassign_sample("S1", "TARGET", tenant_id=TENANT)

    print(f"\n[evidence] loi={type(ei.value).__name__} nhat_ky={env.nhat_ky} "
          f"tep_cu_con={old.exists()} tep_moi_con={moi.exists()}")
    # PostgreSQL được hỏi TRƯỚC — nó là cửa ải, không phải bước cuối.
    assert env.nhat_ky == ["db"], f"thu tu sai: {env.nhat_ky}"
    # ★ CSV chưa từng bị chạm. Đây là dòng mà bản trước sẽ đỏ.
    assert "csv" not in env.nhat_ky
    # Tệp hoàn nguyên: `file_path` trong CSV vẫn trỏ đúng chỗ tệp đang nằm.
    assert old.exists(), "tep khong duoc hoan nguyen -> file_path treo"
    assert not moi.exists(), "tep con nam o lop dich sau mot luot da that bai"


def test_T3b_DB_tu_choi_thi_tep_ve_dung_cho_cu_nguyen_ven(monkeypatch, tmp_path):
    """Hoàn nguyên phải trả lại NỘI DUNG, không chỉ trả lại đường dẫn."""
    _dung_canh(monkeypatch, tmp_path, db_hong=RuntimeError("bi tu choi"))
    old, row = _mau(tmp_path, "S2")
    truoc = old.read_bytes()
    _gan_mau(monkeypatch, row)

    with pytest.raises(Exception):
        cs.sync_reassign_sample("S2", "TARGET", tenant_id=TENANT)

    print(f"\n[evidence] noi_dung_giu_nguyen={old.exists() and old.read_bytes() == truoc}")
    assert old.exists() and old.read_bytes() == truoc


def test_T4_duong_hop_le_ghi_DB_TRUOC_roi_moi_CSV(monkeypatch, tmp_path):
    """Đường thành công: cả hai mặt phẳng được ghi, và DB đi trước."""
    env = _dung_canh(monkeypatch, tmp_path)
    old, row = _mau(tmp_path, "S3")
    _gan_mau(monkeypatch, row)
    moi = tmp_path / "features" / "vn" / "common" / "class_tgt_TARGET00" / "S3.npz"

    ket = cs.sync_reassign_sample("S3", "TARGET", tenant_id=TENANT)

    print(f"\n[evidence] changed={ket['changed']} nhat_ky={env.nhat_ky} "
          f"tep_da_chuyen={moi.exists() and not old.exists()}")
    assert ket["changed"] is True
    assert env.nhat_ky == ["db", "csv"], f"thu tu sai: {env.nhat_ky}"
    assert moi.exists() and not old.exists()


# ===========================================================================
# Khoảng hở CÒN LẠI — đặc tả, không phải che giấu
# ===========================================================================

def test_ghi_CSV_hong_SAU_khi_DB_commit_van_lech(monkeypatch, tmp_path):
    """ĐẶC TẢ khoảng hở còn lại: đây KHÔNG phải hành vi mong muốn.

    Thứ tự mới đóng được chiều đã đo (DB từ chối -> CSV sạch). Chiều ngược lại
    vẫn hở: PostgreSQL đã ghi, rồi lượt ghi CSV hỏng, và hai mặt phẳng lệch —
    lần này CSDL mới là bên "đi trước".

    Phép thử này tồn tại để khoảng hở ấy là một tuyên bố có kiểm chứng chứ không
    phải một điều chưa ai để ý. Khi nào có staging/bù trừ (hoặc một nguồn chân
    lý duy nhất), phép thử này phải được VIẾT LẠI cho hành vi mới — nó đỏ lên là
    tín hiệu đúng, không phải hồi quy.
    """
    env = _dung_canh(monkeypatch, tmp_path, csv_hong=RuntimeError("dia day"))
    old, row = _mau(tmp_path, "S4")
    _gan_mau(monkeypatch, row)

    with pytest.raises(Exception):
        cs.sync_reassign_sample("S4", "TARGET", tenant_id=TENANT)

    print(f"\n[evidence] nhat_ky={env.nhat_ky} — DB da ghi, CSV thi khong. "
          f"Day la khoang ho da biet, chua duoc dong.")
    assert env.nhat_ky == ["db", "csv"]


# ===========================================================================
# P0-A — phân giải phải nằm TRONG phạm vi
# ===========================================================================

def test_thieu_tenant_thi_tu_choi_chu_khong_doc_toan_cuc(monkeypatch, tmp_path):
    _dung_canh(monkeypatch, tmp_path)
    _, row = _mau(tmp_path, "S5")
    _gan_mau(monkeypatch, row)

    with pytest.raises(CatalogSyncError) as ei:
        cs.sync_reassign_sample("S5", "TARGET", tenant_id="")

    print(f"\n[evidence] error_code={ei.value.error_code} status={ei.value.status_code}")
    assert ei.value.error_code == "TENANT_SCOPE_REQUIRED"


def test_mau_cua_tenant_khac_khong_phan_giai_duoc_va_KHONG_cham_tep(
        monkeypatch, tmp_path):
    """Cổng PHẠM VI ở phần ghi, kiểm riêng khỏi cổng quyền sở hữu.

    Vì sao cần phép thử này dù đã có ca T2 qua HTTP
    ----------------------------------------------
    Sau khi `_get_class_or_404` được đưa vào phạm vi, một lượt gọi HTTP nhắm vào
    lớp của tenant khác dừng ngay ở bước PHÂN GIẢI LỚP NGUỒN — trước khi chạm
    tới `sync_reassign_sample`. Đó là kết quả đúng, nhưng nó có nghĩa là ca T2
    không còn kiểm được cổng phạm vi Ở PHẦN GHI nữa.

    Hai cổng phải được chứng minh riêng. Gộp lại thì một ngày nào đó cổng đọc
    được nới ra (một endpoint quản trị mới, một đường xuất) và cổng ghi hoá ra
    chưa bao giờ có ai kiểm.

    Cũng khẳng định KHÔNG có tác dụng phụ: mẫu ngoài phạm vi phải bị từ chối
    trước khi có bất kỳ thao tác tệp nào — tồn tại của tệp không được rò ra
    thành một kênh phụ.
    """
    env = _dung_canh(monkeypatch, tmp_path)
    cua_ben_kia = tmp_path / "features" / "vn" / "bang" / "class_src" / "S7.npz"
    cua_ben_kia.parent.mkdir(parents=True, exist_ok=True)
    cua_ben_kia.write_bytes(b"du lieu cua tenant khac")
    # Kho CHỈ trả về thứ trong phạm vi: mẫu của tenant khác không có ở đây, đúng
    # như `list_samples(scope)` thật sẽ hành xử.
    monkeypatch.setattr(cs, "list_samples", lambda tenant_id: [])
    monkeypatch.setattr(cs, "_load_all_samples_unscoped",
                        lambda: [{"sample_uid": "S7", "tenant_id": "ten_b"}])

    with pytest.raises(CatalogSyncError) as ei:
        cs.sync_reassign_sample("S7", "TARGET", tenant_id=TENANT)

    print(f"\n[evidence] error_code={ei.value.error_code} nhat_ky={env.nhat_ky} "
          f"tep_cua_ben_kia_con_nguyen={cua_ben_kia.exists()}")
    assert ei.value.error_code == "SAMPLE_NOT_FOUND"
    assert env.nhat_ky == [], "da ghi mat phang nao do cho mot mau ngoai pham vi"
    assert cua_ben_kia.exists(), "tep cua tenant khac bi cham"


def test_lop_dich_ngoai_pham_vi_khong_phan_biet_voi_lop_khong_ton_tai(
        monkeypatch, tmp_path):
    """Hai câu hỏi khác nhau phải cho CÙNG một câu trả lời.

    Nếu "lớp của tenant khác" trả khác "lớp không tồn tại", thì endpoint trở
    thành một phép thử tồn tại: người gọi dò được tenant khác có lớp nào, mà
    không cần đọc được lớp ấy.
    """
    _dung_canh(monkeypatch, tmp_path)
    _, row = _mau(tmp_path, "S6")
    _gan_mau(monkeypatch, row)

    loi = {}
    for ten, ref in (("ngoai_pham_vi", "LOP_CUA_TENANT_KHAC"),
                     ("khong_ton_tai", "LOP_KHONG_TON_TAI_0000")):
        with pytest.raises(CatalogSyncError) as ei:
            cs.sync_reassign_sample("S6", ref, tenant_id=TENANT)
        loi[ten] = (ei.value.status_code, ei.value.error_code)

    print(f"\n[evidence] {loi}")
    assert loi["ngoai_pham_vi"] == loi["khong_ton_tai"]
    assert loi["ngoai_pham_vi"][1] == "CLASS_NOT_FOUND"
