# 📋 Báo Cáo Hoàn Thành Giai Đoạn 1 — Nền Móng Database & Core

> **Roadmap:** v2 — [`erd_v2_unified_design.md`](../database/erd_v2_unified_design.md) §7.3
> **Thời gian thực hiện:** 2026-07-04 (kế hoạch: tuần 1–2 — về đích sớm)
> **Nhánh:** `deploy_ctu_ver2.0` · **Commits:** `aa7388d`, `66682de`, `4fcb1e5` (+ báo cáo này)
> **Trạng thái Gate:** ✅ **ĐẠT** — `alembic upgrade → downgrade → upgrade` sạch trên DB trống · guard môi trường hoạt động · seed idempotent · **pytest 47 passed, 0 skipped** (characterization GĐ 0 vẫn xanh)

---

## 1. Mục tiêu vs Kết quả (theo §7.3 Roadmap v2)

| # | Mục tiêu | Kết quả |
|---|---|---|
| ① | ORM 37 bảng vào `orm/` | ✅ `Base.metadata` = đúng 37 bảng / 8 domain |
| ② | Alembic Initial Migration theo schema chốt | ✅ Revision `af7fe2a719fc`, chu trình upgrade/downgrade/upgrade sạch |
| ③ | Seed: roles, languages, dialects, architectures, quota, legal v1, Casbin policies | ✅ Seed idempotent (lần 1: 16 dòng, lần 2: 0) + `rbac_model.conf` + `rbac_policy_seed.csv` |
| ④ | `core/` (config + guard §12.1, security, exceptions, logging, constants, session) | ✅ 6 module, không đụng legacy `app/config.py` |
| ⑤ | `docker-compose.dev.yml` trọn stack local | ✅ Đang chạy: Postgres 5433, Redis 6380, MinIO 9100/9101 |
| ⑥ | Unit tests core + component tests ORM | ✅ 25 test mới, chạy trên Postgres dev thật |

## 2. Chi tiết bàn giao

### 2.1. `backend/app/core/` — 6 module + 2 artifact RBAC
- **`config.py`**: Settings v2 (pydantic) — mọi resource id từ env; **guard fail-fast**:
  `ENVIRONMENT=dev|staging` cầm id nằm trong `PROD_RESOURCE_IDS` → `EnvironmentGuardError`
  từ chối khởi động; `prod` mà còn secret default dev cũng bị chặn. Google tích hợp **OFF mặc định ở dev**.
