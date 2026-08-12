# Paper Pipeline Release — ISDS 2026

> Trạng thái: **pre-freeze**. Tài liệu này mô tả đúng những gì code làm được
> tại thời điểm freeze. Mọi claim ở đây phải kiểm chứng được bằng một artifact
> hoặc một test. Nếu bạn không chứng minh được, đừng viết vào bài báo.

Tag dự kiến: `isds2026-paper-pipeline-v1`

---

## 1. Scope

Release này đóng băng **pipeline nghiên cứu**: từ thu mẫu live-capture → manifest
bất biến → split có kiểm định → training tái lập được → tổng hợp kết quả.

**Thuộc scope**

- Live-capture collection (camera) với quality gate 2 cấp
- Immutable versioned dataset manifest + checksum
- Profile-filtered split (sample-level và strict signer-disjoint)
- Profile-specific training với checkpoint contract v2
- Deterministic training + verification
- Aggregation kết quả từ artifact

**Ngoài scope (cố ý không làm)**

- Realtime multi-profile registry (Phase 4)
- Video pipeline như nguồn benchmark
- QC filtering trong trainer
- Motion-aware training
- GroupKFold / repeated group split
- Model mới, on-device export, personalization

### Supported profiles

| Profile | Loại | Số lớp (isds2026_v3) | Mẫu |
|---|---|---|---|
| `alphabet` | static fingerspelling | 23 | 614 |
| `hoa_de` | dynamic vocabulary | 7 | 211 |

`north` / `south` / `central` đã có trong schema nhưng **chưa có dữ liệu** →
không thuộc release này.

### Benchmark source

**Live capture là nguồn benchmark chính.** Đường video (`processing/pipeline.py`)
vẫn tồn tại cho việc bootstrap dữ liệu nhưng **không** thuộc benchmark:

- nó không đi qua `quality.py` (dùng ngưỡng completeness/activity riêng);
- nó sinh nhiều window có chồng lấn từ một video → các mẫu không độc lập;
- nó chạy augmentation lúc lưu (`augment_per_seq`), khác hoàn toàn hợp đồng
  augmentation train-time.

Bài báo phải nói rõ điều này. Không trộn mẫu video vào tập benchmark.

---

## 2. Preprocessing contract

| Thuộc tính | Giá trị |
|---|---|
| Extractor | MediaPipe Hands, 2 × 21 landmark |
| Feature vector | 126 = `[left(63), right(63)]`, mỗi tay 21 × (x, y, z) |
| Sequence | 60 frame, pad/truncate |
| Handedness | MediaPipe label được **swap** vào slot giải phẫu (`swapped_mp_handedness_slots`) |
| Missing hand | block 63 chiều = 0 |
| Normalization | `hands126_v1` — mỗi tay wrist-center (x, y) rồi chia cho `max(span_x, span_y)` |
| Trục z | **giữ nguyên raw MediaPipe**, không normalize |
| Coordinate space | `mediapipe_normalized` trước normalize; wrist-centered sau |

Implementation: `processed/shared/normalization.py` — **một bản duy nhất**, được
dùng bởi cả collection (`routers/upload.py`) lẫn realtime service
(`realtime_service/app/startup.py` nạp đúng file này theo path). Frontend
**không** normalize (`utils/realtimeFlatten.ts`). Vì vậy training-serving skew
về normalization được ngăn *by construction*, không phải bằng cross-validation test.

> Claim tối đa cho phép: *"prevented by construction via a single shared
> implementation"*. **Không** viết "validated by a golden test" — chưa có.

### Storage contract

| Version | Nội dung npz |
|---|---|
| `npz_v1_legacy` | `sequence`, `meta` |
| `npz_v2` | `sequence`, `landmarks_normalized`, `landmarks_raw [T,126]`, `frame_valid_mask [60]`, `left_hand_valid_mask [60]`, `right_hand_valid_mask [60]`, `meta` |

`storage_contract_version` được đóng dấu bởi **writer** (`dataset_samples.save_sequence_npz`),
không phải bởi caller.

**Trạng thái dữ liệu hiện tại: 865/865 mẫu là `npz_v1_legacy`** — chưa có mẫu nào
có raw landmarks. Ablation tiền xử lý chỉ khả thi trên dữ liệu thu mới.

---

## 3. Augmentation contract

Bảng chuẩn sinh trực tiếp từ code:

```bash
python scripts/export_augmentation_contract.py
# -> reports/augmentation_contract.md  (bảng cho methodology section)
# -> reports/augmentation_contract.json
```

