"""B1–B4 — attack surface, not incidents.

Nothing here claims the system was attacked. Each item is a way in that was
open: a checkpoint that could execute code, endpoints with no ceiling on how
often they can be called, and a traceback served to anyone who could guess a job
id.
"""

from __future__ import annotations

import pytest

from app.checkpoint_io import UntrustedCheckpointError, resolve_checkpoint_path


# ---------------------------------------------------------------------------
# B1 — torch.load
# ---------------------------------------------------------------------------


class TestCheckpointPathContainment:
    @pytest.fixture
    def roots(self, tmp_path):
        allowed = tmp_path / "checkpoints"
        allowed.mkdir()
        return [allowed]

    def test_accepts_a_file_inside_an_allowed_root(self, roots):
        target = roots[0] / "model.pt"
        target.write_bytes(b"x")
        assert resolve_checkpoint_path(target, roots) == target.resolve()

    def test_accepts_a_path_that_does_not_exist_yet(self, roots):
        """`strict=False` on purpose: the caller's "file not found" is a clearer
        error than a resolution failure, and containment is still meaningful."""
        assert resolve_checkpoint_path(roots[0] / "later.pt", roots)

    def test_rejects_a_sibling_directory(self, roots, tmp_path):
        outside = tmp_path / "elsewhere" / "model.pt"
        outside.parent.mkdir()
        with pytest.raises(UntrustedCheckpointError):
            resolve_checkpoint_path(outside, roots)

    def test_rejects_traversal_that_a_prefix_check_would_accept(self, roots):
        """The reason the check compares RESOLVED paths.

        `"<allowed>/../../etc/passwd"` starts with the allowed prefix as a
        string, so `str(p).startswith(str(root))` — the obvious implementation —
        accepts it. Resolving first is what closes that.
        """
        sneaky = str(roots[0] / ".." / ".." / "etc" / "passwd")
        assert sneaky.startswith(str(roots[0].parent))  # premise of the test
        with pytest.raises(UntrustedCheckpointError):
            resolve_checkpoint_path(sneaky, roots)

    def test_rejects_a_symlink_pointing_out_of_the_root(self, roots, tmp_path):
        """A writable checkpoint directory is the realistic supply-chain vector
        (MITRE ATLAS AML.T0010): the attacker never needs to pass a bad path,
        only to leave a link in a directory the service already trusts."""
        secret = tmp_path / "outside.pt"
        secret.write_bytes(b"x")
        link = roots[0] / "innocent.pt"
        try:
            link.symlink_to(secret)
        except (OSError, NotImplementedError):  # pragma: no cover - Windows/CI
            pytest.skip("symlinks not permitted in this environment")
        with pytest.raises(UntrustedCheckpointError):
            resolve_checkpoint_path(link, roots)

    def test_error_names_the_resolved_path_and_the_allowed_roots(self, roots, tmp_path):
        with pytest.raises(UntrustedCheckpointError) as exc:
            resolve_checkpoint_path(tmp_path / "nope.pt", roots)
        assert "outside the allowed roots" in str(exc.value)
        assert str(roots[0].resolve()) in str(exc.value)


class TestNoUnsafeLoadsRemain:
    def test_only_the_loader_may_pass_weights_only_false(self):
        """`weights_only=False` unpickles, and unpickling executes code carried
        in the file. Exactly one place in the backend is allowed to do it: the
        audited fallback in `checkpoint_io`, which runs only after the path has
        been contained and only when weights-only genuinely cannot represent the
        content.

        Kiểm bằng AST chứ không grep chuỗi. Bản grep đã cho một BÁO ĐỘNG GIẢ:
        nó bắt phải đoạn văn xuôi trong docstring của `training_tasks.py` đang
        giải thích chính rủi ro này, vì tìm-chuỗi không phân biệt được mã với
        chú thích. Báo động giả thì người ta tắt đi, và một cổng bảo mật bị tắt
        còn tệ hơn không có.

        AST cũng chặt hơn theo hướng ngược lại: nó bắt cả
        `weights_only = False` viết có dấu cách, thứ mà grep bỏ lọt hoàn toàn.
        """
        import ast
        from pathlib import Path

        backend_app = Path(__file__).resolve().parents[1] / "app"
        offenders = []
        for path in backend_app.rglob("*.py"):
            if path.name == "checkpoint_io.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if (kw.arg == "weights_only"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is False):
                        offenders.append(
                            f"{path.relative_to(backend_app)}:{node.lineno}")

        assert offenders == [], f"unsafe torch.load outside checkpoint_io: {offenders}"


