from __future__ import annotations

import os
import re
import csv
import json
import uuid
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from filelock import FileLock
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from app.processing.utils import atomic_write_json
from app.processing.quality import parse_hands_required  # re-exported for callers
# Single source of truth for alphabet slug rules — see class_registry.
from app.processing.class_registry import (
    _VN_ALPHABET_SLUG,
    assert_single_alphabet_letter,
    is_alphabet_dialect,
)

from app.config import settings
from app.tenancy import (
    DEFAULT_TENANT_ID,
    TENANT_COLUMN,
    normalize_tenant_id,
    tenant_id_of,
)

logger = logging.getLogger(__name__)

DATASET_ROOT = settings.dataset_root
FEATURES_ROOT = DATASET_ROOT / "features"
LABELS_DIR = DATASET_ROOT / "labels"
MASTER_LABELS = DATASET_ROOT / "labels.csv"
LANGUAGE_LABELS = LABELS_DIR / "labels_language.csv"
DIALECT_LABELS = LABELS_DIR / "labels_dialect.csv"

# Field order for labels_master.csv (extended to include class_idx, folder_name, timestamps)
# NOTE: `dialect` is DEPRECATED as a semantic field (it conflated region /
# vocabulary domain / collection campaign). It is kept because it still names
# the physical storage directory. New code must use the vocabulary schema v2
# columns below (see processed/shared/vocabulary.py + docs/02-data/VOCABULARY_SCHEMA_V2.md).
LABEL_FIELDS = [
    "class_uid",
    "class_idx",
    "slug",
    "label_original",
    "language",
    "dialect",  # deprecated semantics — physical storage dir only
    "is_common_global",
    "is_common_language",
    "folder_name",
    "created_at",
    "migrated_at",
    "hands_required",
    # --- vocabulary schema v2 ---
    "semantic_label",
    "vocabulary_scope",
    "recognition_profile",
    "vocabulary_group",
    "collection_campaign",
    "is_active",
    "motion_type",  # static | dynamic | mixed | "" (unknown)
    # Owning tenant. Appended LAST so the Sheets mirror's column positions are
    # unchanged. See app/tenancy.py for why the value is a constant and not a
    # setting, and docs/11-worklog/BACKEND_WORK_PLAN.md item A1 for why the SOT
    # needs the column at all when Postgres already has it.
    TENANT_COLUMN,
    # Vùng miền địa lý của KÝ HIỆU — trục riêng, không phải `dialect`.
    #
    # `dialect` trước đây gánh cả ba nghĩa (xem chú thích ở đầu LABEL_FIELDS);
    # ba lớp dùng nó để chứa vùng miền đã được gỡ ngày 14/08/2026, xem
    # E:\CTU_ProjectOutside\voya_lop_vung_2026-08-14\. Cột này tách nghĩa đó ra
    # để `dialect` chỉ còn là tên thư mục lưu trữ.
    #
    # Giá trị chuẩn hoá: "bac" | "trung" | "nam" | "" (chưa biết).
    # KHÔNG dùng "" như "vùng chung" — chưa biết thì để trống, đừng suy từ nơi
    # thu hay từ người ký. Vùng của NGƯỜI KÝ là cột khác: signers.regional_group.
    #
    # Đặt sau TENANT_COLUMN nên vị trí các cột cũ trên bản chiếu Sheets không đổi.
    "region",
]

# Giá trị hợp lệ cho `region`. Định dạng: chữ thường, không dấu, không khoảng
# trắng — cùng quy ước với dialect_id và profile_id.
#: Mã vùng chưa qua phân loại. KHÁC `common`, và khác biệt đó là cả điểm của
#: thiết kế: `unclassified` nghĩa là "chưa ai xác minh", `common` nghĩa là "đã
#: xác minh rằng không cần phân biệt vùng". Gộp hai thứ này thì không bao giờ
#: trả lời được "còn bao nhiêu nhãn đang chờ phân loại".
#:
#: Chọn `unclassified` chứ không `unknown`: "unknown" đọc lên như một sự thật
#: vĩnh viễn, còn đây là một BƯỚC trong quy trình — nhãn đã vào hệ thống nhưng
#: chưa qua khâu phân loại vùng, và sẽ có người xử lý.
REGION_UNCLASSIFIED = "unclassified"

