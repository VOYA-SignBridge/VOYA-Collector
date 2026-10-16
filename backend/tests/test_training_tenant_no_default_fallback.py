"""C1 — job huấn luyện thiếu tenant KHÔNG được rơi vào tenant seed.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_training_tenant_no_default_fallback.py -v -s

Bất biến
========
```
TrainingJob.tenant_id = ∅   ->  FAIL / KHÔNG GHI
                            ->  không bao giờ -> default
                            ->  không bao giờ -> community
                            ->  không bao giờ -> "system"
```

"Thiếu tenant" KHÔNG BAO GIỜ là cách ngầm để nói "toàn hệ thống". Nếu một ngày
có job thật sự thuộc hệ thống thì nó phải mang danh tính hệ thống TƯỜNG MINH,
đúng cách `platform_administrator` được tách khỏi `tenant_administrator` ở nhóm
B — chứ không biểu diễn bằng một ô trống.

Hai đường, hai mức nguy hiểm
============================
```
_emit_training_event      PHÁT   sự kiện của A tới webhook của tenant seed
_record_output_contract   GHI    hợp đồng lớp của A VÀO tenant seed
```

Đường thứ hai nặng hơn: nó làm `Train(A)` kết thúc bằng việc *làm biến đổi*
`default` — chiều ngược của bất biến "tenant kế thừa từ nguồn seed lúc TẠO,
không phụ thuộc động vào nó lúc CHẠY".

Vì sao `return` chứ không `raise`
=================================
Cả thân `_record_output_contract` nằm trong `except Exception` chỉ ghi cảnh báo
— có chủ ý, và chủ ý ấy đúng: đừng làm hỏng một job đã chạy xong và đã có
checkpoint trên đĩa chỉ vì một bảng phụ trợ không ghi được. Hệ quả là `raise` ở
đây sẽ bị NUỐT thành một dòng log và không đổi được gì.

Nên phân biệt hai loại hỏng:

```
lỗi ghi thoáng qua   ->  best effort, cảnh báo, job vẫn thành công
vi phạm hợp đồng     ->  KHÔNG ghi, ERROR, và tuyệt đối không ghi sang tenant khác
```

Đã kiểm: `_record_output_contract` là helper độc lập gọi ở
`training_tasks.py:507`. `_update_job(status="completed")` chạy TRƯỚC nó và
`_emit_training_event` chạy SAU nó, nên `return` sớm chỉ bỏ đúng bảng phụ trợ —
không bước chuyển trạng thái nào bị mất.
"""

from __future__ import annotations

import logging

import pytest

from app import training_tasks as tt


CKPT = "/tmp/khong-ton-tai.pt"


@pytest.fixture
def bat_emit(monkeypatch):
    """Bắt mọi lượt gọi `webhooks.emit` — kể cả lượt KHÔNG được phép xảy ra."""
    goi = []
    import app.webhooks as wh
    monkeypatch.setattr(wh, "emit", lambda t, e, p: goi.append((t, e, p)))
    return goi


@pytest.fixture
def bat_ghi_lop(monkeypatch):
    """Bắt `replace_training_job_classes` và giả lập checkpoint đọc được."""
    goi = []
    from app.storage import metadata_db as db
    monkeypatch.setattr(
        db, "replace_training_job_classes",
        lambda **kw: goi.append(kw))
    monkeypatch.setattr(
        "app.checkpoint_io.load_checkpoint",
        lambda p: {"idx_to_label": {0: "mot", 1: "hai"}})
    return goi


# =========================================================================
# _emit_training_event
# =========================================================================

def test_su_kien_di_dung_tenant_cua_job(bat_emit):
    tt._emit_training_event({"tenant_id": "iso_a"}, "training.completed", {"x": 1})
    print(f"\n[evidence] emit = {bat_emit}")
    assert len(bat_emit) == 1
    assert bat_emit[0][0] == "iso_a"


@pytest.mark.parametrize("gia_tri", [None, "", "   "])
def test_job_thieu_tenant_thi_KHONG_phat_su_kien(bat_emit, gia_tri, caplog):
    with caplog.at_level(logging.ERROR):
        tt._emit_training_event({"tenant_id": gia_tri}, "training.completed", {})
    print(f"\n[evidence] emit={bat_emit} log={[r.levelname for r in caplog.records]}")
    # ★ Không phát cho AI CẢ — đặc biệt không phát cho `default`.
    assert bat_emit == []
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "vi pham hop dong phai ghi o muc ERROR, khong phai WARNING")


def test_khong_phat_nham_vao_default_khi_key_vang_mat(bat_emit):
    """Hàng job không có KHOÁ `tenant_id` — khác với có khoá mà rỗng."""
    tt._emit_training_event({}, "training.completed", {})
    assert bat_emit == []


# =========================================================================
# _record_output_contract
# =========================================================================

def test_hop_dong_lop_ghi_dung_tenant_cua_job(bat_ghi_lop):
    tt._record_output_contract("job-1", {"tenant_id": "iso_a"}, CKPT)
    print(f"\n[evidence] ghi = {bat_ghi_lop}")
    assert len(bat_ghi_lop) == 1
    assert bat_ghi_lop[0]["tenant_id"] == "iso_a"
    assert bat_ghi_lop[0]["job_id"] == "job-1"


@pytest.mark.parametrize("gia_tri", [None, "", "   "])
def test_job_thieu_tenant_thi_KHONG_ghi_hop_dong_lop(bat_ghi_lop, gia_tri, caplog):
    """★ Hồi quy trực tiếp: `Train(A)` không được làm biến đổi `default`."""
    with caplog.at_level(logging.ERROR):
        tt._record_output_contract("job-2", {"tenant_id": gia_tri}, CKPT)
    print(f"\n[evidence] ghi={bat_ghi_lop} log={[r.levelname for r in caplog.records]}")
    # ★ KHÔNG một lượt ghi nào — `default` không bị chạm.
    assert bat_ghi_lop == []
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_thong_diep_loi_noi_ro_khong_ghi_vao_default(caplog):
    """Thông điệp phải nói ra điều đã KHÔNG làm, không chỉ nói "có lỗi".

    Người đọc log sáu tháng sau cần biết vì sao một job thành công lại thiếu
    hợp đồng đầu ra — và biết rằng dữ liệu đã KHÔNG rơi sang tenant khác.
    """
    with caplog.at_level(logging.ERROR):
        tt._record_output_contract("job-3", {}, CKPT)
    thong_diep = " ".join(r.getMessage() for r in caplog.records)
    print(f"\n[evidence] {thong_diep}")
    assert "default" in thong_diep.lower()
    assert "tenant_id" in thong_diep
