# PDM kiến trúc mở rộng (Target / Extended)

> **Caption cho hình:** Mô hình dữ liệu vật lý mở rộng của CTU.SignBridge, bao
> gồm các đối tượng hiện thực và các cấu phần kiến trúc mục tiêu chưa được
> materialize trong lược đồ runtime.
>
> Extended physical data model of CTU.SignBridge, comprising implemented objects
> together with target architectural components not materialized in the frozen
> runtime schema.

## Ký hiệu

```
đối tượng thường     có trong lược đồ as-built
<<target>>           cấu phần kiến trúc, CHƯA materialize ở revision đóng băng
```

Không dùng màu — quyển in đen trắng. Không dùng nét đứt cho quan hệ giữa hai
`<<target>>`: nét đứt đã mang nghĩa khác trong ký pháp quan hệ.

## Ba quy tắc không được phá

1. **As-built là nguồn sự thật cho hiện trạng.** Target không được dùng để "sửa"
   as-built.
2. **Chín bảng `target-only` là hạt nhân có bằng chứng.** DDL thiết kế cũ chỉ
   dùng để phục hồi *ý định*: quan hệ, lực lượng, khoá, trường. Nó không phải
   nguồn sự thật.
3. **Một đối tượng chỉ được gọi là đã hiện thực nếu nó nằm trong ảnh chụp
   as-built đóng băng.** Xuất hiện trong SQL chết, trong PDM cũ hay trong model
   target đều KHÔNG nâng trạng thái của nó.

Hệ quả của quy tắc 2: một bảng có trong thiết kế cũ mà không nằm trong as-built,
không nằm trong chín bảng hạt nhân, và không đáp một yêu cầu target còn hiệu lực
— thì **không** được đưa vào. Nếu không, Target PDM thành nghĩa trang của mọi ý
tưởng từng tồn tại.

## `user_profiles` KHÔNG vào Target

Nguồn duy nhất của nó là `backup.sql`, và tệp đó là đầu ra `pg_dump` ngày
30/07/2026 — ảnh chụp một cơ sở dữ liệu đã chạy thật.

```
DDL trong backend/migrations/*.sql   ý định   -> ứng viên target
CREATE TABLE trong một pg_dump       quá khứ  -> đã bị bỏ
```

Cùng đuôi tệp, hai loại chứng cứ **trái hướng nhau**. Một bảng chỉ xuất hiện
trong ảnh chụp cũ là bằng chứng rằng nó từng tồn tại rồi bị loại, không phải bằng
chứng rằng ai đó muốn có nó. Đưa nó vào Target và dán nhãn "cấu phần kiến trúc
mục tiêu" là nói ngược lại sự thật.

Công cụ reverse đã tách riêng nhóm `historical` cho đúng trường hợp này. Hiện
`historical = 1`, và đó là `user_profiles`.

## Hạt nhân: chín bảng, hai phát hiện quan trọng hơn bản vẽ

### Phát hiện 1 — hai nguồn thiết kế MÂU THUẪN nhau

`001_create_production_schema.sql` và `002_mvp_schema.sql` không khớp:

| | 001 | 002 |
|---|---|---|
| `model_versions` khoá chính | `model_version_id` | `version_id` |
| `model_versions` UNIQUE | `(model_id, version_string)` | `(model_family, version_string)` |
| `experiments` | 23 cột, có FK sang `dataset_version_id`, `dataset_split_id` | 11 cột, **không** FK sang dataset |

Không được lặng lẽ trộn. Biên bản giải quyết, ghi thành một mục để người sau đọc
được thay vì phải suy lại:

```
Nền tảng Target       : migration 001
Thiết kế xung đột     : migration 002
Giải quyết            : chọn 001; KHÔNG hợp nhất 002
```

Lý do chọn:

1. `001` đầy đủ hơn về liên kết miền — nó là bản **duy nhất** định nghĩa chuỗi
   dataset và nối `experiments` vào chuỗi ấy.
2. `002` là một nhánh thiết kế khác cho MVP, tức một điểm dừng trung gian, không
   phải kiến trúc đích.
3. **Không có hiện thực runtime nào phân xử được xung đột này** — cả hai đều chưa
   từng chạy. Nên lựa chọn là một phán quyết thiết kế, và phải được ghi là phán
   quyết, không phải trình bày như một sự thật tìm thấy.