# ---------------------------------------------------------------------------
# B2/B3 — rate limits
# ---------------------------------------------------------------------------


class TestRateLimitKeys:
    def test_user_and_ip_use_separate_key_spaces(self, monkeypatch):
        """Signing in must not inherit an anonymous caller's spent budget, and
        signing out must not reset it."""
        from app import rate_limit

        keys = []
        monkeypatch.setattr(
            rate_limit, "_incr_with_window", lambda key, window, sliding=False: (keys.append(key), (1, window))[1]
        )
        monkeypatch.setattr(rate_limit, "client_ip", lambda request: "10.0.0.1")

        rate_limit.enforce_actor_limit(None, "upload", 10, 60, user_id="u-1")
        rate_limit.enforce_actor_limit(None, "upload", 10, 60, user_id=None)

        assert ":user:" in keys[0] and ":ip:" in keys[1]
        assert keys[0] != keys[1]

    def test_user_id_is_hashed_into_the_key(self, monkeypatch):
        """Redis keys end up in `KEYS`/`MONITOR` output and in memory dumps; a
        raw user id there is a needless identifier leak."""
        from app import rate_limit

        keys = []
        monkeypatch.setattr(
            rate_limit, "_incr_with_window", lambda key, window, sliding=False: (keys.append(key), (1, window))[1]
        )
        rate_limit.enforce_actor_limit(None, "upload", 10, 60, user_id="secret-user-id")
        assert "secret-user-id" not in keys[0]

    def test_over_limit_raises_429_with_retry_after(self, monkeypatch):
        from fastapi import HTTPException

        from app import rate_limit

        monkeypatch.setattr(
            rate_limit, "_incr_with_window", lambda key, window, sliding=False: (99, 42)
        )
        with pytest.raises(HTTPException) as exc:
            rate_limit.enforce_actor_limit(None, "upload", 10, 60, user_id="u-1")
        assert exc.value.status_code == 429
        assert exc.value.headers.get("Retry-After") == "42"

    def test_under_limit_does_not_raise(self, monkeypatch):
        from app import rate_limit

        monkeypatch.setattr(
            rate_limit, "_incr_with_window", lambda key, window, sliding=False: (1, 60)
        )
        rate_limit.enforce_actor_limit(None, "upload", 10, 60, user_id="u-1")

    def test_redis_outage_fails_OPEN(self, monkeypatch):
        """Pinned deliberately, because it is a trade-off and not an oversight.

        `_incr_with_window` returns (0, 0) when Redis is unreachable, so a
        limiter cannot decide it has been exceeded and the request proceeds. The
        opposite choice would mean a Redis blip stops a collector mid-session at
        a special-education facility — losing recordings that are expensive to
        arrange — in exchange for briefly capping abuse on an authenticated,
        admin-provisioned endpoint. Availability wins here.

        Note this differs from the tenant boundary, which fails CLOSED: that one
        protects other people's data, this one protects capacity.
        """
        from app import rate_limit

        monkeypatch.setattr(rate_limit, "_client", lambda: None)
        rate_limit.enforce_actor_limit(None, "upload", 1, 60, user_id="u-1")
        rate_limit.enforce_actor_limit(None, "upload", 1, 60, user_id="u-1")


