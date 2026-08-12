"""Tenant lifecycle: creating tenants, inviting people, and the rules that bind.

Runs against the real Postgres. Every test cleans up the tenants, accounts and
invitations it creates, because this database also holds the live corpus — a
suite that leaves `test-*` tenants behind would eventually make the operator's
tenant list useless.

What is deliberately NOT asserted here: that a tenant's *data* is isolated.
That is `test_tenant_isolation.py`, which proves it against row-level security.
This file proves the plane that decides who belongs where.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import registration_consents

from app import tenant_admin
from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


def _new_tenant_id() -> str:
    return f"test-{uuid.uuid4().hex[:10]}"


def _purge_tenant(tenant_id: str) -> None:
    """Remove a throwaway tenant and everything pointing at it.

    Shared with `test_two_tenant_proof.py` via conftest: creating a tenant now
    clones a whole vocabulary catalogue into it, so the list of tables to clear
    is long enough that a second copy would drift and start leaving rows behind.
    """
    from conftest import purge_tenant

    purge_tenant(tenant_id)


@pytest.fixture
def tenant():
    tid = _new_tenant_id()
    tenant_admin.create_tenant(tid, display_name="Throwaway School")
    yield tid
    _purge_tenant(tid)


@pytest.fixture
def other_tenant():
    tid = _new_tenant_id()
    tenant_admin.create_tenant(tid, display_name="A Different School")
    yield tid
    _purge_tenant(tid)


@pytest.fixture
def account():
    """A throwaway account, removed afterwards along with its memberships."""
    created = []

    def _make(username: str = "", *, is_admin: bool = False) -> dict:
        from app.auth import create_user

        name = username or f"t{uuid.uuid4().hex[:10]}"
        user = create_user(
            username=name, email=f"{name}@example.test",
            password="correct horse battery", is_admin=is_admin,
        )
        created.append(user["id"])
        return user

    yield _make

    with system_scope("test cleanup"):
        for uid in created:
            db._execute("DELETE FROM tenant_members WHERE user_id = %s", (uid,))
            db._execute(
                "UPDATE tenant_invitations SET accepted_by = NULL WHERE accepted_by = %s",
                (uid,),
            )
            db._execute(
                "UPDATE tenant_invitations SET invited_by = NULL WHERE invited_by = %s",
                (uid,),
            )
            db._execute("DELETE FROM users WHERE id = %s", (uid,))


# ---------------------------------------------------------------------------
# Tenant records
# ---------------------------------------------------------------------------


class TestTenantRecords:
    def test_create_and_read_back(self, tenant):
        row = tenant_admin.get_tenant(tenant)
        assert row["tenant_id"] == tenant
        assert row["display_name"] == "Throwaway School"
        assert row["is_active"] is True

    def test_duplicate_is_refused(self, tenant):
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.create_tenant(tenant)
        assert exc.value.status_code == 409

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("Has-Capitals", id="uppercase"),
            pytest.param("has space", id="space"),
            pytest.param("-leading-dash", id="leading-dash"),
            pytest.param("a" * 64, id="too-long"),
            pytest.param("../escape", id="path-traversal"),
            pytest.param("", id="empty"),
            pytest.param("   ", id="whitespace-only"),
        ],
    )
    def test_malformed_id_is_refused(self, bad):
        """A tenant id names a storage directory (A4) and a CSV cell, not just a
        row. `../escape` is the one that makes the point: unchecked, it is a
        path."""
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.create_tenant(bad)
        assert exc.value.status_code == 422

    @pytest.mark.parametrize(
        "surrounded",
        [
            pytest.param("trailing-lf\n", id="trailing-lf"),
            pytest.param("trailing-crlf\r\n", id="trailing-crlf"),
            pytest.param("  padded  ", id="spaces"),
            pytest.param("\ttabbed\n", id="tab-and-lf"),
        ],
    )
    def test_surrounding_whitespace_is_stripped_not_stored(self, surrounded):
        """The A1 hazard was a tenant id that CONTAINS a newline: it breaks the
        CSV row it is written into, names a directory with a newline in it, and
        reads as a separate partition that is indistinguishable from the clean
        one in any log.

        Stripping is the fix, not rejection — a trailing newline is a paste
        artefact, not an attack. What must never happen is the whitespace
        reaching storage, and that is what this asserts.
        """
        tid = surrounded.strip()
        assert tid, "test case must strip to something valid"
        try:
            row = tenant_admin.create_tenant(surrounded)
            assert row["tenant_id"] == tid
            assert not any(c.isspace() for c in row["tenant_id"])
        finally:
            _purge_tenant(tid)

    def test_bootstrap_tenant_cannot_be_deleted(self):
        """Deleting it would orphan every pre-tenant row and every anonymous
        reader of the public catalogue."""
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.delete_tenant(DEFAULT_TENANT_ID)
        assert exc.value.status_code == 409

    def test_bootstrap_tenant_cannot_be_deactivated(self):
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.update_tenant(DEFAULT_TENANT_ID, is_active=False)
        assert exc.value.status_code == 409

    def test_soft_delete_hides_from_list_but_keeps_the_row(self, account):
        tid = _new_tenant_id()
        try:
            tenant_admin.create_tenant(tid)
            tenant_admin.delete_tenant(tid)

            listed = {t["tenant_id"] for t in tenant_admin.list_tenants()}
            assert tid not in listed
            with_deleted = {
                t["tenant_id"] for t in tenant_admin.list_tenants(include_deleted=True)
            }
            assert tid in with_deleted
            # Still addressable, which is what makes an export or a restore possible.
            assert tenant_admin.get_tenant(tid, include_deleted=True)["deleted_at"]
        finally:
            _purge_tenant(tid)

    def test_list_reports_member_count(self, tenant, account):
        user = account()
        tenant_admin.add_member(tenant, user["id"], "admin")
        row = next(t for t in tenant_admin.list_tenants() if t["tenant_id"] == tenant)
        assert row["member_count"] == 1


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


class TestMembership:
    def test_add_member_and_list(self, tenant, account):
        user = account()
        tenant_admin.add_member(tenant, user["id"], "editor")
        members = tenant_admin.list_members(tenant)
        assert [m["user_id"] for m in members] == [uuid.UUID(user["id"])] or [
            str(m["user_id"]) for m in members
        ] == [user["id"]]
        assert members[0]["role"] == "editor"

    def test_adding_twice_updates_the_role_instead_of_erroring(self, tenant, account):
        user = account()
        tenant_admin.add_member(tenant, user["id"], "editor")
        tenant_admin.add_member(tenant, user["id"], "admin")
        assert tenant_admin.list_members(tenant)[0]["role"] == "admin"

    def test_add_member_defaults_to_no_tenant_role(self, tenant, account):
        """Gắn người vào tổ chức KHÔNG cấp vai nào, trừ khi có người nói ra.

        Mặc định cũ là `'viewer'`, và vai đó đọc được hoá đơn, nhật ký kiểm
        toán, danh sách khoá API và trạng thái đồng thuận của người ký. Nghĩa là
        bỏ qua một tham số đã cấp quyền đọc bốn thứ đó. Ghim ở đây để mặc định
        không trôi ngược lại thành một vai nào đó.
        """
        user = account()
        tenant_admin.add_member(tenant, user["id"])
        member = tenant_admin.list_members(tenant)[0]
        assert member["role"] is None

    def test_membership_without_a_tenant_role_is_a_real_membership(self, tenant, account):
        """Không vai KHÔNG phải không có mặt.

        Đây là điểm của cả lượt thay đổi: tư cách thành viên và vai là hai sự
        thật. Người này phải đếm được, liệt kê được, và `tenant_role` phải trả
        `None` — chứ không phải chuỗi `"None"`, vốn là một vai không tồn tại đi
        thẳng vào bản đồ role cũ.
        """
        from app.vocabulary_registry import tenant_role

        user = account()
        tenant_admin.add_member(tenant, user["id"])
        assert len(tenant_admin.list_members(tenant)) == 1
        assert tenant_role(tenant, user["id"]) is None

    @pytest.mark.parametrize("blank", [None, "", "  ", "none", "NONE"])
    def test_the_three_spellings_of_no_role_all_mean_no_role(self, tenant, account, blank):
        """`None`, chuỗi rỗng và `"none"` tới từ ba nơi khác nhau.

        Chuỗi rỗng là cái đáng ghim nhất: nó là thứ một ô `<select>` rỗng gửi
        lên. Nếu nó ăn 422, giao diện sẽ buộc phải gửi một vai nào đó, và cái
        được chọn để "cho qua" sẽ là vai thấp nhất — đúng cái mặc định âm thầm
        mà lượt này gỡ đi.
        """
        user = account()
        tenant_admin.add_member(tenant, user["id"], blank)
        assert tenant_admin.list_members(tenant)[0]["role"] is None

    def test_viewer_is_refused_rather_than_quietly_translated(self, tenant, account):
        """`'viewer'` từng hợp lệ, nên nó còn trong script và bookmark của người ta.

        Dịch im lặng sang `None` sẽ giấu mất việc chỗ gọi đó cần được sửa; dịch
        im lặng sang `'editor'` thì tệ hơn nữa. 422 là câu trả lời đúng.
        """
        user = account()
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.add_member(tenant, user["id"], "viewer")
        assert exc.value.status_code == 422

    def test_removing_a_role_keeps_the_membership(self, tenant, account):
        """Gỡ vai ≠ gỡ người. Sau lời gọi họ vẫn ở trong tổ chức."""
        keeper, user = account(), account()
        tenant_admin.add_member(tenant, keeper["id"], "admin")
        tenant_admin.add_member(tenant, user["id"], "editor")
        tenant_admin.update_member_role(tenant, user["id"], None)
        roles = {str(m["user_id"]): m["role"] for m in tenant_admin.list_members(tenant)}
        assert roles[user["id"]] is None
        assert len(roles) == 2

    def test_unknown_user_is_refused(self, tenant):
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.add_member(tenant, str(uuid.uuid4()), "editor")
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("bad_role", ["owner", "viewer", "superuser", "adm", "admin;--"])
    def test_invalid_role_is_refused(self, tenant, account, bad_role):
        """Roles are a closed set. `owner` and `superuser` are the interesting
        ones: they read like real roles and would silently become no authority
        at all if the column merely accepted any string."""
        user = account()
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.add_member(tenant, user["id"], bad_role)
        assert exc.value.status_code == 422

    def test_role_case_is_normalised_not_rejected(self, tenant, account):
        """`ADMIN` is the same authority as `admin`. Accepting it is safe — the
        set is closed and the database has a CHECK — and rejecting it would be a
        papercut with no security value. Pinned so the normalisation is a
        decision rather than an accident."""
        user = account()
        tenant_admin.add_member(tenant, user["id"], "  ADMIN ")
        assert tenant_admin.list_members(tenant)[0]["role"] == "admin"

    def test_last_admin_cannot_be_removed(self, tenant, account):
        """A tenant with no admin cannot be administered — not even to add one
        back. The dead end is silent, so it is refused at the edge."""
        user = account()
        tenant_admin.add_member(tenant, user["id"], "admin")
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.remove_member(tenant, user["id"])
        assert exc.value.status_code == 409
        assert "last admin" in str(exc.value)

    def test_last_admin_cannot_be_demoted(self, tenant, account):
        """Demotion produces exactly the same dead end as removal, so it is the
        same check. Testing only removal would leave the other door open."""
        user = account()
        tenant_admin.add_member(tenant, user["id"], "admin")
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.update_member_role(tenant, user["id"], "editor")
        assert exc.value.status_code == 409

    def test_second_admin_makes_the_first_removable(self, tenant, account):
        """Negative control for the two tests above: the rule is 'not the LAST
        admin', not 'admins are permanent'."""
        first, second = account(), account()
        tenant_admin.add_member(tenant, first["id"], "admin")
        tenant_admin.add_member(tenant, second["id"], "admin")
        tenant_admin.remove_member(tenant, first["id"])
        assert [m["role"] for m in tenant_admin.list_members(tenant)] == ["admin"]

    def test_home_tenant_blocks_removal(self, tenant, account):
        """An account whose data lands in a tenant it has no role in is a state
        with no correct behaviour, so it cannot be reached."""
        user = account()
        tenant_admin.set_home_tenant(user["id"], tenant, role="editor")
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.remove_member(tenant, user["id"])
        assert exc.value.status_code == 409
        assert "home tenant" in str(exc.value)

    def test_set_home_tenant_writes_both_facts(self, tenant, account):
        """Home tenant and membership are written by different statements; the
        invariant is that they never disagree."""
        user = account()
        tenant_admin.set_home_tenant(user["id"], tenant, role="editor")

        with system_scope("test read"):
            rows = db._fetch_all("SELECT tenant_id FROM users WHERE id = %s", (user["id"],))
        assert rows[0]["tenant_id"] == tenant
        assert [m["role"] for m in tenant_admin.list_members(tenant)] == ["editor"]
        assert user["id"] not in {str(o["user_id"]) for o in tenant_admin.orphaned_members()}


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