Chuẩn hoá xung đột rồi làm như nó chưa từng tồn tại là biến Target thành một bản
tổng hợp âm thầm. Có biên bản thì Target là một thiết kế **có nguồn gốc**.

## Quan hệ CHƯA GIẢI — không tự suy từ tên bảng

`002` không có khoá ngoại `experiments → dataset`, `001` thì có hai:
`dataset_version_id` và `dataset_split_id`. Vì đã chọn 001, quan hệ ấy có mặt
trong Target. Nhưng **ý nghĩa nghiệp vụ của nó chưa được chốt**, và tài liệu này
không chốt hộ.

Câu hỏi thật: một thực nghiệm chạy trên cái gì?

```
dataset          -> mất chính lợi ích của versioning: một thực nghiệm trỏ vào
                    một bộ dữ liệu CÓ THỂ ĐỔI thì không tái lập được
dataset version  -> cố định thành phần mẫu
split            -> cố định cả phép chia
training job     -> nối vào as-built, nhưng đổi bản chất của `experiments`
```

Nếu mục tiêu là tái lập được, quan hệ hợp lý nằm ở `DatasetVersion` hoặc `Split`,
không ở `Dataset`. Nhưng "hợp lý" không phải bằng chứng, và suy một khoá ngoại từ
tên bảng là đúng thứ bước lập PDM này sinh ra để tránh.

**Trạng thái: quan hệ chưa giải.** Vẽ trên diagram kèm ghi chú, không vẽ như một
khoá ngoại đã chốt. Cùng cách xử lý cho
`model_deployments UNIQUE(environment, deployment_status)`.

## Bảng delta — thiết kế gốc so với Target đã hiệu chỉnh

Dành cho Chương 3 / phụ lục thiết kế. **Không** đưa vào Chương 2.

| Vấn đề của thiết kế gốc (001) | Hiệu chỉnh Target |
|---|---|
| quyền sở hữu dataset/model theo NGƯỜI DÙNG | đưa về phạm vi TỔ CHỨC |
| không có khoá tenant | `tenant_id NOT NULL` trên cả chín bảng |
| nối sang mẫu chỉ bằng `sample_uid` | khoá ngoại hợp `(tenant_id, sample_uid)` |
| UNIQUE toàn nền tảng trên `name` | đặt phạm vi theo tổ chức khi là khoá nghiệp vụ |
| không có RLS | RLS + FORCE RLS + policy theo phạm vi |
| quan hệ cha–con không kiểm phạm vi | khoá ngoại hợp xuyên toàn chuỗi |
| `experiments → dataset` nghĩa chưa rõ | đánh dấu **chưa giải**, không tự suy |

### Phát hiện 2 — thiết kế target neo vào NGƯỜI DÙNG, không vào TỔ CHỨC

Đây là phát hiện đáng giá nhất của cả bước này, và nó chỉ lộ ra khi đọc DDL thay
vì đọc sơ đồ.

**Cả chín bảng đều không có `tenant_id`.** Quyền sở hữu của chúng đi qua
`users.id`:

```
datasets            created_by, owner_user_id  -> users.id
dataset_versions    created_by, approved_by    -> users.id
dataset_splits      created_by                 -> users.id
experiments         created_by, started_by     -> users.id
model_versions      created_by, approved_by    -> users.id
model_deployments   deployed_by, approved_by   -> users.id
```

Và có đúng **một** cầu nối từ target sang as-built:

```
dataset_samples_mapping.sample_uid  ->  samples.sample_uid
```

`samples` có `tenant_id`, có RLS, có FORCE. `dataset_samples_mapping` thì không
có gì cả. Nghĩa là nếu hiện thực nguyên trạng thiết kế này, một hàng ở bảng không
phạm vi sẽ trỏ thẳng vào một hàng ở bảng có phạm vi — và mọi thứ đi qua cầu ấy
rời khỏi ranh giới tổ chức mà không có lớp nào chặn.

Đó là **cùng một hình dạng** với bốn lỗi đã vá ở C3 và hai lỗi ở C5: phạm vi
được truyền đúng cho tới một mắt xích không biết phạm vi là gì.

