from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .schemas import LabelSpec, RegistryModelEntry


EXPECTED_HANDEDNESS_POLICY = "swapped_mp_handedness_slots"


def canonical_json_sha256(obj: Any) -> str:
    """Compute a semantic contract hash using canonical JSON.

    This is NOT the checkpoint file hash. This hashes contract content only.
    """
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_registry_contract(entry: RegistryModelEntry) -> None:
    # Strict shape invariants
    if int(entry.seq_len) != 60 or int(entry.feature_dim) != 126:
        raise ValueError(f"registry model {entry.id} has unsupported dims: seq_len={entry.seq_len} feature_dim={entry.feature_dim}")

    # Handedness semantic invariant
    pol = entry.preprocess_contract.feature_layout.handedness_policy
    if pol != EXPECTED_HANDEDNESS_POLICY:
        raise ValueError(
            f"registry model {entry.id} handedness_policy must be {EXPECTED_HANDEDNESS_POLICY!r} (got {pol!r})"
        )

    # Strict expected shape must match
    T, D = entry.preprocess_contract.expects_strict_shape
    if int(T) != int(entry.seq_len) or int(D) != int(entry.feature_dim):
        raise ValueError(
            f"registry model {entry.id} expects_strict_shape {entry.preprocess_contract.expects_strict_shape} mismatches seq_len/feature_dim"
        )


def validate_checkpoint_schema(ckpt: Dict[str, Any]) -> None:
    required = [
        "schema_version",
        "model_state_dict",
        "model_type",
        "model_config",
        "feature_dim",
        "seq_len",
        "num_classes",
        "normalization_version",
        "preprocess_contract",
        "idx_to_label",
    ]
    missing = [k for k in required if k not in ckpt]
    if missing:
        raise ValueError(f"checkpoint missing required keys: {missing}")

    if not isinstance(ckpt.get("idx_to_label"), list):
        raise ValueError("checkpoint idx_to_label must be a list")


def validate_labels(
    idx_to_label: List[Dict[str, Any]],
    *,
    num_classes: int,
    registry_language: str,
    registry_dialect: Optional[str],
) -> List[LabelSpec]:
    if len(idx_to_label) != int(num_classes):
        raise ValueError(f"idx_to_label length {len(idx_to_label)} != num_classes {num_classes}")

    labels: List[LabelSpec] = []
    seen_keys: Set[str] = set()

    for i, raw in enumerate(idx_to_label):
        try:
            spec = LabelSpec.parse_obj(raw)
        except Exception as exc:
            raise ValueError(f"idx_to_label[{i}] invalid: {exc}") from exc

        if spec.label_key in seen_keys:
            raise ValueError(f"duplicate label_key in idx_to_label: {spec.label_key}")
        seen_keys.add(spec.label_key)

        # Alignment safeguards: labels must match model scope
        if spec.language != registry_language:
            raise ValueError(
                f"idx_to_label[{i}] language mismatch: {spec.language!r} != registry {registry_language!r}"
            )

        if registry_dialect is not None and spec.dialect != registry_dialect:
            raise ValueError(
                f"idx_to_label[{i}] dialect mismatch: {spec.dialect!r} != registry {registry_dialect!r}"
            )

        labels.append(spec)

    return labels


def validate_checkpoint_vs_registry(ckpt: Dict[str, Any], entry: RegistryModelEntry) -> None:
    # Dim checks
    if int(ckpt.get("seq_len")) != int(entry.seq_len):
        raise ValueError(f"checkpoint seq_len {ckpt.get('seq_len')} != registry {entry.seq_len}")
    if int(ckpt.get("feature_dim")) != int(entry.feature_dim):
        raise ValueError(f"checkpoint feature_dim {ckpt.get('feature_dim')} != registry {entry.feature_dim}")

    # Normalization version must match registry intent
    if str(ckpt.get("normalization_version")) != str(entry.normalization_version):
        raise ValueError(
            f"checkpoint normalization_version {ckpt.get('normalization_version')!r} != registry {entry.normalization_version!r}"
        )

    # Preprocess contract must match exactly (semantic invariants)
    if ckpt.get("preprocess_contract") != entry.preprocess_contract.dict():
        raise ValueError("checkpoint preprocess_contract != registry preprocess_contract (refusing to start)")

    # Optional semantic contract hash pinning
    expected = entry.expected_contract_hash
    if expected:
        actual = ckpt.get("contract_hash")
        if not actual:
            raise ValueError(f"registry pins expected_contract_hash but checkpoint has no contract_hash (model_id={entry.id})")
        if str(actual) != str(expected):
            raise ValueError(
                f"contract_hash mismatch for model_id={entry.id}: checkpoint={actual!r} registry_expected={expected!r}"
            )