class TestInvitations:
    def test_token_is_returned_once_and_never_stored(self, tenant, account):
        """The raw token must not be recoverable from the database.

        This is the property the whole design rests on: an operator with a
        database dump holds digests, not invitations.
        """
        inviter = account()
        invitation, token = tenant_admin.create_invitation(
            tenant, "Someone@Example.test", "editor", invited_by=inviter["id"]
        )
        assert token and len(token) >= 32
        assert "token" not in invitation  # not in the public projection either

        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT * FROM tenant_invitations WHERE invitation_id = %s",
                (invitation["invitation_id"],),
            )
        stored = " ".join(str(v) for v in rows[0].values())
        assert token not in stored, "the raw token reached the database"
        # Address is normalised on the way in, so a re-invite to the same person
        # typed with different capitalisation collides as intended.
        assert rows[0]["email"] == "someone@example.test"

    def test_reinviting_replaces_the_live_invitation(self, tenant):
        """Two valid tokens for one seat means revoking one still leaves a way in."""
        _, first = tenant_admin.create_invitation(tenant, "a@example.test")
        _, second = tenant_admin.create_invitation(tenant, "a@example.test", "admin")

        assert tenant_admin._invitation_by_token(first)["revoked_at"] is not None
        assert tenant_admin._invitation_by_token(second)["revoked_at"] is None
        open_ones = tenant_admin.list_invitations(tenant)
        assert len(open_ones) == 1 and open_ones[0]["role"] == "admin"

    def test_peek_hides_whether_a_token_ever_existed(self, tenant):
        """An unknown token and an expired one must be indistinguishable, or this
        endpoint becomes an oracle for testing guesses."""
        _, token = tenant_admin.create_invitation(tenant, "b@example.test")
        with system_scope("test setup"):
            db._execute(
                "UPDATE tenant_invitations SET expires_at = %s WHERE tenant_id = %s",
                (datetime.now(timezone.utc) - timedelta(days=1), tenant),
            )

        with pytest.raises(tenant_admin.TenantError) as expired:
            tenant_admin.peek_invitation(token)
        with pytest.raises(tenant_admin.TenantError) as unknown:
            tenant_admin.peek_invitation("not-a-real-token")
        assert expired.value.status_code == unknown.value.status_code == 404
        assert str(expired.value) == str(unknown.value)

    def test_accept_attaches_role_and_home_tenant(self, tenant, account):
        user = account()
        _, token = tenant_admin.create_invitation(tenant, user["email"], "editor")
        result = tenant_admin.consume_invitation(
            token, email=user["email"], user_id=user["id"]
        )
        assert result == {"tenant_id": tenant, "role": "editor"}

        with system_scope("test read"):
            rows = db._fetch_all("SELECT tenant_id FROM users WHERE id = %s", (user["id"],))
        assert rows[0]["tenant_id"] == tenant
        assert tenant_admin.list_members(tenant)[0]["role"] == "editor"

    def test_forwarded_link_is_refused(self, tenant, account):
        """The invitation names a person. Letting whoever holds the URL join
        instead makes email forwarding the authentication factor."""
        invited, someone_else = account(), account()
        _, token = tenant_admin.create_invitation(tenant, invited["email"], "admin")

        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.consume_invitation(
                token, email=someone_else["email"], user_id=someone_else["id"]
            )
        assert exc.value.status_code == 403
        assert tenant_admin.list_members(tenant) == []

    def test_replay_is_refused(self, tenant, account):
        first, second = account(), account()
        _, token = tenant_admin.create_invitation(tenant, first["email"], "admin")
        tenant_admin.consume_invitation(token, email=first["email"], user_id=first["id"])

        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.consume_invitation(
                token, email=first["email"], user_id=second["id"]
            )
        assert exc.value.status_code == 409

    def test_revoked_invitation_cannot_be_accepted(self, tenant, account):
        user = account()
        invitation, token = tenant_admin.create_invitation(tenant, user["email"], "editor")
        tenant_admin.revoke_invitation(tenant, invitation["invitation_id"])

        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.consume_invitation(token, email=user["email"], user_id=user["id"])
        assert exc.value.status_code == 409

    def test_expired_invitation_cannot_be_accepted(self, tenant, account):
        user = account()
        _, token = tenant_admin.create_invitation(tenant, user["email"])
        with system_scope("test setup"):
            db._execute(
                "UPDATE tenant_invitations SET expires_at = %s WHERE tenant_id = %s",
                (datetime.now(timezone.utc) - timedelta(seconds=1), tenant),
            )
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.consume_invitation(token, email=user["email"], user_id=user["id"])
        assert exc.value.status_code == 409

    def test_inactive_tenant_cannot_be_joined(self, tenant, account):
        """The relationship can end while a link is in flight."""
        user = account()
        _, token = tenant_admin.create_invitation(tenant, user["email"])
        tenant_admin.update_tenant(tenant, is_active=False)

        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.consume_invitation(token, email=user["email"], user_id=user["id"])
        assert exc.value.status_code == 409

    def test_revoking_another_tenants_invitation_is_refused(
        self, tenant, other_tenant, account
    ):
        """Scoped by tenant AND id: an admin of one tenant must not be able to
        revoke another's invitation by guessing a UUID."""
        invitation, _ = tenant_admin.create_invitation(
            other_tenant, "c@example.test"
        )
        with pytest.raises(tenant_admin.TenantError) as exc:
            tenant_admin.revoke_invitation(tenant, invitation["invitation_id"])
        assert exc.value.status_code == 404

    def test_invitations_of_one_tenant_are_not_listed_for_another(
        self, tenant, other_tenant
    ):
        tenant_admin.create_invitation(other_tenant, "d@example.test")
        assert tenant_admin.list_invitations(tenant) == []
        assert len(tenant_admin.list_invitations(other_tenant)) == 1


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_client():
    """Unauthenticated client whose every request gets its own rate-limit bucket.

    Registration is rate-limited per client IP with counters that live in Redis
    for an hour, so without this the file passes once and 429s on the next run —
    a failure that looks like broken code and is not. `LoopbackPeer` makes the
    app trust the forwarding header; `fresh_client_ip` makes each request land
    somewhere new.
    """
    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _PerRequestIp:
        def post(self, url, **kwargs):
            headers = {**kwargs.pop("headers", {}), "X-Forwarded-For": fresh_client_ip()}
            return inner.post(url, headers=headers, **kwargs)

    return _PerRequestIp()


