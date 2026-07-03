# Kế Hoạch Tái Cấu Trúc Hệ Thống SignBridge (Bản Chi Tiết Toàn Diện)

> Bản Refactoring Master Plan v2.0  
> Dựa trên: `SignBridge_Architecture.md` - Kiến trúc 5 Tầng, 7 Domain nghiệp vụ  
> Nguyên tắc chủ đạo: **Incremental Migration** (Chuyển đổi dần dần, không đập đi xây lại)

---

## 1. PHÂN TÍCH HIỆN TRẠNG & CHIẾN LƯỢC TỔNG THỂ

### 1.1. Vấn đề hiện tại (Code Smells)

| Vấn đề | Vị trí | Mức độ nghiêm trọng |
|---|---|---|
| **God Files** – File chứa quá nhiều trách nhiệm | `dataset_manager.py` (23KB), `catalog_sync.py` (47KB), `training.py` router (35KB) | 🔴 Nghiêm trọng |
| **Thiếu phân tầng** – Logic nghiệp vụ nằm trong Router | `routers/upload.py`, `routers/trash.py`, `routers/training.py` | 🔴 Nghiêm trọng |
| **Thiếu Schema validation** – Pydantic models nằm rải rác trong router | `routers/training.py` (chứa cả class Pydantic) | 🟡 Trung bình |
| **Không có lớp Repository** – Truy xuất trực tiếp CSV/GDrive từ mọi nơi | `dataset_samples.py`, `raw_uploads.py`, `export_tasks.py` | 🔴 Nghiêm trọng |
| **Không có Middleware bảo mật tập trung** | `auth.py` nằm ngang cùng cấp với `config.py` | 🟡 Trung bình |
| **Không có bài kiểm thử tự động (Tests)** | Toàn bộ dự án | 🔴 Nghiêm trọng |
| **Frontend: Flat structure** – Không phân cụm tính năng | `components/`, `pages/`, `hooks/` nằm ngang | 🟡 Trung bình |
| **File rác / backup** ở thư mục gốc | `patch_*.py`, `old_LabelsPage.tsx`, `*_backup.tsx`, `audit_drive*.py` | 🟢 Nhẹ |

### 1.2. Chiến lược tổng thể

