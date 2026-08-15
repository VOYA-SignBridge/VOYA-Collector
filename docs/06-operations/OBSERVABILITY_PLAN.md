# Kế hoạch quan sát hệ thống (logs / traces / metrics / audit)

Trạng thái: **bản thiết kế đã chốt nguyên tắc, chưa triển khai.**
Ghi lại ngày 2026-07-31, trong lúc merge `feature/vocab-schema-v2` vào `deploy_ctu_ver-2.2.1`.

Kế hoạch này KHÔNG nằm trong phạm vi merge đó. Việc duy nhất của merge là giữ
`logging_config.py` bản deploy (JSON ra stdout) — đúng hướng kế hoạch mô tả.

---

## 1. Nguyên tắc đã chốt

### 1.1 Loki chỉ giữ label cardinality thấp

Loki **chỉ index label**, không index nội dung log. Mỗi tổ hợp label duy nhất là
một *stream* riêng, có chunk riêng trong ingester (RAM) và trên đĩa. Cardinality
của label vì thế quyết định gần như toàn bộ chi phí vận hành.

Label được phép dùng — đều là tập giá trị hữu hạn, biết trước:

- `service_name`
- `deployment_environment`
- `component`
- `log_level`

Tuyệt đối **không** đưa vào label: `workspace_id`, `project_id`, `user_id`,
`request_id`, `trace_id`, `span_id`.

> Hiện trạng cần sửa: `logging/promtail-config.yaml` đang đặt `request_id` và
> `task_id` làm label. Mỗi request sinh một stream mới → index phình tuyến tính,
> ingester ăn RAM, query chậm dần. Đây là cách làm hỏng Loki phổ biến nhất.

### 1.2 ID đi vào structured metadata

Các field dùng để liên kết và điều tra được gắn dưới dạng **structured metadata**
— không tạo stream mới, không phải parse lại JSON khi query:

`request_id`, `trace_id`, `span_id`, `workspace_id`, `project_id`,
`actor_user_id`, `http.route`, `http.method`, `http.status_code`, `error.type`,
`event.name`

```logql
{ service_name="signbridge-api", deployment_environment="production" }
| workspace_id="ws_123"
| project_id="prj_456"
```

Điều kiện kỹ thuật đã có sẵn: Loki 3.0.0, `schema: v13`, `store: tsdb` — cả ba
đều bắt buộc để dùng structured metadata.

Giới hạn cần nhớ: structured metadata hợp cho điều tra trong **một khoảng thời
gian đã tương đối rõ**. Nó không phải inverted index như Elasticsearch — đó
chính là lý do cần bảng tra cứu ở §1.4.

### 1.3 Loki không phải nơi lưu lịch sử audit

Những câu hỏi nghiệp vụ — ai đã xoá sample, user nào đổi quyền, workspace này có
hoạt động gì trong sáu tháng — trả lời bằng bảng kiểm toán trong PostgreSQL,
không phải bằng log.

> Bảng thật tên là **`audit_log`**, không phải `audit_events` như bản kế hoạch
> này viết. Xem §10 về những gì đã dựng.

Loki giữ **chi tiết kỹ thuật** và hết hạn sau 7 ngày. Audit database giữ **sự
kiện nghiệp vụ chính thức** và giữ lâu.

### 1.4 Bảng tra cứu request

Giải bài toán "có `request_id` nhưng không biết service hay thời gian", để Loki
không phải quét nhiều ngày log:

```
request_id → request_lookup → service + thời gian + trace_id
           → mở trace trong Tempo
           → mở log liên quan trong Loki
```

### 1.5 Route template, không phải raw URL

Không lưu `/api/workspaces/ws_123/projects/prj_456`, mà lưu
`/api/workspaces/{workspace_id}/projects/{project_id}`.

`http.route` trước mắt để trong structured metadata. Dashboard theo route
(latency, request rate, error rate) lấy từ **metrics**, không quét raw log.

---

## 2. Phân loại field

| Field | Loki label | Structured metadata | PostgreSQL index |
|---|---|---|---|
| `service_name` | Có | Có thể | Không cần |
| `deployment_environment` | Có | Không cần | Có thể |
| `component` | Có | Có thể | Không cần |
| `log_level` | Có | Có thể | Không cần |
| `workspace_id` | Không | Có | Có |
| `project_id` | Không | Có | Có |
| `actor_user_id` | Không | Có | Có |
| `request_id` | Không | Có | Có, khoá chính |
| `trace_id` | Không | Có | Có |
| `span_id` | Không | Có | Không bắt buộc |
| `http.route` | Chưa | Có | Có trong request summary |
| `http.method` | Không bắt buộc | Có | Có thể |
| `status_code` | Không bắt buộc | Có | Có thể |
| `event.name` | **Không** (xem §4) | Có | Có trong audit |
| Raw URL | Không | Hạn chế | Không |
| Request body | Không | Thường không | Không |

