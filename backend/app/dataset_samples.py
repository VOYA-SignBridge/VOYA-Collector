from __future__ import annotations

import os
import csv
import uuid
import tempfile
import logging
import time
from typing import Dict, Any, List
from pathlib import Path
from filelock import FileLock
from datetime import datetime
from app.config import settings
from app.processing.utils import atomic_write_json
from app.tenancy import TENANT_COLUMN, tenant_id_of


DATASET_ROOT = settings.dataset_root
SAMPLES_DIR = DATASET_ROOT
# Canonical catalog file is dataset/samples.csv (repo-root layout, matches the
# historical file and the Drive mirror). A stray dataset/samples/samples.csv
# from an interim layout was merged back on 2026-07-20 and retired
# (renamed *.pre_merge_bak) — do NOT resurrect the subdirectory path.
SAMPLES_CSV = DATASET_ROOT / "samples.csv"

# A machine that still holds a POPULATED dataset/samples/samples.csv is running
# the retired layout, and this module would ignore those rows in silence — which
# is exactly how the 2026-07-20 split-brain went unnoticed until the Drive mirror
# overwrote the full catalog with the partial one. Refusing to boot is too blunt
# (a stale empty file would block a healthy deploy), so shout instead: ERROR is
# loud enough for the deploy check and for Loki.
_LEGACY_SAMPLES_CSV = DATASET_ROOT / "samples" / "samples.csv"


def _warn_if_legacy_catalog_present() -> None:
    try:
        if not _LEGACY_SAMPLES_CSV.exists():
            return
        with _LEGACY_SAMPLES_CSV.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            rows = max(0, sum(1 for _ in csv.reader(fh)) - 1)
        if rows:
            logging.getLogger(__name__).error(
                "[CATALOG] Máy này còn %d dòng ở layout đã bị bỏ (%s). Những dòng đó "
                "KHÔNG được đọc — catalog chuẩn là %s. Gộp chúng rồi đổi tên file cũ "
                "thành *.pre_merge_bak trước khi chạy tiếp "
                "(xem docs/KNOWN_ISSUES.md, mục 2026-07-20).",
                rows, _LEGACY_SAMPLES_CSV, SAMPLES_CSV,
            )
    except Exception:  # pragma: no cover - cảnh báo không bao giờ được làm sập app
        pass


_warn_if_legacy_catalog_present()

SAMPLE_FIELDS = [
    "sample_uid",
    "class_uid",
    "slug",
    "label_original",
    "language",
    "dialect",
    "source_type",
    "user_id",
    "session_id",
    "fps_original",
    "fps_processed",
    "seq_len",
    "augment_id",
    "completeness",
    "file_path",
    "storage_key",
    "storage_url",
    "checksum",
    "created_at",
    "left_hand_ratio",
    "right_hand_ratio",
    "both_hands_ratio",
    "jitter",
    "quality_flags",
    "signer_id",
    "collection_campaign",
    "raw_landmarks_available",
    "normalization_version",
    "preprocess_contract_version",
    "sequence_length_original",
    "quality_status",
    # Owner of the recording, as an account UUID. Appended LAST on purpose: the
    # Google Sheets mirror writes the header verbatim, so a new column at the
    # end shifts nothing that already exists.
    #
    # Why the CSV needs it at all: `user_id` holds a display name, and a name is
    # not an identity (two accounts spelled "Trâm"/"Tram" were the same person;
    # "Trân" was not). Without this column every row imported from another
    # machine's CSV reaches Postgres with auth_user_id NULL, and its contributor
    # then finds an empty personal Trash. See cli/backfill_sample_owners.py.
    "auth_user_id",
    # Which tenant owns this row. Appended LAST for the same Sheets-mirror
    # reason as auth_user_id above.
    #
    # Why the SOT needs it and the Postgres column is not enough: init_db()
    # drops every table and rebuilds them from this file when the schema check
    # fails (see app/db.py). Without the column, that rebuild returns every row
    # as the bootstrap tenant — a silent reassignment of another tenant's whole
    # corpus, undetectable afterwards because the CSV never held the evidence.
    TENANT_COLUMN,
]


#: Values that mean "each hand was moved onto its own wrist and rescaled".
COORD_SPACE_WRIST_CENTRED = {
    # Written by upload.py (camera): each hand moved onto its own wrist and its
    # x,y divided by its own span. z untouched. This is the MODEL's input.
    "wrist_centred_v1",
    # Historic spelling of the same thing. Kept only for reading old samples —
    # never write it again. It collides with MediaPipe's own vocabulary, where
    # "normalized landmarks" means image coordinates in [0,1], i.e. the exact
    # opposite of what this value denotes here.
    "mediapipe_normalized",
}

