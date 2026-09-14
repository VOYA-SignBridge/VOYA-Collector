"""Học ký hiệu — danh mục QIPEDC và API công khai."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import learn_catalog


class TestDanhMuc:
    def test_slug_bo_dau_va_d_gach(self):
        assert learn_catalog.slugify("Địa chỉ") == "dia-chi"
        assert learn_catalog.slugify("cảm ơn") == "cam-on"

    def test_gop_bien_the_vung_cua_cung_mot_tu(self):
        w = learn_catalog.get("dia-chi")
        assert w is not None and w["word"] == "địa chỉ"
        regions = {v["region"] for v in w["variants"]}
        assert {"bac", "nam"} <= regions
        assert all(v["video_url"].startswith("https://qipedc.moet.gov.vn/videos/") for v in w["variants"])

    def test_tim_khong_dau_khop_dau_tu_truoc(self):
        hits = learn_catalog.search("chao", limit=10)
        assert hits and hits[0]["slug"].startswith("chao")
        assert any(h["word"] == "chào" for h in hits)

    def test_loc_theo_vung(self):
        hits = learn_catalog.search("", region="trung", limit=200)
        assert hits and all(any(v["region"] == "trung" for v in h["variants"]) for h in hits)

    def test_khong_co_thi_None(self):
        assert learn_catalog.get("khong-ton-tai-xyz") is None

    def test_danh_muc_du_lon(self):
        c = learn_catalog.count()
        assert c["entries"] >= 4000 and c["words"] >= 3000


@pytest.mark.integration
class TestApiCongKhai:
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_khach_vang_lai_tim_duoc(self, client):
        r = client.get("/api/v1/learn/signs", params={"q": "dia chi"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"][0]["slug"] == "dia-chi"
        assert "QIPEDC" in body["attribution"]
        # "đã có mẫu" chỉ tính tenant công bố, kèm số mẫu đã duyệt.
        assert "own_sample_count" in body["items"][0]

    def test_mot_ky_hieu(self, client):
        r = client.get("/api/v1/learn/sign", params={"slug": "dia-chi"})
        assert r.status_code == 200
        assert r.json()["word"] == "địa chỉ"

    def test_khong_co_thi_404_co_cau_tieng_viet(self, client):
        r = client.get("/api/v1/learn/sign", params={"slug": "khong-ton-tai"})
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "not_found"

    def test_vung_la_bi_tu_choi(self, client):
        r = client.get("/api/v1/learn/signs", params={"region": "tay"})
        assert r.status_code == 422
