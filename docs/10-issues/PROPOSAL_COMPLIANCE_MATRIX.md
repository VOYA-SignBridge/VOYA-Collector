# Proposal Compliance Matrix

Đề cương là **hợp đồng nền** của luận văn. Mọi việc kỹ thuật phải truy ngược về
một cam kết ở đây; mọi cam kết ở đây phải có bằng chứng mã + kiểm thử + luận
văn, hoặc được **hạ claim một cách minh bạch trước khi bảo vệ**.

Hai câu hỏi dùng cho mọi todo:

1. Việc này đóng cam kết nào?
2. Nếu không làm, câu nào trong đề cương trở thành overclaim?

## Trạng thái — chỉ dùng 5 giá trị

| | |
|---|---|
| `DONE` | có bằng chứng mã + kiểm thử, và luận văn nói đúng mức |
| `PARTIAL` | có phần, thiếu phần; **phải ghi rõ thiếu gì** |
| `NOT STARTED` | chưa có |
| `OUT OF SCOPE` | đề cương đã loại trừ tường minh |
| `WORDING RISK` | mã đúng, nhưng **câu chữ trong luận văn mạnh hơn bằng chứng** |

Không dùng "gần xong", "về cơ bản đạt", "chắc là có". Trước hội đồng, những từ
ấy là chỗ câu hỏi đầu tiên nhắm vào.

## Kỷ luật bằng chứng

Mỗi ô `Evidence` phải trỏ tới **tệp:dòng**, tên kiểm thử, hoặc mục luận văn —
không phải một câu khẳng định. Ô nào chưa tự xác minh trong phiên làm việc thì
ghi `CHƯA XÁC MINH`, không suy từ tên bảng hay tên hàm.

---

## P1 — Workspace–Project multi-tenant architecture

**Đề cương:** mỗi workspace là một tenant độc lập, có project riêng, member
riêng, dataset ownership riêng. Đây là Specific Objective **thứ nhất** và
Expected Outcome **số 2**.

| | |
|---|---|
| Evidence — lược đồ | `backend/app/storage/authz_schema.py:338` (`workspaces`), `:374` (`projects`) — CÓ |
| Evidence — API | **KHÔNG CÓ**. `backend/app/routers/` không có router workspace hay project nào (kiểm 16/08/2026) |
| Evidence — mặt phẳng dữ liệu | **KHÔNG CÓ**. `project_id` không xuất hiện một lần nào trong `backend/app/storage/metadata_db.py`, nên `samples`/`classes` không mang project |
| Evidence — kiểm thử | CHƯA XÁC MINH |
| **Status** | **`PARTIAL`** |
| **Gap** | Bảng có, nhưng không có đường nghiệp vụ tạo/quản lý workspace–project, và `project_id` không đi xuyên tới dữ liệu. "Dataset ownership riêng theo project" hiện **chưa cưỡng chế được**. |
| **Decision** | Ưu tiên **cao nhất sau khi đóng P0**. Hai lựa chọn, phải chọn sớm: (a) triển khai tối thiểu đường nghiệp vụ + gắn `project_id` vào `samples`/`classes`; (b) hạ claim xuống "workspace = tenant; project là đơn vị tổ chức ở tầng phân quyền, chưa phân vùng dữ liệu". |

**Vì sao đây là RED:** hội đồng đọc Objective 1 rồi hỏi "cho xem tạo một
project" là câu hỏi tự nhiên nhất có thể có.

---

## P2 — Logical tenant isolation

**Đề cương:** dữ liệu của một tenant không truy cập được bởi tenant khác.

| | |
|---|---|
| Evidence — RLS | 33 bảng dưới RLS + FORCE; `voya_control` cho `tenant_purges` (mặt phẳng điều khiển) |
| Evidence — mặt phẳng tệp | P0-A/P0-B: `docs/00-thesis/MEASUREMENT_tenant_isolation.md` §13 |
| Evidence — kiểm thử | T4/T0/T1/T2/T2b qua HTTP trên môi trường đóng băng (§13.2–13.3); T3 tiêm lỗi 7/7; nhóm ghi 43/43; **A2 READ-1..7 ĐẠT** trên `repro-20260816-010330-c648c5` + `test_read_scope_fail_closed.py` 14/14 |
| Evidence — bất biến nguồn seed | Không có `fallback(seed_source)` ở đường ĐỌC: không UNION ngầm với `default`/`community`, `rls.py` không có ngoại lệ cho `default`. Còn 5 chỗ `or DEFAULT_TENANT_ID` — phân loại ở bảng dưới |
| Evidence — luận văn | CTIVR/UASR/SVSR §7 (lượt đo lịch sử, giữ nguyên) |
| **Status** | **`PARTIAL`** |
| **Gap** | A1 ghi + A2 đọc đã đóng. Còn: B admin, C export/training, D internal, E maintenance, F architecture guard, G audit raw/manifest/worker. |
| **Decision** | **KHÔNG được đóng cam kết này** trước khi caller migration và audit các mặt phẳng còn lại xong. Đây là cam kết mà cả P0 đang phục vụ. |