#: Raw MediaPipe image coordinates: x,y in [0,1] of the frame, z a relative
#: depth regressed against the wrist. The hands hold their true positions.
COORD_SPACE_IMAGE = "mediapipe_image"


def coordinate_space_of(meta: dict, sequence=None) -> str:
    """Which coordinate convention a stored `sequence` is in.

    Metadata is authoritative when present. It is stamped by the WRITER, so it
    describes the array actually in the archive rather than what a caller
    intended.

    Legacy samples predate the field entirely (measured: 1874 of 3871 files),
    and for those the convention has to be recovered from the numbers. The test
    is exact rather than statistical: wrist-centring puts landmark 0 at the
    origin BY CONSTRUCTION, so every live hand in a wrist-centred sample has
    |wrist| == 0 to float precision. No threshold tuning is involved.
    """
    declared = str((meta or {}).get("coordinate_space") or "").strip()
    if declared in COORD_SPACE_WRIST_CENTRED:
        return "wrist_centred_v1"
    if declared == COORD_SPACE_IMAGE:
        return COORD_SPACE_IMAGE
    if sequence is None:
        return "unknown"

    import numpy as np

    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 2 or seq.shape[1] != 126:
        return "unknown"
    hands = seq.reshape(len(seq), 2, 21, 3)
    saw_hand = False
    for h in range(2):
        block = hands[:, h]
        live = np.any(block.reshape(len(block), -1) != 0.0, axis=1)
        if not live.any():
            continue
        saw_hand = True
        if float(np.abs(block[live][:, 0, :2]).max()) > 1e-4:
            return COORD_SPACE_IMAGE
    return "wrist_centred_v1" if saw_hand else "unknown"


def _atomic_write_npz(path: Path, arrays: dict) -> None:
    """Write a compressed npz that a reader can only ever see whole.

    fsync before the rename, so the rename cannot be ordered ahead of the data
    it publishes. Without it a crash can leave a correctly-named file holding
    nothing — worse than a missing one, because every reader treats presence as
    proof.
    """
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="npztmp_", suffix=".npz", dir=str(path.parent))
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, **arrays)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def raw_archive_path(npz_path) -> Path:
    """Where a sample's untouched recording lives, given its features path.

    The two archives mirror each other exactly — same class hierarchy, same
    file name — so one is derivable from the other and no index has to be kept
    in step:

        dataset/features/vn/common/class_xxx/sample_ab12.npz   model input
        dataset/raw/vn/common/class_xxx/sample_ab12.npz        the recording

    Splitting them is not tidiness. `sequence` is reproducible from the raw
    landmarks by re-running the normalizer; the raw landmarks are reproducible
    from nothing. Keeping the irreplaceable half in its own tree means a change
    to how we normalize is a re-run over an archive we already hold, rather
    than a new collection campaign — which is what makes the known z bug in
    normalize_single_hand a fixable defect instead of a permanent one.

    It also takes the raw and world arrays out of the file the training loader
    opens for every sample of every epoch: measured, they are 33% of a v2 npz.
    """
    p = Path(npz_path).resolve()
    parts = list(p.parts)
    # Rightmost "features" wins: a deployment can sit under any prefix, and only
    # the dataset-relative segment is ours to rewrite.
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "features":
            parts[i] = "raw"
            return Path(*parts)
    return p.parent / "raw" / p.name


def load_world_sequence(npz_path):
    """The metric 3D array written at capture time, or None.

    MediaPipe emits two landmark sets per hand and only one of them is 3D in
    any real sense. `landmarks` (what `sequence` and `landmarks_raw` are built
    from) is 2.5D: x,y are image coordinates and z is a relative depth the
    model regresses, documented as "roughly the same scale as x" and carrying
    no metric meaning. `world_landmarks` is true 3D in metres with the origin
    at the hand's geometric centre.

    Measured on this corpus, image-space depth spans only ~0.20 of a hand's own
    width per frame (p50 over 18046 frames), which is why hands render like
    cardboard however carefully they are drawn. That ceiling belongs to the
    data, not the renderer, and `landmarks_world` is the only thing that lifts
    it.

    Only samples recorded after this contract landed have the key; nothing is
    synthesized for the ones that do not, because it cannot be.
    """
    world = _read_archived_array(npz_path, "landmarks_world")
    if world is None or world.ndim != 2 or world.shape[1] != 126:
        return None
    import numpy as np

    return world if np.any(world != 0.0) else None