#: Nguồn sự thật là bảng `regions` (theo tenant). Tuple này chỉ là bộ lọc đầu
#: vào ở tầng ứng dụng cho năm mã của nền tảng — nó KHÔNG được phép là nơi
#: định nghĩa tập giá trị, vì tenant thêm được vùng riêng (`tay-nguyen`,
#: `tay-nam-bo`) mà không sửa mã.
VALID_REGIONS = (REGION_UNCLASSIFIED, "common", "bac", "trung", "nam")


def normalize_region(value: Any) -> str:
    """Chuẩn hoá về một mã vùng; giá trị lạ hoặc rỗng thành `unclassified`.

    Không bao giờ trả NULL hay chuỗi rỗng: cột `classes.region` là NOT NULL kể
    từ v3.19, và "chưa biết" đã có một mã riêng để nói. Giá trị lạ KHÔNG bị
    đoán thành một vùng cụ thể — nó rơi về `unclassified` để người phân loại
    còn thấy mà xử lý, thay vì biến mất thành một vùng nào đó.
    """
    v = (str(value or "")).strip().lower()
    v = {"bắc": "bac", "trung bộ": "trung", "nam bộ": "nam",
         "north": "bac", "central": "trung", "south": "nam",
         "chung": "common", "": REGION_UNCLASSIFIED}.get(v, v)
    return v if v in VALID_REGIONS else REGION_UNCLASSIFIED


