# Vocabulary Schema v2 — Recognition Profiles

> Trạng thái: Phase 1–3 đã triển khai (schema + migration, raw landmark storage +
> immutable manifest, profile-aware training + signer-disjoint splits).
> Phase 4–5 (realtime profile routing, experiment automation) CHƯA triển khai.

## Vì sao thay đổi

Trường `dialect` cũ trộn 3 khái niệm: vùng miền (can-tho), nhóm từ vựng
(bang-chu-cai = bảng chữ cái, spa) và chiến dịch thu thập. Hướng sản phẩm mới:
người dùng realtime chọn một **recognition profile** (north/central/south/hoa_de),
model chỉ nhận diện trong **common + profile được chọn**.

## Schema

Module canonical: `processed/shared/vocabulary.py` (pure stdlib — backend,
trainer, scripts, tests dùng chung).

**Label** (labels.csv + bảng `classes`, cột mới):
- `semantic_label` — nghĩa đầu ra, dạng underscore (`rang_muoi`)
- `vocabulary_scope` — `common` | `profile_specific` | `""` (chưa gán/chờ xác nhận)
- `recognition_profile` — `alphabet|north|central|south|hoa_de|legacy_unassigned|""`
  - `alphabet` là profile ĐỘC LẬP (fingerspelling tĩnh) — train/deploy riêng,
    KHÔNG tự động nằm trong các model vùng
  - scope=common → profile PHẢI rỗng
  - scope=profile_specific → profile bắt buộc, thuộc 5 profile hợp lệ
- `motion_type` (tùy chọn) — `static|dynamic|mixed|""` (alphabet=static, hoa_de=dynamic)
- **Chính sách include_common (từ 2026-07-19): mặc định FALSE** — profile model
  chỉ chứa từ vựng của chính profile đó; muốn thêm common phải truyền
  `--include_common` tường minh. `--unified` vẫn gộp common + mọi profile.
- `vocabulary_group` — nhóm nghiệp vụ (alphabet, hoa_de_vocabulary, spa…), KHÔNG dùng để route model
- `collection_campaign` — nguồn thu (legacy_2026, isds2026_v1…)
- `is_active`

**Label key v2:** `vn/common/<slug>` hoặc `vn/<profile>/<slug>`.
`dialect` bị **deprecated** về ngữ nghĩa (chỉ còn là tên thư mục vật lý).

**Signer** (`dataset/signers.csv` + bảng `signers`): `signer_id` (S001…),
`display_name`, `regional_group`, `external_user_id` (auth UUID), `is_active`,
`created_at`. `signer_id` là khóa DUY NHẤT cho signer-disjoint split; sample mới
resolve signer từ tài khoản đăng nhập (không free-text). KHÔNG auto-merge tên
giống nhau — script migration chỉ BÁO CÁO ứng viên trùng để xác nhận tay
(`config/legacy_signer_mapping.json`).

**Sample** (cột mới): `signer_id`, `collection_campaign`,
`raw_landmarks_available`, `normalization_version`, `preprocess_contract_version`,
`sequence_length_original`, `quality_status` (+ các cột QC có sẵn).

## NPZ v2 (mẫu thu mới)

```
sequence               float32 [60,126]   # key legacy — loader cũ vẫn đọc được
landmarks_normalized   float32 [60,126]
landmarks_raw          float32 [T_original,126]  # TRƯỚC wrist-centering/scaling
frame_valid_mask       bool [60]
left_hand_valid_mask   bool [60]
right_hand_valid_mask  bool [60]
meta                   dict (contract v2)
```
Mẫu cũ không có raw → `raw_landmarks_available=false`; KHÔNG BAO GIỜ tạo raw giả
từ dữ liệu đã chuẩn hóa.

## Lệnh

```bash
# Migration legacy (dry-run trước)
python scripts/migrate_legacy_vocabulary_schema.py --dry-run --mapping config/legacy_vocabulary_mapping.json
python scripts/migrate_legacy_vocabulary_schema.py --mapping config/legacy_vocabulary_mapping.json

# Manifest immutable + validate
python scripts/create_dataset_manifest.py --version isds2026_v1
python scripts/validate_dataset_manifest.py --version isds2026_v1 --check-checksums

# Split theo profile (versioned, không đụng frozen legacy splits)
python processed/splits/make_splits.py \
  --dataset_manifest dataset/manifests/dataset_manifest_isds2026_v1.csv \
  --split_mode strict_signer_disjoint --recognition_profile hoa_de \
  --include_common --seed 42 --output_version hoa_de_signer_disjoint_v1
# (protocol so sánh nghiên cứu: --split_mode sample)

# Train profile model (trong container trainer)
python processed/train_utils/train_tcn.py \
  --model_type tcn --recognition_profile hoa_de --include_common \
  --dataset_version isds2026_v1 --split_version hoa_de_sample_v1 \
  --train_csv processed/splits/versions/hoa_de_sample_v1/train.csv \
  --val_csv   processed/splits/versions/hoa_de_sample_v1/val.csv \
  --test_csv  processed/splits/versions/hoa_de_sample_v1/test.csv \
  --seed 42

# Unified baseline
python processed/train_utils/train_tcn.py --model_type tcn --unified \
  --dataset_version isds2026_v1 --split_version <unified_split> ...
```

Output: `outputs/<dataset_version>/<profile|unified>/<split_version>/<model>/seed_<n>/`

## Checkpoint contract v2 (trường bổ sung)

`vocabulary_schema_version`, `recognition_profile`, `include_common`, `unified`,
`dataset_version`, `split_version`, `preprocess_contract_version`,
`common_labels`, `profile_specific_labels`, `seed`, `git_commit`,
`training_config` (kèm augmentation config), `dataset_manifest_checksum`.
Run legacy (`--dialect`) ghi `vocabulary_schema_version="v1_legacy"`.

## Backward compatibility & deprecation

- Frozen legacy splits (`processed/splits/{train,val,test}.csv`) giữ nguyên,
  không regenerate; chỉ dùng để so sánh nghiên cứu.
- `--dialect` còn hoạt động nhưng in cảnh báo DEPRECATED.
- Cột `dialect` chưa bị xóa (còn là tên thư mục vật lý); kế hoạch: sau khi
  toàn bộ label được xác nhận scope/profile và realtime chuyển sang v2 (Phase 4),
  tách "storage_dir" thành cột riêng và ngừng đọc `dialect` ở mọi API.
- Checkpoint legacy vẫn load bình thường (realtime chưa đổi; Phase 4 sẽ thêm
  explicit compatibility mode thay vì silently bypass).

## Trạng thái quyết định nghiệp vụ (cập nhật 2026-07-19)

**Đã xác nhận:** `bang-chu-cai` → profile `alphabet` (static, độc lập);
`trung` → `central`; gộp signer Minh/minh→S002, Tran/Trân/trân→S001
(đã apply qua `scripts/apply_signer_merges.py`).

**Chờ xác nhận:**
1. `can-tho` (40 mẫu) — ĐÃ REVERT về needs_review theo chỉ thị mới nhất;
   không tự gán `south`.
2. `spa` (2 lớp) — scope/profile chưa quyết.
3. 7 file orphan/invalid trong `config/orphan_file_decisions.json` (pending).
4. Signer-disjoint: alphabet bị chặn bởi `vn/alphabet/p` (1 signer);
   hoa_de chỉ có 2 signer (cần ≥3 cho 3 tập); central chưa có mẫu nào.