### A2 — request READ: **CLOSED** (16/08/2026)

| | Nội dung | Kết quả |
|---|---|---|
| READ-1 | rò hàng, 6 điểm đọc | ĐẠT — 0 định danh của B |
| READ-2 | phép thử tồn tại | ĐẠT — 404 giống nhau **từng byte** |
| READ-3 | rò tổng hợp: thêm 1 lớp + 3 mẫu + 1 người vào B | ĐẠT — 6/6 bất biến |
| READ-4 | quan hệ phụ: hàng của **B mang `class_uid` của A** | ĐẠT — 0/4 quan hệ rò |
| READ-5 | không rơi về `default` | ĐẠT — HTTP 6/6 + helper 14/14 |
| READ-6 | nguồn liệt kê TTS | ĐẠT — nhãn của A bất biến (4→4) khi B có nhãn mới |
| READ-7 | phân loại phạm vi tường minh | ĐẠT ở mức "một tenant tường minh" — xem cảnh báo dưới |

**READ-4 đánh đúng mặt phẳng nguy hiểm.** `classes.class_uid` là PRIMARY KEY
toàn cục ở PostgreSQL, nên trạng thái "hai tenant cùng một `class_uid`" không
dựng được ở đó. Nhưng `samples.csv` **không có ràng buộc ấy**, và đường đọc lấy
dữ liệu từ CSV — đúng mặt phẳng nơi lỗ P0 từng sống. Phép đo tiêm một hàng thuộc
`iso_b` mang `class_uid` của `iso_a` rồi đọc bằng tài khoản A; không định danh
nào lọt qua bốn quan hệ (sessions/list/stats/collectors). Cây được trả về nguyên
trạng sau đo.

**READ-6 đo NGUỒN LIỆT KÊ, không đo bộ đệm.** Khoá đệm TTS là `(voice, text)` —
nội dung thuần — nên đệm chia sẻ được một cách hợp lệ, và "khoá đệm tồn tại"
không phải bằng chứng rò (nó có thể đã nóng từ lượt gọi của B). Thứ đo được là
số nhãn mà prewarm của A xếp lịch: bất biến khi B có thêm nhãn mới.

> **Cảnh báo phân loại — READ-7.** `/classes/community-stats` **không** đọc mặt
> phẳng Community. Nó đọc `settings.public_tenant_id` = `"default"`, và `default`
> là tenant BOOTSTRAP/SEED (`tenant_type='ORGANIZATION'`), không phải commons
> (`tenant_id='community'`, `tenant_type='COMMUNITY'`). Vì vậy điểm này **chỉ
> chứng minh "phạm vi một tenant tường minh"**, KHÔNG chứng minh chính sách
> Community. Đừng dùng nó làm bằng chứng cho "Community exception".
>
> ```
> Kết quả an ninh:  aggregate(mọi tenant) -> aggregate(một tenant tường minh)   ĐÃ ĐÓNG
> Kết quả ngữ nghĩa: nguồn = default ≠ Community thật                            CHƯA GIẢI QUYẾT
> ```
>
> Community có kiến trúc và reserved tenant, nhưng **workflow runtime chưa được
> hiện thực đầu-cuối** — không nên viết "0 dòng mã", vì điều đó ngụ ý không có
> nền tảng kỹ thuật nào.

### `DEFAULT_TENANT_ID` — ba mặt phẳng, đừng đánh đồng

Bất biến: `bootstrap inheritance ≠ runtime fallback`.

