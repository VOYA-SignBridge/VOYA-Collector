# Từ điển dữ liệu — Nhóm M5: Huấn luyện & Mô hình

*3 bảng · 33 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Nhóm nhỏ nhất lược đồ, nhưng mang quan hệ quan trọng nhất về khả năng tái lập:**
khoá ngoại ghép **ghim phiên bản danh mục** vào từng lượt chạy.

**Một chỗ để trống có chủ ý:** lược đồ **không có bảng "mô hình" riêng**. Mô hình
được quản lý như **hiện vật của tác vụ huấn luyện** (`checkpoint_path`); tách
thành thực thể riêng là việc của bước phát triển tiếp theo.

---

## 5.1 Bảng `training_jobs` — Tác vụ huấn luyện

**Khoá chính:** `job_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 19 · **Số hàng
(10/08/2026):** 90

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| job_id | text | — | Primary key | Định danh lượt chạy huấn luyện |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu lượt chạy |
| status | text | — | Not null | Trạng thái: đang chờ / đang chạy / hoàn tất / thất bại |
| model_type | text | — | Null | **Kiến trúc mạng neural** đã chọn |
| config | jsonb | — | Null | **Toàn bộ siêu tham số của lượt chạy**, lưu nguyên khối |
| auth_user_id | uuid | — | Null, Foreign key → users.id | Người chạy — cũng là người nhận thông báo khi tác vụ hỏng |
| registry_version | bigint | 64 | Null, **Foreign key kép** → registry_versions(tenant_id, version) | **PHIÊN BẢN DANH MỤC ĐÃ GHIM** — điều kiện để tái lập thí nghiệm |
| created_at | timestamptz | — | Null | Thời điểm xếp hàng |
| started_at | timestamptz | — | Null | Thời điểm bắt đầu chạy thật |
| completed_at | timestamptz | — | Null | Thời điểm kết thúc |
| current_epoch | integer | 32 | Not null, Default 0 | Chu kỳ đang chạy |
| total_epochs | integer | 32 | Not null, Default 0 | Tổng số chu kỳ theo cấu hình |
| checkpoint_path | text | — | Null | **Đường dẫn hiện vật mô hình** trên đĩa |
| test_acc | real | 24 | Null | Độ chính xác trên tập đánh giá |
| test_f1 | real | 24 | Null | Điểm F1 trên tập đánh giá |
| evaluation | jsonb | — | Null | **Kết quả đánh giá chi tiết**, gồm hiệu suất theo từng lớp |
| error_message | text | — | Null | Lý do thất bại, **đọc được cho người dùng** |
| promoted_at | timestamptz | — | Null | **Thời điểm THĂNG HẠNG** — mô hình bắt đầu phục vụ thật |
| superseded_at | timestamptz | — | Null | Thời điểm bị một mô hình khác thay thế |

**Ràng buộc duy nhất kép:** `UNIQUE (tenant_id, job_id)` — mặt đỡ cho khoá ngoại
ghép từ `training_metrics`.

### Ba cột đáng bảo vệ riêng

**`registry_version` — quan hệ GHIM, không phải tham chiếu thông thường.** Nó trỏ
tới một **ảnh chụp bất biến**, không trỏ tới trạng thái danh mục hiện tại. Chạy
lại tác vụ sáu tháng sau vẫn dùng **đúng tập nhãn của lần đầu**, kể cả khi danh mục
đã thay đổi. Khoá ngoại là **ghép** `(tenant_id, registry_version)`, nên một tác vụ
của tổ chức A không ghim được vào phiên bản danh mục của tổ chức B.

**`promoted_at` và `superseded_at` — hai cột phân biệt *"đã huấn luyện xong"* với
*"đang phục vụ"*.** Đây là hai trạng thái **hoàn toàn khác nhau**, và lẫn chúng là
lỗi khái niệm chứ không phải lỗi hiển thị:

| Trạng thái | Điều kiện |
|---|---|
| Đã huấn luyện xong | `completed_at` có giá trị |
| **Đang phục vụ** | `promoted_at` có giá trị **và** `superseded_at` rỗng |
| Đã từng phục vụ | `promoted_at` và `superseded_at` **đều** có giá trị |

**Phiên bản mới nhất ≠ phiên bản đang phục vụ.** Một mô hình vừa huấn luyện xong
**chưa phục vụ ai** cho tới khi được thăng hạng — một hành động **tường minh** của
quản trị nền tảng, **có bản ghi**, và **đảo ngược được**. Biểu tượng *"Đã đưa vào
Realtime"* trên màn hình lịch sử huấn luyện đọc chính hai cột này.

**`config` và `evaluation` kiểu `jsonb` — phi chuẩn hoá có chủ đích.** Siêu tham
số và kết quả đánh giá thay đổi hình dạng theo từng kiến trúc mô hình; chuẩn hoá
chúng ra thành cột cố định sẽ buộc phải đổi lược đồ mỗi lần thêm một kiến trúc mới.
Đánh đổi được chấp nhận: **mất khả năng truy vấn theo từng tham số**, đổi lấy việc
**không phải di trú lược đồ** khi mô hình thay đổi.

---

## 5.2 Bảng `training_job_classes` — Tập lớp thực sự tham gia

**Khoá chính:** `(job_id, class_idx)` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 5 ·
**Số hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| job_id | text | — | Primary key (kép), Foreign key → training_jobs.job_id | Lượt chạy |
| class_idx | integer | 32 | Primary key (kép) | **Chỉ số lớp đã gán trong lượt chạy này** — vị trí trong không gian nhãn của mô hình |
| class_uid | text | — | Null, Foreign key → classes.class_uid | Lớp tương ứng trong danh mục |
| label | text | — | Not null | **Nhãn tại thời điểm chạy**, chép cứng — không đọc lại từ danh mục |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |

> **Bảng này lưu tập lớp THỰC SỰ THAM GIA sau khi qua ba cổng chặn, không phải tập
> lớp người dùng chọn.** Phân biệt này cần cho việc giải thích kết quả: nếu chỉ lưu
> tập được chọn, một lần chạy loại bớt lớp sẽ **không để lại dấu vết**, và người
> dùng sẽ tưởng mô hình được huấn luyện trên tập lớp mình chọn.

**`label` được chép cứng thay vì đọc lại từ `classes`.** Lý do: nhãn trong danh mục
có thể đổi sau lượt chạy; đọc lại sẽ khiến kết quả cũ hiển thị nhãn mới, tức **viết
lại quá khứ**. Cột `class_uid` giữ đường tra ngược tới lớp hiện tại nếu cần.

**`class_idx` là chỉ số trong không gian nhãn, và thứ tự của nó có hậu quả thật.**
Sàn số mẫu mỗi lớp **phải áp TRƯỚC khi đánh chỉ số**. Nếu đánh chỉ số trước rồi
mới loại lớp, chỉ số sẽ **nhảy cóc**, và mô hình huấn luyện trên một không gian
nhãn **khác** với không gian nhãn lúc suy luận — một lỗi **không sinh ra thông báo
nào**, chỉ sinh ra kết quả sai.

---

## 5.3 Bảng `training_metrics` — Chỉ số theo chu kỳ

**Khoá chính:** `(job_id, epoch)` · **RLS:** — không bật · **Số cột:** 9 · **Số
hàng (10/08/2026):** 393

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| job_id | text | — | Primary key (kép), **Foreign key kép** → training_jobs(tenant_id, job_id) | Lượt chạy |
| epoch | integer | 32 | Primary key (kép) | **Số thứ tự chu kỳ huấn luyện** |
| train_loss | real | 24 | Null | Mất mát trên tập huấn luyện |
| train_acc | real | 24 | Null | Độ chính xác trên tập huấn luyện |
| val_loss | real | 24 | Null | Mất mát trên tập kiểm định |
| val_acc | real | 24 | Null | Độ chính xác trên tập kiểm định |
| val_f1 | real | 24 | Null | Điểm F1 trên tập kiểm định |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm ghi chỉ số |

**Năm cột chỉ số đứng cạnh nhau là một quyết định về tính trung thực.** Độ chính
xác trên tập **huấn luyện** cao mà trên tập **kiểm định** thấp là dấu hiệu học vẹt;
lưu **cả hai** làm dấu hiệu đó nhìn thấy được, thay vì phải suy ra sau. Giao diện
theo dõi hiển thị đúng bốn trong năm cột này theo thời gian thực.

**Ghi chú trung thực — bảng này KHÔNG bật RLS.** Nó mang cột `tenant_id` và có
khoá ngoại ghép tới `training_jobs(tenant_id, job_id)`, nhưng **không có chính
sách bảo mật mức hàng**. Ảnh chụp 10/08/2026 ở Phụ lục A cũng ghi nhận điều này.
Đánh giá rủi ro: bảng chỉ chứa **số liệu chỉ số**, không chứa dữ liệu người dùng
hay nội dung mẫu; nhưng nó **liệt kê được sự tồn tại và tiến độ của các lượt chạy
thuộc tổ chức khác**, và việc lọc phải do tầng ứng dụng làm — tức **mức bảo đảm
thấp hơn** hai bảng còn lại trong nhóm.

---

## Tổng kết nhóm M5

```
registry_versions (1) ──< training_jobs        [GHIM PHIÊN BẢN — khoá ngoại ghép]
training_jobs (1) ──< training_job_classes     [tập lớp SAU ba cổng chặn]
training_jobs (1) ──< training_metrics         [khoá ngoại ghép (tenant_id, job_id)]
users (1) ──< training_jobs                    [người chạy, nhận thông báo khi hỏng]
classes (1) ──< training_job_classes           [đường tra ngược tới lớp hiện tại]
```

### Ba cổng chặn ghi dấu vào lược đồ ở đâu

| Cổng | Hỏi gì | Dấu vết trong lược đồ |
|---|---|---|
| Đồng thuận | Người ký cho phép dùng ở mức phát hành này không? | Mẫu không đủ mức **không xuất hiện** trong tập → không có hàng tương ứng |
| Sàn số mẫu mỗi lớp | Lớp này đủ mẫu để chia tập không? | Lớp bị loại **không có hàng** trong `training_job_classes` |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Tác vụ **không được tạo** — không có hàng trong `training_jobs` |

**Ba cổng hỏi ba câu khác nhau và không thay thế được cho nhau.** Chúng để lại dấu
vết ở ba chỗ khác nhau, và đó là lý do `training_job_classes` phải tồn tại: nó là
**bằng chứng duy nhất** cho biết cổng thứ hai đã loại những lớp nào.

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng có `tenant_id` | 3 / 3 |
| Bảng bật RLS | **2 / 3** — `training_metrics` không bật |
| Khoá ngoại ghép trong nhóm | 2 |
| Cột `jsonb` phi chuẩn hoá có chủ đích | 2 (`config`, `evaluation`) |
| Bảng "mô hình" riêng | **Không có** — chỗ để trống có chủ ý |