---

## 3. Kiến trúc

```
        CTU-SignBridge:  Web API   Background Worker   Recognition Service
                             │            │                    │
                             └────────────┴────────┬───────────┘
                                                   │  OpenTelemetry SDK (OTLP)
                                                   ▼
                                      ┌────────────────────────┐
                                      │ OpenTelemetry Collector│
                                      │  enrich / redact /     │
                                      │  batch / route         │
                                      └──┬────────┬────────┬───┘
                                    logs │ traces │metrics │
                                         ▼        ▼        ▼
                                     ┌──────┐ ┌──────┐ ┌──────────┐
                                     │ Loki │ │Tempo │ │Prometheus│
                                     └───┬──┘ └───┬──┘ └────┬─────┘
                                         └────────┴─────────┘
                                                  ▼
                                             ┌─────────┐
                                             │ Grafana │
                                             └─────────┘

        Dữ liệu tra cứu & audit (tách riêng, không đi qua Collector):

        Request Middleware ──► request_lookup ─┐
        Business Services  ──► audit_events   ─┴──► PostgreSQL
```

### Vai trò từng hệ thống

| Hệ thống | Câu hỏi nó trả lời |
|---|---|
| Loki | Lỗi chi tiết là gì? Dòng log nào liên quan? |
| Tempo | Request đã đi qua những service và span nào? |
| Prometheus | Hệ thống có đang chậm hoặc lỗi nhiều không? |
| `request_lookup` | Request ID này xảy ra khi nào, ở đâu, thuộc trace nào? |
| `audit_events` | Ai đã làm gì với workspace, project hoặc dữ liệu? |
| Grafana | Giao diện tổng hợp log, trace, metrics, dashboard |

### Quy trình điều tra

**Biết request ID:** `request_id` → `request_lookup` → lấy `started_at`,
service, `trace_id` → mở trace trong Tempo → xem span lỗi → mở log tương ứng
trong Loki.

**Biết workspace/project:** tra `audit_events` → tìm hành động đáng chú ý → lấy
`request_id`/`trace_id` → mở Tempo và Loki.

**Hệ thống đang chậm:** Prometheus cảnh báo latency/error rate → xác định route
và service → mở trace mẫu trong Tempo → xem log lỗi trong Loki.

---

## 4. Rủi ro và điểm cần quyết trước khi triển khai

Bốn điểm dưới đây là kết quả rà soát kế hoạch, **chưa được giải quyết**.

### 4.1 `request_lookup` ghi mọi request → khuếch đại write

Mỗi request thành 1 INSERT + 1 UPDATE (`started_at` rồi `completed_at`), tức
PostgreSQL nhận write theo đúng tần suất truy cập, trên cùng instance với dữ
liệu nghiệp vụ, trên host 6 core/12GB. Sau vài tháng bảng này lớn hơn dữ liệu
thật, và bắt buộc phải có partition theo thời gian + job dọn.

**Đề xuất rẻ hơn:** cho `request_id` **chính là** `trace_id`. Khi đó bài toán
"có request_id mà không biết service/thời gian" tự biến mất vì Tempo tra thẳng
được, và `request_lookup` chỉ cần ghi cho request *đáng chú ý* — 5xx, chậm quá
ngưỡng, hoặc có thay đổi dữ liệu. Giảm khoảng 99% lượng ghi mà không mất khả
năng điều tra nào.

### 4.2 Kế hoạch viết cho mô hình tenant chưa tồn tại

`workspace_id`/`project_id` xuyên suốt mọi bảng và mọi field, nhưng hệ hiện tại
chưa có khái niệm đó. Cần tách rõ hai mốc: phần làm được ngay (sửa label, bật
structured metadata) và phần chờ mô hình multi-tenant có thật.

### 4.3 Ngân sách RAM

Thêm Tempo + OTel Collector vào stack đang chạy 13 container trên 12GB.
Collector nhẹ, Tempo thì không. Phải cấp `mem_limit` cho cả hai **trước** khi
thêm, nếu không chúng ăn vào phần đã chia cho PostgreSQL/Redis.

### 4.4 Bốn chỗ kế hoạch chưa nói tới

- **Retention/partition** cho cả `request_lookup` lẫn `audit_events` — giữ bao lâu?
- **`metadata JSONB`** trong `audit_events` cần giới hạn kích thước và quy tắc
  PII. Đây là dữ liệu người ký; để tự do sẽ thành chỗ rò dữ liệu cá nhân.
- **Redaction đang nằm hai nơi**: `mask_sensitive_data` trong
  `backend/app/logging_config.py` (phía app) và bước "redact" ở Collector. Phải
  chốt một nơi chịu trách nhiệm, nếu không sẽ có ảo giác an toàn.