def _read_archived_array(npz_path, key: str):
    """Read `key` from the features npz, falling back to the raw archive.

    Two layouts are live at once and both are correct for their era. Samples
    written before the archive split carry landmarks_raw / landmarks_world
    inline; samples written after it keep them in dataset/raw/. Nothing
    migrates the old ones, because rewriting 1997 archived recordings to move a
    key is a risk taken for no gain — so readers accept both, and the inline
    copy wins when present since that is the file the caller already named.
    """
    import numpy as np

    try:
        with np.load(npz_path, allow_pickle=True) as data:
            if key in data:
                return np.asarray(data[key], dtype=np.float32)
    except Exception:
        return None

    archived = raw_archive_path(npz_path)
    if not archived.is_file():
        return None
    try:
        with np.load(archived, allow_pickle=True) as data:
            if key not in data:
                return None
            return np.asarray(data[key], dtype=np.float32)
    except Exception:
        return None


def load_display_sequence(npz_path) -> tuple:
    """(sequence, source) for anything that SHOWS a sample to a human.

    Prefers `landmarks_raw` over `sequence`, because `sequence` is the model's
    input, not a picture of what was recorded. `normalize_single_hand` subtracts
    each hand's own wrist and divides x,y by that hand's span — but leaves z
    alone. Two things are lost:

      * where the hands were relative to each other. Both wrists land on the
        origin, so a recording where the hands nearly touch and one where they
        are far apart become identical. Measured: wrist distance is exactly
        0.0000 in `sequence` and 0.026-0.343 in `landmarks_raw`.

      * the depth proportion. x and y get multiplied by ~6 while z does not, so
        z/xy collapses from ~0.23 to ~0.04 and the hand renders flat.

    Neither can be recovered from `sequence`, and neither is invented here: 53%
    of stored samples carry `landmarks_raw` and simply were not being read. The
    rest fall back to `sequence`, and the caller is told which it got so the UI
    can say so rather than quietly showing a flattened hand as if it were real.

    Not every sample needs the fallback to be a compromise. The video and npz
    import paths never normalized at all, so their `sequence` IS raw image
    coordinates — 440 files measured. Reporting those as "normalized" put a
    warning banner on the one group whose geometry was never damaged, so the
    convention is read rather than assumed. See coordinate_space_of.

    Training is untouched — it reads `sequence` through its own loader.
    """
    import numpy as np

    with np.load(npz_path, allow_pickle=True) as data:
        legacy = np.asarray(data["sequence"], dtype=np.float32)
        meta = data["meta"].item() if "meta" in data else {}

    raw = _read_archived_array(npz_path, "landmarks_raw")
    if raw is not None:
        # The contract allows raw to keep its original frame count; only use it
        # when it lines up, rather than resampling behind the scenes.
        if raw.ndim == 2 and raw.shape == legacy.shape and np.any(raw != 0.0):
            return raw, "raw"

    if coordinate_space_of(meta, legacy) == COORD_SPACE_IMAGE:
        return legacy, "raw"
    return legacy, "normalized"


def now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _samples_fieldnames() -> List[str]:
    """Return samples.csv's ACTUAL header.

    The on-disk schema drifted wider than SAMPLE_FIELDS (extra DB-mirror columns
    like username/session_uid/status/updated_at/deleted_at). Writers MUST respect
    the real header, otherwise rows misalign against the header and
    csv.DictWriter raises "dict contains fields not in fieldnames". Falls back to
    SAMPLE_FIELDS when the file does not exist yet.
    """
    try:
        if SAMPLES_CSV.exists():
            with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), None)
            if header:
                return header
    except Exception:
        pass
    return list(SAMPLE_FIELDS)


