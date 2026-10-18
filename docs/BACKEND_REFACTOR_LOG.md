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

## 2026-10-18 — BR-004: Tách auth schemas khỏi HTTP router

### Mục tiêu

- Giữ auth router tập trung vào HTTP orchestration thay vì định nghĩa data model.
- Đặt request/response contract cạnh bounded context `identity`.
- Giữ nguyên OpenAPI schema names và validation constraints.

### Thay đổi

- Thêm `app/modules/identity/schemas.py` chứa:
  - `RegisterRequest`;
  - `LoginRequest`;
  - `UserOut`;
  - `MessageResponse`;
  - `ForgotPasswordRequest`;
  - `ResetPasswordRequest`.
- Export các schema qua `app.modules.identity`.
- Xóa định nghĩa Pydantic model khỏi `routers/auth.py`; router import contract từ
  identity module.
- Loại các import `BaseModel`, `Field`, `datetime`, `Optional` không còn dùng ở
  router.
- Thêm `tests/test_identity_schemas.py` bảo vệ các giới hạn username, identifier
  và password đã tồn tại trước refactor.

### Contract được giữ nguyên

- Tên Pydantic classes và field names không đổi.
- Min/max length của toàn bộ auth payload không đổi.
- Response model của register/login/refresh/logout/me/reset không đổi.
- Không đổi endpoint, status code, cookie hoặc token behavior.

### Kiểm tra

- CodeGraph xác nhận các schema trước đó chỉ được sử dụng trong auth router.
- Kiểm tra source xác nhận router không còn định nghĩa Pydantic model.
- AST parse được dùng để kiểm tra cú pháp các file thay đổi.
- Runtime pytest vẫn chờ môi trường dependency của project hoặc Docker daemon.

### Hoàn tác

- Đưa sáu schema class về `routers/auth.py` và khôi phục import Pydantic cũ.
- Xóa `identity/schemas.py`, schema exports và regression test BR-004.

## 2026-10-18 — BR-005: Tách password và access-token primitives

### Mục tiêu

- Di chuyển logic mật khẩu và JWT thuần khỏi legacy `app/auth.py` vào bounded
  context `identity`.
- Giảm trách nhiệm của legacy auth module trước khi tách account repository và
  session persistence ở các đợt tiếp theo.
- Giữ nguyên function object và private compatibility aliases để consumer cũ,
  FastAPI dependency overrides và test hiện hữu không đổi hành vi.

### Thay đổi

- Thêm `app/modules/identity/passwords.py` chứa:
  - bcrypt context;
  - dummy password hash chống username enumeration qua timing;
  - `get_password_hash`;
  - `verify_password`.
- Thêm `app/modules/identity/tokens.py` chứa:
  - HTTP bearer dependency;
  - `create_access_token`;
  - `decode_access_token`.
- `app/auth.py` chuyển sang import các primitive trên và giữ aliases
  `_DUMMY_PASSWORD_HASH`, `_decode_token` cho tương thích ngược.
- Identity facade export `create_access_token` trực tiếp từ token module.
- `app/db.py` lấy password hashing từ identity boundary thay vì legacy auth.
- Chuyển `app/modules/identity/__init__.py` sang lazy exports. Việc này giữ nguyên
  public import path nhưng tránh vòng import trong giai đoạn legacy auth đang
  lần lượt ủy quyền implementation cho identity module.
- Thêm `tests/test_identity_security_primitives.py` kiểm tra callable identity
  và hành vi hash/verify mật khẩu.

### Contract được giữ nguyên

- JWT algorithm, secret, expiry, `iat`, `exp`, `typ` và subject validation không
  đổi.
- Nội dung lỗi 401 cho token hết hạn/không hợp lệ và token thiếu subject không
  đổi.
- Bcrypt scheme và xử lý password/hash rỗng hoặc hash lỗi không đổi.
- `app.auth.create_access_token`, `get_password_hash`, `verify_password`,
  `_decode_token` và `bearer_scheme` vẫn tồn tại và trỏ đúng function/object mới.
- `from app.modules.identity import ...` vẫn là public API của router.