| Chỗ | Mặt phẳng | Phán quyết | Xử ở |
|---|---|---|---|
| `dataset_manager.py:194` `ambient_tenant()` | BOOTSTRAP/CREATE | có thể hợp lệ — **chỉ khi** thật sự là đường tạo dữ liệu mới | — |
| `metadata_db.py:4564` payload | BOOTSTRAP/CREATE | như trên | — |
| `auth.py:100` `users.tenant_id` | **IDENTITY** | **không hợp lệ** — `tenant_id` NULL không được âm thầm thành `default` | **B** |
| `training_tasks.py:533` webhook emit | **PIPELINE** | **không hợp lệ** — phát sự kiện sai phạm vi | **C** |
| `training_tasks.py:582` `replace_training_job_classes` | **PIPELINE** | **không hợp lệ, nặng nhất** — *mutate* state của tenant seed | **C** |

Bất biến phải viết vào nhóm C:

```
TrainingJob.tenant_id = ∅  ->  FAIL          (không phải -> default)
Train(T) -> outputs ⊆ T                       gồm class contract, model artifact,
                                              webhook/event, registry, dataset ref
```

---

## P3 — IAM / RBAC ba tầng (system / workspace / project)

| | |
|---|---|
| Evidence — lược đồ | `authz` 2 bảng gộp, 13 role, Casbin adapter |
| Evidence — phân biệt nền tảng/tenant | **ĐÃ XÁC MINH** — xem nhóm B dưới |
| Evidence — phạm vi `workspace` đầu-cuối | CHƯA XÁC MINH |
| Evidence — phạm vi `project` đầu-cuối | **KHÔNG CÓ** — xem RED-1 |
| **Status** | **`PARTIAL`** |

> **Đừng đọc nhầm nhóm B thành "P3 xong".** Nhóm B chứng minh **một** ranh giới:
> `platform_administrator` ≠ `tenant_administrator`. Đề cương hứa RBAC theo **ba**
> phạm vi. `users.is_admin` vẫn là một cờ boolean đặc biệt ở tầng nền tảng chứ
> không phải một vai có phạm vi trong mô hình đầy đủ, và phạm vi `project` chưa
> có đường nghiệp vụ nào chạm tới.
>
> ```
> System/tenant administrator distinction    VERIFIED
> Three-scope RBAC (system/workspace/project) PARTIAL
> ```

### B — admin & identity: **CLOSED** (16/08/2026)

Bốn bất biến, đo trên môi trường đóng băng (`repro-20260816-010330-c648c5`,
fingerprint khớp trước khi đo):

| # | Bất biến | Bằng chứng |
|---|---|---|
| 1 | thiếu tenant **không** thành `default` | B-ID-1..5, 8/8 |
| 2 | quyền cao trong tenant **không** mở rộng ranh giới tenant | B6, 5/5 ca âm |
| 3 | quản trị nền tảng là principal riêng, không suy từ tư cách thành viên | `test_tenant_admin_is_not_platform_admin.py` 5/5 |
| 4 | endpoint phân loại TENANT_ADMIN phải cấp bằng **quyền có phạm vi tenant** | B+-1 |

```
B6-1 tadmin(A) -> lớp của B (sessions)      404   không phân biệt với không tồn tại
B6-1 tadmin(A) -> mẫu của B (/data)         404   (trước bản vá: 500)
B6-2 tadmin(A) -> hồ sơ tenant default      403   `default` KHÔNG phải "ai cũng vào được"
B6-3 tadmin(A) -> liệt kê MỌI tenant        403
B6-3 tadmin(A) -> hồ sơ tenant B            403
B+-1 tadmin(A) -> /admin/data-report của A  200   0 định danh của B
B+-2 padmin    -> liệt kê MỌI tenant        200   đúng thiết kế
B+-3 padmin    -> /admin/data-report        200
```

**Ba mutation trong nhóm B**

1. `users.tenant_id` bỏ `DEFAULT 'default'`, **giữ** NOT NULL — một `INSERT`
   quên tenant nay NỔ thay vì lặng lẽ sinh ra một tư cách thành viên. Không hàng
   nào bị di chuyển (11 tài khoản vẫn thuộc `default`).
2. `/admin/data-report` đổi cổng `require_admin` → `require_tenant_editor`, để
   **chủ thể / quyền / phạm vi / ngữ nghĩa endpoint** cùng nói một điều.
