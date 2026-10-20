"""Bản nháp, tranh chấp ghi, và sổ đăng bạ.

Tệp này canh mặt phẳng SỬA ĐƯỢC của phần pháp lý — mặt phẳng duy nhất có nó.
Ba nhóm khẳng định, và nhóm giữa là nhóm khó viết nhất nên cũng là nhóm hay bị
bỏ:

* **Vòng đời.** nháp → rà soát → phê duyệt → công bố, không có đường tắt.
* **Tranh chấp THẬT.** Hai luồng ghi cùng lúc, không phải hai lời gọi tuần tự
  giả vờ là đồng thời. Một khoá lạc quan chỉ được kiểm bằng tuần tự thì chưa
  chứng minh được gì về hành vi dưới tải.
* **Sổ đăng bạ.** Chỉ-thêm, và **không bao giờ mang nội dung văn bản**.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import legal
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Kho tệp riêng cho mỗi test — bước phê duyệt ghi blob thật."""
    monkeypatch.setenv("LEGAL_STORE_ROOT", str(tmp_path / "legal"))


@pytest.fixture
def drafts():
    """Thu bản nháp đã tạo và dọn ở cuối, kể cả khi test đỏ.

    Dọn cả những bản nháp mà `create_draft` từ chối tạo thì không cần — nhưng
    dọn phải nằm ở fixture chứ không ở cuối thân test, vì một `assert` đỏ nhảy
    ra khỏi hàm trước khi tới dòng dọn. Bài học từ `lop-thu-70eb62`.
    """
    created: list[str] = []
    yield created
    with system_scope("test cleanup: gỡ bản nháp"):
        for draft_id in reversed(created):
            try:
                db._execute("DELETE FROM legal_document_drafts WHERE draft_id = %s",
                            (draft_id,))
            except Exception:
                pass


@pytest.fixture
def published():
    """Công bố văn bản và gỡ đúng những bản mình công bố."""
    created: list[tuple[str, str]] = []

    def _publish(kind: str, *, version: str | None = None, body: str = "Nội dung.",
                 **kwargs):
        version = version or f"dft-{uuid.uuid4().hex[:10]}"
        legal.register_document(kind, version, url=f"/legal/{kind}", body=body,
                                **kwargs)
        created.append((kind, version))
        return version

    yield _publish

    with system_scope("test cleanup: gỡ văn bản đã công bố"):
        for kind, version in reversed(created):
            for sql in (
                "DELETE FROM user_consents WHERE kind = %s AND version = %s",
                "DELETE FROM legal_documents WHERE kind = %s AND version = %s",
            ):
                try:
                    db._execute(sql, (kind, version))
                except Exception:
                    pass


def _new_draft(drafts, kind: str = "guardian", **kwargs) -> dict:
    draft = legal.create_draft(kind, seed_from_current=False, **kwargs)
    drafts.append(draft["draft_id"])
    return draft


# ===========================================================================
# Vòng đời
# ===========================================================================

