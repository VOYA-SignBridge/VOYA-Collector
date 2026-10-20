"""Cảnh báo GPU phải nói được VIỆC CẦN LÀM, không chỉ nói "hỏng".

Ngày 2026-08-09 hệ thống gửi đi một lá thư báo *"Nvidia GPU is missing or
unreadable"*. Máy chủ có một RTX 3050 nằm yên trong đó, NVIDIA Container Toolkit
chạy tốt, và lỗi thật là stack được dựng thiếu `docker-compose.gpu.yml` nên
container trainer không được cấp thiết bị. Người nhận thư đi tìm phần cứng;
phần cứng không phải chỗ hỏng.

Thiếu ảnh chụp trong Redis là câu trả lời chung cho ba tình huống rất khác nhau,
và bộ test này ghim việc chúng phải phân biệt được.
"""
from __future__ import annotations

import json
import time

import pytest

from app import monitoring


class _FakeRedis:
    def __init__(self, values: dict):
        self._values = values
        self.closed = False

    def get(self, key):
        return self._values.get(key)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_redis(monkeypatch):
    def _install(values: dict):
        client = _FakeRedis(values)
        monkeypatch.setattr(monitoring, "_redis_client", lambda: client)
        return client
    return _install


class TestBaTinhHuongPhaiPhanBietDuoc:
    def test_trainer_chay_nhung_khong_duoc_cap_thiet_bi(self, fake_redis):
        """Đúng sự cố 2026-08-09: có đèn báo vắng mặt = trainer sống và không
        thấy thiết bị nào → gợi ý phải nói tới overlay."""
        fake_redis({monitoring.GPU_ABSENCE_KEY: json.dumps(
            {"reason": "no_device_in_container", "ts": time.time()})})
        snap = monitoring.read_gpu_snapshot()
        assert snap["available"] is False
        assert snap["reason"] == "no_device_in_container"
        # Khẳng định theo Ý NGHĨA, không theo mặt chữ. Bản trước bắt đúng chuỗi
        # "docker-compose.gpu.yml", nên khi câu gợi ý được viết lại cho gọn —
        # bỏ dòng lệnh ba tệp, trỏ sang `scripts/deploy.sh` vốn tự dò card —
        # test đỏ dù nội dung đã TỐT HƠN. Một test khoá cứng câu chữ sẽ dạy
        # người sau rằng cách rẻ nhất để nó xanh lại là đừng sửa câu nào cả.
        hint = snap["hint"].lower()
        assert "overlay" in hint, "phải nói được rằng stack dựng thiếu overlay GPU"
        assert "deploy.sh" in hint, "và chỉ ra chỗ bật lại nó"

    def test_khong_ai_bao_cao_gi_ca(self, fake_redis):
        """Không ảnh chụp, không đèn → trainer có thể đã chết. Gợi ý phải bảo đi
        xem trainer còn sống không, KHÔNG bảo đi tìm cái card."""
        fake_redis({})
        snap = monitoring.read_gpu_snapshot()
        assert snap["reason"] == "no_snapshot"
        hint = snap["hint"].lower()
        assert "trainer" in hint, "phải trỏ vào trainer, nơi thật sự cần xem"
        # Điều quan trọng nhất của test này: KHÔNG được đổ cho phần cứng. Không
        # có ảnh chụp nghĩa là không ai báo cáo, chứ không phải không có card.
        assert "missing" not in hint
        assert "không có card" not in snap["hint"].lower()

    def test_redis_chet_thi_noi_la_su_co_redis(self, monkeypatch):
        monkeypatch.setattr(monitoring, "_redis_client", lambda: None)
        snap = monitoring.read_gpu_snapshot()
        assert snap["reason"] == "redis_unavailable"
        assert "Redis" in snap["hint"]


class TestAnhChupThatLuonThang:
    def test_co_anh_chup_thi_khong_hoi_den_bao_vang_mat(self, fake_redis):
        """Đèn có TTL dài hơn ảnh chụp (180s so với 15s), nên nó còn sống một
        lúc sau khi thiết bị quay lại. Nếu đèn thắng thì GPU vừa hồi phục sẽ
        vẫn bị báo là mất."""
        client = fake_redis({
            monitoring.GPU_SNAPSHOT_KEY: json.dumps(
                {"available": True, "name": "RTX 3050", "ts": time.time()}),
            monitoring.GPU_ABSENCE_KEY: json.dumps(
                {"reason": "no_device_in_container", "ts": time.time()}),
        })
        snap = monitoring.read_gpu_snapshot()
        assert snap["available"] is True
        assert snap["name"] == "RTX 3050"
        assert "hint" not in snap
        assert client.closed

    def test_anh_chup_hong_dinh_dang_thi_noi_dung_the(self, fake_redis):
        fake_redis({monitoring.GPU_SNAPSHOT_KEY: "{ khong phai json"})
        assert monitoring.read_gpu_snapshot()["reason"] == "parse_error"


class TestDenBaoVangMatChiTrainerMoiDuocThap:
    """Tín hiệu `worker_ready` nổ ở CẢ trình xử lý video lẫn trainer.

    Trình xử lý video không bao giờ có GPU và điều đó là bình thường. Cho nó
    thắp đèn thì mọi triển khai đều báo sự cố GPU vĩnh viễn.
    """

    def test_worker_thuong_khong_thap_den(self, monkeypatch):
        started = []
        monkeypatch.setattr(monitoring.shutil, "which", lambda _n: None)
        monkeypatch.setattr(monitoring.threading, "Thread",
                            lambda **kw: started.append(kw.get("name")) or _NoopThread())
        monkeypatch.setattr(monitoring, "_sampler_started", False)
        monitoring.start_gpu_monitor(is_trainer=False)
        assert started == []

    def test_trainer_thap_den(self, monkeypatch):
        started = []
        monkeypatch.setattr(monitoring.shutil, "which", lambda _n: None)
        monkeypatch.setattr(monitoring.threading, "Thread",
                            lambda **kw: started.append(kw.get("name")) or _NoopThread())
        monkeypatch.setattr(monitoring, "_sampler_started", False)
        monitoring.start_gpu_monitor(is_trainer=True)
        assert started == ["gpu-absence"]


class _NoopThread:
    def start(self):
        return None


class TestMoiLyDoDeuCoCauTraLoi:
    def test_khong_ly_do_nao_bi_bo_trong(self):
        """`metrics.py` tra bảng này để dựng `details` của cảnh báo. Một lý do
        thiếu gợi ý sẽ gửi đi đúng loại thư trống rỗng mà việc này ra đời để bỏ."""
        for reason in ("no_device_in_container", "no_snapshot", "redis_unavailable",
                       "redis_error", "parse_error"):
            assert monitoring.GPU_ABSENCE_HINTS.get(reason)
