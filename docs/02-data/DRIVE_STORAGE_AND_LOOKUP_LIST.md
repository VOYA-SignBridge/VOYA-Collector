# Lưu trữ Google Drive và Lookup list

Chốt ngày 18/10/2026. Tài liệu này mô tả cấu trúc thư mục Google Drive theo tổ
chức, các Google Sheet tra cứu (Lookup list), quản lý phiên bản dữ liệu và mô
hình, và nhật ký kiểm toán. Mục 9 ghi thứ tự triển khai.

## 1. Nguyên tắc

- **Database là nguồn sự thật.** Drive chỉ giữ tệp; Sheet chỉ là bảng tra cứu cho
  người đọc. Sửa tay trên Sheet không chảy ngược vào hệ thống, nên người dùng chỉ
  có quyền xem.
- **Mỗi tổ chức một không gian riêng**: dữ liệu, mô hình, Sheet tra cứu, nhật ký.
- **Phiên bản là bất biến**: dataset đã chốt và mô hình đã phát hành không bị ghi
  đè; chỉ thêm bản mới, mỗi bản có sha256.
- **Chỉ ghi khi có thay đổi**: không còn chu kỳ 30 giây / 60 giây / 5 phút.
- **Không hardcode**: tên thư mục, tên tệp Sheet, tên tab nằm ở một module cấu
  hình (`app/storage/drive_layout.py`). Mọi tên trên Drive là tiếng Anh không dấu.
- **Đọc theo ID tệp**, không theo đường dẫn. Dời hay đổi tên thư mục không làm
  hỏng link nào.

## 2. Cây thư mục

```
SignBridge Storage/
├── Lookup list/                        chỉ quản trị nền tảng xem
│   ├── platform - Tenants
│   └── platform - Storage layout
├── SOT/                                gói dữ liệu có chữ ký (không đổi)
│   ├── Ver<n>/
│   └── _archive/
├── Community/                          VOYA (tenant_id = default)
│   ├── Lookup list/
│   │   ├── community - Labels
│   │   ├── community - Samples
│   │   ├── community - Videos
│   │   ├── community - Dataset versions
│   │   ├── community - Models
│   │   └── community - Audit logs
│   ├── Videos/
│   │   └── <language>/<dialect>/<video>
│   ├── Samples/
│   │   └── <language>/<dialect>/class_<slug>_<id>/sample_<id>.npz
│   └── Models/
│       └── <model_name>/
│           ├── latest_manifest.json    con trỏ tới bản đang phát hành (app đọc)
│           └── v<n>/
│               ├── <tệp mô hình>
│               ├── labels.json         số thứ tự -> nhãn
│               ├── dataset.json        danh sách mẫu đã dùng để huấn luyện
│               └── metadata.json       chỉ số, sha256, ngày phát hành
└── Tenants/
    └── <tenant slug>/                  tên duy nhất, xem mục 7
        ├── Lookup list/                (6 Sheet như Community, tiền tố là slug)
        ├── Videos/
        ├── Samples/
        └── Models/
```

Ghi chú:

- `Samples/` là cây `features/` trên đĩa; `Videos/` là `raw_videos/`. Tên trên đĩa
  giữ nguyên, chỉ tên trên Drive đổi (ánh xạ trong `drive_path_for`).
- Điểm mốc thô (`dataset/raw/`) **không** đẩy lên Drive — chưa từng đẩy.
- Không có thư mục `datasets/`: một phiên bản dữ liệu chỉ là danh sách mẫu, lưu ở
  DB, hiện ở Sheet `Dataset versions`, và chép vào `dataset.json` của mô hình.
- Thư mục tổ chức và `Lookup list/` chỉ được tạo khi có dữ liệu đầu tiên; từng
  Sheet chỉ được tạo khi có dòng đầu tiên của loại đó.

Bị bỏ khỏi gốc Drive: `labels.csv`, `samples.csv`, `raw_uploads.csv`, các thư mục
`features/`, `raw_videos/`, `models/`, `tenants/default/`. Hai Sheet cũ `labels`,
`samples` giữ trong lúc chuyển, kiểm đủ rồi mới đưa vào Thùng rác. Tệp
`labels.csv`/`samples.csv` **trên đĩa máy chủ** vẫn là nguồn sự thật, không bỏ.

## 3. Quy ước chung cho Sheet