class TestRegistration:
    """The one path by which a person, unaided, ends up inside a tenant.

    Every body carries `**registration_consents()`. Publishing the terms IS what
    switches consent enforcement on, and this suite runs against a copy of the
    real database where they are published — so a body without them gets 400
    `consent_required` and the test fails for a reason it is not about. The
    helper reads the live versions, so it stays correct on a deployment that has
    published nothing (it contributes no fields) and on one that publishes a new
    version tomorrow.
    """

    @staticmethod
    def _cleanup(username: str) -> None:
        """Uỷ cho bản dùng chung ở conftest — xem `purge_registered_account`."""
        from conftest import purge_registered_account

        purge_registered_account(username)

    def test_open_registration_gets_its_own_tenant_not_the_public_one(self, anon_client):
        """Đảo ngược một khẳng định CŨ, có chủ ý.

        Test này trước đây khẳng định `tenant_id == DEFAULT_TENANT_ID` và nó
        xanh — vì hành vi lúc đó đúng là như vậy. Đó chính là lỗ hổng: tenant
        gốc giữ toàn bộ dữ liệu thật, `users.is_active` mặc định TRUE, nên bất
        kỳ ai đăng ký được đều thành thành viên hoạt động của tổ chức đó.

        Một test chốt đúng hành vi sai sẽ bảo vệ cái sai đó. Giữ nguyên tên tệp
        và vị trí để lịch sử git chỉ thẳng vào chỗ khẳng định bị đảo.
        """
        name = f"t{uuid.uuid4().hex[:10]}"
        try:
            res = anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": f"{name}@example.test",
                "password": "correct horse battery",
                **registration_consents(),
            })
            assert res.status_code == 201, res.text
            assert res.json()["tenant_id"] != DEFAULT_TENANT_ID
        finally:
            self._cleanup(name)

    def test_invitation_puts_the_account_in_that_tenant(self, anon_client, tenant):
        name = f"t{uuid.uuid4().hex[:10]}"
        email = f"{name}@example.test"
        _, token = tenant_admin.create_invitation(tenant, email, "editor")
        try:
            res = anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": email,
                "password": "correct horse battery",
                **registration_consents(),
                "invitation_token": token,
            })
            assert res.status_code == 201, res.text
            assert res.json()["tenant_id"] == tenant
            assert tenant_admin.list_members(tenant)[0]["role"] == "editor"
        finally:
            self._cleanup(name)

    def test_email_mismatch_creates_no_account(self, anon_client, tenant):
        """Rejected BEFORE the insert. Creating first and failing after would
        leave a real account stranded in the public tenant, and the caller —
        seeing an error — would retry and collide with the username they just
        took."""
        name = f"t{uuid.uuid4().hex[:10]}"
        _, token = tenant_admin.create_invitation(tenant, "invited@example.test", "admin")
        try:
            res = anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": f"{name}@example.test",
                "password": "correct horse battery",
                **registration_consents(),
                "invitation_token": token,
            })
            assert res.status_code == 403, res.text
            with system_scope("test read"):
                assert db._fetch_all(
                    "SELECT 1 FROM users WHERE username = %s", (name,)
                ) == []
        finally:
            self._cleanup(name)

    def test_a_bad_token_creates_no_account(self, anon_client):
        name = f"t{uuid.uuid4().hex[:10]}"
        try:
            res = anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": f"{name}@example.test",
                "password": "correct horse battery",
                **registration_consents(),
                "invitation_token": "not-a-real-token",
            })
            assert res.status_code == 404, res.text
            with system_scope("test read"):
                assert db._fetch_all(
                    "SELECT 1 FROM users WHERE username = %s", (name,)
                ) == []
        finally:
            self._cleanup(name)

    def test_the_caller_cannot_name_their_own_tenant(self, anon_client, tenant):
        """There is no `tenant_id` field on the registration body, and an extra
        key must not become one. Tenant ids appear in URLs; a caller who could
        supply one would join any tenant they can read off a link.

        Khẳng định được siết lại ở v4. Trước đây nó là `== DEFAULT_TENANT_ID`,
        và điều đó chứng minh được ít hơn vẻ ngoài: tenant gốc CŨNG là nơi mọi
        lượt đăng ký rơi vào, nên test vẫn xanh kể cả khi trường `tenant_id`
        được tôn trọng — miễn là người gọi tình cờ điền đúng "default".

        Bây giờ mỗi lượt tự đăng ký sinh một tenant riêng có hậu tố ngẫu nhiên,
        nên "khác tenant người gọi nêu" là một khẳng định thật sự chặt: không
        giá trị nào người gọi gửi lên có thể trùng nó.
        """
        name = f"t{uuid.uuid4().hex[:10]}"
        try:
            res = anon_client.post("/api/v1/auth/register", json={
                "username": name, "email": f"{name}@example.test",
                "password": "correct horse battery",
                **registration_consents(),
                "tenant_id": tenant,
            })
            assert res.status_code == 201, res.text
            landed = res.json()["tenant_id"]
            assert landed != tenant, "trường tenant_id do người gọi gửi đã được tôn trọng"
            assert landed != DEFAULT_TENANT_ID
        finally:
            self._cleanup(name)


