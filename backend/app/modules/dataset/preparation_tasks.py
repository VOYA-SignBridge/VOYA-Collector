"""Chuẩn bị dữ liệu để huấn luyện — từ giao diện, không cần terminal.

Gốc: `experiment/feature-v2` (Kateht, 17/08/2026) — một nút sinh manifest, split
triển khai, split nghiên cứu và fold LOSO. Bản đó viết cho bố cục split cũ
(`processed/splits/versions/<profile>_deploy_vN`) nên hiện vật nó sinh ra không
có chủ tổ chức và bị `resolve_operational` của nhánh này từ chối. Bản này giữ
đúng ý tưởng (một nút, tiến độ ghi ra JSON, chạy trên hàng đợi mặc định) nhưng
sinh thứ mà lượt huấn luyện ở đây thật sự ghim được:

  1. HIỆN VẬT VẬN HÀNH, mỗi phương ngữ một cái:
       make_splits.py --operational_split_id=<dialect>-<YYYYMMDD>-<run>-floor<N>
                      --tenant_id=<tổ chức của người bấm> --dialects <dialect>
                      --min_samples_per_class=<N>
     Có chủ (ràng buộc chữ ký), có sàn mẫu, bất biến — đúng thứ bốn cổng ở
     `POST /training/start` soi. Đây là đường dùng hằng ngày.

  2. (tuỳ chọn, `with_research=True`) SPLIT NGHIÊN CỨU cho các profile của
     phương ngữ đã chọn: đóng băng manifest có checksum → kiểm định → chia
     strict_signer_disjoint (fail-closed, người ký tách riêng). Chúng xuất hiện ở
     "Chế độ nghiên cứu" của wizard, rồi fold LOSO (`make_loso_folds.py`, chép sang
     15/09/2026) từ split strict — mỗi người ký một fold, thứ các bảng báo cáo
     lấy trung bình. LOSO đọc THƯ MỤC split, không đọc manifest.

Tiến độ ghi vào `processed/splits/prepare_runs/<run_id>.json` sau MỖI bước:
giao diện hỏi mỗi vài giây, và worker sập giữa chừng vẫn để lại bằng chứng đã
đi tới đâu. `.delay()` → hàng đợi mặc định (worker), KHÔNG phải hàng đợi
`training` (trainer chạy concurrency thấp trên GPU; chuẩn bị dữ liệu chiếm chỗ
đó là chặn huấn luyện vô cớ).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.infrastructure.celery.app import celery_app

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
MANIFEST_DIR = WORKSPACE_ROOT / "dataset" / "manifests"
SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"
VERSIONS_DIR = SPLITS_DIR / "versions"
RUNS_DIR = SPLITS_DIR / "prepare_runs"

_VERSION_RE = re.compile(r"dataset_manifest_(?P<stem>.+)_v(?P<n>\d+)\.csv$")
MANIFEST_PREFIX = "VSL2026"
LEGACY_MANIFEST_PREFIXES = ("isds2026", "ctu_20260806")
_STEP_TIMEOUT_S = 3600
_SAFE_ID = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_manifest_version(prefix: str = MANIFEST_PREFIX) -> str:
    """Phiên bản manifest chưa dùng. Manifest là bất biến sau khi ghi; bộ đếm
    phủ cả các tiền tố cũ để không cấp lại một số đã định danh ảnh chụp khác."""
    highest = 0
    if MANIFEST_DIR.is_dir():
        for known in (prefix,) + LEGACY_MANIFEST_PREFIXES:
            for f in MANIFEST_DIR.glob(f"dataset_manifest_{known}_v*.csv"):
                m = _VERSION_RE.search(f.name)
                if m and m.group("stem") == known:
                    highest = max(highest, int(m.group("n")))
    return f"{prefix}_v{highest + 1}"


def operational_split_id_for(dialect: str, run_id: str, floor: int, when: Optional[datetime] = None) -> str:
    """`<dialect>-<YYYYMMDD>-<run>-floor<N>`: đọc được bằng mắt, duy nhất theo lượt."""
    d = _SAFE_ID.sub("-", str(dialect).strip().lower()).strip("-") or "unknown"
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"{d}-{stamp}-{run_id[:6]}-floor{int(floor)}"


def _write_report(run_id: str, report: Dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_DIR / f"{run_id}.json.tmp"
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(RUNS_DIR / f"{run_id}.json")


def read_report(run_id: str) -> Optional[Dict[str, Any]]:
    if not re.fullmatch(r"[a-f0-9]{6,32}", str(run_id or "")):
        return None
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[PREP] không đọc được report %s: %s", run_id, exc)
        return None


def create_pending_report(run_id: str, *, tenant_id: str, dialects: List[str], floor: int,
                          seed: int, with_research: bool, requested_by: str) -> Dict[str, Any]:
    """Ghi "đang chờ" TRƯỚC khi đẩy vào hàng đợi: giao diện bắt đầu hỏi ngay khi
    có run_id, không có tệp thì nó báo "không tồn tại" trong khi việc đang xếp hàng."""
    report = {
        "run_id": run_id,
        "status": "queued",
        "tenant_id": tenant_id,
        "dialects": list(dialects),
        "min_samples_per_class": int(floor),
        "seed": int(seed),
        "with_research": bool(with_research),
        "requested_by": requested_by,
        "started_at": _now(),
        "current_step": None,
        "steps": [],
        "operational_splits": [],
        "research_splits": [],
        "warnings": [],
    }
    _write_report(run_id, report)
    return report


def _run(step: str, cmd: List[str], report: Dict[str, Any], run_id: str) -> bool:
    entry: Dict[str, Any] = {"step": step, "cmd": cmd, "started_at": _now()}
    report["steps"].append(entry)
    report["current_step"] = step
    _write_report(run_id, report)

    # KẾ THỪA môi trường của worker (DATABASE_URL, REDIS_URL...): make_splits.py
    # đọc cổng kiểm duyệt từ Postgres và cần `app` import được. Bản gốc dựng một
    # env tối giản chỉ có PYTHONPATH=/workspace nên ở đây sẽ đổ ngay câu đầu
    # ("Khong import duoc app.moderation").
    env = dict(os.environ)
    env["PYTHONPATH"] = "/app:" + str(WORKSPACE_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True,
                              timeout=_STEP_TIMEOUT_S, env=env)
        ok = proc.returncode == 0
        entry["returncode"] = proc.returncode
        entry["stdout_tail"] = (proc.stdout or "")[-3000:]
        entry["stderr_tail"] = (proc.stderr or "")[-3000:]
    except subprocess.TimeoutExpired:
        ok = False
        entry["returncode"] = -1
        entry["stderr_tail"] = f"quá {_STEP_TIMEOUT_S}s — đã dừng"
    except Exception as exc:
        ok = False
        entry["returncode"] = -1
        entry["stderr_tail"] = str(exc)
    entry["ok"] = ok
    entry["finished_at"] = _now()
    _write_report(run_id, report)
    return ok


def _last_lines(text: str, n: int = 3) -> str:
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return " | ".join(lines[-n:])


def _describe_operational(split_id: str) -> Dict[str, Any]:
    meta_path = SPLITS_DIR / "operational" / split_id / "split_metadata.json"
    out: Dict[str, Any] = {"split_id": split_id, "exists": meta_path.exists()}
    if not meta_path.exists():
        return out
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["error"] = str(exc)
        return out
    classes = meta.get("classes") or []
    out.update({
        "num_classes": int(meta.get("num_classes") or len(classes)),
        "dialects": sorted({str(c.get("dialect") or "") for c in classes if c.get("dialect")}),
        "min_samples_per_class": (meta.get("policy") or {}).get("min_samples_per_class"),
        "tenant_id": meta.get("tenant_id"),
    })
    return out


def _describe_research(name: str) -> Dict[str, Any]:
    meta_path = VERSIONS_DIR / name / "split_metadata.json"
    out: Dict[str, Any] = {"split_version": name, "exists": meta_path.exists()}
    if not meta_path.exists():
        return out
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["error"] = str(exc)
        return out
    out.update({
        "split_mode": meta.get("split_mode"),
        "num_classes": meta.get("num_classes"),
        "valid_for_research": meta.get("valid_for_research"),
        "invalid_reasons": meta.get("invalid_reasons") or [],
    })
    return out


_FATAL_CATEGORIES = ("missing files", "schema violations", "checksum mismatches")
_FAIL_LINE = re.compile(r"^\[FAIL\]\s*([^:]+):\s*(\d+)", re.MULTILINE)


def _validation_verdict(step: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Bốn loại phát hiện của trình kiểm định: ba loại làm manifest không tin
    được; "orphan files" chỉ là tệp không được tham chiếu — trạng thái bình
    thường ở đây (excluded_samples.json cố ý bỏ mẫu mà giữ tệp) → cảnh báo."""
    fatal: List[str] = []
    advisories: List[str] = []
    text = "\n".join([step.get("stdout_tail") or "", step.get("stderr_tail") or ""])
    for name, count in _FAIL_LINE.findall(text):
        label = f"{name.strip()}: {count}"
        (fatal if name.strip() in _FATAL_CATEGORIES else advisories).append(label)
    if step.get("returncode") not in (0, None) and not fatal and not advisories:
        fatal.append("trình kiểm định không chạy được (rc=%s)" % step.get("returncode"))
    return fatal, advisories