- **`event.name` không nên làm label.** Số loại sự kiện nghiệp vụ tăng dần theo
  mỗi feature mới — đó là cardinality tăng âm thầm. Bảng §2 đã chốt "Không".

### 4.5 Promtail đang ở chế độ bảo trì

Grafana đã chuyển sang **Alloy**. Không cần đổi ngay, nhưng nếu đằng nào cũng
dựng OTel Collector thì Collector thay luôn vai trò promtail, khỏi cần migrate
hai lần.

---

## 5. Lược đồ hai bảng PostgreSQL

Ghi lại nguyên trạng thiết kế; xem §4.1 trước khi tạo `request_lookup`.

```sql
CREATE TABLE request_lookup (
    request_id VARCHAR(64) PRIMARY KEY,
    trace_id VARCHAR(64),

    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    environment VARCHAR(30) NOT NULL,
    entry_service VARCHAR(100) NOT NULL,

    workspace_id VARCHAR(64),
    project_id VARCHAR(64),
    actor_user_id VARCHAR(64),

    http_method VARCHAR(10),
    http_route VARCHAR(300),
    status_code INTEGER
);

CREATE INDEX idx_request_lookup_trace_id      ON request_lookup(trace_id);
CREATE INDEX idx_request_lookup_workspace_time ON request_lookup(workspace_id, started_at DESC);
CREATE INDEX idx_request_lookup_project_time   ON request_lookup(project_id, started_at DESC);
CREATE INDEX idx_request_lookup_user_time      ON request_lookup(actor_user_id, started_at DESC);
```

```sql
CREATE TABLE audit_events (
    event_id VARCHAR(64) PRIMARY KEY,
    event_name VARCHAR(150) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,

    workspace_id VARCHAR(64),
    project_id VARCHAR(64),

    actor_type VARCHAR(30) NOT NULL,
    actor_user_id VARCHAR(64),

    target_type VARCHAR(50),
    target_id VARCHAR(64),

    request_id VARCHAR(64),
    trace_id VARCHAR(64),

    result VARCHAR(30) NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_audit_workspace_time ON audit_events(workspace_id, occurred_at DESC);
CREATE INDEX idx_audit_project_time   ON audit_events(project_id, occurred_at DESC);
CREATE INDEX idx_audit_actor_time     ON audit_events(actor_user_id, occurred_at DESC);
CREATE INDEX idx_audit_event_time     ON audit_events(event_name, occurred_at DESC);
```

---

## 6. Phạm vi triển khai

Không cần Elasticsearch hay ClickHouse. Bộ khởi điểm:

| Thành phần | Vai trò |
|---|---|
| Loki | log kỹ thuật |
| Tempo | distributed tracing |
| Prometheus | metrics |
| PostgreSQL | request lookup + audit events |
| Grafana | giao diện quan sát |
| OTel Collector | chuẩn hoá và chuyển telemetry |

Cân bằng được chi phí lưu trữ, tốc độ tìm request, tránh cardinality explosion,
hỗ trợ multi-tenant, có audit chính xác — và mở rộng sang Elasticsearch hoặc
ClickHouse sau này mà không phải thay toàn bộ mô hình logging.

### Thứ tự đề nghị

1. **Sửa `promtail-config.yaml`** — bỏ `request_id`/`task_id` khỏi `labels`,
   chuyển sang `structured_metadata`. Rẻ, độc lập, chặn ngay rủi ro cardinality.
2. Chốt §4.1 (`request_id` = `trace_id`?) trước khi tạo bảng nào.
3. `audit_events` — dùng được ngay cả khi chưa có tenant model.
4. OTel Collector + Tempo — khi đã cấp xong `mem_limit`.
5. `request_lookup` — sau cùng, theo phương án đã chốt ở bước 2.

### Giao diện xuất log cho admin

Yêu cầu ban đầu là "log xoay theo ngày + giao diện admin xuất text theo khung
thời gian tuỳ chọn". Cân nhắc: Grafana **đã** làm đúng việc đó — chọn khoảng
thời gian bất kỳ, lọc theo level/service/request_id, gộp log của mọi service.
Chỉ nên tự dựng log-viewer riêng nếu admin không được phép vào Grafana.

---

## 7. Giới hạn đăng nhập — ĐÃ TRIỂN KHAI (2026-07-31)

Nằm trong `backend/app/rate_limit.py`. Ghi lại ở đây vì phần §8/§9 bên dưới xây
tiếp lên nó.

Một luật **chặn**, hai luật **chỉ quan sát**:

