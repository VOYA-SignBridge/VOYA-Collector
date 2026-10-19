"""Build research provenance reports from trained-model checkpoints."""

from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_CRITERION_LABELS: Dict[str, str] = {
    "C1_run_purpose": "Chạy nghiên cứu (không phải smoke test)",
    "C2_augmentation_contract": "Hợp đồng augmentation đã sửa lỗi mirror",
    "C3_contract_complete": "Checkpoint ghi đủ trường bắt buộc",
    "C4_versions_present": "Có phiên bản dataset và split",
    "C5_manifest_checksum": "Checksum manifest KHỚP file dữ liệu",
    "C6_split_metadata": "Split có metadata mô tả cách chia",
    "C7_split_valid_for_research": "Split hợp lệ cho nghiên cứu (không rò rỉ người ký)",
    "C8_profile_matches_labels": "Nhãn khớp profile đã khai báo",
    "C9_no_cross_profile": "Không lẫn nhãn của profile khác",
    "C10_runtime_env": "Ghi đủ môi trường chạy",
    "C11_git_commit": "Ghim được commit sinh ra model",
    "C12_test_set_non_empty": "Tập đánh giá không rỗng",
    "C13_best_val_restored": "Metrics lấy từ checkpoint val tốt nhất",
    "C14_run_completed": "Lần chạy kết thúc bình thường",
}


def _determinism_summary(determinism: Any) -> str:
    """Collapse the checkpoint determinism block into UI-readable text."""
    if not isinstance(determinism, dict):
        return str(determinism or "")

    full = bool(determinism.get("cudnn_deterministic")) and bool(
        determinism.get("deterministic_algorithms")
    )
    warnings = determinism.get("warnings") or []
    text = "đầy đủ" if full else "một phần"
    if warnings:
        text += f" ({len(warnings)} cảnh báo)"
    return text


def _load_research_validity(workspace_root: Optional[Path] = None):
    """Load the shared research criteria implementation from repository scripts."""
    roots = (
        Path("/workspace"),
        workspace_root or Path("/workspace"),
        Path(__file__).resolve().parents[4],
    )
    for base in roots:
        candidate = base / "scripts" / "research_validity.py"
        if not candidate.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location("research_validity", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.warning("[PROVENANCE] không nạp được research_validity: %s", exc)
            return None
    return None


def _provenance_checks(
    ckpt: Dict[str, Any],
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Evaluate all C1-C14 criteria with the canonical audit implementation."""
    rv = _load_research_validity(workspace_root)
    if rv is None:
        return [{
            "id": "—",
            "label": "Không chạy được bộ kiểm tính hợp lệ",
            "ok": False,
            "detail": (
                "không nạp được scripts/research_validity.py — "
                "không thể xác nhận lần chạy này hợp lệ cho nghiên cứu"
            ),
        }]

    try:
        verdict = rv.evaluate_checkpoint(ckpt)
    except Exception as exc:
        logger.warning("[PROVENANCE] evaluate_checkpoint lỗi: %s", exc)
        return [{
            "id": "—",
            "label": "Bộ kiểm tính hợp lệ gặp lỗi",
            "ok": False,
            "detail": str(exc),
        }]

    detail_by_code: Dict[str, str] = {}
    for reason in verdict.reasons:
        match = re.search(r"\((C\d+)\)\s*$", str(reason))
        if match:
            detail_by_code.setdefault(match.group(1), str(reason))

    checks: List[Dict[str, Any]] = []
    for key, ok in verdict.criteria.items():
        code = key.split("_", 1)[0]
        checks.append({
            "id": code,
            "label": _CRITERION_LABELS.get(key, key),
            "ok": bool(ok),
            "detail": detail_by_code.get(code, "đạt" if ok else "không đạt"),
        })
    checks.sort(key=lambda item: int(item["id"][1:]) if item["id"][1:].isdigit() else 99)
    return checks


def build_provenance_report(
    job_id: str,
    ckpt: Dict[str, Any],
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create the API response for a checkpoint that contains provenance."""
    checks = _provenance_checks(ckpt, workspace_root)
    return {
        "available": True,
        "job_id": job_id,
        "code": {
            "git_commit": ckpt.get("git_commit") or "",
            "seed": ckpt.get("seed"),
            "run_purpose": ckpt.get("run_purpose") or "",
            "run_status": ckpt.get("run_status") or "",
            "determinism": _determinism_summary(ckpt.get("determinism")),
            "created_at": ckpt.get("created_at") or "",
        },
        "data": {
            "dataset_version": ckpt.get("dataset_version") or "",
            "split_version": ckpt.get("split_version") or "",
            "dataset_manifest_checksum": ckpt.get("dataset_manifest_checksum") or "",
            "recognition_profile": ckpt.get("recognition_profile") or "",
            "vocabulary_schema_version": ckpt.get("vocabulary_schema_version") or "",
        },
        "model": {
            "model_type": ckpt.get("model_type") or "",
            "num_classes": ckpt.get("num_classes"),
            "seq_len": ckpt.get("seq_len"),
            "feature_dim": ckpt.get("feature_dim"),
            "normalization_version": ckpt.get("normalization_version") or "",
            "storage_contract_version": ckpt.get("storage_contract_version") or "",
        },
        "model_selection": ckpt.get("model_selection") or {},
        "runtime_env": ckpt.get("runtime_env") or {},
        "checks": checks,
        "reproducible": all(check["ok"] for check in checks),
    }
