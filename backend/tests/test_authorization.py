"""Mặt phẳng phân quyền PDM + Casbin: bằng chứng ALLOW và bằng chứng DENY.

Vì sao mỗi quyền cần CẢ HAI
----------------------------
Một bộ test chỉ khẳng định "admin làm được X" sẽ xanh với một hàm
`authorize()` luôn trả True. Nửa còn lại — "viewer KHÔNG làm được X" — mới là
nửa chứng minh có một ranh giới. §45 PDM liệt kê chúng thành cặp vì lý do đó,
và tệp này giữ đúng hình dạng ấy.

Ba nhóm, ba loại hạ tầng
-------------------------
1. Thuần Python. Danh mục quyền, thống trị phạm vi, hình dạng model.conf.
   Chạy ở đâu cũng được, và bắt được phần lớn lỗi vì phần lớn lỗi là ở việc
   xếp quyền vào sai role.

2. Casbin với adapter GIẢ. Chứng minh engine cư xử đúng với một tập policy
   biết trước — không có Postgres, không có độ trễ, không có dữ liệu thật.
   Đây là nơi kiểm thống trị phạm vi và cách ly tenant, vì cả hai là tính chất
   của model.conf + chuỗi domain chứ không phải của cơ sở dữ liệu.

3. Tích hợp, cần Postgres sống. Chứng minh các truy vấn LỌC đúng: assignment
   đã thu hồi, membership đã gỡ, role đã vô hiệu. Ba điều kiện đó là thứ duy
   nhất adapter thật làm khác adapter giả, nên đó là thứ duy nhất nhóm này cần
   kiểm.

Dọn dẹp
-------
Nhóm 3 GHI vào cơ sở dữ liệu thật. Mọi định danh do nó tạo mang tiền tố
`pytest-authz`, và fixture xoá sạch ở cả đường thành công lẫn đường lỗi. Bài
học đã trả giá trong repo này: một lượt chạy suite từng để lại 37 tệp trong kho
pháp lý thật vì mỗi tệp test tự lo dọn dẹp.
"""

from __future__ import annotations

import uuid

import pytest

from app.authorization import catalog
from app.authorization.adapter import (
    project_domain,
    role_subject,
    subject,
    tenant_domain,
    workspace_domain,
)
from app.authorization.catalog import BUILTIN_ROLES, BY_CODE, PERM, PERMISSIONS
from app.authorization.scope_resolver import ScopeContext, build_domains
from app.storage import authz_schema


# ===========================================================================
# 1. Danh mục — thuần Python
# ===========================================================================

class TestCatalogue:
    def test_every_permission_code_is_well_formed(self):
        """Cùng luật mà `ck_permissions_code_shape` cưỡng chế ở cơ sở dữ liệu.

        Kiểm ở đây nữa vì seed chạy trong `_run_ddl`, nơi nuốt lỗi: một mã sai
        hình dạng sẽ bị Postgres từ chối, để lại một dòng WARNING, và quyền đó
        đơn giản là không tồn tại lúc chạy — endpoint dùng nó từ chối tất cả.
        """
        import re

        pattern = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
        bad = [p.code for p in PERMISSIONS if not pattern.match(p.code)]
        assert bad == []

    def test_no_duplicate_permission_codes(self):
        codes = [p.code for p in PERMISSIONS]
        assert len(codes) == len(set(codes))

    def test_system_permissions_are_never_api_assignable(self):
        """§17. Khoá API của tenant không bao giờ cầm được quyền nền tảng."""
        leaked = [p.code for p in PERMISSIONS
                  if p.scope == catalog.SYSTEM and p.api_assignable]
        assert leaked == []

    def test_builtin_roles_respect_scope_dominance(self):
        """Cùng bất biến mà trigger `ct_role_permissions_dominance` cưỡng chế."""
        rank = {"SYSTEM": 4, "TENANT": 3, "WORKSPACE": 2, "PROJECT": 1}
        violations = [
            (role.code, code)
            for role in BUILTIN_ROLES
            for code in role.permissions
            if rank[role.scope] < rank[BY_CODE[code].scope]
        ]
        assert violations == []

    def test_platform_admin_holds_everything(self):
        """Nó là ánh xạ của `users.is_admin`, vốn không bị giới hạn gì.

        Nếu test này đỏ sau khi thu hẹp `platform_admin` một cách CÓ CHỦ Ý ở
        Phase D, hãy sửa nó — nhưng chỉ sau khi shadow mode đã sạch, vì thu hẹp
        trong lúc còn so sánh cũ-mới sẽ tạo ra mismatch do chính test này gây ra.
        """
        role = next(r for r in BUILTIN_ROLES if r.code == "platform_administrator")
        assert set(role.permissions) == {p.code for p in PERMISSIONS}

    def test_tenant_admin_holds_no_system_permission(self):
        """Quản trị viên tenant KHÔNG phải quản trị viên nền tảng."""
        role = next(r for r in BUILTIN_ROLES if r.code == "tenant_administrator")
        system = [c for c in role.permissions if BY_CODE[c].scope == catalog.SYSTEM]
        assert system == []

    def test_viewer_roles_cannot_write_anything(self):
        """Không quyền nào của viewer mang động từ ghi.

        Dựa vào quy ước đặt tên, cùng quy ước mà `_read_only()` dùng để dựng ba
        role đó. Nếu một quyền ghi lọt vào vì tên nó kết thúc bằng `.read`, thì
        cái sai nằm ở TÊN QUYỀN — và đó cũng đáng đỏ.
        """
        write_verbs = (".create", ".update", ".delete", ".manage", ".publish",
                       ".submit", ".cancel", ".promote", ".annotate", ".invite",
                       ".remove", ".suspend", ".purge", ".staff")
        for name in ("workspace_viewer", "project_viewer"):
            role = next(r for r in BUILTIN_ROLES if r.code == name)
            bad = [c for c in role.permissions if c.endswith(write_verbs)]
            assert bad == [], f"{name} cam quyen ghi: {bad}"

    def test_legacy_map_covers_every_value_the_check_constraint_allows(self):
        """`tenant_members_role_valid` cho phép 'admin' | 'editor' | NULL.

        Hai giá trị KHÔNG NULL phải dịch được sang role dựng sẵn. Một giá trị
        không dịch được sẽ làm `_legacy_decision` trả False cho mọi thứ — người
        dùng đó mất sạch quyền trong shadow mode mà không có lỗi nào.

        NULL cố ý KHÔNG có mặt trong bản đồ: nó nghĩa là "không vai", nên không
        có gì để dịch. Xem `catalog.RETIRED_BUILTIN_ROLES`.
        """
        assert set(catalog.LEGACY_TENANT_ROLE_MAP) == {"admin", "editor"}
        builtin_codes = {r.code for r in BUILTIN_ROLES}
        assert set(catalog.LEGACY_TENANT_ROLE_MAP.values()) <= builtin_codes
        assert catalog.LEGACY_SYSTEM_ADMIN_ROLE in builtin_codes

    def test_retired_roles_are_gone_from_the_catalogue(self):
        """Vai đã nghỉ không được còn sống trong danh mục.

        Chốt tự kiểm lúc import đã canh giao của hai danh sách; test này canh vế
        còn lại — `tenant_viewer` thật sự không còn ai dựng ra được. Thiếu nó,
        một lần thêm lại role đó sẽ đi qua mọi test hiện có.
        """
        assert "tenant_viewer" in catalog.RETIRED_BUILTIN_ROLES
        assert "tenant_viewer" not in {r.code for r in BUILTIN_ROLES}
        assert "tenant_viewer" not in catalog.LEGACY_TENANT_ROLE_MAP.values()

    def test_no_builtin_tenant_role_reads_the_whole_tenant_read_only(self):
        """Không có vai dựng sẵn nào gói trọn bộ quyền đọc phạm vi TENANT.

        Đây là điều `tenant_viewer` từng làm, và là lý do nó nghỉ: bốn phép đọc
        trong bộ đó — hoá đơn, nhật ký kiểm toán, khoá API, đồng thuận — không
        thuộc về một vai tên "chỉ xem". Ai cần chúng thì nhận qua role TỰ TẠO
        của tổ chức, nơi có người ký tên vào quyết định.

        Chỉ soi vai TENANT không-quản-trị: `tenant_owner` và
        `tenant_administrator` đương nhiên cầm hết, và đó không phải chuyện này.
        """
        tenant_reads = {p.code for p in PERMISSIONS
                        if p.scope == catalog.TENANT and p.code.endswith(".read")}
        exempt = {"tenant_owner", "tenant_administrator"}
        offenders = [
            r.code for r in BUILTIN_ROLES
            if r.scope == catalog.TENANT and r.code not in exempt
            and tenant_reads <= set(r.permissions)
        ]
        assert offenders == []

    def test_permissions_requiring_passcode_are_all_high_risk(self):
        """Bắt xác thực nâng cấp cho một thao tác thường là làm phiền vô ích."""
        wrong = [p.code for p in PERMISSIONS
                 if p.requires_passcode and p.risk == catalog.NORMAL]
        assert wrong == []