```
cặp (identifier, IP):  sai 1–10  → cho qua
                       sai 11    → chờ 30s
                       sai 12    → chờ 2m
                       sai 13    → chờ 5m
                       sai 14+   → chờ 15m (trần)

theo identifier:       chỉ đếm + cảnh báo (nhiều IP dò một tài khoản)
theo IP:               chỉ đếm + cảnh báo; chặn cứng ở 1000 lỗi/10 phút
```

Ba tính chất bắt buộc giữ khi sửa về sau:

1. **Khoá theo cặp, không theo identifier trần.** Khoá theo identifier cho phép
   bất kỳ ai biết email của người khác khoá họ vô hạn.
2. **Đang chờ thì không đếm tiếp.** `check_login_allowed` raise trước
   `register_failed_login`, nên gõ lại lúc bị chặn không kéo dài hình phạt.
3. **Đăng nhập thành công reset cặp, KHÔNG reset bộ đếm IP.** Một lần đăng nhập
   đúng không nói gì về các tài khoản khác mà địa chỉ đó đang dò.

Kiểm bằng Redis thật: 9/9 tính chất trên đứng vững.

### Phụ thuộc: nginx phải giữ bản HEAD

`nginx.conf` (đang conflict trong merge) khác nhau đúng chỗ chí mạng:

| | X-Real-IP stamp |
|---|---|
| HEAD (deploy 2.2.1) | `$rl_client` — map từ `$http_cf_connecting_ip`, IP client thật sau Cloudflare |
| vocab-schema-v2 | `$remote_addr` — sau Cloudflare đây là IP của **Cloudflare** |

**Phải lấy HEAD.** Lấy bản kia thì mọi người dùng gộp về một địa chỉ: chặn flood
theo IP thành vô nghĩa, và lệnh ban IP của admin sẽ ban Cloudflare, tức ban tất
cả. Backend chỉ tin header khi TCP peer nằm trong `TRUSTED_PROXIES`, nên bản thân
việc giả header từ ngoài đã bị chặn — nhưng nếu chính nginx điền sai thì backend
không có cách nào biết.

---

## 8. Giới hạn request cho user đã đăng nhập — ĐÃ LÀM, KHÁC KẾ HOẠCH

> **Cập nhật 2026-08-08.** Mục này từng ghi "CHƯA LÀM" và đã lạc hậu.
> `app/rate_limit_deps.py` cưỡng chế hạn mức theo `user_id` thật, bằng thùng
> đếm trong Redis theo giờ — **không** phải theo giây ở nginx như đề xuất bên
> dưới. Đọc mã trước khi tin phần còn lại của mục này.
>
> Một chi tiết của bản đã dựng không có trong kế hoạch và đáng giữ: người gọi
> ẩn danh **không bị đếm** khi endpoint vốn đòi đăng nhập. Đếm họ đổi câu trả
> lời từ 401 thành 429, và vì mọi khách ẩn danh chung một thùng theo IP, một
> kẻ gõ cửa liên tục sẽ làm cạn hạn mức của cả phòng sau cùng một NAT.

Hiện `nginx.conf` (HEAD) đặt `auth_limit 5r/s` và `api_limit 30r/s` theo
`$rl_client`, tức **theo IP**. Hai vấn đề: 5 r/s quá thấp khi frontend mở trang
và bắn nhiều request song song; và khoá theo IP thì cả phòng lab dùng chung một
hạn mức.

Đề xuất — khoá chính là `user_id` sau khi đã đăng nhập:

| Nhóm API | Tốc độ | Burst |
|---|---:|---:|
| Đọc dữ liệu thông thường | 10 req/s | 30 |
| Tạo, sửa, xoá | 3 req/s | 10 |
| Tìm kiếm phức tạp | 2 req/s | 5 |
| Export / xử lý nặng | 1 req/s | 3 |
| Upload | tối đa 2 tác vụ đồng thời | — |

Trần tổng: 600 request/phút. Vượt thì trả `429` kèm `Retry-After`, **không** khoá
tài khoản. Đăng nhập vẫn dùng chính sách riêng ở §7, không dùng chung hạn mức API.

**Bật ở chế độ `dry-run` trước** (`API_RATE_LIMIT_DRY_RUN=true`): ghi nhận request
đáng lẽ bị chặn nhưng chưa trả 429, xem số liệu thật rồi mới bật chặn.

---

## 9. Metrics và cảnh báo — KẾ HOẠCH, PHẦN LỚN CHƯA LÀM

> **Đã làm rồi, và không giống kế hoạch dưới đây:** hạ tầng cảnh báo đã chạy —
> 10 quy tắc trong `logging/grafana/alerting/`, gửi thư qua contact point
> "Admin Email". Xem §9bis ngay dưới về cách nó thật sự hoạt động, và §10.4 về
> ba cảnh báo cho nhật ký kiểm toán. Danh sách chỉ số dưới đây là **kế hoạch
> gốc cho phần đăng nhập/rate-limit**, và phần đó vẫn chưa làm.