- Tên tệp: `<tenant slug> - <Type>`; với VOYA là `community`, với nền tảng là
  `platform`. Mỗi tệp một tab, tên tab là loại viết thường (`labels`, `samples`…).
- Tên cột `snake_case` tiếng Anh; thời gian dạng ISO; boolean `0`/`1` — giống hai
  Sheet cũ để script đang đọc theo tên cột không vỡ.
- Một cột link duy nhất: **`storage_url`**, trỏ đúng thứ dòng đó mô tả (tệp hoặc
  thư mục).
- Dòng bị xoá không bị gỡ, chỉ có `deleted_at`. Cột mới luôn thêm ở **cuối**.
- Chỉ ghi các dòng đã đổi; dòng mới nối xuống cuối.

## 4. Các Sheet của một tổ chức

### 4.1 `<slug> - Labels`
Cột y như `labels` cũ, bỏ `tenant_id`, thêm ở cuối: `sample_count`,
`approved_count`, `pending_count`, `updated_at`, `storage_url` (thư mục lớp).

### 4.2 `<slug> - Samples`
Cột y như `samples` cũ (kể cả `file_path`), bỏ `tenant_id`. `storage_url` trỏ
tệp `.npz`.

### 4.3 `<slug> - Videos`
Cột y như `raw_uploads.csv` cũ (`upload_uid` … `visibility`, `deleted_at`), bỏ
`tenant_id`, thêm ở cuối: `duration_sec`, `size_bytes`, `sample_count`,
`processing_status` (`pending`/`processing`/`done`/`failed`). `storage_url` trỏ
tệp video.

### 4.4 `<slug> - Dataset versions`
| Cột | Ý nghĩa |
|---|---|
| `dataset_version` | `ds-0007` |
| `created_at`, `created_by` | |
| `sample_count`, `class_count`, `signer_count` | |
| `train_count`, `val_count`, `test_count` | |
| `split_method`, `seed` | chia lại ra đúng kết quả |
| `content_hash` | sha256 của danh sách mẫu |
| `used_by_models` | ví dụ `gdcbst-recognizer v4, v5` |
| `note` | |
| `storage_url` | tệp `dataset.json` |

### 4.5 `<slug> - Models`
| Cột | Ý nghĩa |
|---|---|
| `model_name`, `version` | `gdcbst-recognizer`, `v4` |
| `status` | `draft` / `published` / `retired` |
| `job_id`, `model_type` | lần huấn luyện tạo ra bản này |
| `dataset_version` | nối sang Dataset versions |
| `test_acc`, `test_f1`, `class_count` | |
| `file_size_bytes`, `sha256` | app kiểm tệp tải về |
| `trained_at`, `published_at`, `published_by`, `retired_at` | |
| `changelog` | thay đổi so với bản trước |
| `notified_at` | lúc đã gửi thông báo bản mới |
| `storage_url` | thư mục `v<n>/` |

`job_id`, `model_type`, `test_acc`, `test_f1`, `trained_at` (`completed_at`),
`published_at` (`promoted_at`), `retired_at` (`superseded_at`) đã có ở
`training_jobs`; phần còn lại bổ sung khi làm đăng ký mô hình (mục 6).

### 4.6 `<slug> - Audit logs`
| Cột | Ý nghĩa |
|---|---|
| `event_id`, `occurred_at` | |
| `log_category` | xem mục 5 |
| `event_type` | |
| `actor` | tên tài khoản hoặc `system` |
| `object_type`, `object_id`, `object_name` | |
| `summary` | |
| `storage_url` | tệp/thư mục của đối tượng |

## 5. Nhật ký kiểm toán

`audit_log` trong DB chỉ ghi sự kiện cần thiết, có thêm cột `log_category`:

| `log_category` | `event_type` |
|---|---|
| `label` | `label.created`, `label.renamed`, `label.moved`, `label.deleted`, `label.restored` |
| `sample` | `samples.added`, `samples.deleted`, `samples.restored`, `samples.approved` — gộp theo ngày × lớp |
| `video` | `video.uploaded`, `video.deleted` |
| `dataset` | `dataset_version.created` |
| `model` | `model.trained`, `model.published`, `model.retired`, `model.rolled_back` |
| `member` | `member.added`, `member.removed`, `member.role_changed` |
| `storage` | `storage.moved`, `storage.purged` |
| `security` | các sự kiện bảo mật đang có (`security.*`, `api_key.*`, 2FA…) |