# ===========================================================================
# 2. Chuỗi domain — thống trị phạm vi, thuần Python
# ===========================================================================

class TestDomainChain:
    CTX = ScopeContext(tenant_id="t", workspace_id="w", project_id="p")

    def test_project_permission_walks_the_whole_chain(self):
        """§14: hẹp trước, rộng sau. Tenant admin do đó thống trị được project."""
        assert build_domains(self.CTX, "PROJECT") == [
            project_domain("p"), workspace_domain("w"), tenant_domain("t"), "sys",
        ]

    def test_tenant_permission_never_asks_a_narrower_domain(self):
        """Đây là nửa chứng minh KHÔNG leo thang được.

        `project_manager` dù được gán ở bao nhiêu project cũng không chạm được
        vào một quyền phạm vi TENANT, vì `prj:` không bao giờ nằm trong chuỗi.
        """
        assert build_domains(self.CTX, "TENANT") == [tenant_domain("t"), "sys"]
        assert build_domains(self.CTX, "WORKSPACE") == [
            workspace_domain("w"), tenant_domain("t"), "sys",
        ]

    def test_system_permission_only_asks_sys(self):
        assert build_domains(self.CTX, "SYSTEM") == ["sys"]

    def test_missing_links_shorten_the_chain_they_do_not_widen_it(self):
        """Tenant chưa backfill: không có project/workspace.

        Chuỗi ngắn lại (chỉ `ten:` và `sys`), nghĩa là quyền phạm vi PROJECT
        chỉ cấp được từ vai tenant trở lên. Hỏng theo hướng CHẶT.
        """
        partial = ScopeContext(tenant_id="t")
        assert build_domains(partial, "PROJECT") == [tenant_domain("t"), "sys"]

    def test_empty_context_leaves_only_the_platform_domain(self):
        assert build_domains(ScopeContext(), "PROJECT") == ["sys"]

    def test_domains_of_two_tenants_never_collide(self):
        assert tenant_domain("a") != tenant_domain("b")
        assert subject("x") != role_subject("x")


# ===========================================================================
# 3. Casbin với adapter giả
# ===========================================================================

def _casbin_adapter_base():
    from casbin.persist import Adapter

    return Adapter


class _FakeAdapter(_casbin_adapter_base()):
    """Adapter nạp một tập policy biết trước.

    Cùng giao diện với `ReadOnlyPolicyAdapter` nhưng không chạm cơ sở dữ liệu,
    nên các test dưới đây kiểm ĐÚNG model.conf + chuỗi domain và không thể đỏ
    vì một lý do khác.

    PHẢI kế thừa `casbin.persist.Adapter`: `Enforcer.__init__` làm
    `isinstance(adapter, Adapter)` và ném `RuntimeError("Invalid parameters")`
    chứ không phải `AttributeError` — một thông báo không nói gì về nguyên nhân.
    """

    def __init__(self, p_rules, g_rules):
        self.p_rules = p_rules
        self.g_rules = g_rules

    def load_policy(self, model):
        for role, perm in self.p_rules:
            model.add_policy("p", "p", [role, perm])
        for user, role, domain in self.g_rules:
            model.add_policy("g", "g", [user, role, domain])

    def save_policy(self, model):
        raise NotImplementedError

    def add_policy(self, sec, ptype, rule):
        raise NotImplementedError

    def remove_policy(self, sec, ptype, rule):
        raise NotImplementedError

    def remove_filtered_policy(self, sec, ptype, field_index, *field_values):
        raise NotImplementedError