class TestTheDraftLifecycle:
    def test_createDraft_startsAtRevisionOne(self, drafts):
        draft = _new_draft(drafts)

        assert draft["revision"] == 1
        assert draft["status"] == "draft"

    def test_createDraft_seedsFromTheDocumentInForce(self, drafts, published):
        """Gần như mọi lần sửa điều khoản là sửa MỘT MỤC của bản cũ. Bắt người
        soạn dán lại 6.000 ký tự là mời họ đánh rơi một đoạn."""
        published("guardian", body="# Bản đang dùng\n\nĐoạn một.")

        draft = legal.create_draft("guardian", seed_from_current=True)
        drafts.append(draft["draft_id"])

        assert draft["body"] == "# Bản đang dùng\n\nĐoạn một."
        assert draft["based_on_version"] is not None

    def test_aSecondOpenDraftForTheSameKind_isRefused(self, drafts):
        """Nhiều bản nháp song song = hai người soạn hai bản khác nhau của cùng
        một văn bản, và không ai hợp nhất chúng. Một bản nháp chung với khoá lạc
        quan biến chuyện đó thành xung đột ghi phát hiện được ngay."""
        _new_draft(drafts)

        with pytest.raises(legal.ConsentError) as exc:
            legal.create_draft("guardian", seed_from_current=False)

        assert exc.value.code == "draft_already_open"

    def test_aDraftForAnotherKind_isAllowedAlongside(self, drafts, free_legal_kinds):
        """Phản chứng. Không có nó, một bản vá chặn MỌI bản nháp thứ hai vẫn
        xanh.

        Hai loại lấy ĐỘNG từ `free_legal_kinds`: bản sao dữ liệu thật có thể
        đang giữ một bản nháp mở của bất kỳ loại nào, và viết cứng loại là cách
        test này đỏ vì công việc dở dang của một người soạn.
        """
        if len(free_legal_kinds) < 2:
            pytest.skip(f"can hai loai con trong, chi co {free_legal_kinds}")
        first_kind, second_kind = free_legal_kinds[:2]

        _new_draft(drafts, kind=first_kind)
        second = _new_draft(drafts, kind=second_kind)

        assert second["kind"] == second_kind

    def test_discardingADraft_freesTheSlot(self, drafts):
        first = _new_draft(drafts)
        legal.advance_draft(first["draft_id"], first["revision"], "discarded")

        second = _new_draft(drafts)

        assert second["draft_id"] != first["draft_id"]

    def test_updateDraft_bumpsTheRevision(self, drafts):
        draft = _new_draft(drafts)

        updated = legal.update_draft(draft["draft_id"], draft["revision"],
                                     {"title": "Tiêu đề mới"})

        assert updated["revision"] == draft["revision"] + 1
        assert updated["title"] == "Tiêu đề mới"

    def test_updateDraft_refusesAFieldThatIsNotEditable(self, drafts):
        """`status` và `revision` cố ý không nằm trong danh sách sửa được: đổi
        trạng thái đi qua bảng chuyển hợp lệ, còn để người gọi tự đặt `revision`
        là mở đường vô hiệu hoá chính khoá lạc quan."""
        draft = _new_draft(drafts)

        with pytest.raises(legal.ConsentError) as exc:
            legal.update_draft(draft["draft_id"], draft["revision"],
                               {"status": "approved"})

        assert exc.value.code == "field_not_editable"


class TestTheTransitionTable:
    def test_draftCannotJumpStraightToApproved(self, drafts):
        """Không có đường tắt. Bảng `DRAFT_TRANSITIONS` là quy trình, viết ra
        thành dữ liệu để đọc được."""
        draft = _new_draft(drafts)

        with pytest.raises(legal.ConsentError) as exc:
            legal.advance_draft(draft["draft_id"], draft["revision"], "approved")

        assert exc.value.code == "invalid_transition"

    def test_reviewCanSendItBackToDraft(self, drafts):
        draft = _new_draft(drafts)
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")

        sent_back = legal.advance_draft(draft["draft_id"], draft["revision"], "draft")

        assert sent_back["status"] == "draft"

    def test_publishedStatusCannotBeSetByHand(self, drafts):
        """Đặt tay sẽ tạo ra một bản nháp tự nhận là đã công bố mà không có văn
        bản nào ứng với nó."""
        draft = _new_draft(drafts)

        with pytest.raises(legal.ConsentError) as exc:
            legal.advance_draft(draft["draft_id"], draft["revision"], "published")

        assert exc.value.code == "status_not_settable"

    def test_approving_writesTheBodyToTheStore(self, drafts):
        """Bản đã phê duyệt là hiện vật người duyệt đã đọc; nó phải có một địa
        chỉ cố định TRƯỚC khi ai đó bấm Công bố."""
        from app import legal_store

        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"],
                                   {"body": "# Đã duyệt\n\nNội dung."})
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "approved")

        assert draft["storage_key"]
        assert legal_store.verify(draft["storage_key"], draft["content_hash"])


# ===========================================================================
# Tranh chấp ghi — hai luồng THẬT, không phải hai lời gọi tuần tự
# ===========================================================================

