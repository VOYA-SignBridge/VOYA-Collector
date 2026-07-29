"""Single source of truth for "is this run citable in the paper?".

Both scripts/audit_checkpoint_validity.py and
scripts/aggregate_experiment_results.py import from here. There must never be
two implementations of these rules: a run that the audit calls valid and the
aggregator silently drops (or worse, the reverse) is exactly how a broken
number reaches a table.

A run is research-valid only when EVERY criterion below holds. Anything that
cannot be decided from the artifacts is treated as NOT valid — never as
"probably fine".

Criteria
--------
C1   run_purpose == "research"            (default is smoke_test, on purpose)
C2   augmentation contract is post-fix    v2_wrist_centered_mirror
C3   checkpoint contract fields present   REQUIRED_CONTRACT_KEYS
C4   dataset_version / split_version set  non-empty
C5   dataset_manifest_checksum present    and, when the manifest is on disk,
                                          matching its recorded sha256
C6   split metadata exists
C7   split metadata valid_for_research    (empty val/test etc. -> false)
C8   recognition_profile matches labels   every label key inside the profile
C9   no cross-profile label leakage       common + declared profile only
C10  runtime environment metadata         python/torch/numpy/device recorded
C11  git_commit non-empty
C12  test set non-empty
C13  metrics come from the restored best-validation checkpoint
C14  run not marked failed/incomplete

NOTE on epochs: a low epoch count is deliberately NOT a criterion. Early
stopping legitimately ends a real run in few epochs. Smoke tests are excluded
by C1 (an explicit run_purpose), not by guessing from hyperparameters.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

POST_FIX_AUGMENTATION_CONTRACTS = {"v2_wrist_centered_mirror"}

RUN_PURPOSE_RESEARCH = "research"
RUN_PURPOSE_SMOKE = "smoke_test"
VALID_RUN_PURPOSES = (RUN_PURPOSE_SMOKE, RUN_PURPOSE_RESEARCH)

# Broken image-space mirror was live in the train loader across this window.
BROKEN_MIRROR_FROM = "2026-05-14"
BROKEN_MIRROR_UNTIL = "2026-07-21"

REQUIRED_CONTRACT_KEYS = (
    "model_type", "recognition_profile", "include_common", "dataset_version",
    "split_version", "vocabulary_schema_version", "normalization_version",
    "seq_len", "feature_dim", "label_to_idx", "idx_to_label",
    "common_labels", "profile_specific_labels", "num_classes", "seed",
    "git_commit", "training_config", "dataset_manifest_checksum",
    "preprocess_contract_version", "storage_contract_version",
    "motion_types_present",
)

REQUIRED_RUNTIME_ENV_KEYS = ("python_version", "pytorch_version", "numpy_version", "device")


class Verdict:
    """valid is True / False / None (None = undecidable from the artifact)."""

    __slots__ = ("valid", "reasons", "criteria")

    def __init__(self, valid, reasons: list, criteria: dict):
        self.valid = valid
        self.reasons = reasons
        self.criteria = criteria

    @property
    def label(self) -> str:
        return {True: "true", False: "false"}.get(self.valid, "unverifiable")

    def __repr__(self) -> str:
        return f"<Verdict {self.label}: {'; '.join(self.reasons) or 'all criteria met'}>"


# --------------------------------------------------------------------------
# split metadata
# --------------------------------------------------------------------------

def evaluate_split_metadata(meta: dict | None) -> tuple[bool, list]:
    """(ok, reasons) for a split_metadata.json payload.

    A split written before the validity gate existed carries no
    valid_for_research field. Those are treated as NOT valid: the two known
    strict splits from that era both had empty val/test.
    """
    if not meta:
        return False, ["split metadata missing (C6)"]
    if "valid_for_research" not in meta:
        return False, [
            "split metadata predates the validity gate and has no "
            "valid_for_research field (C7); regenerate the split"
        ]
    if not meta.get("valid_for_research"):
        detail = "; ".join(meta.get("invalid_reasons") or ["unspecified"])
        return False, [f"split is not valid for research (C7): {detail}"]
    return True, []


def load_split_metadata(split_version: str, repo_root: Path | None = None) -> dict | None:
    root = repo_root or REPO_ROOT
    if not split_version:
        return None
    path = root / "processed" / "splits" / "versions" / split_version / "split_metadata.json"
    if not path.exists():
        return None
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def augmentation_of(ckpt: dict) -> dict | None:
    tc = ckpt.get("training_config")
    if isinstance(tc, dict) and isinstance(tc.get("augmentation"), dict):
        return tc["augmentation"]
    if isinstance(ckpt.get("augmentation"), dict):
        return ckpt["augmentation"]
    return None


def run_purpose_of(ckpt: dict) -> str:
    tc = ckpt.get("training_config") if isinstance(ckpt.get("training_config"), dict) else {}
    return str(ckpt.get("run_purpose") or tc.get("run_purpose") or "").strip()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def allowed_label_prefixes(profile: str, include_common: bool = True) -> set:
    prefixes = {"vn/common/"} if include_common else set()
    if profile == "unified":
        from processed.shared.vocabulary import RECOGNITION_PROFILES
        prefixes |= {f"vn/{p}/" for p in RECOGNITION_PROFILES}
        prefixes.add("vn/common/")
    elif profile:
        prefixes.add(f"vn/{profile}/")
    return prefixes


# --------------------------------------------------------------------------
# the verdict
# --------------------------------------------------------------------------

def evaluate_checkpoint(ckpt: dict, *, split_meta: dict | None = None,
                        repo_root: Path | None = None,
                        check_manifest_checksum: bool = True) -> Verdict:
    """Apply C1..C14 to one loaded checkpoint dict."""
    root = repo_root or REPO_ROOT
    reasons: list = []
    criteria: dict = {}
    undecidable = False

    def note(key: str, ok: bool, reason: str = "") -> bool:
        criteria[key] = ok
        if not ok and reason:
            reasons.append(reason)
        return ok

    # ---- C2 augmentation contract (also the legacy-detection path) --------
    aug = augmentation_of(ckpt)
    if aug is None:
        undecidable = True
        note("C2_augmentation_contract", False,
             "no training_config.augmentation recorded (pre-contract checkpoint); "
             f"train_tcn.py has applied the broken mirror by default since "
             f"{BROKEN_MIRROR_FROM} — assume affected (C2)")
    else:
        contract = str(aug.get("augmentation_contract_version") or "")
        disabled = aug.get("enabled") is False or str(aug.get("profile")) == "none"
        mirror = aug.get("mirror_prob")
        if contract in POST_FIX_AUGMENTATION_CONTRACTS:
            note("C2_augmentation_contract", True)
        elif disabled:
            note("C2_augmentation_contract", True)
        elif mirror is None:
            undecidable = True
            note("C2_augmentation_contract", False,
                 "augmentation recorded but mirror_prob absent — cannot determine (C2)")
        elif float(mirror) == 0.0:
            note("C2_augmentation_contract", True)
        else:
            p = float(aug.get("p", 1.0))
            note("C2_augmentation_contract", False,
                 f"broken image-space mirror active: profile='{aug.get('profile')}' "
                 f"p={p} mirror_prob={mirror} -> ~{p * float(mirror):.0%} of training "
                 f"samples distorted (C2)")

    # ---- C1 run purpose ---------------------------------------------------
    purpose = run_purpose_of(ckpt)
    if not purpose:
        undecidable = True
        note("C1_run_purpose", False,
             "run_purpose not recorded; cannot tell a real experiment from a "
             "smoke test (C1)")
    else:
        note("C1_run_purpose", purpose == RUN_PURPOSE_RESEARCH,
             f"run_purpose='{purpose}', not '{RUN_PURPOSE_RESEARCH}' (C1)")

    # ---- C3 contract completeness ----------------------------------------
    missing = [k for k in REQUIRED_CONTRACT_KEYS if k not in ckpt]
    note("C3_contract_complete", not missing,
         f"checkpoint missing contract keys: {missing[:6]} (C3)")

    # ---- C4 dataset/split version ----------------------------------------
    dsv = str(ckpt.get("dataset_version") or "").strip()
    spv = str(ckpt.get("split_version") or "").strip()
    note("C4_versions_present", bool(dsv) and bool(spv),
         f"dataset_version={dsv!r} split_version={spv!r} — both must be set (C4)")

    # ---- C5 manifest checksum --------------------------------------------
    checksum = str(ckpt.get("dataset_manifest_checksum") or "").strip()
    if not checksum:
        note("C5_manifest_checksum", False, "dataset_manifest_checksum empty (C5)")
    elif check_manifest_checksum and dsv:
        manifest = root / "dataset" / "manifests" / f"dataset_manifest_{dsv}.csv"
        if manifest.exists():
            actual = _sha256_file(manifest)
            note("C5_manifest_checksum", actual == checksum,
                 f"dataset_manifest_checksum does not match {manifest.name} "
                 f"(recorded {checksum[:12]}..., actual {actual[:12]}...) (C5)")
        else:
            note("C5_manifest_checksum", True)  # recorded; manifest not local
    else:
        note("C5_manifest_checksum", True)

    # ---- C6/C7 split validity --------------------------------------------
    if split_meta is None:
        split_meta = load_split_metadata(spv, root)
    ok_split, split_reasons = evaluate_split_metadata(split_meta)
    criteria["C6_split_metadata"] = split_meta is not None
    criteria["C7_split_valid_for_research"] = ok_split
    reasons.extend(split_reasons)

    # ---- C8/C9 label space vs declared profile ----------------------------
    profile = str(ckpt.get("recognition_profile") or "")
    label_map = ckpt.get("label_to_idx") or {}
    if not label_map:
        note("C8_profile_matches_labels", False, "label_to_idx missing/empty (C8)")
        criteria["C9_no_cross_profile"] = False
    else:
        include_common = bool(ckpt.get("include_common"))
        prefixes = allowed_label_prefixes(profile, include_common=include_common)
        foreign = [k for k in label_map if not any(k.startswith(p) for p in prefixes)]
        note("C8_profile_matches_labels", bool(profile),
             "recognition_profile empty while label map is populated (C8)")
        note("C9_no_cross_profile", not foreign,
             f"cross-profile labels in a '{profile}' checkpoint: {foreign[:5]} (C9)")
        declared = set(ckpt.get("common_labels") or []) | set(ckpt.get("profile_specific_labels") or [])
        if declared and declared != set(label_map):
            reasons.append("common+profile label lists disagree with label_to_idx (C8)")
            criteria["C8_profile_matches_labels"] = False

    # ---- C10 runtime env --------------------------------------------------
    env = ckpt.get("runtime_env") if isinstance(ckpt.get("runtime_env"), dict) else {}
    missing_env = [k for k in REQUIRED_RUNTIME_ENV_KEYS if not env.get(k)]
    note("C10_runtime_env", not missing_env,
         f"runtime_env incomplete, missing {missing_env} (C10)")

    # ---- C11 git commit ---------------------------------------------------
    note("C11_git_commit", bool(str(ckpt.get("git_commit") or "").strip()),
         "git_commit empty — run provenance cannot be pinned (C11)")

    # ---- C12 test set non-empty ------------------------------------------
    counts = (split_meta or {}).get("counts") or {}
    n_test = counts.get("test")
    if n_test is None:
        note("C12_test_set_non_empty", split_meta is not None,
             "cannot determine test-set size (C12)")
    else:
        note("C12_test_set_non_empty", int(n_test) > 0,
             f"test split has {n_test} samples (C12)")

    # ---- C13 metrics from restored best-val checkpoint --------------------
    tc = ckpt.get("training_config") if isinstance(ckpt.get("training_config"), dict) else {}
    selection = ckpt.get("model_selection") or tc.get("model_selection")
    if selection is None:
        undecidable = True
        note("C13_best_val_restored", False,
             "model_selection not recorded; cannot confirm test metrics came from "
             "the restored best-validation checkpoint (C13)")
    else:
        note("C13_best_val_restored", bool(selection.get("restored_best_state")),
             "test metrics were not produced from the restored best-validation "
             "state (C13)")

    # ---- C14 run completed ------------------------------------------------
    status = str(ckpt.get("run_status") or "completed").strip().lower()
    note("C14_run_completed", status in ("completed", "ok", ""),
         f"run_status='{status}' (C14)")

    hard_failures = [k for k, ok in criteria.items() if not ok]
    if not hard_failures:
        return Verdict(True, [], criteria)
    # Undecidable only when nothing is definitively wrong beyond the unknowns.
    definite = [k for k in hard_failures
                if k not in ("C1_run_purpose", "C2_augmentation_contract",
                             "C13_best_val_restored")]
    if undecidable and not definite:
        return Verdict(None, reasons, criteria)
    return Verdict(False, reasons, criteria)


def summarize(verdicts: Iterable[Verdict]) -> dict:
    out = {"true": 0, "false": 0, "unverifiable": 0}
    for v in verdicts:
        out[v.label] += 1
    return out