Version hiện tại: **`v2_wrist_centered_mirror`**, đóng dấu vào mọi checkpoint mới
tại `training_config.augmentation.augmentation_contract_version`.

Điểm cần nêu trong bài báo:

- **Mirror là phép phản chiếu `x → -x` quanh gốc cổ tay**, sau đó swap slot giải phẫu.
  Đây là một isometry: cổ tay là điểm bất động, mọi khoảng cách giữa landmark và
  hand span được bảo toàn chính xác. Script export **tự kiểm chứng** hình học này
  mỗi lần chạy và fail nếu implementation lệch khỏi hợp đồng.
- **Temporal masking = 0 ở mọi profile.** Nó zero cả frame, không phân biệt được
  với padding và với "mất cả hai tay" trong biểu diễn 126 chiều. Bật lại cần một
  frame-validity channel trong model input contract — ngoài scope.
- Augmentation **chỉ** chạy trên train (`build_train_augment` không bao giờ được
  truyền cho val/test loader).

Trainer từ chối chạy (hoặc cảnh báo lớn ở chế độ smoke_test) khi: thiếu contract
version, mirror lệch hình học, hoặc `temporal_mask_prob > 0`. Xem
`_enforce_augmentation_contract` trong `train_tcn.py`.

---

## 4. Manifest và versioning

```
dataset/manifests/
  dataset_manifest_<version>.csv      1 dòng / npz, có file_checksum sha256
  dataset_manifest_<version>.sha256   checksum của chính manifest
  labels_<version>.csv                bản đóng băng của label table
  signers_<version>.csv               bản đóng băng của signer registry
  dataset_stats_<version>.json        thống kê theo scope/profile/signer/class
```

- Manifest **bất biến theo quy ước**: `create_dataset_manifest.py` từ chối ghi đè
  version đã tồn tại (trừ `--force`, không bao giờ dùng trong release flow).
- `validate_dataset_manifest.py` phát hiện: manifest bị sửa, file thiếu, file mồ côi,
  checksum từng file lệch, vi phạm schema v2.
- Không có cơ chế tự sinh manifest mới khi dữ liệu đổi → **phải chạy release flow**.

Version đã đóng băng: `isds2026_v1`, `isds2026_v2`, `isds2026_v3` (865 mẫu).

---

## 5. Split protocol

Hai chế độ, đều chạy trên manifest (không phải trên `samples.csv`):

| Mode | Ý nghĩa |
|---|---|
| `sample` | stratified theo lớp, **không** ràng buộc signer |
| `strict_signer_disjoint` | signer không xuất hiện ở hai split |

### Split-validity gate

`strict_signer_disjoint` **fail cứng** (mặc định) khi:

- train / val / test rỗng;
- có lớp không có mẫu train / val / test;
- signer overlap giữa các split;
- split nào đó không có signer nào.

Lý do gate này tồn tại: với quá ít signer, greedy group assignment dồn toàn bộ
signer vào train, `_assert_signer_disjoint` pass một cách rỗng nghĩa (tập rỗng
disjoint với mọi tập), và split vẫn được ghi ra đĩa trông như thành công.
`hoa_de_signer_disjoint_v1` và `_v3` đã được sinh ra đúng như vậy: `val=0, test=0`.

`--allow_invalid_split` là lối thoát **debug duy nhất**; artifact khi đó bị đóng dấu
`valid_for_research: false` và aggregator từ chối mọi run huấn luyện trên nó.

`split_metadata.json` luôn có: `valid_for_research`, `invalid_reasons`,
`signer_counts`, `class_coverage`, `sample_counts`, `excluded_unresolved_signers`,
`seed`, `dataset_manifest_checksum`.

> **Giới hạn dữ liệu hiện tại:** signer-disjoint split cho `hoa_de` và `alphabet`
> **không tạo được**. Sau merge chỉ còn ~6 signer thật, trong đó 2 người chiếm 85%
> số mẫu; `vn/alphabet/p` chỉ có 1 signer. Cần ≥6 signer và ≥3 signer/lớp.

---

## 6. Research-valid criteria

Nguồn chân lý duy nhất: **`scripts/research_validity.py`**. Cả
`audit_checkpoint_validity.py` và `aggregate_experiment_results.py` đều import từ đây;
không có bản logic thứ hai.

