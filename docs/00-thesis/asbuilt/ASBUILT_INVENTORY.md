# Lược đồ AS-BUILT — trích trực tiếp từ CSDL đang chạy

Nguồn: `signdb_test`. Sinh bởi `scripts/reverse_asbuilt_schema.py`.

**Revision:** `05bd8ea38746b35795f14078656e20ceda03f231` — cây làm việc **sạch**; phép chụp này đủ tư cách làm as-built.

Revision phải nằm trong tệp này, không nằm trong trí nhớ người chạy. Một mô
hình as-built không tự khai nó chụp lúc nào thì không đối chiếu lại được, và
câu *"tái dựng từ lược đồ của revision được đóng băng"* trong luận văn không
có gì chống lưng. Nếu dòng trên báo cây làm việc bẩn thì phép chụp này chưa
đủ tư cách làm as-built cho bản nộp — chạy lại sau khi commit.

**Nguồn của tệp này là CƠ SỞ DỮ LIỆU, không phải mã.** `ensure_tables()` chỉ
dùng để đối chiếu. Hai nguồn trả lời hai câu khác nhau — *đang có gì* và *mã
muốn tạo gì* — và khi chúng lệch, không bên nào được tự động thắng.

## Tổng lượng

- bảng: **59**
- view: 1
- khoá ngoại: 121 (trong đó **hợp nhiều cột: 24**)
- ràng buộc CHECK: 63
- UNIQUE: 16
- chỉ mục: 177 (partial: 33)
- trigger: 6
- bảng bật RLS: 35 — trong đó FORCE: 35
- policy: 35

## Ma trận sai khác As-built ↔ mã ↔ thiết kế

| Phân loại | Nghĩa | Số |
|---|---|---|
| `runtime` | có trong CSDL **và** trong mã → vào As-built PDM | 59 |
| `view` | materialize dưới dạng **VIEW**, không phải bảng nền → vào As-built PDM, vẽ khác bảng | 1 |
| `legacy` | có trong CSDL, **không** còn trong mã → tồn dư, phải điều tra | 0 |
| `declared` | có trong mã, **chưa** materialize dưới bất kỳ dạng nào | 0 |
| `target-only` | chỉ có trong DDL **thiết kế** chưa thi hành → sang Target PDM | 9 |
| `historical` | chỉ có trong **ảnh chụp CSDL cũ** (`pg_dump`) → đã bị bỏ, KHÔNG phải target | 1 |

**Giới hạn của phép quét này.** Nó đọc VĂN BẢN mã nguồn, nên một câu
`CREATE TABLE` có tên bảng dựng động phức tạp hơn một hằng chuỗi sẽ không được
nhìn thấy. Tên chưa giải được trong lượt này: **không có**.

Mục nào ở đây nghĩa là ma trận trên CHƯA đầy đủ, chứ không phải "không có gì".
Bản đầu của công cụ này báo `schema_migrations` là tồn dư — cho một bảng mã vẫn
tạo, qua `CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE}`. Đó là kết luận
nguy hiểm nhất trong bốn nhóm, vì nó mời người đọc đi xoá một bảng đang dùng.

### `legacy` — 0 bảng

_(không có)_

### `declared` — 0 bảng

_(không có)_

### `target-only` — 9 bảng

- `dataset_lineage` — backend/migrations/001_create_production_schema.sql
- `dataset_samples_mapping` — backend/migrations/001_create_production_schema.sql
- `dataset_splits` — backend/migrations/001_create_production_schema.sql
- `dataset_versions` — backend/migrations/001_create_production_schema.sql
- `datasets` — backend/migrations/001_create_production_schema.sql
- `experiment_metrics` — backend/migrations/001_create_production_schema.sql, backend/migrations/002_mvp_schema.sql
- `experiments` — backend/migrations/001_create_production_schema.sql, backend/migrations/002_mvp_schema.sql
- `model_deployments` — backend/migrations/001_create_production_schema.sql
- `model_versions` — backend/migrations/001_create_production_schema.sql, backend/migrations/002_mvp_schema.sql

### `historical` — 1 bảng

- `user_profiles` — backup.sql

## As-built theo miền (một miền = một diagram)