3. `dataset.py:265/296/466` `list_samples_v2()` → có phạm vi. *Phát hiện trong
   lúc chạy B6*, thuộc nhóm A2 về bản chất — `Purpose: DISPLAY / RESOURCE
   RESOLUTION`, `Authority: tenant-scoped`, `Discovery: found during B6`.

**Hai lỗi của BỘ ĐO, không phải của hệ thống** — ghi lại để giữ nguyên xuất xứ:

* Lượt B6 đầu dùng `iso_admin_a` (`is_admin=TRUE` = **quản trị nền tảng**) rồi
  kỳ vọng bị chặn ở ranh giới tenant. Nó xoá mềm `iso_b` thật và phải khôi phục
  tay. Bài học đáng giữ: *một ca kiểm phân quyền **âm** chỉ có nghĩa khi chủ thể
  **chưa sẵn có** quyền thực hiện hành động đang thử.* Đã thêm `iso_tadmin_a`
  (`is_admin=FALSE`, `tenant_members.role='admin'`) và bỏ ca `DELETE` khỏi nhóm
  âm — một ca âm không bị chặn thì nó vừa phá fixture.
* `verify_effective_code.sh` thiếu `docker exec -i` nên heredoc bị nuốt: script
  in header, exit 0, và **không xác minh gì**.
| **Gap** | Có bảng ≠ có cưỡng chế. Ba bất biến cần chứng minh bằng hành vi: (1) tenant admin **không** trở thành system admin; (2) project role **không** vượt phạm vi workspace; (3) assignment được cưỡng chế trên route thật, không chỉ trong bảng. |
| **Decision** | Đối chiếu ở nhóm **B (2 admin caller)** — chính nhóm ấy phải phân biệt *tenant admin* với *system operator*, nên nó vừa phục vụ P2 vừa phục vụ P3. |

---

## P4 — Vocabulary chuẩn + dialect + tenant extension

| | |
|---|---|
| Evidence | `region` đã thành một phần định danh lớp (commit `f882414`); registry/version; shared catalogue |
| Evidence — 3 vế | CHƯA XÁC MINH đủ |
| **Status** | **`PARTIAL`** |
| **Gap** | Phải chứng minh **cả ba** vế, không chỉ "có bảng vocabulary": (a) canonical/shared tồn tại; (b) tenant mở rộng được; (c) **canonical KHÔNG bị tenant làm biến đổi**. Vế (c) là vế dễ thiếu nhất và cũng là vế đề cương hứa mạnh nhất. |
| **Decision** | Checklist riêng, sau P2. |

---

## P5 — Browser-based landmark extraction + tiết kiệm lưu trữ

**Đề cương:** MediaPipe Holistic trong trình duyệt, lưu `.npz`, *"reduces
per-sample storage by over 90% vs. raw video"*.

| | |
|---|---|
| Evidence — chức năng | CHƯA XÁC MINH trong phiên này |
| Evidence — chỉ số | 88,4% / 93,0% / 96,5% — và là **ước lượng theo bitrate**, không phải đo trực tiếp raw video |
| **Status** | **`WORDING RISK`** |
| **Gap** | Đề cương ghi "over 90%" **vô điều kiện**. Số thấp nhất đo được là **88,4%**, tức câu ấy sai ở ít nhất một cấu hình. Thêm nữa, cách đo là ước lượng bitrate — bản thân nó là một hạn chế phải nói ra. |
| **Decision** | **Không được giữ nguyên "trên 90%" vô điều kiện.** Chọn một: (a) hạ claim xuống "85–96% tuỳ bitrate nguồn"; (b) giữ ">90%" nhưng nêu rõ điều kiện bitrate và ghi 88,4% là biên dưới quan sát được. Kèm ghi chú phương pháp đo. |

---

## P6 — Asynchronous data-processing pipeline (Celery + Redis)

**Đề cương:** ingestion, segmentation, augmentation, cloud synchronization.

| | |
|---|---|
| Evidence — có worker | `export_tasks.py`, `preview_tasks.py`, `saas_tasks.py`, `sync_tasks.py`, `tasks.py`, `training_tasks.py` |
| Evidence — 4 capability | CHƯA XÁC MINH từng cái. `tasks.py` có `enqueue_process_video` |
| Evidence — tenant propagation | **Một phần**: `render_session_preview_task` đã mang `tenant_id` (P0-3, 16/08/2026); các task khác CHƯA XÁC MINH |
| **Status** | **`PARTIAL`** |
| **Gap** | "Có Celery" không phải điều đề cương hứa. Phải chỉ ra **từng** capability trong bốn cái, và chứng minh `tenant_id` đi theo message — worker chạy trong `system_scope`, nên một task không mang phạm vi sẽ đọc rộng hơn phạm vi của người đã yêu cầu nó. |
| **Decision** | Đóng cùng nhóm **C** và **D**; audit ở **G**. |

