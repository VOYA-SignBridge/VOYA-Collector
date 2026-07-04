# 📋 Báo Cáo Hoàn Thành Giai Đoạn 0 — Chốt Nợ & Lưới An Toàn

> **Roadmap:** v2 — [`erd_v2_unified_design.md`](../database/erd_v2_unified_design.md) §7.3
> **Thời gian thực hiện:** 2026-07-03 → 2026-07-04
> **Nhánh:** `deploy_ctu_ver2.0` · **Commits:** `63229dc` → `7954f0d` (5 commits)
> **Trạng thái Gate:** ✅ **ĐẠT** — pytest `21 passed, 0 skipped` · Vitest `2 passed` · 5 tài liệu hết mâu thuẫn schema

---

## 1. Mục tiêu Giai đoạn 0 (theo §7.3 Roadmap v2)

| # | Mục tiêu | Kết quả |
|---|---|---|
| ① | Duyệt & chốt ERD v2 | ✅ 8 ADR + 37 bảng được chốt trong `erd_v2_unified_design.md` |
| ② | Đồng bộ `database_dictionary.md` + 4 tài liệu theo phân công §6 | ✅ Hoàn thành (chi tiết mục 2) |
| ③ | Cấu hình pytest + 4 Characterization Tests cho API legacy | ✅ 21 tests xanh |
| ④ | Cài Vitest thật + `setup.ts` + script `test` | ✅ 2 tests xanh |
| ⑤ | Commit 166 file đã xóa + sườn thư mục mới (tách bạch) | ✅ 5 commits |

---

## 2. Công việc đã hoàn thành

### 2.1. Hợp nhất tài liệu (Documentation Alignment)

- **`docs/database/erd_v2_unified_design.md`** (MỚI — bản quyết định thiết kế trung tâm, 12 mục):
  8 ADR phân xử mọi mâu thuẫn giữa các tài liệu cũ; ERD v2 **37 bảng / 8 domain**
  (tách `DATASETS` → `DATASET_VERSIONS`, tách `MODELS` → 4 bảng registry, thêm `WORKSPACE_QUOTAS`);
  đặc tả Casbin RBAC 3 phạm vi + ma trận phân quyền; module Pháp lý & Cookie Consent;
  Sheets **stateless snapshot** + `user_ref` giả danh hóa; upload **presigned direct-to-MinIO**;
  tách môi trường dev/prod + `dev_refresh`/`dev_promote`; Roadmap v2 (GĐ 0–6) + ma trận bao phủ test §7.5.
- **`database_dictionary.md`**: trở thành **Source of Truth duy nhất về schema** — thay toàn bộ ERD
  + đặc tả 37 bảng; cập nhật các mục phân tích (Pipeline, Use Case 4, Edge Case 4, luồng 6.1/6.2)
  hết tham chiếu bảng ma (`DATASET_ITEMS`, Cloudinary, `sheets_synced` per-row).
- **`SignBridge_Architecture.md`** §3.3: xóa ~660 dòng ERD nhúng trùng lặp, thay bằng tham chiếu
  (file gọn từ 1086 → 429 dòng).
- **`Refactore_SignBridge.md`**: sửa đánh số task trùng (2.13×2 → 2.13–2.17; 6.7×2 → 6.7–6.10),
  dòng `logging.py` lặp, vị trí test chốt về `tests/` ở root; §5.0.4 trỏ về bản chốt v2.
- **`erd_audit_report.md`**: thêm bảng Kết luận cuối — trạng thái từng gap (Áp dụng / Áp dụng một phần / Hoãn) theo ADR.
- **`gdrive_suffix_2_0.md`**: đánh dấu **DEPRECATED** (nguyên nhân gốc được xử bằng tách môi trường §12).

### 2.2. Khôi phục app legacy (điều kiện sống của Strangler Fig)

Phát hiện working tree **gãy giữa chừng refactor**: `main.py` bị làm rỗng, `app/storage/` bị xóa
trong khi routers legacy vẫn import `app.storage.*` (và chính các module đã move sang
`app/core/storage/` cũng tự import theo đường cũ). Xử lý:

- Khôi phục `backend/app/main.py` từ HEAD.
- Viết shim [`backend/app/storage/__init__.py`](../../backend/app/storage/__init__.py):
  alias qua `sys.modules` — hai đường import trỏ về **cùng một module object**
  (cover cả helper gạch dưới `_execute`, `_get_conn`). Gỡ ở GĐ 6 cùng legacy.
- Loại `experiment_tracking_db.py` khỏi shim: module chết, có bug import sẵn
  (`from typing import UUID`), không nơi nào dùng.
- **Kết quả:** app legacy sống lại với **129 routes**.

### 2.3. Lưới an toàn Backend (pytest)

- `pytest.ini` ở root: `testpaths=tests`, `pythonpath=backend`.
- `tests/conftest.py`: fixture `client` **không chạy lifespan** (không init DB / TTS warm-up khi test).
- 4 file Characterization Tests tại `tests/functional_testing/integration_testing/backend_api/`,
  assertions viết theo **hành vi thực đã probe** (không đoán):