- **`security.py`**: bcrypt; JWT access ngắn hạn (15'); refresh token opaque **chỉ lưu SHA-256**;
  `make_user_ref()` = pepper hash 12 hex (§11.3).
- **`exceptions.py`** (AppException + Global Handler — không lộ stack trace),
  **`logging.py`** (Loguru: console + JSONL xoay ngày), **`constants.py`** (toàn bộ enum domain),
  **`session.py`** (pool giới hạn — trỏ **database riêng `signbridge_v2`**, không đụng `signdb` legacy).
- **`rbac_model.conf` + `rbac_policy_seed.csv`**: model Casbin domain-RBAC + policies sinh từ
  ma trận §9.4 — GĐ 2 chỉ việc nạp vào enforcer.

### 2.2. `backend/app/orm/` — 37 bảng, các ràng buộc sống còn có mặt trong DDL
`UNIQUE(dataset_id, version_number)`, `UNIQUE(model_id, version)`, `UNIQUE(training_job_id)`,
partial unique `legal_documents(document_type) WHERE is_active`,
`CHECK models: platform ⇒ architecture_id NOT NULL`, `UNIQUE sample_media.checksum`,
composite index `(status, created_at)` cho `collection_sessions` & `training_jobs`,
schema tinh giản §11.4 (`sample_sync_status` chỉ còn `gdrive_synced`; `project_sheet_exports`
không còn bộ đếm rotation) + `raw_uploads.size_bytes`.

### 2.3. Alembic + Seed + Dev stack
- `backend/alembic.ini` + `migrations/env.py` (URL từ core config, override được bằng
  `ALEMBIC_DATABASE_URL`) + revision `af7fe2a719fc`.
- `app/orm/seed.py` (chạy: `python -m app.orm.seed`): 2 system roles, `vn` + 3 phương ngữ,
  **3 MODEL_ARCHITECTURES** (lstm_v1 / yolov8_pose / timesformer, kèm default hyperparams
  + trainer_entrypoint), 4 log categories, 3 legal docs v1.
- `docker-compose.dev.yml` + `backend/.env.v2.example` (tài liệu hóa mọi biến).

### 2.4. Tests (25 mới — tổng suite 47 passed)
| Nhóm | Cases |
|---|---|
| Unit `core/config` (9) | dev cầm id prod → từ chối; staging cũng được bảo vệ; prod thiếu secret thật → từ chối; prod đủ cấu hình → chạy; ráp database_url |
| Unit `core/security` (8) | bcrypt roundtrip; JWT hết hạn/giả chữ ký bị loại; refresh hash 64-hex ổn định; user_ref 12-hex ổn định, khác nhau giữa users |
| Component ORM (7) | 2 UNIQUE version; CHECK platform-model; external model không cần architecture; partial unique legal (1 active/type, nhiều inactive OK); checksum trùng bị chặn; GDPR soft-delete giữ nguyên FK — chạy trên Postgres dev thật, **transaction-per-test rollback** nên DB không dính rác |
| Seed (1) | chạy 2 lần → lần 2 tạo 0 dòng |

## 3. Sự cố gặp & cách xử (để người sau không dẫm lại)
1. **`alembic.ini` chứa ký tự "Đ"** → configparser Windows đọc cp1252 nổ `UnicodeDecodeError`. Quy tắc: file `.ini` của alembic giữ ASCII thuần.
2. **Seed vỡ FK `dialects → languages`**: ORM v2 chưa khai `relationship()` (giữ lean tới GĐ 3) nên unit-of-work không suy được thứ tự INSERT — phải `flush()` cha trước con trong seed.
3. **`*.csv` toàn cục trong `.gitignore` nuốt `rbac_policy_seed.csv`** → whitelist `!backend/app/**/*.csv` (file policy là code, không phải dataset).

## 4. Quyết định kỹ thuật ghi nhận
- **V2 dùng database riêng `signbridge_v2`** (không chung `signdb` legacy) — tránh đụng độ tên bảng
  (`samples`, `classes`… trùng tên khác cột) trong suốt thời kỳ Strangler Fig; script di trú dữ liệu
  legacy → v2 thuộc GĐ 6.
- ORM **chưa khai relationship** — thêm ở GĐ 3 khi repositories cần, giữ models thuần schema.

## 5. Tồn đọng & bàn giao cho GĐ 2 (Lát cắt Auth & Tenancy)
| Hạng mục | Ghi chú |
|---|---|
| Casbin enforcer + adapter | Nạp `rbac_model.conf` + `rbac_policy_seed.csv` (đã sẵn); bảng `casbin_rule` do adapter tự tạo |
| Chuỗi 6 middleware (`cors → request_id → rate_limiter → auth_guard → tenant_context → authorization_guard`) | File rỗng chờ sẵn trong `app/middleware/` |
| Auth slice (register/login/refresh/revoke + Google OAuth) | Dùng `core/security.py` + bảng `user_sessions`; **kèm test "login sai mật khẩu → 401"** (nợ từ GĐ 0 — thiếu DB phải FAIL) |
| Workspaces/Projects/Membership + Consent Gate (§8.3) | Repos/services/routers v1 tương ứng |
| Legal content v1 lên MinIO | Seed đã trỏ key `legal-docs/POL-*/v1.md`; file .md thật upload qua `legal_service.publish()` |
| Test AuthZ sinh từ ma trận §9.4 | Mỗi ô trống = 1 case 403 (`security_testing/authz_bypass.py`) |

**Gate GĐ 2:** flow API register → ký consent → tạo workspace → mời member chạy đầu-cuối; mọi ô trống ma trận §9.4 trả đúng 403.
