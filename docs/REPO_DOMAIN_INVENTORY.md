# VOYA Collector - Kiểm kê file theo domain

> Trạng thái: Bản kiểm kê ban đầu, chưa di chuyển hoặc xóa source  
> Ngày rà soát: 2026-10-14  
> Liên quan: [ARCHITECTURE_EVOLUTION.md](./ARCHITECTURE_EVOLUTION.md)

## 1. Mục tiêu của đợt rà soát

Mục tiêu trước mắt là làm repo dễ đọc và dễ lần theo luồng gọi. Đợt này không nhằm tách hệ thống thành nhiều microservice vật lý và không thay đổi database.

Nguyên tắc phân loại:

- `domain`: code nghiệp vụ thuộc một chức năng cụ thể.
- `core`: cấu hình và cơ chế dùng xuyên backend.
- `infrastructure`: PostgreSQL, Redis/Celery, Google Drive, filesystem và tích hợp ngoài.
- `ml`: feature contract, normalization, model, training và evaluation.
- `runtime/artifact`: dữ liệu được tạo ra khi chạy; không phải source.
- `tooling`: script chạy thủ công, migration hoặc nghiên cứu.
- `candidate-remove`: ứng viên xóa sau khi xác minh.
- `dormant/broken`: luồng không được mount, thiếu file hoặc không thể coi là chức năng đang hoạt động.

## 2. Kết luận nhanh

Repo hiện tại có ranh giới domain tự nhiên, nhưng source đang được sắp xếp theo loại file và lịch sử phát triển:

- Router tập trung trong `backend/app/routers`.
- Logic nghiệp vụ nằm rải ở thư mục gốc `backend/app`.
- Persistence vừa nằm trong `storage`, vừa nằm trực tiếp trong các module nghiệp vụ.
- `processed` trộn source ML, script tạo split, file mapping sinh ra và runtime artifact.
- Frontend có một phần theo feature (`pages/training`) nhưng phần lớn component/API/hook còn đặt ngang hàng.
- Nhiều file rất lớn đang chứa nhiều trách nhiệm.
- Worker, trainer và beat dùng chung image/source backend; đây là modular monolith có process nền, không phải các service nghiệp vụ độc lập.

Đích phù hợp cho đợt dọn repo là **modular monolith theo domain**, giữ nguyên endpoint, PostgreSQL và cách deploy trong giai đoạn đầu.

## 3. Backend - ánh xạ file theo domain

### 3.1. Core và application shell

| File hiện tại | Vai trò | Đích đề xuất |
|---|---|---|
| `backend/app/main.py` | Tạo FastAPI app, middleware, lifecycle, mount router | `backend/app/main.py`, chỉ giữ composition root |
| `backend/app/config.py` | Toàn bộ settings | `backend/app/core/config.py` |
| `backend/app/logging_config.py` | Cấu hình logging | `backend/app/core/logging.py` |
| `backend/app/logging_utils.py` | Structured operation logging | `backend/app/core/observability.py` |
| `backend/app/api_validation.py` | Validation dùng chung ở API | `backend/app/core/api_validation.py`; validation đặc thù chuyển về domain |
| `backend/app/rate_limit.py` | Rate limiting và IP | `backend/app/core/rate_limit.py` |
| `backend/app/mem_utils.py` | Quản lý bộ nhớ tiến trình | `backend/app/core/memory.py` |
| `backend/app/db.py` | Khởi tạo DB, startup sync, bootstrap admin | Tách thành `infrastructure/database/startup.py` và identity bootstrap |
| `backend/app/worker.py` | Tạo Celery app và đăng ký task | `backend/app/core/celery_app.py` hoặc `infrastructure/queue/celery_app.py` |
| `backend/app/cli/init_db.py` | CLI khởi tạo DB | Giữ trong `backend/app/cli/` |

`main.py` không nên chứa logic nghiệp vụ. Sau khi dọn, file này chỉ nên cấu hình middleware, lifecycle và include router.

