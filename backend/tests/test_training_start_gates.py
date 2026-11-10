"""Các chốt của `POST /training/start` mà đợt tái cấu trúc đã đánh rơi (10/11/2026).

Bản chạy trên máy web trước đó có đủ; bản tách service bỏ mất mà CI vẫn xanh, vì
các test cũ chỉ gọi hàm phụ (`split_classes_below_floor`, ...) chứ không gọi chốt.
Tệp này gọi chính chốt, không cần DB hay dữ liệu thật.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import processed.train_utils.split_artifact as sa  # noqa: E402
from app.config import settings  # noqa: E402
from app.modules.training import submission_service  # noqa: E402
from app.modules.training.schemas import SplitProvenance, TrainingConfig  # noqa: E402
from app.routers import training as tr  # noqa: E402

TENANT = "default"
ME = {"id": "u-me", "username": "me"}


def _artifact(meta):
    root = Path("/khong-ton-tai/operational/a")
    return sa.SplitArtifact(split_id="a", purpose="operational", train_csv=root / "train.csv",
                            val_csv=root / "val.csv", test_csv=root / "test.csv",
                            metadata=meta, tenant_id=TENANT, owner_state="owned")


@pytest.fixture
def gates(monkeypatch):
    """Thay mọi thứ ngoài tiến trình; ghi lại phương ngữ được soi quyền."""
    soi_quyen = []
    monkeypatch.setattr(tr, "assert_can_use_dialect", lambda d, _u, _t: soi_quyen.append(d))
    monkeypatch.setattr(settings, "min_samples_per_class_for_training", 0)
    return soi_quyen


def _check(config):
    asyncio.run(tr._kiem_truoc_khi_nop(config, ME, TENANT))


def test_another_members_personal_artifact_is_not_found(monkeypatch, gates):
    monkeypatch.setattr(sa, "resolve_split_artifact",
                        lambda **_: _artifact({"auth_user_id": "u-other", "scope": {"dialects": ["hoa-de"]}}))
    with pytest.raises(HTTPException) as exc:
        _check(TrainingConfig(operational_split_id="a"))
    assert exc.value.status_code == 400 and "Không tìm thấy" in exc.value.detail


def test_empty_dialects_take_the_artifact_scope_and_are_permission_checked(monkeypatch, gates):
    monkeypatch.setattr(sa, "resolve_split_artifact",
                        lambda **_: _artifact({"auth_user_id": "u-me", "scope": {"dialects": ["hoa-de"]}}))
    config = TrainingConfig(operational_split_id="a", dialects=[])
    _check(config)
    assert config.dialects == ["hoa-de"]
    assert gates == ["hoa-de"]


def test_dialects_outside_the_artifact_are_refused(monkeypatch, gates):
    monkeypatch.setattr(sa, "resolve_split_artifact",
                        lambda **_: _artifact({"scope": {"dialects": ["hoa-de"]}}))
    with pytest.raises(HTTPException) as exc:
        _check(TrainingConfig(operational_split_id="a", dialects=["hoa-de", "bang-chu-cai"]))
    assert exc.value.status_code == 400 and "chỉ chứa phương ngữ" in exc.value.detail


def test_sample_floor_is_enforced(monkeypatch, gates):
    monkeypatch.setattr(settings, "min_samples_per_class_for_training", 25)
    monkeypatch.setattr(tr, "_eligible_class_counts", lambda dialects, n: {"hoa-de": 1})
    with pytest.raises(HTTPException) as exc:
        _check(TrainingConfig(dialects=["hoa-de"]))
    assert exc.value.status_code == 400 and "Không đủ lớp" in exc.value.detail


def test_split_below_floor_is_refused(monkeypatch, gates):
    monkeypatch.setattr(settings, "min_samples_per_class_for_training", 25)
    monkeypatch.setattr(tr, "_eligible_class_counts", lambda dialects, n: {"hoa-de": 9})
    monkeypatch.setattr(tr, "_split_classes_below_floor", lambda d, n, thu_muc=None: [("Xin chào", "uid", 3)])
    monkeypatch.setattr(tr, "_split_snapshot", lambda thu_muc=None: {"min_samples_per_class": 10})
    with pytest.raises(HTTPException) as exc:
        _check(TrainingConfig(dialects=["hoa-de"]))
    assert "chưa đủ 25 mẫu" in exc.value.detail


def test_dispatch_survives_one_broker_hiccup(monkeypatch):
    from app.modules.training import tasks

    calls = []

    class _Task:
        @staticmethod
        def apply_async(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise ConnectionError("redis blip")

    async def _no_sleep(_s):
        return None

    async def _persist(job, auth_user_id=None):
        return None

    monkeypatch.setattr(tasks, "run_training_job", _Task)
    monkeypatch.setattr(submission_service.asyncio, "sleep", _no_sleep)
    job = asyncio.run(submission_service.submit_training_job(
        TrainingConfig(), auth_user_id="u-me", username="me", tenant_id=TENANT, jobs={},
        research_splits=lambda: [], trainable_dialects=lambda: {},
        resolve_provenance=lambda **_: SplitProvenance(counts={"train": 5, "test": 2}),
        persist_job=_persist,
    ))
    assert len(calls) == 2
    assert job.status == "queued"
