"""Tests for the Phase 2 label-detail viewer API + preview renderer.

Covers the risk scenarios from Extra_docs/PHASE2_PLAN_3D_VIEWER.md:
    - session grouping (incl. legacy rows without session_id)
    - original-sample selection (augment_id 0 wins)
    - frames endpoint payload shape + 7-day private cache header
    - 404s: unknown class, unknown session, missing npz
    - auth required on every endpoint
    - renderer: all-zero (missing hand) frames don't crash, output exists
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user

client = TestClient(app)

FAKE_USER = {"id": "u1", "username": "tester", "is_admin": True}


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


class FakeMeta:
    class_uid = "cls123"
    slug = "xin-chao"
    label_original = "Xin chào"
    language = "vn"
    dialect = "mienTay"

    def __init__(self, root):
        self._root = root

    def hierarchy_path(self):
        return self._root


def _sample_row(sample_uid, session_id, augment_id, file_path="", **extra):
    row = {
        "sample_uid": sample_uid,
        "class_uid": "cls123",
        "session_id": session_id,
        "augment_id": str(augment_id),
        "user_id": "nguoi-dong-gop-a",
        "username": "Người A",
        "seq_len": "60",
        "fps_processed": "15",
        "source_type": "camera",
        "created_at": "2026-07-01T00:00:00Z",
        "file_path": file_path,
        "deleted_at": "",
        "status": "",
    }
    row.update(extra)
    return row


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    """A fake class with 2 sessions: one real npz session + one legacy row."""
    import app.preview_render as pr

    class_dir = tmp_path / "features" / "vn" / "mienTay" / "class_xin-chao_cls123"
    class_dir.mkdir(parents=True)
    meta = FakeMeta(class_dir)

    # Real npz: 60 frames, right hand only (left hand missing = zeros).
    seq = np.zeros((60, 126), dtype=np.float32)
    seq[:, 63:126] = np.random.default_rng(7).uniform(0.2, 0.8, size=(60, 63))
    npz_path = class_dir / "sample_abc.npz"
    np.savez_compressed(npz_path, sequence=seq, meta={})

    rows = [
        _sample_row("abc", "sess-1", 0, file_path=str(npz_path)),
        _sample_row("abc-aug", "sess-1", 1, file_path=str(npz_path)),
        _sample_row("legacy", "", 0, file_path=str(class_dir / "missing.npz")),
        _sample_row("ghost", "sess-del", 0, deleted_at="2026-07-02T00:00:00Z"),
    ]

    # Các seam nhận `tenant_id` từ 16/08/2026. Chúng KHẲNG ĐỊNH phạm vi thay vì
    # nuốt nó bằng `**k`: một seam dễ dãi sẽ xanh cả khi router quên truyền
    # phạm vi, và bộ test khi đó chứng minh điều ngược với điều nó tuyên bố.
    def _meta(uid, *, tenant_id):
        assert tenant_id, "find_class_meta goi khong co pham vi tenant"
        return meta if uid == "cls123" else None

    def _mau(tenant_id):
        assert tenant_id, "list_samples goi khong co pham vi tenant"
        return rows

    monkeypatch.setattr(pr, "find_class_meta", _meta)
    monkeypatch.setattr("app.dataset_samples.list_samples", _mau)
    # The router imported these symbols by name — patch its bindings too.
    import app.routers.label_sessions as ls

    monkeypatch.setattr(ls, "find_class_meta", _meta)
    return {"meta": meta, "seq": seq, "class_dir": class_dir}


# ---------------------------------------------------------------------------
# Sessions list
# ---------------------------------------------------------------------------

def test_sessions_grouping(dataset):
    res = client.get("/classes/cls123/sessions")
    assert res.status_code == 200
    body = res.json()
    assert body["label_original"] == "Xin chào"
    # sess-1 (2 samples) + legacy single row; the soft-deleted row is excluded.
    assert body["count"] == 2
    by_id = {s["session_id"]: s for s in body["sessions"]}
    assert by_id["sess-1"]["sample_count"] == 2
    assert by_id["sess-1"]["original_sample_uid"] == "abc"  # augment_id 0 wins
    assert "single-legacy" in by_id


def test_sessions_unknown_class_404(dataset):
    assert client.get("/classes/nope/sessions").status_code == 404


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def test_frames_payload_and_cache_header(dataset):
    res = client.get("/classes/cls123/sessions/sess-1/frames")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "private, max-age=604800"
    body = res.json()
    assert body["frames"] == 60
    assert body["dim"] == 126
    assert body["fps"] == 15.0
    assert body["sample_uid"] == "abc"
    assert len(body["sequence"]) == 60
    assert len(body["sequence"][0]) == 126
    # Left hand was never detected → stored zeros must survive the round trip.
    assert all(v == 0 for v in body["sequence"][0][:63])


def test_frames_unknown_session_404(dataset):
    assert client.get("/classes/cls123/sessions/nope/frames").status_code == 404


def test_frames_missing_npz_404(dataset):
    res = client.get("/classes/cls123/sessions/single-legacy/frames")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Preview (Tier 3)
# ---------------------------------------------------------------------------

def test_preview_video_before_render_404(dataset):
    res = client.get("/classes/cls123/sessions/sess-1/preview.mp4")
    assert res.status_code == 404


def test_preview_status_renders_inline_without_broker(dataset):
    # The endpoint falls back to inline rendering when the async dispatch fails
    # (no broker). Force that path deterministically by making .delay() raise, so
    # the test passes whether or not a redis broker is reachable in this env.
    pytest.importorskip("cv2")
    with patch(
        "app.preview_tasks.render_session_preview_task.delay",
        side_effect=RuntimeError("no broker (forced for test)"),
    ):
        res = client.get("/classes/cls123/sessions/sess-1/preview")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"

    video = client.get("/classes/cls123/sessions/sess-1/preview.mp4")
    assert video.status_code == 200
    assert video.headers["content-type"] == "video/mp4"
    assert video.headers["cache-control"] == "private, max-age=604800"
    assert len(video.content) > 0

    # Session list now reports the cached preview.
    sessions = client.get("/classes/cls123/sessions").json()
    sess1 = next(s for s in sessions["sessions"] if s["session_id"] == "sess-1")
    assert sess1["has_preview"] is True


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_endpoints_require_auth(dataset):
    app.dependency_overrides.pop(get_current_user, None)
    for url in (
        "/classes/cls123/sessions",
        "/classes/cls123/sessions/sess-1/frames",
        "/classes/cls123/sessions/sess-1/preview",
        "/classes/cls123/sessions/sess-1/preview.mp4",
    ):
        assert client.get(url).status_code == 401, url


# ---------------------------------------------------------------------------
# Renderer unit tests
# ---------------------------------------------------------------------------

def test_render_all_zero_sequence_does_not_crash(tmp_path):
    pytest.importorskip("cv2")
    from app.preview_render import render_sequence_to_mp4

    out = tmp_path / "empty.mp4"
    render_sequence_to_mp4(np.zeros((10, 126), dtype=np.float32), out, fps=15)
    assert out.exists() and out.stat().st_size > 0


def test_render_rejects_bad_shape(tmp_path):
    from app.preview_render import render_sequence_to_mp4

    with pytest.raises(ValueError):
        render_sequence_to_mp4(np.zeros((10, 5), dtype=np.float32), tmp_path / "x.mp4")


def test_safe_session_part_sanitizes_paths():
    from app.preview_render import safe_session_part

    assert "/" not in safe_session_part("../../etc/passwd")
    assert "\\" not in safe_session_part("..\\..\\win")
    assert safe_session_part("") == "session"
    assert safe_session_part("sess-01.A_b") == "sess-01.A_b"


# ===========================================================================
# EDGE CASES — Boundary Value Analysis + Equivalence Partitioning
# Mỗi test theo mẫu AAA (Arrange–Act–Assert), tên theo Given-When-Then.
# ===========================================================================

class TestFpsFallbackChain:
    """Equivalence partitions của fps: hợp lệ / rỗng / rác / âm / zero."""

    def test_given_valid_fps_processed_then_it_wins(self):
        from app.preview_render import sample_fps

        assert sample_fps({"fps_processed": "30", "fps_original": "60"}) == 30.0

    def test_given_empty_fps_processed_when_original_valid_then_fallback(self):
        from app.preview_render import sample_fps

        assert sample_fps({"fps_processed": "", "fps_original": "24"}) == 24.0

    def test_given_all_invalid_then_default_15(self):
        from app.preview_render import sample_fps

        for row in (
            {"fps_processed": "", "fps_original": ""},
            {"fps_processed": "abc", "fps_original": "xyz"},
            {"fps_processed": "0", "fps_original": "-5"},
            {},
        ):
            assert sample_fps(row) == 15.0, row


class TestOriginalSampleSelection:
    """Chọn mẫu gốc của session: augment_id nhỏ nhất; rác coi như 0."""

    def test_given_only_augmented_samples_then_lowest_augment_wins(self):
        from app.preview_render import pick_original_sample

        rows = [{"sample_uid": "a2", "augment_id": "2"}, {"sample_uid": "a1", "augment_id": "1"}]
        assert pick_original_sample(rows)["sample_uid"] == "a1"

    def test_given_garbage_augment_id_then_treated_as_zero_no_crash(self):
        from app.preview_render import pick_original_sample

        rows = [{"sample_uid": "g", "augment_id": "abc"}, {"sample_uid": "b", "augment_id": "3"}]
        assert pick_original_sample(rows)["sample_uid"] == "g"

    def test_given_empty_rows_then_none(self):
        from app.preview_render import pick_original_sample

        assert pick_original_sample([]) is None


class TestSessionListEdgeCases:
    def test_given_status_deleted_row_then_excluded_even_without_deleted_at(
        self, dataset, monkeypatch
    ):
        # Arrange: thêm một row bị soft-delete qua cột status (không có deleted_at)
        import app.preview_render as pr

        extra = _sample_row("stat-del", "sess-stat", 0, status="deleted")
        rows = list(pr.list_session_rows("cls123", tenant_id="default").values())
        monkeypatch.setattr(
            "app.dataset_samples.list_samples",
            lambda tenant_id: [r for group in rows for r in group] + [extra],
        )
        # Act
        res = client.get("/classes/cls123/sessions")
        # Assert
        ids = [s["session_id"] for s in res.json()["sessions"]]
        assert "sess-stat" not in ids

    def test_sessions_sorted_newest_first(self, dataset):
        res = client.get("/classes/cls123/sessions")
        dates = [s["created_at"] for s in res.json()["sessions"]]
        assert dates == sorted(dates, reverse=True)

    def test_given_traversal_session_id_then_404_and_no_escape(self, dataset, tmp_path):
        # Path traversal phải bị chặn ở tầng lookup (session không tồn tại)
        res = client.get("/classes/cls123/sessions/..%2F..%2Fetc%2Fpasswd/frames")
        assert res.status_code == 404


class TestCorruptDataHandling:
    def test_given_corrupt_npz_then_500_with_clear_message(self, dataset, monkeypatch):
        # Arrange: ghi đè file npz bằng rác
        bad = dataset["class_dir"] / "sample_abc.npz"
        bad.write_bytes(b"this is not a zip file")
        # Act
        res = client.get("/classes/cls123/sessions/sess-1/frames")
        # Assert
        assert res.status_code == 500
        assert "hỏng" in res.json()["detail"]

    def test_given_1d_sequence_then_500_bad_format(self, dataset):
        # Arrange: npz đúng zip nhưng sequence sai chiều
        np.savez_compressed(
            dataset["class_dir"] / "sample_abc.npz",
            sequence=np.zeros(126, dtype=np.float32),
            meta={},
        )
        res = client.get("/classes/cls123/sessions/sess-1/frames")
        assert res.status_code == 500
        assert "định dạng" in res.json()["detail"]


class TestRendererBoundaries:
    def test_given_single_visible_point_then_degenerate_bbox_does_not_crash(self, tmp_path):
        # Boundary: bbox span = 0 (chia scale phải có epsilon guard)
        pytest.importorskip("cv2")
        from app.preview_render import render_sequence_to_mp4

        seq = np.zeros((5, 126), dtype=np.float32)
        seq[:, 63:66] = 0.5  # đúng 1 landmark, đứng yên
        out = tmp_path / "point.mp4"
        render_sequence_to_mp4(seq, out, fps=15)
        assert out.exists() and out.stat().st_size > 0

    def test_given_existing_preview_when_rerendered_then_atomic_overwrite(self, tmp_path):
        # Idempotency: render 2 lần cùng 1 output không hỏng file
        pytest.importorskip("cv2")
        from app.preview_render import render_sequence_to_mp4

        seq = np.random.default_rng(1).uniform(0.1, 0.9, (10, 126)).astype(np.float32)
        out = tmp_path / "twice.mp4"
        render_sequence_to_mp4(seq, out, fps=15)
        first = out.stat().st_size
        render_sequence_to_mp4(seq, out, fps=15)
        assert out.exists() and out.stat().st_size == first

    def test_given_one_frame_sequence_then_video_still_written(self, tmp_path):
        # Boundary: T = 1 (nhỏ nhất có nghĩa)
        pytest.importorskip("cv2")
        from app.preview_render import render_sequence_to_mp4

        seq = np.random.default_rng(2).uniform(0.1, 0.9, (1, 126)).astype(np.float32)
        out = tmp_path / "one.mp4"
        render_sequence_to_mp4(seq, out, fps=15)
        assert out.exists() and out.stat().st_size > 0

    def test_given_wider_feature_dim_then_first_126_used(self, tmp_path):
        # Forward-compat: dữ liệu Holistic tương lai (D>126) không làm vỡ viewer
        pytest.importorskip("cv2")
        from app.preview_render import render_sequence_to_mp4

        seq = np.random.default_rng(3).uniform(0.1, 0.9, (5, 225)).astype(np.float32)
        out = tmp_path / "wide.mp4"
        render_sequence_to_mp4(seq, out, fps=15)
        assert out.exists()