### Kiểm tra

- CodeGraph xác nhận call path của password/token primitive đã đi qua module mới
  và blast radius chỉ gồm các consumer dự kiến.
- CodeGraph xác nhận `decode_access_token` phục vụ ba call site legacy và
  `create_access_token` phục vụ router/facade/legacy auth như trước.
- AST parse thành công cho 7 file Python được thêm hoặc thay đổi.
- `rg` xác nhận các thư viện `CryptContext`, `HTTPBearer`, `JWTError` chỉ còn ở
  primitive modules tương ứng.
- Chưa chạy pytest runtime vì Docker daemon chưa hoạt động và Python host dùng
  dependency versions khác project (Pydantic 2 so với Pydantic 1.10.11 được
  pin trong project).

### Hoàn tác

- Đưa password/token primitive về `app/auth.py`, khôi phục eager exports trong
  `identity/__init__.py` và import cũ trong `identity/api.py`, `app/db.py`.
- Xóa `identity/passwords.py`, `identity/tokens.py` và regression test BR-005.
- Không cần thay đổi database schema hoặc dữ liệu.

## 2026-10-18 — BR-006: Tách account repository khỏi auth orchestration

### Mục tiêu

- Tách SQL đọc/ghi bảng `users` khỏi legacy auth service.
- Đặt normalization và mapping của account row cạnh persistence boundary.
- Giữ validation, password hashing và HTTP error orchestration ngoài repository.

### Thay đổi

- Thêm `app/modules/identity/repository.py` với các hàm:
  - `get_connection`;
  - `normalize_login`;
  - `row_to_user`;
  - `find_user_by_id`;
  - `find_user_by_login`;
  - `insert_user`.
- Chuyển ba câu SQL account (`SELECT by id`, `SELECT by username/email`,
  `INSERT user`) từ `app/auth.py` sang repository.
- Legacy `app/auth.py` giữ wrapper `_fetch_user_by_id`, `_fetch_user_by_login`
  và aliases normalization/row mapping; wrapper truyền `_get_conn` vào
  repository để code/test cũ vẫn có thể override connection factory.
- `create_user` tiếp tục chịu trách nhiệm validation, duplicate check, UUID và
  password hashing, nhưng ủy quyền thao tác insert cho repository.
- Startup admin bootstrap đọc account qua repository thay vì private auth helper.
- Thêm `tests/test_identity_repository_boundary.py` bảo vệ normalization, row
  mapping, empty-login short circuit và legacy aliases.

### Contract được giữ nguyên

- SQL, selected/returned columns, parameter order và transaction context không
  đổi.
- Mỗi connection vẫn được đóng trong `finally`.
- User dictionary giữ nguyên field names, string conversion của `id`, default
  boolean và fallback chuỗi rỗng.
- Username vẫn chỉ trim; email/login vẫn trim và lowercase.
- Status code và message cho validation/duplicate account không đổi.
- Private fetch wrappers trong `app.auth` vẫn tồn tại cho consumer chuyển tiếp.

### Kiểm tra

- CodeGraph xác nhận `create_user → _fetch_user_by_login → find_user_by_login`
  và các call path lookup/insert đều đi qua repository mới.
- CodeGraph blast radius xác nhận repository mới chỉ được dùng bởi auth service
  và startup admin bootstrap như dự kiến.
- AST parse thành công cho auth, db, repository và regression test.
- Source scan xác nhận `app/auth.py` không còn SQL account và chỉ giữ
  `RealDictCursor` cho password-reset/refresh-session logic chưa chuyển.
- Chưa chạy pytest runtime do giới hạn môi trường dependency đã ghi ở BR-005.

### Hoàn tác

- Đưa account SQL, normalization và row mapping về `app/auth.py`.
- Khôi phục startup admin import `_fetch_user_by_login` từ legacy auth.
- Xóa `identity/repository.py` và regression test BR-006.
- Không có migration hoặc biến đổi dữ liệu cần hoàn tác.

## 2026-10-18 — BR-007: Tách password-reset và refresh-session workflows

### Mục tiêu