class TestLimiterNeverAnswersForTheAuthenticator:
    """A rate limit must not change what an unauthenticated caller is told.

    Found by the suite, not by review: attaching the limiter to `/training/*`
    and `/upload/*` made anonymous requests return **429 instead of 401** once
    the shared IP bucket ran out. Two things wrong with that, and the second is
    the serious one:

      * The limiter had started answering "are you allowed in?", which is the
        authenticator's question.
      * Every anonymous caller shares ONE bucket, keyed by IP. So a caller who
        is going to be refused anyway could exhaust the allowance of legitimate
        users behind the same NAT — a denial of service introduced by the very
        thing meant to prevent one. At a special-education facility the whole
        room is one NAT.
    """

    def _dependency(self, path, method):
        from app.main import app

        route = next(
            r for r in app.routes
            if getattr(r, "path", None) == path and method in getattr(r, "methods", set())
        )
        return next(
            d for d in route.dependant.dependencies
            if d.call is not None
            and "enforce_actor_limit" in getattr(
                d.call, "__code__", type("x", (), {"co_names": ()})
            ).co_names
        )

    @pytest.mark.parametrize("path,method", [
        ("/upload/camera", "POST"),
        ("/training/start", "POST"),
        ("/classes/register", "POST"),
    ])
    def test_authenticated_only_endpoints_do_not_count_anonymous_calls(
        self, path, method, monkeypatch
    ):
        from app import rate_limit

        counted = []
        monkeypatch.setattr(
            rate_limit,
            "_incr_with_window",
            lambda key, window, sliding=False: (counted.append(key), (1, window))[1],
        )
        self._dependency(path, method).call(request=None, user=None)
        assert counted == [], (
            f"{method} {path} counted an anonymous call; it will answer 429 where "
            f"the endpoint's own auth dependency should answer 401"
        )

    def test_the_publicly_reachable_endpoint_still_counts_anonymous_calls(
        self, monkeypatch
    ):
        """`/realtime/predict` serves anonymous callers for real, so skipping
        them would leave it with no ceiling at all — which was B2."""
        from app import rate_limit

        counted = []
        monkeypatch.setattr(
            rate_limit,
            "_incr_with_window",
            lambda key, window, sliding=False: (counted.append(key), (1, window))[1],
        )
        monkeypatch.setattr(rate_limit, "client_ip", lambda request: "10.0.0.9")
        self._dependency("/realtime/predict", "POST").call(request=None, user=None)
        assert len(counted) == 1 and ":ip:" in counted[0]

    def test_authenticated_calls_are_always_counted(self, monkeypatch):
        from app import rate_limit

        counted = []
        monkeypatch.setattr(
            rate_limit,
            "_incr_with_window",
            lambda key, window, sliding=False: (counted.append(key), (1, window))[1],
        )
        self._dependency("/training/start", "POST").call(
            request=None, user={"id": "u-1"}
        )
        assert len(counted) == 1 and ":user:" in counted[0]


class TestWritePathsAreCovered:
    """The gap this closes: before B3, `grep -rl rate_limit backend/app/routers/`
    matched exactly one file — auth.py. `upload.py` is the most expensive path in
    the system and had no ceiling at all."""

    def _routes(self):
        from app.main import app

        return app.routes

    @pytest.mark.parametrize("path,method", [
        ("/upload/video", "POST"),
        ("/upload/video/process", "POST"),
        ("/upload/camera", "POST"),
        ("/realtime/predict", "POST"),
        ("/classes/register", "POST"),
        ("/training/start", "POST"),
    ])
    def test_endpoint_has_a_limiter(self, path, method):
        from app.rate_limit import enforce_actor_limit  # noqa: F401  (documents intent)

        matches = [
            r for r in self._routes()
            if getattr(r, "path", None) == path and method in getattr(r, "methods", set())
        ]
        assert matches, f"{method} {path} is not mounted"

        # A limiter shows up as a dependency whose callable closes over
        # enforce_actor_limit. Checked by walking the dependant tree rather than
        # by name, so renaming the factory cannot silently drop the assertion.
        route = matches[0]
        found = any(
            "enforce_actor_limit" in getattr(d.call, "__code__", type("x", (), {"co_names": ()})).co_names
            for d in route.dependant.dependencies
            if d.call is not None
        )
        assert found, f"{method} {path} has no rate limit dependency"


# ---------------------------------------------------------------------------
# B4 — mounts
# ---------------------------------------------------------------------------


class TestRouterMounts:
    def test_job_status_requires_authentication(self):
        """The payload carries `traceback` and the stringified exception, which
        names filesystem paths, module layout and library versions."""
        from app.main import app

        route = next(
            r for r in app.routes
            if getattr(r, "path", None) == "/jobs/{job_id}" and "GET" in getattr(r, "methods", set())
        )
        names = [
            getattr(d.call, "__name__", "") for d in route.dependant.dependencies if d.call
        ]
        assert "get_current_user" in names

    def test_dead_routers_are_not_imported(self):
        """`experiments` and `dataset_exporter` were imported and never mounted:
        681 lines that read as live endpoints, reachable by no URL, executed at
        import time on every boot."""
        import app.main as main

        for dead in ("experiments", "dataset_exporter"):
            assert not hasattr(main, dead), (
                f"{dead} is imported into main but never mounted; either "
                f"include_router it or drop the import"
            )

    def test_no_route_is_mounted_from_a_dead_router(self):
        from app.main import app

        paths = {getattr(r, "path", "") for r in app.routes}
        assert not any(p.startswith("/experiments") for p in paths)
        assert not any(p.startswith("/dataset-export") for p in paths)
