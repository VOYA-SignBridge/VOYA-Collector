"""HTTP layer for the SYSTEM CATALOG — the config template tenants clone from.

The service layer already existed (`seed_system_catalog`,
`publish_catalog_version`, `clone_catalog_to_tenant`) but nothing exposed it,
so the promise in docs/needFix/REGISTRY_ARCHITECTURE.md §2 — "admin sửa trong
app, redeploy không ghi đè" — could not actually be kept: the only way to change
the template was to edit a CSV and reinstall, which `ON CONFLICT DO NOTHING`
then ignored.

These endpoints were first written at /vocabulary/community. That was wrong:
this plane holds dialect and profile CONFIGURATION — no video, no landmarks, no
consent record, no attribution — while "Community" in CTU-SignBridge means
contributed data and its governance (docs/needFix/COMMUNITY_DATA_COMMONS.md).
The namespace has been handed back; the physical tables keep their
`community_*` names until a migration renames them.

Runs against the real Postgres like the other DB-backed suites. Every test that
writes cleans up after itself: a throwaway `test-*` dialect, and any
`community_versions` row minted during the test is deleted so the published
history the tenants' provenance points at is left exactly as found.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app import vocabulary_registry as vr
from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def client():
    from app.auth import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: {
        "id": None, "username": "tester", "is_admin": True,
    }
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def tenant_user_client():
    """A signed-in user who is NOT a system admin.

    `require_admin` is overridden to let the request through, so what is under
    test is the plane's OWN guard (`assert_system_admin`) rather than the
    dependency in front of it — the two are separate on purpose and either one
    alone would be enough to let a tenant user read the template if the other
    were ever relaxed.
    """
    from app.auth import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: {
        "id": None, "username": "tenant-user", "is_admin": False,
    }
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def throwaway_dialect():
    """A community dialect that exists only for the duration of one test."""
    did = f"test-{uuid.uuid4().hex[:8]}"
    db._execute(
        "INSERT INTO community_dialects(dialect_id, display_name, language, display_order) "
        "VALUES(%s, %s, 'vn', 9999)",
        (did, "Tạm thời"),
    )
    try:
        yield did
    finally:
        db._execute("DELETE FROM community_dialects WHERE dialect_id = %s", (did,))


@pytest.fixture
def version_floor():
    """Roll back any community version published during the test.

    Publishing is deliberately not transactional — it is an act of record — so
    the only honest cleanup is to delete what this test minted. Anything
    published before the test is left untouched.
    """
    rows = db._fetch_all("SELECT COALESCE(MAX(version), 0) AS v FROM community_versions")
    floor = int(rows[0]["v"])
    try:
        yield floor
    finally:
        db._execute("DELETE FROM community_versions WHERE version > %s", (floor,))


# ===========================================================================
# Read
# ===========================================================================

def test_overview_returns_live_catalogue_and_last_published(client):
    r = client.get("/api/v1/vocabulary/catalog")
    assert r.status_code == 200
    body = r.json()
    for key in ("dialects", "profiles", "content_hash", "latest_version",
                "latest_content_hash"):
        assert key in body
    assert body["dialects"], "the community template must not be empty after seeding"


def test_versions_list_omits_the_snapshot_bodies(client):
    r = client.get("/api/v1/vocabulary/catalog/versions?limit=5")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert "snapshot" not in item, (
            "a history list carrying every full catalogue is megabytes of response "
            "nobody asked for"
        )
        assert {"version", "content_hash"} <= set(item)


def test_missing_version_is_404_not_an_empty_body(client):
    assert client.get("/api/v1/vocabulary/catalog/versions/999999").status_code == 404


# ===========================================================================
# Guard — the template is system-admin only
# ===========================================================================

@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/vocabulary/catalog"),
    ("get", "/api/v1/vocabulary/catalog/versions"),
    ("post", "/api/v1/vocabulary/catalog/publish"),
    ("post", "/api/v1/vocabulary/catalog/seed"),
    ("post", "/api/v1/vocabulary/catalog/clone"),
])
def test_tenant_user_is_refused_on_every_community_route(tenant_user_client, method, path):
    # starlette 0.27's TestClient.get() takes no `json=`, so only the writes
    # carry a body — the guard runs before body parsing either way.
    kwargs = {"json": {}} if method == "post" else {}
    r = getattr(tenant_user_client, method)(path, **kwargs)
    assert r.status_code == 403


# ===========================================================================
# Edit
# ===========================================================================

def test_patch_dialect_updates_only_the_named_field(client, throwaway_dialect):
    r = client.patch(f"/api/v1/vocabulary/catalog/dialects/{throwaway_dialect}",
                     json={"display_name": "Đã đổi tên"})
    assert r.status_code == 200
    row = r.json()["dialect"]
    assert row["display_name"] == "Đã đổi tên"
    assert row["dialect_id"] == throwaway_dialect
    assert row["language"] == "vn", "an unnamed field must not be reset to its default"


def test_dialect_id_is_not_editable(client, throwaway_dialect):
    """It names directories, checkpoints and published split manifests."""
    r = client.patch(f"/api/v1/vocabulary/catalog/dialects/{throwaway_dialect}",
                     json={"dialect_id": "renamed"})
    assert r.status_code == 400
    assert "dialect_id" in r.json()["detail"]


def test_unknown_field_is_rejected_rather_than_ignored(client, throwaway_dialect):
    r = client.patch(f"/api/v1/vocabulary/catalog/dialects/{throwaway_dialect}",
                     json={"drop table": 1})
    assert r.status_code == 400


def test_patching_a_missing_dialect_is_404(client):
    r = client.patch("/api/v1/vocabulary/catalog/dialects/khong-ton-tai",
                     json={"display_name": "x"})
    assert r.status_code == 404


def test_patch_profile_roundtrip(client):
    row = db._fetch_all(
        "SELECT profile_id, display_name FROM community_profiles ORDER BY display_order LIMIT 1")
    if not row:
        pytest.skip("community profiles not seeded on this machine")
    pid, original = row[0]["profile_id"], row[0]["display_name"]
    try:
        r = client.patch(f"/api/v1/vocabulary/catalog/profiles/{pid}",
                         json={"display_name": "Tên thử"})
        assert r.status_code == 200
        assert r.json()["profile"]["display_name"] == "Tên thử"
    finally:
        db._execute("UPDATE community_profiles SET display_name = %s WHERE profile_id = %s",
                    (original, pid))


# ===========================================================================
# Publish
# ===========================================================================

def test_editing_does_not_publish(client, throwaway_dialect, version_floor):
    """A version is a deliberate act with a note attached. If every edit minted
    one, the history would fill with versions nobody chose to make and pinning a
    version would stop meaning anything."""
    client.patch(f"/api/v1/vocabulary/catalog/dialects/{throwaway_dialect}",
                 json={"display_name": "Sửa nhưng chưa publish"})
    rows = db._fetch_all("SELECT COALESCE(MAX(version), 0) AS v FROM community_versions")
    assert int(rows[0]["v"]) == version_floor


def test_publish_after_an_edit_mints_a_version_then_dedupes(client, throwaway_dialect,
                                                            version_floor):
    first = client.post("/api/v1/vocabulary/catalog/publish", json={"note": "test"})
    assert first.status_code == 200
    assert first.json()["created"] is True
    version = first.json()["version"]
    assert version > version_floor

    # Nothing changed in between: publishing again must return the version that
    # already holds this content instead of minting a byte-identical duplicate.
    second = client.post("/api/v1/vocabulary/catalog/publish", json={})
    assert second.json() == {"version": version, "created": False}

    body = client.get(f"/api/v1/vocabulary/catalog/versions/{version}").json()
    ids = [d["dialect_id"] for d in body["snapshot"]["dialects"]]
    assert throwaway_dialect in ids, "the frozen snapshot must contain what was live"


def test_published_snapshot_is_immutable_against_later_edits(client, throwaway_dialect,
                                                            version_floor):
    version = client.post("/api/v1/vocabulary/catalog/publish",
                          json={"note": "before edit"}).json()["version"]
    client.patch(f"/api/v1/vocabulary/catalog/dialects/{throwaway_dialect}",
                 json={"display_name": "Sau khi chốt"})

    frozen = client.get(f"/api/v1/vocabulary/catalog/versions/{version}").json()
    names = {d["dialect_id"]: d["display_name"] for d in frozen["snapshot"]["dialects"]}
    assert names[throwaway_dialect] != "Sau khi chốt", (
        "a frozen version that follows later edits answers nothing"
    )


# ===========================================================================
# Clone
# ===========================================================================

def test_clone_refuses_an_unknown_tenant(client):
    """`dialects.tenant_id` has no foreign key to `tenants`, so a typo would
    otherwise half-succeed: catalogue rows written under an unreachable tenant
    while the provenance UPDATE matches zero rows."""
    ghost = f"khong-co-{uuid.uuid4().hex[:6]}"
    r = client.post("/api/v1/vocabulary/catalog/clone", json={"tenant_id": ghost})
    assert r.status_code == 404
    assert not db._fetch_all("SELECT 1 FROM dialects WHERE tenant_id = %s", (ghost,)), (
        "nothing may be written before the tenant check"
    )


def test_clone_requires_a_tenant_id(client):
    assert client.post("/api/v1/vocabulary/catalog/clone", json={}).status_code == 400


def test_clone_into_the_existing_tenant_is_idempotent(client, version_floor):
    """Re-running never clobbers what the tenant has since changed."""
    before = vr.registry_version(vr.DEFAULT_TENANT)
    dialects_before = len(vr.list_dialects())

    r = client.post("/api/v1/vocabulary/catalog/clone",
                    json={"tenant_id": vr.DEFAULT_TENANT})
    assert r.status_code == 200
    assert len(vr.list_dialects()) == dialects_before
    assert r.json()["registry_version"] >= before


# ===========================================================================
# Boundary: the System Catalog is not, and must not become, "Community"
# ===========================================================================

def test_catalog_holds_configuration_only_never_contributed_data():
    """The line that decides what belongs here.

    A dialect list is configuration: it says which categories exist. A sample is
    contributed data: it came from a person, under a consent, with an
    attribution and a licence attached. The moment a media column, a consent
    reference or a contributor reference appears on these tables, the plane has
    quietly become a data commons without any of the governance one needs —
    review, immutable releases, grants, withdrawal.
    """
    forbidden = {
        "storage_key", "file_path", "media_type", "content_hash",
        "consent_id", "consent_record_id", "contributor_id", "attribution_id",
        "license_id", "sample_uid", "npz_path", "video_path",
    }
    for table in ("community_dialects", "community_profiles"):
        cols = {r["column_name"] for r in db._fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s", (table,))}
        leaked = sorted(cols & forbidden)
        assert not leaked, (
            f"{table} grew {leaked} — that is contributed data, and it needs the "
            f"Community Data Commons (docs/needFix/COMMUNITY_DATA_COMMONS.md), "
            f"not the system catalogue"
        )


def test_community_is_a_reserved_tenant_under_the_same_rules():
    """Community LÀ một tenant dự trữ — §10 đã đảo 12/08/2026.

    Bản trước của test này khẳng định điều NGƯỢC LẠI: không được có tenant tên
    `community`. PDM v5 chọn hướng kia, và lý do nằm ở
    `docs/needFix/COMMUNITY_DATA_COMMONS.md §10`: là một tenant, Community thừa
    hưởng nguyên bốn lớp phòng thủ đã có thay vì đòi một trục phân quyền song
    song với bốn cơ chế nhân đôi.

    Cái test này canh giờ là hình dạng của quyết định đó, không phải sự vắng mặt
    của nó: đúng MỘT tenant cộng đồng, mang đúng hai nhãn, và chỉ mục duy nhất
    phải có thật.
    """
    rows = db._fetch_all(
        "SELECT tenant_id, tenant_type, is_system_reserved FROM tenants "
        " WHERE tenant_type = 'COMMUNITY'")
    assert len(rows) == 1, f"phai co DUNG mot tenant cong dong, thay {len(rows)}"
    assert rows[0]["tenant_id"] == "community"
    assert rows[0]["is_system_reserved"] is True

    # Chỉ mục duy nhất là thứ làm câu "đúng một" thành một bất biến của cơ sở dữ
    # liệu chứ không phải một quy ước. Hai tenant cộng đồng nghĩa là hai không
    # gian mà `community_member` gán được, và câu "người dùng mới vào cộng đồng"
    # mất tính xác định.
    idx = db._fetch_all(
        "SELECT indexname FROM pg_indexes "
        " WHERE tablename = 'tenants' AND indexname = 'uq_tenants_single_community'")
    assert idx, "thieu uq_tenants_single_community — 'dung mot' khong duoc cuong che"


def test_community_is_subject_to_the_same_row_level_security():
    """Là tenant dự trữ KHÔNG có nghĩa là đứng ngoài RLS.

    Đây là nửa quan trọng nhất của việc đảo §10. Nếu Community được miễn RLS ở
    bất kỳ bảng nào, thì mọi lo ngại của §10 cũ trở thành hiện thực cùng một
    lúc: dữ liệu đóng góp nằm sau một hàng rào không tồn tại.

    Không có gì trong lược đồ được phép nói riêng về `community` — RLS là chính
    sách theo BẢNG, và tenant nào cũng đi qua cùng một vị từ.
    """
    from app.storage.rls import RLS_TABLES

    policies = {
        (r["tablename"], r["policyname"]): (r["qual"] or "")
        for r in db._fetch_all(
            "SELECT tablename, policyname, qual FROM pg_policies "
            " WHERE schemaname = current_schema()")
    }
    assert policies, "khong doc duoc policy nao — phep kiem nay se xanh vo nghia"

    special_cases = [
        f"{table}.{name}" for (table, name), qual in policies.items()
        if "community" in qual.lower()
    ]
    assert not special_cases, (
        f"policy RLS noi rieng ve community: {special_cases}. Tenant du tru van "
        f"phai di qua dung mot vi tu nhu moi tenant khac."
    )

    with_policy = {t for (t, _) in policies}
    missing = sorted(set(RLS_TABLES) - with_policy)
    assert not missing, f"bang trong RLS_TABLES nhung khong co policy: {missing}"


def test_is_system_reserved_is_never_read_by_authorisation():
    """`is_system_reserved` là NHÃN, không phải QUYỀN.

    Nó nói "đừng xoá tenant này, nó thuộc nền tảng". Ngày nó xuất hiện trong một
    phép kiểm quyền là ngày nó thành đường vòng: `if is_system_reserved: return
    True` ở đúng một chỗ là đủ để mở toang commons.

    Quét mã nguồn thay vì tin vào trí nhớ. Cột này chỉ được phép xuất hiện ở nơi
    ĐỊNH NGHĨA nó (`storage/authz_schema.py`).
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    allowed = {"storage/authz_schema.py"}

    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel in allowed:
            continue
        if "is_system_reserved" in path.read_text(encoding="utf-8"):
            offenders.append(rel)

    assert not offenders, (
        f"is_system_reserved bi doc ngoai noi dinh nghia: {offenders}. "
        f"Xem docs/needFix/COMMUNITY_DATA_COMMONS.md §10 — no la nhan, khong "
        f"phai quyen, va khong bao gio duoc lam duong vong phan quyen."
    )


