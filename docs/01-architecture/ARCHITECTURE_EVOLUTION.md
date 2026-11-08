# VOYA Collector - Định hướng tiến hóa kiến trúc

> Trạng thái: Bản thảo đang thảo luận  
> Cập nhật gần nhất: 2026-10-14  
> Mục đích: Đây là tài liệu sống. Các quyết định trong tài liệu có thể được chỉnh sửa dần sau mỗi buổi thảo luận và chưa được xem là thiết kế cuối cùng.
> Kiểm kê triển khai: [REPO_DOMAIN_INVENTORY.md](./REPO_DOMAIN_INVENTORY.md)

## 1. Mục tiêu

Sắp xếp lại VOYA Collector để:

- Ưu tiên cao nhất: repo dễ đọc, dễ tìm file và dễ hiểu luồng gọi.
- Ranh giới giữa thu thập dữ liệu, huấn luyện và suy luận realtime rõ ràng.
- Những tác vụ nặng có thể deploy và scale độc lập.
- Giảm phụ thuộc vào đường dẫn filesystem và source code dùng chung không kiểm soát.
- Giữ hệ thống có thể chạy bằng Docker Compose trong giai đoạn phát triển.
- Cho phép chuyển đổi từng bước, không viết lại toàn bộ hệ thống cùng lúc.

Việc trở thành microservices không phải mục tiêu bắt buộc của đợt dọn repo. Nếu modular monolith đáp ứng tốt khả năng đọc, kiểm thử và vận hành thì có thể giữ kiến trúc đó lâu dài.

## 2. Kiến trúc hiện tại

Hệ thống hiện tại không phải monolith thuần túy, nhưng phần backend nghiệp vụ chính đang gần với **distributed modular monolith**:

- `frontend` là ứng dụng React độc lập.
- `nginx` là reverse proxy/gateway.
- `backend` là FastAPI API trung tâm, chứa phần lớn nghiệp vụ.
- `worker`, `trainer` và `celery-beat` chạy thành container riêng nhưng cùng dùng image `voya_backend:latest` và cùng source backend.
- `realtime_service` đã là service có image và tiến trình riêng.
- Redis được dùng làm queue/broker.
- Chỉ có một PostgreSQL (`signdb`) dùng chung cho hệ thống.
- Dataset, video, checkpoint, model và report còn phụ thuộc nhiều vào filesystem/volume dùng chung.

Vì vậy, mô tả chính xác hơn là:

> Một backend monolith có cấu trúc module, kết hợp với các worker bất đồng bộ và một realtime service đã được tách riêng; toàn hệ thống vẫn dùng chung một database và nhiều tài nguyên filesystem.

## 3. Hai cách phân chia đang được xem xét

### 3.1. Chia theo loại tiến trình

```text
Core API
Media Worker
Training Worker
Realtime Service
```

Ưu điểm:

- Gần với cấu trúc code hiện tại.
- Ít thay đổi và ít container hơn.
- Dễ debug và vận hành local.
- Nhanh chóng tách được tải xử lý nặng khỏi API.

Hạn chế:

- Ranh giới nghiệp vụ Collection và Training chưa hoàn toàn rõ.
- Core API có nguy cơ tiếp tục phình to.
- Worker có thể phụ thuộc trực tiếp vào model/repository của Core API.

### 3.2. Chia theo phạm vi nghiệp vụ

```text
Core API
Collection Service
Training Service
Realtime Service
TTS Service (tùy nhu cầu)
```

Ưu điểm:

- Ranh giới nghiệp vụ rõ hơn.
- Có thể deploy, scale và phân quyền từng service độc lập.
- Phù hợp với kiến trúc microservices dài hạn.
- Có thể phân chia trách nhiệm giữa nhiều nhóm phát triển.

Hạn chế:

- Nhiều API, container và message contract hơn.
- Phức tạp hơn trong transaction, logging và theo dõi lỗi.
- Rủi ro cao nếu tách toàn bộ ngay từ code hiện tại.

## 4. Định hướng được đề xuất

### Quyết định cho đợt dọn repo hiện tại

Sử dụng **modular monolith tổ chức theo phạm vi nghiệp vụ**. Chưa tách Collection và Training thành HTTP service độc lập trong đợt đầu.