Bỏ ghi `tenant.active.switched` (chuyển tổ chức đang làm việc là điều hướng,
không phải thay đổi). Không ghi đăng nhập, xem trang, lượt đồng bộ, lượt thử lại.

Sheet `Audit logs` ghi **mỗi ngày một lần** (giờ thấp điểm), chỉ nối các dòng mới
kể từ lần trước; ngày không có gì thì không gọi Drive. Nhóm `security` không đưa
lên Sheet. Xem trong ngày thì dùng trang quản trị (đọc thẳng DB).

## 6. Quản lý và phân phối mô hình

- Vòng đời: `draft` → (đạt cổng chất lượng) → `published` → `retired`.
- Metadata ở DB; `metadata.json` trên Drive là bản chép.
- Truy vết: mô hình → `dataset_version` → danh sách mẫu.
- Phân phối: API trả bản đang phát hành; app so `version`, tải theo ID tệp, kiểm
  sha256 rồi mới thay, giữ bản cũ để quay lại. `latest_manifest.json` giữ tên cũ
  làm đường dự phòng cho app cũ — **app phải cập nhật trước khi dời `models/`**.
- Thông báo bản mới: chuông trên web, email thành viên tổ chức, webhook
  `model.published`.
- Quay lại bản cũ = trỏ con trỏ về bản trước, không xoá gì.

## 7. Tên tổ chức duy nhất

- **Khoá so trùng** là slug của tên: bỏ dấu, chữ thường, ký tự khác chữ/số thành
  `-` (`tenant_admin._slugify_tenant`). "Trường A", "truong a", "TRUONG-A" là một.
- Tổ chức mới: `tenant_id` = `slug` = khoá đó, **không còn hậu tố ngẫu nhiên**.
  Hậu tố từng có để không dò được tên tổ chức bằng cách thử đăng ký; nhưng chặn
  tên trùng tự nó đã cho biết tên có tồn tại, nên hậu tố không còn che được gì.
- Tên bị từ chối khi khoá trùng với `slug`, `tenant_id` hoặc khoá của tên hiển
  thị của **bất kỳ** tổ chức nào, kể cả đã xoá mềm (thư mục Drive của nó có thể
  vẫn còn). Đổi tên hiển thị cũng qua đúng phép kiểm này.
- Tên dành riêng: `default`, `community`, `platform`, `tenants`, `lookup-list`,
  `sot` và các tên hệ thống khác — vì chúng trùng thư mục gốc Drive hoặc tenant
  hệ thống. Danh sách sinh từ hằng số trong `drive_layout`, không gõ lại.
- Tổ chức cũ giữ `tenant_id` có hậu tố (30+ khoá ngoại trỏ vào, `ON UPDATE
  RESTRICT`); thư mục Drive của chúng lấy theo `slug`, và `slug` được làm sạch ở
  bước dời bố cục.

## 8. Chống thư mục trùng và test chạm Drive

- Tạo thư mục Drive đi qua khoá Redis theo (thư mục cha, tên). Sau khi tạo, liệt
  kê lại: nếu có nhiều thư mục cùng tên (máy khác tạo cùng lúc), mọi tiến trình
  chọn **thư mục cũ nhất**; thư mục do chính mình vừa tạo mà rỗng thì đưa vào
  Thùng rác. Nhờ vậy cả khi Redis không với tới, các bên vẫn hội tụ về một thư mục.
- Bộ test không bao giờ gọi Google API thật: `conftest.py` chặn ở hai lớp —
  không cho dựng `GoogleDriveClient`, và chặn mọi lệnh gọi HTTP của
  `googleapiclient`. Test cần Drive phải dùng client giả.

## 9. Thứ tự triển khai

1. Nền móng: tên tổ chức duy nhất, khoá chống thư mục trùng, chặn test chạm Drive.
2. Bố cục mới (`Community/`, `Tenants/<slug>/`, `Samples/`, `Videos/`, `Models/`),
   dời dữ liệu cũ (chạy khô trước), dọn rác.
3. Sheet Lookup list theo tổ chức; chỉ ghi khi đổi; bỏ beat CSV.
4. Phiên bản dữ liệu (`ds-xxxx`) nối với split ghim đã có.
5. Đăng ký mô hình `v<n>`, API phát hành, thông báo.
6. `platform - Tenants`, `platform - Storage layout`, Sheet `Audit logs`.
7. Cập nhật app di động rồi mới dời `models/`; tắt bộ ghi Drive ở hai máy khác.