def test_membership_alone_is_never_enough_in_the_community_tenant():
    """Rủi ro §10 cũ nêu, được cưỡng chế bằng mã: tư cách thành viên ≠ quyền.

    "Mọi đường *user thuộc tenant này thì cho qua* âm thầm trở thành đường vào
    commons" — đúng, và cách chặn nó KHÔNG phải là tránh làm Community thành
    tenant. Cách chặn là: không phép kiểm nào được cho qua chỉ vì có tư cách
    thành viên.

    `community_member` là vai mà mọi tài khoản mới nhận trong cộng đồng, nên tập
    quyền của nó chính là câu trả lời cho "có mặt trong commons thì được gì".
    Nó phải KHÔNG chứa quyền nào ở tầng quản trị.
    """
    from app.authorization.catalog import BUILTIN_BY_CODE, BY_CODE, COMMUNITY

    member = BUILTIN_BY_CODE["community_member"]

    # Ghim vào loại tenant: `ct_role_assignments_scope` từ chối gán vai này
    # trong một tenant tổ chức.
    assert member.tenant_type == COMMUNITY

    forbidden = [
        code for code in member.permissions
        if BY_CODE[code].risk != "NORMAL"
        or code.endswith((".manage", ".delete", ".purge", ".publish", ".invite",
                          ".remove", ".suspend"))
    ]
    assert not forbidden, (
        f"community_member cam quyen quan tri: {forbidden}. Vai nay la thu MOI "
        f"tai khoan moi nhan, nen tap quyen cua no chinh la nghia cua 'co mat "
        f"trong commons'."
    )

    # Và vế đối xứng: hai vai Community không rò ra khỏi Community.
    curator = BUILTIN_BY_CODE["community_curator"]
    assert curator.tenant_type == COMMUNITY


def test_the_catalog_router_no_longer_squats_on_the_community_namespace():
    """/vocabulary/community belongs to the data commons, not to config."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    squatting = sorted(p for p in paths if "/vocabulary/community" in p)
    assert not squatting, f"config endpoints still mounted under community: {squatting}"
    assert any("/vocabulary/catalog" in p for p in paths), "catalog routes missing"