def ensure_samples_column(column: str, fill: str = "") -> bool:
    """Append `column` to samples.csv's header if absent. Idempotent.

    Rewrites the file through a temp file + os.replace so a crash mid-migration
    leaves the original catalog intact — this file is the source of truth and a
    truncated copy is not recoverable from Postgres (which mirrors it, not the
    other way round).

    Appending at the END matters: the Google Sheets mirror emits the header
    verbatim as row 1, so a column inserted in the middle would shift every
    existing Sheets column one place to the right.

    `fill` is the value written into the new cell of every EXISTING row, and it
    exists because the two migrations that use this function need opposite
    answers:

      * ``auth_user_id`` fills with ``""`` — the owner of a historical row is
        genuinely unknown, and writing a guess would manufacture attribution.
      * ``tenant_id`` fills with the bootstrap tenant — every historical row
        provably belongs to it, the DB column is NOT NULL, and an empty cell
        would round-trip as "no opinion" and leave the row unassigned.

    Returns True if the file was modified.
    """
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        with open(SAMPLES_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header or column in header:
                return False
            new_header = [*header, column]
            tmp_path = str(SAMPLES_CSV) + ".tmp"
            try:
                with open(tmp_path, "w", newline="", encoding="utf-8") as out:
                    writer = csv.writer(out)
                    writer.writerow(new_header)
                    added = [fill] * (len(new_header) - len(header))
                    for line_no, row in enumerate(reader, start=2):
                        # A row with MORE cells than the header cannot be
                        # migrated: appending the new value after the surplus
                        # would place it under no column at all and shift how
                        # every reader sees that row. Refuse rather than write a
                        # misaligned source of truth — db.py catches this and
                        # logs, so boot continues with the catalog untouched.
                        if len(row) > len(header):
                            raise ValueError(
                                f"samples.csv line {line_no} has {len(row)} cells but "
                                f"the header has {len(header)}; refusing to add "
                                f"'{column}' to a misaligned catalog"
                            )
                        # Pad short rows with "" — a ragged legacy row would
                        # otherwise land `fill` under someone else's column. The
                        # padding and the new cell are different things and must
                        # not share a value.
                        writer.writerow([*row, *[""] * (len(header) - len(row)), *added])
                    out.flush()
                    os.fsync(out.fileno())
            except Exception:
                # Leave no half-written temp file behind for the next run to
                # trip over; the original is still untouched at this point.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        os.replace(tmp_path, SAMPLES_CSV)
    logging.getLogger(__name__).info(
        "[CATALOG] samples.csv: đã thêm cột '%s' (dòng cũ điền %r)", column, fill
    )
    return True


def _ensure_samples_file():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLES_CSV.exists():
        lock = FileLock(str(SAMPLES_CSV) + ".lock")
        with lock:
            if not SAMPLES_CSV.exists():
                with open(SAMPLES_CSV, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS)
                    writer.writeheader()
    else:
        pass


def append_sample_row(row: Dict[str, Any]):
    # Stamp the owning tenant before anything touches the file. csv.DictWriter
    # is configured with restval="", so a row dict that simply omits the key
    # would be written as an EMPTY cell rather than defaulting — a new sample
    # belonging to nobody, in the source of truth, with no error raised.
    # Copied rather than mutated: callers pass dicts they still use afterwards.
    row = {**row, TENANT_COLUMN: tenant_id_of(row)}
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        file_exists = SAMPLES_CSV.exists() and os.path.getsize(SAMPLES_CSV) > 0
        # Match the real on-disk header (may be wider than SAMPLE_FIELDS);
        # extrasaction="ignore" drops keys the header lacks (e.g. session_id),
        # restval="" fills header columns the row dict doesn't provide.
        fieldnames = _samples_fieldnames() if file_exists else list(SAMPLE_FIELDS)
        with open(SAMPLES_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    from app.storage.catalog_mirror import mirror_samples_to_gdrive_and_sheets

    mirror_samples_to_gdrive_and_sheets(SAMPLES_CSV)


def list_samples() -> List[Dict[str, str]]:
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def update_sample_row(sample_uid: str, updates: Dict[str, Any]):
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                rows = list(reader)

            updated = False
            for row in rows:
                if row.get("sample_uid") == sample_uid:
                    for k, v in updates.items():
                        if k in row:
                            row[k] = v
                    updated = True
                    break

            if updated:
                tmp_path = str(SAMPLES_CSV) + ".tmp"
                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, SAMPLES_CSV)
        except Exception as e:
            logging.getLogger(__name__).error("[UPDATE_SAMPLE_ROW] failed: %s", e)


def update_sample_rows_bulk(updates: Dict[str, Dict[str, Any]]):
    """Apply updates to many sample rows in ONE read+write of samples.csv.

    updates: {sample_uid: {field: value, ...}, ...}

    Replaces N calls to update_sample_row() (each of which rewrote the WHOLE
    file under a lock — O(N^2) for a video that produces hundreds of npz).
    Only fields present in SAMPLE_FIELDS are applied.
    """
    if not updates:
        return
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                rows = list(reader)

            changed = False
            for row in rows:
                upd = updates.get(row.get("sample_uid", ""))
                if upd:
                    for k, v in upd.items():
                        if k in fieldnames:
                            row[k] = v
                    changed = True

            if changed:
                tmp_path = str(SAMPLES_CSV) + ".tmp"
                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, SAMPLES_CSV)
        except Exception as e:
            logging.getLogger(__name__).error("[UPDATE_SAMPLE_ROWS_BULK] failed: %s", e)


