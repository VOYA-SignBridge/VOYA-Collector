# Byte nào tính vào `max_storage_mb`

Chốt ngày 25/08/2026, trước khi viết phần quyết toán và đối chiếu của Billing v8.

`max_storage_mb` không có nghĩa cho tới khi câu hỏi này có câu trả lời bằng văn
bản. Không có nó thì lượt giữ chỗ và lượt đối chiếu đếm hai tập byte khác nhau,
và bộ đếm sẽ "đúng" theo cả hai phía mà vẫn sai.

Số đo lấy từ `/dataset` trên sản xuất, 25/08/2026.

## Bảng chốt

| Hiện vật | Đường dẫn | Quy được về tenant bằng | Tính quota | Nguồn kích thước |
|---|---|---|---|---|
| `.npz` đặc trưng | `features/…`, `features/_tenants/<id>/…` | **đường dẫn** | **CÓ** | `stat().st_size` sau khi ghi |
| `.npz` kho raw (hợp đồng v3) | `raw/…`, `raw/_tenants/<id>/…` | **đường dẫn** (gương của `features/`) | **CÓ** | `stat().st_size` |
| video thô tải lên | `raw_videos/<lang>/<dialect>/<class>/` | **hàng `raw_uploads`** — thư mục KHÔNG phân vùng theo tenant | **CÓ** | `bytes_written` khi ghi; `stat()` theo `local_path` khi đối chiếu |
| ZIP xuất dữ liệu | `_exports/<tenant>_<uuid>.zip` | tên tệp | không | — |
| ảnh chụp registry | `registry_versions/<tenant>_v<n>.json` | tên tệp | không | — |
| `samples.csv`, `labels.csv`, `signers.csv`, `*.bak` | gốc `dataset/` | — | không | — |
| `labels/`, `legal/`, `manifests/`, `vocabulary_registry.json` | gốc `dataset/` | — | không | — |
| `features_zfix/`, `_backup_renorm/`, `samples/`, `_deleted/`, `backups/`, `cache/` | gốc `dataset/` | — | không | — |
| điểm lưu huấn luyện | kho hiện vật huấn luyện | — | không | — |

## Vì sao ba mục đầu tính, và bảy mục sau không

**`features/` và `raw/`** là dữ liệu tenant tạo ra và giữ. Hai cây là gương của
nhau: `raw_archive_path()` thay đúng đoạn `features` phải nhất bằng `raw`, nên
`_tenants/<id>/` sống sót qua phép thay và cây raw phân vùng y hệt cây features.
Kho raw là nửa **không tái tạo được** (`sequence` dựng lại được từ landmark thô,
landmark thô không dựng lại được từ gì cả), nên bỏ nó ra khỏi hoá đơn là tính
tiền phần rẻ và cho không phần đắt.

**Video thô** là hiện vật LỚN NHẤT một tenant tạo ra — đo được: một video
95,6 MB so với ~26 KB mỗi `.npz`. Không tính nó thì `max_storage_mb` không canh
được thứ thật sự làm đầy đĩa. Nhưng `raw_videos/<lang>/<dialect>/<class>/`
**không phân vùng theo tenant**, nên quy chủ phải đi đường cơ sở dữ liệu:
`raw_uploads` có `tenant_id` và `local_path`, và tên tệp mang `upload_uid` duy
nhất nên hai tenant thu cùng một lớp không đụng tệp nhau, chỉ chung thư mục.

Ba mục trên là *dữ liệu*; bảy mục dưới là *bản sao, siêu dữ liệu, hoặc hiện vật
nền tảng*.

**ZIP xuất** cố ý không tính, vì hai lý do rời nhau và mỗi lý do đã đủ: nó là
**bản sao của byte đã bị tính rồi** — tính lần nữa là thu tiền hai lần cho cùng
một dữ liệu; và nó có vòng đời riêng (`cleanup_expired_exports`, chạy hằng
ngày), nên tính nó nghĩa là hạn mức của một tổ chức phụ thuộc vào việc họ có
vừa bấm nút xuất hay không. Tính tiền quyền mang dữ liệu đi là điều không nên
làm ngay cả khi con số cho phép.

**`registry_versions/`, các CSV gốc, `labels/`, `legal/`** là mặt phẳng nền
tảng. Chúng nằm cùng ổ đĩa với dữ liệu tenant; đó là lý do kỹ thuật, không phải
lý do thương mại. `samples.csv` là bản SOT của cả hệ thống, không của ai.

**`features_zfix/`, `_backup_renorm/`, `samples/`, `_deleted/`, `backups/`** là
tồn dư của các lượt di trú và sửa lỗi trước đây (66,2 + 10,2 + 8,5 + 1,7 MB).
Chúng là nợ vận hành của nền tảng. Một tổ chức không được trả tiền cho một lượt
sửa lỗi z của chúng tôi.

## Miễn trừ nghĩa là gì

`billing_exempt` **không** nghĩa là "không biết tenant dùng bao nhiêu". Nó nghĩa
là:

    mức dùng vẫn được đo và ghi
    hạn mức không được dùng để chặn

Nên `_limit_bytes()` trả `None` cho tenant miễn trừ (không có trần), còn
`reconcile()` không hề hỏi `billing_exempt` — nó đo mọi tenant như nhau. Một
tenant nền tảng không quan sát được là một tenant không ai biết đang chiếm bao
nhiêu đĩa.

## Trạng thái nghiệp vụ hợp lệ: vượt hạn mức

`bytes_used > limit` **không phải hỏng dữ liệu**. Nó xảy ra một cách hoàn toàn
hợp lệ khi một tổ chức hạ gói. Lượt đối chiếu ghi nhận và báo, nhưng **không**
xoá gì và **không** đổi gói; phần cưỡng chế chỉ chặn lượt ghi TIẾP THEO. Dữ liệu
đã có là của họ.

## Lỗ hổng bảng này vá

Trước lượt chốt này:

* đường ghi video **giữ chỗ theo `Content-Length`** — tức tính tiền byte video
  thô,
* nhưng `reconcile()` chỉ đi bộ `features/`,
* nên mỗi lượt đối chiếu **xoá sạch khoản đã tính cho video**, đưa bộ đếm về
  đúng phần `.npz`.

Bộ đếm sẽ tự "sửa" mình về một con số sai mỗi ngày, và không phép kiểm nào bắt
được vì cả hai phía đều nhất quán với chính nó. Đo được trên sản xuất: 149,3 MB
đếm được trên tổng ~600 MB thật.