# ---------------------------------------------------------------------------
# HTTP authorisation
# ---------------------------------------------------------------------------


class TestRouterAuthorisation:
    """Platform operator and tenant admin are two authorities, not one scale."""

    @staticmethod
    def _client(user):
        from app.auth import get_current_user, require_admin
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: user
        if user.get("is_admin"):
            app.dependency_overrides[require_admin] = lambda: user
        else:
            def _refuse():
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Admin privileges required")

            app.dependency_overrides[require_admin] = _refuse
        return TestClient(app)

    @staticmethod
    def _reset():
        from app.auth import get_current_user, require_admin
        from app.main import app

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(require_admin, None)

    def test_only_a_platform_operator_creates_tenants(self, account):
        user = account()
        try:
            res = self._client({**user, "is_admin": False}).post(
                "/api/v1/tenants", json={"tenant_id": _new_tenant_id()}
            )
            assert res.status_code == 403
        finally:
            self._reset()

    def test_tenant_admin_may_invite_into_their_own_tenant(self, tenant, account):
        user = account()
        tenant_admin.add_member(tenant, user["id"], "admin")
        try:
            res = self._client({**user, "is_admin": False}).post(
                f"/api/v1/tenants/{tenant}/invitations",
                json={"email": "new@example.test", "role": "editor"},
            )
            assert res.status_code == 201, res.text
            # Returned exactly once, in this response, and nowhere else.
            assert res.json()["token"]
            listed = self._client({**user, "is_admin": False}).get(
                f"/api/v1/tenants/{tenant}/invitations"
            ).json()
            assert "token" not in listed[0]
        finally:
            self._reset()

    def test_a_member_without_a_tenant_role_may_not_invite(self, tenant, account):
        """Không vai nghĩa là không quyền quản trị, y như trước.

        Thay cho `test_a_viewer_may_not_invite`: cùng một câu hỏi, hỏi về trạng
        thái đã thay thế vai `viewer`. Đây là vế quan trọng của việc gỡ vai đó —
        người không vai KHÔNG được nới thêm gì.
        """
        user = account()
        tenant_admin.add_member(tenant, user["id"])
        try:
            res = self._client({**user, "is_admin": False}).post(
                f"/api/v1/tenants/{tenant}/invitations",
                json={"email": "new@example.test", "role": "editor"},
            )
            assert res.status_code == 403
        finally:
            self._reset()

    def test_admin_of_one_tenant_has_no_authority_in_another(
        self, tenant, other_tenant, account
    ):
        """The whole point of the tenant plane: a role is authority INSIDE one
        tenant, never a rank that carries across."""
        user = account()
        tenant_admin.add_member(tenant, user["id"], "admin")
        try:
            client = self._client({**user, "is_admin": False})
            assert client.get(f"/api/v1/tenants/{other_tenant}/members").status_code == 403
            assert client.post(
                f"/api/v1/tenants/{other_tenant}/invitations",
                json={"email": "x@example.test", "role": "admin"},
            ).status_code == 403
        finally:
            self._reset()

    def test_a_tenant_admin_cannot_pull_in_an_arbitrary_account(self, tenant, account):
        """Adding a member by id is operator-only. A tenant admin who could do it
        would be able to attach any account on the deployment, and account ids
        are not secret."""
        admin_user, victim = account(), account()
        tenant_admin.add_member(tenant, admin_user["id"], "admin")
        try:
            res = self._client({**admin_user, "is_admin": False}).post(
                f"/api/v1/tenants/{tenant}/members",
                json={"user_id": victim["id"], "role": "admin"},
            )
            assert res.status_code == 403
        finally:
            self._reset()


