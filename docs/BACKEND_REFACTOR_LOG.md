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