- Hoàn tất đợt sắp xếp `app/auth.py` bằng cách tách hai workflow còn chứa SQL.
- Đặt vòng đời password-reset token và refresh-session token trong bounded
  context `identity`.
- Giữ legacy functions làm lớp tương thích mỏng cho router và consumer cũ.

### Thay đổi

- Thêm `app/modules/identity/password_reset.py` chứa:
  - SHA-256 reset-token hashing;
  - phát hành và lưu reset token;
  - kiểm tra expiry/used state;
  - cập nhật password và vô hiệu hóa toàn bộ reset token còn hiệu lực.
- Thêm `app/modules/identity/sessions.py` chứa:
  - SHA-256 refresh-token hashing;
  - phát hành refresh token;
  - rotation trong transaction;
  - best-effort revocation khi logout.
- `app/auth.py` giữ các public function cũ dưới dạng wrapper, truyền rõ
  user lookup và connection factory vào workflow mới.
- Giữ `_hash_reset_token` và `_hash_token` làm aliases tương thích.
- Thêm `tests/test_identity_session_boundaries.py` kiểm tra hash contract và các
  dependency injection points của legacy wrappers.

### Contract được giữ nguyên

- Độ dài entropy của reset token (`token_urlsafe(32)`) và refresh token
  (`token_urlsafe(48)`) không đổi.
- Expiry settings, timezone normalization, SQL, parameter order và transaction
  boundary không đổi.
- Refresh rotation vẫn kiểm tra revoked/expired/inactive user trước khi revoke
  token cũ và insert token mới trong cùng transaction.
- Password reset vẫn vô hiệu hóa mọi reset token chưa dùng của cùng user.
- Logout revocation vẫn best-effort và không phát sinh lỗi ra caller.
- Router/facade tiếp tục gọi đúng các public function trong `app.auth`.

### Kiểm tra

- Docker regression trước BR-007: 8/8 test refactor pass.
- Docker backend suite trong đúng Compose network: 182 pass, 5 fail ngoài phạm
  vi auth do thiếu research artifacts/config trong repository hiện tại.
- CodeGraph được dùng để xác nhận blast radius và toàn bộ caller của reset/
  refresh workflows trước khi di chuyển.
- Docker regression BR-001 đến BR-007: 13 pass.
- Docker training/API lifecycle không phụ thuộc provenance artifacts: 23 pass,
  8 provenance cases được deselect có chủ đích.
- Regression test BR-007 bảo vệ legacy aliases, validation short circuit và
  connection/user-lookup injection để consumer cũ tiếp tục override dependency.

### Lỗi baseline ngoài phạm vi

- `config/legacy_vocabulary_mapping.json` không tồn tại trong HEAD hiện tại.
- Không có released dataset manifest cho frozen-artifact suite.
- Test Phase 3.5 vẫn tham chiếu `scripts/report_dataset_coverage.py` ở path cũ;
  implementation đã được chuyển sang `scripts/dataset/`.
- Hai provenance assertions phụ thuộc các artifact ở trên nên không đạt.

### Hoàn tác

- Đưa implementation của reset/refresh functions từ hai module mới về
  `app/auth.py` và khôi phục imports chuẩn thư viện cũ.
- Xóa hai module mới và regression test BR-007.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-008: Đồng bộ test Phase 3.5 với cấu trúc scripts mới

### Mục tiêu

- Sửa regression test còn tham chiếu các script ở vị trí trước khi tổ chức lại
  thư mục.
- Không thay đổi implementation, database hoặc dataset thật.

### Thay đổi

- `report_dataset_coverage.py` và `validate_pilot_samples.py` được test qua
  `scripts/dataset/`.
- `quarantine_files.py` được test qua `scripts/migration/`.
- Helper `_run` nhận `Path` đầy đủ để mỗi test thể hiện rõ domain của script.

### Kiểm tra

- Chạy `python backend/tests/test_phase35_scripts.py`: 14 pass, 0 fail.
- Test chỉ tạo fixture trong thư mục tạm và xóa thư mục đó khi hoàn tất.
- `git diff --check` thành công.

### Phạm vi dữ liệu