```
┌──────────────────────────────────────────────────────────────────┐
│                    CHIẾN LƯỢC TÁI CẤU TRÚC                      │
│                                                                  │
│  ① Viết Test lưới an toàn cho code hiện tại (Characterization)   │
│  ② Tách Core & Cơ sở hạ tầng (Config, Auth, DB, Middleware)     │
│  ③ Bóc tách Repositories (Data Access Layer)                     │
│  ④ Bóc tách Services (Business Logic Layer)                      │
│  ⑤ Tinh gọn Routers (chỉ còn điều phối HTTP)                    │
│  ⑥ Tái cấu trúc Frontend theo Feature-Sliced Design             │
│  ⑦ Thiết lập E2E Tests với Playwright                            │
│  ⑧ Dọn rác, CI/CD, Tài liệu                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. CẤU TRÚC THƯ MỤC DỰ KIẾN TOÀN BỘ

### 2.1. Toàn cảnh Project Root

```text
VOYA-Collector/                       # Thư mục gốc dự án
├── backend/                          # ═══ FASTAPI BACKEND ═══
│   ├── app/                          # Mã nguồn chính
│   │   ├── core/                     # [Tầng Hạ Tầng] Cấu hình lõi, bảo mật, kết nối
│   │   ├── middleware/               # [Tầng Chặn Giữa] Request/Response interceptors
│   │   ├── schemas/                  # [Tầng Kiểm Duyệt] Pydantic models In/Out
│   │   ├── repositories/            # [Tầng Dữ Liệu] Data Access Objects (DAO)
│   │   ├── services/                 # [Tầng Nghiệp Vụ] Business logic
│   │   ├── routers/                  # [Tầng Giao Tiếp] HTTP endpoints
│   │   ├── workers/                  # [Tầng Tác Vụ Nền] Celery tasks
│   │   ├── processing/              # [Xử lý AI] MediaPipe, feature extraction
│   │   └── main.py                   # Entry point
│   ├── requirements.txt
│   ├── requirements-test.txt         # (MỚI) Dependencies riêng cho test
│   └── Dockerfile
├── frontend/                         # ═══ REACT FRONTEND ═══
│   ├── src/
│   │   ├── app/                      # Entry, Providers, Global styles
│   │   ├── shared/                   # Components, API client, Hooks, Utils dùng chung
│   │   ├── features/                 # Modules theo tính năng (Feature-Sliced)
│   │   ├── pages/                    # Page-level composition
│   │   └── types/                    # TypeScript type definitions
│   ├── playwright.config.ts          # (MỚI) Cấu hình Playwright
│   ├── package.json
│   └── Dockerfile
├── tests/                            # ═══ KIỂM THỬ KỸ THUẬT PHẦN MỀM (14 NHÁNH) ═══
│   ├── functional_testing/           # Kiểm thử chức năng (Unit, Integration, System, E2E...)
│   └── non_functional_testing/       # Kiểm thử phi chức năng (Performance, Security...)
├── ai_training/                      # ═══ AI TRAINING SCRIPTS ═══ (Gộp từ train_model và processed)
├── dataset/                          # Dataset CSV + features (giữ nguyên)
├── docker-compose.yml
├── docker-compose.prod.yml
├── nginx.conf
└── docs/                             # (MỚI) Tài liệu kỹ thuật tập trung
```

### 2.2. Backend – Chi tiết từng thư mục

```text
backend/app/
│
├── core/                              # ═══ TẦM HẠ TẦNG LÕI ═══
│   ├── __init__.py
│   ├── config.py                      # << DỜI TỪ app/config.py
│   │                                  #    Lý do: Config là nền tảng, phải nằm riêng biệt.
│   ├── security.py                    # << TẠO MỚI: Gom JWT encode/decode, password hashing
│   │                                  #    Lý do: Tách logic mật mã khỏi auth router.
│   ├── dependencies.py                # << TẠO MỚI: FastAPI Depends (get_current_user, get_db)
│   │                                  #    Lý do: Tập trung dependency injection, tránh import chéo.
│   ├── exceptions.py                  # << TẠO MỚI: Custom exception classes + Global handler
│   │                                  #    Lý do: Xử lý lỗi tập trung, trả JSON thống nhất.
│   ├── logging.py                     # << DỜI TỪ app/logging_config.py + app/logging_utils.py
│   │                                  #    Lý do: Gom 2 file log thành 1, dùng Loguru.
│   ├── constants.py                   # << TẠO MỚI: Enum, magic numbers, status codes
│   │                                  #    Lý do: Loại bỏ các string cứng rải rác trong code.
│   ├── rbac_model.conf                # << TẠO MỚI: Cấu hình Casbin Model (Luật phân quyền)
│   │                                  #    Lý do: Tách logic phân quyền (AuthZ) ra khỏi code, quản lý tập trung.
│   └── casbin_enforcer.py             # << TẠO MỚI: Khởi tạo PyCasbin Enforcer với DB Adapter
│                                      #    Lý do: Công cụ thực thi luật phân quyền, load model và adapter từ DB.
│
├── middleware/                        # ═══ TẦM TRUNG GIAN ═══
│   ├── __init__.py
│   ├── cors.py                        # << TẠO MỚI: Cấu hình CORS riêng
│   │                                  #    Lý do: CORS là security concern, không nên nằm trong main.py
│   ├── rate_limiter.py                # << DỜI TỪ app/limiter.py
│   │                                  #    Lý do: Rate limiter là middleware, nằm đúng vị trí.
│   ├── request_id.py                  # << TẠO MỚI: Gắn X-Request-ID cho mỗi request
│   │                                  #    Lý do: Truy vết log, debug production dễ dàng.
│   ├── audit_logger.py                # << TẠO MỚI: Middleware thu thập IP, GeoIP, User-Agent
│   │                                  #    Lý do: Ghi nhận Audit Log (Trusted Proxy, CF-IPCountry)
│   ├── auth_guard.py                  # << TẠO MỚI: Middleware kiểm tra JWT trước khi vào Router (AuthN)
│   │                                  #    Lý do: Tách logic xác thực (Authentication) khỏi từng endpoint cụ thể.
│   ├── tenant_context.py              # << TẠO MỚI: Middleware inject workspace_id vào request state
│   │                                  #    Lý do: SaaS Multi-tenancy – mọi query phải filter theo workspace.
│   │                                  #    Sau khi auth_guard xác thực user, middleware này resolve
│   │                                  #    workspace_id từ JWT/header và gắn vào request.state.
│   │                                  #    Tất cả Repository methods tự động nhận workspace scope.
│   └── authorization_guard.py         # << TẠO MỚI: Middleware Phân quyền (AuthZ) tích hợp Casbin + Redis
│                                      #    Lý do: Sử dụng casbin_enforcer để chặn các request trái phép
│                                      #    dựa trên (user, workspace, action), có cache qua Redis.
│
├── orm/                               # ═══ TẦM ORM (SQLAlchemy Models) ═══
│   ├── __init__.py
│   ├── base_model.py                  # Base class cho SQLAlchemy
│   ├── user_model.py                  # Model định nghĩa bảng users trong DB
│   └── ...                            # (Không dùng tên models/ để tránh nhầm với AI models)
│
├── schemas/                           # ═══ TẦM KIỂM DUYỆT (Pydantic) ═══
│   ├── __init__.py
│   ├── auth_schema.py                 # LoginRequest, TokenResponse, RegisterRequest
│   ├── user_schema.py                 # UserProfile, UserUpdate
│   ├── class_schema.py                # ClassCreate, ClassUpdate, ClassResponse
│   ├── sample_schema.py               # SampleCreate, SampleResponse, UploadPayload
│   ├── session_schema.py              # SessionCreate, SessionCommit
│   ├── training_schema.py             # << BÓC TỪ routers/training.py (TrainingConfig, TrainingJob, etc.)
│   ├── taxonomy_schema.py             # LanguageResponse, DialectResponse
│   ├── workspace_schema.py            # << TẠO MỚI: WorkspaceCreate, WorkspaceMemberInvite, QuotaResponse
│   ├── dataset_schema.py              # << TẠO MỚI: DatasetVersionCreate, DatasetManifest
│   ├── model_schema.py                # << TẠO MỚI: ModelCreate, ModelResponse, ModelDownloadLink
│   └── common_schema.py               # PaginatedResponse, ErrorResponse, SuccessResponse
│                                      # Lý do chung: Tách validation khỏi Router.
│                                      # Router chỉ import schema, không định nghĩa Pydantic model.
│
├── repositories/                      # ═══ TẦM DỮ LIỆU (Data Access) ═══
│   ├── __init__.py
│   ├── base_repository.py             # << TẠO MỚI: Abstract base với CRUD methods chung
│   │                                  #    Lý do: DRY – tránh copy-paste logic đọc/ghi CSV/DB.
│   │                                  #    Base class nhận workspace_id, tự filter dữ liệu theo tenant.
│   ├── sample_repository.py           # << BÓC TỪ dataset_samples.py
│   │                                  #    Lý do: Đóng gói toàn bộ thao tác đọc/ghi samples.csv.
│   ├── class_repository.py            # << BÓC TỪ dataset_manager.py (phần labels/classes)
│   │                                  #    Lý do: Tách thao tác CRUD lên labels.csv.
│   ├── session_repository.py          # << TẠO MỚI: Quản lý COLLECTION_SESSIONS
│   ├── user_repository.py             # << TẠO MỚI: Quản lý Users (hiện nằm trong auth.py)
│   ├── training_repository.py         # << BÓC TỪ train_task.py (phần lưu/đọc job state)
│   ├── sync_repository.py             # << BÓC TỪ catalog_sync.py (phần Google Sheets I/O)
│   ├── gdrive_repository.py           # << DỜI TỪ storage/gdrive_client.py
│   │                                  #    Lý do: Google Drive là storage layer = Repository.
│   ├── workspace_repository.py        # << TẠO MỚI: CRUD Workspaces, Members, Quota
│   │                                  #    Lý do: Multi-tenancy – quản lý tổ chức/nhóm.
│   ├── dataset_repository.py          # << TẠO MỚI: CRUD DATASETS (versioning, manifests)
│   │                                  #    Lý do: Quản lý phiên bản Dataset, file manifest.
│   └── model_repository.py            # << TẠO MỚI: CRUD MODELS (weights, metadata)
│                                      #    Lý do: Quản lý Model AI đã train, file trọng số.
│
├── services/                          # ═══ TẦM NGHIỆP VỤ (Business Logic) ═══
│   ├── __init__.py
│   ├── auth_service.py                # << BÓC TỪ app/auth.py (phần logic register/login/refresh)
│   │                                  #    Lý do: Auth logic phức tạp không thuộc Router.
│   ├── upload_service.py              # << BÓC TỪ routers/upload.py (tiền xử lý, normalize, save)
│   │                                  #    Lý do: 15KB logic upload không nên nằm trong Router.
│   ├── class_service.py               # << BÓC TỪ dataset_manager.py (phần logic: fork, merge, normalize)
│   │                                  #    Lý do: Logic Taxonomy Forking phải nằm trong Service riêng.
│   ├── sample_service.py              # << BÓC TỪ dataset_samples.py (phần logic: append, validate)
│   ├── training_service.py            # << BÓC TỪ train_task.py + routers/training.py
│   │                                  #    Lý do: Logic quản lý Training Job cực kỳ phức tạp.
│   ├── trash_service.py               # << BÓC TỪ routers/trash.py (logic soft delete/restore)
│   ├── export_service.py              # << BÓC TỪ export_tasks.py (logic đồng bộ Google Sheets)
│   ├── realtime_service.py            # << BÓC TỪ routers/realtime_proxy.py (WebSocket logic)
│   ├── workspace_service.py           # << TẠO MỚI: Quản lý Workspace, mời thành viên, RBAC
│   │                                  #    Lý do: SaaS multi-tenancy – logic tạo/xóa/phân quyền tổ chức.
│   ├── quota_service.py               # << TẠO MỚI: Cấp phát & Thu hồi tài nguyên
│   │                                  #    Lý do: Quản lý Storage Quota, GPU/RAM cho Training.
│   │                                  #    Gồm: check_quota(), allocate(), release(), get_usage()
│   ├── dataset_service.py             # << TẠO MỚI: Đóng băng Dataset version, tạo manifest
│   │                                  #    Lý do: Logic snapshot video → tạo Dataset v1.0, v2.0.
│   ├── model_service.py               # << TẠO MỚI: Quản lý vòng đời Model (train → deploy → retire)
│   │                                  #    Lý do: Logic quản lý trọng số, metadata, download link.
│   └── legal_service.py               # << TẠO MỚI: Quản lý Tài liệu pháp lý (Terms, Privacy, Cookies)
│                                      #    Lý do: Lưu Metadata vào LEGAL_DOCUMENTS, nội dung vào LEGAL_DOCUMENT_VERSIONS.
│                                      #    Xử lý versioning (Draft/Publish), lưu Acceptances & Cookie Consents.
│
├── routers/                           # ═══ TẦM GIAO TIẾP HTTP ═══ (Mỏng nhất có thể)
│   ├── __init__.py
│   ├── v1/                            # << TẠO MỚI: Versioned API
│   │   ├── __init__.py                #    Lý do: Chuẩn bị cho API Gateway, hỗ trợ backward compatibility.
│   │   ├── auth.py                    #    Chỉ còn: @router.post("/login") -> gọi auth_service
│   │   ├── classes.py
│   │   ├── samples.py                 # << ĐỔI TÊN từ dataset.py
│   │   ├── upload.py
│   │   ├── sessions.py                # << ĐỔI TÊN từ session.py
│   │   ├── training.py
│   │   ├── trash.py
│   │   ├── taxonomies.py
│   │   ├── experiments.py
│   │   ├── tts.py
│   │   ├── health.py
│   │   ├── realtime.py                # << ĐỔI TÊN từ realtime_proxy.py
│   │   ├── workspaces.py              # << TẠO MỚI: CRUD Workspace, mời member, xem quota
│   │   ├── datasets.py                # << TẠO MỚI: Tạo Dataset version, list versions
│   │   └── models.py                  # << TẠO MỚI: List Models, download weights, delete model
│   └── router_registry.py            # << TẠO MỚI: Tập trung include_router ở 1 chỗ
│                                      #    Lý do: main.py không nên biết tên từng router cụ thể.
│
├── workers/                           # ═══ TẦM TÁC VỤ NỀN ═══
│   ├── __init__.py
│   ├── celery_app.py                  # << DỜI TỪ app/worker.py
│   ├── sync_tasks.py                  # << BÓC TỪ export_tasks.py (Celery tasks đồng bộ Sheets)
│   ├── training_tasks.py              # << BÓC TỪ train_task.py (Celery tasks khởi chạy training)
│   ├── resource_tasks.py              # << TẠO MỚI: Cấp phát & thu hồi tài nguyên GPU/RAM
│   │                                  #    Lý do: Khi training xong/fail → tự động release resources.
│   │                                  #    Celery beat kiểm tra mỗi 60s: job nào hết quota → kill.
│   └── cleanup_tasks.py              # << TẠO MỚI: Hệ thống Garbage Collection toàn diện
│                                      #    Lý do: Tách Celery task definitions khỏi business logic.
│                                      #    Bao gồm các cronjob chạy mỗi đêm:
│                                      #    ┌─────────────────────────────────────────────────────┐
│                                      #    │ 1. gc_abandoned_sessions()                          │
│                                      #    │    → Dọn COLLECTION_SESSIONS status='in_progress'   │
│                                      #    │      quá 24h → chuyển 'abandoned' + xóa file GDrive │
│                                      #    │ 2. gc_orphaned_features()                           │
│                                      #    │    → Quét thư mục features/ tìm file .npz không     │
│                                      #    │      có dòng tương ứng trong samples.csv → xóa      │
│                                      #    │ 3. gc_expired_tokens()                              │
│                                      #    │    → Xóa USER_SESSIONS.expires_at < now() khỏi DB   │
│                                      #    │      và Redis Denylist                              │
│                                      #    │ 4. gc_soft_deleted_resources()                      │
│                                      #    │    → Xóa vĩnh viễn records có deleted_at > 30 ngày  │
│                                      #    │      (Samples, Classes, Models, Datasets)            │
│                                      #    │ 5. gc_training_artifacts()                          │
│                                      #    │    → Xóa checkpoint files của training jobs failed   │
│                                      #    │      hoặc đã quá 90 ngày                            │
│                                      #    │ 6. gc_log_rotation()                                │
│                                      #    │    → Xóa file log hệ thống quá retention_days       │
│                                      #    │ 7. gc_reclaim_storage_quota()                       │
│                                      #    │    → Recalculate storage_used cho mỗi Workspace     │
│                                      #    │      sau khi dọn rác (tránh quota bị lệch)          │
│                                      #    └─────────────────────────────────────────────────────┘
│
├── processing/                        # ═══ XỬ LÝ AI ═══ (Giữ nguyên vị trí)
│   ├── __init__.py
│   └── utils.py                       # Normalize landmarks, feature extraction
│
└── main.py                            # Entry point: chỉ import middleware, router_registry, startup/shutdown
```

### 2.3. Frontend – Chi tiết từng thư mục

```text
frontend/src/
│
├── app/                               # ═══ APPLICATION SHELL ═══
│   ├── App.tsx                        # << DỜI TỪ src/App.tsx
│   ├── App.css                        # << DỜI
│   ├── main.tsx                       # << DỜI TỪ src/main.tsx
│   ├── index.css                      # << DỜI TỪ src/index.css
│   ├── providers/                     # << TẠO MỚI: Gom AuthProvider, QueryProvider
│   │   ├── AuthProvider.tsx           #    Lý do: Quản lý auth context tập trung
│   │   └── AppProviders.tsx           #    Lý do: Bọc tất cả Providers vào 1 component
│   └── router.tsx                     # << TẠO MỚI: React Router config tách riêng
│                                      #    Lý do: main.tsx chỉ render, không chứa routing logic.
│
├── shared/                            # ═══ CODE DÙNG CHUNG ═══
│   ├── api/                           # << DỜI TỪ src/api/
│   │   ├── axiosClient.ts            #    Cấu hình Axios interceptors (attach token, refresh)
│   │   ├── auth.ts
│   │   ├── dataset.ts
│   │   ├── upload.ts
│   │   ├── trash.ts
│   │   ├── taxonomies.ts
│   │   ├── realtime.ts
│   │   ├── tts.ts
│   │   ├── preferences.ts
│   │   ├── jobs.ts
│   │   └── validators.ts
│   ├── components/                    # << DỜI TỪ src/components/ui/
│   │   ├── Badge.tsx
│   │   ├── Button.tsx
│   │   ├── EmptyState.tsx
│   │   ├── LoadingSpinner.tsx
│   │   ├── Modal.tsx
│   │   ├── PageHeader.tsx
│   │   ├── Pagination.tsx
│   │   ├── Select.tsx
│   │   ├── SmartLoader.tsx
│   │   ├── Table.tsx
│   │   ├── Toast.tsx
│   │   └── ToastContainer.tsx
│   ├── hooks/                         # << DỜI TỪ src/hooks/ (hooks dùng chung)
│   │   ├── useAuth.ts
│   │   ├── useFetch.ts
│   │   └── useToast.tsx
│   ├── utils/                         # << DỜI TỪ src/utils/
│   │   ├── role.ts
│   │   └── constants.ts              # << TẠO MỚI: API URLs, magic strings
│   ├── config/                        # << DỜI TỪ src/config/
│   │   ├── capture.ts
│   │   └── dialectLabels.ts
│   └── types/                         # << DỜI TỪ src/types/ + src/types.ts
│       ├── mediapipe-hands.d.ts
│       └── index.ts                   # Gom export toàn bộ type definitions
│
├── features/                          # ═══ MODULES TÍNH NĂNG ═══
│   │                                  # Lý do: Mỗi feature là 1 ốc đảo tự chứa (self-contained).
│   │                                  # Khi xóa 1 feature, không ảnh hưởng feature khác.
│   │
│   ├── auth/                          # 🔐 Xác thực
│   │   ├── components/
│   │   │   ├── LoginForm.tsx          # << BÓC TỪ pages/LoginPage.tsx
│   │   │   └── RegisterForm.tsx       # << BÓC TỪ pages/RegisterPage.tsx
│   │   └── hooks/
│   │       └── useLoginFlow.ts        # << TẠO MỚI
│   │
│   ├── dashboard/                     # 📊 Bảng điều khiển
│   │   ├── components/                # << DỜI TỪ components/dashboard/
│   │   │   ├── AnalyticsOverview.tsx
│   │   │   ├── CommunityStatsSection.tsx
│   │   │   ├── DatasetStats.tsx
│   │   │   ├── HeroSection.tsx
│   │   │   ├── MyContributionSection.tsx
│   │   │   ├── QuickActionsSection.tsx
│   │   │   ├── SessionList.tsx
│   │   │   └── FilterPanel.tsx
│   │   └── hooks/
│   │       └── useDashboardData.ts    # << TẠO MỚI
│   │
│   ├── admin/                         # 🛠 Quản trị hệ thống & Giám sát
│   │   ├── components/
│   │   │   ├── LegalDocumentEditor.tsx # Tích hợp React-Markdown Editor
│   │   │   ├── LogViewer.tsx           # UI xem log từ backend (Websocket hoặc Polling)
│   │   │   ├── SystemHealthPanel.tsx   # Hiển thị CPU, RAM, Disk, DB Connection
│   │   │   └── ActiveSessionsTable.tsx # Giám sát các phiên người dùng
│   │   └── hooks/
│   │       ├── useLegalDocs.ts
│   │       └── useSystemMonitoring.ts
│   │
│   ├── taxonomy/                      # 📚 Thư viện nhãn
│   │   ├── components/
│   │   │   ├── LabelCard.tsx          # << BÓC TỪ pages/LabelsPage.tsx
│   │   │   ├── LabelList.tsx
│   │   │   └── AddDialectModal.tsx    # << DỜI TỪ components/AddDialectModal.tsx
│   │   └── hooks/
│   │       └── useTaxonomy.ts
│   │
│   ├── capture/                       # 📹 Thu thập video
│   │   ├── components/
│   │   │   ├── CaptureCamera.tsx      # << DỜI
│   │   │   ├── CaptureGuide.tsx       # << DỜI
│   │   │   ├── FullscreenCaptureModal.tsx  # << DỜI
│   │   │   ├── SessionPanel.tsx       # << DỜI
│   │   │   └── SessionSummary.tsx     # << DỜI
│   │   ├── hooks/
│   │   │   └── useCaptureSession.ts   # << TẠO MỚI
│   │   └── utils/
│   │       └── mediapipeHelpers.ts    # << TẠO MỚI
│   │
│   ├── upload/                        # ⬆️ Upload hàng loạt
│   │   ├── components/
│   │   │   ├── UploadVideoForm.tsx    # << DỜI
│   │   │   └── SamplePreview.tsx      # << DỜI
│   │   └── hooks/
│   │       └── useUploadFlow.ts       # << TẠO MỚI
│   │
│   ├── realtime/                      # 🤖 Nhận diện thời gian thực
│   │   ├── components/
│   │   │   └── RealtimeRuntime.tsx    # << DỜI
│   │   ├── hooks/
│   │   │   └── useSpeechToText.ts     # << DỜI TỪ hooks/useSpeechToText.ts
│   │   └── utils/
│   │       ├── oneEuro.ts             # << DỜI
│   │       ├── predictionSmoother.ts  # << DỜI
│   │       ├── realtimeFlatten.ts     # << DỜI
│   │       ├── realtimeInferenceScheduler.ts  # << DỜI
│   │       └── realtimeRingBuffer.ts  # << DỜI
│   │
│   ├── training/                      # 🧠 Huấn luyện mô hình
│   │   ├── components/
│   │   │   └── TrainingDashboard.tsx   # << TẠO MỚI (hiện nằm trong pages)
│   │   └── hooks/
│   │       └── useTrainingAPI.ts      # << DỜI TỪ hooks/useTrainingAPI.ts
│   │
│   └── trash/                         # 🗑️ Thùng rác
│       ├── components/
│       │   └── TrashList.tsx          # << BÓC TỪ pages/TrashPage.tsx
│       └── hooks/
│           └── useTrashActions.ts     # << TẠO MỚI
│
├── pages/                             # ═══ PAGE COMPOSITION ═══
│   │                                  # Lý do: Pages chỉ lắp ráp features, không chứa business logic.
│   ├── DashboardPage.tsx
│   ├── LabelsPage.tsx
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── UploadPage.tsx
│   ├── TrashPage.tsx
│   ├── TrainingPage.tsx               # << TẠO MỚI (tách từ logic hiện tại)
│   ├── PublicUploadPage.tsx
│   └── RealtimeRecognitionPage.tsx
│
└── types/                             # Global TypeScript declarations
    └── mediapipe-hands.d.ts