```text
Một FastAPI backend
├── Identity domain
├── Administration domain
├── Catalog domain
├── Collection domain
├── Training domain
├── TTS domain
└── Workers

Một Realtime Service riêng (giữ theo hiện trạng)
Một PostgreSQL
Một Redis
```

Cách này trực tiếp phục vụ mục tiêu làm repo dễ hiểu, đồng thời vẫn tạo ranh giới để có thể tách service trong tương lai nếu thật sự cần.

Không nên tạo thêm HTTP service chỉ để đạt hình thức microservices. Một service mới chỉ nên được tách khi có nhu cầu deploy, scale, bảo mật hoặc ownership độc lập.

### Hướng dài hạn nếu cần microservices

Sử dụng **phạm vi nghiệp vụ làm cấu trúc chính**, rồi chuyển đổi từng giai đoạn.

Một service nghiệp vụ có thể gồm nhiều process/container. Ví dụ:

```text
Collection Service
├── Collection API
└── Media Worker

Training Service
├── Training API / Orchestrator
└── Trainer Worker
```

Như vậy, cấu trúc repo phản ánh nghiệp vụ, còn Docker Compose phản ánh các tiến trình cần chạy.

## 5. Kiến trúc đích đề xuất

```text
Frontend
  |
  v
Nginx API Gateway
  |-- /api/v1/auth/*        -> Core API
  |-- /api/v1/admin/*       -> Core API
  |-- /api/v1/catalog/*     -> Core API
  |-- /api/v1/collection/*  -> Collection API -> Redis -> Media Worker
  |-- /api/v1/training/*    -> Training API   -> Redis -> Trainer Worker
  |-- /api/v1/realtime/*    -> Realtime Service
  `-- /api/v1/tts/*         -> Core API trước mắt; TTS Service khi cần

Hạ tầng dùng chung trong giai đoạn đầu:
  - PostgreSQL
  - Redis / message queue
  - Local volume; sau đó chuyển sang MinIO hoặc S3-compatible storage
  - Logging, metrics và tracing
```

## 6. Trách nhiệm dự kiến

### 6.1. Core API

- Identity, đăng nhập và refresh token.
- Role và permission.
- Quản trị người dùng.
- Dataset catalog, label và metadata của sample.
- Audit log và security operations.
- Model metadata/model registry ở giai đoạn đầu.
- TTS ở giai đoạn đầu nếu chức năng còn nhẹ.

Core API không xử lý video, không huấn luyện model và không chạy inference realtime.

### 6.2. Collection Service

- Tiếp nhận camera sequence và video upload.
- Lưu raw object và tạo processing job.
- Trích xuất keypoint.
- Quality control và augmentation.
- Tạo sample và phát event `SampleCreated`.

### 6.3. Training Service

- Chuẩn bị dataset/split.
- Tạo và theo dõi training job.
- Huấn luyện, đánh giá và lưu checkpoint.
- Đăng ký model version.
- Yêu cầu promote model và phát event `ModelPromoted`.

### 6.4. Realtime Service

- Load model đã được promote.
- Kiểm tra feature contract.
- Thực hiện inference.
- Trả label, confidence và thông tin model version.
- Reload model an toàn.

### 6.5. TTS Service

Chưa tách trong giai đoạn đầu. Chỉ tách khi TTS có model riêng, cần GPU, cần scale độc lập hoặc được nhiều ứng dụng cùng sử dụng.

## 7. Cấu trúc repo dự kiến

### 7.1. Cấu trúc nên áp dụng trong đợt dọn repo

```text
VOYA-Collector/
├── frontend/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   └── logging.py
│   │   ├── domains/
│   │   │   ├── identity/
│   │   │   ├── administration/
│   │   │   ├── catalog/
│   │   │   ├── collection/
│   │   │   ├── training/
│   │   │   └── tts/
│   │   ├── infrastructure/
│   │   │   ├── database/
│   │   │   ├── queue/
│   │   │   ├── storage/
│   │   │   └── google_drive/
│   │   └── workers/
│   │       ├── media/
│   │       ├── dataset/
│   │       └── training/
│   ├── realtime_service/
│   ├── migrations/
│   ├── tests/
│   └── Dockerfile
├── ml/
│   ├── shared/
│   ├── models/
│   ├── training/
│   └── evaluation/
├── infrastructure/
│   ├── compose/
│   ├── nginx/
│   └── monitoring/
├── scripts/
│   ├── maintenance/
│   ├── migration/
│   └── research/
├── runtime/
├── tests/
└── docs/
```

Trong cấu trúc này, `worker` và `trainer` vẫn có thể chạy thành container riêng nhưng dùng chung codebase backend. Đó là lựa chọn có chủ ý để giữ repo đơn giản.

### 7.2. Cấu trúc dài hạn nếu quyết định tách microservices

```text
VOYA-Collector/
├── apps/
│   └── web/
├── gateway/
│   └── nginx/
├── services/
│   ├── core-api/
│   ├── collection-service/
│   │   ├── api/
│   │   └── worker/
│   ├── training-service/
│   │   ├── api/
│   │   └── worker/
│   ├── realtime-service/
│   └── tts-service/          # Chưa triển khai
├── packages/
│   ├── contracts/
│   ├── ml-core/
│   └── observability/
├── infrastructure/
│   ├── compose/
│   ├── postgres/
│   ├── redis/
│   ├── object-storage/
│   └── monitoring/
├── scripts/
├── runtime/                  # Không commit artifact runtime
├── tests/
└── docs/
```

## 8. Dữ liệu và quyền sở hữu

Giai đoạn đầu vẫn sử dụng một PostgreSQL instance để giảm rủi ro migration, nhưng chia schema logic:

```text
identity.*
catalog.*
collection.*
training.*
operations.*
```

Đây là bước chuyển tiếp, không phải trạng thái microservices hoàn chỉnh. Về lâu dài, service phải sở hữu dữ liệu của mình và service khác không được truy cập trực tiếp bảng nội bộ.

### 8.1. Quyết định tạm thời về database

**Chưa tách PostgreSQL thành nhiều database vật lý trong giai đoạn đầu.** Việc tách database ngay khi code còn truy cập chéo bảng và dùng chung ORM sẽ tạo ra distributed transaction, đồng bộ dữ liệu và lỗi migration khó kiểm soát.

Thứ tự chuyển đổi được đề xuất:

1. Lập danh sách bảng và xác định domain sở hữu từng bảng.
2. Buộc mọi truy cập dữ liệu đi qua repository/service của domain sở hữu.
3. Loại bỏ dần join và foreign key đi xuyên ranh giới domain.
4. Chia schema logic và database role trong cùng PostgreSQL instance.
5. Giao tiếp giữa domain bằng service API hoặc event contract.
6. Chỉ chuyển schema thành database riêng khi service có thể deploy độc lập.

Quyền sở hữu dự kiến:

```text
identity     -> user, credential, role, session/refresh token
catalog      -> label, dataset, sample metadata
collection   -> upload, capture session, processing job
training     -> dataset version, training run, metric, checkpoint, model version
operations   -> audit log, security event, task status dùng cho vận hành
```

Một service chỉ được ghi vào schema mình sở hữu. Truy vấn báo cáo đi qua read model/API thay vì cho mọi service tự do join bảng của nhau.

### 8.2. Khi nào mới tách database vật lý

Chỉ nên tách khi phần lớn điều kiện sau đã đạt được:

- Service đã có API, worker và pipeline deploy độc lập.
- Không còn transaction bắt buộc ghi đồng thời vào bảng của nhiều domain.
- Không còn join trực tiếp xuyên domain trong luồng nghiệp vụ chính.
- API/event contract đã có version và tương đối ổn định.
- Có retry, idempotency và outbox/inbox cho event quan trọng.
- Có nhu cầu thật về scale, bảo mật, backup hoặc độ sẵn sàng độc lập.
- Có integration test chứng minh service vẫn hoạt động khi service khác tạm thời không khả dụng.

Tách database chỉ để được gọi là microservices không phải là mục tiêu.

Artifact lớn không nên lưu trong Git hoặc trực tiếp trong PostgreSQL:

- Video.
- Keypoint/NPZ.
- Dataset artifact.
- Checkpoint.
- Model.
- Report và log.

Local development có thể dùng `runtime/`. Production nên dùng object storage; Google Drive chỉ đóng vai trò mirror/backup.

## 9. Giao tiếp giữa service

HTTP dùng cho thao tác ngắn cần phản hồi tức thời. Redis/Celery hoặc message broker dùng cho tác vụ dài.

Các command/event dự kiến:

```text
ProcessVideo
PrepareDataset
TrainModel
EvaluateModel
BackupModel

RawVideoUploaded
VideoProcessingCompleted
SampleCreated
DatasetPrepared
TrainingCompleted
TrainingFailed
ModelPromoted
ModelReloaded
```

Mỗi message cần tối thiểu `event_id`, `event_type`, `occurred_at`, `correlation_id`, `schema_version` và `payload`.

## 10. Lộ trình chuyển đổi

### Giai đoạn 0 - Tạo đường cơ sở an toàn

1. Xác nhận trạng thái Git sạch và làm việc trên nhánh tái cấu trúc riêng. Lưu ý: Codex cần quyền ngoài sandbox để `git status` làm mới index của repo `experiment`; đây không phải lỗi worktree của repo.
2. Sao lưu PostgreSQL, volume và các artifact quan trọng.
3. Ghi lại danh sách endpoint, Celery task, bảng dữ liệu và đường dẫn filesystem đang dùng.
4. Tạo smoke test cho đăng nhập, upload, xử lý video, chuẩn bị dataset, training và realtime.
5. Lưu kết quả chạy hiện tại làm baseline trước khi di chuyển source.

### Giai đoạn 1 - Modular hóa nhưng chưa tách deployment

1. Chuẩn hóa toàn bộ API dưới `/api/v1`.
2. Chia backend theo domain: identity, catalog, collection, training và operations.
3. Tách router, service và repository; router không truy cập database trực tiếp.
4. Lập bảng quyền sở hữu dữ liệu và ngăn domain ghi trực tiếp vào bảng của domain khác.
5. Tập trung cấu hình đường dẫn vào settings; đưa artifact runtime ra khỏi source tree.
6. Tách source ML dùng chung thành `packages/ml-core`.

### Giai đoạn 2 - Tách các tiến trình nặng

1. Hoàn chỉnh Realtime Service và định nghĩa model/feature contract.
2. Tách Collection API và Media Worker theo job contract.
3. Tách Training API/Orchestrator và Trainer Worker.
4. Mỗi service có Dockerfile, health check, test và logging riêng.

### Giai đoạn 3 - Tách hạ tầng dữ liệu khi cần

1. Bổ sung object storage và model registry rõ ràng.
2. Thêm event outbox/inbox, idempotency và correlation ID.
3. Chia PostgreSQL schema và role theo quyền sở hữu.
4. Đánh giá lại nhu cầu tách database vật lý cho từng service.
5. Chỉ cân nhắc tách TTS và Identity khi có nhu cầu vận hành thực tế.

Mỗi bước phải giữ cho Docker Compose chạy được và không đổi endpoint một cách đột ngột.

## 11. Nguyên tắc cần giữ

- Không cho service import source nghiệp vụ của service khác.
- Chỉ chia sẻ contract, ML primitive và observability utility.
- Không tạo một package `common` chứa mọi thứ.
- Không dùng filesystem dùng chung như một API ngầm giữa service.
- Không để nhiều service tự do ghi vào cùng một bảng.
- Mọi job bất đồng bộ phải idempotent và có trạng thái rõ ràng.
- Model phải có version, checksum và feature contract.
- Việc promote model phải là hành động rõ ràng, có audit log.

## 12. Quyết định đang thảo luận

Các câu hỏi cần quyết định trong những lần trao đổi tiếp theo:

- Collection API có sở hữu metadata sample hay Core Catalog sở hữu?
- Có giữ một PostgreSQL với nhiều schema bao lâu?
- Có sử dụng MinIO ngay trong local development không?
- Model Registry thuộc Core API hay Training Service?
- Frontend gọi Realtime Service qua Core proxy hay trực tiếp qua Gateway?
- TTS chạy phía frontend, trong Core API hay thành service riêng?
- Có giữ Celery hay chuyển sang hệ thống queue khác?

## 13. Nhật ký quyết định

| Ngày | Quyết định | Trạng thái |
|---|---|---|
| 2026-10-14 | Chọn domain-first làm hướng tổ chức repo; chuyển đổi theo từng giai đoạn | Đề xuất |
| 2026-10-14 | Giữ một PostgreSQL instance; xác lập ownership và schema logic trước khi tách vật lý | Khuyến nghị |
| 2026-10-14 | Chưa tách TTS thành service độc lập | Đề xuất |
| 2026-10-14 | Mục tiêu hiện tại là dọn repo; áp dụng modular monolith trước, chưa tách Collection/Training thành HTTP service | Khuyến nghị |