class TestConcurrentWrites:
    def test_aStaleRevision_isRefusedWithTheCurrentOne(self, drafts):
        draft = _new_draft(drafts)
        legal.update_draft(draft["draft_id"], draft["revision"], {"title": "A"})

        with pytest.raises(legal.DraftConflict) as exc:
            legal.update_draft(draft["draft_id"], draft["revision"], {"title": "B"})

        # Số hiệu hiện tại phải đi kèm: không có nó, giao diện chỉ biết "hỏng"
        # và cách duy nhất còn lại là bảo người dùng tải lại — mất phần vừa gõ.
        assert exc.value.current_revision == draft["revision"] + 1

    def test_twoThreadsWritingTheSameRevision_onlyOneWins(self, drafts):
        """Tính chất trung tâm, kiểm bằng ĐỒNG THỜI THẬT.

        Kiểm bằng hai lời gọi tuần tự chỉ chứng minh câu `WHERE revision = %s`
        có mặt. Nó không chứng minh rằng hai giao dịch chồng nhau không cùng
        thắng — và đó chính là câu hỏi mà khoá lạc quan tồn tại để trả lời.
        """
        draft = _new_draft(drafts)
        revision = draft["revision"]

        def _write(marker: str):
            try:
                legal.update_draft(draft["draft_id"], revision, {"title": marker})
                return "ok"
            except legal.DraftConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(_write, ["A", "B"]))

        assert sorted(outcomes) == ["conflict", "ok"]
        # Và bản nháp chỉ nhích đúng MỘT bậc — không phải hai lượt ghi đều vào.
        assert (legal.get_draft(draft["draft_id"]) or {})["revision"] == revision + 1

    def test_theWinningWriteIsTheOneThatSurvives(self, drafts):
        """Người thua không được để lại dấu vết nào trên nội dung. Nếu cả hai
        cùng ghi rồi một bên báo lỗi, dữ liệu đã hỏng dù mã trả về đúng."""
        draft = _new_draft(drafts)
        revision = draft["revision"]
        results = {}

        def _write(marker: str):
            try:
                legal.update_draft(draft["draft_id"], revision, {"title": marker})
                results[marker] = True
            except legal.DraftConflict:
                results[marker] = False

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(_write, ["A", "B"]))

        winner = next(m for m, ok in results.items() if ok)
        assert (legal.get_draft(draft["draft_id"]) or {})["title"] == winner


class TestPublishingADraft:
    def _approved(self, drafts, *, version: str, body: str = "# Bản\n\nNội dung."):
        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"],
                                   {"body": body, "target_version": version,
                                    "title": "Người giám hộ"})
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")
        return legal.advance_draft(draft["draft_id"], draft["revision"], "approved")

    def test_publishing_requiresApproval(self, drafts):
        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"],
                                   {"body": "x", "target_version": "v1"})

        with pytest.raises(legal.ConsentError) as exc:
            legal.publish_draft(draft["draft_id"], draft["revision"])

        assert exc.value.code == "draft_not_approved"

    def test_publishing_withAStaleRevision_isRefused(self, drafts):
        """Nếu ai đó sửa nội dung giữa lúc người này bấm Công bố và lúc câu ghi
        chạy, thì bản văn sắp công bố KHÔNG phải bản họ vừa đọc. Phải hỏng ở đó
        thay vì công bố nhầm."""
        draft = self._approved(drafts, version=f"dft-{uuid.uuid4().hex[:8]}")

        with pytest.raises(legal.DraftConflict):
            legal.publish_draft(draft["draft_id"], draft["revision"] - 1)

    def test_publishing_closesTheDraftAndCreatesTheDocument(self, drafts):
        version = f"dft-{uuid.uuid4().hex[:8]}"
        draft = self._approved(drafts, version=version)

        result = legal.publish_draft(draft["draft_id"], draft["revision"])

        try:
            assert result["draft"]["status"] == "published"
            assert result["draft"]["published_version"] == version
            assert legal.read_document("guardian", version) is not None
        finally:
            with system_scope("test cleanup"):
                db._execute("DELETE FROM legal_documents WHERE kind = %s AND version = %s",
                            ("guardian", version))

    def test_publishing_requiresAVersionNumber(self, drafts):
        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"], {"body": "x"})
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "approved")

        with pytest.raises(legal.ConsentError) as exc:
            legal.publish_draft(draft["draft_id"], draft["revision"])

        assert exc.value.code == "missing_version"