def _enforcer(p_rules, g_rules):
    import casbin

    from app.authorization.enforcer import MODEL_PATH

    return casbin.Enforcer(str(MODEL_PATH), _FakeAdapter(p_rules, g_rules))


ADMIN = subject("admin-uuid")
VIEWER = subject("viewer-uuid")
OUTSIDER = subject("outsider-uuid")
R_TENANT_ADMIN = role_subject("role-tenant-admin")
R_PROJECT_VIEWER = role_subject("role-project-viewer")
R_PROJECT_EDITOR = role_subject("role-project-editor")


@pytest.fixture
def enforcer():
    return _enforcer(
        p_rules=[
            (R_TENANT_ADMIN, PERM.SAMPLE_DELETE),
            (R_TENANT_ADMIN, PERM.TENANT_BILLING_MANAGE),
            (R_PROJECT_VIEWER, PERM.SAMPLE_READ),
            (R_PROJECT_EDITOR, PERM.SAMPLE_READ),
            (R_PROJECT_EDITOR, PERM.SAMPLE_ANNOTATE),
        ],
        g_rules=[
            (ADMIN, R_TENANT_ADMIN, tenant_domain("t1")),
            (VIEWER, R_PROJECT_VIEWER, project_domain("p1")),
            (OUTSIDER, R_TENANT_ADMIN, tenant_domain("t2")),
        ],
    )


class TestCasbinDecisions:
    CTX = ScopeContext(tenant_id="t1", workspace_id="w1", project_id="p1")

    def _allowed(self, enforcer, sub, permission):
        scope = BY_CODE[permission].scope
        return any(enforcer.enforce(sub, d, permission)
                   for d in build_domains(self.CTX, scope))

    # -- ALLOW ------------------------------------------------------------

    def test_project_viewer_can_read(self):
        e = _enforcer([(R_PROJECT_VIEWER, PERM.SAMPLE_READ)],
                      [(VIEWER, R_PROJECT_VIEWER, project_domain("p1"))])
        assert self._allowed(e, VIEWER, PERM.SAMPLE_READ)

    def test_project_editor_can_annotate(self, enforcer):
        e = _enforcer([(R_PROJECT_EDITOR, PERM.SAMPLE_ANNOTATE)],
                      [(VIEWER, R_PROJECT_EDITOR, project_domain("p1"))])
        assert self._allowed(e, VIEWER, PERM.SAMPLE_ANNOTATE)

    def test_tenant_admin_dominates_a_project_permission(self, enforcer):
        """§14, và đây là nửa quan trọng nhất của cả tệp.

        `admin` KHÔNG có assignment nào ở `prj:p1`. Nó vẫn xoá được mẫu trong
        project đó, vì chuỗi domain đi tiếp lên `ten:t1`. Không có tính chất
        này thì mỗi tenant admin phải được gán role ở từng project — và mỗi
        lần thu hồi phải nhớ gỡ tất cả.
        """
        assert not enforcer.enforce(ADMIN, project_domain("p1"), PERM.SAMPLE_DELETE)
        assert self._allowed(enforcer, ADMIN, PERM.SAMPLE_DELETE)

    # -- DENY -------------------------------------------------------------

    def test_project_viewer_cannot_delete(self, enforcer):
        assert not self._allowed(enforcer, VIEWER, PERM.SAMPLE_DELETE)

    def test_project_role_cannot_reach_a_tenant_permission(self, enforcer):
        """Không leo thang phạm vi, kiểm ở tầng engine.

        Ngay cả khi ai đó CỐ gán một quyền phạm vi TENANT cho một role phạm vi
        PROJECT (mà trigger dominance đã chặn ở cơ sở dữ liệu), chuỗi domain
        vẫn không bao giờ hỏi `prj:` cho quyền đó. Hai lớp, độc lập.
        """
        e = _enforcer(
            [(R_PROJECT_VIEWER, PERM.TENANT_BILLING_MANAGE)],
            [(VIEWER, R_PROJECT_VIEWER, project_domain("p1"))],
        )
        assert e.enforce(VIEWER, project_domain("p1"), PERM.TENANT_BILLING_MANAGE)
        assert not self._allowed(e, VIEWER, PERM.TENANT_BILLING_MANAGE)

    def test_role_in_another_tenant_grants_nothing_here(self, enforcer):
        """Cách ly tenant ở tầng phân quyền, độc lập với RLS."""
        assert not self._allowed(enforcer, OUTSIDER, PERM.SAMPLE_DELETE)
        assert not self._allowed(enforcer, OUTSIDER, PERM.TENANT_BILLING_MANAGE)

    def test_a_subject_with_no_role_at_all_is_denied(self, enforcer):
        assert not self._allowed(enforcer, subject("nobody"), PERM.SAMPLE_READ)

    def test_permission_matching_is_exact_not_prefix(self):
        """`sample.read` không được khớp `sample.read_raw` hay ngược lại.

        Nếu model.conf đổi sang `keyMatch` hay regex, test này đỏ — và nó nên
        đỏ, vì khớp mẫu trên mã quyền làm mọi quyền tương lai cùng tiền tố bị
        cấp kèm mà không ai để ý.
        """
        e = _enforcer([(R_PROJECT_VIEWER, "sample.read")],
                      [(VIEWER, R_PROJECT_VIEWER, project_domain("p1"))])
        assert e.enforce(VIEWER, project_domain("p1"), "sample.read")
        assert not e.enforce(VIEWER, project_domain("p1"), "sample.read_raw")
        assert not e.enforce(VIEWER, project_domain("p1"), "sample")


