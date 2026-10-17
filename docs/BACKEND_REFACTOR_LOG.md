# Backend Refactor Log

Tài liệu này ghi lại từng đợt sắp xếp backend. Mỗi đợt phải mô tả phạm vi,
file thay đổi, contract runtime được giữ nguyên, cách kiểm tra và cách hoàn tác.

## 2026-10-18 — BR-001: Tách application composition khỏi `main.py`

### Mục tiêu

- Làm `app/main.py` thành ASGI entry point tối thiểu.
- Tách việc tạo FastAPI app, lifecycle, đăng ký route và middleware thành các
  ranh giới riêng.
- Không đổi nghiệp vụ, API công khai, queue, database schema hoặc logic training.

### Thay đổi

- Thêm `app/bootstrap/app_factory.py` để tạo và cấu hình FastAPI application.
- Thêm `app/bootstrap/lifecycle.py` chứa startup, TTS prewarm, khôi phục training
  jobs và shutdown.
- Thêm `app/bootstrap/routing.py` làm nơi duy nhất đăng ký legacy routes và
  `/api/v1` routes.
- Chuyển CSRF middleware sang `app/core/middleware/csrf.py`.
- Chuyển activity/IP block middleware sang `app/core/middleware/activity.py`.
- Chuyển endpoint `/api/v1/presence` sang `app/routers/presence.py`.
- Thu gọn `app/main.py`; vẫn re-export các symbol cũ để giảm rủi ro làm hỏng
  code hoặc test đang import trực tiếp từ `app.main`.
- Thêm `tests/test_app_composition.py` kiểm tra route compatibility và lifecycle
  registration.

### Contract được giữ nguyên

- ASGI entry point vẫn là `app.main:app`.
- Các unversioned route cũ vẫn tồn tại.
- Auth tiếp tục chỉ được đăng ký dưới `/api/v1/auth`.
- `/api/v1/presence` giữ nguyên URL và HTTP 204.
- Thứ tự middleware giữ nguyên: activity bọc CSRF, CSRF bọc CORS.
- Startup vẫn kiểm tra production secrets, khởi tạo DB/admin, realtime client,
  TTS và khôi phục training jobs.
- Shutdown vẫn đóng realtime HTTP client và TTS resources.

### Kiểm tra

- AST parse thành công cho 7 file Python được tạo hoặc thay đổi.
- CodeGraph đọc lại source mới và xác nhận wiring route/lifecycle/middleware.
- Đã thêm regression tests cho route layout và lifecycle handlers.
- Chưa chạy được pytest trên host: Python hệ thống dùng Pydantic 2 trong khi
  project khóa `pydantic==1.10.11`; Docker daemon cũng chưa chạy tại thời điểm
  kiểm tra. Cần chạy lại test trong container hoặc environment của project.

### Hoàn tác

- Khôi phục `app/main.py` trước BR-001.
- Xóa `app/bootstrap/`, `app/core/middleware/`, `app/routers/presence.py` và
  `tests/test_app_composition.py`.
- Không cần hoàn tác dữ liệu hoặc database vì đợt này không thay đổi persistence.

## 2026-10-18 — BR-002: Thiết lập ranh giới hạ tầng PostgreSQL

### Mục tiêu

- Đưa kết nối PostgreSQL và connection pool ra khỏi `storage/` tổng quát.
- Tạo hướng phụ thuộc rõ ràng từ application code tới infrastructure adapter.
- Giữ tương thích cho code/test còn import đường dẫn cũ.

### Thay đổi

- Thêm `app/infrastructure/database/connection.py` làm nguồn sự thật mới cho:
  - kết nối PostgreSQL có fallback hostname;
  - process-local threaded connection pool;
  - fork-safe pool rebuild cho Celery;
  - borrow/return pooled connection.
