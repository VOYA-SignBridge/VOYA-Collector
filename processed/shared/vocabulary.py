"""Vocabulary schema v2 — canonical module.

Single source of truth for recognition-profile / vocabulary-scope semantics,
shared by backend collection, the migration script, the split pipeline and
the trainer. Pure stdlib on purpose: importable everywhere (backend container,
trainer container, host scripts, tests) without pydantic/torch/numpy.

Schema v2 replaces the overloaded legacy `dialect` field with:
  - vocabulary_scope:     "common" | "profile_specific" | "" (unassigned/needs review)
  - recognition_profile:  north | central | south | hoa_de | legacy_unassigned | ""
  - vocabulary_group:     business grouping (alphabet, hoa_de_vocabulary, spa, ...)
                          NEVER used for model routing
  - collection_campaign:  provenance of the recording (legacy_2026, isds2026_v1, ...)
  - semantic_label:       output meaning (underscore form of the slug)

The legacy `dialect` column is DEPRECATED for new code but kept on disk for
backward compatibility (it still names the physical storage directory).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

VOCABULARY_SCHEMA_VERSION = "v2"

# Profiles a realtime model can be built/routed for. Order is display order.
# "alphabet" is a standalone profile (static fingerspelling) — it is trained
# and deployed independently and is NOT auto-included in regional models.
RECOGNITION_PROFILES: Tuple[str, ...] = ("alphabet", "north", "central", "south", "hoa_de")

# Optional per-label motion characteristic (informational + contract field).
MOTION_TYPES: Tuple[str, ...] = ("static", "dynamic", "mixed")

# Sentinel for legacy rows whose regional assignment is NOT confirmed.
# Never a valid training/routing profile; excluded from profile models.
LEGACY_UNASSIGNED = "legacy_unassigned"

SCOPE_COMMON = "common"
SCOPE_PROFILE_SPECIFIC = "profile_specific"
VALID_SCOPES: Tuple[str, ...] = (SCOPE_COMMON, SCOPE_PROFILE_SPECIFIC)

# New v2 columns appended to labels.csv (order matters for CSV headers).
LABEL_V2_FIELDS: Tuple[str, ...] = (
    "semantic_label",
    "vocabulary_scope",
    "recognition_profile",
    "vocabulary_group",
    "collection_campaign",
    "is_active",
    "motion_type",  # static | dynamic | mixed | "" (unknown)
)


def semantic_label_from_slug(slug: str) -> str:
    """cam-on -> cam_on. Semantic labels use underscores by convention."""
    return (slug or "").strip().replace("-", "_")


def validate_label_v2(row: Dict[str, str]) -> List[str]:
    """Return a list of human-readable schema violations (empty = valid).

    Rules:
      - scope common        -> recognition_profile must be empty/null
      - scope profile_specific -> recognition_profile required, in RECOGNITION_PROFILES
      - legacy_unassigned   -> only allowed with empty scope (pending review)
      - empty scope         -> allowed (unmigrated/needs review) but flagged upstream
    """
    errors: List[str] = []
    scope = (row.get("vocabulary_scope") or "").strip()
    profile = (row.get("recognition_profile") or "").strip()

    if scope and scope not in VALID_SCOPES:
        errors.append(f"invalid vocabulary_scope '{scope}' (allowed: {VALID_SCOPES})")

    if scope == SCOPE_COMMON and profile not in ("", "null", "none"):
        errors.append(
            f"common label must not carry a recognition_profile (got '{profile}')"
        )
    if scope == SCOPE_PROFILE_SPECIFIC:
        if profile in ("", "null", "none"):
            errors.append("profile_specific label requires a recognition_profile")
        elif profile not in RECOGNITION_PROFILES:
            errors.append(
                f"invalid recognition_profile '{profile}' "
                f"(allowed: {RECOGNITION_PROFILES}; '{LEGACY_UNASSIGNED}' is not trainable)"
            )
    if not scope and profile and profile not in (LEGACY_UNASSIGNED,) + RECOGNITION_PROFILES:
        errors.append(f"unknown recognition_profile '{profile}' on unassigned row")
    motion = (row.get("motion_type") or "").strip()
    if motion and motion not in MOTION_TYPES:
        errors.append(f"invalid motion_type '{motion}' (allowed: {MOTION_TYPES} or empty)")
    return errors


def label_key_v2(
    language: str,
    vocabulary_scope: str,
    recognition_profile: str,
    slug: str,
) -> str:
    """Stable v2 label key.

    common           -> vn/common/<slug>
    profile_specific -> vn/<profile>/<slug>

    Raises ValueError for rows that are not cleanly assigned — callers must
    filter those out (or keep using the legacy key for legacy experiments).
    """
    lang = (language or "vn").strip() or "vn"
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("label_key_v2: empty slug")
    scope = (vocabulary_scope or "").strip()
    profile = (recognition_profile or "").strip()
    if scope == SCOPE_COMMON:
        return f"{lang}/common/{slug}"
    if scope == SCOPE_PROFILE_SPECIFIC and profile in RECOGNITION_PROFILES:
        return f"{lang}/{profile}/{slug}"
    raise ValueError(
        f"label_key_v2: row not assignable (scope='{scope}', profile='{profile}', slug='{slug}')"
    )


def is_row_selectable(row: Dict[str, str]) -> bool:
    """A row participates in v2 training only when cleanly assigned."""
    return not validate_label_v2(row) and (row.get("vocabulary_scope") or "").strip() in VALID_SCOPES


def select_rows_for_profile(
    rows: Iterable[Dict[str, str]],
    recognition_profile: Optional[str] = None,
    include_common: bool = False,
    unified: bool = False,
) -> List[Dict[str, str]]:
    """Core subset rule for profile training.

    profile model:  profile_specific(selected profile) ONLY by default;
                    common vocabulary is added only with an EXPLICIT
                    include_common=True (policy since 2026-07-19: profiles —
                    including the standalone 'alphabet' — train independently)
    unified model:  common + every profile_specific row with a VALID profile
                    (legacy_unassigned rows are excluded from all models)
    """
    if unified and recognition_profile:
        raise ValueError("--unified and --recognition_profile are mutually exclusive")
    if not unified:
        if recognition_profile not in RECOGNITION_PROFILES:
            raise ValueError(
                f"recognition_profile must be one of {RECOGNITION_PROFILES}, got '{recognition_profile}'"
            )

    out: List[Dict[str, str]] = []
    for r in rows:
        scope = (r.get("vocabulary_scope") or "").strip()
        profile = (r.get("recognition_profile") or "").strip()
        if scope == SCOPE_COMMON:
            if unified or include_common:
                out.append(r)
        elif scope == SCOPE_PROFILE_SPECIFIC and profile in RECOGNITION_PROFILES:
            if unified or profile == recognition_profile:
                out.append(r)
        # empty scope / legacy_unassigned: never selected
    return out


def check_label_collisions(rows: Iterable[Dict[str, str]]) -> List[str]:
    """Detect slugs present in BOTH common and any profile-specific set.

    A collision would make a profile model contain the "same" word twice under
    two label keys — must be resolved (rename or reassign) before training.
    Returns list of offending slugs.
    """
    common_slugs = set()
    profile_slugs = set()
    for r in rows:
        scope = (r.get("vocabulary_scope") or "").strip()
        slug = (r.get("label_slug") or r.get("slug") or "").strip()
        if not slug:
            continue
        if scope == SCOPE_COMMON:
            common_slugs.add(slug)
        elif scope == SCOPE_PROFILE_SPECIFIC:
            profile_slugs.add(slug)
    return sorted(common_slugs & profile_slugs)


def split_common_and_profile_labels(
    label_keys: Sequence[str],
) -> Tuple[List[str], List[str]]:
    """Partition v2 label keys into (common_labels, profile_specific_labels)."""
    common: List[str] = []
    specific: List[str] = []
    for k in label_keys:
        parts = (k or "").split("/")
        if len(parts) >= 2 and parts[1] == "common":
            common.append(k)
        else:
            specific.append(k)
    return common, specific
