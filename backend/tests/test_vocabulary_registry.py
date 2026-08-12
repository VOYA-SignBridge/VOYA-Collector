"""Invariants for the dialect / profile registry. No database needed.

Each test below corresponds to a way this system actually broke:
  T1  a dialect reached the data without ever being registered  ("testdatase")
  T2  a dialect sat in a picker with no data behind it          ("ha-noi")
  T2b an exported snapshot went stale and nobody noticed        (the lost configs)
  T3  a seventh hardcoded copy of the list appears
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from app.vocabulary_registry import slugify_dialect

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "dataset"
SEED = REPO / "config" / "dialects.seed.csv"


def _seeded_ids() -> set:
    if not SEED.is_file():
        pytest.skip("chưa có config/dialects.seed.csv")
    with SEED.open(newline="", encoding="utf-8-sig") as fh:
        return {(r["dialect_id"] or "").strip() for r in csv.DictReader(fh)}


def _csv_dialects(name: str) -> set:
    path = DATASET / name
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return {(r.get("dialect") or "").strip() for r in csv.DictReader(fh)} - {""}


# --------------------------------------------------------------------- slug


@pytest.mark.parametrize("raw,expected", [
    ("Miền Bắc", "mien-bac"),
    ("  MIỀN BẮC  ", "mien-bac"),
    ("Mien Bac", "mien-bac"),
    ("Bảng chữ cái", "bang-chu-cai"),
    ("Hòa Đê", "hoa-de"),
    ("Cần Thơ", "can-tho"),
    ("Đà Nẵng", "da-nang"),
    ("spa", "spa"),
])
def test_slug_is_ascii_lowercase(raw, expected):
    """dialect_id becomes a directory name, so it must fold to ASCII.

    Postgres stores accents perfectly well — display_name keeps them. The
    constraint is the filesystem and Drive sync, not the database.
    """
    assert slugify_dialect(raw) == expected


def test_slug_never_leaves_non_ascii():
    for raw in ("Miền Tây", "Nghệ An", "Đắk Lắk", "Thừa Thiên Huế"):
        slug = slugify_dialect(raw)
        assert slug.isascii() and re.fullmatch(r"[a-z0-9-]+", slug), slug


def test_slug_rejects_empty_after_normalisation():
    for raw in ("", "   ", "!!!", "///"):
        assert slugify_dialect(raw) == ""


# --------------------------------------------------------------------- T1


def test_t1_every_dialect_in_the_data_is_registered():
    """No orphan dialects: data must not invent its own vocabulary."""
    in_data = _csv_dialects("labels.csv") | _csv_dialects("samples.csv")
    missing = sorted(in_data - _seeded_ids())
    assert not missing, (
        f"phương ngữ có trong dữ liệu nhưng KHÔNG có trong danh mục: {missing}. "
        f"Nó ra đời ngoài cửa ghi — đúng cách 'testdatase' lọt vào."
    )


# --------------------------------------------------------------------- T2


def test_t2_no_phantom_dialects():
    """A registered dialect should either hold data or be explicitly inactive."""
    in_data = _csv_dialects("labels.csv") | _csv_dialects("samples.csv")
    with SEED.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    phantom = [
        r["dialect_id"] for r in rows
        if (r.get("is_active") or "1").strip() == "1"
        and (r["dialect_id"] or "").strip() not in in_data
        and (r.get("note") or "").strip() == ""
    ]
    assert not phantom, (
        f"phương ngữ đang hiện trong menu nhưng không có dữ liệu nào: {phantom}. "
        f"Đặt is_active=0, hoặc ghi note giải thích vì sao giữ."
    )


# --------------------------------------------------------------------- T2b


def test_t2b_snapshot_matches_its_own_shape():
    """The export must carry a version — a snapshot without one cannot be
    detected as stale, which is exactly how the old hand-copied config files
    disappeared without anyone noticing."""
    snap = DATASET / "vocabulary_registry.json"
    if not snap.is_file():
        pytest.skip("chưa xuất snapshot (cần DB chạy)")
    data = json.loads(snap.read_text(encoding="utf-8"))
    assert isinstance(data.get("registry_version"), int)
    assert data["registry_version"] > 0, "version 0 nghĩa là chưa bao giờ được ghi"
    for d in data.get("dialects", []):
        assert d["dialect_id"] == slugify_dialect(d["dialect_id"]), d


# --------------------------------------------------------------------- T3


_SCAN_ROOTS = ((REPO / "backend" / "app"), (REPO / "frontend" / "src"))
_ALLOWED = {
    "vocabulary_registry.py",   # the registry itself
    "dataset_manager.py",       # _INPUT_ALIASES: spellings, not identities
    "test_vocabulary_registry.py",
}
# Derived, never hand-listed. The hand-written tuple that used to sit here knew
# only the canonical ids, so a seventh copy of the list in DialectSelector.tsx
# went unnoticed for weeks: it was keyed by the ALIAS spellings ('mien-bac',
# 'mien-nam', 'mien-trung') and matched nothing this test was looking for.
# Reading the alias table means a spelling can never again be invisible here.
def _known_dialect_ids() -> tuple:
    from app.dataset_manager import _INPUT_ALIASES

    ids = set(_INPUT_ALIASES) | set(_INPUT_ALIASES.values())
    # Registered ids that no alias points at, so they are not reachable above.
    ids |= {"bang-chu-cai", "spa"}
    ids |= _seeded_ids() if SEED.is_file() else set()
    return tuple(sorted(i for i in ids if i))


_KNOWN = _known_dialect_ids()

# Copies that already existed and are scheduled for đợt 2 — they live in files
# still carrying merge conflicts, so they cannot be touched yet. This list may
# only ever SHRINK; test_t3_baseline_only_shrinks fails if an entry becomes
# clean and is left here, so it cannot quietly turn into a permanent excuse.
_LEGACY_OFFENDERS: set[str] = set()

_PY_DOCSTRING = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')
_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")


def _strip_comments(text: str, suffix: str) -> str:
    """Comments and docstrings mention dialects constantly and mean nothing.

    Without this the check fires on `self.dialect = dialect  # 'bac', 'nam', …`,
    which is documentation, not a second source of truth.
    """
    if suffix == ".py":
        text = _PY_DOCSTRING.sub("", text)
        return "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    text = _BLOCK_COMMENT.sub("", text)
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def _scan_offenders() -> dict:
    found = {}
    for root in _SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in list(root.rglob("*.py")) + list(root.rglob("*.ts")) + list(root.rglob("*.tsx")):
            if path.name in _ALLOWED or "node_modules" in path.parts:
                continue
            try:
                code = _strip_comments(path.read_text(encoding="utf-8", errors="replace"), path.suffix)
            except Exception:
                continue
            hits = {k for k in _KNOWN if f'"{k}"' in code or f"'{k}'" in code}
            if len(hits) >= 3:
                found[path.relative_to(REPO).as_posix()] = sorted(hits)
    return found


def test_t3_no_new_hardcoded_dialect_list():
    """Block the eighth copy of the list.

    Seven existed when this was written — two of them in one file, shadowing
    each other — and they disagreed about `spa`, `common` and `bang-chu-cai`.
    Ugly as this test is, it is the only thing that stops a new component
    quietly growing its own table again.
    """
    new = {k: v for k, v in _scan_offenders().items() if k not in _LEGACY_OFFENDERS}
    assert not new, (
        "danh sách phương ngữ gắn sẵn MỚI:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in new.items())
        + "\nDùng GET /vocabulary/registry thay vì liệt kê trong mã."
    )


def test_t3_baseline_only_shrinks():
    """A file cleaned up must leave the baseline, or the baseline rots into a
    permanent exemption list."""
    stale = sorted(_LEGACY_OFFENDERS - set(_scan_offenders()))
    assert not stale, (
        f"các file này đã sạch — xoá khỏi _LEGACY_OFFENDERS: {stale}"
    )