### Metrics (Prometheus)

```
login_attempts_total{result="success|failure|blocked"}
login_pair_throttled_total{backoff_level}
login_ip_warning_total{severity}
login_distinct_identifiers{source_type}

api_requests_total{route_group, method, status}
api_rate_limited_total{limiter="user|workspace|ip", route_group}
api_request_duration_seconds{route_group}
api_concurrent_requests{route_group}
```

Tuyệt đối **không** đưa vào Prometheus label: `user_id`, `identifier`,
`workspace_id`, IP, `request_id`. Cùng lý do cardinality như §1.1 — chúng thuộc
về structured metadata của log, không thuộc về metric.

### Log sự kiện

```json
{ "event_name": "auth.login_throttled", "request_id": "req_...",
  "identifier_hash": "...", "source_ip": "203.0.113.10",
  "failure_count": 12, "backoff_seconds": 120, "limit_type": "identifier_ip" }

{ "event_name": "api.rate_limited", "request_id": "req_...",
  "user_id": "usr_123", "workspace_id": "ws_456", "source_ip": "203.0.113.10",
  "route_group": "project_write", "limit_type": "user",
  "configured_rate": 10, "configured_burst": 30, "retry_after_seconds": 2 }
```

Không ghi mật khẩu, token, hay email thô — `rate_limit.py` đã băm identifier
(`_hashed`) đúng vì lý do này.

> Hiện `rate_limit.py` mới log dạng **text** (`[auth] login_throttled
> identifier_hash=… backoff_seconds=…`). Để chúng thành field JSON thật, cần thêm
> `structlog.stdlib.ExtraAdder` vào `foreign_pre_chain` trong `logging_config.py`
> rồi chuyển sang `logger.warning(..., extra={...})`. Chưa làm.

### Cảnh báo

```
một tài khoản bị thử từ nhiều IP        → tấn công phân tán
một IP thử nhiều identifier khác nhau   → password spraying
IP vượt 200 lỗi / 10 phút               → mức thấp
IP vượt 500 lỗi / 10 phút               → mức cao
tỷ lệ đăng nhập bị giới hạn tăng đột biến → bot, hoặc cấu hình quá chặt
tỷ lệ API trả 429 > 2% trong 10 phút     → rate limit sai, hoặc frontend gọi trùng
một user nhận > 20 lần 429 trong 5 phút  → hành vi bất thường hoặc frontend lỗi
một route có 429 tăng mạnh               → retry sai hoặc endpoint quá nặng
```

Cảnh báo theo **tỷ lệ bất thường**, không theo từng lần sai riêng lẻ.

### Biến môi trường còn thiếu

```env
API_USER_RATE=10
API_USER_BURST=30
API_USER_MINUTE_LIMIT=600
API_USER_WRITE_RATE=3
API_USER_WRITE_BURST=10
API_USER_HEAVY_RATE=1
API_USER_HEAVY_BURST=3
API_USER_MAX_CONCURRENT_UPLOADS=2
API_RATE_LIMIT_DRY_RUN=true
API_RATE_LIMIT_WARN_COUNT=20
API_RATE_LIMIT_WARN_WINDOW=300
```

Các biến của §7 thì đã có trong `.env` và cần thêm vào `.env.example` khi gỡ
conflict file đó.

---

## 9bis. Hạ tầng cảnh báo — trạng thái thật (2026-08-09)

### Cảnh báo sống ở Grafana, KHÔNG ở Prometheus

`logging/prometheus.yml` cố ý **không có `rule_files`**. Bản triển khai này
không chạy Alertmanager, nên một quy tắc phía Prometheus chỉ chuyển sang trạng
thái ĐANG KÊU trên trang `/alerts` rồi nằm im — không ai nhận được gì.

Một quy tắc không gửi được cho ai còn **tệ hơn** không có quy tắc: nó tạo cảm
giác đang có người canh.

Toàn bộ quy tắc nằm trong hệ hợp nhất của Grafana:

| Tệp | Nội dung |
|---|---|
| `logging/grafana/alerting/hardware-alerts.yml` | 7 quy tắc: phần cứng, CPU, lưu lượng, 5xx, backend/Redis/Postgres chết |
| `logging/grafana/alerting/audit-alerts.yml` | 3 quy tắc cho nhật ký kiểm toán (§10.4) |
| `logging/grafana/alerting/contact-points.yml` | một địa chỉ thư |
| `logging/grafana/alerting/templates.yml` | khuôn tiêu đề + thân thư |
| `logging/grafana/alerting/policies.yml` | gộp theo `grafana_folder` + `alertname`, nhắc lại mỗi 4 giờ |

### Thư cảnh báo phải là VĂN BẢN THUẦN

Đây là chỗ đã hỏng, và cách nó hỏng không hiển nhiên.