@lru_cache(maxsize=1)
def _vocabulary_mapping() -> Dict[str, Dict[str, str]]:
    """dialect -> its confirmed vocabulary-schema-v2 fields.

    Reads config/legacy_vocabulary_mapping.json, the same file
    scripts/migrate_legacy_vocabulary_schema.py used to back-fill the existing
    classes. Only entries the owner marked ``status: confirmed`` are returned —
    an unconfirmed dialect keeps empty cells and shows up in the review report,
    which is the behaviour that file was designed around.

    Without this, a class created through the app carries empty
    recognition_profile / vocabulary_scope, and every split filtered by profile
    silently omits it: the class trains nothing and nobody is told.
    """
    override = os.getenv("VOCABULARY_MAPPING_PATH", "").strip()
    candidates = [Path(override)] if override else [
        Path(__file__).resolve().parents[2] / "config" / "legacy_vocabulary_mapping.json",
        Path("/workspace/config/legacy_vocabulary_mapping.json"),
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            raw = json.loads(path.read_text(encoding="utf-8")).get("dialect_mapping", {})
        except Exception as exc:  # a malformed file must not block recording
            logger.warning("[VOCAB] cannot read %s: %s", path, exc)
            continue
        return {
            dialect: entry
            for dialect, entry in raw.items()
            if isinstance(entry, dict) and entry.get("status") == "confirmed"
        }
    logger.warning("[VOCAB] no vocabulary mapping found; new classes will need manual review")
    return {}


def _semantic_label_from_slug(slug: str) -> str:
    """cam-on -> cam_on. Mirrors semantic_label_from_slug in
    processed/shared/vocabulary.py, which the backend cannot import (the
    `processed` package is not on its path and no backend module depends on it).
    """
    return (slug or "").strip().replace("-", "_")


def vocabulary_defaults_for_dialect(dialect: str) -> Dict[str, str]:
    """The v2 cells a new class in this dialect should be born with."""
    entry = _vocabulary_mapping().get((dialect or "").strip().lower(), {})
    return {
        key: str(entry.get(key) or "")
        for key in (
            "vocabulary_scope",
            "recognition_profile",
            "vocabulary_group",
            "motion_type",
            "collection_campaign",
        )
    }


def ambient_tenant() -> str:
    """The tenant a newly created class belongs to.

    Falls back to the bootstrap tenant when nothing is scoped, which is the same
    answer `app.tenancy` gives for an absent value everywhere else: platform work
    (the CSV import, a CLI) creates rows that provably predate multi-tenancy, and
    those belong to the bootstrap tenant.

    This is the WRITE side only. It never widens what a caller can read — that is
    decided by the database policy, not by this function.
    """
    from app.tenant_context import current_tenant

    return current_tenant() or DEFAULT_TENANT_ID


def tenant_features_root(tenant_id: str) -> Path:
    """Storage root for one tenant — the second isolation plane.

    The bootstrap tenant keeps the historical layout; every other tenant gets its
    own subtree. Two layouts coexist, split by TENANT rather than by time, and
    that distinction is what makes this cheap:

      * `ClassMetadata.hierarchy_path()` has twenty callers — previews, class
        rename/move, the validator, oversampling, the reclassifier. Had the
        bootstrap tenant's path changed, all twenty would need a new-then-legacy
        fallback, and all 8.784 existing `.npz` files would sit behind that
        fallback forever.
      * Splitting by tenant instead gives each tenant exactly ONE layout. No read
        path needs a fallback, no file moves, and every tenant created from here
        on is partitioned from its first byte — the property actually claimed.

    Moving the bootstrap tenant under `_tenants/default/` later is a rename of one
    directory plus a `file_path` rewrite; nothing depends on the asymmetry.

    `_tenants` is underscore-prefixed for the same reason `_profiles` and
    `_versions` are in the registry: it namespaces a directory holding partitions
    rather than data, and it cannot collide with a language code. Path traversal
    is not a concern because `is_valid_tenant_id` excludes `/`, `\\` and `.` —
    that restricted alphabet exists for exactly this reason.
    """
    tenant = normalize_tenant_id(tenant_id)
    if tenant == DEFAULT_TENANT_ID:
        return FEATURES_ROOT
    return FEATURES_ROOT / "_tenants" / tenant


def ambient_tenant_features_root() -> Path:
    """Storage root for the calling tenant."""
    return tenant_features_root(ambient_tenant())


def slugify(text: str, maxlen: int = 40, preserve_vn_letters: bool = False) -> str:
    """ASCII slug. preserve_vn_letters keeps Ă/Â/Đ/Ê/Ô/Ơ/Ư distinct from their
    base letter for the fingerspelling alphabet (see class_registry.slugify)."""
    if preserve_vn_letters:
        # NFC first — see the note in class_registry.slugify: a decomposed "Â"
        # otherwise misses this table and collapses into the base letter.
        key = unicodedata.normalize("NFC", (text or "").strip()).lower()
        if key in _VN_ALPHABET_SLUG:
            return _VN_ALPHABET_SLUG[key]
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


# Ways people TYPE an existing dialect — not identities of their own. Keys are
# already slugified ("Miền Bắc" arrives here as "mien-bac"). Adding a NEW
# dialect belongs in the registry, never here.
_INPUT_ALIASES = {
    "mien-bac": "bac", "north": "bac",
    "mien-trung": "trung", "central": "trung",
    "mien-nam": "nam", "south": "nam",
    "hoade": "hoa-de",
    "cantho": "can-tho",
    "chung": "common",
}


def _assert_known_dialect(dialect_id: str) -> None:
    """Refuse to create a class in a dialect nobody registered.

    This is the door that should have been shut: a sync script wrote the
    non-existent recognition_profile "spa" into 7 classes and nothing objected,
    because every layer accepted whatever string it was handed. Empty stays
    allowed — an unset field shows up in the review report and gets fixed; a
    plausible-looking wrong value never gets looked at again.

    Fails OPEN when the registry is unreachable: a database blip must not stop
    people collecting data. The FK on classes.dialect is the hard guarantee.
    """
    if not dialect_id:
        return
    try:
        from app.vocabulary_registry import known_dialect_ids

        known = known_dialect_ids()
    except Exception as exc:
        logger.warning("[VOCAB] không kiểm được dialect '%s' (registry lỗi: %s)", dialect_id, exc)
        return
    if known and dialect_id not in known:
        raise ValueError(
            f"Phương ngữ '{dialect_id}' chưa có trong danh mục. "
            f"Tạo nó ở Thư viện nhãn trước, đừng gõ thẳng vào đây."
        )


def normalize_dialect(dialect: Optional[str]) -> str:
    """Free-text dialect from the API -> a registered dialect_id.

    Two near-identical copies of this function used to sit here, the second
    silently shadowing the first (and missing "bang-chu-cai"). Both carried a
    hand-maintained table that drifted from the data — "spa" was in neither.
    The registry in Postgres is the list now; what stays here is only the
    handful of INPUT SPELLINGS that are not identities: "Miền Bắc", "north" and
    "bac" are three ways to type one dialect, not three dialects.

    Unknown input passes through as its slug rather than raising: this runs on
    every upload, and refusing here would reject data over a naming question.
    The write-time guard in register_class is what actually blocks unknown
    dialects, and it can explain itself.
    """
    from app.vocabulary_registry import resolve_dialect, slugify_dialect

    slug = slugify_dialect(dialect)
    if not slug:
        return ""
    slug = _INPUT_ALIASES.get(slug, slug)
    try:
        return resolve_dialect(slug)   # follow a merge, e.g. mien-bac -> bac
    except Exception:
        return slug                     # DB unreachable: never block a capture


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
    hands_required: Optional[int] = None  # 1 | 2 | None (unknown)
    # --- vocabulary schema v2 (empty string = unassigned / needs review) ---
    semantic_label: str = ""
    vocabulary_scope: str = ""       # "common" | "profile_specific" | ""
    recognition_profile: str = ""    # north|central|south|hoa_de|legacy_unassigned|""
    vocabulary_group: str = ""
    collection_campaign: str = ""
    is_active: bool = True
    motion_type: str = ""  # static | dynamic | mixed | "" (unknown)
    region: str = REGION_UNCLASSIFIED   # xem VALID_REGIONS / bảng `regions`
    # Owning tenant. Last field and defaulted, so every existing positional and
    # keyword construction keeps working unchanged. Defaulting here (rather than
    # at each call site) is what makes it impossible to register a class with no
    # tenant: there is one constructor and it always has an answer.
    tenant_id: str = DEFAULT_TENANT_ID

    def folder_name(self) -> str:
        if self.folder_override:
            return self.folder_override
        # Generate folder_name from slug (hyphenated) keeping hyphens for folder naming
        short_uid = self.class_uid[:8] if self.class_uid else "unknown"
        return f"class_{self.slug}_{short_uid}"

    def hierarchy_path(self) -> Path:
        """Directory holding this class's samples, partitioned by tenant.

        See `tenant_features_root` for why the bootstrap tenant keeps the
        historical layout while every other tenant gets its own subtree.
        """
        root = tenant_features_root(self.tenant_id)
        if self.is_common_global:
            return root / "global_common" / self.folder_name()
        if self.is_common_language:
            return root / self.language / "common" / self.folder_name()
        # dialect-specific
        return root / self.language / self.dialect / self.folder_name()

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
            "hands_required": str(self.hands_required or ""),
            "semantic_label": self.semantic_label or "",
            "vocabulary_scope": self.vocabulary_scope or "",
            "recognition_profile": self.recognition_profile or "",
            "vocabulary_group": self.vocabulary_group or "",
            "collection_campaign": self.collection_campaign or "",
            "is_active": "1" if self.is_active else "0",
            "motion_type": self.motion_type or "",
            TENANT_COLUMN: normalize_tenant_id(self.tenant_id),
            "region": normalize_region(self.region),
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
            "hands_required": self.hands_required,
        }
        atomic_write_json(path, data, indent=2)


