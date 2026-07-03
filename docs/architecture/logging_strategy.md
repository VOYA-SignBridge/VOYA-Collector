# Chiến Lược Logging Toàn Diện (Enterprise & AI Lifecycle)

Đối với một AI SaaS Platform như SignBridge, hệ thống ghi nhật ký (Logging) không chỉ dùng để debug lỗi mà còn phục vụ cho việc kiểm toán (Audit), bảo mật (Security), thanh toán (Billing) và theo dõi vòng đời của AI (AI Lifecycle).

## 1. Hệ Thống 7-Layer Logs
Chúng ta thiết kế 7 bảng log độc lập để lưu trữ các loại log theo mục đích khác nhau. Việc tách riêng giúp tối ưu hóa truy vấn, áp dụng vòng đời dữ liệu (retention policies) khác nhau và dễ dàng phân quyền truy cập.

```text
LOGS
│
├── AUDIT_LOGS          (Truy vết hành vi: CRUD, Publish, Deploy, Role Change...)
│
├── ACCESS_LOGS         (Lưu lượng mạng: Thông tin HTTP Request, Response Code, Latency)
│
├── AUTH_LOGS           (Truy cập tài khoản: Login, Logout, Refresh Token, MFA)
│
├── AUTHORIZATION_LOGS  (Quyết định phân quyền: Lịch sử Casbin Allow/Deny)
│
├── SECURITY_LOGS       (Cảnh báo an ninh: Attack, JWT Invalid, XSS, Rate Limit hits)
│
├── BUSINESS_EVENTS     (Sự kiện nghiệp vụ: Inference, Upload Model, Billing, Quota Usage)
│
└── SYSTEM_LOG_FILES    (Trạng thái hệ thống: Redis, RabbitMQ, MinIO, Celery Worker...)
```

## 2. Tracking AI Lifecycle (Nhật ký Vòng đời AI)
SignBridge là một AI SaaS, do đó chúng ta theo dõi sát sao vòng đời của các thành phần AI (Model, Inference, Dataset). Đây là xương sống để giải đáp các bài toán vận hành và truy xuất trách nhiệm.

### 2.1. MODEL_EVENTS (Lịch sử Vòng đời Model)
- `UPLOAD_MODEL`
- `REGISTER_MODEL`
- `DEPLOY_MODEL`
- `ROLLBACK_MODEL`
- `DELETE_MODEL`

### 2.2. INFERENCE_EVENTS (Lịch sử Suy luận)
- `REQUEST_RECEIVED`
- `INFERENCE_STARTED`
- `INFERENCE_COMPLETED`
- `INFERENCE_FAILED`

### 2.3. DATASET_EVENTS (Lịch sử Tập dữ liệu)
- `IMPORT`
- `EXPORT`
- `DELETE`
- `ANNOTATION_COMPLETED`

## 3. Các Use Cases Thực Tiễn
Với kiến trúc trên, hệ thống có khả năng truy vấn chéo (dựa vào `tenant_id`, `workspace_id`, `trace_id`) để trả lời ngay lập tức các câu hỏi sau:

1. **"Ai đã deploy model nhận diện ngôn ngữ ký hiệu này lên production?"** 
   *(Tra cứu trong `AUDIT_LOGS` hoặc `BUSINESS_EVENTS` với event `DEPLOY_MODEL`)*
2. **"Model nào đang chạy và phục vụ request trong khoảng 14:00–15:00 ngày hôm qua?"** 
   *(Tra cứu trong `MODEL_EVENTS` và `ACCESS_LOGS`)*
3. **"Có bao nhiêu quá trình inference thất bại sau khi chúng ta deploy phiên bản Model V2.1 mới?"** 
   *(Truy vấn đếm `INFERENCE_FAILED` sau mốc thời gian diễn ra `DEPLOY_MODEL`)*
4. **"Tenant nào đang sử dụng nhiều tài nguyên GPU nhất trong tuần qua?"** 
   *(Tra cứu tổng thời gian chạy trong `INFERENCE_EVENTS` kết hợp `BUSINESS_EVENTS`)*

## 4. Kiến trúc Lưu trữ
- **PostgreSQL Partitioning**: Các bảng log có lưu lượng lớn như `ACCESS_LOGS`, `AUDIT_LOGS` sẽ được phân mảnh (partition) theo tháng (Ví dụ: `audit_logs_2026_07`).
- **Trace ID**: Mỗi request vào hệ thống (từ Nginx hoặc FastAPI Middleware) sẽ sinh ra một `trace_id` duy nhất (UUID). Giá trị này sẽ truyền xuyên suốt qua tất cả 7 lớp log để nối chuỗi sự kiện.