Khuôn thư cũ dựng một trang HTML đầy đủ trong trường `message`. Người nhận thấy
**nguyên văn mã đó** — `<div style="font-family: Arial…">` in ra thành chữ, kéo
dài hai màn hình, không một dòng nào đọc được.

Nguyên nhân: **`message` của contact point kiểu email không phải thân thư.**
Grafana có khuôn HTML riêng (`ng_alert_notification.html` — chính cái khung có
logo Grafana ở đầu thư) và chèn `message` vào đó **qua `html/template`**, tức
là escape mọi dấu ngoặc nhọn. Không có cấu hình nào tắt được ở Grafana OSS;
muốn thân thư HTML thật thì phải thay tệp khuôn bên trong image.

Nên khuôn đúng là văn bản thuần. Grafana tự bọc nó trong khung có thương hiệu.

Hai điều nữa đã sửa cùng lúc:

* **Duyệt `.Alerts` thay vì đọc `.CommonLabels`.** Chính sách gộp theo
  `alertname`, nên khi hai máy cùng kêu một cảnh báo thì những nhãn **khác**
  nhau biến mất khỏi `CommonLabels` — thư cũ hiện "Mức độ: " bỏ trống và không
  nói gì về việc có hai sự cố.
* **Bỏ ký hiệu tượng hình.** Nhiều trình đọc thư dựng emoji bằng phông của hệ
  điều hành; trên máy chủ và điện thoại cũ nó ra ô vuông rỗng.

### BẪY MÔI TRƯỜNG: container Alpine/Go không phân giải được tên ngoài

Đo trên máy này 2026-08-09, và nó **chặn hoàn toàn thư cảnh báo** dù khuôn thư
đã đúng:

```
container → 8.8.8.8  UDP/53   → hết giờ
container → 8.8.8.8  TCP/53   → 64.233.170.109      (chạy)
container → smtp.gmail.com:587 TCP → mở              (chạy)
```

**Outbound UDP cổng 53 bị chặn ở máy chủ này.** DNS nhúng của Docker
(`127.0.0.11`) chuyển tiếp bằng UDP, nên mọi phân giải tên ngoài trong container
đều chết; chỉ những tên còn trong bộ nhớ đệm mới trả lời.

Vì sao chỉ Grafana chết mà backend thì không:

| Ảnh | Bộ phân giải | Kết quả |
|---|---|---|
| `voya_backend` (Debian, glibc) | glibc, có lối lùi sang TCP | **chạy** — thư OTP/lời mời/đặt lại mật khẩu vẫn gửi được |
| `grafana` (Alpine, không glibc) | bộ phân giải thuần Go | **chết** — Go không lùi sang TCP khi UDP *hết giờ* (chỉ lùi khi câu trả lời bị cắt) |

Triệu chứng trong log: `notify retry canceled due to unrecoverable error after
1 attempts: … dial tcp: lookup smtp.gmail.com: i/o timeout`. Chú ý
**`after 1 attempts`** — Grafana coi đây là lỗi không cứu được và **bỏ luôn**
thông báo đó; lần thử tiếp theo phải chờ hết `repeat_interval`.

Đây là vấn đề của **máy chủ**, không phải của kho mã: mở outbound UDP/53 cho
card mạng của Docker/WSL, hoặc kiểm tra VPN/phần mềm diệt virus đang chặn. Ghim
`extra_hosts` cho `smtp.gmail.com` sẽ chữa được ngay nhưng địa chỉ của Google
thay đổi liên tục, nên nó đổi một lỗi ồn ào lấy một lỗi im lặng vài tuần sau.

Kiểm nhanh lại bất cứ lúc nào:

```bash
docker run --rm --network voya-collector_voya_network alpine:3.19 sh -c   "apk add -q bind-tools; dig +short +timeout=4 +tries=1 @8.8.8.8 A smtp.gmail.com"
```

### Đổi ngưỡng hoặc người nhận

Sửa tệp YAML rồi `docker compose restart grafana` — provisioning nạp lại lúc
khởi động. **Không sửa qua giao diện Grafana:** quy tắc do provisioning tạo có
`provenance: file`, giao diện không cho sửa, và nếu có sửa được thì lần khởi
động sau sẽ ghi đè.

> **Bẫy đã biết:** Grafana **không xoá** một quy tắc khi nó biến mất khỏi tệp
> provisioning — nó nằm lại trong `grafana_data` với `provenance: file`, vô
> hình trong git và không xoá được qua giao diện. Cách được hỗ trợ là khai
> `deleteRules` (xem đầu `hardware-alerts.yml`, nơi quy tắc `high-error-rule`
> cũ đang được cho về hưu theo cách đó).

---

## 10. Dấu vết kiểm toán — trạng thái thật (2026-08-08)