class TestOneDocumentInForceAtATime:
    def test_twoVersionsWithTheSameEffectiveFrom_isRefused(self, published):
        """Vá một lỗi có thật, không phải thêm ràng buộc cho vui.

        `current_document` chọn bằng `ORDER BY effective_from DESC LIMIT 1`. Hai
        bản cùng giờ hiệu lực làm câu đó trả về một trong hai KHÔNG XÁC ĐỊNH —
        cùng truy vấn, hai lần chạy, hai bản văn khác nhau, và chấp thuận thu
        được trỏ tới bản nào là chuyện may rủi.
        """
        moment = datetime.now(timezone.utc) + timedelta(days=400)
        published("guardian", body="Bản một.", effective_from=moment)

        with pytest.raises(legal.ConsentError) as exc:
            published("guardian", body="Bản hai.", effective_from=moment)

        assert exc.value.code == "effective_from_taken"

    def test_theSameMomentForADifferentKind_isFine(self, published):
        """Phản chứng: ràng buộc là (loại, thời điểm), không phải chỉ thời điểm.
        Công bố `terms` và `privacy` cùng lúc là việc bình thường."""
        moment = datetime.now(timezone.utc) + timedelta(days=401)
        published("guardian", body="Một.", effective_from=moment)
        published("data_contribution", body="Hai.", effective_from=moment)


# ===========================================================================
# Sổ đăng bạ
# ===========================================================================