class TestReadOnlyAdapter:
    def test_every_write_path_raises(self):
        """§51 mục 2: không có bảng policy ghi được, kể cả qua API của Casbin.

        `pass` thay vì `raise` ở đây sẽ làm mọi `add_role_for_user()` trông như
        thành công rồi biến mất ở lần nạp lại — quyền cấp qua giao diện, chạy
        vài phút, tự bốc hơi.
        """
        from app.authorization.adapter import ReadOnlyPolicyAdapter

        adapter = ReadOnlyPolicyAdapter()
        with pytest.raises(NotImplementedError):
            adapter.save_policy(None)
        with pytest.raises(NotImplementedError):
            adapter.add_policy("p", "p", ["a", "b"])
        with pytest.raises(NotImplementedError):
            adapter.remove_policy("p", "p", ["a", "b"])
        with pytest.raises(NotImplementedError):
            adapter.remove_filtered_policy("p", "p", 0, "a")

    def test_queries_filter_all_three_ways_a_grant_ends(self):
        """Thu hồi, gỡ thành viên, vô hiệu role — bỏ sót cái nào cũng để lọt quyền.

        Kiểm bằng cách đọc chính SQL. Thô, nhưng nó bắt được đúng loại hồi quy
        đáng sợ nhất ở đây: một lần sửa truy vấn làm rơi mất một mệnh đề WHERE,
        và hậu quả là người đã bị gỡ khỏi tenant vẫn giữ nguyên quyền.
        """
        from app.authorization import adapter as ad

        for sql in (ad._Q_TENANT_ASSIGNMENTS, ad._Q_WORKSPACE_ASSIGNMENTS,
                    ad._Q_PROJECT_ASSIGNMENTS):
            assert "revoked_at IS NULL" in sql
            assert "m.status = 'ACTIVE'" in sql
            # v5: cột vòng đời của `memberships` là `left_at`, không phải
            # `removed_at` (tên cũ chỉ còn sống trong view tương thích).
            assert "m.left_at IS NULL" in sql
            assert "r.is_active" in sql

        assert "revoked_at IS NULL" in ad._Q_SYSTEM_ASSIGNMENTS
        assert "u.is_active" in ad._Q_SYSTEM_ASSIGNMENTS
        assert "p.is_active" in ad._Q_ROLE_PERMISSIONS