Mục này mô tả cái **đang chạy**, không phải cái dự định. Các mục 1–9 ở trên là
kế hoạch và đã lệch khỏi mã ở vài chỗ.

### 10.1 Hai nhật ký, và vì sao giữ cả hai

| | `sec:log` (Redis) | `audit_log` (Postgres) |
|---|---|---|
| Trả lời câu hỏi | "vừa có chuyện gì?" | "tháng trước ai đã làm gì?" |
| Dung lượng | 500 mục, `ltrim` | không giới hạn |
| Bị đuổi khỏi bộ nhớ | **có** — `maxmemory-policy volatile-lru` | không |
| Có `ip_hash` đối chiếu | không | có |
| Chịu RLS | không | có |
| Giao diện | bảng "Nhật ký bảo mật" | bảng "Nhật ký kiểm toán" |

Trước 2026-08-08 chỉ có nhánh Redis, và bảy lối gọi quản trị (chặn IP, khoá tài
khoản, ép đăng xuất, cảnh báo…) chỉ tồn tại ở đó. Một dấu vết mà hệ thống được
phép tự xoá khi cần chỗ thì không phải dấu vết.

`activity.log_security_event` giờ ghi **cả hai**, mỗi nhánh một `try` riêng:
Postgres chết không được kéo theo nhánh Redis, vì như thế là thêm một nhật ký
thứ hai lại làm yếu đi cái thứ nhất.

### 10.2 Mặt phẳng dữ liệu ghi cái gì

Ghi: `data.class.purge`, `data.class.purge.bulk`, `data.class.soft_delete`,
`data.sample.purge`, `data.sample.purge.bulk`.

**Không** ghi: xoá mềm MỘT mẫu. Nó hồi được từ Thùng rác và xảy ra hàng trăm
lần mỗi buổi thu; đổ vào đây là đổi một bảng bằng chứng thưa và đọc được lấy
một bảng nhật ký dày mà không ai đọc. Bằng chứng bị chôn giữa tiếng ồn cũng như
không có.

### 10.3 Phạm vi — cái bẫy khó thấy nhất

`audit_log` chịu RLS với vị từ dùng chung. Ba trạng thái, và cả ba đều đúng
thiết kế:

| Phạm vi lúc ghi | `tenant_id` | Ai đọc lại được |
|---|---|---|
| tenant scope | tenant đó | quản trị viên tenant đó |
| system scope | NULL | chỉ system scope |
| **không có phạm vi** | — | **không ghi được**, `record()` trả False |

Hệ quả cần biết: `GET /admin/audit-log` chạy trong phạm vi tenant của người
gọi, nên nó **không** hiển thị dòng tầng nền tảng. Endpoint nói ra điều đó
bằng trường `excludes_platform_rows` thay vì để người đọc suy đoán — một bảng
thiếu dòng mà không báo là một bảng nói dối.

Sản xuất không rơi vào trạng thái "không phạm vi": middleware HTTP,
`task_prerun` của Celery và `platform_command` của CLI đều đặt phạm vi. Một lối
vào thứ tư thì phải tự đặt lấy; `test_audit_fails_closed_when_there_is_no_scope_at_all`
ghim hậu quả nếu quên.

### 10.4 Cảnh báo cho nhật ký kiểm toán — ĐÃ LÀM (2026-08-09)

Bản trước của mục này viết *"`audit.count_since()` đã có sẵn cho việc này"*.
**Hàm đó chưa từng tồn tại.** Nó được nhắc tới ở đây và trong docstring của
`app/audit.py`, và cả hai chỗ đều mô tả một thứ chưa ai viết. Giờ nó đã có.

Nhật ký kiểm toán hỏng theo **đúng hai cách**, và một chỉ số không bắt được cả
hai:

| Kiểu hỏng | Dấu hiệu | Chỉ số bắt được |
|---|---|---|
| Lời gọi ghi **ném lỗi** | một dòng `[AUDIT-FAIL]` trong log, không gì khác | `voya_audit_write_failures_total` |
| Đường ghi **biến mất**, không ném gì | *không có dấu hiệu nào* | `voya_audit_log_age_seconds` |

Cách thứ hai mới là cách nguy hiểm. `audit.record` cố ý nuốt mọi ngoại lệ — nó
không được phép làm hỏng thao tác nó đang ghi lại — nhưng khi một lời gọi
`record` bị xoá đi, hoặc một nhánh mã mới không gọi nó ngay từ đầu, thì **không
có ngoại lệ nào để đếm và không có dòng log nào để đọc**. Chỉ có một cái sổ
ngừng dày lên, trông hệt như một hệ thống yên tĩnh. Bộ đếm mù hoàn toàn với nó.

Ba chỉ số, xuất ở `/metrics`:

