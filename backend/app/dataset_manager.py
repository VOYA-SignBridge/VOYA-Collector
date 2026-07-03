from __future__ import annotations

import os
import re
import csv
import uuid
import logging
import unicodedata
from pathlib import Path
from datetime import datetime
from filelock import FileLock
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from app.processing.utils import atomic_write_json

from app.config import settings

logger = logging.getLogger(__name__)

DATASET_ROOT = settings.dataset_root
FEATURES_ROOT = DATASET_ROOT / "features"
LABELS_DIR = DATASET_ROOT / "labels"
MASTER_LABELS = DATASET_ROOT / "labels.csv"
LANGUAGE_LABELS = LABELS_DIR / "labels_language.csv"
DIALECT_LABELS = LABELS_DIR / "labels_dialect.csv"

# Field order for labels_master.csv (extended to include class_idx, folder_name, timestamps)
LABEL_FIELDS = [
    "class_uid",
    "class_idx",
    "slug",
    "label_original",
    "language",
    "dialect",
    "is_common_global",
    "is_common_language",
    "folder_name",
    "created_at",
    "migrated_at",
    "deleted_at",
]


def slugify(text: str, maxlen: int = 40) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    if len(text) > maxlen:
        text = text[:maxlen].rstrip("-")
    return text or "label"


def now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