- Không kết nối hoặc thay đổi database.
- Không đọc, ghi, di chuyển hay tạo manifest trong dataset thật.
- Không thay đổi vocabulary mapping hoặc provenance artifacts.

### Hoàn tác

- Khôi phục các path cũ trong `backend/tests/test_phase35_scripts.py`.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-009: Khôi phục vocabulary mapping vào source control

### Mục tiêu

- Đưa `config/legacy_vocabulary_mapping.json` trở lại Git để backend, Docker và
  CI cùng đọc một source of truth thay vì phụ thuộc file local bị ignore.

### Thay đổi

- Thêm ngoại lệ `!config/legacy_vocabulary_mapping.json` ngay sau quy tắc
  `*.json` trong `.gitignore`.
- Track lại mapping có nội dung trùng byte-for-byte với bản ở commit `028c1a0`.

### Kiểm tra

- SHA Git object hiện tại và lịch sử cùng là
  `7a659984e6b5c3a87147c9a127560fca4a6d4543`.
- Pytest vocabulary trong Docker: 10 pass.
- Standalone migration test trên host: 19 pass.
- Toàn bộ backend pytest trong Docker: 197 pass, 5 fail.
  - 1 lỗi do chưa có released dataset manifest.
  - 2 lỗi provenance do thiếu research artifacts/split metadata.
  - 2 lỗi sync do ổ D: đang dùng 96%, kích hoạt backpressure ≥95%; download
    được chủ động dừng trước khi mock trong test được gọi.

### Phạm vi dữ liệu

- Không chạy migration trên dataset thật.
- Không kết nối hoặc thay đổi database.
- Không thay đổi labels, split, manifest hoặc checkpoint.

### Hoàn tác

- Bỏ ngoại lệ mapping khỏi `.gitignore` và untrack file mapping.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-010: Hoàn tất identity service và HTTP dependencies

### Mục tiêu

- Chuyển account orchestration và FastAPI authorization dependencies ra khỏi
  `app/auth.py`.
- Biến `app/auth.py` thành compatibility facade cho consumer và test cũ.
- Giữ nguyên public callable identity, HTTP contract, SQL và session behaviour.

### Thay đổi

- Thêm `app/modules/identity/service.py` chứa:
  - đăng ký và xác thực tài khoản;
  - tra user từ raw access token cho WebSocket;
  - điều phối password reset và refresh-session public workflows.
- Thêm `app/modules/identity/dependencies.py` chứa:
  - cookie-first/Bearer-fallback current-user resolution;
  - force-logout check;
  - authenticated-user và admin dependencies.
- `identity/api.py` export trực tiếp từ các component mới và không còn import
  ngược `app.auth`.
- `app/auth.py` giữ aliases cùng reset/refresh wrappers tương thích; private
  injection points cũ vẫn được bảo vệ bởi regression test.
- Thêm `tests/test_identity_service_dependencies.py` bảo vệ public callable
  identity, account orchestration, dummy password verification và cookie
  precedence mà không mở database.

### Contract được giữ nguyên

- Validation messages/status, email normalization, UUID và duplicate lookup
  order không đổi.
- Unknown/inactive account vẫn chạy dummy bcrypt verify chống timing probe.
- Access cookie vẫn được ưu tiên trước stale Bearer header.
- Force logout vẫn fail-open khi activity/Redis gặp lỗi và trả đúng thông báo
  admin khi marker hợp lệ.
- Router, WebSocket và legacy import tiếp tục nhận cùng callable contract.

### Kiểm tra

- Compile check thành công cho facade, service, dependencies, API và test mới.
- Identity regression: 14 pass.
- Toàn bộ backend pytest trong Docker: 203 pass, 3 fail.
- Ba lỗi còn lại đúng baseline ngoài phạm vi: một released manifest và hai
  provenance assertions phụ thuộc research artifacts.
- Source scan xác nhận code runtime không còn import `app.auth`; chỉ lifecycle
  test cố ý dùng legacy path để bảo vệ compatibility.

### Phạm vi dữ liệu

- Không thay đổi SQL, database schema hoặc dữ liệu database.
- Không chạy dataset migration và không sửa manifest/split/checkpoint.