def _model_directives() -> str:
    """model.conf với phần chú thích bị bỏ đi.

    Bắt buộc, và bài học vừa trả giá: `assert "keyMatch" not in text` đỏ vì
    chính chú thích trong model.conf giải thích VÌ SAO không dùng `keyMatch`.
    Một khẳng định về hành vi không được đọc phần văn xuôi nói về hành vi.
    """
    from app.authorization.enforcer import MODEL_PATH

    return "\n".join(
        line for line in MODEL_PATH.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


class TestModelDefinition:
    def test_model_has_no_deny_effect(self):
        """Thuần allow-list. Xem chú thích trong model.conf về vì sao."""
        text = _model_directives()
        assert "some(where (p.eft == allow))" in text
        assert "!some" not in text
        assert "priority" not in text

    def test_role_definition_carries_a_domain(self):
        assert "g = _, _, _" in _model_directives(), \
            "g phai co ba thanh phan (user, role, domain)"

    def test_matcher_compares_permissions_exactly(self):
        text = _model_directives()
        assert "r.perm == p.perm" in text
        assert "keyMatch" not in text and "regexMatch" not in text


class TestMembershipNarrowsRatherThanDenies:
    """Mất tư cách thành viên tenant cắt thẩm quyền TENANT, không cắt SYSTEM.

    Từ chối thẳng ở đây là một lỗi tinh vi và tốn kém: người vận hành nền tảng
    thường KHÔNG phải thành viên của tenant họ đang xử lý (đình chỉ, xoá, hỗ
    trợ). Chặn họ sẽ làm mọi thao tác quản trị trả 403 — kể cả ở shadow mode,
    nơi theo định nghĩa không kết quả nào được phép đổi.
    """

    def _authorize_with(self, monkeypatch, *, is_member, actor):
        from app.authorization import authorization_service as svc

        monkeypatch.setattr(svc, "_membership_active",
                            lambda actor_id, ctx: is_member)
        monkeypatch.setattr(svc, "resolve",
                            lambda target: ScopeContext("t1", "w1", "p1"))
        monkeypatch.setattr(svc, "_mode", lambda: "legacy")
        return svc.authorize(actor, PERM.SAMPLE_DELETE, ("sample", "x"))

    def test_platform_admin_still_passes_without_tenant_membership(self, monkeypatch):
        d = self._authorize_with(monkeypatch, is_member=False,
                                 actor={"id": "u", "is_admin": True})
        assert d.allowed
        assert d.domains == ("sys",), "chuoi domain phai bi cat con moi sys"

    def test_a_plain_member_who_was_removed_loses_tenant_authority(self, monkeypatch):
        from app.authorization import authorization_service as svc

        monkeypatch.setattr(svc, "_legacy_decision",
                            lambda actor, perm, ctx: bool(actor.get("is_admin")))
        d = self._authorize_with(monkeypatch, is_member=False,
                                 actor={"id": "u", "is_admin": False})
        assert not d.allowed
        assert d.domains == ("sys",)

    def test_an_active_member_keeps_the_full_chain(self, monkeypatch):
        d = self._authorize_with(monkeypatch, is_member=True,
                                 actor={"id": "u", "is_admin": True})
        assert d.domains == ("prj:p1", "ws:w1", "ten:t1", "sys")


class TestPasscodeOrdering:
    def test_step_up_authorizes_before_it_asks_for_a_code(self, monkeypatch):
        """§16: mã hành động không bao giờ biến DENY thành ALLOW.

        Chứng minh bằng cách làm `verify` nổ nếu bị gọi. Nếu thứ tự bị đảo,
        `require_step_up` sẽ hỏi mã trước, gặp `AssertionError` thay vì
        `AuthorizationError`, và test đỏ.
        """
        from app.authorization import passcode
        from app.authorization.authorization_service import AuthorizationError, Decision

        def _never(*args, **kwargs):
            raise AssertionError("verify() da duoc goi TRUOC khi phan quyen cho qua")

        monkeypatch.setattr(passcode, "verify", _never)
        monkeypatch.setattr(
            "app.authorization.authorization_service.authorize",
            lambda actor, perm, target=None: Decision(
                False, perm, "test: tu choi", requires_passcode=True),
        )

        with pytest.raises(AuthorizationError):
            passcode.require_step_up({"id": "u"}, PERM.TENANT_PURGE, passcode="123456")

    def test_lock_windows_only_grow(self):
        windows = [w for _, w in passcode_thresholds()]
        assert windows == sorted(windows)


def passcode_thresholds():
    from app.authorization.passcode import LOCK_THRESHOLDS

    return LOCK_THRESHOLDS


# ===========================================================================
# 4. Tích hợp — cần Postgres sống
# ===========================================================================

def _live_conn():
    from app.storage.postgres_connection import connect_postgres

    try:
        return connect_postgres(connect_timeout=3)
    except Exception as exc:  # pragma: no cover - phụ thuộc môi trường
        pytest.skip(f"khong co Postgres song: {exc}")


@pytest.fixture
def authz_fixture():
    """Một tenant, hai người dùng, cây đầy đủ. Xoá sạch ở mọi đường ra.

    Định danh mang tiền tố `pytest-authz` và một hậu tố ngẫu nhiên, nên hai
    lượt chạy song song không giẫm lên nhau và một lượt chạy bị giết giữa
    chừng để lại thứ nhận ra được bằng mắt.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    suffix = uuid.uuid4().hex[:8]
    tenant = f"pytest-authz-{suffix}"
    data: dict = {"tenant": tenant}

    with system_scope("test: dung fixture phan quyen"):
        with _cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (tenant_id, display_name) VALUES (%s, %s)",
                (tenant, f"pytest authz {suffix}"))
            # `norole` thay cho `viewer` cũ: thành viên đang hoạt động, KHÔNG
            # có vai ở tầng tenant. Đó là trạng thái đã thay thế vai `viewer`,
            # nên nó phải là thứ được kiểm.
            for key in ("admin", "norole"):
                cur.execute(
                    "INSERT INTO users (id, username, email, password_hash, tenant_id) "
                    "VALUES (gen_random_uuid(), %s, %s, 'x', %s) RETURNING id",
                    (f"pytest-authz-{key}-{suffix}",
                     f"pytest-authz-{key}-{suffix}@example.invalid", tenant))
                data[key] = str(cur.fetchone()[0])
                # Ghi qua VIEW `tenant_members`, không thẳng `memberships`:
                # đường này là thứ 33 tệp khác đang dùng, nên nếu view mất tính
                # chèn được thì fixture phải là chỗ phát hiện.
                cur.execute(
                    "INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (%s,%s,%s)",
                    (tenant, data[key], "admin" if key == "admin" else None))

            cur.execute(
                "INSERT INTO workspaces (tenant_id, name, is_default) "
                "VALUES (%s, 'default', TRUE) RETURNING workspace_id", (tenant,))
            data["workspace"] = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO projects (tenant_id, workspace_id, name, is_default) "
                "VALUES (%s, %s, 'default', TRUE) RETURNING project_id",
                (tenant, data["workspace"]))
            data["project"] = str(cur.fetchone()[0])

            # Cây membership v5: WORKSPACE treo dưới TENANT, PROJECT treo dưới
            # WORKSPACE. `ct_membership_chain` từ chối nếu thiếu cha, nên thứ tự
            # ba câu dưới đây là bắt buộc chứ không phải thẩm mỹ.
            data["membership"] = {}
            for key in ("admin", "norole"):
                cur.execute(
                    "SELECT membership_id FROM memberships "
                    " WHERE scope_level = 'TENANT' AND tenant_id = %s AND user_id = %s",
                    (tenant, data[key]))
                tenant_membership = cur.fetchone()[0]
                data["membership"][key] = str(tenant_membership)

                cur.execute(
                    "INSERT INTO memberships (user_id, scope_level, tenant_id, "
                    "  workspace_id, parent_membership_id, status, joined_at) "
                    "VALUES (%s,'WORKSPACE',%s,%s,%s,'ACTIVE',NOW()) RETURNING membership_id",
                    (data[key], tenant, data["workspace"], tenant_membership))
                workspace_membership = cur.fetchone()[0]

                cur.execute(
                    "INSERT INTO memberships (user_id, scope_level, tenant_id, "
                    "  workspace_id, project_id, parent_membership_id, status, joined_at) "
                    "VALUES (%s,'PROJECT',%s,%s,%s,%s,'ACTIVE',NOW())",
                    (data[key], tenant, data["workspace"], data["project"],
                     workspace_membership))

            cur.execute(
                "SELECT role_id, role_code FROM roles WHERE is_builtin AND tenant_id IS NULL")
            data["roles"] = {code: str(rid) for rid, code in cur.fetchall()}

    try:
        yield data
    finally:
        # Thứ tự ngược lại thứ tự tạo. `tenants` cuối cùng vì mọi thứ khác trỏ
        # tới nó; `users` trước `tenants` vì `users.tenant_id` là khoá ngoại.
        with system_scope("test: don fixture phan quyen"), _cursor() as cur:
            # `role_assignments` không có `tenant_id`; nó ra đi theo
            # `fk_role_assignments_membership` (CASCADE) khi `memberships` bị
            # xoá. Chỉ assignment PHẠM VI HỆ THỐNG mới phải dọn tay, vì chúng
            # không treo dưới membership nào.
            cur.execute("DELETE FROM role_assignments "
                        " WHERE membership_id IS NULL AND user_id::text = ANY(%s)",
                        ([data["admin"], data["norole"]],))
            for table in ("memberships", "projects", "workspaces",
                          "audit_log", "roles"):
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant,))  # noqa: S608
            cur.execute("DELETE FROM users WHERE tenant_id = %s", (tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant,))


@pytest.mark.integration
class TestSchemaIsActuallyInstalled:
    def test_no_authorization_object_is_missing(self):
        """`_run_ddl` nuốt lỗi, nên "khởi động xong" không chứng minh gì.

        Đây là câu trả lời kiểm tra được cho "schema phân quyền đã cài đủ chưa".
        """
        conn = _live_conn()
        try:
            assert authz_schema.missing_objects(conn) == []
        finally:
            conn.close()

    def test_the_catalogue_in_the_database_matches_the_one_in_code(self):
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("test: doc danh muc quyen"):
            rows = _fetch_all(
                "SELECT permission_code, applicable_scope, requires_passcode "
                "FROM permissions WHERE is_active")
        in_db = {r["permission_code"]: r for r in rows}
        for perm in PERMISSIONS:
            assert perm.code in in_db, f"{perm.code} chua duoc seed"
            assert in_db[perm.code]["applicable_scope"] == perm.scope
            assert in_db[perm.code]["requires_passcode"] == perm.requires_passcode


@pytest.mark.integration
class TestAdapterFiltersAgainstRealData:
    """Ba cách một quyền chấm dứt, mỗi cách một test.

    Đây là thứ DUY NHẤT adapter thật làm khác adapter giả ở nhóm 3, nên đây là
    thứ duy nhất nhóm này kiểm.
    """

    def _load(self):
        from app.authorization.adapter import ReadOnlyPolicyAdapter

        import casbin

        from app.authorization.enforcer import MODEL_PATH

        return casbin.Enforcer(str(MODEL_PATH), ReadOnlyPolicyAdapter())

    def _grant_tenant_admin(self, fixture):
        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        with system_scope("test: cap role"), _cursor() as cur:
            cur.execute(
                "INSERT INTO role_assignments "
                "(user_id, role_id, membership_id, assigned_by_user_id) VALUES (%s,%s,%s,%s) "
                "RETURNING assignment_id",
                (fixture["admin"], fixture["roles"]["tenant_administrator"],
                 fixture["membership"]["admin"], fixture["admin"]))
            return str(cur.fetchone()[0])

    def test_an_active_grant_is_loaded(self, authz_fixture):
        self._grant_tenant_admin(authz_fixture)
        e = self._load()
        assert e.enforce(subject(authz_fixture["admin"]),
                         tenant_domain(authz_fixture["tenant"]),
                         PERM.SAMPLE_DELETE)

    def test_a_revoked_grant_is_never_loaded(self, authz_fixture):
        assignment = self._grant_tenant_admin(authz_fixture)
        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        with system_scope("test: thu hoi role"), _cursor() as cur:
            cur.execute(
                "UPDATE role_assignments SET revoked_at = NOW(), revoked_by_user_id = %s "
                " WHERE assignment_id = %s",
                (authz_fixture["admin"], assignment))

        e = self._load()
        assert not e.enforce(subject(authz_fixture["admin"]),
                             tenant_domain(authz_fixture["tenant"]),
                             PERM.SAMPLE_DELETE)

    def test_a_removed_membership_kills_a_still_active_grant(self, authz_fixture):
        """Trường hợp dễ quên nhất, và lý do adapter JOIN vào membership.

        Dòng gán VẪN `revoked_at IS NULL` — không ai thu hồi nó. Chỉ tư cách
        thành viên bị gỡ mềm. Không có phép JOIN kia, người này giữ nguyên
        quyền quản trị tenant sau khi đã bị đuổi khỏi tổ chức.
        """
        self._grant_tenant_admin(authz_fixture)
        from app.storage.metadata_db import _cursor, _fetch_all
        from app.tenant_context import system_scope

        with system_scope("test: go thanh vien"), _cursor() as cur:
            cur.execute(
                "UPDATE tenant_members SET status = 'REMOVED', removed_at = NOW() "
                " WHERE tenant_id = %s AND user_id = %s",
                (authz_fixture["tenant"], authz_fixture["admin"]))

        with system_scope("test: doc lai dong gan"):
            rows = _fetch_all(
                "SELECT a.revoked_at FROM role_assignments a "
                "  JOIN memberships m ON m.membership_id = a.membership_id "
                " WHERE m.tenant_id = %s AND a.user_id = %s AND m.scope_level = 'TENANT'",
                (authz_fixture["tenant"], authz_fixture["admin"]))
        assert rows and rows[0]["revoked_at"] is None, "dong gan phai VAN con hieu luc"

        e = self._load()
        assert not e.enforce(subject(authz_fixture["admin"]),
                             tenant_domain(authz_fixture["tenant"]),
                             PERM.SAMPLE_DELETE)

    def test_a_grant_in_one_tenant_does_not_reach_another(self, authz_fixture):
        self._grant_tenant_admin(authz_fixture)
        e = self._load()
        assert not e.enforce(subject(authz_fixture["admin"]),
                             tenant_domain("some-other-tenant"),
                             PERM.SAMPLE_DELETE)

    def test_a_member_without_a_tenant_role_gets_no_policy_line(self, authz_fixture):
        """Không vai = không có `g` nào ở domain tenant. Không phải "ít quyền hơn".

        Đây là vế Casbin của việc gỡ `tenant_viewer`. Nếu một dòng policy nào đó
        vẫn xuất hiện cho người này, nghĩa là ở đâu đó còn một mặc định cấp vai
        — đúng thứ lượt thay đổi này gỡ đi.
        """
        self._grant_tenant_admin(authz_fixture)
        e = self._load()
        for permission in (PERM.SAMPLE_READ, PERM.SAMPLE_DELETE, PERM.TENANT_READ):
            assert not e.enforce(subject(authz_fixture["norole"]),
                                 tenant_domain(authz_fixture["tenant"]),
                                 permission), permission

    def test_an_inactive_role_cannot_be_assigned_at_all(self, authz_fixture):
        """Vai đã nghỉ phải KHÔNG gán mới được — cưỡng chế ở cơ sở dữ liệu.

        Lớp này và bộ lọc `r.is_active` của adapter trả lời hai câu khác nhau,
        và thiếu lớp nào cũng để lại một nửa lỗ:

            trigger vắng  → giao diện cho gán một vai không bao giờ có hiệu lực,
                            và người dùng thấy "đã cấp" trong khi Casbin nói không
            bộ lọc vắng   → vai bị tắt vẫn cấp quyền cho những người đã mang nó

        Test này canh lớp thứ nhất; `test_an_inactive_role_is_never_projected`
        canh lớp thứ hai.
        """
        import psycopg2

        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        with system_scope("test: tao mot vai roi tat no"), _cursor() as cur:
            cur.execute(
                "INSERT INTO roles (tenant_id, role_code, role_name, description, "
                "scope_level, is_builtin, is_active) "
                "VALUES (%s, %s, %s, '', 'TENANT', FALSE, FALSE) RETURNING role_id",
                (authz_fixture["tenant"], "pytest_retired", "Pytest Retired"))
            dead_role = str(cur.fetchone()[0])

        with pytest.raises(psycopg2.errors.CheckViolation) as exc:
            with system_scope("test: thu gan vai da tat"), _cursor() as cur:
                cur.execute(
                    "INSERT INTO role_assignments "
                    "(user_id, role_id, membership_id, assigned_by_user_id) "
                    "VALUES (%s,%s,%s,%s)",
                    (authz_fixture["norole"], dead_role,
                     authz_fixture["membership"]["norole"], authz_fixture["admin"]))
        assert "inactive" in str(exc.value)

    def test_an_inactive_role_is_never_projected(self, authz_fixture):
        """Gán khi vai còn sống, rồi tắt vai: quyền phải biến mất khỏi policy.

        Đây là đường mà `RETIRED_BUILTIN_ROLES` đi qua — `seed.py` tắt vai chứ
        không xoá, và `role_permissions` được GIỮ LẠI để còn kiểm toán. Nếu
        adapter không lọc `r.is_active`, việc giữ lại đó biến thành một vai đã
        nghỉ vẫn cấp quyền.
        """
        assignment = self._grant_tenant_admin(authz_fixture)
        assert self._load().enforce(subject(authz_fixture["admin"]),
                                    tenant_domain(authz_fixture["tenant"]),
                                    PERM.SAMPLE_DELETE), "tien de: dang co quyen"

        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        with system_scope("test: tat vai"), _cursor() as cur:
            cur.execute("UPDATE roles SET is_active = FALSE WHERE role_id = %s",
                        (authz_fixture["roles"]["tenant_administrator"],))
        try:
            assert not self._load().enforce(subject(authz_fixture["admin"]),
                                            tenant_domain(authz_fixture["tenant"]),
                                            PERM.SAMPLE_DELETE)
            # Dòng gán VẪN còn và VẪN chưa bị thu hồi — đó là điểm của test:
            # thứ làm quyền biến mất là trạng thái của VAI, không phải của lần gán.
            with system_scope("test: doc lai dong gan"), _cursor() as cur:
                cur.execute("SELECT revoked_at FROM role_assignments "
                            " WHERE assignment_id = %s", (assignment,))
                assert cur.fetchone()[0] is None
        finally:
            # Vai dựng sẵn dùng chung cho mọi test; để nó tắt sẽ làm mọi tệp
            # chạy sau đỏ với một triệu chứng không liên quan gì tới nguyên nhân.
            with system_scope("test: bat lai vai"), _cursor() as cur:
                cur.execute("UPDATE roles SET is_active = TRUE WHERE role_id = %s",
                            (authz_fixture["roles"]["tenant_administrator"],))


@pytest.mark.integration
class TestLegacyAndAdapterAgreeOnMembership:
    """`tenant_role()` và adapter phải dùng CÙNG định nghĩa "còn là thành viên".

    Lệch nhau thì shadow mode báo bất đồng cho một khác biệt do chính hai truy
    vấn tạo ra — tiếng ồn che mất tín hiệu thật.

    Hôm nay `remove_member` xoá CỨNG nên đường này chưa bao giờ chạy trong sản
    xuất. Test dựng trạng thái gỡ MỀM bằng tay, chính là trạng thái mà một luồng
    gỡ mềm tương lai sẽ tạo ra.
    """

    def _soft_remove(self, tenant, user_id):
        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        with system_scope("test: go mem thanh vien"), _cursor() as cur:
            cur.execute(
                "UPDATE tenant_members SET status = 'REMOVED', removed_at = NOW() "
                " WHERE tenant_id = %s AND user_id = %s", (tenant, user_id))

    def test_tenant_role_sees_an_active_member(self, authz_fixture):
        from app.vocabulary_registry import tenant_role

        assert tenant_role(authz_fixture["tenant"], authz_fixture["admin"]) == "admin"

    def test_tenant_role_ignores_a_soft_removed_member(self, authz_fixture):
        """Bản vá 11/08. Trước đó hàm này trả 'admin' cho người đã bị gỡ."""
        from app.vocabulary_registry import can_edit_registry, tenant_role

        self._soft_remove(authz_fixture["tenant"], authz_fixture["admin"])
        assert tenant_role(authz_fixture["tenant"], authz_fixture["admin"]) is None
        # Và hệ quả thật sự quan trọng: cổng sửa danh mục đóng lại.
        assert not can_edit_registry(authz_fixture["tenant"], authz_fixture["admin"])

    def test_the_adapter_reaches_the_same_conclusion(self, authz_fixture):
        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope
        from app.vocabulary_registry import tenant_role

        with system_scope("test: cap role"), _cursor() as cur:
            cur.execute(
                "INSERT INTO role_assignments "
                "(user_id, role_id, membership_id, assigned_by_user_id) VALUES (%s,%s,%s,%s)",
                (authz_fixture["admin"], authz_fixture["roles"]["tenant_administrator"],
                 authz_fixture["membership"]["admin"], authz_fixture["admin"]))

        self._soft_remove(authz_fixture["tenant"], authz_fixture["admin"])

        import casbin

        from app.authorization.adapter import ReadOnlyPolicyAdapter
        from app.authorization.enforcer import MODEL_PATH

        e = casbin.Enforcer(str(MODEL_PATH), ReadOnlyPolicyAdapter())
        casbin_says = e.enforce(subject(authz_fixture["admin"]),
                                tenant_domain(authz_fixture["tenant"]),
                                PERM.SAMPLE_DELETE)
        legacy_says = tenant_role(authz_fixture["tenant"], authz_fixture["admin"]) is not None
        assert casbin_says == legacy_says is False, "hai ben phai cung noi KHONG"


class TestTheRolelessWriteGate:
    """Cổng chặn ghi cho tài khoản KHÔNG có grant tenant nào (`access_gate`).

    Thuần hàm, không cần cơ sở dữ liệu: cái đáng canh ở đây là DANH SÁCH đường
    tự phục vụ, và cả hai lỗi đã mắc đều là lỗi khớp chuỗi chứ không phải lỗi
    truy vấn.
    """

    def test_consent_actions_are_self_service(self):
        """Lỗi đã mắc: danh sách ghi `/legal/accept`, khớp KHÔNG GÌ CẢ.

        Đường thật là `/legal/{kind}/accept` — `kind` nằm GIỮA. Hậu quả: một
        thành viên chưa có vai không chấp nhận được điều khoản, tức là không bao
        giờ qua nổi cổng đồng thuận để dùng hệ thống.
        """
        from app.access_gate import _is_self_service_write

        for kind in ("terms", "privacy", "data_contribution", "guardian"):
            assert _is_self_service_write(f"/legal/{kind}/accept"), kind
            assert _is_self_service_write(f"/legal/{kind}/withdraw"), kind

    def test_the_identity_plane_is_self_service(self):
        from app.access_gate import _is_self_service_write

        for path in ("/auth/logout", "/auth/2fa/enable", "/account/profile",
                     "/verification/email/confirm", "/support/tickets",
                     "/notifications/read-all", "/trial/start"):
            assert _is_self_service_write(path), path

    def test_tenant_data_writes_are_NOT_self_service(self):
        """Vế quan trọng hơn: danh sách là CHO PHÉP, nên nó phải hẹp.

        Mỗi đường dưới đây ghi vào dữ liệu của tổ chức. Nếu một trong số chúng
        lọt vào danh sách tự phục vụ, cổng thành trang trí.
        """
        from app.access_gate import _is_self_service_write

        for path in ("/upload/video", "/classes/create", "/dataset/samples",
                     "/training/start", "/tenants/abc/invitations",
                     "/vocabulary/registry", "/legal/documents"):
            assert not _is_self_service_write(path), path


@pytest.mark.integration
class TestTheCompatibilityViewDoesNotBypassRls:
    """`tenant_members` là VIEW, nên nó KHÔNG nằm trong `RLS_TABLES` được nữa.

    Cái thay thế phép kiểm đó là `security_invoker`. Không có thuộc tính ấy,
    view chạy dưới quyền CHỦ SỞ HỮU và RLS trên `memberships` bị bỏ qua hoàn
    toàn — mọi tenant đọc được danh sách thành viên của mọi tenant khác, và
    không một dòng log nào nói gì.

    Đó là fail-OPEN ở mặt phẳng danh tính, đúng kiểu hỏng đã xảy ra ba lần
    trong dự án này. Nên nó phải có một test riêng chứ không nấp trong một
    danh sách bảng.
    """

    def test_the_view_is_declared_security_invoker(self):
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("test: doc thuoc tinh cua view"):
            rows = _fetch_all(
                "SELECT c.reloptions FROM pg_class c "
                "  JOIN pg_namespace n ON n.oid = c.relnamespace "
                " WHERE c.relname = 'tenant_members' AND c.relkind = 'v' "
                "   AND n.nspname = current_schema()")
        assert rows, "tenant_members phai la VIEW sau luot gop v5"
        options = rows[0]["reloptions"] or []
        assert any("security_invoker=true" in o.replace(" ", "") for o in options), (
            f"view tenant_members KHONG co security_invoker: {options}. "
            f"RLS tren memberships dang bi bo qua."
        )

    def test_the_base_table_carries_the_policy(self):
        """Vế còn lại: policy phải THẬT SỰ ở trên `memberships`."""
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("test: doc policy cua bang nen"):
            rows = _fetch_all(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                " WHERE relname = 'memberships' AND relkind = 'r'")
        assert rows and rows[0]["relrowsecurity"], "memberships chua bat RLS"
        assert rows[0]["relforcerowsecurity"], "memberships chua FORCE RLS"


@pytest.mark.integration
class TestRolesCatalogueRlsIsAsymmetric:
    """`roles` là bảng DUY NHẤT có USING rộng hơn WITH CHECK. Chứng minh cả hai vế.

    Vế đọc mà hỏng: tenant không thấy role dựng sẵn nào, nên không gán được
    role nào — giao diện quản lý thành viên trống trơn.

    Vế ghi mà hỏng: một tenant tạo được role `tenant_id IS NULL`, tức là role
    ở danh mục NỀN TẢNG. Vì `platform_admin` cầm mọi quyền SYSTEM, đó là đường
    leo thang đặc quyền thẳng từ tenant lên nền tảng. Vế này quan trọng hơn.
    """

    def test_a_tenant_can_read_the_platform_builtin_roles(self, authz_fixture):
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import tenant_scope

        with tenant_scope(authz_fixture["tenant"]):
            rows = _fetch_all(
                "SELECT role_code FROM roles WHERE is_builtin AND tenant_id IS NULL")
        names = {r["role_code"] for r in rows}
        assert "tenant_administrator" in names and "tenant_editor" in names

    def test_a_tenant_cannot_create_a_platform_role(self, authz_fixture):
        from app.storage.metadata_db import _cursor
        from app.storage.postgres_connection import current_role_privileges
        from app.tenant_context import tenant_scope

        # Chính sách RLS không ràng buộc được một role BYPASSRLS, nên với
        # DATABASE_URL trỏ vào superuser thì test này sẽ xanh một cách vô
        # nghĩa. Bỏ qua thay vì báo một đảm bảo không tồn tại.
        with _cursor() as cur:
            if current_role_privileges(cur.connection).can_bypass_rls:
                pytest.skip("DATABASE_URL dang tro vao role bo qua RLS")

        with tenant_scope(authz_fixture["tenant"]):
            with pytest.raises(Exception) as exc:
                with _cursor() as cur:
                    cur.execute(
                        "INSERT INTO roles (tenant_id, role_code, role_name, "
                        "                   scope_level, is_builtin) "
                        "VALUES (NULL, 'leo-thang', 'Leo thang', 'TENANT', TRUE)")
        assert "row-level security" in str(exc.value).lower()

    def test_a_tenant_can_create_a_role_of_its_own(self, authz_fixture):
        """Nửa còn lại: chính sách chặt nhưng không chặn việc hợp lệ."""
        from app.storage.metadata_db import _cursor
        from app.tenant_context import tenant_scope

        with tenant_scope(authz_fixture["tenant"]), _cursor() as cur:
            cur.execute(
                "INSERT INTO roles (tenant_id, role_code, role_name, scope_level) "
                "VALUES (%s, 'pytest-role-rieng', 'Vai rieng', 'PROJECT') "
                "RETURNING role_id",
                (authz_fixture["tenant"],))
            assert cur.fetchone()[0]
        # Dọn: fixture xoá theo tenant_id nên dòng này đi theo `DELETE FROM
        # roles`… mà fixture KHÔNG có. Xoá tại chỗ.
        from app.tenant_context import system_scope

        with system_scope("test: don role rieng"), _cursor() as cur:
            cur.execute("DELETE FROM roles WHERE tenant_id = %s", (authz_fixture["tenant"],))
