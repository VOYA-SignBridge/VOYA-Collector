"""Shared test bootstrap, for a repository that mixes two test styles.

Two jobs, both needed for `pytest backend/tests` to mean what it looks like it
means.

1. Environment. A bare `pytest` on the HOST is pointed at the localhost stack
   (the compose test-ports override publishes postgres:5432 + redis:6379) and at
   the repo's Google Drive credentials — so the suite runs with NO skips and no
   "forgot to export an env var" false failures. Only UNSET values are filled,
   so the real container env (postgres:/redis: hostnames, /gdrive paths) and
   anything exported explicitly are never overridden. On a machine without
   gdrive credentials the SOT integration tests still skip gracefully.

2. Collection. Most research-pipeline suites are STANDALONE scripts: pure-stdlib
   files with a main() that prints PASS/FAIL and returns an exit code, runnable
   without pytest inside the trainer container. Pytest collects nothing from them
   (they define no test_* functions), so a plain `pytest backend/tests` silently
   reported success while ~200 assertions never ran. They are ignored here and
   executed as subprocesses by test_research_suites.py, which asserts their exit
   codes.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# The standalone suites import from both the repo root and backend/.
for _p in (_REPO, _REPO / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# 1. Infra the compose test-ports override exposes on localhost. `setdefault`
#    leaves the docker/container env (postgres:/redis:) untouched.
for _key, _val in {
    "DATABASE_URL": "postgresql://admin:admin@localhost:5432/signdb",
    "REDIS_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
    "TTS_REDIS_URL": "redis://localhost:6379/0",
    # A pepper for the OTP digests. `setdefault`, so a real deployment's value
    # is never overridden — but present, because `app/tokens.py` refuses to hash
    # a six-digit code without one, and that refusal is deliberate: a test run
    # that silently fell back to a plain hash would be exercising a scheme the
    # product does not use.
    "OTP_PEPPER": "pytest-pepper-not-a-production-secret-32ch",
}.items():
    os.environ.setdefault(_key, _val)

# 1b. Kho tài liệu pháp lý phải nằm NGOÀI `dataset/legal` thật.
#
# `os.environ[...]`, không phải `setdefault`: đây là lá chắn, và một lá chắn
# nhường chỗ cho giá trị có sẵn thì không chắn gì cả. Container test kế thừa môi
# trường của ảnh backend, nên `setdefault` sẽ im lặng để nguyên đường thật.
#
# Vì sao cần: từ v6, `legal.register_document` GHI MỘT TỆP mỗi lần công bố. Mọi
# test công bố văn bản — và có bốn tệp test làm vậy — sẽ rải blob vào kho thật.
# Sổ dấu vết không bắt được: nó theo dõi HÀNG trong cơ sở dữ liệu, không theo
# dõi tệp trên đĩa.
#
# Đã xảy ra: một lượt chạy suite để lại 37 tệp trong `dataset/legal` với nội
# dung kiểu "Nội dung privacy.". Vá bằng cách thêm fixture vào từng tệp test là
# mời tệp thứ năm quên tiếp — cùng bài học với `purge_registered_account`.
#
# Test nào cần một kho riêng biệt cho riêng nó vẫn `monkeypatch.setenv` như
# thường; dòng này chỉ đảm bảo mặc định KHÔNG BAO GIỜ là kho thật.
_LEGAL_STORE_FOR_TESTS = Path(tempfile.gettempdir()) / "voya-test-legal-store"
_LEGAL_STORE_FOR_TESTS.mkdir(parents=True, exist_ok=True)
os.environ["LEGAL_STORE_ROOT"] = str(_LEGAL_STORE_FOR_TESTS)

# 2. Point Google Drive at the repo's gdrive/ (host absolute path) so the SOT
#    integration tests find the credentials and RUN instead of skipping. If the
#    files aren't present (e.g. CI), we leave it alone and those tests skip.
_gdrive = _REPO / "gdrive"
if (_gdrive / "credentials.json").exists():
    os.environ.setdefault("GOOGLE_DRIVE_CREDENTIALS", str(_gdrive / "credentials.json"))
if (_gdrive / "token.json").exists():
    os.environ.setdefault("GOOGLE_DRIVE_TOKEN", str(_gdrive / "token.json"))

# 2b. A real hand-sign clip for the video->npz extraction test. Point it at the
#     first clip in a known sample folder if present, so the test RUNS (no skip)
#     on the data machine and skips gracefully elsewhere.
#
#     /testvideos is the CONTAINER path: the suite runs inside voya_backend_test
#     with only the repo mounted, so the Windows path below is invisible there
#     and the dataset/raw_videos fallback is empty since the PENDING uploads
#     were purged. Mounting a clip folder read-only at /testvideos is what keeps
#     this test running rather than skipping:
#
#       -v "E:\CTU_ProjectOutside\Videos:/testvideos:ro"
if not os.environ.get("VOYA_TEST_VIDEO"):
    _vids = []
    for _cand in (
        Path("/testvideos"),
        _REPO / "sample_clips",
        Path("E:/CTU_ProjectOutside/Videos"),
    ):
        try:
            _vids = sorted(_cand.glob("*.mp4")) if _cand.exists() else []
        except Exception:
            _vids = []
        if _vids:
            break
    if not _vids:
        # Neither of the two locations above exists on the data machine — the
        # real uploads live under dataset/raw_videos/<lang>/<dialect>/<class>/,
        # so the extraction test skipped even where clips were present. Search
        # there too (recursively, first match wins) and keep excluding the
        # rendered skeleton previews under dataset/features/, which have no real
        # hands for MediaPipe to find and would fail the test for the wrong
        # reason.
        _raw = _REPO / "dataset" / "raw_videos"
        try:
            _vids = sorted(_raw.rglob("*.mp4"))[:1] if _raw.exists() else []
        except Exception:
            _vids = []
    if _vids:
        os.environ["VOYA_TEST_VIDEO"] = str(_vids[0])

# 3. Drive root folder id (needed so SOT publishes into the shared folder, not
#    the service account's My Drive). Read just that key out of the repo .env.
if not os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID"):
    _envf = _REPO / ".env"
    if _envf.exists():
        for _line in _envf.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line.startswith("GOOGLE_DRIVE_ROOT_FOLDER_ID=") and not _line.startswith("#"):
                os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"] = _line.split("=", 1)[1].strip()
                break

import pytest


class _MirroringOverrides(dict):
    """`app.dependency_overrides` biết rằng "có admin" cũng có nghĩa "có người dùng".

    Vì sao cần lớp này
    ------------------
    `app/access_gate.py` chặn mọi request không có phiên, và nó hỏi
    `get_current_user_optional`. Hơn hai chục test giả lập đăng nhập bằng cách
    ghi đè `require_admin` hoặc `get_current_user` — hai thứ khác. Cổng không
    thấy chúng, nên các test đó nhận 401 trước khi chạm tới điều chúng kiểm.

    Ba cách chữa, và vì sao chọn cách này:

    * Sửa hơn hai chục fixture để ghi đè thêm một dependency nữa: đúng nhưng
      lặp lại, và fixture thứ hai mươi ba viết sau sẽ quên.
    * Cho cổng dò xem `require_admin` có bị ghi đè không: đó là mã production
      biết về pytest — không chấp nhận được.
    * Gương chiếu ở conftest, một chỗ, có tài liệu. Nó chỉ nói ra một điều vốn
      đã đúng: một test tuyên bố "người gọi là quản trị viên" thì cũng đang
      tuyên bố "người gọi đã đăng nhập".

    Không gương chiếu ngược lại: ghi đè `get_current_user_optional` KHÔNG hàm ý
    người đó là quản trị viên.
    """

    @staticmethod
    def _as_optional(value):
        """Biến một bản ghi đè quyền thành bản ghi đè danh tính.

        Bản ghi đè `require_admin` cho một người KHÔNG phải quản trị viên
        thường là một hàm ném 403. Chiếu thẳng nó sang
        `get_current_user_optional` khiến cổng bắt được ngoại lệ và kết luận
        "chưa đăng nhập" — rồi trả 401 thay vì để endpoint trả 403. Test khi đó
        kiểm sai thứ: nó tưởng đang kiểm phân quyền, thực ra đang kiểm xác thực.

        Nên: 403 có nghĩa là **đã đăng nhập, không đủ quyền**. Trả về một người
        dùng tối thiểu để cổng cho đi tiếp, và để phép kiểm quyền thật sự diễn
        ra ở endpoint.
        """

        def _resolve(*args, **kwargs):
            try:
                return value(*args, **kwargs)
            except Exception:
                return {"id": None, "username": "test", "is_admin": False}

        # FastAPI ĐỌC CHỮ KÝ của một dependency để biết phải bơm gì vào. Bản
        # đầu để nguyên `(*_args, **_kwargs)`, nên FastAPI kết luận dependency
        # này cần hai THAM SỐ TRUY VẤN tên `_args` và `_kwargs` — và mọi
        # endpoint nào phụ thuộc `get_current_user_optional` trả về
        # **422 Unprocessable Entity** thay vì chạy.
        #
        # Cụ thể là mọi endpoint có `Depends(limit_catalog)` và họ hàng, vì các
        # dependency giới hạn tần suất đều phụ thuộc `get_current_user_optional`.
        # Triệu chứng không hề gợi tới conftest: test gọi một route quản trị
        # hoàn toàn bình thường và nhận lại lỗi thiếu tham số truy vấn cho hai
        # cái tên không xuất hiện ở đâu trong mã production. Phát hiện
        # 2026-08-08 khi viết `test_admin_audit_api.py`.
        #
        # Mượn chữ ký của chính bản ghi đè: FastAPI sẽ phân giải đúng những gì
        # `value` khai báo (thường là không gì cả) rồi chuyển tiếp xuống.
        import inspect
        try:
            _resolve.__signature__ = inspect.signature(value)
        except (TypeError, ValueError):
            _resolve.__signature__ = inspect.Signature()

        return _resolve

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        from app.auth import get_current_user, get_current_user_optional, require_admin

        if key is get_current_user:
            super().__setitem__(get_current_user_optional, value)
        elif key is require_admin and get_current_user not in self:
            # Chỉ chiếu từ `require_admin` khi KHÔNG có bản ghi đè
            # `get_current_user` — cái đó cụ thể hơn và phải thắng.
            super().__setitem__(get_current_user_optional, self._as_optional(value))

    def __delitem__(self, key):
        super().__delitem__(key)
        self._drop_mirror(key)

    def pop(self, key, *default):
        result = super().pop(key, *default)
        self._drop_mirror(key)
        return result

    def _drop_mirror(self, key):
        from app.auth import get_current_user, get_current_user_optional, require_admin

        if key in (require_admin, get_current_user):
            super().pop(get_current_user_optional, None)


@pytest.fixture(scope="session", autouse=True)
def _mirror_auth_overrides():
    """Cài lớp gương chiếu một lần cho cả phiên chạy."""
    from app.main import app

    app.dependency_overrides = _MirroringOverrides(app.dependency_overrides)
    yield


@pytest.fixture(autouse=True)
def _platform_scope():
    """Run every test as platform work, the way Celery and the CLIs do.

    Once row-level security is enforced, a connection with no tenant scope sees
    zero rows. Production code always has a scope by the time it reaches the
    database — the HTTP middleware sets one per request, `task_prerun` sets one
    per Celery task, `platform_command` sets one per CLI. A bare pytest function
    has none of those, so without this fixture most of the suite would query an
    empty-looking database and fail for a reason that has nothing to do with
    what it is testing.

    Choosing SYSTEM scope rather than a tenant is deliberate: the suite operates
    on fixtures belonging to several tenants and asserts on totals, which is
    exactly what platform scope is for.

    This does not weaken the isolation proof. `test_tenant_isolation.py` opens
    its own connections and sets each scope explicitly, including the unscoped
    case, so the fail-closed behaviour is still asserted directly rather than
    inherited from the ambient state.
    """
    from app.tenant_context import system_scope

    with system_scope("pytest: suite runs as platform"):
        yield


# ---------------------------------------------------------------------------
# Rate-limit isolation for HTTP tests
#
# The rate limiter is real, backed by the same Redis the stack uses, and its
# counters outlive a test run. Any suite that registers accounts or attempts
# logins therefore spends a shared budget: run the file twice and the second
# run gets 429s that look like application failures.
#
# Two pieces are needed together, and neither works alone:
#   * a loopback PEER, so the app trusts the forwarding header at all
#   * a fresh forwarded IP per call, so each request lands in its own bucket
#
# Kept here rather than in one test file because two suites need it and two
# copies would drift — the second copy is how one suite quietly stops being
# isolated.
# ---------------------------------------------------------------------------

#: Ranges TRUSTED_PROXIES covers by default. An address drawn from these would
#: be treated as one of our own proxies and SKIPPED when the X-Forwarded-For
#: chain is walked right-to-left, silently falling back to the peer — i.e. the
#: bucket collision this helper exists to avoid, hit at random now and then.
PRIVATE_FIRST_OCTETS = {10, 127, 172, 192}


class LoopbackPeer:
    """Present a real loopback peer address to the app under test.

    starlette 0.27's TestClient hardcodes the ASGI peer as the literal string
    `"testclient"`, which is not an IP, so `rate_limit._is_trusted()` rejects it
    and `client_ip()` ignores forwarding headers outright. That is the
    production rule working as intended — a caller must not get to choose which
    IP the limits count — but it also disables per-test isolation: every request
    collapses onto ONE bucket.

    127.0.0.1 is inside the default TRUSTED_PROXIES, so the peer is trusted and
    the X-Forwarded-For each request sends is honoured again. starlette 0.27 has
    no `client=` argument (added later), hence the wrapper.
    """

    def __init__(self, app, peer=("127.0.0.1", 50000)):
        self.app = app
        self.peer = peer

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope, client=self.peer)
        await self.app(scope, receive, send)


def fresh_client_ip() -> str:
    """A public-looking address no other test or run will pick.

    Fully random rather than sequential: Redis keys live an hour, so a counter
    scheme would collide across runs on the same machine — which is precisely
    the failure this exists to prevent.
    """
    import random

    while True:
        first = random.randint(1, 223)
        if first not in PRIVATE_FIRST_OCTETS:
            break
    return (
        f"{first}.{random.randint(0, 255)}."
        f"{random.randint(0, 255)}.{random.randint(1, 254)}"
    )


def registration_consents() -> dict:
    """The consent fields a `POST /auth/register` must carry on THIS deployment.

    Read from the live documents rather than hardcoded, for two reasons that
    each produced a red suite:

    * **Hardcoding a version gives 409 `stale_version`.** The suite runs on a
      copy of the real database, where the legal documents are published with
      real version strings that change when someone publishes a new one.
    * **Hardcoding the FIELDS gives 400 `consent_required` on a deployment that
      has published nothing.** Consent enforcement switches on by publishing —
      "no documents" is a valid state, not an outage — so the correct payload
      there is no consent fields at all.

    Six tests across three files were failing on the first case after the legal
    documents went live: they were written before enforcement existed and
    registration quietly started requiring something they never sent.
    """
    from app import legal

    if legal.missing_for_registration():
        return {}
    out = {}
    for kind in legal.REQUIRED_AT_REGISTRATION:
        doc = legal.current_document(kind)
        if doc:
            out[f"accepted_{kind}_version"] = str(doc["version"])
    return out


# ---------------------------------------------------------------------------
# Throwaway tenants
#
# These suites run against the LIVE database, so a half-removed test tenant
# would sit in the operator's list forever. Deletion order matters: every
# tenant-scoped table carries ON DELETE RESTRICT against `tenants`, and several
# reference each other (samples -> classes -> dialects), so the children go
# first or the delete is refused — which is the constraint working, not a bug.
# ---------------------------------------------------------------------------

#: Leaf-first. `users` is not deleted, only moved home: an account may have been
#: created by another fixture that owns its lifetime.
#:
#: THỨ TỰ LÀ MỘT PHẦN CỦA TÍNH ĐÚNG, không phải sở thích. Mọi bảng ở đây mang
#: khoá ngoại `ON DELETE RESTRICT` tới `tenants`, và nhiều bảng tham chiếu lẫn
#: nhau; con phải đi trước cha, nếu không câu xoá bị từ chối — và bị từ chối là
#: ràng buộc đang làm việc, không phải lỗi.
#:
#: Sáu bảng schema v3 được chèn vào đúng vị trí phụ thuộc của chúng, không phải
#: nối vào cuối. Nối vào cuối là cách hỏng: `capture_sessions` tham chiếu
#: `classes` và `signers`, nên xoá nó sau hai bảng kia sẽ thất bại. Danh sách
#: này phải khớp với `metadata_db.TENANT_SCOPED_TABLES`, và
#: `test_tenant_purge_order_covers_every_tenant_table` là thứ giữ hai bên khớp.
#: NHẬP LẠI từ mã sản xuất, không giữ bản sao.
#:
#: Bản trước là một tuple chép tay ở đây, song song với thứ tự mà một hàm xoá
#: thật cũng cần. Hai bản sao của một thứ tự phụ thuộc là thứ trôi ra khỏi nhau
#: ngay lần thêm bảng tiếp theo — và khi chúng lệch, cái lệch không lộ ra ở
#: đây mà lộ ra lúc xoá tenant thật trên sản xuất. `tenant_lifecycle.PURGE_ORDER`
#: giờ là nguồn duy nhất; `test_tenant_purge_order_covers_every_tenant_table`
#: vẫn canh nó khớp `metadata_db.TENANT_SCOPED_TABLES`.
from app.tenant_lifecycle import PURGE_ORDER as _TENANT_PURGE_ORDER  # noqa: E402


# ---------------------------------------------------------------------------
# SỔ DẤU VẾT: bộ test để lại gì, hiện ra, rồi dọn
#
# Bốn lần dữ liệu test rò vào dữ liệu thật, và cả bốn lần đều được vá bằng cách
# sửa teardown của đúng fixture gây ra lần đó. Cách vá ấy hỏng vì nó phụ thuộc
# vào việc MỖI fixture nhớ dọn phần MÌNH tạo — và fixture thứ N+1 luôn quên.
#
# Cơ chế ở đây không hỏi fixture nào cả. Nó chụp tập KHOÁ CHÍNH của các bảng dễ
# rò trước khi suite chạy, chụp lại sau khi xong, và hiệu hai tập chính là mọi
# hàng bộ test đã sinh ra — bất kể fixture nào tạo, có khai báo hay không.
#
# In ra TRƯỚC khi xoá, vì thấy được mình vừa tạo ra gì là một phần của kết quả
# chạy test. Kiểm lại SAU khi xoá, vì "đã chạy lệnh xoá" và "hàng đã biến mất"
# là hai chuyện khác nhau.
# ---------------------------------------------------------------------------

#: Bảng theo dõi, LÁ TRƯỚC GỐC, kèm biểu thức khoá chính.
#:
#: MỘT danh sách cho cả ba việc: chụp ảnh, xoá, và kiểm lại. Bản đầu tôi viết
#: hai dict — một để chụp, một để xoá — với nội dung y hệt nhau. Đó đúng là
#: kiểu "hai bản sao rồi trôi ra khỏi nhau" mà tôi vừa dọn ở ba chỗ khác trong
#: chính phiên này; sửa ngay thay vì để lại.
#:
#: Thứ tự là lá-trước-gốc và nó LÀ một phần của tính đúng: mọi bảng ở đây đều
#: bị bảng khác trỏ tới, nên xoá cha trước con sẽ bị khoá ngoại từ chối.
_ARTIFACT_TABLES = (
    # v4 — không bảng nào bị bảng khác trỏ tới, nên chúng đứng đầu danh sách
    # lá-trước-gốc. `webhook_deliveries` phải trước `webhook_endpoints`.
    ("webhook_deliveries", "delivery_id::text"),
    ("webhook_endpoints", "endpoint_id::text"),
    ("api_keys", "key_id::text"),
    ("tenant_exports", "export_id::text"),
    ("tenant_usage_daily", "tenant_id || ':' || usage_date::text || ':' || metric"),
    ("tenant_subscriptions", "subscription_id::text"),
    ("tenant_purges", "purge_id::text"),
    ("audit_log", "audit_id::text"),
    ("training_job_classes", "job_id || ':' || class_idx"),
    ("samples", "sample_uid"),
    ("capture_sessions", "capture_session_id::text"),
    ("signer_consents", "consent_id::text"),
    ("signer_aliases", "tenant_id || ':' || old_signer_id"),
    ("user_consents", "consent_id::text"),
    ("verification_codes", "challenge_id::text"),
    ("tenant_invitations", "invitation_id::text"),
    ("tenant_members", "tenant_id || ':' || user_id::text"),
    ("training_jobs", "job_id"),
    ("classes", "class_uid"),
    ("vocabulary_groups", "tenant_id || ':' || group_id"),
    ("dialects", "tenant_id || ':' || dialect_id"),
    ("signers", "signer_id"),
    # v6 — sổ đăng bạ trước, rồi bản nháp, rồi văn bản. Sổ không có khoá ngoại
    # nào (cố ý: nó phải sống lâu hơn thứ nó ghi lại), nhưng giữ thứ tự
    # lá-trước-gốc cho nhất quán với phần còn lại của danh sách.
    ("legal_document_events", "event_id::text"),
    ("legal_document_drafts", "draft_id::text"),
    ("legal_documents", "doc_id::text"),
    ("platform_settings", "key"),
    ("users", "id::text"),
    ("tenants", "tenant_id"),
)


#: Bảng có trigger chặn mọi DELETE. Sổ dấu vết vẫn phải dọn được chúng.
#:
#: Nghe như mâu thuẫn, nhưng không: bất biến "chỉ-thêm" nói rằng **vai ứng
#: dụng** không được xoá dòng nào — đó là thứ bảo vệ sổ đăng bạ pháp lý khỏi
#: chính mã ứng dụng. Việc dọn dẹp của bộ test là công việc của người chủ bảng,
#: một vai khác hẳn, và nó tắt trigger một cách CÔNG KHAI trong `_purge_append_
#: only` thay vì đi cửa sau.
#:
#: Bỏ chúng khỏi sổ thì rẻ hơn, nhưng sai: hàng test sẽ tích lại trên bản sao
#: mà không ai thấy, và đúng cái lớp lỗi mà sổ này tồn tại để bắt sẽ có một chỗ
#: trốn.
_APPEND_ONLY_TABLES = {"legal_document_events"}


def _purge_append_only(table: str, key_expr: str, keys: list) -> int:
    """Xoá hàng test khỏi một bảng chỉ-thêm, qua vai migration.

    Vai ứng dụng không tắt được trigger (nó không sở hữu bảng), và đó chính là
    điều làm bất biến có giá trị. Vai migration sở hữu bảng, nên nó làm được —
    và mọi câu ở đây nằm trong CÙNG một giao dịch, nên trigger không thể ở lại
    trạng thái tắt nếu bước xoá hỏng giữa chừng.
    """
    from app.storage.metadata_db import _migration_cursor

    trigger = "trg_legal_events_append_only"
    with _migration_cursor() as cur:
        cur.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")  # noqa: S608
        try:
            cur.execute(
                f"DELETE FROM {table} WHERE {key_expr} = ANY(%s)",  # noqa: S608
                (keys,))
            return cur.rowcount or 0
        finally:
            cur.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")  # noqa: S608


def _artifact_snapshot() -> dict:
    """Tập khoá chính của mỗi bảng theo dõi. Bảng chưa tồn tại thì bỏ qua."""
    from app.storage import metadata_db as db
    from app.tenant_context import system_scope

    out = {}
    with system_scope("test ledger: chup anh truoc/sau suite"):
        for table, key in _ARTIFACT_TABLES:
            try:
                rows = db._fetch_all(f"SELECT {key} AS k FROM {table}")  # noqa: S608
                out[table] = {r["k"] for r in rows}
            except Exception:
                out[table] = None  # bảng chưa có trên máy này
    return out


def _database_is_production() -> bool:
    """`signdb` ĐÚNG BẰNG tên đó là sản xuất; `signdb_test` là bản sao."""
    import re

    match = re.search(r"/([^/?]+)(\?|$)", os.getenv("DATABASE_URL", ""))
    return bool(match) and match.group(1) == "signdb"


#: Tệp dữ liệu mà bộ test PHẢI trả lại nguyên trạng.
#:
#: `dataset/signers.csv` là nguồn sự thật của danh sách người ký, và nó nằm
#: ngoài cơ sở dữ liệu — nên việc chạy suite trên một bản sao Postgres KHÔNG
#: che được đường ghi này. Đã trả giá: `test_upload_camera_training` tạo tài
#: khoản `pipe_*`, endpoint upload gọi `resolve_signer_for_user()` ghi thêm một
#: dòng vào CSV, còn teardown chỉ xoá hàng trong `users`. Sau nhiều lượt chạy,
#: 30 dòng rác `pipe_*` nằm lại trong tệp dữ liệu thật (phát hiện 2026-08-08).
_FILES_THE_SUITE_MUST_NOT_CHANGE = ("signers.csv", "labels.csv")


@pytest.fixture(scope="session", autouse=True)
def _restore_dataset_files():
    """Chụp ảnh vài tệp dữ liệu trước suite và trả lại nguyên trạng sau suite.

    Chọn khôi phục thay vì cấm ghi, vì cấm ghi sẽ làm hỏng chính những test cần
    kiểm đường ghi đó. Khôi phục cho cả hai: đường ghi vẫn được kiểm thật, và
    tệp thật vẫn không đổi.

    Bảo đảm này là TỔNG QUÁT — nó không phụ thuộc vào việc từng fixture có nhớ
    dọn hay không, mà đó chính là thứ đã hỏng ba lần trước.
    """
    from app.config import settings

    root = Path(settings.dataset_root)
    snapshot = {}
    for name in _FILES_THE_SUITE_MUST_NOT_CHANGE:
        path = root / name
        if path.exists():
            snapshot[path] = path.read_bytes()

    yield

    for path, content in snapshot.items():
        try:
            if path.read_bytes() != content:
                path.write_bytes(content)
                print(f"\n[conftest] da tra lai nguyen trang {path.name} "
                      f"(mot test da ghi vao tep du lieu that)")
        except Exception as exc:  # pragma: no cover
            print(f"\n[conftest] KHONG tra lai duoc {path}: {exc}")


#: Ảnh chụp trước suite, do `pytest_sessionstart` đặt và
#: `pytest_terminal_summary` đọc.
_ARTIFACT_BEFORE: dict = {}


def pytest_sessionstart(session):
    """Chụp ảnh vạch xuất phát, SAU khi lược đồ đã đầy đủ.

    Bản đầu tôi làm việc này trong một fixture cấp session, và nó sai hai lần:

    1. Finalizer của fixture cấp session chạy SAU khi trình báo cáo terminal đã
       đóng, nên báo cáo không hiện ra dòng nào — đúng thứ người dùng yêu cầu
       lại là thứ duy nhất không chạy.
    2. Fixture cấp session chạy TRƯỚC mọi fixture cấp module gọi
       `ensure_tables()`. Trên cơ sở dữ liệu chưa migrate, ảnh chụp đầu sẽ
       thiếu 250 hàng `capture_sessions`, 10 hàng `tenant_members` và 2 hàng
       `signers` do chính migration sinh ra — rồi bước dọn coi chúng là dấu vết
       của bộ test và XOÁ đi. Chạy suite một lần sẽ huỷ kết quả backfill.

    Cặp hook `sessionstart` + `terminal_summary` sửa cả hai: nó chạy đủ sớm để
    đặt vạch xuất phát và đủ muộn để in được.
    """
    global _ARTIFACT_BEFORE
    try:
        from app.storage import metadata_db as db

        # `migrate_database()` chứ không phải `ensure_tables()`, và đây là chỗ
        # DUY NHẤT trong bộ test gọi nó.
        #
        # Từ 12/08/2026 `ensure_tables()` chỉ còn THÊM: phần một chiều (chép dữ
        # liệu sang `memberships`, bỏ bảng cũ, bỏ chỉ mục toàn cục) chỉ chạy
        # dưới lệnh migration. Khoảng ba mươi tệp test có fixture riêng gọi
        # `ensure_tables()`, và tất cả vẫn đúng — vì hook này chạy TRƯỚC hết,
        # nên tới lượt chúng thì cơ sở dữ liệu đã ở phiên bản hiện hành và
        # "thêm cho đủ" là vừa đủ.
        #
        # `stamp=False` rồi đóng dấu CÓ ĐIỀU KIỆN: bộ test chạy trên cơ sở dữ
        # liệu phát triển dùng chung, và một dòng `schema_migrations` mới sau
        # mỗi lượt chạy sẽ biến sổ đăng bạ — thứ để đọc khi có sự cố — thành
        # nhật ký của pytest. Nhưng phải có ĐÚNG MỘT dấu, nếu không mọi test
        # gọi `init_db()` sẽ vấp cổng phiên bản.
        db.migrate_database(stamp=False)

        from app.storage.schema_version import (
            APP_SCHEMA_VERSION, read_schema_version, stamp_schema_version,
        )

        with db._migration_cursor() as cur:
            if read_schema_version(cur) is None:
                stamp_schema_version(cur, APP_SCHEMA_VERSION, note="pytest bootstrap")

        _ARTIFACT_BEFORE = _artifact_snapshot()
    except Exception as exc:  # pragma: no cover
        _ARTIFACT_BEFORE = {}
        print(f"[so dau vet] khong chup duoc anh truoc suite: {exc}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Hiện ra mọi hàng bộ test đã tạo, rồi dọn, rồi kiểm lại.

    Ba bước, và bước giữa là thứ được yêu cầu: **thấy được** dấu vết trước khi
    nó biến mất. Một lượt chạy im lặng rồi tự dọn thì không phân biệt được với
    một lượt chạy không tạo gì cả.

    Trên CƠ SỞ DỮ LIỆU SẢN XUẤT thì chỉ BÁO CÁO, không xoá: hiệu hai lần chụp
    ảnh bao gồm cả hàng do người dùng thật tạo trong lúc suite chạy, và xoá
    nhầm hàng đó tệ hơn nhiều so với để lại vài hàng test.
    """
    def say(line=""):
        terminalreporter.write_line(line)

    if not _ARTIFACT_BEFORE:
        return

    before = _ARTIFACT_BEFORE
    try:
        after = _artifact_snapshot()
    except Exception as exc:  # pragma: no cover
        say(f"[so dau vet] khong chup duoc anh sau suite: {exc}")
        return

    delta = {}
    for table, keys_after in after.items():
        keys_before = before.get(table)
        if keys_before is None or keys_after is None:
            continue
        new = keys_after - keys_before
        if new:
            delta[table] = new

    say()
    say("=" * 68)
    if not delta:
        say("  SO DAU VET: bo test khong de lai hang nao. Sach.")
        say("=" * 68)
        return

    tong = sum(len(v) for v in delta.values())
    say(f"  SO DAU VET — bo test da tao {tong} hang tren {len(delta)} bang")
    say("-" * 68)
    for table in sorted(delta):
        keys = sorted(delta[table])
        vidu = ", ".join(str(k)[:24] for k in keys[:3])
        them = f" (+{len(keys) - 3} nua)" if len(keys) > 3 else ""
        say(f"  {table:<24} +{len(keys):<5} {vidu}{them}")
    say("-" * 68)

    if _database_is_production():
        say("  DATABASE_URL tro vao 'signdb' (SAN XUAT) -> CHI BAO CAO, KHONG XOA.")
        say("  Hieu hai lan chup anh co the chua ca hang do nguoi dung that tao")
        say("  ra trong luc suite chay; xoa nham hang do te hon nhieu so voi de")
        say("  lai vai hang test. Hay chay lai suite tren mot ban sao.")
        say("=" * 68)
        return

    from app.storage import metadata_db as db
    from app.tenant_context import system_scope

    # Xoá theo LÔ bằng `= ANY(%s)`, không phải một câu mỗi hàng: một lượt chạy
    # tạo vài trăm hàng thì vài trăm vòng round-trip biến bước dọn thành phần
    # chậm nhất của cả suite.
    #
    # Nếu cả lô hỏng (thường vì một khoá ngoại chưa lường trước) thì lùi về xoá
    # từng hàng, để một hàng vướng không kéo theo cả lô ở lại — và tên hàng
    # vướng hiện ra trong báo cáo thay vì chìm trong một thông báo chung.
    da_xoa, that_bai = 0, []
    with system_scope("test ledger: don dau vet cua suite"):
        for table, key_expr in _ARTIFACT_TABLES:
            keys = sorted(delta.get(table) or ())
            if not keys:
                continue
            if table in _APPEND_ONLY_TABLES:
                # Bảng có trigger chặn DELETE. Xem `_purge_append_only`.
                try:
                    da_xoa += _purge_append_only(table, key_expr, keys)
                except Exception as exc:
                    that_bai.append(f"{table}:* ({exc.__class__.__name__})")
                continue
            sql = f"DELETE FROM {table} WHERE {key_expr} = ANY(%s)"  # noqa: S608
            try:
                db._execute(sql, (keys,))
                da_xoa += len(keys)
            except Exception:
                for k in keys:
                    try:
                        db._execute(
                            f"DELETE FROM {table} WHERE {key_expr} = %s",  # noqa: S608
                            (k,))
                        da_xoa += 1
                    except Exception as exc:
                        that_bai.append(f"{table}:{k} ({exc.__class__.__name__})")

    con_lai = _artifact_snapshot()
    sot = {}
    for table, keys in delta.items():
        still = con_lai.get(table)
        if still:
            left = keys & still
            if left:
                sot[table] = left

    say(f"  Da xoa {da_xoa}/{tong} hang.")
    if that_bai:
        say(f"  {len(that_bai)} cau xoa that bai: {', '.join(that_bai[:5])}")
    if sot:
        say("  CON SOT LAI (kiem lai sau khi xoa):")
        for table, keys in sorted(sot.items()):
            say(f"    {table:<24} {len(keys)} hang: {sorted(keys)[:3]}")
        say("  Day la ro ri that — sua teardown cua fixture da tao chung.")
    else:
        say("  Kiem lai: 0 hang con sot. Du lieu tra ve dung trang thai truoc suite.")
    say("=" * 68)


