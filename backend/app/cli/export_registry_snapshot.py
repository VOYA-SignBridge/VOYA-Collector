"""Write the vocabulary snapshot that DB-less consumers read.

Two modes, and the difference between them is the whole point:

  --bootstrap   Build a snapshot from the COMMUNITY seed CSVs. Needs no
                database, so a fresh clone can run make_splits.py. The snapshot
                is stamped `"source": "community_seed"` and version 0, so any
                artifact built from it records that its vocabulary came from the
                template rather than from a real tenant registry.

  (default)     Export tenant <id>'s current registry from Postgres, which also
                freezes it as an immutable version.

This command exists because `processed/shared/vocabulary.py` no longer carries a
hardcoded fallback list. It used to, the list had drifted from the one the
database is seeded with, and every class assigned to `legacy_unassigned` was
dropped from splits in silence. Making the missing case an error is only
tolerable if producing the file is one obvious command — this is it.

    python -m app.cli.export_registry_snapshot --bootstrap
    python -m app.cli.export_registry_snapshot --tenant default
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("registry.snapshot")

REPO = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO / "config"


def _read(name: str) -> List[Dict[str, str]]:
    src = CONFIG_DIR / name
    if not src.is_file():
        return []
    with src.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _flag(row: Dict[str, str], key: str, default: str = "1") -> bool:
    return (row.get(key) or default).strip() == "1"


def _order(row: Dict[str, str], fallback: int) -> int:
    try:
        return int(row.get("display_order") or fallback)
    except (TypeError, ValueError):
        return fallback


def build_bootstrap_snapshot() -> Dict[str, Any]:
    """Community template as a snapshot, straight from the tracked CSVs.

    Deliberately NOT a fallback that some other code path reaches for on its
    own: producing this requires typing --bootstrap, and the result announces
    what it is. A silent version of exactly this is what caused the bug.
    """
    dialects = sorted(_read("dialects.seed.csv"),
                      key=lambda r: (_order(r, 999), r.get("dialect_id") or ""))
    profiles = sorted(_read("profiles.seed.csv"),
                      key=lambda r: (_order(r, 999), r.get("profile_id") or ""))
    if not profiles:
        raise SystemExit(
            "config/profiles.seed.csv trống hoặc không tồn tại — không dựng được "
            "snapshot. DỪNG, không đoán danh sách profile."
        )
    payload: Dict[str, Any] = {
        "source": "community_seed",
        "tenant_id": None,
        "registry_version": 0,
        "generated": "app.cli.export_registry_snapshot --bootstrap",
        "dialects": [
            {"dialect_id": (r.get("dialect_id") or "").strip(),
             "display_name": (r.get("display_name") or "").strip(),
             "language": (r.get("language") or "vn").strip(),
             "is_alphabet": _flag(r, "is_alphabet", "0"),
             "is_active": _flag(r, "is_active"),
             "status": (r.get("status") or "approved").strip()}
            for r in dialects if (r.get("dialect_id") or "").strip()
        ],
        "profiles": [
            {"profile_id": (r.get("profile_id") or "").strip(),
             "display_name": (r.get("display_name") or "").strip(),
             "is_trainable": _flag(r, "is_trainable")}
            for r in profiles if (r.get("profile_id") or "").strip()
        ],
        "aliases": {},
    }
    payload["content_hash"] = _hash(payload)
    return payload


def _hash(payload: Dict[str, Any]) -> str:
    """Same recipe as vocabulary_registry.content_hash, reimplemented with the
    stdlib so --bootstrap keeps working without the backend package importable."""
    import hashlib

    body = {k: v for k, v in payload.items()
            if k not in ("registry_version", "content_hash", "generated", "exported_at")}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _default_target() -> Path:
    return REPO / "dataset" / "vocabulary_registry.json"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Xuất snapshot danh mục từ vựng")
    parser.add_argument("--bootstrap", action="store_true",
                        help="Dựng từ config/*.seed.csv, không cần database")
    parser.add_argument("--tenant", default="default", help="Tenant cần xuất (mặc định: default)")
    parser.add_argument("--out", default=None, help="Đường dẫn file (mặc định dataset/vocabulary_registry.json)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    target = Path(args.out) if args.out else _default_target()

    if args.bootstrap:
        payload = build_bootstrap_snapshot()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning(
            "Đã ghi snapshot BOOTSTRAP từ community seed -> %s\n"
            "  %d phương ngữ, %d profile, hash %s\n"
            "  Đây là MẪU CHUNG, không phải danh mục của tenant nào. Artifact dựng từ "
            "nó sẽ ghi source=community_seed. Khi đã có stack, chạy lại không kèm "
            "--bootstrap để lấy danh mục thật.",
            target, len(payload["dialects"]), len(payload["profiles"]),
            payload["content_hash"][:12],
        )
        return 0

    from app.vocabulary_registry import export_snapshot, registry_version

    path = export_snapshot(args.tenant, path=target if args.out else None)
    logger.info("Đã xuất registry tenant '%s' v%s -> %s",
                args.tenant, registry_version(args.tenant), path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