def parse_bool(value) -> bool:
    """Parse a boolean-like CSV field into Python bool.
    Accepts: 1/0, '1'/'0', 'true'/'false', 'True'/'False', and raw bools.
    Falls back to False for unknown values.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    sl = s.lower()
    if sl in ("1", "true", "t", "yes", "y"):
        return True
    if sl in ("0", "false", "f", "no", "n"):
        return False
    try:
        return bool(int(s))
    except Exception:
        return False


def normalize_dialect(dialect: Optional[str]) -> str:
    """Normalize frontend dialect names to canonical slugs.
    Examples: "Bắc"->"bac", "Trung"->"trung", "Nam"->"nam", "Hòa Đê"/"Hoa De"->"hoa-de".
    Also accepts already-normalized values.
    """
    if not dialect:
        return ""
    d = str(dialect).strip().lower()
    # Remove diacritics and extra spaces to match mapping better
    base = "".join([c for c in d if not unicodedata.combining(c)])
    base = re.sub(r"\s+", " ", base).strip()
    # Try exact and base
    return DIALECT_MAPPING.get(d, DIALECT_MAPPING.get(base, d))


# Module-level mapping constant for reuse and testability
DIALECT_MAPPING = {
    "bac": "bac",
    "bắc": "bac",
    "mien bac": "bac",
    "miền bắc": "bac",
    "north": "bac",
    "trung": "trung",
    "miền trung": "trung",
    "mien trung": "trung",
    "central": "trung",
    "nam": "nam",
    "miền nam": "nam",
    "mien nam": "nam",
    "south": "nam",
    "hoa de": "hoa-de",
    "hòa đê": "hoa-de",
    "hoa đê": "hoa-de",
    "hoade": "hoa-de",
    "hoa-de": "hoa-de",
    "chung": "common",
}


def normalize_dialect(dialect: Optional[str]) -> str:
    """ASCII-safe normalization for dialect values received from the API."""
    if not dialect:
        return ""

    raw = str(dialect).strip()
    if not raw:
        return ""

    lowered = raw.lower().replace("\u0111", "d")
    ascii_base = unicodedata.normalize("NFKD", lowered)
    ascii_base = "".join(c for c in ascii_base if not unicodedata.combining(c))
    ascii_base = re.sub(r"[^a-z0-9]+", " ", ascii_base).strip()
    compact = re.sub(r"\s+", " ", ascii_base)
    slug = compact.replace(" ", "-")

    robust_mapping = {
        "bac": "bac",
        "mien bac": "bac",
        "trung": "trung",
        "mien trung": "trung",
        "nam": "nam",
        "mien nam": "nam",
        "north": "bac",
        "central": "trung",
        "south": "nam",
        "hoa de": "hoa-de",
        "hoade": "hoa-de",
        "hoa-de": "hoa-de",
        "can tho": "can-tho",
        "cantho": "can-tho",
        "can-tho": "can-tho",
        "chung": "common",
        "common": "common",
    }

    for candidate in (compact, slug):
        if candidate in robust_mapping:
            return robust_mapping[candidate]

    return slug


@dataclass
class ClassMetadata:
    class_uid: str
    slug: str
    label_original: str
    language: str
    dialect: str
    is_common_global: bool
    is_common_language: bool
    folder_override: Optional[str] = None
    class_idx: Optional[int] = None
    deleted_at: Optional[str] = None

    def folder_name(self) -> str:
        if self.folder_override:
            return self.folder_override
        # Generate folder_name from slug (hyphenated) keeping hyphens for folder naming
        short_uid = self.class_uid[:8] if self.class_uid else "unknown"
        return f"class_{self.slug}_{short_uid}"

    def hierarchy_path(self) -> Path:
        if self.is_common_global:
            return FEATURES_ROOT / "global_common" / self.folder_name()
        if self.is_common_language:
            return FEATURES_ROOT / self.language / "common" / self.folder_name()
        # dialect-specific
        return FEATURES_ROOT / self.language / self.dialect / self.folder_name()

    def to_label_row(self) -> Dict[str, Any]:
        return {
            "class_uid": self.class_uid,
            "class_idx": str(self.class_idx or ""),
            "slug": self.slug,
            "label_original": self.label_original,
            "language": self.language,
            "dialect": self.dialect,
            "is_common_global": str(int(self.is_common_global)),
            "is_common_language": str(int(self.is_common_language)),
            "folder_name": self.folder_name(),
            "created_at": now_str(),
            "migrated_at": now_str(),
            "deleted_at": self.deleted_at or "",
        }

    def write_metadata_json(self):
        path = self.hierarchy_path() / "metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "class_uid": self.class_uid,
            "class_idx": self.class_idx,
            "slug": self.slug,
            "label_original": self.label_original,
            "language": self.language,
            "dialect": self.dialect,
            "is_common_global": self.is_common_global,
            "is_common_language": self.is_common_language,
            "folder_name": self.folder_name(),
            "deleted_at": self.deleted_at,
        }
        atomic_write_json(path, data, indent=2)


def _ensure_labels_file():
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    # Ensure the canonical master labels file exists at dataset root
    if not MASTER_LABELS.exists():
        lock = FileLock(str(MASTER_LABELS) + ".lock")
        with lock:
            if not MASTER_LABELS.exists():  # double-check under lock
                MASTER_LABELS.parent.mkdir(parents=True, exist_ok=True)
                with open(MASTER_LABELS, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
                    writer.writeheader()
    # ensure derivative label indexes exist (generated lazily)
    for path, fields in [
        (
            LANGUAGE_LABELS,
            ["language", "class_uid", "slug", "label_original", "is_common_language"],
        ),
        (
            DIALECT_LABELS,
            ["language", "dialect", "class_uid", "slug", "label_original"],
        ),
    ]:
        if not path.exists():
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()


def load_labels() -> List[Dict[str, str]]:
    _ensure_labels_file()
    with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_existing(language: str, dialect: str, slug: str) -> Optional[Dict[str, str]]:
    rows = load_labels()
    for r in rows:
        if r["language"] == language and r["dialect"] == dialect and r["slug"] == slug:
            return r
    return None


def _exists_in_locked(file_path: Path, target_row: Dict[str, Any]) -> bool:
    """Read FRESH STATE directly from disk. MUST only be called while INSIDE a lock.

    Checks the full uniqueness tuple (language, dialect, slug) — not just slug.
    """
    if not file_path.exists():
        return False
    target_lang = target_row.get("language", "")
    target_dialect = target_row.get("dialect", "")
    target_slug = target_row.get("slug", "")
    if not target_slug:
        return False
    with open(file_path, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (
                r.get("language") == target_lang
                and r.get("dialect") == target_dialect
                and r.get("slug") == target_slug
            ):
                return True
    return False


def _load_labels_locked() -> List[Dict[str, str]]:
    """Read labels from disk. MUST only be called while INSIDE a lock."""
    if not MASTER_LABELS.exists():
        return []
    with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_label_row(row: Dict[str, Any]):
    """Append a label row with TOCTOU-safe Check → Lock → Write."""
    _ensure_labels_file()

    lock = FileLock(str(MASTER_LABELS) + ".lock")
    with lock:
        # CHECK: read fresh state from disk while holding lock
        if _exists_in_locked(MASTER_LABELS, row):
            logger.debug(
                "[CLASS] Label already exists, skipping: slug=%s lang=%s dialect=%s",
                row.get("slug"), row.get("language"), row.get("dialect"),
            )
            return

        # WRITE: append immediately after check
        file_exists = MASTER_LABELS.exists()
        with open(MASTER_LABELS, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
            if not file_exists or os.path.getsize(MASTER_LABELS) == 0:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    # Regenerate derived language/dialect index files under dataset/labels/
    regenerate_label_indexes()

    sync_master_labels_to_gdrive()


def sync_master_labels_to_gdrive() -> None:
    from app.storage.catalog_mirror import mirror_labels_to_gdrive_and_sheets

    mirror_labels_to_gdrive_and_sheets(MASTER_LABELS)


def regenerate_label_indexes():
    rows = load_labels()
    # language-level common summary
    lang_rows = []
    dialect_rows = []
    for r in rows:
        lang = r["language"]
        dialect = r["dialect"]
        lang_rows.append(
            {
                "language": lang,
                "class_uid": r["class_uid"],
                "slug": r["slug"],
                "label_original": r["label_original"],
                "is_common_language": r["is_common_language"],
            }
        )
        dialect_rows.append(
            {
                "language": lang,
                "dialect": dialect,
                "class_uid": r["class_uid"],
                "slug": r["slug"],
                "label_original": r["label_original"],
            }
        )
    for path, items, fields in [
        (
            LANGUAGE_LABELS,
            lang_rows,
            ["language", "class_uid", "slug", "label_original", "is_common_language"],
        ),
        (
            DIALECT_LABELS,
            dialect_rows,
            ["language", "dialect", "class_uid", "slug", "label_original"],
        ),
    ]:
        lock = FileLock(str(path) + ".lock")
        with lock:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(items)


def _build_meta_from_row(existing: Dict[str, str]) -> ClassMetadata:
    """Construct ClassMetadata from a labels CSV row."""
    return ClassMetadata(
        class_uid=existing["class_uid"],
        class_idx=int(existing.get("class_idx") or 0)
        if existing.get("class_idx")
        else None,
        slug=existing["slug"],
        label_original=existing["label_original"],
        language=existing["language"],
        dialect=existing["dialect"],
        is_common_global=parse_bool(existing.get("is_common_global")),
        is_common_language=parse_bool(existing.get("is_common_language")),
        folder_override=existing.get("folder_name") or None,
        deleted_at=existing.get("deleted_at") or None,
    )


def _collect_indices(rows: List[Dict[str, str]]) -> List[int]:
    """Extract all valid class_idx integers from label rows."""
    out = []
    for r in rows:
        val = r.get("class_idx") or ""
        if val.isdigit():
            try:
                out.append(int(val))
            except Exception:
                pass
    return out


def register_class(
    label_original: str,
    language: str,
    dialect: str,
    is_common_global: bool = False,
    is_common_language: bool = False,
) -> ClassMetadata:
    """Register or fetch existing class with TOCTOU-safe locking.

    The entire Check → Allocate class_idx → Write sequence is wrapped
    in a single FileLock to prevent race conditions.

    Rules:
    - global_common: is_common_global=True overrides other flags.
    - language common: is_common_language=True and dialect should be 'common'.
    - dialect specific: neither flag true.
    """
    _ensure_labels_file()
    language = language.lower().strip()
    dialect = dialect.lower().strip()

    slug = slugify(label_original)

    if is_common_global:
        language_key = "global"
        dialect_key = "global"
    elif is_common_language:
        dialect_key = "common"
        language_key = language
    else:
        language_key = language
        dialect_key = dialect

    lock = FileLock(str(MASTER_LABELS) + ".lock")
    with lock:
        # 1. CHECK — read fresh state from disk while holding lock
        rows = _load_labels_locked()
        for r in rows:
            if (
                r.get("language") == language_key
                and r.get("dialect") == dialect_key
                and r.get("slug") == slug
            ):
                # Class already exists — return it
                meta = _build_meta_from_row(r)
                # Release lock before triggering sync
                break
        else:
            # 2. ALLOCATE — compute next class_idx safely inside lock
            indices = _collect_indices(rows)
            next_idx = (max(indices) + 1) if indices else 1

            class_uid = str(uuid.uuid4())
            short_uid = class_uid[:8]
            folder_name = f"class_{slug}_{short_uid}"

            meta = ClassMetadata(
                class_uid=class_uid,
                class_idx=next_idx,
                slug=slug,
                label_original=label_original,
                language=language_key,
                dialect=dialect_key,
                is_common_global=is_common_global,
                is_common_language=is_common_language and not is_common_global,
                folder_override=folder_name,
            )

            # 3. WRITE — append immediately after allocate
            label_row = meta.to_label_row()
            with open(MASTER_LABELS, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
                if os.path.getsize(MASTER_LABELS) == 0:
                    writer.writeheader()
                writer.writerow(label_row)
                f.flush()
                os.fsync(f.fileno())

            # Still inside lock context — this is the new-class path
            # We'll do post-lock work below using the `meta` object

    # --- Post-lock work (safe to do outside lock) ---

    # Regenerate derived index files
    regenerate_label_indexes()

    # Best-effort sync to Google Drive
    sync_master_labels_to_gdrive()

    if getattr(settings, "use_google_drive", False):
        try:
            from app.storage.gdrive_client import get_gdrive_client

            drive_folder_path = f"features/{meta.language}/{meta.dialect}/{meta.folder_name()}"
            get_gdrive_client().ensure_path(drive_folder_path)
            logger.info("[CLASS] Ensured Drive folder path=%s", drive_folder_path)
        except Exception as exc:
            logger.warning("[CLASS] Drive folder ensure failed: %s", exc)

    # Create folder and metadata.json
    folder = meta.hierarchy_path()
    folder.mkdir(parents=True, exist_ok=True)
    meta.write_metadata_json()
    logger.info(
        "[CLASS] Registered class '%s' uid=%s path=%s",
        label_original,
        meta.class_uid,
        folder,
    )
    return meta


def list_classes(
    language: Optional[str] = None, dialect: Optional[str] = None
) -> List[ClassMetadata]:
    rows = load_labels()
    out: List[ClassMetadata] = []
    for r in rows:
        if r.get("deleted_at"):
            continue
        if language and r["language"] != language:
            continue
        if dialect and r["dialect"] != dialect:
            continue
        out.append(
            ClassMetadata(
                class_uid=r["class_uid"],
                class_idx=int(r.get("class_idx") or 0) if str(r.get("class_idx") or "").strip() else None,
                slug=r["slug"],
                label_original=r["label_original"],
                language=r["language"],
                dialect=r["dialect"],
                is_common_global=parse_bool(r.get("is_common_global")),
                is_common_language=parse_bool(r.get("is_common_language")),
                deleted_at=r.get("deleted_at") or None,
            )
        )
    return out


def compute_sample_dir(meta: ClassMetadata) -> Path:
    return meta.hierarchy_path()


def ensure_structure():
    """Create base directories if missing."""
    for p in [
        DATASET_ROOT,
        FEATURES_ROOT,
        LABELS_DIR,
        DATASET_ROOT / "samples",
        DATASET_ROOT / "raw_videos",
        DATASET_ROOT / "raw_live",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def get_or_register_class(
    label_original: str,
    language: str = "vn",
    dialect: str = "",
    is_common_global: bool = False,
    is_common_language: bool = False,
) -> ClassMetadata:
    """Convenience wrapper used by pipelines & routes.
    If class exists returns metadata, else registers.
    For language common classes pass dialect="common" and is_common_language=True.
    For global common classes pass is_common_global=True (language/dialect ignored).
    """
    # Attempt to preserve legacy folder naming if an existing folder is present
    lang = (language or "vn").lower().strip()
    dia_input = dialect or ("common" if is_common_language else "")
    dia = normalize_dialect(dia_input)
    if not dia:
        dia = "common" if is_common_language else ""
    slug = slugify(label_original)

    # Search existing folder under the target hierarchy
    def _find_legacy_folder(base: Path) -> Optional[str]:
        if not base.exists():
            return None
        try:
            for d in base.iterdir():
                if not d.is_dir():
                    continue
                name = d.name
                # Expect legacy folder pattern: class_####_<slug>
                if re.fullmatch(rf"class_\d+_{re.escape(slug)}", name):
                    return name
        except Exception:
            return None
        return None

    base_dir = None
    if is_common_global:
        base_dir = FEATURES_ROOT / "global_common"
    elif is_common_language or dia == "common":
        base_dir = FEATURES_ROOT / lang / "common"
    elif dia:
        base_dir = FEATURES_ROOT / lang / dia

    if base_dir is not None:
        legacy_folder = _find_legacy_folder(base_dir)
        if legacy_folder:
            # Best-effort re-sync on legacy fast-path to keep Drive catalog fresh.
            sync_master_labels_to_gdrive()
            # Try to parse class_idx from legacy folder name: class_0001_slug
            cls_idx_val = None
            try:
                prefix = legacy_folder.split("_")[1]  # '0001'
                if prefix.isdigit():
                    cls_idx_val = int(prefix)
            except Exception:
                cls_idx_val = None
            meta = ClassMetadata(
                class_uid=legacy_folder.split("_")[
                    0
                ],  # not a UUID; used only for metadata/samples rows
                slug=slug,
                label_original=label_original,
                language=("global" if is_common_global else lang),
                dialect=(
                    "global"
                    if is_common_global
                    else ("common" if (is_common_language or dia == "common") else dia)
                ),
                is_common_global=is_common_global,
                is_common_language=(is_common_language or dia == "common")
                and not is_common_global,
                folder_override=legacy_folder,
                class_idx=cls_idx_val,
            )
            # ensure metadata.json exists for this class
            try:
                meta.write_metadata_json()
            except Exception:
                pass
            return meta

    # Fallback to new registration
    return register_class(
        label_original=label_original,
        language=lang,
        dialect=dia,
        is_common_global=is_common_global,
        is_common_language=is_common_language,
    )


if __name__ == "__main__":  # simple manual test
    ensure_structure()
    m1 = register_class("cảm ơn", "vn", "bac")
    m2 = register_class("cảm ơn", "vn", "common", is_common_language=True)
    m3 = register_class("hello", "en", "common", is_common_language=True)
    m4 = register_class("thank you", "global", "global", is_common_global=True)
    print("Registered:")
    for m in [m1, m2, m3, m4]:
        print(m)
    print("List VN common:", list_classes("vn", "common"))