### Hoàn tác

- Đưa orchestration/dependencies từ hai component mới trở lại `app/auth.py`.
- Khôi phục `identity/api.py` import qua legacy facade và xóa regression BR-010.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-011: Tách web security controls khỏi activity monitor

### Mục tiêu

- Giảm trách nhiệm của `app/activity.py` mà không đổi API admin, middleware hoặc
  identity force-logout contract.
- Tách Redis connection và các security control khỏi logic theo dõi session.

### Thay đổi

- Thêm `infrastructure/redis/connection.py` quản lý activity Redis singleton và
  fail-open khi Redis không khả dụng.
- Thêm `modules/security/ip_controls.py` chứa block/unblock/list IP cùng timed
  TTL metadata.
- Thêm `modules/security/audit_log.py` chứa capped Redis security event log.
- Thêm `modules/security/account_controls.py` chứa:
  - force logout và refresh-token revocation;
  - lock/unlock account;
  - one-off user warning;
  - username/admin lookup cho activity report.
- `app/activity.py` re-export các callable cũ và tiếp tục sở hữu session/GeoIP
  monitoring trong lát cắt này; kích thước giảm từ khoảng 798 xuống 381 dòng.
- Thêm `tests/test_security_module_boundaries.py` bảo vệ facade identity,
  fail-open contract, timed IP payload và force-logout marker/revocation.

### Contract được giữ nguyên

- Redis keys, TTL, JSON payload, log cap và fail-open behaviour không đổi.
- IP block vẫn được middleware áp dụng qua `activity.guard`.
- Lock account vẫn đặt marker, force logout ngay và revoke refresh tokens.
- Router admin/auth cùng identity dependency tiếp tục dùng legacy names qua
  `app.activity`; không đổi route hoặc response contract.
- SQL revoke refresh token và username lookup giữ nguyên câu lệnh/transaction.

### Kiểm tra

- Compile check thành công cho activity facade, Redis infrastructure, security
  components và regression test mới.
- Security/identity/composition regression: 11 pass.
- Toàn bộ backend pytest trong Docker: 207 pass, 3 fail.
- Ba lỗi còn lại đúng baseline ngoài phạm vi: một released manifest và hai
  provenance assertions phụ thuộc research artifacts.
- CodeGraph xác nhận admin → security component → Redis infrastructure call
  path và identity force-logout callers vẫn đi qua facade tương thích.

### Phạm vi dữ liệu

- Không thay đổi database schema hoặc dữ liệu hiện hữu.
- Không chạy dataset migration và không sửa manifest/split/checkpoint.
- Test security dùng fake Redis và không ghi Redis/Postgres thật.

### Hoàn tác

- Đưa Redis/IP/audit/account-control implementation về `app/activity.py`.
- Xóa hai package mới và regression BR-011.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-012: Tách GeoIP và activity session monitor

### Mục tiêu

- Hoàn tất việc thu gọn `app/activity.py` sau BR-011 mà không làm thay đổi API
  middleware, presence hoặc admin activity report.
- Đặt logic GeoIP và theo dõi request/session vào hai component có ranh giới rõ.

### Thay đổi

- Thêm `modules/security/geo.py` chứa:
  - optional MaxMind City/ASN reader;
  - nhận diện IP nội bộ;
  - Redis GeoIP cache và nhãn vị trí hiển thị.
- Thêm `modules/security/activity_monitor.py` chứa:
  - nhận diện browser và user từ access token;
  - request/session heartbeat và rate counter;
  - browser GPS presence;
  - danh sách phiên, anomaly detection và activity report.
- Thu gọn `app/activity.py` thành compatibility facade re-export toàn bộ tên cũ.
- Mở rộng `tests/test_security_module_boundaries.py` để bảo vệ facade aliases,
  private-IP short circuit, health filtering và invalid GPS fail-open.

### Contract được giữ nguyên

- Middleware vẫn gọi `activity.guard`, presence router vẫn gọi
  `activity.record_presence`, admin vẫn gọi `activity.activity_report`.