| # | Tiêu chí |
|---|---|
| C1 | `run_purpose == "research"` |
| C2 | augmentation contract là `v2_wrist_centered_mirror` (hoặc augmentation tắt / mirror_prob = 0) |
| C3 | checkpoint contract đủ trường (`REQUIRED_CONTRACT_KEYS`) |
| C4 | `dataset_version` và `split_version` khác rỗng |
| C5 | `dataset_manifest_checksum` tồn tại và khớp manifest trên đĩa |
| C6 | split metadata tồn tại |
| C7 | split có `valid_for_research: true` |
| C8 | `recognition_profile` khớp label map |
| C9 | không có label chéo profile |
| C10 | runtime environment metadata đủ (python / torch / numpy / device) |
| C11 | `git_commit` khác rỗng |
| C12 | test set khác rỗng |
| C13 | test metrics sinh sau khi restore best-validation state |
| C14 | run không bị đánh dấu failed / incomplete |

**Số epoch KHÔNG phải tiêu chí.** Early stopping có thể kết thúc một run thật sau
vài epoch. Smoke test bị loại bằng C1 (`run_purpose` khai báo tường minh), không
bằng cách đoán từ hyperparameter.

`--run-purpose` mặc định là `smoke_test`. Chế độ `research` enforce provenance và
split validity **trước khi** training bắt đầu (`_enforce_research_preconditions`).

---

## 7. Checkpoint contract

Mỗi checkpoint tự mô tả: `model_type`, `model_config`, `feature_dim`, `seq_len`,
`num_classes`, `label_to_idx` / `idx_to_label`, `common_labels`,
`profile_specific_labels`, `recognition_profile`, `include_common`, `unified`,
`dataset_version`, `split_version`, `dataset_manifest_checksum`,
`vocabulary_schema_version`, `normalization_version`, `preprocess_contract`,
`preprocess_contract_version`, `storage_contract_version`, `motion_types_present`,
`seed`, `git_commit`, `training_config` (gồm augmentation đầy đủ),
`run_purpose`, `run_status`, `model_selection`, `determinism`, `runtime_env`.

Realtime service từ chối khởi động khi checkpoint lệch registry về seq_len,
feature_dim, normalization_version hoặc preprocess_contract
(`realtime_service/app/contracts.py`).

### Chính sách checkpoint legacy

**Toàn bộ 27 checkpoint hiện có đều KHÔNG research-valid.** Xem
`reports/checkpoint_validity.md`.

Nguyên nhân chính: từ 2026-05-14 đến 2026-07-21, mirror train-time dùng dạng
image-space `x → 1-x` trên dữ liệu đã wrist-center, làm phồng hand span **3.1×**
và đẩy ~45% mỗi batch vào vùng toạ độ không bao giờ xuất hiện lúc inference.

- **Không xoá checkpoint nào.** Chúng được giữ làm hồ sơ.
- **Không trích dẫn số liệu của chúng** trong bài báo, kể cả để "tham khảo".
- Mọi bảng kết quả phải sinh lại sau tag này.

---

## 8. Commands

```bash
# BƯỚC 0 — ảnh chụp đồng thuận. Chạy TRONG container (chỗ duy nhất nối được
# Postgres). Thiếu nó thì chuỗi release dừng ngay ở pre-flight, và các script
# dựng manifest / chia split cũng từ chối chạy. Ảnh chụp có hạn 7 NGÀY.
# Xem docs/CONSENT_ENFORCEMENT.md.
docker exec voya_backend python -m app.cli.consent_snapshot \
  --out /dataset/consent_snapshot.json

# Hợp đồng augmentation cho methodology section
python scripts/export_augmentation_contract.py

# Chuỗi release (dừng ngay khi có bước fail; không bao giờ dùng --force)
python scripts/prepare_research_release.py \
  --campaign isds2026_v4 --manifest-version isds2026_v4 \
  --profiles alphabet hoa_de

# Training chính thức (KHÔNG mặc định — phải khai báo tường minh)
python processed/train_utils/train_tcn.py --run-purpose research \
  --train_csv processed/splits/versions/<split>/train.csv \
  --val_csv   processed/splits/versions/<split>/val.csv \
  --test_csv  processed/splits/versions/<split>/test.csv \
  --features_root dataset/features \
  --recognition_profile hoa_de \
  --dataset_version isds2026_v4 --split_version <split> \
  --augmentation_profile full --epochs 80 --seed 42

# Kiểm định tái lập
python scripts/verify_determinism.py --train_csv ... --val_csv ... --test_csv ... \
  --features_root dataset/features --recognition_profile hoa_de --epochs 2 --seed 42

# Hồ sơ và bảng kết quả
python scripts/audit_checkpoint_validity.py --json --markdown
python scripts/aggregate_experiment_results.py
python scripts/report_quality_stats.py --campaign isds2026_v4
python scripts/audit_duplicate_samples.py --manifest-version isds2026_v4

# Toàn bộ test (container)
docker build -f backend/Dockerfile.test -t voya_backend_test:latest backend
docker run --rm --network voya-collector_voya_network \
  -e DATABASE_URL='postgresql://admin:admin@postgres:5432/signdb' \
  -e CELERY_BROKER_URL='redis://redis:6379/0' \
  -e CELERY_RESULT_BACKEND='redis://redis:6379/0' \
  -v "$PWD:/src" -w /src voya_backend_test:latest \
  python -m pytest backend/tests -q
```