@celery_app.task(bind=True, name="app.dataset_prep_tasks.prepare_dataset")
def prepare_dataset(
    self,
    run_id: str,
    *,
    tenant_id: str,
    dialects: List[str],
    min_samples_per_class: int = 25,
    seed: int = 42,
    with_research: bool = False,
    profiles: Optional[List[str]] = None,
    requested_by: str = "",
) -> Dict[str, Any]:
    dialects = [str(d).strip() for d in (dialects or []) if str(d).strip()]
    floor = int(min_samples_per_class or 0)
    report = read_report(run_id) or create_pending_report(
        run_id, tenant_id=tenant_id, dialects=dialects, floor=floor, seed=seed,
        with_research=with_research, requested_by=requested_by)
    report["status"] = "running"
    report["started_at"] = _now()
    _write_report(run_id, report)

    def finish(status: str, error: Optional[str] = None) -> Dict[str, Any]:
        report["status"] = status
        if error:
            report["error"] = error
        report["current_step"] = None
        report["finished_at"] = _now()
        _write_report(run_id, report)
        (logger.error if status == "failed" else logger.info)(
            "[PREP] %s %s%s", run_id, status, f": {error}" if error else "")
        return report

    if not tenant_id:
        return finish("failed", "thiếu tenant_id — hiện vật vận hành phải có chủ")
    if not dialects:
        return finish("failed", "chưa chọn phương ngữ nào")

    # 1. Hiện vật vận hành — mỗi phương ngữ một cái, có chủ, có sàn.
    for d in dialects:
        split_id = operational_split_id_for(d, run_id, floor)
        ok = _run(
            f"operational_split:{d}",
            ["python", "processed/splits/make_splits.py",
             "--operational_split_id", split_id, "--tenant_id", tenant_id,
             "--dialects", d, "--min_samples_per_class", str(floor), "--seed", str(seed)],
            report, run_id)
        desc = _describe_operational(split_id)
        desc["dialect"] = d
        desc["ok"] = bool(ok and desc.get("exists"))
        if not desc["ok"]:
            last = report["steps"][-1]
            desc["error"] = _last_lines(last.get("stderr_tail") or last.get("stdout_tail") or "")
            report["warnings"].append(f"{d}: không dựng được hiện vật vận hành — {desc['error']}")
        report["operational_splits"].append(desc)
        _write_report(run_id, report)

    # 2. (tuỳ chọn) split nghiên cứu: manifest đóng băng → kiểm định → strict.
    if with_research:
        # Ảnh chụp đồng thuận phải ≤7 ngày, nếu không create_dataset_manifest
        # từ chối (rc=4, đo 15/09/2026: ảnh 24 ngày tuổi). Worker nối được
        # Postgres nên làm mới ngay tại đây thay vì bắt người dùng chạy lệnh.
        if not _run("consent_snapshot",
                    ["python", "-m", "app.cli.consent_snapshot", "--tenant", tenant_id,
                     "--out", str(WORKSPACE_ROOT / "dataset" / "consent_snapshot.json")],
                    report, run_id):
            report["warnings"].append("không làm mới được ảnh chụp đồng thuận — manifest có thể bị từ chối")
        version = next_manifest_version()
        manifest = f"dataset/manifests/dataset_manifest_{version}.csv"
        report["manifest_version"] = version
        report["manifest"] = manifest
        if not _run("create_manifest",
                    ["python", "scripts/dataset/create_dataset_manifest.py", "--version", version],
                    report, run_id):
            report["warnings"].append("không tạo được manifest — bỏ qua phần nghiên cứu")
        else:
            _run("validate_manifest",
                 ["python", "scripts/dataset/validate_dataset_manifest.py", "--version", version],
                 report, run_id)
            fatal, advisories = _validation_verdict(report["steps"][-1])
            report["warnings"].extend(advisories)
            if fatal:
                report["warnings"].append("manifest không hợp lệ: " + "; ".join(fatal))
            else:
                for profile in (profiles or []):
                    # Tên mang TRỌN phiên bản manifest (`alphabet_strict_VSL2026_v5`),
                    # không chỉ số đuôi: `alphabet_loso_v5` từng trùng tên với hiện
                    # vật isds2026_v5 chép từ máy khác và ghi đè hai fold của nó
                    # (15/09/2026). Hiện vật nghiên cứu là bất biến — trùng tên là DỪNG.
                    strict = f"{profile}_strict_{version}"
                    if (VERSIONS_DIR / strict).exists():
                        report["warnings"].append(f"{profile}: {strict} đã tồn tại — không ghi đè")
                        report["research_splits"].append({"split_version": strict, "profile": profile,
                                                          "ok": False, "exists": True, "error": "đã tồn tại"})
                        continue
                    ok = _run(
                        f"research_split:{profile}",
                        ["python", "-m", "processed.splits.make_splits",
                         "--dataset_manifest", manifest, "--recognition_profile", profile,
                         "--group_col", "signer_id", "--seed", str(seed),
                         "--split_mode", "strict_signer_disjoint",
                         # Cùng sàn với hiện vật vận hành. Không có sàn, một lớp
                         # 16 mẫu do MỘT người ký ("lấy chỉ tôm") ở lại trong tập,
                         # và không phân hoạch tách người ký nào chứa được nó ở cả
                         # ba phần → cả split hoà-đê bị từ chối dù 7 lớp còn lại
                         # có 5–6 người ký (15/09/2026).
                         "--min_samples_per_class", str(floor),
                         "--exclude_unresolved_signers", "--output_version", strict],
                        report, run_id)
                    desc = _describe_research(strict)
                    desc["profile"] = profile
                    desc["ok"] = bool(ok and desc.get("exists"))
                    if desc["ok"] and (WORKSPACE_ROOT / "processed" / "splits" / "make_loso_folds.py").exists():
                        loso = f"{profile}_loso_{version}"
                        if (VERSIONS_DIR / loso).exists():
                            report["warnings"].append(f"{profile}: {loso} đã tồn tại — bỏ qua LOSO")
                            desc["loso"] = {"protocol": loso, "ok": False, "folds": [], "error": "đã tồn tại"}
                            report["research_splits"].append(desc)
                            _write_report(run_id, report)
                            continue
                        loso_ok = _run(
                            f"loso_folds:{profile}",
                            ["python", "processed/splits/make_loso_folds.py",
                             "--source", f"processed/splits/versions/{strict}",
                             "--output_version", loso, "--group_col", "signer_id", "--seed", str(seed)],
                            report, run_id)
                        loso_dir = VERSIONS_DIR / loso
                        desc["loso"] = {
                            "protocol": loso, "ok": loso_ok,
                            "folds": sorted(p.name for p in loso_dir.iterdir()
                                            if p.is_dir() and (p / "train.csv").exists()) if loso_dir.is_dir() else [],
                        }
                        if not loso_ok:
                            last = report["steps"][-1]
                            report["warnings"].append(f"{profile}: LOSO không dựng được — "
                                                      f"{_last_lines(last.get('stderr_tail') or last.get('stdout_tail') or '')}")
                    if not desc["ok"]:
                        # make_splits tự từ chối split nó không bảo đảm được
                        # (cần ≥3 người ký mỗi lớp) — phương ngữ nhỏ thất bại ở
                        # đây là đúng, không phải lỗi.
                        last = report["steps"][-1]
                        desc["error"] = _last_lines(last.get("stderr_tail") or last.get("stdout_tail") or "")
                        report["warnings"].append(
                            f"{profile}: chưa đủ người ký cho split nghiên cứu — {desc['error']}")
                    report["research_splits"].append(desc)
                    _write_report(run_id, report)

    produced = [s for s in report["operational_splits"] if s.get("ok")]
    if not produced:
        return finish("failed", "không dựng được hiện vật vận hành nào")
    return finish("completed")
