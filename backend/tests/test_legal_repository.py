"""Kho văn bản pháp lý: lưu nguyên văn, bất biến, hẹn giờ, và đọc lại được.

Tệp này canh phần v5 thêm vào. Phần chấp thuận và cưỡng chế lúc đăng ký nằm ở
`test_legal_consent.py`; ranh giới giữa hai tệp là: ở kia hỏi *"chữ ký có được
ghi đúng không"*, ở đây hỏi *"bản văn được ký có còn đọc lại được nguyên vẹn
không"*.

Tính chất trung tâm, và là lý do phần lớn phần còn lại tồn tại: **một dòng
`user_consents` trỏ tới `(kind, version)`, nên nếu bản văn ứng với cặp đó không
đọc lại được thì dòng ấy chỉ là một con số.** Trước v5 nó đúng là một con số —
`register_document` băm nội dung rồi vứt.

Bố cục: mỗi lớp một tính chất, mỗi test một hành vi. Mỗi test tự dựng dữ liệu
của nó và không đọc trạng thái test khác để lại.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import legal
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


# ---------------------------------------------------------------------------
# Dụng cụ
# ---------------------------------------------------------------------------
#
# Tệp này KHÔNG xoá sạch `legal_documents`. `test_legal_consent.py` phải làm vậy
# vì nó kiểm hành vi "chưa công bố gì", và nó trả bảng lại nguyên trạng ở cuối
# module. Ở đây không cần bảng rỗng, nên cách an toàn hơn là mỗi test dùng một
# số hiệu phiên bản của riêng nó và dọn đúng số hiệu đó.

def _version() -> str:
    return f"test-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def published():
    """Công bố văn bản và dọn đúng những bản mình đã công bố.

    Trả về một hàm chứ không một bản ghi: phần lớn test ở đây cần từ hai bản
    trở lên để nói được điều gì đó về phiên bản.
    """
    created: list[tuple[str, str]] = []

    def _publish(kind: str = "terms", *, version: str | None = None,
                 body: str = "Nội dung bản thử.", **kwargs):
        version = version or _version()
        doc = legal.register_document(
            kind, version, url=f"/legal/{kind}", body=body, **kwargs)
        created.append((kind, version))
        return version, doc

    yield _publish

    with system_scope("test cleanup: gỡ đúng những bản test này công bố"):
        for kind, version in reversed(created):
            db._execute(
                "DELETE FROM user_consents WHERE kind = %s AND version = %s",
                (kind, version))
            db._execute(
                "DELETE FROM legal_documents WHERE kind = %s AND version = %s",
                (kind, version))


@pytest.fixture
def account():
    from app.auth import create_user

    name = f"lgr{uuid.uuid4().hex[:9]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield user
    from conftest import purge_registered_account

    purge_registered_account(name)


def _anon() -> TestClient:
    from conftest import LoopbackPeer
    from app.main import app

    return TestClient(LoopbackPeer(app))


# ===========================================================================
# Thân văn bản được lưu và đọc lại được
# ===========================================================================

class TestTheBodyIsStored:
    def test_readDocument_afterPublishing_returnsTheBodyVerbatim(self, published):
        """Tính chất trung tâm của cả v5.

        Trước v5 test này không viết được: `register_document` nhận `body` chỉ
        để băm, và không hàm nào trả nội dung về.
        """
        body = "# Điều khoản\n\nĐoạn một.\n\n- gạch đầu dòng\n"
        version, _ = published(body=body)

        doc = legal.read_document("terms", version)

        assert doc is not None
        assert doc["body"] == body

    def test_readDocument_withNoVersion_returnsTheEffectiveOne(self, published):
        published(version="v-old", body="Bản cũ.")
        published(version="v-new", body="Bản mới.")

        doc = legal.read_document("terms")

        assert doc is not None and doc["body"] == "Bản mới."

    def test_readDocument_forASupersededVersion_stillReturnsIt(self, published):
        """Người đã ký bản cũ phải đọc lại được đúng bản MÌNH ký.

        Đây là điều phân biệt một kho văn bản với một biến "nội dung hiện tại".
        """
        published(version="v-signed", body="Bản người ta đã ký.")
        published(version="v-later", body="Bản thay thế.")

        doc = legal.read_document("terms", "v-signed")

        assert doc is not None and doc["body"] == "Bản người ta đã ký."

    def test_contentHash_matchesTheStoredBody(self, published):
        """Hash phải đối chiếu được với thứ ĐANG nằm trong bảng.

        Trước v5 hash tính từ một chuỗi rồi chuỗi ấy biến mất, nên không có gì
        để đối chiếu — hash tồn tại mà không kiểm được điều gì.
        """
        version, _ = published(body="Nội dung để băm.")

        doc = legal.read_document("terms", version)

        assert doc is not None
        assert doc["content_hash"] == legal.content_hash(doc["body"])

    def test_registerDocument_withAnEmptyBody_isRefused(self):
        """Công bố một bản rỗng là thu chữ ký cho khoảng trắng."""
        with pytest.raises(legal.ConsentError) as exc:
            legal.register_document("terms", _version(), url="/legal/terms",
                                    body="   \n  ")

        assert exc.value.code == "empty_body"

    def test_registerDocument_withAnUnknownFormat_isRefused(self):
        with pytest.raises(legal.ConsentError) as exc:
            legal.register_document("terms", _version(), url="/legal/terms",
                                    body="x", body_format="docx")

        assert exc.value.code == "unknown_format"


# ===========================================================================
# Bất biến — cưỡng chế ở tầng cơ sở dữ liệu, không phải ở quy ước ứng dụng
# ===========================================================================

class TestThePublishedTextCannotBeRewritten:
    """`register_document` đã từ chối ghi đè và có test ghim điều đó. Lớp này
    kiểm hàng rào THỨ HAI: trigger trên bảng.

    Vì sao cần cả hai: phép kiểm ở ứng dụng chỉ bảo vệ đường đi qua ứng dụng.
    Một lệnh `psql` lúc vận hành, một script sửa dữ liệu, hay một migration
    tương lai viết ẩu đều đi vòng qua nó. Bất biến này đáng nằm ở cơ sở dữ liệu
    chính vì giá trị của nó là đúng KỂ CẢ khi mã ứng dụng sai.
    """

    def test_updatingTheBody_raises(self, published):
        version, _ = published(body="Bản gốc.")

        with pytest.raises(Exception) as exc:
            with system_scope("test: thử sửa lén thân văn bản"):
                db._execute(
                    "UPDATE legal_documents SET body = %s WHERE version = %s",
                    ("Đã bị sửa.", version))

        assert "chi-them" in str(exc.value)

    def test_updatingTheContentHash_raises(self, published):
        """Sửa riêng hash cũng phải chặn: nó là cách làm cho một thân đã bị đổi
        trông như khớp."""
        version, _ = published()

        with pytest.raises(Exception):
            with system_scope("test: thử sửa lén hash"):
                db._execute(
                    "UPDATE legal_documents SET content_hash = %s WHERE version = %s",
                    ("0" * 64, version))

    def test_updatingTheVersionNumber_raises(self, published):
        version, _ = published()

        with pytest.raises(Exception):
            with system_scope("test: thử đổi số hiệu"):
                db._execute(
                    "UPDATE legal_documents SET version = %s WHERE version = %s",
                    (_version(), version))

    def test_updatingTheTitle_isAllowed(self, published):
        """Phản chứng. Không có nó, ba test trên vẫn xanh khi trigger chặn MỌI
        lượt ghi — và một bảng không sửa được gì cả thì không sửa nổi cả lỗi
        chính tả ở tiêu đề."""
        version, _ = published(title="Tiêu đề gõ nhầm")

        with system_scope("test: sửa tiêu đề, việc hợp lệ"):
            db._execute("UPDATE legal_documents SET title = %s WHERE version = %s",
                        ("Tiêu đề đúng", version))

        doc = legal.read_document("terms", version)
        assert doc is not None and doc["title"] == "Tiêu đề đúng"

    def test_reschedulingADocumentThatIsAlreadyEffective_raises(self, published):
        """Dời ngày hiệu lực của một bản ĐANG áp dụng là viết lại câu trả lời
        cho "hôm đó bản nào đang áp dụng"."""
        version, _ = published()

        with pytest.raises(Exception) as exc:
            with system_scope("test: thử dời ngày hiệu lực về quá khứ"):
                db._execute(
                    "UPDATE legal_documents SET effective_from = now() - interval "
                    "'10 days' WHERE version = %s", (version,))

        assert "effective_from" in str(exc.value)

    def test_reschedulingADocumentThatIsNotYetEffective_isAllowed(self, published):
        """Ranh giới là THỜI ĐIỂM, không phải bản thân cột.

        Một bản hẹn cho tháng sau chưa nói gì với ai; dời nó là lên lịch lại.
        """
        later = datetime.now(timezone.utc) + timedelta(days=30)
        version, _ = published(effective_from=later)

        moved = datetime.now(timezone.utc) + timedelta(days=60)
        with system_scope("test: dời lịch một bản chưa tới hạn"):
            db._execute(
                "UPDATE legal_documents SET effective_from = %s WHERE version = %s",
                (moved, version))

        doc = legal.admin_read_document("terms", version)
        assert doc is not None
        assert doc["effective_from"].date() == moved.date()


# ===========================================================================
# Hẹn giờ
# ===========================================================================

class TestSchedulingAFutureVersion:
    def test_currentDocument_ignoresAVersionScheduledForTheFuture(self, published):
        published(version="v-now", body="Bản đang áp dụng.")
        published(version="v-later", body="Bản sắp tới.",
                  effective_from=datetime.now(timezone.utc) + timedelta(days=7))

        assert legal.current_document("terms")["version"] == "v-now"

    def test_readDocument_refusesToServeAFutureVersionEvenByName(self, published):
        """Đường đọc công khai không được rò bản điều khoản sắp đổi ra ngoài
        trước khi tổ chức kịp thông báo — kể cả khi người gọi đoán trúng số
        hiệu."""
        published(version="v-secret", body="Chưa công bố.",
                  effective_from=datetime.now(timezone.utc) + timedelta(days=7))

        assert legal.read_document("terms", "v-secret") is None

    def test_adminReadDocument_seesTheFutureVersion(self, published):
        """Phản chứng của test trên, và là lý do `admin_read_document` tồn tại:
        người soạn phải đọc lại được bản mình vừa hẹn giờ."""
        published(version="v-secret", body="Chưa công bố.",
                  effective_from=datetime.now(timezone.utc) + timedelta(days=7))

        doc = legal.admin_read_document("terms", "v-secret")

        assert doc is not None and doc["body"] == "Chưa công bố."

    def test_listDocuments_marksWhichVersionsAreEffective(self, published):
        published(version="v-live", body="Đang dùng.")
        published(version="v-pending", body="Hẹn giờ.",
                  effective_from=datetime.now(timezone.utc) + timedelta(days=7))

        rows = {r["version"]: r for r in legal.list_documents("terms")}

        assert rows["v-live"]["is_effective"] is True
        assert rows["v-pending"]["is_effective"] is False


# ===========================================================================
# Liệt kê và đếm chữ ký
# ===========================================================================

class TestListingCountsSignatures:
    def test_listDocuments_countsLiveConsentsPerVersion(self, published, account):
        version, _ = published()
        legal.record_consent(account["id"], "terms", version)

        row = next(r for r in legal.list_documents("terms")
                   if r["version"] == version)

        assert row["consent_count"] == 1

    def test_listDocuments_doesNotCountWithdrawnConsents(self, published, account):
        """Con số này tồn tại để trả lời "xoá bản này có an toàn không". Đếm cả
        chữ ký đã rút sẽ nói không an toàn trong khi khoá ngoại vẫn chặn — hai
        câu trả lời khác nhau cho hai câu hỏi khác nhau, và câu ở đây là câu về
        chấp thuận còn hiệu lực."""
        first, _ = published(version="v-1", body="Một.")
        legal.record_consent(account["id"], "terms", first)
        second, _ = published(version="v-2", body="Hai.")
        legal.record_consent(account["id"], "terms", second)

        rows = {r["version"]: r for r in legal.list_documents("terms")}

        assert rows["v-1"]["consent_count"] == 0
        assert rows["v-2"]["consent_count"] == 1

    def test_listDocuments_reportsBodyLengthWithoutShippingTheBody(self, published):
        """Trang quản trị cần biết bản văn dài bao nhiêu; nó không cần tải cả
        bốn bản văn về để dựng một cái bảng."""
        version, _ = published(body="x" * 500)

        row = next(r for r in legal.list_documents("terms")
                   if r["version"] == version)

        assert row["body_length"] == 500
        assert "body" not in row


# ===========================================================================
# Xuất xứ của một chấp thuận
# ===========================================================================

class TestConsentProvenance:
    def test_recordConsent_defaultsToTheUserSource(self, published, account):
        version, _ = published()
        legal.record_consent(account["id"], "terms", version)

        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT source FROM user_consents WHERE user_id = %s",
                (account["id"],))[0]

        assert row["source"] == "user"

    def test_recordConsent_withAnUnknownSource_isRefused(self, published, account):
        version, _ = published()

        with pytest.raises(legal.ConsentError) as exc:
            legal.record_consent(account["id"], "terms", version,
                                 source="tu-nghi-ra", note="x")

        assert exc.value.code == "unknown_source"

    def test_recordConsent_withABackfillSourceAndNoNote_isRefused(
        self, published, account
    ):
        """Ranh giới đạo đức của cả tính năng ghi hộ.

        Một dòng ghi hộ không giải thích được thì sáu tháng sau không ai đọc ra
        vì sao nó ở đó, và nó sẽ bị đọc nhầm thành chữ ký thật.
        """
        version, _ = published()

        with pytest.raises(legal.ConsentError) as exc:
            legal.record_consent(account["id"], "terms", version, source="backfill")

        assert exc.value.code == "note_required"

    def test_recordConsent_withABackfillSourceAndANote_storesBoth(
        self, published, account
    ):
        version, _ = published()

        legal.record_consent(account["id"], "terms", version, source="backfill",
                             note="tài khoản nội bộ, đã đồng ý ngoài hệ thống")

        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT source, note FROM user_consents WHERE user_id = %s",
                (account["id"],))[0]

        assert row["source"] == "backfill"
        assert "nội bộ" in row["note"]

    def test_consentCoverage_reportsUserSignaturesSeparatelyFromBackfills(
        self, published, account
    ):
        """Hai con số, vì hai loại bằng chứng.

        Gộp chúng lại là để một bảng điều khiển báo "100% đã đồng ý" trong khi
        không ai bấm nút nào.
        """
        version, _ = published()
        legal.record_consent(account["id"], "terms", version, source="backfill",
                             note="ghi hộ")

        row = next(r for r in legal.consent_coverage() if r["kind"] == "terms")

        assert row["accepted"] >= 1
        assert row["accepted_by_user"] < row["accepted"]

    def test_consentCoverage_stopsCountingStaleConsentsAfterAReconsentRelease(
        self, published, account
    ):
        """Độ phủ phải khớp ĐỊNH NGHĨA của `has_consent`, không được lỏng hơn.

        Đếm lỏng hơn nghĩa là ngay sau một lần công bố `requires_reconsent`,
        bảng báo phủ 100% đúng vào lúc thực tế là 0% và mọi người đang bị đá ra
        màn hình đồng ý — con số nói ngược lại điều đang xảy ra, đúng thời điểm
        người vận hành cần nó nhất.
        """
        old, _ = published(version="v-old", body="Bản cũ.")
        legal.record_consent(account["id"], "terms", old)
        before = next(r for r in legal.consent_coverage() if r["kind"] == "terms")
        assert before["accepted"] >= 1, "chấp thuận vừa ghi không được đếm"
        assert legal.has_consent(account["id"], "terms") is True

        published(version="v-new", body="Phạm vi mới.", requires_reconsent=True)

        after = next(r for r in legal.consent_coverage() if r["kind"] == "terms")

        # KHÔNG khẳng định `after == before - 1`.
        #
        # Phép trừ đó chỉ đúng nếu tài khoản của test là chấp thuận HỢP LỆ duy
        # nhất trong cơ sở dữ liệu. Bộ test chạy trên bản sao của dữ liệu thật,
        # nơi đã có sẵn hàng chục chấp thuận — và một lần công bố
        # `requires_reconsent` làm TẤT CẢ chúng cũ đi cùng lúc, không phải chỉ
        # một. Đo được 2026-08-09: 11 → 0, và test đỏ vì số học chứ không phải
        # vì hành vi.
        #
        # Điều cần ghim là điều docstring nói: chấp thuận cũ NGỪNG được đếm, và
        # con số của bảng khớp với định nghĩa của `has_consent`. Cả hai khẳng
        # định dưới đây đúng bất kể trong bảng có bao nhiêu dòng.
        assert after["accepted"] < before["accepted"], (
            "chấp thuận cho bản cũ vẫn được đếm sau một lần công bố "
            "requires_reconsent"
        )
        assert legal.has_consent(account["id"], "terms") is False
        assert after["missing"] > before["missing"]


# ===========================================================================
# Đường đọc công khai
# ===========================================================================

class TestThePublicReadSurface:
    def test_everyLegalKind_hasBothPublicPathsInTheGate(self):
        """Cổng khớp ĐƯỜNG NGUYÊN VĂN, không khớp template. Một `kind` mới thêm
        vào `legal.KINDS` mà quên hai dòng tương ứng sẽ bị 401 — hỏng an toàn,
        nhưng lặng lẽ."""
        from app.access_gate import PUBLIC_ROUTES

        for kind in legal.KINDS:
            assert ("GET", f"/legal/{kind}") in PUBLIC_ROUTES, kind
            assert ("GET", f"/legal/{kind}/content") in PUBLIC_ROUTES, kind

    def test_noPublicLegalPath_isParameterised(self):
        """Số hiệu phiên bản phải đi qua tham số TRUY VẤN, không phải một đoạn
        đường: cổng chạy trước định tuyến nên không đọc được template."""
        from app.access_gate import PUBLIC_ROUTES

        legal_paths = [p for _m, p in PUBLIC_ROUTES if p.startswith("/legal")]

        assert legal_paths
        assert not any("{" in p for p in legal_paths)

    def test_contentEndpoint_returnsTheBody(self, published):
        body = "# Điều khoản thử\n\nĐoạn văn."
        published(body=body)

        response = _anon().get("/api/v1/legal/terms/content")

        assert response.status_code == 200, response.text
        assert response.json()["body"] == body

    def test_contentEndpoint_withAVersion_returnsThatVersion(self, published):
        published(version="v-signed", body="Bản đã ký.")
        published(version="v-current", body="Bản hiện hành.")

        response = _anon().get(
            "/api/v1/legal/terms/content", params={"version": "v-signed"})

        assert response.status_code == 200, response.text
        assert response.json()["body"] == "Bản đã ký."

    def test_contentEndpoint_forAFutureVersion_is404(self, published):
        published(version="v-future", body="Chưa tới lúc.",
                  effective_from=datetime.now(timezone.utc) + timedelta(days=7))

        response = _anon().get(
            "/api/v1/legal/terms/content", params={"version": "v-future"})

        assert response.status_code == 404

    def test_documentsIndex_listsOnlyPublishedKinds(self, published):
        published("terms", body="Điều khoản.")

        response = _anon().get("/api/v1/legal/documents")

        assert response.status_code == 200, response.text
        kinds = [d["kind"] for d in response.json()["documents"]]
        assert "terms" in kinds
        assert len(kinds) == len(set(kinds)), "mỗi loại chỉ được một dòng"

    def test_metadataEndpoint_doesNotShipTheBody(self, published):
        """`/legal/{kind}` được gọi ở mỗi lần dựng biểu mẫu đăng ký. Kéo cả bản
        văn về chỉ để hiển thị một dòng "Tôi đồng ý với…" là trả giá băng thông
        cho thứ không ai đọc ở đường đó."""
        published(body="x" * 5000)

        response = _anon().get("/api/v1/legal/terms")

        assert response.status_code == 200
        assert "body" not in response.json()