---

## 9. Known limitations

Phải xuất hiện trong phần Limitations của bài báo:

1. **Signer diversity**: ~6 signer thật, 2 người chiếm 85% mẫu. Signer-disjoint
   evaluation **chưa chạy được**. Không claim signer-independent performance.
2. **Chưa có QC data**: 865/865 mẫu hiện tại có `quality_status = unknown`. Quality
   gate đã triển khai và có test, nhưng **chưa mẫu nào đi qua nó**. Không claim
   "quality-aware training" — trainer không đọc metadata QC.
3. **Chưa có raw landmarks**: `raw_landmarks_available = 0` cho toàn bộ 865 mẫu.
   Preprocessing ablation chỉ khả thi trên dữ liệu mới.
4. **motion_type chỉ là metadata**: không điều khiển augmentation, window length hay
   capture protocol. Không claim "motion-aware".
5. **Chưa có run research-valid nào**: mọi checkpoint hiện tại đều bị loại.
6. **Phần lớn dữ liệu do nhóm phát triển thu.** Wording an toàn: *"a collection
   platform designed for multi-signer contribution, currently populated by a pilot
   cohort"*. Không dùng "community-driven dataset".
7. **Không có golden test** giữa frontend và backend preprocessing (rủi ro thấp vì
   chỉ có một implementation, nhưng chưa được kiểm chứng chéo).
8. **Ngưỡng QC là heuristic chưa hiệu chỉnh** (`qc_v1_heuristic_2026-07`). Được
   snapshot đầy đủ vào từng mẫu, nhưng chưa có nghiên cứu calibration.
9. **Windows path trong split metadata**: `dataset_manifest` được ghi bằng dấu `\`,
   nên `test_frozen_artifacts` bỏ qua 6 phép kiểm checksum khi chạy trong container
   Linux (25 pass thay vì 31). Không phải fail, nhưng nên chuẩn hoá thành POSIX path.
10. **Chưa thu được đồng thuận nào ở mức `research_release`.** Cổng đồng thuận
    (2026-08-09) chặn mọi mẫu không có đồng thuận còn hiệu lực ra khỏi bản phát
    hành nghiên cứu, và hiện `signer_consents` có **0 dòng**, còn **56,6%** mẫu
    không có `signer_id` để quy kết. Nghĩa là: **chuỗi release chạy hôm nay sẽ
    dừng ở pre-flight**, và đó là hành vi đúng chứ không phải lỗi. Trước khi
    dựng được artifact cho bài, phải thu đồng thuận thật và điền `signer_id`
    cho phần dữ liệu cũ. Xem `docs/CONSENT_ENFORCEMENT.md`.

    Với phần Limitations, đây là điểm MẠNH chứ không phải điểm yếu: nền tảng
    chứng minh được nó *không thể* phát hành dữ liệu chưa xin phép, thay vì hứa
    rằng nó sẽ không làm vậy.

---

## 10. Claim tuyệt đối không được viết

| Claim | Vì sao |
|---|---|
| "quality-aware training pipeline" | Trainer không đọc QC metadata; 0 mẫu có QC |
| "motion-aware" | `motion_type` không điều khiển gì |
| "community-driven dataset" | 85% mẫu từ 2 người |
| "signer-independent performance" | Signer-disjoint split không tạo được |
| "multi-dialect generalization" | Chỉ có alphabet + hoa_de; north/south/central không có dữ liệu |
| Bất kỳ số accuracy nào từ checkpoint hiện có | Toàn bộ 27 checkpoint không research-valid |