@pytest.fixture(scope="module")
def corpus_row_to_poke():
    """Bảo đảm có ÍT NHẤT một mẫu để các test ràng buộc đâm vào.

    Vì sao cần, và vì sao mãi tới 2026-08-10 mới cần
    ------------------------------------------------
    Các test ở `test_schema_constraints.py` chứng minh một ràng buộc chặn thật
    bằng cách **sửa một dòng có sẵn**::

        UPDATE samples SET signer_id = 'KHONG_TON_TAI'
         WHERE sample_uid = (SELECT sample_uid FROM samples LIMIT 1)

    Trên cơ sở dữ liệu RỖNG, câu đó chạm 0 dòng. Không có gì vi phạm, không có
    ngoại lệ nào được ném, và `pytest.raises(ForeignKeyViolation)` đỏ — với một
    thông báo ("DID NOT RAISE") nghe như ràng buộc đã biến mất, trong khi ràng
    buộc vẫn nguyên vẹn.

    Suốt từ trước tới nay bộ test luôn chạy trên **bản sao của sản xuất**, nơi
    3.860 mẫu có sẵn, nên khoảng trống này không lộ ra. Nó chỉ lộ khi lần đầu
    chạy suite trên một CSDL dựng từ số không — tức khi dựng CI.

    Là no-op khi đã có dữ liệu: trên bản sao sản xuất fixture này không chèn gì
    và không xoá gì. Nó chỉ hành động khi thật sự rỗng, và dọn đúng phần mình
    tạo ra.
    """
    import uuid as _uuid

    from app.storage import metadata_db as db
    from app.tenancy import DEFAULT_TENANT_ID
    from app.tenant_context import system_scope

    with system_scope("test: bảo đảm corpus có dòng để thử ràng buộc"):
        if db._fetch_all("SELECT 1 FROM samples LIMIT 1"):
            yield None          # đã có dữ liệu thật — không đụng vào
            return

        tag = _uuid.uuid4().hex[:8]
        class_uid = f"seed_cls_{tag}"
        signer_id = f"SEED{tag[:6].upper()}"
        # `samples_uid_is_hex10` đòi ĐÚNG 10 ký tự hex thường. Một tiền tố dễ
        # đọc kiểu `seed_smp_…` bị CHECK từ chối — và thông báo lỗi khi đó nói
        # về ràng buộc chứ không nói về fixture, nên ghi rõ ở đây.
        sample_uid = _uuid.uuid4().hex[:10]
        db._execute(
            "INSERT INTO classes (tenant_id, class_uid, slug, label_original) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (DEFAULT_TENANT_ID, class_uid, f"seed-{tag}", "hạt giống cho test ràng buộc"))
        db._execute(
            "INSERT INTO signers (tenant_id, signer_id, display_name) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (DEFAULT_TENANT_ID, signer_id, f"Seed {tag}"))
        db._execute(
            "INSERT INTO samples (tenant_id, sample_uid, class_uid, signer_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (DEFAULT_TENANT_ID, sample_uid, class_uid, signer_id))

    yield sample_uid

    # Dọn từng câu trong `try` riêng: một câu hỏng không được phép chặn câu sau.
    # Cùng bài học với `_purge_account` — teardown phải chịu được thất bại từng
    # phần, nếu không dòng cuối (thứ quan trọng nhất) không bao giờ chạy tới.
    with system_scope("test cleanup: gỡ hạt giống corpus"):
        for sql, args in (
            ("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,)),
            ("DELETE FROM signers WHERE tenant_id = %s AND signer_id = %s",
             (DEFAULT_TENANT_ID, signer_id)),
            ("DELETE FROM classes WHERE tenant_id = %s AND class_uid = %s",
             (DEFAULT_TENANT_ID, class_uid)),
        ):
            try:
                db._execute(sql, args)
            except Exception:
                pass


@pytest.fixture
def rollback_cursor():
    """Con trỏ luôn được rollback, buộc vào SYSTEM scope.

    Dùng cho mọi test CỐ TÌNH ghi để chứng minh một ràng buộc từ chối. Ba file
    từng chép ba bản gần giống nhau của fixture này; gom về đây để chúng không
    trôi ra khỏi nhau — bản trong `test_real_email_identities.py` đã suýt thiếu
    `apply_scope`, và thiếu nó thì kết quả đổi nghĩa hoàn toàn.

    Buộc scope là bắt buộc chứ không phải tiện tay: các bảng này có chính sách
    row-level security, nên một kết nối không scope trượt ở `WITH CHECK` TRƯỚC
    khi khoá ngoại được hỏi tới. Test vẫn đỏ-rồi-xanh, nhưng xanh vì
    `InsufficientPrivilege` chứ không phải vì ràng buộc dưới thử nghiệm — tức
    là ràng buộc đó không hề chạy.
    """
    import psycopg2

    from app.storage import metadata_db as db
    from app.storage.rls import apply_scope
    from app.tenant_context import system_scope

    conn = psycopg2.connect(db.settings.database_url)
    conn.autocommit = False
    try:
        with system_scope("test: exercise a constraint on purpose"):
            with conn.cursor() as cur:
                apply_scope(cur)
                yield cur
    finally:
        conn.rollback()
        conn.close()


def purge_tenant(tenant_id: str) -> None:
    """Remove a throwaway tenant and everything pointing at it."""
    from app.storage import metadata_db as db
    from app.tenancy import DEFAULT_TENANT_ID
    from app.tenant_context import system_scope

    with system_scope("test cleanup: remove a throwaway tenant"):
        for table in _TENANT_PURGE_ORDER:
            db._execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
        db._execute(
            "UPDATE users SET tenant_id = %s WHERE tenant_id = %s",
            (DEFAULT_TENANT_ID, tenant_id),
        )
        db._execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant_id,))


#: Bảng trỏ tới `users`, xoá trước khi xoá tài khoản.
#:
#: `users` có 16 khoá ngoại trỏ về; đây là những bảng mà một tài khoản TEST
#: thực sự chạm tới. Mỗi câu trong `try` riêng, có chủ ý: ở lượt chạy đầu trên
#: một cơ sở dữ liệu mới, một bảng có thể chưa tồn tại, và một `UndefinedTable`
#: giữa chừng sẽ khiến câu `DELETE FROM users` cuối cùng không bao giờ chạy tới.
#: Đó đúng là cách lần rò thứ ba xảy ra — xem [[testing-infra]].
_USER_CHILD_TABLES = (
    "refresh_tokens", "password_reset_tokens", "verification_codes",
    "user_consents", "tenant_members",
)


def purge_registered_account(username: str) -> None:
    """Xoá một tài khoản test VÀ tổ chức mà lượt đăng ký của nó vừa tạo.

    MỘT bản, dùng chung. Trước đó có bốn bản gần giống nhau nằm ở bốn tệp test
    (`test_tenant_lifecycle`, `test_login_rate_limit`, `test_legal_consent`, và
    tệp v4 mới), và ba trong bốn bản đó viết cho hình dạng CŨ của một lượt đăng
    ký: chèn đúng một hàng `users`.

    Hình dạng đó đổi ở v4 — đăng ký không lời mời giờ tạo hẳn một tenant kèm
    bản sao danh mục từ vựng. Cả ba bản cũ lập tức để lại tenant mồ côi, và sổ
    dấu vết bắt chúng ở ba lượt chạy suite liên tiếp: 29, rồi 27, rồi 5.

    Vá từng bản một là mời bản thứ năm quên tiếp. Gom về đây để lần sau hình
    dạng của "đăng ký" đổi thì chỉ có một chỗ phải sửa.

    Chỉ xoá tenant có cờ `is_self_serve`: một tenant do lời mời cấp thuộc về
    fixture khác, và xoá nó là dọn sang phần của người khác.
    """
    from app.storage import metadata_db as db
    from app.tenancy import DEFAULT_TENANT_ID
    from app.tenant_context import system_scope

    with system_scope("test cleanup: find the account and the tenant it created"):
        rows = db._fetch_all(
            "SELECT id, tenant_id FROM users WHERE username = %s", (username,)
        )
    if not rows:
        return

    owned = set()
    for row in rows:
        tenant_id = row.get("tenant_id")
        if not tenant_id or tenant_id == DEFAULT_TENANT_ID:
            continue
        with system_scope("test cleanup: is this tenant ours to remove"):
            try:
                mine = db._fetch_all(
                    "SELECT is_self_serve FROM tenants WHERE tenant_id = %s",
                    (tenant_id,),
                )
            except Exception:
                mine = []
        if mine and mine[0].get("is_self_serve"):
            owned.add(tenant_id)

    with system_scope("test cleanup: detach and remove the account"):
        for row in rows:
            for table in _USER_CHILD_TABLES:
                try:
                    db._execute(f"DELETE FROM {table} WHERE user_id = %s", (row["id"],))
                except Exception:
                    pass
            for sql in (
                "UPDATE tenant_invitations SET accepted_by = NULL WHERE accepted_by = %s",
                "UPDATE tenants SET owner_user_id = NULL WHERE owner_user_id = %s",
            ):
                try:
                    db._execute(sql, (row["id"],))
                except Exception:
                    pass
            try:
                db._execute("DELETE FROM users WHERE id = %s", (row["id"],))
            except Exception:
                pass

    for tenant_id in owned:
        try:
            purge_tenant(tenant_id)
        except Exception:
            pass


# Standalone suites — executed by test_research_suites.py, not collected here.
STANDALONE_SUITES = (
    "test_augmentation_geometry.py",
    "test_frozen_artifacts.py",
    "test_manifest.py",
    "test_migration_vocab.py",
    "test_phase35_scripts.py",
    "test_profile_training_prep.py",
    "test_quality.py",
    "test_signer_disjoint_split.py",
    "test_split_safety.py",
    "test_vocabulary_v2.py",
)

collect_ignore = list(STANDALONE_SUITES)


@pytest.fixture
def free_legal_kinds():
    """Các loại văn bản pháp lý hiện KHÔNG có bản nháp nào đang mở.

    Vì sao cần chọn động thay vì viết cứng `"data_contribution"`: bộ test chạy
    trên BẢN SAO của cơ sở dữ liệu thật (xem docs/TESTING.md §2.4), và ở đó
    `legal_document_drafts` có thể đang giữ một bản nháp thật do người soạn mở
    dở. Đúng tình huống 2026-08-09: sản xuất có một bản nháp `data_contribution`
    đang mở, và ba test viết cứng đúng loại đó cùng đỏ với thông báo
    `draft_already_open` — đọc lên như một hồi quy ở cơ chế khoá bản nháp, thật
    ra là dữ liệu thật của người dùng.

    Không xoá và không sửa bản nháp đang mở đó: nó là công việc dở dang của một
    con người, và một fixture không được phép quyết định thay họ. Chọn một chỗ
    trống khác thì rẻ hơn và không mất gì.
    """
    from app import legal
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("test setup: tim loai van ban con trong"):
        rows = _fetch_all(
            "SELECT DISTINCT kind FROM legal_document_drafts WHERE status = ANY(%s)",
            (list(legal.OPEN_DRAFT_STATUSES),))
    taken = {r["kind"] for r in rows}
    free = [k for k in legal.KINDS if k not in taken]
    if not free:
        pytest.skip(f"moi loai van ban deu dang co ban nhap mo: {sorted(taken)}")
    return free