Kết luận cho quyển: **thiết kế target như đang có sẽ tái lập lại chính khoảng
trống cách ly mà nhóm C1–C5 vừa đóng.** Nó phải được sửa trước khi hiện thực, chứ
không phải hiện thực rồi vá. Đây là một đóng góp có thật của bước lập PDM, và nên
được nói thẳng ở Chương 3 thay vì để hội đồng tự phát hiện.

## Nguyên tắc đóng băng từ phát hiện này

> **Kiến trúc mục tiêu phải bảo toàn MỌI bất biến mà lõi as-built đã thiết lập.**
>
> Target architecture must preserve every invariant already established by the
> as-built core.

Một kiến trúc "mở rộng" mà mở lại đường xuyên tổ chức đã đóng thì không phải mở
rộng — đó là **hồi quy ở tầng thiết kế**.

## Thiết kế Target ĐÃ HIỆU CHỈNH

Từ đây, artifact này không còn là "PDM phục hồi từ 001". Trạng thái của nó là:

> **Mô hình dữ liệu vật lý mở rộng đã hiệu chỉnh theo các bất biến đa thuê bao
> hiện hành.**

```
TargetCorrected = TargetDDL001 + CurrentTenantInvariants + AsBuiltIntegrityPatterns
```

### Provenance từng thuộc tính — bắt buộc ghi

Nếu không tách nguồn, tài liệu này sẽ chống lưng cho một khẳng định sai:
*"DDL target ban đầu đã thiết kế multi-tenancy."* Nó **chưa** thiết kế phần đó.

| Thuộc tính | Nguồn |
|---|---|
| tên bảng, ý định vòng đời dataset/model | DDL target 001 (di sản) |
| quan hệ cha–con giữa các thực thể | DDL target 001 (di sản) |
| `tenant_id` | **bổ sung** theo bất biến đa thuê bao hiện hành |
| khoá ngoại hợp theo phạm vi | **bổ sung** theo bất biến toàn vẹn xuyên phạm vi |
| RLS / FORCE RLS | **bổ sung** theo kiến trúc cách ly hiện hành |
| UNIQUE có phạm vi tenant | **hiệu chỉnh** theo quyền sở hữu của tổ chức |

### Khuôn ràng buộc

Không đưa `tenant_id` vào khoá chính — các định danh hiện là UUID toàn cục, và
đổi khoá chính sẽ kéo theo mọi tham chiếu. Thay vào đó, mỗi bảng cha mang một
UNIQUE phụ để bảng con tham chiếu **hợp**:

```sql
datasets            PRIMARY KEY (dataset_id)
                    UNIQUE      (tenant_id, dataset_id)

dataset_versions    UNIQUE      (tenant_id, dataset_version_id)
                    FOREIGN KEY (tenant_id, dataset_id)
                        REFERENCES datasets (tenant_id, dataset_id)

dataset_splits      FOREIGN KEY (tenant_id, dataset_version_id) -> dataset_versions
dataset_samples_mapping
                    FOREIGN KEY (tenant_id, dataset_version_id) -> dataset_versions
                    FOREIGN KEY (tenant_id, sample_uid)         -> samples
dataset_lineage     FOREIGN KEY (tenant_id, child_dataset_version_id)  -> dataset_versions
                    FOREIGN KEY (tenant_id, parent_dataset_version_id) -> dataset_versions

experiments         UNIQUE      (tenant_id, experiment_id)
experiment_metrics  FOREIGN KEY (tenant_id, experiment_id) -> experiments
model_versions      UNIQUE      (tenant_id, model_version_id)
                    FOREIGN KEY (tenant_id, experiment_id) -> experiments
model_deployments   FOREIGN KEY (tenant_id, model_version_id) -> model_versions
```

Điều khuôn này mua được, phát biểu chính xác:

```
trước:  khoá ngoại hợp lệ  =>  đối tượng TỒN TẠI
sau :   khoá ngoại hợp lệ  =>  đối tượng tồn tại VÀ CÙNG TỔ CHỨC
```

Bất biến `child.tenant_id = parent.tenant_id` phải giữ ở **mọi** cạnh, không chỉ
cạnh cuối tới `samples`. Sửa mỗi mắt xích cuối là lặp lại đúng lỗi C5: một guard
đặt ở một chỗ là một guard mà mắt xích thứ tư không biết là có.

### Phạm vi của UNIQUE — hỏi từng cái, không thêm máy móc