def _upgrade_labels_header_locked():
    """Rewrite labels.csv with the current LABEL_FIELDS header if the on-disk
    header is missing columns. MUST be called while holding the MASTER_LABELS
    lock. All label writers use LABEL_FIELDS directly, so appending new-schema
    rows to an old-header file would silently misalign columns.
    Old rows get "" for the new columns (DictReader restval) — except tenant_id,
    which is stamped with the bootstrap tenant because an empty tenant cell in
    the source of truth means "unassigned", and every pre-A1 class provably
    belongs to that tenant."""
    with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, restval="")
        on_disk = reader.fieldnames or []
        if all(col in on_disk for col in LABEL_FIELDS):
            return
        rows = list(reader)
    for row in rows:
        row[TENANT_COLUMN] = tenant_id_of(row)
    tmp = MASTER_LABELS.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, MASTER_LABELS)
    logger.info("[CLASS] Upgraded labels.csv header to %s (%d rows preserved)", LABEL_FIELDS, len(rows))


def _labels_header_outdated() -> bool:
    """Cheap lock-free peek at the on-disk header (first line only)."""
    try:
        with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
    except (OSError, StopIteration):
        return False
    return bool(header) and any(col not in header for col in LABEL_FIELDS)


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
    elif _labels_header_outdated():
        lock = FileLock(str(MASTER_LABELS) + ".lock")
        with lock:
            _upgrade_labels_header_locked()
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