### 3.2. Identity/Auth

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/auth.py` | `domains/identity/api.py` | Giữ nguyên `/auth/*` |
| `backend/app/auth.py` | Tách thành `service.py`, `repository.py`, `tokens.py`, `passwords.py` | Đang trộn JWT, password, query user và reset token |
| `backend/app/cookie_auth.py` | `domains/identity/cookies.py` | HTTP cookie/CSRF |
| `backend/app/email_service.py` | `infrastructure/email/client.py` | Identity gọi qua interface |
| Phần session/lock trong `activity.py` | `domains/identity/session_service.py` hoặc administration security | Cần tách khỏi activity reporting |

Frontend tương ứng: đăng nhập, đăng ký, quên/đặt lại mật khẩu, auth context và route guard.

### 3.3. Administration và Operations

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/admin.py` | `domains/administration/api.py` | Users, resources, activity, security, sync |
| `backend/app/activity.py` | Tách `presence.py`, `security.py`, `sessions.py`, `audit.py` | Hiện chứa quá nhiều trách nhiệm và Redis key |
| `backend/app/monitoring.py` | `domains/operations/monitoring.py` | CPU, RAM, GPU, disk, container |
| `backend/app/sync_tasks.py` | `domains/operations/tasks/storage_sync.py` | Job đồng bộ Drive về local |
| `backend/app/export_tasks.py` | Chia theo owner: catalog export và collection artifact upload | Không để một file task chung chứa mọi loại sync |
| `backend/app/routers/health.py` | `domains/operations/health_api.py` | Health/live/ready/config/deps |
| `backend/app/routers/jobs.py` | `domains/operations/jobs_api.py` | Celery job inspection tổng quát |

### 3.4. Catalog/Dataset

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/classes.py` | `domains/catalog/classes_api.py` | Class, suggestion, stats, balance, trash |
| `backend/app/routers/dataset.py` | `domains/catalog/dataset_api.py` | Label/sample/session endpoints |
| `backend/app/routers/inference.py` | `domains/catalog/inference_api.py` | Danh sách class phục vụ inference |
| `backend/app/dataset_manager.py` | `domains/catalog/class_service.py` + repository | Đang quản lý CSV, class metadata và vocabulary |
| `backend/app/dataset_samples.py` | `domains/catalog/sample_service.py` + repository | Đang quản lý CSV, NPZ và metadata DB |
| `backend/app/catalog_sync.py` | Tách `class_mutations.py`, `trash_service.py`, `mirror_service.py` | File lớn, trộn DB/CSV/filesystem/Drive/TTS cache |
| `backend/app/balancer.py` | `domains/catalog/balance_service.py` | Thống kê và kế hoạch cân bằng |
| `backend/app/inference_loader.py` | `domains/catalog/inference_queries.py` | Chuyển label thành class map |
| `backend/app/signers.py` | `domains/catalog/signers.py` | Signer profile/metadata |
| `backend/app/validation/dataset_validator.py` | `domains/catalog/validation.py` | Validation đặc thù dataset |
| `backend/app/processing/class_registry.py` | `domains/catalog/class_registry.py` | Thuộc catalog, không thuộc media processing |
| `backend/app/storage/metadata_db.py` | Chia thành repository của catalog/collection/training | Hiện là persistence god-module |
| `backend/app/storage/catalog_mirror.py` | `domains/catalog/mirror.py` hoặc infrastructure adapter | Xác định rõ chiều sync |

Điểm cần xử lý: Catalog đang có nhiều nguồn dữ liệu đồng thời gồm PostgreSQL, CSV, JSON sidecar, filesystem và Google Drive. Không nên đổi schema hay xóa một nguồn trong cùng commit với việc di chuyển file.

### 3.5. Collection/Upload

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/upload.py` | `domains/collection/api.py` | Tách camera upload, video upload và process request |
| `backend/app/raw_uploads.py` | `domains/collection/raw_upload_repository.py` | Metadata raw video/CSV |
| `backend/app/tasks.py` | `domains/collection/tasks.py` | Celery entry point xử lý video |
| `backend/app/processing/pipeline.py` | `domains/collection/pipeline.py` | Orchestrator xử lý video |
| `backend/app/processing/ingest.py` | `domains/collection/ingest.py` | Đọc frame và temporal variants |
| `backend/app/processing/keypoints_adapter.py` | `domains/collection/keypoints.py` | Trích xuất sequence |
| `backend/app/processing/quality.py` | `domains/collection/quality.py` | QC dùng khi thu thập |
| `backend/app/processing/validator.py` | `domains/collection/validation.py` | Validation pipeline |
| `backend/app/processing/augmenter.py` | `domains/collection/augmentation.py` | Adapter augmentation |
| `backend/app/processing/augmentations.py` | `ml/augmentation/collection.py` hoặc domain collection | Chốt sau khi kiểm tra reuse với training |
| `backend/app/processing/feature_writer.py` | `domains/collection/feature_writer.py` | Ghi feature artifact |
| `backend/app/processing/storage_utils.py` | `domains/collection/storage.py` | Upload storage helpers |
| `backend/app/processing/utils.py` | Chia normalize sang `ml/shared`; atomic file write sang infrastructure | Không giữ utility hỗn hợp |

Điểm chức năng cần xác minh riêng: frontend hiện upload video nhưng luồng gọi `/upload/video/process` chưa được nối rõ trong `UploadVideoForm`. Không sửa luồng này trong commit chỉ di chuyển file.

### 3.6. Training

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/training.py` | `domains/training/api/` nhiều file | File rất lớn; không di chuyển và tách logic cùng một commit |
| `backend/app/training_tasks.py` | `domains/training/tasks/train.py`, `promote.py`, `backup.py` | Celery training queue |
| `backend/app/dataset_prep_tasks.py` | `domains/training/tasks/prepare_dataset.py` | Gọi các script tạo/validate manifest và split |
| `backend/app/storage/experiment_tracking_db.py` | `domains/training/repository.py` | Luồng tracking cũ/có phần dormant, cần kiểm tra bảng đang dùng |
| `processed/train_utils/train_tcn.py` | `ml/training/trainer.py` rồi tiếp tục chia nhỏ | File rất lớn |
| `processed/train_utils/dataset_loader.py` | `ml/training/dataset.py` | Dataset loader |
| `processed/train_utils/models/*` | `ml/models/*` | Model definitions |
| `processed/train_utils/metrics.py` | `ml/evaluation/metrics.py` | Evaluation |
| `processed/train_utils/augmentation.py` | `ml/augmentation/training.py` | Training augmentation |
| `processed/train_utils/hpo_search.py` | `ml/training/hpo.py` | Tooling/training |
| `processed/train_utils/handedness_analysis.py` | `ml/evaluation/handedness.py` | Analysis |
| `processed/splits/make_splits.py` | `ml/datasets/make_splits.py` | Source; CSV kết quả tách ra runtime |
| `processed/splits/make_budget_grid.py` | `scripts/training/` hoặc `ml/experiments/` | Research tooling |

### 3.7. Realtime

| File hiện tại | Đích đề xuất | Ghi chú |
|---|---|---|
| `backend/app/routers/realtime_proxy.py` | `domains/realtime_gateway/api.py` | Proxy từ core backend sang realtime service |
| `backend/realtime_service/app/*` | Giữ thành package độc lập, sau đó đổi tên nhất quán | Đây là service rõ ràng nhất hiện nay |
| `backend/realtime_service/config/models.json` | Registry config; lâu dài chỉ giữ metadata | Checkpoint không nên nằm cạnh source |
| `backend/realtime_service/config/checkpoints/*` | `runtime/models/` hoặc object storage | Artifact runtime, không phải source |
| `processed/realtime/run_realtime.py` | `scripts/development/` hoặc archive | Realtime CLI cũ, cần so với service hiện tại |
| `processed/realtime/assets/hand_landmarker.task` | `assets/ml/` hoặc runtime model assets | Binary dependency, cần ghi version/checksum |

### 3.8. TTS

| File hiện tại | Đích đề xuất |
|---|---|
| `backend/app/routers/tts.py` | `domains/tts/api.py` |
| `backend/app/services/tts_service.py` | `domains/tts/service.py` |
| `backend/app/services/tts_prewarm.py` | `domains/tts/prewarm.py` |

TTS vẫn là module trong backend; chưa cần service/container riêng.

### 3.9. Infrastructure

| File hiện tại | Đích đề xuất |
|---|---|
| `backend/app/storage/postgres_connection.py` | `infrastructure/database/postgres.py` |
| `backend/app/storage/gdrive_client.py` | `infrastructure/google_drive/client.py` |
| File lock/atomic writer dùng chung | `infrastructure/filesystem/` |
| Celery setup | `infrastructure/queue/` |
| `backend/migrations/*.sql` | Giữ nguyên trong giai đoạn đầu |

Không chuyển business query vào infrastructure chung. Query user, sample hoặc training job phải nằm trong repository của domain sở hữu.

## 4. Frontend - ánh xạ theo feature

### 4.1. App shell và shared

```text
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/components/Layout.tsx
frontend/src/components/Footer.tsx
frontend/src/components/ui/*
frontend/src/hooks/useToast.tsx
frontend/src/api/axiosClient.ts
frontend/src/utils/apiError.ts
```

Đích lâu dài: `app/`, `shared/ui`, `shared/api`, `shared/lib`.

### 4.2. Identity

```text
contexts/AuthContext.tsx
hooks/useAuth.ts
api/auth.ts
pages/LoginPage.tsx
pages/RegisterPage.tsx
pages/ForgotPasswordPage.tsx
pages/ResetPasswordPage.tsx
pages/NotAuthorizedPage.tsx
components/auth/*
utils/redirect.ts
utils/role.ts
```

Đích: `features/identity/`.

### 4.3. Collection

```text
pages/UploadPage.tsx
components/CaptureCamera.tsx
components/FullscreenCaptureModal.tsx
components/UploadVideoForm.tsx
components/CaptureGuide.tsx
api/upload.ts
api/jobs.ts
config/capture.ts
utils/qualityMessages.ts
utils/handIdentity.ts
utils/session.ts
```

Đích: `features/collection/`. `FullscreenCaptureModal.tsx` và `UploadVideoForm.tsx` cần tách nhỏ sau khi đã di chuyển nguyên trạng.

### 4.4. Catalog

```text
pages/LabelsPage.tsx
pages/TrashPage.tsx
components/AddDialectModal.tsx
api/dataset.ts
api/preferences.ts (nếu preference thuộc thu thập thì chuyển về collection)
config/languageLabels.ts
config/dialectLabels.ts
```

Đích: `features/catalog/`.

### 4.5. Training

```text
pages/training/*
hooks/useTrainingAPI.ts
```

Đích: `features/training/`. `useTrainingAPI.ts` cần được tách thành API client, query hooks và websocket hook.

### 4.6. Realtime

```text
pages/RealtimeRecognitionPage.tsx
components/realtime/RealtimeRuntime.tsx
api/realtime.ts
utils/realtimeRingBuffer.ts
utils/realtimeInferenceScheduler.ts
utils/realtimeFlatten.ts
utils/predictionSmoother.ts
utils/oneEuro.ts
config/handTracking.ts
```

Đích: `features/realtime/`. Các primitive thực sự được collection và training preview dùng chung có thể đặt tại `shared/mediapipe/`.

### 4.7. Administration/Operations

```text
pages/AdminUsersPage.tsx
pages/AdminResourcesPage.tsx
pages/AdminDataPage.tsx
pages/AdminActivityPage.tsx
components/LockUserModal.tsx
components/BlockIpModal.tsx
components/SyncGDriveModal.tsx
components/SecurityNotices.tsx
hooks/usePresence.ts
hooks/useIdleLogout.ts
```

Đích: `features/admin/` và `features/session/` nếu hook dùng ngoài admin.

### 4.8. Dashboard và TTS

- `pages/DashboardPage.tsx`, `components/dashboard/*` -> `features/dashboard/`.
- `api/tts.ts`, `components/SpeechInputButton.tsx`, `hooks/useSpeechToText.ts` -> xác minh: speech-to-text input không đồng nghĩa TTS output; đặt theo feature thực sự dùng chúng.

### 4.9. Frontend cần xử lý riêng

- `frontend/src/types.ts` đang là type tổng; chia type vào từng feature, chỉ giữ type dùng chung tại `shared/types`.
- `frontend/src/index.css` và `TrainingPipeline.css` lớn; chưa tách CSS cùng commit di chuyển component.
- `SessionSumary.tsx` có khả năng sai chính tả (`Summary`); đổi tên trong commit riêng.
- `components/ui/Icons.tsx` lớn nhưng vẫn là shared UI hợp lệ; tối ưu sau.

## 5. ML, dataset, artifact và research

### 5.1. Source cần giữ

```text
processed/shared/*.py                 -> ml/shared/
processed/train_utils/models/*.py     -> ml/models/
processed/train_utils/*.py            -> ml/training/ hoặc ml/evaluation/
processed/splits/make_splits.py       -> ml/datasets/
processed/analysis/export_labels.py   -> scripts/maintenance/ hoặc ml/datasets/
scripts/*.py                          -> phân loại maintenance/migration/research
```

### 5.2. Artifact/runtime, không phải source

```text
processed/splits/train.csv
processed/splits/val.csv
processed/splits/test.csv
processed/analysis/classes.txt
processed/analysis/*_to_*.json
backend/realtime_service/config/checkpoints/*.pt
dataset/*.csv và dataset/raw_videos/*
dataset/*.lock
reports/Generated/*
reports/verification/*
```

Không xóa ngay. Trước hết xác định file nào là fixture/reproducibility artifact và file nào chỉ là output local. Đích dự kiến là `runtime/`, artifact store hoặc release bundle.

### 5.3. Script thủ công đang đặt sai chỗ

Các file sau không nên nằm trực tiếp trong `backend/app`:

```text
cleanup_legacy_features.py
feature_structure_audit.py
dialect_reclassifier.py
dialect_mapping_reclassifier.py
global_common_promoter.py
oversample_balance.py
```

Đích:

- `scripts/maintenance/`: audit, cleanup, balance.
- `scripts/migration/`: dialect reclassifier, vocabulary/schema migrations.
- `scripts/training/`: split, experiment runner, k-fold và LOSO.
- `scripts/evaluation/`: figures, statistical reports và kiểm tra kết quả.

Đã chuyển root `monitor_jobs.py` về `scripts/maintenance/` và
`run_kfold_cv.py` về `scripts/training/` ngày 2026-10-14.

## 6. Dormant, broken và ứng viên xóa

### 6.1. Dormant/broken đã xác định

1. `backend/app/main.py` từng import `app.routers.experiments`, nhưng file đã được chủ động xóa cùng `train_task.py` và hai storage API cũ trong commit `875c6a7 (first arrange)`. Luồng cũ quản lý `experiments`, `experiment_metrics`, `model_versions`, start training và promote model. Luồng hiện tại đã thay bằng `routers/training.py`, `training_tasks.py`, `dataset_prep_tasks.py`, `storage/metadata_db.py` với `training_jobs`/`training_metrics`, cùng registry/reload của realtime service. Frontend hiện chỉ gọi `/training/*`, không gọi `/experiments` hoặc `/models`. **Đã xử lý ngày 2026-10-14: xóa import bị bỏ sót, không khôi phục router cũ.** Giữ migration cũ cho tới khi có kế hoạch database migration riêng.
2. `backend/app/routers/dataset_exporter.py` từng cung cấp `POST /api/dataset/export`: materialize sample từ Drive, validate NPZ và ghép toàn bộ thành NumPy memmap `features.dat`. Router được import nhưng chưa bao giờ được `include_router`; không có frontend, test hoặc tài liệu vận hành gọi endpoint này. Pipeline hiện tại dùng manifest + split version + `processed/train_utils/dataset_loader.py` đọc NPZ, nên không dùng memmap. **Đã xử lý ngày 2026-10-14: xóa import, router, `processing/validator.py`, `load_npz_features` và `merge_memmap`.** Đây là pipeline cũ được thay về mặt mục đích bởi dataset preparation, không có replacement một-một cho định dạng memmap.
3. `backend/app/storage/experiment_tracking_db.py` không có caller trong source hiện tại. Nó thuộc một thiết kế tracking cũ khác với `metadata_db.py`; chuyển thành ứng viên archive/xóa sau khi xác minh database production không có tool ngoài repo sử dụng trực tiếp.
4. Nhiều router đang được mount cả không version và dưới `/api/v1`; việc dọn cần giữ tương thích trước, sau đó deprecate endpoint cũ.

### 6.2. Ứng viên xóa có độ tin cậy cao

Chỉ xóa sau khi Git hoạt động bình thường và có một commit riêng:

```text
frontend/public/vite.svg                         # Đã xóa 2026-10-14
frontend/src/assets/react.svg                    # Đã xóa 2026-10-14
```

Hai file `.bak` từng được liệt kê ở đây đã được kiểm tra lại và **không còn được xem là ứng viên xóa an toàn**:

- `config/legacy_signer_mapping.json.bak_20260727_204104` là bản mapping signer duy nhất còn có trên nhánh này, trong khi nhiều script mặc định tìm `config/legacy_signer_mapping.json`. Cần quyết định khôi phục/đồng bộ với mapping mới, không xóa.
- `reports/Source/budget_grid_hoa_de_budget_v2_tcn_raw.txt.bak_144457` chứa 938 dòng kết quả grid đầy đủ (header, 936 lượt, footer), gồm cả các lượt `FAILED`; `reports/Source/tien-do.ps1` đang kỳ vọng file cùng tên không có hậu tố backup. Đây là dữ liệu nghiên cứu cần giữ hoặc đổi tên/archive có chủ đích.

Các file `__init__.py` rỗng không phải file thừa; chúng đánh dấu Python package và nên giữ khi package vẫn tồn tại.

### 6.3. Cần xác minh trước khi xóa

```text
frontend/src/components/DebugPanel.tsx
frontend/src/components/DebugPanel.css
processed/realtime/run_realtime.py
backend/app/storage/experiment_tracking_db.py
reports/verification/e2e_run_2026-08-16/
nginx.conf.d/.gitkeep và volume mount tương ứng
.grapuco/.gitignore
```

`DebugPanel` hiện chỉ xuất hiện trong import/render đã comment. `nginx.conf.d` hiện không có cấu hình thực; phải kiểm tra `nginx.conf` trước khi bỏ mount.

## 7. Các điểm nóng cần tách sau khi di chuyển nguyên trạng

| File | Xấp xỉ số dòng | Hành động |
|---|---:|---|
| `frontend/src/components/FullscreenCaptureModal.tsx` | 2035 | Chia camera lifecycle, MediaPipe, form metadata, quality và upload |
| `processed/train_utils/train_tcn.py` | 1839 | Chia config, dataset, trainer, evaluation và CLI |
| `backend/app/routers/training.py` | 1784 | Chia API theo dataset/jobs/evaluation/promotion/prediction |
| `backend/app/catalog_sync.py` | 1171 | Chia mutation, trash, mirror và transaction/rollback |
| `frontend/src/components/UploadVideoForm.tsx` | 1063 | Chia form, upload state, metadata và job progress |
| `frontend/src/components/realtime/RealtimeRuntime.tsx` | 1034 | Chia camera, buffer, scheduler, prediction và speech output |
| `processed/splits/make_splits.py` | 1000 | Chia split policies, validation, reporting và CLI |
| `backend/app/storage/gdrive_client.py` | 842 | Chia auth/client, upload/download, lookup và materialization |
| `backend/app/storage/metadata_db.py` | 835 | Chuyển query vào repository của domain sở hữu |

Không vừa `git mv` vừa refactor một file lớn trong cùng commit. Trước tiên di chuyển nguyên trạng và sửa import; sau đó mới chia file.

## 8. Chiến lược thực hiện

### Phase 0 - Làm cho trạng thái hiện tại có thể kiểm chứng

1. Xác nhận trạng thái Git sạch. `git status` đã chạy thành công ngoài sandbox; lỗi `must be run in a work tree` trước đó là giới hạn quyền ghi/làm mới index của phiên Codex đối với repo nằm ngoài workspace, không phải repo bị hỏng.
2. ~~Sửa import `experiments` bị thiếu và quyết định số phận `dataset_exporter`.~~ Hoàn thành 2026-10-14.
3. Build image từ source hiện tại, không dựa vào `voya_backend:latest` cũ.
4. Chạy smoke test: health, login, catalog, camera upload, video upload/process, dataset prepare, training API và realtime.
5. Lưu danh sách route và test result làm baseline.

### Phase 1 - Cleanup chắc chắn, không đổi hành vi

1. Xóa bốn file backup/template có độ tin cậy cao trong một commit riêng.
2. Chuyển script thủ công ra khỏi `backend/app` và root; cập nhật README/lệnh gọi/test.
3. Tạo `runtime/` và `.gitignore`, nhưng chưa di chuyển dataset/checkpoint trước khi xác minh mount và quy trình deploy.
4. Chuẩn hóa tên file sai chính tả trong commit riêng.

### Phase 2 - Backend domain-first trong cùng một ứng dụng

Thực hiện mỗi domain một commit hoặc một chuỗi commit nhỏ:

1. `core` và `infrastructure`.
2. `identity`.
3. `tts`.
4. `operations/administration`.
5. `catalog`.
6. `collection`.
7. `training`.
8. `realtime_gateway`.

Trong phase này:

- Giữ nguyên route URL.
- Giữ nguyên PostgreSQL schema.
- Giữ nguyên Celery task name vì task đang nằm trong queue có thể tham chiếu tên cũ.
- Có thể giữ compatibility module ở đường dẫn cũ để re-export tạm thời.
- Sau mỗi domain: import check, unit test, build đúng service và smoke test.

### Phase 3 - Frontend feature-first

1. Tạo `app`, `shared`, `features`.
2. Di chuyển từng feature: identity, dashboard, admin, catalog, collection, training, realtime.
3. Chỉ sửa import, không đổi UI trong commit di chuyển.
4. Sau khi ổn định mới chia các component/hook lớn.

### Phase 4 - ML và runtime

1. Chuyển `processed/shared` thành `ml/shared` và cập nhật cả trainer/realtime cùng lúc có kiểm soát.
2. Chuyển model definition và training source.
3. Tách script tạo artifact khỏi artifact đã sinh.
4. Cập nhật Compose volume và Python path.
5. Di chuyển checkpoint/dataset/report sau khi có manifest, checksum và backup.

### Phase 5 - Giảm nợ kiến trúc

1. Chọn PostgreSQL làm source of truth; xác định vai trò CSV/Drive là export, cache hay backup.
2. Tách repository theo data ownership.
3. Chuẩn hóa `/api/v1` và deprecate route không version.
4. Nối đầy đủ luồng video upload -> process job.
5. Chỉ đánh giá tách microservices/database sau khi repo đã rõ và test đủ.

## 9. Các commit đầu tiên được đề xuất

```text
docs: add architecture and domain inventory
fix: remove stale experiments router import or restore the intended router
test: add current-system smoke baseline
chore: remove confirmed template and backup files
refactor: move maintenance and research scripts out of backend app
refactor: introduce backend core and infrastructure packages
refactor: group identity domain without changing routes
```

Quyết định `remove` hay `restore` cho router `experiments` phải dựa trên việc so sánh với nhánh deploy/lịch sử Git; không nên đoán.

## 10. Điều chưa thực hiện trong bản kiểm kê này

- Chưa xóa file.
- Chưa di chuyển source.
- Chưa đổi import.
- Chưa đổi endpoint.
- Chưa đổi PostgreSQL schema.
- Chưa thay đổi Docker Compose.
- Chưa xác nhận runtime bằng build mới vì Docker Engine không khả dụng ở thời điểm kiểm tra cuối.

## 11. Nhật ký cleanup

### 2026-10-14 - Loại bỏ hai luồng dormant

- Xóa import `experiments` bị bỏ sót khỏi `backend/app/main.py`.
- Xóa import và file `backend/app/routers/dataset_exporter.py`.
- Xóa `backend/app/processing/validator.py` vì chỉ exporter cũ sử dụng.
- Xóa `load_npz_features` và `merge_memmap` khỏi `backend/app/processing/utils.py`.
- Xác nhận không còn caller bằng tìm kiếm toàn repo.
- Compile cú pháp thành công 158 file Python.
- Chưa chạy pytest vì Python local chưa cài package `pytest`; cần chạy qua image/backend environment khi Docker Engine sẵn sàng.

### 2026-10-14 - Xóa asset mẫu frontend

- Xóa `frontend/public/vite.svg` và `frontend/src/assets/react.svg` sau khi xác nhận không có caller.
- Giữ lại hai file `.bak` sau khi phát hiện chúng chứa cấu hình signer và kết quả nghiên cứu chưa có bản canonical tương ứng trên nhánh hiện tại.

### 2026-10-14 - Kiểm kê dataset ngoài repo và signer mapping

- Xác nhận checkout hiện tại không chứa dataset thật; `dataset/` chỉ có các file `*.lock` và toàn bộ dataset được ignore khỏi Git.
- Xác định file signer mapping `.bak` là mapping lịch sử; bản deploy ngày 2026-09-15 đã tái cấp một số ID và không tương thích ngược với manifest cũ.
- Xác định code không tự mirror `signers.csv` lên Drive, nên catalog Drive một mình chưa đủ để chứng minh registry canonical.
- Chưa khôi phục/đổi tên mapping và chưa chạy migration vì còn thiếu metadata Drive cùng registry signer từ PostgreSQL.
- Chi tiết và checklist đối chiếu nằm tại `docs/DATASET_AND_SIGNER_AUDIT.md`.

### 2026-10-14 - Phân nhóm công cụ trong `scripts/`

- Chuyển các script thực thi vào năm nhóm: `dataset`, `training`, `evaluation`, `migration`, `maintenance`.
- Giữ `_console.py`, `research_validity.py` và `prepare_research_release.py` ở root `scripts/` vì đây là helper/logic dùng chung và orchestrator.
- Cập nhật caller trong backend, test, tài liệu và shell script; không đổi logic API, database, Docker service hoặc dataset.
- Neo `/dataset/` trong `.gitignore` để không bỏ qua nhầm `scripts/dataset/`; cho phép thư mục script này đi vào Docker build qua `.dockerignore`.

### 2026-10-14 - Dọn hai Python CLI còn sót ở repository root

- Chuyển `monitor_jobs.py` vào `scripts/maintenance/` vì đây là công cụ quan sát job thủ công.
- Chuyển `run_kfold_cv.py` vào `scripts/training/` vì nó trực tiếp điều phối trainer.
- Cập nhật repo-root resolution, docstring, README và ghi chú cũ trong `KNOWN_ISSUES.md`.
- Không đổi API, thuật toán chia fold hoặc tham số training.