def count_samples_for_class(class_uid: str) -> int:
    """Return number of samples for a class_uid based on samples.csv.

    This is the source of truth for enforcing a global per-class cap (e.g. MAX_SAMPLES_PER_CLASS).
    """
    if not class_uid:
        return 0
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                return sum(
                    1 for row in csv.DictReader(f) if row.get("class_uid") == class_uid
                )
        except FileNotFoundError:
            return 0


def save_sequence_npz(
    class_meta, sequence, meta: Dict[str, Any], augment_id: int, source_type: str,
    upload_collector: "list | None" = None,
    raw_sequence=None,
    world_sequence=None,
    coordinate_space: str = "",
    frame_valid_mask=None,
    left_hand_valid_mask=None,
    right_hand_valid_mask=None,
) -> str:
    """Save a (T,D) sequence locally first, then mirror to Google Drive when enabled.

    Returns the local file path. If Drive upload succeeds, the Drive URL is also stored
    in the sample metadata, but the local NPZ remains the canonical on-disk artifact.

    upload_collector: when provided (a list), the Drive upload is NOT dispatched
    per-file. Instead the upload descriptor is appended to this list so the caller
    (e.g. the video pipeline generating hundreds of npz) can dispatch ONE batch
    task — avoiding one Celery task + one GDrive session per file. When None
    (default, e.g. camera capture = 1 file), a single upload task is dispatched
    immediately as before.

    Preprocess contract v2 (optional, backward compatible): when raw_sequence
    and the masks are provided, the npz additionally stores
      landmarks_raw          float32 [T_original, 126]  (BEFORE wrist centering/scaling)
      landmarks_normalized   float32 [60, 126]          (same array as legacy 'sequence')
      frame_valid_mask       bool    [60]
      left_hand_valid_mask   bool    [60]
      right_hand_valid_mask  bool    [60]
    The legacy 'sequence' key is ALWAYS written so existing loaders
    (dataset_loader.py feature_key_priority) keep working unchanged. Legacy
    samples without raw landmarks are marked raw_landmarks_available=false —
    raw data is never synthesized from normalized data.

    world_sequence (optional) stores MediaPipe's `world_landmarks` as
      landmarks_world       float32 [T_original, 126]  metres, hand-centred
    This is the only metrically-3D array MediaPipe produces; `sequence` and
    `landmarks_raw` both carry the 2.5D image-space z instead, whose depth is a
    relative regression. Viewers use it for depth; the model does not see it.

    coordinate_space names the convention of `sequence` itself and is written
    into the metadata by the WRITER. Callers that normalize pass
    "wrist_centred_v1"; callers that store MediaPipe image coordinates verbatim
    pass COORD_SPACE_IMAGE. Getting this wrong is not cosmetic — a viewer that
    believes image-space data is wrist-centred lays the two hands out in
    separate columns and invents a gap the signer never made.
    """
    import numpy as np

    log = logging.getLogger(__name__)

    sample_uid = uuid.uuid4().hex[:10]
    created_at = (meta or {}).get("created_at") or now_str()
    fname = f"sample_{sample_uid}.npz"

    metadata = {
        "class_uid": class_meta.class_uid,
        "slug": class_meta.slug,
        "label_original": class_meta.label_original,
        "language": class_meta.language,
        "dialect": class_meta.dialect,
        "augment_id": augment_id,
        "created_at": created_at,
        **meta,
    }

    class_dir = class_meta.hierarchy_path()
    class_dir.mkdir(parents=True, exist_ok=True)
    fpath = class_dir / fname
    sidecar = class_dir / f"sample_{sample_uid}.json"

    # Preprocess contract v2: raw + masks alongside the legacy 'sequence' key.
    raw_available = raw_sequence is not None
    world_available = world_sequence is not None
    metadata.setdefault("raw_landmarks_available", bool(raw_available))
    metadata["world_landmarks_available"] = bool(world_available)
    # Overwrite rather than setdefault: what the array IS is a property of this
    # write, not a hint the caller may leave stale in a copied meta dict. The
    # video pipeline reuses one window_meta across every augmented variant.
    #
    # Derived when the caller stays silent, so a save site added later cannot
    # produce another 440 unlabelled files. The derivation is exact, not a
    # guess: wrist-centring pins landmark 0 at the origin by construction. It
    # only declines on a sequence with no hand at all, and nothing is stamped
    # then.
    resolved_space = coordinate_space or coordinate_space_of(metadata, sequence)
    if resolved_space and resolved_space != "unknown":
        metadata["coordinate_space"] = resolved_space
    # Stamped by the WRITER (not the caller) so it always describes what was
    # actually put in the archive. scripts/validate_pilot_samples.py gates new
    # campaigns on this; the checkpoint contract records the same token.
    # v3 = the recording lives in its own archive rather than inline. The token
    # changes because readers must know where to look, not because the contract
    # got stricter: v2 and v3 carry the same guarantees.
    metadata.setdefault(
        "storage_contract_version",
        "npz_v3_split_raw" if raw_available else "npz_v1_legacy",
    )
    # ------------------------------------------------------------------
    # The recording goes to disk FIRST, in its own archive, before anything
    # derived from it exists.
    #
    # The two halves are not equally replaceable. `sequence` can be rebuilt
    # from the raw landmarks at any time by re-running the normalizer; the raw
    # landmarks can be rebuilt from nothing at all — the signer would have to
    # come back and sign it again. So the ordering is chosen for the failure
    # that survives: a crash between the two writes leaves a raw recording with
    # no sample row, which a later pass can normalize and register. The reverse
    # order would lose the take.
    #
    # It is also what makes the pipeline re-runnable. normalize_single_hand
    # scales x and y by the hand span but leaves z alone, which is a real
    # defect; with the recordings archived, fixing it is a re-run over data we
    # already hold instead of a new collection campaign.
    # ------------------------------------------------------------------
    if raw_available or world_available:
        raw_arrays: Dict[str, Any] = {"meta": metadata}
        if raw_available:
            raw_arrays["landmarks_raw"] = np.asarray(raw_sequence, dtype=np.float32)
        if world_available:
            raw_arrays["landmarks_world"] = np.asarray(world_sequence, dtype=np.float32)
        try:
            _atomic_write_npz(raw_archive_path(fpath), raw_arrays)
        except Exception as e:
            # Loud, and it stops the write. Continuing would produce a sample
            # whose recording was silently dropped — the exact loss this
            # ordering exists to prevent.
            log.error("[RAW][ERROR] raw archive write failed for %s: %s", fname, e)
            raise

    npz_arrays: Dict[str, Any] = {
        "sequence": sequence.astype("float32"),          # legacy key (loaders)
        "landmarks_normalized": sequence.astype("float32"),
        "meta": metadata,
    }
    if frame_valid_mask is not None:
        npz_arrays["frame_valid_mask"] = np.asarray(frame_valid_mask, dtype=bool)
    if left_hand_valid_mask is not None:
        npz_arrays["left_hand_valid_mask"] = np.asarray(left_hand_valid_mask, dtype=bool)
    if right_hand_valid_mask is not None:
        npz_arrays["right_hand_valid_mask"] = np.asarray(right_hand_valid_mask, dtype=bool)

    _atomic_write_npz(fpath, npz_arrays)

    try:
        metadata["storage_provider"] = "local"
        atomic_write_json(sidecar, metadata, indent=2)
    except Exception as e:
        logging.getLogger(__name__).warning("[SIDECAR] write failed: %s", e)

    storage_url = None
    storage_key = None
    # Dispatched only AFTER the samples.csv + Postgres rows exist — see the tail
    # of this function. Dispatching here would race the row it needs to update.
    pending_single_upload = None
    use_google_drive = settings.use_google_drive

    if use_google_drive:
        folder_name = class_meta.folder_name()
        storage_key = f"features/{class_meta.language}/{class_meta.dialect}/{folder_name}/{fname}"
        upload_item = {
            "sample_uid": sample_uid,
            "local_path": str(fpath),
            "storage_key": storage_key,
            "sidecar_path": str(sidecar),
        }
        if upload_collector is not None:
            # Batch mode: caller dispatches ONE task for all collected items,
            # after it has finished writing every row.
            upload_collector.append(upload_item)
        else:
            # Single mode (e.g. camera): hold it until the rows are written. The
            # task writes storage_url back onto the sample, so dispatching here
            # let the worker look for a row that did not exist yet — the cause of
            # "row in Postgres, missing from samples.csv, storage_url never set".
            pending_single_upload = upload_item
    else:
        log.info("[SAVE_SEQUENCE] Google Drive not enabled; keeping local copy only")

    result_path = str(fpath)

    # Append sample record
    try:
        expected_T = int(getattr(settings, "seq_len", 60))
        expected_D = int(getattr(settings, "feature_dim", 126))
        if int(sequence.shape[0]) != expected_T or int(sequence.shape[1]) != expected_D:
            logging.getLogger(__name__).warning(
                "[SHAPE] unexpected sequence shape=%s (expected=%sx%s)",
                tuple(sequence.shape),
                expected_T,
                expected_D,
            )
    except Exception:
        pass

    # Compute relative path for storage (portable across machines)
    try:
        relative_path = str(Path(result_path).relative_to(DATASET_ROOT))
    except ValueError:
        relative_path = result_path  # fallback: keep absolute if outside DATASET_ROOT

    append_sample_row(
        {
            "sample_uid": sample_uid,
            "class_uid": class_meta.class_uid,
            "slug": class_meta.slug,
            "label_original": class_meta.label_original,
            "language": class_meta.language,
            "dialect": class_meta.dialect,
            "source_type": source_type,
            "user_id": meta.get("user_id") or meta.get("user", ""),
            "session_id": meta.get("session_id", ""),
            "fps_original": meta.get("fps_original", meta.get("fps", "")),
            "fps_processed": meta.get("fps_processed", meta.get("fps", "")),
            "seq_len": str(sequence.shape[0]),
            "augment_id": str(augment_id),
            "completeness": str(meta.get("completeness", "")),
            "file_path": relative_path,
            # storage_url is always None here (Drive upload is deferred to Celery),
            # so the old `if storage_url` guard dropped the key entirely. Persist the
            # computed storage_key immediately; the async task fills storage_url later.
            "storage_key": storage_key or "",
            "storage_url": storage_url or "",
            "checksum": metadata.get("checksum", ""),
            "created_at": created_at,
            "left_hand_ratio": str(meta.get("left_hand_ratio", "")),
            "right_hand_ratio": str(meta.get("right_hand_ratio", "")),
            "both_hands_ratio": str(meta.get("both_hands_ratio", "")),
            "jitter": str(meta.get("jitter", "")),
            "quality_flags": str(meta.get("quality_flags", "") or ""),
            "signer_id": str(meta.get("signer_id", "") or ""),
            "collection_campaign": str(meta.get("collection_campaign", "") or ""),
            "raw_landmarks_available": "1" if metadata.get("raw_landmarks_available") else "0",
            "normalization_version": str(meta.get("normalization_version", "") or ""),
            "preprocess_contract_version": str(meta.get("preprocess_contract_version", "") or ""),
            "sequence_length_original": str(meta.get("sequence_length_original", "") or ""),
            "quality_status": str(meta.get("quality_status", "") or ""),
            "auth_user_id": str(meta.get("auth_user_id", "") or ""),
        }
    )

    # Also persist metadata to Postgres if configured
    try:
        from app.storage.metadata_db import insert_sample

        db_row = {
            "sample_uid": sample_uid,
            "class_uid": class_meta.class_uid,
            "slug": class_meta.slug,
            "label_original": class_meta.label_original,
            "language": class_meta.language,
            "dialect": class_meta.dialect,
            "source_type": source_type,
            "user_id": meta.get("user_id") or meta.get("user", ""),
            "auth_user_id": meta.get("auth_user_id") or None,
            "session_id": meta.get("session_id", ""),
            "fps_original": meta.get("fps_original", meta.get("fps", "")),
            "fps_processed": meta.get("fps_processed", meta.get("fps", "")),
            "seq_len": int(sequence.shape[0]),
            "augment_id": int(augment_id),
            "completeness": float(meta.get("completeness") or 0.0),
            "file_path": relative_path,
            "storage_url": metadata.get("storage_url", ""),
            "checksum": metadata.get("checksum", ""),
            "created_at": created_at,
            "gdrive_synced": not use_google_drive,
            "left_hand_ratio": meta.get("left_hand_ratio"),
            "right_hand_ratio": meta.get("right_hand_ratio"),
            "both_hands_ratio": meta.get("both_hands_ratio"),
            "jitter": meta.get("jitter"),
            "quality_flags": meta.get("quality_flags") or None,
            "signer_id": meta.get("signer_id"),
            "collection_campaign": meta.get("collection_campaign"),
            "raw_landmarks_available": metadata.get("raw_landmarks_available"),
            "normalization_version": meta.get("normalization_version"),
            "preprocess_contract_version": meta.get("preprocess_contract_version"),
            "sequence_length_original": meta.get("sequence_length_original"),
            "quality_status": meta.get("quality_status"),
        }
        insert_sample(db_row)
    except Exception as e:
        # Previously logged only in debug mode — a sample could land in
        # samples.csv but never in Postgres and go unnoticed. Always warn.
        logging.getLogger(__name__).warning("[DB] insert_sample failed for %s: %s", sample_uid, e)

    # The row now exists in samples.csv + Postgres, so the single-file Drive
    # upload can safely run: its storage_url write-back will find the sample.
    if pending_single_upload is not None:
        try:
            from app.export_tasks import upload_npz_to_gdrive_task

            upload_npz_to_gdrive_task.delay(**pending_single_upload)
            log.info(
                "[SAVE_SEQUENCE] Google Drive upload deferred to Celery for key: %s",
                pending_single_upload["storage_key"],
            )
        except Exception as e:
            log.warning("[SAVE_SEQUENCE] Failed to dispatch Celery upload task: %s", e)

    return result_path