---

## P7 — Signed, versioned synchronization (SOT)

**Đề cương:** *"guarantees authoritative, tamper-evident dataset state across
deployments, extended per workspace."*

| | |
|---|---|
| Evidence | SOT có ký/publish, `sot-init` chặn stack khi sai (exit 4), `sot_authorized_keys` |
| Evidence — workspace scoping | **KHÔNG CÓ**. `backend/app/sot/` không nhắc `workspace` một lần nào (kiểm 16/08/2026) |
| **Status** | **`PARTIAL`** — và từ *"guarantees"* làm nó thành **`WORDING RISK`** |
| **Gap** | Vế "per workspace" chưa có. Ngoài ra cần chứng minh **từ chối trạng thái đã bị sửa**, không chỉ có hàm băm/chữ ký — hash + manifest + signature helper chưa đủ để dùng từ "guarantees". |
| **Decision** | Hoặc triển khai workspace scoping cho SOT, hoặc sửa câu trong luận văn bỏ "extended per workspace". Quyết sớm — đây là RED-3. |

---

## P8 — Evaluation (4 trục)

| Trục | Evidence | Status |
|---|---|---|
| Tenant isolation | CTIVR/UASR/SVSR §7; T-cases §13 | `PARTIAL` (chờ P2 đóng) |
| Storage efficiency | 88,4 / 93,0 / 96,5% | `WORDING RISK` (xem P5) |
| Performance | p50/p95/p99 API latency | `PARTIAL` — cần bảng tổng hợp |
| Functional correctness | full suite (lần cuối 2330 pass / 2 fail, **chưa chạy lại**) + focused suites | `PARTIAL` |

**Gap:** thiếu **một bảng tổng hợp cuối** chứng minh đủ cả bốn trục trong cùng
một chỗ. **Decision:** dựng sau khi caller migration xong, để số không phải đo lại.

---

## P9 — Real-time recognition (downstream-utility demonstration)

Đề cương xếp mục này trong phần **Included**, dù không phải mục tiêu cốt lõi.

| | |
|---|---|
| Evidence | CHƯA XÁC MINH |
| **Status** | **`PARTIAL`** — chưa xác minh |
| **Gap** | Nằm trong "Included" thì cần tối thiểu một bằng chứng chạy được: route/UI demo, hoặc luồng demo có ảnh chụp. |
| **Decision** | Quyết **sớm**: làm mức tối thiểu, hay sửa phạm vi luận văn để không overclaim. Đừng để tới tuần cuối. |

---

## Đề cương đã LOẠI TRỪ — không được để chiếm thời gian

Ghi ra để chống scope creep. Có thể làm nếu cần sản phẩm, nhưng **không phải cam
kết** và không được ưu tiên trước bảo vệ:

* huấn luyện / tối ưu / đánh giá mô hình sâu
* thuật toán thị giác máy tính mới
* dịch thuật quy mô sản xuất
* Kubernetes / HA
* pipeline toàn thân + khuôn mặt
* quản trị tài nguyên tenant tự động hoàn chỉnh
* tự động hoá vòng đời tenant đầy đủ
* quản lý pháp lý / đồng thuận đầy đủ

`OUT OF SCOPE` — cả tám.

Lưu ý: billing/quota, legal workflow và lifecycle automation **đã được làm khá
nhiều** trong kho này. Đó không phải lý do để làm tiếp; đó là lý do để **dừng**
và ghi chúng là phần vượt phạm vi đã có sẵn.

---

## Ánh xạ backlog hiện tại → cam kết