```
voya_audit_write_failures_total   # bộ đếm; chỉ tăng
voya_audit_log_age_seconds        # giây kể từ dòng mới nhất; -1 = rỗng hoặc không đọc được
voya_audit_log_entries_1h         # số dòng trong một giờ; -1 = không đọc được
```

**`-1` là một giá trị mang nghĩa, không phải lỗi.** Nó nói "đừng suy luận gì từ
tôi", và nó phân biệt hai chuyện mà số 0 gộp làm một: *không hỏi được cơ sở dữ
liệu* và *không có hoạt động nào*. Trả 0 cho cả hai sẽ biến một sự cố kết nối
thành cảnh báo "sổ ngừng tăng" — đúng hồi chuông vì sai lý do, và lần sau không
ai tin nó nữa. Hai quy tắc cảnh báo vì thế **lọc `-1` ra khỏi biểu thức**, và
có một quy tắc thứ ba canh chính tình trạng `-1` kéo dài.

Ba quy tắc nằm ở `logging/grafana/alerting/audit-alerts.yml`:

| Cảnh báo | Điều kiện | `for` | Mức |
|---|---|---|---|
| Không ghi được nhật ký kiểm toán | `increase(...write_failures_total[1h]) > 0` | 5m | critical |
| Nhật ký kiểm toán ngừng tăng | `age != -1` và `> 21600` (6 giờ) | 30m | warning |
| Không đọc được bảng | `age == -1` **and** `entries_1h == -1` | 1h | warning |

**Vì sao quy tắc thứ ba phải hỏi CẢ HAI chỉ số:** `age == -1` mang hai nghĩa —
sổ rỗng, và không đọc được bảng. Chỉ lọc theo nó thì trên một bản có sổ rỗng
(đúng tình trạng máy này ngày 2026-08-09: `audit_log` **0 dòng**) cảnh báo kêu
sau một giờ và kêu mãi cho tới khi ai đó tình cờ làm một thao tác được ghi. Kêu
sai ngay ngày đầu là cách chắc chắn nhất để một cảnh báo bị tắt vĩnh viễn.
`entries_1h` tách được hai nghĩa: sổ rỗng cho **0** (truy vấn chạy được, không
có dòng nào), không đọc được bảng mới cho **-1**.

**Vì sao ở Grafana chứ không phải trong `rule_files` của Prometheus:** bản
triển khai này không chạy Alertmanager. Một quy tắc phía Prometheus chỉ chuyển
sang trạng thái ĐANG KÊU trên trang `/alerts` rồi nằm im — không ai nhận được
gì. Đường gửi thư duy nhất đang chạy là hệ cảnh báo hợp nhất của Grafana.
Một quy tắc không gửi được cho ai còn tệ hơn không có quy tắc: nó tạo cảm giác
đang có người canh.

**Vì sao ngưỡng 6 giờ chứ không phải 1 giờ:** đây là bản triển khai của một
trường, và ban đêm không có ai đăng nhập là chuyện bình thường. Một ngưỡng một
giờ sẽ kêu mỗi đêm cho tới khi có người tắt nó đi — và lúc đó nó bỏ sót 100%.

### 10.4bis `audit_log` đang RỖNG trên bản triển khai này (2026-08-09)

Đếm thật: **0 dòng, chưa từng có dòng nào**, dù đường ghi đã nối từ 2026-08-08
và cả endpoint lẫn giao diện đều có.

Đường ghi **không hỏng** — bộ test dựng 15 dòng thật trên bản sao Postgres ở mỗi
lượt chạy rồi dọn đi. Nghĩa là chưa có thao tác nào **được ghi nhật ký** xảy ra:
danh sách hành động được ghi toàn là việc hiếm của quản trị viên (xoá sạch lớp,
xoá vĩnh viễn tổ chức, đổi vai). Xoá mềm MỘT mẫu cố ý không ghi (§10.2).

Đây đúng là tình huống mà `voya_audit_log_age_seconds = -1` được thiết kế để
KHÔNG kết luận điều gì — và cũng là lý do quy tắc thứ ba phải hỏi thêm
`entries_1h`, nếu không nó sẽ kêu oan ngay ngày đầu.

Dòng đầu tiên xuất hiện là lúc đồng hồ bắt đầu có nghĩa. Trước đó, cảnh báo
"ngừng tăng" im lặng — đúng như mong muốn.

### 10.5 Còn thiếu

* Không có chính sách lưu trữ — bảng chỉ tăng. Ở quy mô hiện tại (vài nghìn
  dòng/năm) chưa thành vấn đề, nhưng cần quyết trước khi mở cho nhiều tổ chức.
* Chưa có Alertmanager. Cảnh báo đi qua Grafana tới đúng một địa chỉ thư; không
  có phân ca trực, không có leo thang, không có kênh thứ hai khi thư hỏng.