# ---------------------------------------------------------------------------
# Sending the invitation
# ---------------------------------------------------------------------------


class TestTheLinkAndTheMail:
    """`POST /tenants/{id}/invitations` — the link is built here, not in a browser.

    It used to be assembled by the admin page from `window.location.origin` plus
    a hardcoded `/invitation`, which put the name of a frontend route in two
    repositories at once. Renaming it on one side kills every invitation issued
    afterwards, and nothing fails until a stranger opens a blank page days later.
    """

    @staticmethod
    def _client(user):
        from app.auth import get_current_user, require_admin
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[require_admin] = lambda: user
        return TestClient(app)

    @staticmethod
    def _reset():
        from app.auth import get_current_user, require_admin
        from app.main import app

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(require_admin, None)

    def _invite(self, tenant, account, **kwargs):
        user = account(is_admin=True)
        return self._client(user).post(
            f"/api/v1/tenants/{tenant}/invitations",
            json={"email": "invited@example.test", "role": "editor"},
            **kwargs,
        )

    def test_the_response_carries_a_whole_url_not_just_a_token(self, tenant, account):
        try:
            body = self._invite(tenant, account).json()
            assert body["accept_url"].endswith(f"#token={body['token']}")
            assert "/invitation#token=" in body["accept_url"]
        finally:
            self._reset()

    def test_the_token_rides_in_the_fragment_never_the_query_string(
        self, tenant, account
    ):
        """Browsers do not transmit anything after the `#`. A token there
        reaches no access log, no proxy and no `Referer` header; the same token
        in `?token=` reaches all three."""
        try:
            url = self._invite(tenant, account).json()["accept_url"]
            assert "?" not in url, f"the token left the fragment: {url}"
        finally:
            self._reset()

    def test_an_untrusted_host_does_not_choose_the_url(self, tenant, account,
                                                       monkeypatch):
        """Host is attacker-controlled. Honouring a forged one here would mail
        someone a VALID invitation pointing at somebody else's site."""
        from app.config import settings as app_settings

        monkeypatch.setattr(app_settings, "frontend_base_url",
                            "https://voya.example.edu", raising=False)
        try:
            body = self._invite(tenant, account,
                                headers={"Host": "evil.example"}).json()
            assert body["accept_url"].startswith("https://voya.example.edu/invitation")
        finally:
            self._reset()

    def test_delivery_failure_does_not_undo_the_invitation(self, tenant, account,
                                                           monkeypatch):
        """SMTP being unconfigured is the NORMAL state of a local deployment.
        The invitation is already in the table and the link is in this response,
        so the admin can still send it by hand — failing the request would throw
        away a perfectly good invitation."""
        from app import email_service

        def _explode(*_a, **_kw):
            raise email_service.EmailNotConfigured("no smtp here")

        monkeypatch.setattr(email_service, "send_invitation_email", _explode)
        try:
            res = self._invite(tenant, account)
            assert res.status_code == 201, res.text
            assert res.json()["email_sent"] is False
            assert res.json()["accept_url"]
            assert len(tenant_admin.list_invitations(tenant)) == 1
        finally:
            self._reset()

    def test_a_successful_send_is_reported_as_one(self, tenant, account, monkeypatch):
        """`email_sent` decides which sentence the admin page shows. Saying
        "sent" when nothing was sent leaves the invited person waiting for a
        message that does not exist."""
        from app import email_service

        seen = {}

        def _capture(to_email, **kwargs):
            seen.update({"to": to_email, **kwargs})

        monkeypatch.setattr(email_service, "send_invitation_email", _capture)
        try:
            body = self._invite(tenant, account).json()
            assert body["email_sent"] is True
            assert seen["to"] == "invited@example.test"
            assert seen["accept_url"] == body["accept_url"]
            assert seen["role"] == "editor"
        finally:
            self._reset()

    def test_the_mail_never_falls_back_to_a_log(self, monkeypatch, caplog):
        """Unlike the password-reset link next door, which IS loggable. The
        difference is the failure path: an admin issuing an invitation already
        holds the link, so writing a tenant-joining credential into Loki buys
        nothing at all."""
        import logging

        from app import email_service

        monkeypatch.setattr(email_service.settings, "smtp_host", "", raising=False)
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(email_service.EmailNotConfigured):
                email_service.send_invitation_email(
                    "someone@example.test", tenant_name="Trường A", role="editor",
                    accept_url="https://voya.example.edu/invitation#token=SECRET-TOKEN",
                    expires_hours=168,
                )
        assert "SECRET-TOKEN" not in "\n".join(r.getMessage() for r in caplog.records)