```

### 2.4. Thư mục Kiểm thử (Testing) – Chi tiết

```text
tests/                                # ═══ HỆ THỐNG KIỂM THỬ KỸ THUẬT PHẦN MỀM ═══
├── functional_testing/               # ─── KIỂM THỬ CHỨC NĂNG ───
│   ├── unit_testing/                 # Cấp độ 1: Kiểm thử cô lập (Hàm, Class)
│   │   ├── backend/
│   │   │   ├── core/                 # Test security, config, utils
│   │   │   │   ├── test_security.py
│   │   │   │   └── test_config.py
│   │   │   ├── schemas/              # Test Pydantic validation
│   │   │   │   ├── test_auth_schema.py
│   │   │   │   └── test_dataset_schema.py
│   │   │   └── services/             # Test business logic (mock repo)
│   │   │       ├── test_auth_service.py
│   │   │       ├── test_upload_service.py
│   │   │       └── test_legal_service.py
│   │   └── frontend/
│   │       ├── shared/               # Test common hooks, utils
│   │       │   ├── useFetch.test.ts
│   │       │   └── validators.test.ts
│   │       └── features/             # Test logic nội bộ của feature
│   │           └── auth/
│   │               └── useLoginFlow.test.ts
│   ├── component_testing/            # Cấp độ 2: Kiểm thử thành phần (UI/DB)
│   │   ├── backend/                  # Test Repositories với DB SQLite in-memory
│   │   │   ├── fixtures/             # Dữ liệu mẫu (Factories)
│   │   │   ├── test_user_repository.py
│   │   │   └── test_model_repository.py
│   │   └── frontend/                 # Test React Components với React Testing Library
│   │       ├── shared/
│   │       │   ├── Button.test.tsx
│   │       │   └── Modal.test.tsx
│   │       └── features/
│   │           └── LoginForm.test.tsx
│   ├── integration_testing/          # Cấp độ 3: Kiểm thử ghép nối
│   │   ├── backend_api/              # Test Router -> Service -> DB (FastAPI TestClient)
│   │   │   ├── test_auth_flow.py     # Login -> Lấy Token
│   │   │   └── test_upload_flow.py   # Upload -> Lưu DB -> MinIO mock
│   │   └── frontend_hooks/           # Test Custom Hooks + API Backend Mock (MSW)
│   │       └── useTrainingAPI.test.ts
│   ├── system_testing/               # Cấp độ 4: Kiểm thử toàn hệ thống (Playwright E2E)
│   │   ├── config/
│   │   │   └── playwright.config.ts
│   │   ├── helpers/
│   │   │   └── auth.helper.ts        # Hàm login nhanh cho E2E
│   │   └── specs/
│   │       ├── auth.spec.ts          # UI: Đăng ký -> Đăng nhập -> Dashboard
│   │       ├── upload.spec.ts        # UI: Chọn file -> Kéo thả -> Upload -> Toast
│   │       └── training.spec.ts      # UI: Chọn Model -> Train -> Progress bar
│   ├── smoke_testing/                # Kiểm thử khói (Chạy nhanh sau khi deploy/build)
│   │   ├── backend_health.py         # Ping /api/v1/health đảm bảo server chạy
│   │   └── frontend_load.spec.ts     # Kiểm tra trang chủ có render ra được UI không
│   ├── sanity_testing/               # Kiểm thử tỉnh táo (Sau khi fix bug)
│   │   └── test_bugfix_102.py        # Đảm bảo lỗi crash khi upload file > 50MB đã hết
│   ├── regression_testing/           # Kiểm thử hồi quy
│   │   └── test_legacy_api.py        # Đảm bảo API cũ (v1) vẫn hoạt động khi ra mắt API v2
│   └── user_acceptance_testing/      # Kịch bản UAT (Giao cho QA / Khách hàng)
│       └── uat_checklists.md         # Bảng checklist nghiệm thu thủ công
│
└── non_functional_testing/           # ─── KIỂM THỬ PHI CHỨC NĂNG ───
    ├── performance_testing/          # Kiểm thử hiệu năng
    │   ├── load_testing/             # Sức chịu tải (Locust/k6)
    │   │   ├── locustfile.py         # Kịch bản 1000 user login đồng thời
    │   │   └── k6_upload_test.js     # Kịch bản 500 user upload video cùng lúc
    │   └── stress_testing/           # Thử thách sập server (Tìm điểm chết)
    │       └── max_connection.py     # Mở 10000 kết nối WebSocket xem khi nào sập
    ├── security_testing/             # Kiểm thử bảo mật (Pen-test tự động)
    │   ├── authz_bypass.py           # Thử truy cập chéo tenant (Tenant A xem data Tenant B)
    │   ├── jwt_manipulation.py       # Sửa đổi JWT Signature, đổi hạn sử dụng token
    │   ├── rate_limit_test.py        # Spam 100 request/giây xem có bị chặn (429) không
    │   └── payloads/
    │       ├── sqli_payloads.txt     # Test SQL Injection vào form search
    │       └── xss_payloads.txt      # Test XSS vào tên Workspace/Label
    ├── scalability_testing/          # Kiểm thử khả năng mở rộng
    │   └── test_worker_scaling.py    # Đẩy 1000 job training, kiểm tra Celery có tự auto-scale không
    ├── reliability_testing/          # Kiểm thử độ tin cậy
    │   ├── failover_db.py            # Đánh sập Redis xem hệ thống có fallback về DB không
    │   └── failover_storage.py       # Ngắt kết nối MinIO xem có queue retry không
    ├── usability_testing/            # Kiểm thử tính khả dụng (UI/UX)
    │   ├── lighthouse_audit.js       # Đo điểm Accessibility, SEO, Web Vitals
    │   └── color_contrast_test.js    # Kiểm tra độ tương phản màu sắc đạt chuẩn WCAG
    └── interoperability_testing/     # Kiểm thử tương tác ngoại vi
        ├── test_sso_google.py        # Test quá trình đăng nhập qua Google OAuth
        └── test_gdrive_sync.py       # Test API đồng bộ dữ liệu với Google Drive