class TestTheRegister:
    def test_everyDraftActionLeavesALine(self, drafts):
        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"],
                                   {"title": "T"})
        legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")

        actions = [e["action"] for e in legal.list_events(kind="guardian", limit=20)]

        assert "draft.create" in actions
        assert "draft.update" in actions
        assert "draft.in_review" in actions

    def test_theRegisterNamesTheFieldsChangedNotTheirValues(self, drafts):
        """Ghi HÀNH ĐỘNG và ĐỐI TƯỢNG, không ghi nội dung. Giá trị của `body`
        chính là bản văn, và sổ này được đọc, xuất và chuyển tiếp thường xuyên
        hơn bảng văn bản."""
        secret = "ĐOẠN VĂN KHÔNG ĐƯỢC XUẤT HIỆN TRONG SỔ"
        draft = _new_draft(drafts)
        legal.update_draft(draft["draft_id"], draft["revision"], {"body": secret})

        events = legal.list_events(kind="guardian", limit=20)
        blob = repr(events)

        assert secret not in blob
        update = next(e for e in events if e["action"] == "draft.update")
        assert update["detail"]["fields"] == ["body"]

    def test_theRegisterRefusesUpdates(self, drafts):
        """Chỉ-thêm, cưỡng chế ở tầng cơ sở dữ liệu. Một sổ đăng bạ sửa được thì
        không trả lời được câu hỏi duy nhất nó tồn tại để trả lời."""
        _new_draft(drafts)
        event_id = legal.list_events(kind="guardian", limit=1)[0]["event_id"]

        with pytest.raises(Exception) as exc:
            with system_scope("test: thử sửa sổ đăng bạ"):
                db._execute("UPDATE legal_document_events SET action = %s "
                            "WHERE event_id = %s", ("da-bi-sua", event_id))

        assert "CHI-THEM" in str(exc.value)

    def test_theRegisterRefusesDeletes(self, drafts):
        _new_draft(drafts)
        event_id = legal.list_events(kind="guardian", limit=1)[0]["event_id"]

        with pytest.raises(Exception):
            with system_scope("test: thử xoá dòng sổ đăng bạ"):
                db._execute("DELETE FROM legal_document_events WHERE event_id = %s",
                            (event_id,))

    def test_theRegisterDoesNotBlockDeletingTheAccountThatActed(self, drafts):
        """Bản đầu có khoá ngoại `actor_user_id -> users ON DELETE SET NULL`, và
        `SET NULL` phát ra một UPDATE mà trigger chỉ-thêm từ chối — nên
        `DELETE FROM users` bắt đầu hỏng cho bất kỳ ai từng xuất hiện trong sổ.

        Tức là thêm một sổ đăng bạ đã âm thầm làm hỏng quyền xoá tài khoản, thứ
        chính sách quyền riêng tư hứa ở mục 6. Test này ghim việc đó đã được vá.
        """
        from app.auth import create_user
        from conftest import purge_registered_account

        name = f"lgev{uuid.uuid4().hex[:8]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        draft = legal.create_draft("guardian", actor_id=str(user["id"]),
                                   seed_from_current=False)
        drafts.append(draft["draft_id"])

        purge_registered_account(name)

        with system_scope("test: tài khoản phải biến mất thật"):
            rows = db._fetch_all("SELECT id FROM users WHERE username = %s", (name,))
        assert rows == [], "sổ đăng bạ đang chặn việc xoá tài khoản"

    def test_theRegisterKeepsTheActorLabelAfterTheAccountIsGone(self, drafts,
                                                                free_legal_kinds):
        """Xoá tài khoản không được xoá dấu vết ai đã làm gì. `actor_label` được
        điền ngay lúc ghi, chính vì `actor_user_id` không còn khoá ngoại."""
        from app.auth import create_user
        from conftest import purge_registered_account

        name = f"lglb{uuid.uuid4().hex[:8]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        draft = legal.create_draft(free_legal_kinds[0], actor_id=str(user["id"]),
                                   seed_from_current=False)
        drafts.append(draft["draft_id"])
        purge_registered_account(name)

        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT actor_label FROM legal_document_events "
                "WHERE draft_id = %s AND action = 'draft.create'",
                (draft["draft_id"],))

        assert rows and rows[0]["actor_label"] == str(user["id"])

    def test_theRegisterKeepsItsBlobsAliveAgainstGarbageCollection(self, drafts):
        """Sổ đăng bạ giữ `storage_key`, nên dọn rác PHẢI đếm nó là tham chiếu.

        Kịch bản làm lộ chuyện này không hiếm chút nào: soạn nháp → duyệt (ghi
        blob) → công bố → dọn bản nháp. Sau bước cuối, `legal_document_drafts`
        không còn trỏ tới blob nữa, nhưng dòng `draft.approved` trong sổ thì có.
        Bản đầu của `referenced_storage_keys` chỉ hợp hai bảng documents+drafts,
        nên `gc --apply` sẽ xoá blob sau 24 giờ và để lại một dòng sổ trỏ vào
        tệp không tồn tại.

        Có hai lý do việc này phải xanh, và lý do thứ hai mới là lý do nó được
        viết ra: `scripts/pg_backup.sh` đối chiếu đúng phép hợp BA bảng trước
        khi đóng gói kho tệp. Nếu dọn rác xoá thứ mà bản sao lưu coi là bắt
        buộc thì mọi lượt sao lưu sau đó bị đánh dấu `.CORRUPT` — hệ thống mất
        sao lưu, và không ai nối được hai chuyện đó với nhau.
        """
        draft = _new_draft(drafts)
        draft = legal.update_draft(draft["draft_id"], draft["revision"],
                                   {"body": "# Chỉ sổ còn nhớ\n\nNội dung."})
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "in_review")
        draft = legal.advance_draft(draft["draft_id"], draft["revision"], "approved")
        key = draft["storage_key"]
        assert key, "bước duyệt phải ghi blob, nếu không test này không kiểm gì"

        with system_scope("test: bỏ bản nháp, chỉ còn sổ trỏ tới blob"):
            db._execute("DELETE FROM legal_document_drafts WHERE draft_id = %s",
                        (draft["draft_id"],))

        assert key in legal.referenced_storage_keys(), (
            "blob chỉ còn sổ đăng bạ trỏ tới — dọn rác sẽ xoá nó và làm hỏng "
            "cả dấu vết lẫn phép đối chiếu của pg_backup.sh")

    def test_aFailingRegisterWrite_doesNotRaise(self):
        """Ghi sổ hỏng không được ném lỗi lên bên gọi.

        Cùng lập luận với `_send_welcome_verification` ở `routers/auth.py`: khi
        `record_event` được gọi, thao tác đã xong và dữ liệu đã ghi. Ném lỗi ở
        đây trả 500 cho một request đã thành công, và người dùng sẽ thử lại một
        việc đã hoàn tất — với `document.publish` thì lần thử lại đó đụng chính
        số hiệu họ vừa chiếm.

        Dùng một hỏng THẬT: `action = ''` vi phạm ràng buộc
        `ck_legal_events_action_not_blank`, nên câu INSERT đổ vỡ ở tầng cơ sở dữ
        liệu. Giả lập bằng monkeypatch sẽ chỉ kiểm được cái `try` có tồn tại,
        không kiểm được nó bắt đúng loại lỗi phát sinh trong thực tế.
        """
        before = len(legal.list_events(limit=1000))

        legal.record_event("", kind="guardian")  # không được ném

        assert len(legal.list_events(limit=1000)) == before