- Redis key, TTL, rate window, response fields và thông báo anomaly không đổi.
- GeoIP vẫn hoàn toàn offline; thiếu MaxMind DB hoặc Redis vẫn fail-open.
- Các private helper/constant cũ vẫn được alias qua facade để tránh làm vỡ test
  hoặc consumer chưa migration.

### Kiểm tra

- Compile check trong Docker thành công cho facade, GeoIP, activity monitor và
  regression test.
- Security/identity/composition focused regression: 12 pass.
- Toàn bộ backend pytest trên Docker Compose network: 209 pass, 3 fail.
- Ba lỗi còn lại đúng baseline ngoài phạm vi: một released manifest và hai
  provenance assertions phụ thuộc research artifacts.
- Một lần chạy test container ngoài Compose network làm disk-watermark test
  không resolve được hostname `redis`; chạy lại trên đúng network đã pass và
  xác nhận đây là lỗi cấu hình môi trường test, không phải regression.

### Phạm vi dữ liệu

- Không thay đổi SQL, database schema hoặc dữ liệu database.
- Không chạy dataset migration và không sửa manifest/split/checkpoint.
- Test mới dùng fake Redis và không kết nối Redis/Postgres thật.

### Hoàn tác

- Đưa implementation GeoIP/session monitor trở lại `app/activity.py`.
- Xóa hai component mới và các regression assertion BR-012.
- Không có database migration hoặc dữ liệu cần hoàn tác.

## 2026-10-18 — BR-013: Thống nhất Redis và tách rate-limit component

### Mục tiêu

- Loại bỏ Redis singleton trùng lặp trong `app/rate_limit.py`.
- Đặt nghiệp vụ chống brute-force/spam vào security module đúng tầng.
- Giữ nguyên import contract cũ cho consumer chưa migration.

### Thay đổi

- `infrastructure/redis/connection.py` cung cấp tên tổng quát
  `get_redis_client`; `get_activity_client` được giữ làm compatibility alias.
- Thêm `modules/security/rate_limits.py` chứa:
  - xác định client IP sau nginx;
  - fixed-window Redis counter;
  - giới hạn login theo IP và normalized identifier;
  - giới hạn register/forgot/reset theo IP;
  - HTTP 429 cùng `Retry-After` và fail-open behaviour.
- Thu gọn `app/rate_limit.py` thành compatibility facade, bao gồm các public
  callable/constant và private helper aliases cũ.
- Identity API, presence và activity monitor import component mới trực tiếp,
  không đi vòng qua facade.
- Thêm `tests/test_rate_limit_module_boundaries.py` bảo vệ facade identity,
  shared Redis client, key/TTL/reset contract, forwarded IP và fail-open.

### Contract được giữ nguyên

- Redis key prefix, login threshold/window, identifier normalization và generic
  bucket format không đổi.
- HTTP status, thông báo tiếng Việt và `Retry-After` không đổi.
- Redis không khả dụng vẫn cho request đi qua; nginx tiếp tục là lớp giới hạn
  lưu lượng ngoài cùng.
- `app.rate_limit` và exports qua `modules.identity` vẫn dùng được như trước.

### Kiểm tra

- Compile check trong Docker thành công cho infrastructure, component, facade
  và các consumer đã migration.
- Rate-limit/security/identity/composition focused regression: 16 pass.
- Toàn bộ backend pytest trên Docker Compose network: 213 pass, 3 fail.
- Ba lỗi còn lại đúng baseline ngoài phạm vi: một released manifest và hai
  provenance assertions phụ thuộc research artifacts.

### Phạm vi dữ liệu

- Không thay đổi SQL, database schema hoặc dữ liệu database.
- Không chạy dataset migration và không sửa manifest/split/checkpoint.
- Regression test dùng fake Redis; full suite dùng Redis của Docker test
  network theo cấu hình dự án.

### Hoàn tác

- Đưa rate-limit implementation và Redis singleton riêng về
  `app/rate_limit.py`.
- Khôi phục import consumer qua facade, xóa component/test BR-013.
- Không có database migration hoặc dữ liệu cần hoàn tác.