Không tự động nhét `tenant_id` vào mọi UNIQUE. Câu hỏi phải hỏi cho từng ràng
buộc là: **duy nhất toàn nền tảng, hay duy nhất trong một tổ chức?**

| UNIQUE gốc (001) | Phán | Hiệu chỉnh |
|---|---|---|
| `datasets(language, dialect, name)` | theo tổ chức | `(tenant_id, language, dialect, name)` |
| `dataset_versions(dataset_id, version_number)` | **giữ nguyên** | `dataset_id` đã hàm ý một tổ chức qua FK hợp |
| `dataset_splits(dataset_version_id, split_name)` | **giữ nguyên** | cùng lý do |
| `dataset_samples_mapping(dataset_version_id, sample_uid, augment_id)` | **giữ nguyên** | cùng lý do |
| `experiments(name)` | theo tổ chức | `(tenant_id, name)` |
| `experiment_metrics(experiment_id, epoch)` | **giữ nguyên** | cùng khuôn `training_metrics` ở C3 |
| `model_versions(model_id, version_string)` | theo tổ chức | `(tenant_id, model_id, version_string)` |
| `model_deployments(environment, deployment_status)` | **cần quyết** | xem dưới |

Hai ràng buộc `UNIQUE(name)` là nghiêm trọng nhất: `datasets` và `experiments`.
Để nguyên nghĩa là tổ chức A đặt tên một bộ dữ liệu `hoa-de` thì tổ chức B không
đặt được nữa — và va chạm tên giữa hai tổ chức cùng thu Ngôn ngữ Ký hiệu Việt Nam
là trường hợp **bình thường**, không phải ngoại lệ. Đây cũng chính là lập luận đã
dùng cho `dataset_manager` khi nó từ chối tìm thư mục lớp ở gốc chung.

`model_deployments(environment, deployment_status)` để **chưa quyết**: nó đang
nói "mỗi môi trường chỉ có một bản triển khai ở mỗi trạng thái". Câu đó có nghĩa
khác hẳn tuỳ theo `environment` là của nền tảng hay của tổ chức, và DDL 001 không
trả lời. Xem mục quan hệ chưa giải bên dưới.

### RLS

Cả chín bảng: `RLS = ON`, `FORCE RLS = ON`, policy theo phạm vi tổ chức — giống
34/34 bảng của as-built. Nhắc lại: đây là thuộc tính của **thiết kế đã hiệu
chỉnh**, không phải thứ phục hồi được từ 001.

## Chuỗi quan hệ (nguồn: 001)

```
                    samples ─────────┐  (as-built, tenant-scoped)
                                     │
   users ──┬─> datasets              │
           │       │ 1:n             │
           │       v                 │
           ├─> dataset_versions <────┼──── parent_version_id (tự trỏ)
           │       │                 │
           │       ├── 1:n ──> dataset_splits
           │       ├── 1:n ──> dataset_samples_mapping ──┘
           │       └── 1:n ──> dataset_lineage <── parent_experiment_id
           │                        (child/parent: cả hai trỏ dataset_versions)
           │
           ├─> experiments ──> dataset_versions, dataset_splits
           │       │ 1:n
           │       v
           │   experiment_metrics        UQ(experiment_id, epoch)
           │
           ├─> model_versions ──> experiments
           │       │ 1:n
           │       v
           └─> model_deployments ──> model_versions
                                 └──> previous_model_version_id (tự trỏ)
```

Tất cả chín bảng mang `<<target>>`. `samples` và `users` là đối tượng as-built,
vẽ ở ký hiệu thường — chúng cho thấy Target gắn vào hiện trạng ở đâu.

## Bố cục diagram

Target dùng **đúng sáu miền** của As-built để so được từng cặp `AsBuilt-X ↔
Target-X`:

| miền | Target thêm gì |
|---|---|
| A | *(không)* — `user_profiles` bị loại, xem trên |
| B | *(không)* |
| C | `dataset_samples_mapping` — **đối tượng liên miền**, xem dưới |
| **D** | chín bảng — toàn bộ vòng đời dataset → experiment → model |
| E | *(không)* |
| F | *(không)* |

### `dataset_samples_mapping` nằm ở cả C và D

Cùng lý do với `signer_consents` ở As-built: nó là **một** Table object có hai
vai, và ép nó về một miền sẽ làm mất một quan hệ.

