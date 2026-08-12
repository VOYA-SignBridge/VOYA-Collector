"""Văn bản pháp lý là TỆP, không phải markdown gõ trong ứng dụng.

Văn bản pháp lý thật không ra đời trong một ô soạn markdown: phòng pháp chế gửi
`.docx`, bản đã ký và đóng dấu về dưới dạng `.pdf`. Bộ này canh ba nhóm tính
chất, và nhóm thứ ba là nhóm dễ mất nhất khi thêm một đường lưu trữ mới.

1. **Đường cũ không hỏng.** Bốn văn bản đã công bố mang thân markdown và có chữ
   ký trỏ vào băm của thân đó. Một cột NOT NULL hay một `body_format` bị siết
   thêm sẽ giết chúng, và cái chết đó chỉ lộ ra khi có người mở trang.
2. **Băm mô tả đúng thứ người ta ký.** `content_hash` của bản tệp phải là băm
   BYTE CỦA TỆP. Đây là giá trị `user_consents` trỏ tới; băm sai thứ nghĩa là
   một chữ ký không đối chiếu được với bất cứ cái gì.
3. **Đường phục vụ tệp không tự biến thành đường phục vụ bất cứ thứ gì.**
"""

from __future__ import annotations

import uuid

import pytest

from app import legal, legal_store
from app.storage.metadata_db import _execute
from app.tenant_context import system_scope