### PDM-A_tenant_iam_authz  (17 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `api_keys` | 12 | ✓ | ✓ | 1 |
| `memberships` | 14 | ✓ | ✓ | 1 |
| `password_reset_tokens` | 5 | — | — | 0 |
| `permissions` | 9 | — | — | 0 |
| `projects` | 10 | ✓ | ✓ | 1 |
| `refresh_tokens` | 8 | — | — | 0 |
| `role_assignments` | 9 | — | — | 0 |
| `role_permissions` | 3 | — | — | 0 |
| `roles` | 12 | ✓ | ✓ | 1 |
| `tenant_invitations` | 11 | ✓ | ✓ | 1 |
| `tenants` | 20 | ✓ | ✓ | 1 |
| `user_action_passcodes` | 8 | — | — | 0 |
| `user_recovery_codes` | 4 | — | — | 0 |
| `user_totp` | 5 | — | — | 0 |
| `users` | 15 | ✓ | ✓ | 1 |
| `verification_codes` | 11 | — | — | 0 |
| `workspaces` | 9 | ✓ | ✓ | 1 |

### PDM-B_danh_muc_vsl  (12 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `classes` | 23 | ✓ | ✓ | 1 |
| `community_dialects` | 9 | — | — | 0 |
| `community_profiles` | 8 | — | — | 0 |
| `community_versions` | 6 | — | — | 0 |
| `dialect_aliases` | 5 | ✓ | ✓ | 1 |
| `dialects` | 14 | ✓ | ✓ | 1 |
| `languages` | 2 | — | — | 0 |
| `recognition_profiles` | 7 | ✓ | ✓ | 1 |
| `regions` | 8 | — | — | 0 |
| `registry_versions` | 7 | ✓ | ✓ | 1 |
| `vocabulary_groups` | 6 | ✓ | ✓ | 1 |
| `vocabulary_registry_meta` | 3 | ✓ | ✓ | 1 |

### PDM-C_nguoi_ky_phien_thu_mau  (6 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `capture_sessions` | 11 | ✓ | ✓ | 1 |
| `raw_uploads` | 21 | ✓ | ✓ | 1 |
| `samples` | 42 | ✓ | ✓ | 1 |
| `signer_aliases` | 6 | ✓ | ✓ | 1 |
| `signer_consents` | 11 | ✓ | ✓ | 1 |
| `signers` | 9 | ✓ | ✓ | 1 |

### PDM-D_huan_luyen_hien_vat  (3 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `training_job_classes` | 5 | ✓ | ✓ | 1 |
| `training_jobs` | 19 | ✓ | ✓ | 1 |
| `training_metrics` | 9 | ✓ | ✓ | 1 |

### PDM-E_phap_ly_dong_thuan_kiem_toan  (5 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `audit_log` | 10 | ✓ | ✓ | 1 |
| `legal_document_drafts` | 21 | — | — | 0 |
| `legal_document_events` | 12 | — | — | 0 |
| `legal_documents` | 21 | — | — | 0 |
| `user_consents` | 11 | — | — | 0 |

### PDM-F_control_plane  (15 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `event_outbox` | 11 | ✓ | ✓ | 1 |
| `google_sheets_sync_status` | 7 | — | — | 0 |
| `notifications` | 10 | ✓ | ✓ | 1 |
| `plans` | 25 | — | — | 0 |
| `platform_settings` | 4 | — | — | 0 |
| `schema_migrations` | 6 | — | — | 0 |
| `sot_authorized_keys` | 7 | — | — | 0 |
| `support_messages` | 9 | ✓ | ✓ | 1 |
| `support_tickets` | 10 | ✓ | ✓ | 1 |
| `tenant_exports` | 13 | ✓ | ✓ | 1 |
| `tenant_purges` | 10 | — | — | 0 |
| `tenant_subscriptions` | 15 | ✓ | ✓ | 1 |
| `tenant_usage_daily` | 5 | ✓ | ✓ | 1 |
| `webhook_deliveries` | 12 | ✓ | ✓ | 1 |
| `webhook_endpoints` | 14 | ✓ | ✓ | 1 |

### PDM-Z_chua_phan_loai  (1 bảng)

| Bảng | Cột | RLS | FORCE | Policy |
|---|---|---|---|---|
| `project_allocations` | 7 | ✓ | ✓ | 1 |