- Thêm package `app/infrastructure/` và `app/infrastructure/database/`.
- Cập nhật các module runtime sau sang đường dẫn infrastructure mới:
  - `app/auth.py`;
  - `app/activity.py`;
  - `app/sync_tasks.py`;
  - `app/routers/admin.py`;
  - `app/routers/health.py`;
  - `app/storage/metadata_db.py`;
  - `app/storage/experiment_tracking_db.py`.
- Giữ `app/storage/postgres_connection.py` làm compatibility module alias. Import
  cũ và import mới cùng trỏ đến một module object, tránh tách đôi pool state.
- Thêm `tests/test_database_connection_boundary.py` kiểm tra identity của legacy
  module, connection function và pool function.

### Contract được giữ nguyên

- Không đổi `DATABASE_URL`, hostname fallback hoặc connect timeout.
- Không đổi pool min/max, application name hoặc quy tắc rebuild sau fork.
- Không đổi SQL, transaction boundary hay database schema.
- Import cũ `app.storage.postgres_connection` vẫn hoạt động.
- Test/consumer monkeypatch module cũ vẫn tác động lên module infrastructure mới.

### Kiểm tra

- CodeGraph xác nhận 13 call site `connect_postgres` và các call site pooled
  connection nội bộ đã trỏ sang infrastructure adapter.
- `rg` xác nhận không còn runtime import đường dẫn cũ ngoài compatibility module.
- AST parse thành công cho infrastructure package, compatibility module và test.
- Chưa chạy pytest runtime vì Docker daemon vẫn chưa hoạt động và Python host
  không dùng dependency versions của project.

### Hoàn tác

- Đổi các import trên về `app.storage.postgres_connection`.
- Xóa compatibility alias được thêm vào module cũ.
- Xóa `app/infrastructure/` và test boundary mới.
- Không cần hoàn tác dữ liệu hoặc database.

## 2026-10-18 — BR-003: Tạo public boundary cho identity/auth

### Mục tiêu

- Cho router và application code phụ thuộc vào bounded context `identity`, không
  phụ thuộc trực tiếp vào các file triển khai auth/cookie/rate-limit/email.
- Chuẩn bị cho việc tách repository, token, password và session ở các đợt sau mà
  không cần sửa import trên toàn bộ router lần nữa.
- Giữ nguyên callable identity để FastAPI dependency overrides và test cũ không
  bị phá vỡ.

### Thay đổi

- Thêm `app/modules/identity/api.py` làm facade công khai cho:
  - account creation và authentication;
  - access/refresh token;
  - current-user/admin dependencies;
  - auth cookies và CSRF token;
  - login/register/reset rate limiting;
  - password-reset email.
- Thêm `app/modules/identity/__init__.py` với explicit `__all__`.
- Chuyển các router `auth`, `admin`, `classes`, `dataset`, `upload`, `training`
  sang import qua `app.modules.identity`.
- Chuyển WebSocket cookie lookup trong training router sang identity boundary.
- Giữ implementation hiện tại trong các legacy modules; facade trả chính các
  function object cũ, không tạo wrapper hoặc thay đổi dependency identity.
- Thêm `tests/test_identity_module_boundary.py` kiểm tra callable identity.

### Contract được giữ nguyên

- Không đổi auth URL, request/response schema hoặc status code.
- Không đổi JWT payload, cookie name/path, CSRF, refresh-token rotation hoặc
  password-reset behavior.
- `app.auth` và các import cũ vẫn hoạt động cho test/consumer hiện tại.
- FastAPI `dependency_overrides[get_current_user]` tiếp tục dùng cùng function
  object trước và sau refactor.

### Kiểm tra

- CodeGraph xác nhận toàn bộ runtime router consumer đã đi qua identity facade.
- `rg` xác nhận không còn direct `app.auth` import trong routers.
- AST parse thành công cho module boundary, auth router và regression test.
- Chưa chạy pytest runtime vì Docker daemon chưa hoạt động và Python host dùng
  dependency versions khác project.

### Hoàn tác

- Đổi import trong các router về các legacy modules ban đầu.
- Xóa `app/modules/` và regression test của BR-003.
- Không cần hoàn tác database, cookie hoặc token.