def _load_all_labels_unscoped() -> List[Dict[str, str]]:
    """MỌI lớp của mọi tenant. Vượt qua ranh giới cách ly — dùng đúng chỗ.

    Xem chú thích dài ở `dataset_samples._load_all_samples_unscoped()`: đây là
    nửa còn lại của cùng một lỗ, đo được ngày 15/08/2026. Đường đọc lớp không đi
    qua PostgreSQL nên RLS không bảo vệ gì; `labels.csv` có cột `tenant_id` mà
    không đường nào hỏi tới.

    Chỉ đường ĐỒNG BỘ / BẢO TRÌ được gọi. Danh sách được cưỡng chế bằng phép
    kiểm kiến trúc, không bằng quy ước.
    """
    _ensure_labels_file()
    with open(MASTER_LABELS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_labels(tenant_id: Optional[str] = None) -> List[Dict[str, str]]:
    """Hàng lớp MÀ TENANT NÀY ĐƯỢC THẤY. `tenant_id` bắt buộc.

    `None` ném lỗi chứ không rơi về toàn cục, và cũng không rơi về `default`.
    Xem `dataset_samples.list_samples()` về vì sao không có đường lùi.
    """
    from app.dataset_samples import TenantScopeRequired

    if not (tenant_id or "").strip():
        raise TenantScopeRequired(
            "load_labels() can tenant_id. Duong bao tri doc toan bo kho phai "
            "goi _load_all_labels_unscoped() — ten do la co y.")
    scope = normalize_tenant_id(tenant_id)
    return [r for r in _load_all_labels_unscoped() if tenant_id_of(r) == scope]


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
    # DictWriter's restval defaults to "", so a row dict that omits tenant_id is
    # written as an empty cell rather than rejected. Stamp it first. Copied, not
    # mutated — callers reuse the dict after this returns.
    row = {**row, TENANT_COLUMN: tenant_id_of(row)}
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


def set_class_hands_required(class_uid: str, hands_required: int) -> bool:
    """Persist hands_required (1|2) for a class, first-capture-wins.

    Only writes when the class has no value yet. Mutates ONLY the
    hands_required cell of the matching row (rebuilding rows via
    to_label_row() would clobber created_at/migrated_at), then atomically
    rewrites labels.csv. Returns True if the value was written.
    """
    hands_required = parse_hands_required(hands_required)
    if hands_required is None:
        return False
    _ensure_labels_file()

    updated_row: Optional[Dict[str, str]] = None
    lock = FileLock(str(MASTER_LABELS) + ".lock")
    with lock:
        rows = _load_labels_locked()
        for r in rows:
            if r.get("class_uid") == class_uid:
                if parse_hands_required(r.get("hands_required")) is not None:
                    return False  # already set — first capture wins
                r["hands_required"] = str(hands_required)
                updated_row = dict(r)
                break
        else:
            logger.warning("[CLASS] set_class_hands_required: class_uid=%s not found", class_uid)
            return False

        tmp = MASTER_LABELS.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS, extrasaction="ignore", restval="")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, MASTER_LABELS)

    logger.info("[CLASS] hands_required=%s persisted for class_uid=%s", hands_required, class_uid)

    # Best-effort mirrors — never fail the caller for these
    try:
        from app.storage.metadata_db import upsert_class
        upsert_class(updated_row)
    except Exception as exc:
        logger.warning("[CLASS] hands_required DB mirror failed: %s", exc)
    try:
        sync_master_labels_to_gdrive()
    except Exception as exc:
        logger.warning("[CLASS] hands_required Drive mirror failed: %s", exc)
    return True


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
        hands_required=parse_hands_required(existing.get("hands_required")),
        semantic_label=(existing.get("semantic_label") or "").strip(),
        vocabulary_scope=(existing.get("vocabulary_scope") or "").strip(),
        recognition_profile=(existing.get("recognition_profile") or "").strip(),
        vocabulary_group=(existing.get("vocabulary_group") or "").strip(),
        collection_campaign=(existing.get("collection_campaign") or "").strip(),
        is_active=parse_bool(existing.get("is_active", "1")) if str(existing.get("is_active") or "").strip() else True,
        motion_type=(existing.get("motion_type") or "").strip(),
        region=normalize_region(existing.get("region")),
        # Without this every class read back from labels.csv would come out as
        # the bootstrap tenant, and since A4 derives the storage directory from
        # this field, tenant B's samples would be written into tenant A's tree —
        # the exact cross-tenant leak the partition exists to prevent. Blank
        # means "written before tenants existed", which `tenant_id_of` resolves
        # to the bootstrap tenant.
        tenant_id=tenant_id_of(existing),
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
    region: str | None = None,
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
    dialect = normalize_dialect(dialect)
    _assert_known_dialect(dialect)

    slug = slugify(label_original, preserve_vn_letters=is_alphabet_dialect(dialect))

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

        # `region=None` (KHÔNG nói ra) khác `region='unclassified'` (nói rõ).
        #
        # Phân biệt này sinh ra từ một hồi quy đã lên sản xuất ngày 15/08/2026.
        # Khi `region` bước vào phép tìm, `unclassified` trở thành một giá trị
        # CỤ THỂ phải khớp — nhưng mọi đường thu mẫu (`upload.py` video và
        # camera, `processing/pipeline.py`) gọi hàm này mà không truyền vùng,
        # nên chúng mặc nhiên đi tìm `region='unclassified'`.
        #
        # Sản xuất có 60/60 nhãn mang `region='nam'`. Phép tìm không khớp cái
        # nào, và hàm đi thẳng xuống nhánh TẠO. Đo được: thu một mẫu cho nhãn
        # `tom` đã tồn tại thì sinh ra lớp `tom` thứ hai với
        # `region='unclassified'`, mẫu rơi vào lớp ma đó. Im lặng, API trả 200,
        # và khoá duy nhất năm cột KHÔNG chặn vì hai vùng là hai lớp hợp lệ.
        #
        # Nên: không nói ra vùng nghĩa là "nhãn nào cũng được, miễn không mơ
        # hồ" — chứ không phải "vùng phải là unclassified".
        region_given = region is not None
        region_key = normalize_region(region)

        cung_nhan = [
            r for r in rows
            if r.get("language") == language_key
            and r.get("dialect") == dialect_key
            and r.get("slug") == slug
        ]
        if region_given:
            # Nói rõ vùng nào thì so khớp CHÍNH XÁC vùng ấy, không nới.
            khop = [r for r in cung_nhan
                    if normalize_region(r.get("region")) == region_key]
        else:
            # Không nói ra vùng: KHÔNG so khớp chính xác trước.
            #
            # Bản đầu vẫn lọc theo `region_key` (= `unclassified` khi bỏ trống)
            # rồi mới xét mơ hồ nếu không khớp gì. Nghe hợp lý và SAI: khi một
            # trong các biến thể tình cờ LÀ `unclassified`, phép lọc khớp ngay
            # và nhánh kiểm mơ hồ không bao giờ chạy — hệ thống lặng lẽ chọn
            # bản `unclassified` thay vì từ chối.
            #
            # Bộ kiểm không bắt được vì nó dựng `bac` + `nam`; smoke sau triển
            # khai 15/08 bắt được, vì nó dựng đúng tổ hợp `nam` + `unclassified`
            # do chính bước trước sinh ra. Bài học: hai biến thể "khác vùng"
            # phải bao gồm cả trường hợp một trong hai là giá trị MẶC ĐỊNH.
            khop = cung_nhan
            if len(cung_nhan) > 1:
                # Fail-closed, và đây đúng là chỗ phải đóng. Từ điển quốc gia có
                # 483 từ mang biến thể miền; khi `ăn|bac` và `ăn|nam` cùng tồn
                # tại thì một yêu cầu chỉ nói "ăn" là MƠ HỒ. Đoán một trong hai
                # là ghi dữ liệu vào lớp sai — hỏng nặng hơn hẳn việc từ chối.
                co_vung = ", ".join(sorted(
                    normalize_region(r.get("region")) for r in cung_nhan))
                raise ValueError(
                    f"Nhãn '{slug}' ({language_key}/{dialect_key}) có nhiều biến "
                    f"thể vùng: {co_vung}. Phải nói rõ vùng nào, hoặc gọi bằng "
                    f"class_uid.")
            # Đúng một biến thể: nhãn đã có, người gọi chỉ không nhắc tới vùng.
            # Trả về lớp đang có thay vì đẻ thêm một bản sao `unclassified`.
            #
            # ĐÂY LÀ ĐƯỜNG TƯƠNG THÍCH CŨ, KHÔNG PHẢI CÁCH CHỌN LỚP.
            # ---------------------------------------------------------------
            # Nhánh này tồn tại để cứu một thế giới mà mỗi nhãn chỉ có ĐÚNG MỘT
            # biến thể đang tồn tại — tức là sản xuất hôm nay, 60 nhãn đều
            # `region='nam'`, và các client cũ gửi lên nhãn dạng chuỗi. Nó
            # KHÔNG phải hợp đồng lâu dài.
            #
            # Cách đúng để gắn mẫu vào một lớp ĐÃ TỒN TẠI là `class_uid`. Ngay
            # khi `ăn|bac` và `ăn|nam` cùng có mặt, `upload("ăn")` PHẢI thất
            # bại — hệ thống không được đoán — và nhánh trên sẽ ném lỗi. Lúc đó
            # đường đi đúng là: giao diện chọn lớp cụ thể → `class_uid` →
            # attach vào đúng lớp ấy. Không phải label + dialect + region rồi
            # tìm lại lớp.
            #
            # Viết dài dòng ở đây vì một lý do cụ thể: nhánh này TIỆN, và cái
            # tiện thì được sao chép. Nếu không nói rõ nó là đường tạm, vài
            # tháng nữa sẽ có API mới dựng quanh nó, và `class_uid` sẽ không
            # bao giờ thành định danh thật ở phía GHI.

        # `region` nằm TRONG phép so ở trên, không đứng ngoài.
        #
        # Thiếu nó thì phép tìm dùng khoá (slug, language, dialect) trong khi cơ
        # sở dữ liệu định danh lớp bằng (…, region) — hai định nghĩa khác nhau
        # về "lớp nào". Hệ quả đo được: tạo `ăn|pho-thong|bac` rồi tạo
        # `ăn|pho-thong|nam` thì lần thứ hai KHÔNG tạo gì cả, nó trả về lớp
        # `bac` — cùng `class_uid`, cùng `region='bac'`. Người dùng tưởng đã có
        # biến thể miền Nam, và mọi mẫu thu sau đó rơi vào lớp miền Bắc.
        #
        # Im lặng hoàn toàn: không lỗi, không cảnh báo, API trả 200 kèm một lớp
        # trông hợp lệ. Với 483 từ có biến thể miền trong từ điển quốc gia, đây
        # là đường nhập QIPEDC gộp sạch chúng lại.
        if khop:
            # Class already exists — return it
            meta = _build_meta_from_row(khop[0])
        else:
            # 2. ALLOCATE — compute next class_idx safely inside lock
            indices = _collect_indices(rows)
            next_idx = (max(indices) + 1) if indices else 1

            class_uid = str(uuid.uuid4())
            short_uid = class_uid[:8]
            folder_name = f"class_{slug}_{short_uid}"

            v2 = vocabulary_defaults_for_dialect(dialect_key)
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
                # Born with its schema-v2 cells filled. Leaving them empty made
                # the class invisible to every profile-filtered split.
                semantic_label=_semantic_label_from_slug(slug),
                vocabulary_scope=v2["vocabulary_scope"],
                recognition_profile=v2["recognition_profile"],
                vocabulary_group=v2["vocabulary_group"],
                motion_type=v2["motion_type"],
                collection_campaign=v2["collection_campaign"],
                # Vùng do người tạo chọn; bỏ trống thì `unclassified` — và đó
                # là một trạng thái CÓ NGHĨA, không phải chỗ trống: "đã vào hệ
                # thống, chưa qua khâu phân loại vùng". Nó cố ý KHÔNG đoán
                # thành một vùng cụ thể, để người phân loại còn thấy mà xử lý.
                region=normalize_region(region),
                # Owner of the new class. Without this every class created
                # through the app would be born under the bootstrap tenant no
                # matter who created it, and the storage partition — which is
                # derived from this field — would never engage.
                tenant_id=ambient_tenant(),
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
    language: Optional[str] = None, dialect: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[ClassMetadata]:
    """Lớp MÀ TENANT NÀY ĐƯỢC THẤY. `tenant_id` bắt buộc — xem `load_labels()`.

    `tenant_id` đứng SAU hai tham số lọc cũ để không đổi thứ tự vị trí của
    caller hiện có; nhưng nó không có mặc định dùng được, nên caller nào quên
    truyền sẽ hỏng ồn ào chứ không lặng lẽ đọc toàn kho.
    """
    rows = load_labels(tenant_id)
    out: List[ClassMetadata] = []
    for r in rows:
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
                hands_required=parse_hands_required(r.get("hands_required")),
                # `region` phải đi theo, không được để rơi về mặc định.
                #
                # Thiếu dòng này thì `list_classes()` trả về `unclassified` cho
                # MỌI lớp, và `/classes/list` — thứ giao diện dựng danh sách từ
                # đó — không phân biệt nổi hai biến thể miền của cùng một từ.
                # Hai dòng `ăn` sẽ hiện ra giống hệt nhau. Với 483 từ có biến
                # thể miền trong từ điển quốc gia, đó là hỏng ngay ở lối vào.
                region=normalize_region(r.get("region")),
                # Same reason as in `_build_meta_from_row`: `hierarchy_path()`
                # is derived from this, so dropping it points every listed class
                # at the bootstrap tenant's directory tree.
                #
                # This is a second, partial copy of `_build_meta_from_row` that
                # has already drifted from it (no folder_override, none of the
                # vocabulary-v2 cells). Collapsing the two is the right fix but
                # changes `folder_name()` for every caller of `list_classes`,
                # which is more than this change should carry — recorded in
                # BACKEND_WORK_PROGRESS.md §9.5 instead of done in passing.
                tenant_id=tenant_id_of(r),
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
    region: str | None = None,
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
    if is_alphabet_dialect(dia):
        assert_single_alphabet_letter(label_original)
    slug = slugify(label_original, preserve_vn_letters=is_alphabet_dialect(dia))

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

    # Scoped to the CALLING tenant's subtree, not to FEATURES_ROOT. Searching
    # the shared root would let tenant B adopt a directory belonging to the
    # bootstrap tenant whenever their slugs collide — and slug collisions are
    # the normal case here, since two deployments collecting Vietnamese sign
    # language will both have a folder for "cam-on".
    tenant_root = ambient_tenant_features_root()
    base_dir = None
    if is_common_global:
        base_dir = tenant_root / "global_common"
    elif is_common_language or dia == "common":
        base_dir = tenant_root / lang / "common"
    elif dia:
        base_dir = tenant_root / lang / dia

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
                region=normalize_region(region),
                # The folder was found under this tenant's own subtree (see
                # `tenant_root` above), so it belongs to this tenant.
                tenant_id=ambient_tenant(),
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
        region=region,
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