```
ở diagram C   nhấn quan hệ  DatasetSampleMapping -> Sample   (cầu nối sang mẫu)
ở diagram D   nhấn quan hệ  DatasetVersion -> DatasetSampleMapping  (ghim tập mẫu)
```

Một Table object duy nhất, hai symbol. Không tạo hai bảng, không tạo shortcut.

### Quy tắc đếm

Vì có đối tượng liên miền, phép cộng theo miền **không** bằng tổng số bảng. Phải
nói rõ đang đếm gì:

```
số bảng PHÂN BIỆT trong Target      = 58 as-built + 9 target-only  = 67
số symbol trên diagram D            = 3 as-built(D) + 9 target      = 12
số symbol trên diagram C            = 6 as-built(C) + 1 liên miền   = 7
```

Ba bảng as-built của miền D là `training_jobs`, `training_job_classes`,
`training_metrics`.

Bản đầu của tài liệu này ghi "D = 11", vì nó gán `dataset_samples_mapping` **chỉ**
cho C. Con số ấy tự nhất quán nhưng đến từ một lựa chọn sai — ép một đối tượng
liên miền về một miền. Sau khi vẽ nó ở cả hai, D = 12, và `3 + 9 = 12` khớp.

Ghi lại vì đây là loại lỗi không có bộ đo nào bắt được: mọi con số đều đúng theo
định nghĩa của chính nó, và chỉ lộ ra khi ai đó cộng lại.

Target PDM **không** nên là một model chỉ gồm chín bảng mới. Nó là
`AsBuiltCore + TargetExtensions`, phân biệt bằng ký hiệu — nếu không, người đọc
không thấy chúng gắn vào hiện trạng ở đâu.

## Ma trận As-built ↔ Target

| Đối tượng | As-built | Target | Ý nghĩa |
|---|---|---|---|
| `samples` | ✓ | ✓ | mẫu; đã tenant-scoped |
| `capture_sessions` | ✓ | ✓ | phiên thu |
| `registry_versions` | ✓ | ✓ | phiên bản **danh mục** — bảo toàn không gian nhãn |
| `training_jobs` | ✓ | ✓ | việc huấn luyện ở mức ứng dụng |
| `datasets` | ✗ | ✓ | trừu tượng "sản phẩm dữ liệu" |
| `dataset_versions` | ✗ | ✓ | trạng thái bộ dữ liệu bất biến, tham chiếu được |
| `dataset_splits` | ✗ | ✓ | đặc tả phép chia |
| `dataset_lineage` | ✗ | ✓ | quan hệ nguồn gốc giữa các phiên bản |
| `dataset_samples_mapping` | ✗ | ✓ | ghim TẬP MẪU vào một phiên bản |
| `experiments` | ✗ | ✓ | theo dõi thực nghiệm |
| `experiment_metrics` | ✗ | ✓ | số liệu theo epoch của thực nghiệm |
| `model_versions` | ✗ | ✓ | đăng ký phiên bản mô hình |
| `model_deployments` | ✗ | ✓ | con trỏ triển khai + rollback |
| `user_profiles` | ✗ | ✗ | **historical** — đã bị bỏ, không phải target |
| reserved tenant `community` | ✓ | ✓ | phạm vi đã đăng ký |
| dữ liệu nghiệp vụ Community | ✗ | ✓ | chưa vận hành đầu-cuối |

## Điều Chương 2 được giữ, và điều Chương 3 phải phân biệt

Chương 2 **giữ được** lý thuyết dataset versioning — nó là lý thuyết đúng, và
Target PDM là chỗ để nó đứng.

Chương 3 phải phân biệt hai thứ mà tiếng Việt dễ gộp:

```
đã hiện thực : phiên bản DANH MỤC (registry versioning)
                -> bảo toàn KHÔNG GIAN NHÃN ứng với một trạng thái danh mục

kiến trúc mở rộng : phiên bản BỘ DỮ LIỆU bất biến (dataset versioning)
                -> cố định TẬP MẪU, qua `dataset_samples_mapping`
```

Đây chính là lý do câu *"registry makes a dataset reproducible"* đã bị hạ ở
Abstract: ghim danh mục là **điều kiện cần**, và cơ chế cung cấp điều kiện **đủ**
nằm ở cột `Target`, chưa ở cột `As-built`.
