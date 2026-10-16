"""Create an immutable, versioned dataset manifest.

Usage:
    python scripts/create_dataset_manifest.py --version isds2026_v1
    python scripts/create_dataset_manifest.py --version test_v1 \
        --features-root dataset/features --labels-csv dataset/labels.csv \
        --signers-csv dataset/signers.csv --out-dir dataset/manifests

Outputs (in --out-dir):
    dataset_manifest_<version>.csv    one row per .npz sample
    labels_<version>.csv              frozen copy of the label table
    signers_<version>.csv             frozen copy of the signer registry
    dataset_stats_<version>.json      counts by scope/profile/signer/class
    dataset_manifest_<version>.sha256 checksum of the manifest file itself

Rules:
  - a released manifest is IMMUTABLE: this script refuses to overwrite an
    existing version unless --force is passed (use a NEW version instead);
  - file checksums are sha256 of the npz bytes;
  - raw_landmarks_available is read from the npz keys (never guessed);
  - signer_id is resolved from the legacy name mapping when the sidecar/meta
    has no signer_id yet; unresolvable rows keep signer_id="" and are counted.

Requires numpy (to inspect npz keys); otherwise stdlib only.
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
# `backend/` cũng vào đường nhập khẩu: cổng đồng thuận sống ở `app.consent_gate`
# và script này phải dùng CHÍNH nó, không được chép lại quy tắc. Bản sao thứ hai
# của một quy tắc đạo đức là bản sẽ trôi đi.
sys.path.insert(0, str(REPO_ROOT / "backend"))

from processed.shared.vocabulary import (  # noqa: E402
    label_key_v2,
    semantic_label_from_slug,
    validate_label_v2,
)

MANIFEST_FIELDS = [
    "sample_id", "file_path", "file_checksum",
    "label_key", "semantic_label", "vocabulary_scope", "recognition_profile",
    "vocabulary_group", "collection_campaign", "motion_type",
    "signer_id", "session_id", "source_type",
    "raw_landmarks_available", "normalization_version", "quality_status",
    # physical-location columns kept so the existing dataset_loader keeps working
    "class_uid", "slug", "label_original", "language", "dialect", "folder_name", "file",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_sidecar(npz_path: Path) -> dict:
    sidecar = npz_path.with_suffix(".json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def _signer_name(*candidates) -> str:
    """First candidate that is a signer NAME, skipping account UUIDs.

    A sidecar's `user_id` holds either the signer's name or the id of the
    account that recorded them — the two meanings were never separated. Reading
    it blindly made 15 alphabet samples unresolvable: their sidecar carries
    `user_id: "eeeaeb8b-…"` (the account) alongside `user: "Minh"` (the person),
    and the UUID won, so the legacy name mapping had nothing to match. Those
    samples then blocked strict signer-disjoint splitting entirely.

    A UUID is never a name, so skipping UUID-shaped values loses nothing and
    lets the real name behind it through.
    """
    for c in candidates:
        s = str(c or "").strip()
        if s and not _UUID_RE.fullmatch(s):
            return s
    return ""


def _raw_archive_path(npz_path: Path) -> Path:
    """dataset/features/<...>/x.npz -> dataset/raw/<...>/x.npz

    See app.dataset_samples.raw_archive_path, which is the definition.
    """
    parts = list(npz_path.resolve().parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "features":
            parts[i] = "raw"
            return Path(*parts)
    return npz_path.parent / "raw" / npz_path.name


def _npz_flags(npz_path: Path) -> dict:
    try:
        with np.load(npz_path, allow_pickle=True) as z:
            keys = set(z.keys())
        # Contract v3 moved the recording out of the file the training loader
        # opens, so presence has to be checked in both places. Reading only the
        # features npz would mark every newly collected sample as having no raw
        # landmarks and quietly disqualify it from research use.
        archived = _raw_archive_path(npz_path)
        if archived.is_file():
            try:
                with np.load(archived, allow_pickle=True) as rz:
                    keys |= set(rz.keys())
            except Exception:
                pass
        # `world` tracks the rollout of MediaPipe's metric landmarks. It is a
        # DISPLAY array — no model reads it — so it must never gate research
        # validity the way `raw` does; it is reported so the share of the corpus
        # with true 3D is a number rather than a guess.
        return {
            "readable": True,
            "raw": "landmarks_raw" in keys,
            "world": "landmarks_world" in keys,
        }
    except Exception:
        return {"readable": False, "raw": False, "world": False}


def build_legacy_user_index(sources) -> dict:
    """sample_id -> legacy user_id name, from frozen split CSVs / samples.csv.

    Many pre-sidecar npz files have no per-sample JSON; the frozen legacy split
    CSVs are the only surviving record of who signed them. This is recorded
    provenance (not inference) — rows absent everywhere stay unresolved.
    """
    index: dict = {}
    for src in sources:
        src = Path(src)
        if not src.exists():
            continue
        for r in _read_csv(src):
            sid = (r.get("sample_id") or r.get("sample_uid") or "").strip()
            name = (r.get("user_id") or "").strip()
            if sid and name and sid not in index:
                index[sid] = name
    return index


def build_sample_class_index(sources) -> dict:
    """sample_id -> class_uid, from samples.csv / frozen split CSVs.

    Needed because a .npz keeps living in the folder of the class it was
    recorded under, even after the row is repointed elsewhere. Merging the
    duplicate `q` class left 5 files in class_q_795eec29/ while their rows moved
    to class_q_356d0732 — folder-name lookup found nothing and the manifest
    silently dropped all five.

    Augmented rows (augment_id > 0) are deliberately NOT indexed: an augmented
    copy must never become an independent manifest row, or the copy can land in
    val/test while its original is in train.
    """
    index: dict = {}
    for src in sources:
        src = Path(src)
        if not src.exists():
            continue
        for r in _read_csv(src):
            if str(r.get("augment_id") or "0").strip() not in ("", "0"):
                continue
            sid = (r.get("sample_id") or r.get("sample_uid") or "").strip()
            cuid = (r.get("class_uid") or "").strip()
            if sid and cuid and sid not in index:
                index[sid] = cuid
    return index


def load_unapproved_ids(sources) -> dict:
    """sample_id -> lý do, cho mọi mẫu CHƯA qua kiểm duyệt.

    Trả về đúng hình dạng của `load_excluded_ids` để gộp thẳng vào cùng một cơ
    chế: một manifest là **bản công bố**, và loại ở tầng manifest giữ được mọi
    split đã phát hành trước đó vẫn chạy — cùng lý lẽ đã ghi cho tệp quyết định.

    Vì sao không lọc bằng `moderation.filter_rows` trên chính `rows`
    -----------------------------------------------------------------
    `build_manifest` dựng dòng từ cây `.npz` chứ không từ `samples.csv`, nên
    dòng nó tạo ra KHÔNG mang `review_status`. Cổng đọc sự im lặng thành "chưa
    duyệt" (đúng theo thiết kế), nên lọc ở đó sẽ loại sạch mọi thứ. Trạng thái
    phải tra từ chính tệp giữ nó.

    Mẫu KHÔNG có dòng nào trong `samples.csv` không rơi vào đây: những tệp ấy đã
    được `unlabeled` / `unreadable` xử lý, và thêm một luật thứ hai vào cùng chỗ
    sẽ làm một bản phát hành teo lại vì một lý do khác hẳn thứ báo cáo nói.
    """
    from app.moderation import APPROVED, status_of

    out: dict = {}
    for src in sources:
        src = Path(src)
        if not src.exists():
            continue
        for r in _read_csv(src):
            sid = (r.get("sample_id") or r.get("sample_uid") or "").strip()
            if not sid or sid in out:
                continue
            tt = status_of(r)
            if tt != APPROVED:
                out[sid] = f"chua qua kiem duyet (review_status={tt})"
    return out


def load_excluded_ids(path: Path | None) -> dict:
    """sample_id -> reason, from a decisions file.

    Excluding at the manifest instead of deleting or moving the file keeps every
    previously published split runnable: a manifest is a versioned view of the
    feature tree, so a new version can drop a sample while the older versions
    that reference it still resolve on disk.
    """
    if not path or not path.exists():
        return {}
    cfg = json.loads(path.read_text(encoding="utf-8"))
    excluded = {}
    for entry in cfg.get("files", []):
        if str(entry.get("decision") or "").strip() not in ("exclude", "quarantine"):
            continue
        sample_id = Path(str(entry.get("path") or "")).stem.replace("sample_", "")
        if sample_id:
            excluded[sample_id] = str(entry.get("reason") or "")
    return excluded


def build_manifest(features_root: Path, labels_rows: list, signer_name_to_id: dict,
                   legacy_user_index: dict | None = None,
                   excluded_ids: dict | None = None,
                   sample_class_index: dict | None = None) -> tuple:
    label_by_folder = {}
    label_by_uid = {}
    for r in labels_rows:
        folder = (r.get("folder_name") or "").strip()
        if folder:
            label_by_folder[folder] = r
        cuid = (r.get("class_uid") or "").strip()
        if cuid:
            label_by_uid[cuid] = r

    sample_class_index = sample_class_index or {}
    excluded_ids = excluded_ids or {}
    rows, unreadable, unlabeled, excluded, augmented = [], [], [], [], []
    for npz_path in sorted(features_root.rglob("*.npz")):
        sample_id_early = npz_path.stem.replace("sample_", "")
        if sample_id_early in excluded_ids:
            excluded.append({"sample_id": sample_id_early, "path": str(npz_path),
                             "reason": excluded_ids[sample_id_early]})
            continue

        folder = npz_path.parent.name
        # class_*/aug_NNN/ holds augmented copies. They are skipped on purpose:
        # an augmented copy in val/test while its original is in train scores
        # the model on data it trained on. They used to fall out silently as
        # "no matching label folder", which read like a defect rather than a
        # decision — and the class_uid fallback below would have pulled every
        # one of them in.
        if folder.startswith("aug_"):
            augmented.append(str(npz_path))
            continue
        label_row = label_by_folder.get(folder)
        if label_row is None:
            # The file may sit in the folder of a class that has since been
            # merged away; samples.csv still records where the row belongs.
            label_row = label_by_uid.get(sample_class_index.get(sample_id_early, ""))
        if label_row is None:
            unlabeled.append(str(npz_path))
            continue
        flags = _npz_flags(npz_path)
        if not flags["readable"]:
            unreadable.append(str(npz_path))
            continue
        side = _load_sidecar(npz_path)

        slug = (label_row.get("slug") or "").strip()
        scope = (label_row.get("vocabulary_scope") or "").strip()
        profile = (label_row.get("recognition_profile") or "").strip()
        language = (label_row.get("language") or "vn").strip() or "vn"
        try:
            lkey = label_key_v2(language, scope, profile, slug)
        except ValueError:
            # unassigned rows keep the legacy key so they remain addressable
            dialect = (label_row.get("dialect") or "").strip()
            lkey = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"

        sample_id = npz_path.stem.replace("sample_", "")
        raw_name = _signer_name(side.get("user_id"), side.get("user"))
        if not raw_name and legacy_user_index:
            raw_name = _signer_name(legacy_user_index.get(sample_id, ""))
        # Tên người ký (user_id) được ưu tiên hơn signer_id trong sidecar, vì
        # signer_id ở đó suy ra từ TÀI KHOẢN thu thập. Tài khoản S010 và S011
        # mỗi cái được ba người dùng chung để ký, nên lấy theo signer_id sẽ gộp
        # nhiều người thành một và làm hỏng mọi split "tách người ký".
        signer_id = signer_name_to_id.get(raw_name, "") or str(side.get("signer_id") or "").strip()

        quality_flags = str(side.get("quality_flags") or "").strip()
        quality_status = str(side.get("quality_status") or "").strip() or (
            "flagged" if quality_flags else "unknown"
        )

        rel = npz_path.relative_to(REPO_ROOT) if str(npz_path).startswith(str(REPO_ROOT)) else npz_path
        rows.append({
            "sample_id": sample_id,
            "file_path": str(rel).replace("\\", "/"),
            "file_checksum": sha256_file(npz_path),
            "label_key": lkey,
            "semantic_label": (label_row.get("semantic_label") or semantic_label_from_slug(slug)),
            "vocabulary_scope": scope,
            "recognition_profile": profile,
            "vocabulary_group": (label_row.get("vocabulary_group") or "").strip(),
            "collection_campaign": str(side.get("collection_campaign") or label_row.get("collection_campaign") or "").strip(),
            "motion_type": (label_row.get("motion_type") or "").strip(),
            "signer_id": signer_id,
            "session_id": str(side.get("session_id") or "").strip(),
            "source_type": str(side.get("source_type") or "camera").strip(),
            "raw_landmarks_available": "1" if flags["raw"] else "0",
            # Deliberately NOT in MANIFEST_FIELDS. The manifest schema is
            # versioned and hash-pinned, and splits are frozen against it, so a
            # new column would invalidate artifacts to report a number that no
            # model reads — world landmarks are display-only. It rides along for
            # the stats block and the CSV writer drops it (extrasaction).
            "world_landmarks_available": "1" if flags["world"] else "0",
            "normalization_version": str(side.get("normalization_version") or "hands126_v1").strip(),
            "quality_status": quality_status,
            "class_uid": (label_row.get("class_uid") or "").strip(),
            "slug": slug,
            "label_original": (label_row.get("label_original") or "").strip(),
            "language": language,
            "dialect": (label_row.get("dialect") or "").strip(),
            "folder_name": folder,
            "file": npz_path.name,
        })
    return rows, unreadable, unlabeled, excluded, augmented


def compute_stats(rows: list) -> dict:
    return {
        "total_samples": len(rows),
        "by_vocabulary_scope": dict(Counter(r["vocabulary_scope"] or "<unassigned>" for r in rows)),
        "by_recognition_profile": dict(Counter(r["recognition_profile"] or "<none>" for r in rows)),
        "by_signer": dict(Counter(r["signer_id"] or "<unresolved>" for r in rows)),
        "by_label_key": dict(Counter(r["label_key"] for r in rows)),
        "raw_landmarks_available": dict(Counter(r["raw_landmarks_available"] for r in rows)),
        "world_landmarks_available": dict(Counter(r["world_landmarks_available"] for r in rows)),
        "by_quality_status": dict(Counter(r["quality_status"] for r in rows)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "dataset" / "labels.csv")
    ap.add_argument("--signers-csv", type=Path, default=REPO_ROOT / "dataset" / "signers.csv")
    ap.add_argument("--signer-mapping", type=Path, default=REPO_ROOT / "config" / "legacy_signer_mapping.json")
    ap.add_argument("--legacy-user-sources", type=Path, nargs="*",
                    default=[REPO_ROOT / "processed" / "splits" / "train.csv",
                             REPO_ROOT / "processed" / "splits" / "val.csv",
                             REPO_ROOT / "processed" / "splits" / "test.csv",
                             REPO_ROOT / "dataset" / "samples.csv"],
                    help="Frozen CSVs recording sample_id->user_id for pre-sidecar samples")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "dataset" / "manifests")
    ap.add_argument("--exclude", type=Path, default=REPO_ROOT / "config" / "excluded_samples.json",
                    help="Decisions file listing samples to leave OUT of this manifest version")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing version (breaks immutability — avoid)")
    # --- cổng đồng thuận -------------------------------------------------
    ap.add_argument("--consent-scope", default="internal_training",
                    choices=["internal_training", "research_release", "public_library"],
                    help="Manifest này dùng để làm gì. Mặc định nội bộ; đóng gói "
                         "phát hành hay công bố phải nói rõ, và mẫu không truy "
                         "được người ký sẽ bị loại ở hai mức đó.")
    ap.add_argument("--consent-snapshot", type=Path,
                    default=REPO_ROOT / "dataset" / "consent_snapshot.json",
                    help="Ảnh chụp đồng thuận, xuất bằng "
                         "`python -m app.cli.consent_snapshot` TRONG container")
    ap.add_argument("--skip-consent-gate", action="store_true",
                    help="Bỏ qua cổng đồng thuận. Việc bỏ qua được GHI VÀO stats "
                         "của phiên bản này và đi theo nó vĩnh viễn.")
    args = ap.parse_args()

    out_dir = args.out_dir
    manifest_path = out_dir / f"dataset_manifest_{args.version}.csv"
    if manifest_path.exists() and not args.force:
        print(f"[ERROR] {manifest_path} already exists. Manifests are immutable — "
              f"create a NEW --version (or pass --force if you really mean to overwrite).")
        return 2

    labels_rows = _read_csv(args.labels_csv)
    signer_name_to_id = {}
    if args.signer_mapping.exists():
        signer_name_to_id = json.loads(args.signer_mapping.read_text(encoding="utf-8")).get(
            "legacy_name_to_signer_id", {})

    legacy_user_index = build_legacy_user_index(args.legacy_user_sources)
    sample_class_index = build_sample_class_index(args.legacy_user_sources)
    # Cổng kiểm duyệt và tệp quyết định dùng CHUNG một cơ chế loại trừ.
    #
    # Tệp quyết định thắng khi trùng: một mẫu bị loại vì lý do chất lượng thì
    # lý do ấy đáng đọc hơn "chưa qua kiểm duyệt", kể cả khi cả hai đều đúng.
    chua_duyet = load_unapproved_ids(args.legacy_user_sources)
    if chua_duyet:
        print(f"[kiem-duyet] loai {len(chua_duyet)} mau chua qua kiem duyet")
    excluded_ids = {**chua_duyet, **load_excluded_ids(args.exclude)}
    rows, unreadable, unlabeled, excluded, augmented = build_manifest(
        args.features_root, labels_rows, signer_name_to_id, legacy_user_index,
        excluded_ids=excluded_ids, sample_class_index=sample_class_index)
    # --- cổng đồng thuận, TRƯỚC khi thống kê -----------------------------
    #
    # Đặt ở đây chứ không sau `compute_stats`: mọi con số trong stats phải mô tả
    # đúng tập mẫu thật sự nằm trong manifest. Một bản thống kê đếm cả mẫu đã bị
    # loại là một bản thống kê nói dối về chính tệp đi kèm nó.
    consent_note: dict = {"scope": args.consent_scope}
    if args.skip_consent_gate:
        # Ghi lại việc bỏ qua vào chính phiên bản manifest. Manifest là bất biến,
        # nên dòng này đi theo nó vĩnh viễn — đó là toàn bộ mục đích.
        consent_note.update({"enforced": False, "reason": "--skip-consent-gate"})
        print("[WARN] cong dong thuan BI BO QUA theo yeu cau — ghi vao dataset_stats")
    else:
        from app.consent_gate import (  # noqa: E402
            SnapshotUnusable, filter_rows, load_snapshot,
        )

        try:
            consents, aliases, snap_meta = load_snapshot(args.consent_snapshot)
        except SnapshotUnusable as exc:
            # Mặc định-TỪ CHỐI. Quên xuất ảnh chụp không được phép âm thầm trở
            # thành "phát hành mọi thứ".
            print(f"[ERROR] {exc}")
            print("        Hoac chay lai lenh xuat anh chup, hoac neu that su muon")
            print("        dung manifest KHONG loc thi truyen --skip-consent-gate.")
            return 4

        gated = filter_rows(rows, scope=args.consent_scope,
                            consents=consents, aliases=aliases)
        consent_note.update({
            "enforced": True,
            "snapshot_hash": snap_meta.get("content_hash"),
            "snapshot_generated_at": snap_meta.get("generated_at"),
            "kept": len(gated.kept),
            "withheld": len(gated.withheld),
            "withheld_reasons": gated.reasons,
        })
        print(f"[CONSENT] {gated.summary()}")
        if gated.withheld and not gated.kept:
            print("[ERROR] cong dong thuan loai HET moi mau. Voi muc "
                  f"'{args.consent_scope}' thi mau khong truy duoc nguoi ky va "
                  "nguoi ky chua ky deu bi loai — day la hanh vi dung, nhung mot "
                  "manifest rong thi khong dung duoc.")
            return 5
        rows = gated.kept

    stats = compute_stats(rows)
    stats["consent_gate"] = consent_note
    stats["generated_at"] = datetime.utcnow().isoformat() + "Z"
    stats["version"] = args.version
    stats["unreadable_files"] = unreadable
    stats["unlabeled_files_count"] = len(unlabeled)
    # Recorded in the version's stats so a later reader can tell that this
    # manifest deliberately omits samples that still exist on disk, and why.
    stats["excluded_samples_count"] = len(excluded)
    stats["excluded_samples"] = excluded
    # Augmented copies are a policy omission, not a defect — counted separately
    # so nobody reads them as missing data.
    stats["augmented_files_skipped"] = len(augmented)

    # Two rows with the same file_checksum are the same recording twice. Split
    # them across train and test and the model is scored on data it memorised —
    # and nothing downstream would notice, because they carry different
    # sample_ids. This was found only by chance (a stray Windows "(1)" copy),
    # so it is checked here, before the version is frozen.
    by_checksum: dict = {}
    for r in rows:
        by_checksum.setdefault(r["file_checksum"], []).append(r["sample_id"])
    dupes = {k: v for k, v in by_checksum.items() if len(v) > 1}
    if dupes:
        print(f"[ERROR] {len(dupes)} duplicate recording(s) — identical bytes under "
              f"different sample_ids. Releasing this manifest would allow the same "
              f"recording into train and test:")
        for checksum, ids in list(dupes.items())[:10]:
            print(f"  sha256={checksum[:16]}…  sample_ids={ids}")
        print(f"Resolve by listing the redundant file(s) in {args.exclude}, then re-run.")
        return 3

    out_dir.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # Frozen copies of labels + signers
    import shutil
    shutil.copy2(args.labels_csv, out_dir / f"labels_{args.version}.csv")
    if args.signers_csv.exists():
        shutil.copy2(args.signers_csv, out_dir / f"signers_{args.version}.csv")
    (out_dir / f"dataset_stats_{args.version}.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    checksum = sha256_file(manifest_path)
    (out_dir / f"dataset_manifest_{args.version}.sha256").write_text(checksum + "\n", encoding="utf-8")

    print(f"manifest -> {manifest_path}  ({len(rows)} samples, sha256={checksum[:12]}...)")
    print(f"stats: scope={stats['by_vocabulary_scope']} profiles={stats['by_recognition_profile']}")
    print(f"raw available: {stats['raw_landmarks_available']}")
    print(f"world (metric 3D) available: {stats['world_landmarks_available']}")
    if excluded:
        print(f"excluded by {args.exclude.name}: {len(excluded)} samples "
              f"(files left on disk so older manifest versions still resolve)")
    if augmented:
        print(f"augmented copies skipped: {len(augmented)} "
              f"(aug_*/ — keeping them would put a copy of a train sample in val/test)")
    if unreadable:
        print(f"[WARN] unreadable npz: {len(unreadable)}")
    if unlabeled:
        print(f"[WARN] npz whose class could not be resolved by folder OR samples.csv: "
              f"{len(unlabeled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