# Một PDF hợp lệ tối thiểu. Dùng byte thật chứ không phải `b"gia bo"`: đường đi
# qua băm, qua đĩa và qua header HTTP, và một chuỗi ASCII sẽ giấu mất bất kỳ chỗ
# nào lỡ ép sang str.
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"
       b"\x00\x01\x02\xff\xfe\n%%EOF\n")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    from app.storage.metadata_db import ensure_tables

    ensure_tables()


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Kho blob riêng cho mỗi test. KHÔNG ghi vào kho thật —
    `dataset/legal/` mang bản văn của bốn tài liệu đang có chữ ký."""
    monkeypatch.setenv("LEGAL_STORE_ROOT", str(tmp_path / "legal"))
    return tmp_path / "legal"


@pytest.fixture
def published():
    """Dọn mọi bản do test này công bố, kể cả khi test đổ giữa chừng."""
    versions: list = []
    yield versions
    with system_scope("test cleanup: legal files"):
        for kind, version in versions:
            _execute("DELETE FROM legal_documents WHERE kind = %s AND version = %s",
                     (kind, version))


def _version() -> str:
    return f"test-{uuid.uuid4().hex[:10]}"


class TestKhoBlobNhiPhan:
    def test_ghi_va_doc_lai_dung_tung_byte(self, store):
        key, digest, size = legal_store.write_bytes("terms", PDF, ".pdf")
        assert legal_store.read_bytes(key) == PDF
        assert size == len(PDF)
        assert key.endswith(".pdf")
        assert digest in key

    def test_cung_noi_dung_thi_khong_ghi_them_lan_nao(self, store):
        """Khử trùng lặp là tính chất của kho định-địa-chỉ-bằng-nội-dung. Công
        bố lại đúng tệp cũ không được tốn thêm byte nào."""
        k1, d1, _ = legal_store.write_bytes("terms", PDF, ".pdf")
        k2, d2, _ = legal_store.write_bytes("terms", PDF, ".pdf")
        assert (k1, d1) == (k2, d2)

    @pytest.mark.parametrize("name", ["hop_dong.exe", "a.svg", "b.html", "khong_duoi"])
    def test_tu_choi_duoi_ngoai_danh_sach_trang(self, name):
        """Danh sách TRẮNG, không phải đen. `.svg` chạy được script khi mở
        trực tiếp; `.html` thì khỏi bàn."""
        with pytest.raises(ValueError):
            legal_store.normalize_extension(name)

    def test_kieu_noi_dung_suy_tu_DUOI_KHOA_chu_khong_tu_ai_khai(self, store):
        key, _, _ = legal_store.write_bytes("terms", PDF, ".pdf")
        assert legal_store.content_type_for(key) == "application/pdf"
        # Khoá lạ (hàng bị sửa tay) không bao giờ ra một kiểu thi hành được.
        assert legal_store.content_type_for("terms/ab/abc.exe") == "application/octet-stream"

    def test_tep_qua_lon_bi_tu_choi(self, store):
        big = b"x" * (legal_store.MAX_FILE_BYTES + 1)
        with pytest.raises(ValueError):
            legal_store.write_bytes("terms", big, ".pdf")

    def test_iter_keys_THAY_ca_tep_khong_phai_markdown(self, store):
        """Bản đầu chỉ tìm `*.md`. Khi kho nhận PDF, những tệp đó biến mất khỏi
        tầm nhìn của `collect_garbage` — hỏng về phía an toàn, nhưng một tệp
        không ai trỏ tới sẽ nằm lại vĩnh viễn và lượt kiểm toàn vẹn báo 'sạch'
        mà chưa nhìn nó lần nào."""
        legal_store.write_bytes("terms", PDF, ".pdf")
        legal_store.write("terms", "# van ban markdown")
        keys = list(legal_store.iter_keys())
        assert any(k.endswith(".pdf") for k in keys)
        assert any(k.endswith(".md") for k in keys)


class TestCongBoBangTep:
    def test_bam_la_bam_BYTE_CUA_TEP(self, store, published):
        """`content_hash` là giá trị `user_consents` trỏ tới. Băm sai thứ nghĩa
        là một chữ ký không đối chiếu được với bất cứ cái gì."""
        import hashlib

        v = _version()
        published.append(("terms", v))
        legal.register_document("terms", v, url="/legal/terms", body="",
                                file_bytes=PDF, file_name="dieu-khoan.pdf")
        doc = legal.admin_read_document("terms", v)
        assert doc["content_hash"] == hashlib.sha256(PDF).hexdigest()

    def test_ghi_du_sieu_du_lieu_tep(self, store, published):
        v = _version()
        published.append(("privacy", v))
        legal.register_document("privacy", v, url="/legal/privacy", body="",
                                file_bytes=PDF, file_name="Chinh Sach.pdf")
        doc = legal.admin_read_document("privacy", v)
        assert doc["body_format"] == "file"
        assert doc["file_name"] == "Chinh Sach.pdf"
        assert doc["file_mime"] == "application/pdf"
        assert doc["file_size"] == len(PDF)
        assert legal_store.read_bytes(doc["file_key"]) == PDF

    def test_tep_rong_bi_tu_choi(self, store, published):
        with pytest.raises(legal.ConsentError):
            legal.register_document("terms", _version(), url="/legal/terms",
                                    body="", file_bytes=b"", file_name="a.pdf")

    def test_duoi_khong_hop_le_bi_tu_choi_TRUOC_khi_ghi_dia(self, store, published):
        """Từ chối phải xảy ra trước lượt ghi. Ghi rồi mới từ chối để lại một
        blob mồ côi cho mỗi lần người dùng chọn nhầm tệp."""
        with pytest.raises(legal.ConsentError):
            legal.register_document("terms", _version(), url="/legal/terms",
                                    body="", file_bytes=PDF, file_name="virus.exe")
        assert list(legal_store.iter_keys()) == []


class TestDuongMarkdownCuKhongHong:
    """Bốn văn bản đã công bố mang thân markdown và có chữ ký trỏ vào băm của
    thân đó. Đây là nhóm test tồn tại để một đường lưu trữ MỚI không giết
    đường CŨ trong im lặng."""

    def test_van_cong_bo_duoc_bang_markdown(self, store, published):
        v = _version()
        published.append(("terms", v))
        legal.register_document("terms", v, url="/legal/terms",
                                body="# Dieu khoan\n\nNoi dung.")
        doc = legal.admin_read_document("terms", v)
        assert doc["body_format"] == "markdown"
        assert doc["body"].startswith("# Dieu khoan")

    def test_ban_markdown_KHONG_co_cot_tep(self, store, published):
        """NULL, không phải chuỗi rỗng. Chuỗi rỗng làm `has_file` ở giao diện
        phải kiểm hai giá trị, và một trong hai sẽ bị quên."""
        v = _version()
        published.append(("privacy", v))
        legal.register_document("privacy", v, url="/legal/privacy", body="noi dung")
        doc = legal.admin_read_document("privacy", v)
        assert doc["file_key"] is None
        assert doc["file_name"] is None
        assert doc["file_size"] is None

    def test_bam_cua_ban_markdown_van_la_bam_UTF8_cua_than_bai(self, store, published):
        """Đổi cách tính băm sẽ làm mọi chữ ký đã thu trỏ vào hư không. Dòng
        này là thứ chặn việc đó."""
        v = _version()
        published.append(("terms", v))
        body = "# Dieu khoan\n\nNoi dung cu the."
        legal.register_document("terms", v, url="/legal/terms", body=body)
        doc = legal.admin_read_document("terms", v)
        assert doc["content_hash"] == legal.content_hash(body)

    def test_than_rong_van_bi_tu_choi_o_duong_markdown(self, store):
        with pytest.raises(legal.ConsentError):
            legal.register_document("terms", _version(), url="/legal/terms", body="   ")