```

---

## 3. NGUYÊN TẮC KIỂM THỬ (Testing Principles)

### 3.1. Kim tự tháp kiểm thử (Testing Pyramid)

```
        ╱╲
       ╱ E2E ╲           ← Ít nhất (5-10 bài) – Chậm, tốn tài nguyên
      ╱────────╲            Chạy trên trình duyệt thật bằng Playwright
     ╱Integration╲       ← Trung bình (20-30 bài) – Gọi API thật, Mock DB
    ╱──────────────╲
   ╱   Unit Tests    ╲   ← Nhiều nhất (50+ bài) – Cô lập, cực nhanh
  ╱────────────────────╲
```

### 3.2. Quy tắc Kiểm thử Bắt Buộc

| Quy tắc | Giải thích |
|---|---|
| **① Arrange-Act-Assert (AAA)** | Mỗi bài test phải có 3 phần rõ ràng: Chuẩn bị dữ liệu → Thực thi hành động → Kiểm tra kết quả |
| **② Tên bài test phải mô tả kịch bản** | ✅ `test_login_with_wrong_password_returns_401` ❌ `test_login_1` |
| **③ Mỗi bài test là độc lập** | Không được phụ thuộc vào kết quả của bài test khác. Dữ liệu test phải setup và teardown riêng biệt |
| **④ Mock ở ranh giới hệ thống** | Unit test Service → Mock Repository. Integration test → Mock Google Drive API, không mock Service |
| **⑤ Không test implementation, test behavior** | Test xem "upload trả về sample_uid" chứ không test "hàm X được gọi Y lần" |
| **⑥ Test phải chạy offline** | Tuyệt đối không kết nối Google Drive, Redis, hay bất kỳ service bên ngoài nào trong Unit Test |
| **⑦ Coverage target: ≥ 70% cho Services** | Services là "não bộ" – phải được bảo vệ bằng test dày đặc nhất |
| **⑧ CI chặn merge nếu test fail** | Mọi Pull Request phải pass toàn bộ test suite trước khi được merge |

### 3.3. Công cụ & Cấu hình

| Loại | Backend | Frontend |
|---|---|---|
| **Framework** | `pytest` + `pytest-asyncio` | `vitest` + `@testing-library/react` |
| **Mock HTTP** | `httpx` (TestClient), `unittest.mock` | `msw` (Mock Service Worker) |
| **E2E** | — | `@playwright/test` |
| **Coverage** | `pytest-cov` | Vitest built-in coverage |
| **CI Runner** | GitHub Actions / GitLab CI | GitHub Actions / GitLab CI |

### 3.4. Playwright E2E – Quy tắc Riêng

| Quy tắc | Chi tiết |
|---|---|
| **Selector strategy** | Ưu tiên `data-testid` trên mọi element tương tác. Tuyệt đối không dùng CSS class hay XPath mong manh |
| **Trạng thái sạch** | Mỗi test suite phải tự login vào tài khoản test riêng, không dùng chung session |
| **Timeout** | Global timeout: 30s. Navigation timeout: 15s. Assertion timeout: 5s |
| **Screenshot on failure** | Tự động chụp ảnh màn hình khi test fail (Playwright hỗ trợ sẵn) |
| **Video recording** | Bật recording cho CI runs để debug khi test fail trên server |
| **Parallel** | Chạy song song tối đa 2 workers để tránh xung đột dữ liệu |

---

## 4. API GATEWAY & BẢO MẬT

### 4.1. API Gateway – Cần hay Không?

> **Kết luận: Chưa cần API Gateway riêng biệt ở giai đoạn hiện tại.**

**Lý do:**
- Hệ thống hiện tại chỉ có 1 Backend (FastAPI) phía sau Nginx reverse proxy.
- API Gateway (như Kong, AWS API Gateway) chỉ cần thiết khi có **nhiều microservices** cần điều phối.
- Nginx hiện tại đã đảm nhiệm tốt vai trò: Reverse proxy, SSL termination, Static file serving.

**Giải pháp thay thế bằng Middleware nội bộ:**
Thay vì dựng API Gateway bên ngoài, ta sẽ xây dựng các lớp Middleware bên trong FastAPI để xử lý:

| Tính năng API Gateway | Giải pháp nội bộ |
|---|---|
| Rate Limiting | `middleware/rate_limiter.py` (dùng SlowAPI + Redis) |
| Authentication | `middleware/auth_guard.py` + `core/security.py` |
| CORS | `middleware/cors.py` |
| Request Logging / Tracing | `middleware/request_id.py` + `core/logging.py` |
| Input Validation | `schemas/*.py` (Pydantic) |
| API Versioning | `routers/v1/` prefix path |

**Khi nào cần nâng cấp lên API Gateway thực sự?**
- Khi tách Backend thành microservices (VD: tách Training Service ra container riêng).
- Khi cần OAuth2 gateway cho bên thứ 3 truy cập API.
- → Lúc đó chuyển sang **Traefik** (đã có sẵn trong K3s) hoặc **Kong**.

### 4.2. Cấu hình Bảo mật

```text
backend/app/core/
├── security.py                        # JWT encode/decode, password hashing (bcrypt)
│   ├── create_access_token()
│   ├── create_refresh_token()
│   ├── verify_token()
│   ├── hash_password()
│   └── verify_password()
│
├── dependencies.py                    # FastAPI Depends
│   ├── get_current_user()             # Decode JWT, trả về User object
│   ├── get_current_admin()            # get_current_user() + check role == admin
│   ├── get_optional_user()            # Cho các endpoint public có thể login hoặc không
│   └── get_db_session()               # (Chuẩn bị cho PostgreSQL) yield db session
│
└── exceptions.py                      # Custom Exceptions
    ├── UnauthorizedException          # 401 – Token hết hạn / không hợp lệ
    ├── ForbiddenException             # 403 – Không đủ quyền
    ├── NotFoundException              # 404 – Resource không tồn tại
    ├── ConflictException              # 409 – Trùng lặp (VD: email đã tồn tại)
    └── ValidationException            # 422 – Dữ liệu không hợp lệ
```

---

## 5.0. KẾT QUẢ ĐỐI CHIẾU ERD: `database_dictionary.md` vs `SignBridge_Architecture.md`

Sau khi đối chiếu kỹ lưỡng 2 tài liệu, phát hiện các điểm khác biệt quan trọng cần đồng bộ trước khi tạo Database Schema:

### 5.0.1. Các bảng có trong Architecture nhưng THIẾU trong Dictionary ERD

| Bảng | Domain | Ghi chú |
|---|---|---|
| `SYSTEM_AUDIT_LOGS` | Auth & Audit | Bảng truy vết hành động (CREATE/UPDATE/DELETE). Có `workspace_id` FK – quan trọng cho Multi-tenancy |
| `USER_SESSIONS` | Auth | Quản lý phiên đăng nhập & thu hồi token (Revocation). Cột `refresh_token_hash`, `is_revoked` |
| `CATEGORIES` | Taxonomy | Bảng Chủ đề (Y tế, Giao thông…) – vệ tinh của CLASSES |
| `CLASS_CATEGORIES` | Taxonomy | Bảng trung gian Nhiều-Nhiều giữa CLASSES và CATEGORIES |
| `SIGN_FEATURES` | Taxonomy | Đặc tính cử chỉ (2 tay, biểu cảm mặt…) |
| `PROJECT_MEMBERS` | Auth | Phân quyền cấp Project (Manager, Contributor) với `project_role` và `joined_at` |

### 5.0.2. Các cột có trong Architecture nhưng THIẾU trong Dictionary

| Bảng | Cột | Ghi chú |
|---|---|---|
| `SAMPLES` | `upload_uid` (FK → RAW_UPLOADS) | Truy vết nguồn gốc nếu sample sinh ra từ file ZIP upload |
| `DATASETS` | `workspace_id` (FK → WORKSPACES) | **Multi-tenancy** – Dataset thuộc Workspace nào |
| `CLASSES` | `feature_id` (FK → SIGN_FEATURES) | Liên kết đặc tính cử chỉ |
| `SAMPLE_REVIEWS` | `suggested_class_uid` (FK → CLASSES) | QA gán nhãn đúng nếu phát hiện user gán sai |
| `LEGAL_DOCUMENTS` | `updated_at` | Dictionary có thêm cột này, Architecture không có – GIỮ LẠI |

### 5.0.3. Khác biệt về Mối quan hệ (Relationships)

| Mối quan hệ | Architecture | Dictionary | Hành động |
|---|---|---|---|
| `RAW_UPLOADS` → `SAMPLES` | Có (generates_samples) | Không có FK trực tiếp | **Thêm** FK `upload_uid` vào SAMPLES |
| `LOG_CATEGORIES` → `SYSTEM_LOG_FILES` | Có | Có | Đồng nhất ✅ |
| `WORKSPACES` → `SYSTEM_AUDIT_LOGS` | Có (audited_in) | Thiếu bảng | **Thêm** bảng SYSTEM_AUDIT_LOGS |
| `WORKSPACES` → `DATASETS` | Có (FK workspace_id) | Thiếu cột | **Thêm** cột workspace_id |

### 5.0.4. Kết luận & Hành động

> [!IMPORTANT]
> **[CẬP NHẬT 2026-07] Mục này đã được thực thi và thay thế bởi ERD v2.**
> Source of Truth về Schema hiện là [`docs/database/database_dictionary.md`](../database/database_dictionary.md) (đã đồng bộ theo ERD v2 — 37 bảng).
> Toàn bộ quyết định thiết kế (ADR-1 → ADR-8) và **Roadmap giai đoạn v2 (thay thế §5/§8 của tài liệu này)** xem tại [`docs/database/erd_v2_unified_design.md`](../database/erd_v2_unified_design.md) §7.
> Các bảng task GĐ 1–6 bên dưới giữ lại làm tham chiếu chi tiết; khi mâu thuẫn với Roadmap v2 thì **Roadmap v2 thắng**.

---

## 5. KẾ HOẠCH CHI TIẾT TỪNG GIAI ĐOẠN

### GIAI ĐOẠN 1: Thiết lập Hạ tầng Kiểm thử & Dọn Rác (Tuần 1)

**Mục tiêu:** Tạo "lưới an toàn" (Safety Net) bằng Test trước khi dời bất kỳ file nào.

| STT | Task | File liên quan | Output |
|---|---|---|---|
| 1.1 | Cấu hình pytest cho thư mục `tests/` ở root (theo cấu trúc 14 nhánh §2.4) + `conftest.py` | `conftest.py`, `requirements-test.txt` | Pytest chạy được |
| 1.2 | Viết **Characterization Tests** cho API hiện tại | `tests/integration/test_auth_flow.py` | Capture hành vi hiện tại |
| 1.3 | Viết Characterization Tests cho Upload API | `tests/integration/test_upload_flow.py` | Capture hành vi upload |
| 1.4 | Viết Characterization Tests cho Label CRUD | `tests/integration/test_label_crud.py` | Capture hành vi labels |
| 1.5 | Viết Characterization Tests cho Trash API | `tests/integration/test_trash_flow.py` | Capture hành vi trash |
| 1.6 | Cài đặt Vitest cho Frontend | `frontend/vitest.config.ts`, `tests/setup.ts` | Vitest chạy được |
| 1.7 | Xóa file rác ở root | `patch_*.py`, `old_*.tsx`, `*_backup.*`, `audit_*.py`, `debug_*.py` | Repo sạch |
| 1.8 | Di chuyển file tài liệu vào `docs/` | `docs/SignBridge_Architecture.md`, `docs/database_dictionary.md` | Tài liệu tập trung |
| 1.9 | **Đối chiếu ERD**: Kiểm định `database_dictionary.md` với `SignBridge_Architecture.md` | Tạo `docs/erd_audit_report.md` | Danh sách các bảng/cột bị thiếu/khác biệt (xem Mục 5.0 bên dưới) |
| 1.10 | **Cập nhật `database_dictionary.md`** theo ERD chuẩn từ Architecture | Thêm các bảng/cột thiếu, đồng bộ mối quan hệ (relationships) | 2 tài liệu đồng nhất 100% |

**Kiểm tra hoàn thành:** `pytest backend/tests/ -v` → Tất cả PASS ✅

---

### GIAI ĐOẠN 2: Tái cấu trúc Backend – Core, Middleware & Exceptions (Tuần 2)

**Mục tiêu:** Gom nhóm nền tảng hệ thống vào `core/` và `middleware/`.

| STT | Task | Chi tiết | Verification |
|---|---|---|---|
| 2.1 | Tạo `app/core/` và dời `config.py` | Cập nhật toàn bộ `from app.config` → `from app.core.config` | Import không lỗi |
| 2.2 | Tạo `core/security.py` | Bóc JWT logic + password hashing từ `app/auth.py` | Unit test `test_security.py` PASS |
| 2.3 | Tạo `core/dependencies.py` | Gom `get_current_user`, `get_current_admin` từ `auth.py` | Integration test auth PASS |
| 2.4 | Tạo `core/exceptions.py` | Viết Custom Exceptions + Global Exception Handler | Test trả về JSON chuẩn khi lỗi |
| 2.5 | Tạo `core/logging.py` | Gom `logging_config.py` + `logging_utils.py` | Log xuất ra đúng format |
| 2.6 | Tạo `core/constants.py` | Gom magic strings: status codes, role names | Grep không còn hardcoded string |
| 2.7 | Tạo `middleware/cors.py` | Bóc CORS config từ `main.py` | CORS vẫn hoạt động |
| 2.8 | Tạo `middleware/rate_limiter.py` | Dời `limiter.py` | Rate limit vẫn hoạt động |
| 2.9 | Tạo `middleware/request_tracing.py` | Gắn `X-Request-ID` và `X-Trace-ID` header cho mọi request | Kiểm tra header trong response |
| 2.10 | Tạo `middleware/audit_logger.py` | Middleware ghi `ACCESS_LOGS`, `SECURITY_LOGS` và lấy IP (Trusted Proxy), GeoIP | Logs lưu chuẩn JSONB |
| 2.11 | Tạo `middleware/tenant_context.py` | Inject `workspace_id` vào `request.state` từ JWT | Multi-tenant middleware hoạt động |
| 2.12 | **Tích hợp Casbin (AuthZ)** | Cài `casbin` & cấu hình Redis Adapter. Tạo `rbac_model.conf` | Enforcer ghi log `AUTHORIZATION_LOGS` |
| 2.13 | Tạo `middleware/authorization_guard.py` | Middleware phân quyền tự động dùng Casbin cho các route | Chặn request sai quyền trả 403 |
| 2.14 | **Thiết lập Alembic Migrations** | Cài Alembic, tạo file `alembic.ini` + `migrations/` | `alembic upgrade head` chạy được |
| 2.15 | **Tạo Initial Migration & Table Partitioning** | Tạo 25 bảng từ ERD + Legal Module. **Đặc biệt:** Thiết lập Table Partitioning (chia bảng theo tháng) cho `AUDIT_LOGS` và `ACCESS_LOGS` để giảm tải khi dữ liệu lớn | Schema PostgreSQL tối ưu cho Big Data |
| 2.16 | **Seed data cơ bản** | Tạo roles, languages, dialects mặc định và Seed RBAC Policies cho Casbin | DB có dữ liệu nền & Luật quyền |
| 2.17 | Chạy lại toàn bộ test Giai đoạn 1 | — | Tất cả Characterization Tests PASS ✅ |

---

### GIAI ĐOẠN 3: Tái cấu trúc Backend – Repositories (Tuần 3)

**Mục tiêu:** Cô lập toàn bộ logic truy xuất dữ liệu vào tầng `repositories/`.

| STT | Task | Source → Destination | Verification |
|---|---|---|---|
| 3.1 | Tạo `repositories/base_repository.py` | Viết mới: Abstract class với `read_csv`, `write_csv`, `find_by_id` | Unit test PASS |
| 3.2 | Tạo `repositories/sample_repository.py` | Bóc từ `dataset_samples.py` | `test_sample_repository.py` PASS |
| 3.3 | Tạo `repositories/class_repository.py` | Bóc từ `dataset_manager.py` (phần đọc/ghi `labels.csv`) | `test_class_repository.py` PASS |
| 3.4 | Tạo `repositories/user_repository.py` | Bóc từ `auth.py` (phần đọc/ghi user data) | `test_user_repository.py` PASS |
| 3.5 | Tạo `repositories/storage/minio_repository.py` | Quản lý Object Storage (Models, Datasets) thay cho Local/GDrive cũ. Đảm bảo Isolation (tenant-a/workspace-1/) | Upload/Download MinIO thành công |
| 3.6 | Tạo `repositories/cache/redis_repository.py` | Quản lý Redis Cache cho Session, Casbin, Rate Limit. Namespace theo `tenant:workspace:project` | Cache Hit/Miss hoạt động đúng |
| 3.7 | Tạo `repositories/training_repository.py` | Bóc từ `train_task.py` | Training data I/O cô lập |
| 3.8 | Tạo `repositories/sync_repository.py` | Bóc từ `catalog_sync.py` + `export_tasks.py` | Sheets sync vẫn hoạt động |
| 3.9 | Chạy lại toàn bộ test | — | Tất cả Tests PASS ✅ |

---

### GIAI ĐOẠN 4: Tái cấu trúc Backend – Schemas & Services (Tuần 4)

**Mục tiêu:** Bóc tách logic nghiệp vụ ra khỏi Routers, đẩy vào Services.

| STT | Task | Chi tiết | Verification |
|---|---|---|---|
| 4.1 | Tạo `schemas/` | Bóc Pydantic models từ `routers/training.py` và các router khác | Import schema PASS |
| 4.2 | Tạo `services/auth_service.py` | Bóc logic register/login/refresh từ `app/auth.py` | `test_auth_service.py` PASS |
| 4.3 | Tạo `services/upload_service.py` | Bóc logic tiền xử lý, normalize từ `routers/upload.py` | `test_upload_service.py` PASS |
| 4.4 | Tạo `services/class_service.py` | Bóc logic fork/merge/normalize từ `dataset_manager.py` | `test_class_service.py` PASS |
| 4.5 | Tạo `services/sample_service.py` | Bóc logic validate, append từ `dataset_samples.py` | `test_sample_service.py` PASS |
| 4.6 | Tạo `services/training_service.py` | Bóc logic job management từ `train_task.py` + `routers/training.py` | `test_training_service.py` PASS |
| 4.7 | Tạo `services/trash_service.py` | Bóc logic soft-delete/restore từ `routers/trash.py` | `test_trash_service.py` PASS |
| 4.8 | Tạo `services/export_service.py` | Bóc logic đồng bộ Sheets từ `export_tasks.py` | Export vẫn hoạt động |
| 4.9 | Tạo `services/legal_service.py` | Quản lý Legal Docs: Lưu Markdown vào DB, APIs Import/Export file `.md` | API trả về text Markdown chuẩn |
| 4.10 | Xây dựng API Quản trị & Giám sát | Tạo APIs: System Health, Xem Log xoay vòng, Quản lý Sessions | APIs trả về metric chuẩn |
| 4.11 | Tinh gọn Routers | Mỗi Router chỉ còn: validate schema → gọi service → trả response | Router files < 100 dòng |
| 4.12 | Tạo `routers/v1/` | Dời các router vào sub-package `v1/` | API prefix `/api/v1/` giữ nguyên |
| 4.13 | Tạo `routers/router_registry.py` | Tập trung `include_router` | `main.py` gọn nhẹ |
| 4.14 | Chuyển `workers/` | Dời `worker.py` → `workers/celery_app.py`, tách tasks | Celery beat vẫn chạy |
| 4.15 | Chạy lại toàn bộ test | — | Tất cả Tests PASS ✅ |

---

### GIAI ĐOẠN 5: Tái cấu trúc Frontend (Tuần 5-6)

**Mục tiêu:** Chuyển sang cấu trúc Feature-Sliced Design.

| STT | Task | Chi tiết | Verification |
|---|---|---|---|
| 5.1 | Tạo `src/app/`, dời `App.tsx`, `main.tsx`, `index.css` | Cập nhật entry point | `npm run dev` → trang hiển thị |
| 5.2 | Tạo `src/shared/`, dời `api/`, `components/ui/`, `hooks/`, `utils/`, `config/` | Cập nhật imports | Build không lỗi |
| 5.3 | Tạo `features/auth/` | Bóc LoginForm, RegisterForm từ pages | Login/Register hoạt động |
| 5.4 | Tạo `features/dashboard/` | Dời `components/dashboard/` | Dashboard hiển thị đúng |
| 5.5 | Tạo `features/taxonomy/` | Bóc logic label từ LabelsPage | LabelsPage hoạt động |
| 5.6 | Tạo `features/capture/` | Dời CaptureCamera, FullscreenCaptureModal | Camera hoạt động |
| 5.7 | Tạo `features/upload/` | Dời UploadVideoForm | Upload hoạt động |
| 5.8 | Tạo `features/realtime/` | Dời RealtimeRuntime + utils | Realtime hoạt động |
| 5.9 | Tạo `features/training/` | Dời useTrainingAPI | Training page hoạt động |
| 5.10 | Tạo `features/trash/` | Bóc logic từ TrashPage | Trash hoạt động |
| 5.11 | Tạo `features/admin/` | Xây dựng màn hình Giám sát (Log Viewer, Health, Sessions) và Trình soạn thảo Legal Docs (Web Markdown Editor kết nối DB, có nút Export/Import `.md`) | Chức năng Admin hiện diện |
| 5.12 | Cài Vitest + React Testing Library | Viết unit tests cho shared components | `npm run test` PASS |
| 5.13 | Chạy `npm run build` | — | Build production thành công ✅ |

---

### GIAI ĐOẠN 6: Playwright E2E & Hoàn thiện (Tuần 7)

**Mục tiêu:** Thiết lập E2E tests tự động và dọn dẹp cuối cùng.

| STT | Task | Chi tiết | Verification |
|---|---|---|---|
| 6.1 | Cài đặt Playwright & Reporter | `npm init playwright@latest` và cài đặt `allure-playwright` để xuất báo cáo Test HTML trực quan | Playwright UI chạy được |
| 6.2 | Thiết lập Mock API cho E2E | Cấu hình Playwright chặn và mock các third-party APIs (nếu cần) để test độc lập | Mạng bị ngắt vẫn test UI được |
| 6.3 | Viết E2E: SaaS Onboarding Flow | Đăng ký Tenant → Đăng nhập → Chấp nhận Legal Documents (Privacy Policy) | `npx playwright test onboarding.spec.ts` PASS |
| 6.4 | Viết E2E: Core AI Lifecycle | Tạo Workspace → Upload Dataset → Bấm Train → Đợi Progress Bar hoàn thành | `npx playwright test ai-lifecycle.spec.ts` PASS |
| 6.5 | Viết E2E: RBAC & Quota Edge Cases | Test User bị chặn vì hết Quota hoặc không có quyền Casbin (`viewer` không được Train) | API trả về 403, UI hiển thị lỗi đúng |
| 6.6 | Thêm `data-testid` vào UI components | Chuẩn hoá selectors cho mọi button, input, dialog | Không bị flaky test do đổi CSS |
| 6.7 | Cấu hình CI pipeline | GitHub Actions: chạy pytest (Backend) + vitest (Unit UI) + playwright (E2E UI) | CI xanh toàn bộ ✅ |
| 6.8 | Xóa file cũ không còn dùng | `app/auth.py` (đã chuyển sang core+service), các file gốc đã bóc tách | Không còn dead code |
| 6.9 | Cập nhật README.md | Hướng dẫn chạy test, cấu trúc thư mục mới | README phản ánh đúng hiện trạng |
| 6.10 | Docker Compose rebuild & smoke test | `docker compose up --build` | Tất cả services khởi động ✅ |

---

## 6. KIẾN TRÚC MULTI-TENANCY & QUẢN LÝ TÀI NGUYÊN

### 6.1. Cách Multi-tenancy & Casbin AuthZ hoạt động xuyên suốt

Hệ thống sử dụng **JWT cho Authentication (Định danh)** và **Casbin cho Authorization (Phân quyền)**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        LUỒNG REQUEST ĐA BẢO MẬT                             │
│                                                                              │
│  Request HTTP ──→ auth_guard.py (Xác thực AuthN: Token JWT có hợp lệ?)       │
│                 ──→ tenant_context.py (Resolve workspace_id từ JWT/URL)      │
│                 ──→ authorization_guard.py (Phân quyền AuthZ với Casbin)     │
│                     [Hỏi Casbin: User U có quyền Read trên Workspace W?]     │
│                     (Nếu FALSE -> Chặn ngay lập tức trả 403 Forbidden)       │
│                 ──→ Router (Nhận request đã qua 3 vòng kiểm duyệt)           │
│                 ──→ Service (Chạy business logic)                            │
│                 ──→ Repository (Filter an toàn WHERE workspace_id = ?)       │
│                                                                              │
│  Quy tắc: KHÔNG BAO GIỜ có query nào chạy mà thiếu workspace_id             │
│  (Ngoại trừ: CLASSES global, health check, auth endpoints)                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Tại sao dùng Casbin và cấu hình như thế nào?**
Thay vì viết hàng chục lệnh `if user.role == 'admin'` rải rác khắp nơi, ta áp dụng mô hình **RBAC3 + ABAC** tiên tiến nhất:

1. **RBAC3 (Hierarchy + Constraints):** User có thể có nhiều Role khác nhau ở các Workspace khác nhau (VD: User A là `Admin` ở Tenant 1, nhưng chỉ là `Viewer` ở Tenant 2). Có Super Admin bao trùm toàn hệ thống.
2. **Resource:Action Format:** Quyền (Permissions) được định nghĩa siêu mịn (Granular) theo chuẩn `resource:action`. 
   *Ví dụ: `model:create`, `model:deploy`, thay vì quyền to đùng như `Manage Model`.*
3. **ABAC (Attribute-Based Access Control):** Casbin không chỉ check Role, mà còn check thuộc tính (VD: Chỉ cho phép `model:delete` nếu `model.status != "production"` và IP người dùng thuộc dải nội bộ).
4. **Redis Caching:** Để tránh nghẽn DB, Casbin Watcher + Redis sẽ cache toàn bộ permissions (VD: `user:15_permissions: [model:view, dataset:view]`). Middleware chỉ query RAM, tốc độ < 1ms.

### 6.1.b. Thu thập IP và Audit Log (Truy vết bảo mật)
- **Trusted Proxy:** Lấy đúng IP thật của người dùng qua các header như `X-Forwarded-For` hoặc `CF-Connecting-IP` (nếu dùng Cloudflare).
- **GeoIP:** Phân tích tọa độ, quốc gia truy cập để ghi vào bảng `SYSTEM_AUDIT_LOGS` phục vụ truy vết hoặc khóa tài khoản khi có đăng nhập bất thường.

### 6.2. Quản lý Tài nguyên (Resource Quota & Allocation)

| Tài nguyên | Cấp phát | Thu hồi | Giám sát |
|---|---|---|---|
| **Storage (Ổ cứng)** | Mỗi Workspace có `storage_quota_mb` (VD: 5GB miễn phí) | `gc_reclaim_storage_quota()` tính lại mỗi đêm | `quota_service.get_usage()` trả về % đã dùng |
| **Training Slots (GPU/RAM)** | `quota_service.allocate()` cấp 1 slot khi bấm Train | `resource_tasks.py` thu hồi khi job done/fail/timeout | Celery beat kiểm tra mỗi 60s |
| **API Rate Limit** | `rate_limiter.py` giới hạn theo workspace_id | Tự động reset mỗi phút | SlowAPI + Redis |
| **Concurrent Training** | Mỗi Workspace tối đa N jobs chạy cùng lúc | Queued jobs chờ slot trống | `training_service.py` kiểm tra trước khi submit |

### 6.3. Vòng đời Quản lý Dataset & Model

```
┌───────────────────────────────────────────────────────────────┐
│                   VÒNG ĐỜI DATASET                            │
│                                                               │
│  Thu thập Samples ──→ Duyệt QA (approved) ──→ "Đóng băng"    │
│  (SAMPLES)            (SAMPLE_REVIEWS)        (DATASETS v1.0) │
│                                                    │          │
│                                               Tạo manifest    │
│                                               (CSV snapshot)  │
│                                                    │          │
│                                              Train Model      │
│                                              (MODELS v1)      │
│                                                    │          │
│                                              Deploy / Retire  │
│                                              (status change)  │
└───────────────────────────────────────────────────────────────┘
```

### 6.4. Enterprise Legal & Compliance Module (Quản lý Pháp lý)

Áp dụng chuẩn Enterprise Compliance cho tất cả các loại tài liệu pháp lý (Privacy Policy, Terms of Service, Cookie Policy...):

```
LEGAL_DOCUMENTS (Master Data)
        │
        ▼
LEGAL_DOCUMENT_VERSIONS (Transactional Data)
        │
        ├──────────────┐
        ▼              ▼
LEGAL_APPROVALS    LEGAL_ATTACHMENTS
        │
        ▼
LEGAL_COMMENTS
        │
        ▼
LEGAL_ACCEPTANCES & COOKIE_CONSENTS
```

**Triết lý thiết kế (Tách biệt theo Business Responsibility):**
1. **Master Data (`LEGAL_DOCUMENTS`)**: Định nghĩa tài liệu (Ví dụ: `privacy-policy`, `terms-of-service`). Chỉ chứa metadata, không chứa nội dung.
2. **Versioning (`LEGAL_DOCUMENT_VERSIONS`)**: Chứa nội dung thực tế (Markdown + HTML). Khi đã Publish thì trở thành "bất biến" (Immutable). Hỗ trợ Rollback dễ dàng qua việc trỏ lại version cũ.
3. **Approval Workflow (`LEGAL_APPROVALS` & `LEGAL_COMMENTS`)**: Lưu trữ toàn bộ quy trình duyệt (Draft → Legal Review → Compliance Review → Approved → Published) cùng với Comment từ các reviewer (giống GitHub Pull Request). 
4. **Quản lý File (`LEGAL_ATTACHMENTS`)**: Lưu các file đính kèm (PDF, DOCX) của luật sư (lưu Storage Key, không lưu BLOB trong DB).
5. **Đồng thuận (`LEGAL_ACCEPTANCES`)**: Ghi nhận cụ thể User nào, thuộc Tenant nào đã đồng ý với Version nào vào lúc nào (Kèm IP và User Agent).
6. **Cross-cutting (`SYSTEM_AUDIT_LOGS`)**: Ghi nhận mọi thao tác (Ai tạo, Ai duyệt, Ai publish) để tuân thủ compliance. Mọi bảng trên đều được truy vết bởi hệ thống Audit Log chung.

### 6.5. Enterprise Logging & Auditing Architecture

Hệ thống xoá bỏ khái niệm "một bảng log duy nhất", chuyển sang mô hình **7-Layer Logging** để tối ưu vòng đời, bảo mật và phân tích nghiệp vụ AI:

```
                                [ REQUEST XUẤT PHÁT (TraceID: 3bc98a...) ]
                                                 │
 ┌──────────────┬────────────────┬───────────────┼───────────────┬────────────────┬──────────────┐
 ▼              ▼                ▼               ▼               ▼                ▼              ▼
AUDIT         ACCESS            AUTH        AUTHORIZATION     SECURITY         BUSINESS        SYSTEM
(CRUD,        (HTTP req,        (Login,     (Casbin Allow/    (Attack,         (AI Lifecycle,  (Redis/DB
Deploy)       Latency, Size)    MFA)        Deny)             Rate Limit)      Billing)        Crash)
```

**Triết lý thiết kế (Traceability & Separation):**
1. **TraceID & RequestID xuyên suốt:** Mọi request từ Gateway → Middleware → Service → Worker đều mang theo `TraceID`. Khi có lỗi, chỉ cần search TraceID là ra toàn bộ luồng chạy của request đó.
2. **Audit Logs (Lõi Tuân thủ):** Lưu các sự kiện thay đổi dữ liệu (Chỉ `INSERT`, không bao giờ `UPDATE/DELETE`). Sử dụng `JSONB` của PostgreSQL để lưu `old_data` và `new_data`.
3. **Casbin Authorization Logs:** Khi Casbin ra quyết định chặn, hệ thống không chỉ trả 403 mà ghi log cụ thể: `(User: Admin, Action: model:delete, Object: model/123, Effect: DENY, Reason: Missing Permission)`. Giúp debug cực nhanh.
4. **AI Lifecycle (Business Events):** Đặc biệt cho nền tảng SaaS AI, Log nghiệp vụ sẽ theo vết sát sao vòng đời dữ liệu:
   - *MODEL_EVENTS*: `UPLOAD`, `DEPLOY`, `ROLLBACK`.
   - *INFERENCE_EVENTS*: `REQUEST_RECEIVED`, `COMPLETED`, `FAILED` (giúp trả lời câu hỏi: Model nào bị lỗi nhiều nhất hôm nay?).
   - *DATASET_EVENTS*: `IMPORT`, `ANNOTATION_COMPLETED`.
5. **Cơ chế lưu trữ:** `SYSTEM_LOGS` đẩy ra stdout (để Loki/Elasticsearch thu thập). `ACCESS_LOGS` xoay vòng (rotate) mỗi 30 ngày. `AUDIT_LOGS` lưu vĩnh viễn trong Database.

### 6.6. Hệ thống Garbage Collection (Dọn rác tự động)

| Cronjob | Tần suất | Mục tiêu | Điều kiện kích hoạt |
|---|---|---|---|
| `gc_abandoned_sessions` | Mỗi đêm 2:00 AM | `COLLECTION_SESSIONS` | `status='in_progress'` AND `created_at < now() - 24h` |
| `gc_orphaned_features` | Mỗi đêm 2:30 AM | Thư mục `features/*.npz` | File .npz không có dòng nào trong `samples.csv` tham chiếu |
| `gc_expired_tokens` | Mỗi đêm 3:00 AM | `USER_SESSIONS` + Redis | `expires_at < now()` OR `is_revoked = true` |
| `gc_soft_deleted_resources` | Mỗi tuần Chủ nhật | Tất cả bảng có `deleted_at` | `deleted_at < now() - 30 ngày` → xóa vĩnh viễn + xóa file GDrive |
| `gc_training_artifacts` | Mỗi đêm 3:30 AM | Checkpoint files, logs | Training jobs `status='failed'` OR `created_at < now() - 90 ngày` |
| `gc_log_rotation` | Mỗi đêm 4:00 AM | `SYSTEM_LOG_FILES` | `log_date < now() - retention_days` |
| `gc_reclaim_storage_quota` | Mỗi đêm 4:30 AM | Workspace quotas | Tính lại `storage_used` sau khi dọn rác |

---

## 7. NGUYÊN TẮC KIẾN TRÚC ENTERPRISE SAAS (MANIFESTO)

Đây là kim chỉ nam cho mọi dòng code của SignBridge AI Platform để đảm bảo khả năng scale từ 1 lên hàng nghìn Tenant (B2B) mà không cần đập đi xây lại:

### 7.1. Hệ thống Phân cấp (Hierarchy) và Thành viên (Membership)
- **Hierarchy:** `Platform` ➝ `Tenant` (Doanh nghiệp) ➝ `Workspace` (Phòng ban/AI Lab) ➝ `Project` (Dự án cụ thể chứa Models/Datasets).
- **Membership thay vì User Role:** User không sở hữu Role trực tiếp. Thay vào đó: `User` ➝ `Tenant/Workspace/Project Membership` ➝ `Role`. (VD: Alice là Admin ở Workspace A, nhưng chỉ là Viewer ở Workspace B).

### 7.2. Phân quyền và Bảo mật dữ liệu (AuthZ & Isolation)
- **RBAC + Casbin:** Không hardcode role. Mọi phân quyền (VD: `model:create`) đều được định nghĩa trong Casbin Policy và được ánh xạ qua các cấp Domain (`tenant-1`, `workspace-3`).
- **Visibility (RLS):** Mọi tài nguyên quan trọng đều gắn `tenant_id`, `workspace_id`, `project_id`. Mọi truy vấn DB luôn có điều kiện `WHERE tenant_id = ?`. PostgreSQL Row Level Security (RLS) được dùng làm chốt chặn cuối cùng.
- **Privacy (ABAC):** Casbin kiểm tra thuộc tính động (VD: Chỉ cho phép xoá nếu `owner_id == user_id` và `project_id == current_project`).

### 7.3. Quản lý Tài nguyên AI (Resource Management & Quota)
- Tách bạch rõ ràng **Quota (Hạn mức)** và **Usage (Thực tế sử dụng)**.
- **Allocation:** Tenant có 10 GPU ➝ Cấp xuống Workspace A 8 GPU ➝ Cấp xuống Project OCR 3 GPU. Chống hiện tượng *Noisy Neighbor* (Một project ăn hết tài nguyên toàn hệ thống).
- **Reservation:** Đặt chỗ tài nguyên (GPU/Camera) theo khung giờ để tránh kẹt lịch training.
- **Billing:** Đọc từ `USAGE_RECORDS` thay vì `AUDIT_LOGS`.

### 7.4. Cô lập hạ tầng (Storage Isolation)
- **MinIO/S3:** `tenant-a/workspace-1/project-2/models/`
- **Redis & RabbitMQ:** Dùng tiền tố/namespace (VD: `tenant.a.project2.inference`)
- Mọi thành phần từ Storage tới Queue đều bị cô lập.

### 7.5. Mười nguyên tắc vàng của Developer
1. **Không hardcode role** ➝ Mọi quyền do Casbin quản lý.
2. **Role gắn với Membership**, không gắn trực tiếp với User.
3. Mọi tài nguyên đều có `tenant_id`, `workspace_id`, `project_id` và `owner_id`.
4. **Không ghi đè dữ liệu quan trọng** ➝ Dùng Versioning (như Pháp lý) và Soft Delete.
5. **Không dùng một bảng log duy nhất** ➝ Tuân thủ 7-Layer Logging.
6. **Quota và Usage tách riêng** để tính phí và cấp phát chính xác.
7. **Namespace** mọi thành phần hạ tầng theo cấp độ dự án.
8. Kết hợp **RBAC + ABAC + PostgreSQL RLS**.
9. Mọi thao tác quan trọng đều có **Audit Log và Trace ID**.
10. Mỗi HTTP Request chỉ hoạt động trong đúng Context (Tenant/Workspace) mà nó được xác thực.

---

## 8. TỔNG KẾT TIMELINE

| Giai đoạn | Mô tả | Thời gian | Deliverable |
|---|---|---|---|
| **GĐ 1** | Hạ tầng Test + Dọn rác | Tuần 1 | Test suite chạy, repo sạch |
| **GĐ 2** | Backend Core + Middleware (bao gồm `tenant_context.py`) | Tuần 2 | `core/`, `middleware/` hoàn chỉnh |
| **GĐ 3** | Backend Repositories (bao gồm workspace, dataset, model repos) | Tuần 3 | `repositories/` cô lập Data Access |
| **GĐ 4** | Backend Services + Schemas + Router v1 (bao gồm quota, workspace, dataset, model services) | Tuần 4-5 | Kiến trúc 5 tầng + Multi-tenancy hoàn chỉnh |
| **GĐ 5** | Frontend Feature-Sliced | Tuần 6-7 | Feature modules + Unit tests |
| **GĐ 6** | Playwright E2E + CI/CD + GC Workers | Tuần 8 | E2E automation, CI pipeline, Garbage Collection |

**Tổng thời gian: ~8 tuần**

> [!CAUTION]
> **Nguyên tắc vàng:** Sau mỗi Giai đoạn, PHẢI chạy lại toàn bộ test suite. Nếu có bất kỳ test nào FAIL, DỪNG LẠI và sửa trước khi sang giai đoạn tiếp theo. Không được "nợ test".

> [!IMPORTANT]
> **Nguyên tắc Multi-tenancy:** Mọi API endpoint (trừ `/auth/*`, `/health`, và tài nguyên `CLASSES` global) đều PHẢI đi qua `tenant_context.py` middleware. Repository layer tự động filter theo `workspace_id`. Nếu dev viết query không có `workspace_id` → test phải FAIL ngay lập tức.