| Nhóm việc | Cam kết | Trạng thái |
|---|---|---|
| P0-A / P0-B | P2 | ĐÃ KHOÁ bằng phép đo |
| A1 request WRITE (10 caller) | P2 | DONE — 43/43 |
| A2 request READ | P2 | DONE — READ-1..7 |
| B admin (2) | P2 + **P3** | DONE — 4 bất biến |
| C1 sự kiện + hợp đồng lớp | P2 + P6 | DONE |
| C2a `training_jobs.tenant_id` tường minh | P2 | DONE — 9/9 |
| C2b chủ sở hữu operational split | P2 | DONE — 21/21, xem dưới |
| C2c cưỡng chế resolver + ma trận C2-1..C2-7 | P2 | DONE — 18/18, xem dưới |
| C export/training (7 caller còn lại) | P2 + **P6** + P8 | chưa |
| D internal (9) | P2 + **P6** | chưa |
| E maintenance ledger (21) | P2 | chưa |
| F architecture guard | P2 | chưa |
| G ma trận + audit raw/manifest/worker | P2 + P6 + **P7** | chưa |
| P1 multi-plane atomicity | hỗ trợ P2/P7, **không phải claim riêng** | issue mở |
| full suite | P8 | chưa chạy lại |

### C2b — chủ sở hữu hiện vật chia dữ liệu (16/08/2026)

**Proposal trace:** P2 (logical tenant isolation). Củng cố, KHÔNG nâng P6.

**Cam kết đóng được:** dữ liệu huấn luyện của một tổ chức có một chủ sở hữu
tường minh, ghi tại thời điểm tạo. Trước bước này, `split_metadata.json` không
có khái niệm tổ chức nào cả — nên câu "hai mặt phẳng cách ly" trong luận văn
đúng với hàng CSDL và hàng CSV, nhưng **không** đúng với hiện vật chia dữ liệu,
mặt phẳng thứ ba mà mọi lượt huấn luyện đều đọc.

**Nếu không làm:** mọi câu về cách ly ở tầng huấn luyện là overclaim — không có
gì để cưỡng chế, nên C2c sẽ chỉ là một phép kiểm luôn trả lời "không biết".

| | Nội dung | Chứng cứ |
|---|---|---|
| C2b-1 | Tạo split cho A → `tenant_id == A` | `test_split_owner_metadata.py::TestC2b_1_2` |
| C2b-2 | Tạo split cho B → `tenant_id == B`; ràng buộc khác nhau | cùng trên |
| C2b-3 | Thiếu chủ → DỪNG, **không để lại hiện vật nửa chừng** | `TestC2b_3` (5 ca) |
| C2b-4 | `purpose=research` không bị luật vận hành chạm | `TestC2b_4`; ba tệp đóng băng khớp mã băm |
| C2b-5 | Chủ BẤT BIẾN; sửa/thêm/chép bằng tay đều bị từ chối | `TestC2b_5` (6 ca) |

**Đột biến đã chạy:** (1) tắt cổng thiếu-chủ ở CLI → 4 ca đỏ, trong đó ca
"không để lại hiện vật nửa chừng" chứng minh vị trí cổng là nội dung chứ không
phải hình thức; (2) bỏ `tenant_id` khỏi ràng buộc → 2 ca đỏ. Xanh mà không đột
biến thì chưa phải chứng cứ.

**Ba trạng thái, không phải `Optional[str]`:** `owned` / `unknown` (vận hành mất
chủ) / `not_applicable` (nghiên cứu đóng băng). Gộp hai cái sau vào một `None`
thì hoặc chặn oan mọi lượt nghiên cứu, hoặc cho qua mọi hiện vật mất chủ.

**Giới hạn nói thẳng:** `owner_binding` là bằng chứng-chống-sửa, **không** phải
ranh giới thẩm quyền. Ai có quyền ghi vào cây hiện vật và đọc được hàm băm thì
tính lại được. Ranh giới thật vẫn là quyền ghi trên hệ tệp. Cái nó chặn là
những gì thực sự hay xảy ra: sửa tay, chép nửa vời, backfill "cho tiện".

### C2c — cưỡng chế quyền sở hữu ở resolver (16/08/2026)

**Proposal trace:** P2 (logical tenant isolation). Vẫn KHÔNG nâng P6.

**Cam kết đóng được:** mặt phẳng thứ ba — hiện vật chia dữ liệu — nay cách ly
thật, không chỉ khai báo. Trước bước này, biết `split_id` là đọc được, bất kể
tổ chức nào.