def _db_row_to_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Project a Postgres samples row onto the samples.csv schema.

    `storage_key` is not a DB column but equals the relative file_path
    (features/<lang>/<dialect>/<folder>/sample_x.npz), so it is derived. Every
    other field is copied by name when the DB has it and left empty when it does
    not — which keeps this working while the vocabulary-v2 columns roll out to
    machines still on the 19-column schema.
    """
    fp = row.get("file_path") or ""
    out = {name: "" for name in SAMPLE_FIELDS}
    for name in SAMPLE_FIELDS:
        value = row.get(name)
        if value is not None:
            out[name] = str(value)
    out["file_path"] = fp
    out["storage_key"] = fp
    # Belt and braces against the SELECT drifting: this projection writes "" for
    # any column the query did not return, and an empty tenant cell in the
    # source of truth is exactly the state A1 exists to make impossible. Forcing
    # it here means a future edit to list_active_samples() cannot silently
    # reintroduce the hole.
    out[TENANT_COLUMN] = tenant_id_of(out)
    return out


def reconcile_samples_csv_from_db() -> int:
    """Heal samples.csv by appending any ACTIVE Postgres sample missing from it.

    Postgres is authoritative here, so a row can only be *lost* from the CSV (the
    rare append-vs-catalog-rewrite race), never the reverse — hence APPEND-ONLY
    and idempotent. Returns the number of rows restored.

    MUST run under _catalog_lock, the same lock every catalog mutation holds. A
    soft delete removes the row from samples.csv and THEN sets deleted_at in the
    DB; a reconcile reading "DB active" inside that gap would resurrect the
    just-trashed sample. Taking the catalog lock — and reading the DB only after
    acquiring it — makes reconcile see a settled state. Same acquire order as
    catalog ops (catalog lock, then the samples file lock) → no deadlock.
    """
    _ensure_samples_file()

    from filelock import Timeout
    from app.catalog_sync import _catalog_lock

    try:
        # Skip this run (not fail) if a catalog op is busy — the beat retries soon.
        with _catalog_lock().acquire(timeout=30):
            try:
                from app.storage.metadata_db import list_active_samples

                db_rows = list_active_samples()
            except Exception as e:
                logging.getLogger(__name__).warning("[RECONCILE] DB read failed: %s", e)
                return 0
            if not db_rows:
                return 0

            lock = FileLock(str(SAMPLES_CSV) + ".lock")
            with lock:
                with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                    existing = {(row.get("sample_uid") or "").strip() for row in reader}

                missing = [r for r in db_rows if (r.get("sample_uid") or "") not in existing]
                if not missing:
                    return 0

                with open(SAMPLES_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames,
                                            extrasaction="ignore", restval="")
                    for r in missing:
                        writer.writerow(_db_row_to_csv_row(r))
                    f.flush()
                    os.fsync(f.fileno())

            logging.getLogger(__name__).warning(
                "[RECONCILE] restored %d sample row(s) from DB into samples.csv", len(missing)
            )
            return len(missing)
    except Timeout:
        logging.getLogger(__name__).info("[RECONCILE] skipped: catalog busy")
        return 0