| File | Chốt hành vi |
|---|---|
| `test_auth_flow.py` | login thiếu field → 422 (đúng field bị thiếu); `/me` không token / token rác → 401 |
| `test_label_crud.py` | `GET /classes/list` → 200 + `{count, items}` từ CSV; alias `/classes` ≡ `/api/v1/classes`; PUT/DELETE không token → 401 |
| `test_upload_flow.py` | upload không token → 401; `OPTIONS /upload/camera` mở (CORS preflight); **route inventory** — 8 route FE đang phụ thuộc không được biến mất |
| `test_trash_flow.py` | 6 endpoint trash đều đòi auth; `/health/live` → 200 alive |

- **Nguyên tắc đã chốt qua review:** GĐ 0 = 100% không cần hạ tầng. Case `login sai mật khẩu → 401`
  (cần Postgres) được **dời sang GĐ 2** (ghi tại §7.5) — ở đó thiếu DB phải **FAIL chứ không skip**;
  toàn bộ máy móc auto-skip đã gỡ bỏ.
- 4 script ad-hoc cũ (`test_auth.py`, `test_gdrive.py`…) chuyển sang `scripts/manual_checks/`
  (chúng gọi service thật ngay lúc import — không phải test).

### 2.4. Lưới an toàn Frontend (Vitest)

- Cài `vitest` + `jsdom` + `@testing-library/react@16` (tương thích React 19) + `jest-dom`.
- `src/tests/setup.ts` (jest-dom matchers + cleanup); scripts `test` / `test:watch`.
- Smoke test `Button.smoke.test.tsx` chứng minh pipeline chạy: render children + disabled khi loading.

### 2.5. Sửa lỗi hạ tầng repo phát hiện trong lúc làm

- 🔴 **`.gitignore` có `*.md` và `*.txt` toàn cục** → toàn bộ tài liệu thiết kế chưa từng được
  version control (mất máy = mất trắng tri thức). Đã gỡ 2 pattern, re-include `docs/**`,
  commit toàn bộ docs vào git.
- Ignore tường minh các thư mục runtime: `logs/`, `_tmp/`, `signbridge-prod/`, `backend/secrets/`, `backend/static/`.
- `backend/requirements-test.txt` (nạn nhân của `*.txt`) đã được track.

---

## 3. Danh sách Commits

| Commit | Nội dung |
|---|---|
| `63229dc` | chore: xóa 169 file rác/legacy (−56.448 dòng) — patch scripts, backups, file đã di dời |
| `fa52f96` | docs: ERD v2 + đồng bộ toàn bộ tài liệu kiến trúc + fix `.gitignore` docs |
| `2ef3d68` | test+scaffold: lưới an toàn pytest/Vitest + shim legacy + sườn kiến trúc v2 |
| `074ee15` | chore: ignore thư mục runtime + track `requirements-test.txt` |
| `7954f0d` | test: GĐ 0 phải infrastructure-free — dời case DB sang GĐ 2, gỡ auto-skip |

## 4. Kết quả kiểm thử cuối cùng

```
Backend :  ./.venv/Scripts/python -m pytest   →  21 passed, 0 skipped  (0.23s)
Frontend:  npm test (frontend/)               →  2 passed              (~6s)
```

Môi trường chạy: venv Python 3.11 tại `.venv/` (KHÔNG dùng `.venv_py313_backup` — pydantic v1
không tương thích Python 3.13; IDE cần trỏ interpreter về `.venv\Scripts\python.exe`).

## 5. Tồn đọng & bàn giao cho GĐ 1

| Hạng mục | Ghi chú |
|---|---|
| `backend/app/orm/` đang rỗng | GĐ 1 lấp bằng ORM models 37 bảng (git không track thư mục rỗng) |
| Alembic `versions/` trống | GĐ 1 tạo Initial Migration theo schema chốt (kèm partial unique, composite index, schema tinh giản §11.4) |
| `core/`, `middleware/`, `services/`… là file rỗng | Lấp dần theo lát cắt GĐ 1→4; **không** code trước khi migration xong |
| Test case "login sai mật khẩu → 401" | Nợ có địa chỉ: GĐ 2 Integration Auth (§7.5) |
| Guard môi trường + `docker-compose.dev.yml` | Deliverable GĐ 1 — điều kiện để test DB không bao giờ phải skip |
| Case `Button` loading/disabled | Smoke đã pin hành vi hiện tại; test component đầy đủ thuộc GĐ 5 |

**Bước kế tiếp:** GĐ 1 — Nền móng DB & Core (tuần 1–2), bắt đầu bằng ORM 37 bảng + Alembic Initial Migration + seed (`MODEL_ARCHITECTURES`, Casbin policies §9.4, Legal v1) + `core/config.py` với `ENVIRONMENT` guard fail-fast.