| | Nội dung | Kết quả |
|---|---|---|
| C2-1 | job A + split của A | CHO QUA |
| C2-2 | job A + split của B | TỪ CHỐI, không lộ tên tổ chức chủ |
| C2-3 | split của B ≡ split không tồn tại | hai câu trả lời GIỐNG HỆT nhau |
| C2-4 | chủ `unknown` | TỪ CHỐI với mọi tenant, kể cả `default`/`community` |
| C2-5 | không biết tenant người hỏi | TỪ CHỐI trước cả khi tìm hiện vật |
| C2-6 | vận hành bị chặn | KHÔNG rơi về mốc nghiên cứu đóng băng |
| C2-7 | nghiên cứu | hợp đồng riêng, không chịu luật chủ sở hữu |
| C2-X | sửa tay chủ, không sửa ràng buộc | TỪ CHỐI ở tầng resolver |

**Ba câu trả lời gộp làm một.** "Không tồn tại", "của tổ chức khác" và "không rõ
chủ" nói y hệt nhau với người gọi; lý do thật đi vào nhật ký ở mức ERROR. Ba câu
trả lời khác nhau biến `split_id` thành máy đoán — đúng lớp rò rỉ *existence
oracle* đã kiểm ở A2, chỉ khác mặt phẳng lưu trữ.

**`tenant_id` không có giá trị mặc định**, kể cả `None`. Quên truyền là
`TypeError` ngay lúc gọi. Một mặc định biến "quên truyền" thành "được miễn kiểm"
— đúng hình dạng của `normalize_tenant_id("")` trả `"default"`: hàng rào còn
nguyên, chỉ là không ai đi qua nó nữa.

**Đột biến đã chạy:** (1) tắt phép so chủ ↔ người hỏi → 5 ca đỏ; (2) tắt cổng
`unknown` → chỉ **1** ca đỏ, và đó là phát hiện đáng ghi: nhánh `unknown` chặn
TRÙNG với phép so bên dưới (`tenant_id` là `None` thì luôn lệch). Nó ở lại vì
lý do **chẩn đoán**, không phải chặn — bỏ đi thì nhật ký báo "hiện vật thuộc
tenant None" và người trực sẽ đi tìm một lỗi lưu trữ, trong khi vấn đề thật là
nguồn gốc không đủ. Đã ghi rõ điều này ngay tại chỗ để không ai dọn nó đi vì
tưởng là mã chết.

**Hai hiện vật lịch sử:** giữ, không gán chủ, không dùng được lúc chạy. Chi tiết
và điều kiện backfill-có-chứng-cứ ở `KNOWN_ISSUES.md`.

**Không nằm trong backlog an ninh — và đây là lý do chạy hết P0 chưa phải là
xong đề tài:** P1 Workspace–Project, P3 RBAC ba tầng đầu-cuối, P4 vocabulary ba
vế, P5 landmark + câu chữ lưu trữ, P6 bốn capability, P7 SOT per workspace, P9
demo nhận dạng.

---

## Ba mục đỏ nhất

| | Mục | Vì sao |
|---|---|---|
| **RED-1** | P1 Workspace–Project | Objective **thứ nhất**; bảng có, API không, `project_id` không tới dữ liệu |
| **RED-2** | P5 lưu trữ ">90%" | Đề cương ghi vô điều kiện; số thấp nhất đo được **88,4%** |
| **RED-3** | P7 SOT "guarantees … per workspace" | Từ "guarantees" rất mạnh; `sot/` không có khái niệm workspace |

Theo dõi nhưng chưa đỏ: **P3 RBAC** — nếu lược đồ + Casbin đã đủ thì đóng nhanh,
nhưng phải chứng minh bằng hành vi trên route thật, không bằng sự tồn tại của
bảng.

---

## Thứ tự sau P0

```
1. hoàn tất P0 caller audit          P2
2. Workspace–Project gap             P1   <- RED-1
3. RBAC 3-scope đầu-cuối             P3
4. Signed SOT per workspace          P7   <- RED-3
5. xác minh async pipeline           P6
6. vocabulary/QIPEDC/tenant ext      P4
7. landmark + câu chữ lưu trữ        P5   <- RED-2
8. demo nhận dạng thời gian thực     P9
9. bảng đánh giá tổng hợp            P8
10. rà toàn bộ claim luận văn ↔ đề cương
```

*Cập nhật 16/08/2026. Các ô `CHƯA XÁC MINH` là công nợ có chủ ý: chúng đánh dấu
chỗ chưa ai kiểm, chứ không phải chỗ đã đạt.*
