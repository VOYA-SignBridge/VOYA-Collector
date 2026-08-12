# Vòng đời một phương ngữ — mọi tầng nó chạm tới, và cơ chế xử lý

Ngày 2026-08-01. Đi kèm [`HARDCODED_VOCABULARY_AUDIT.md`](HARDCODED_VOCABULARY_AUDIT.md)
(vì sao phải làm) — tài liệu này trả lời *làm thế nào cho không vỡ*.

Điểm xuất phát: `dialect` **không phải một cột trong một bảng**. Nó là một khoá
lan ra 10 tầng lưu trữ, và **3 tầng trong đó không sửa được**. Toàn bộ thiết kế
dưới đây xoay quanh sự thật đó.

---

## 1. Bản đồ: một giá trị `dialect` đọng ở đâu

| # | tầng | dạng | sửa được? | ghi chú |
|---|---|---|---|---|
| 1 | Postgres `classes.dialect`, `samples.dialect`, `raw_uploads.dialect` | cột | **được** | có transaction, có FK |
| 2 | Postgres `training_jobs.config` | JSON | được | danh sách dialect của job |
| 3 | `dataset/labels.csv`, `samples.csv`, `raw_videos/uploads.csv` | cột CSV | được | cần FileLock |
| 4 | `dataset/features/<lang>/<dialect>/class_.../` | **tên thư mục** | được nhưng phải **di chuyển file thật** | |
| 5 | `dataset/raw_videos/<lang>/<dialect>/` | **tên thư mục** | như trên | cây thứ hai, dễ quên |
| 6 | `file_path` / `storage_key` trong (1) và (3) | chuỗi chứa đường dẫn | được | **phải sửa cùng lúc với (4)(5)** |
| 7 | sidecar cạnh mỗi npz: `metadata.json` (mỗi lớp) + `sample_*.json` (**mỗi mẫu**) | JSON có khoá `dialect` | được | **3860 file** — tầng dễ bỏ sót nhất |
| 8 | Google Drive | bản sao của (4)(5) | được, nhưng **không có transaction** | gọi API, phải retry |
| 9 | Google Sheets | bảng xuất | tự khỏi | lần export sau ghi đè toàn bộ |
| 10 | localStorage `dialectSelected` | chuỗi | tự khỏi | client tự sửa khi nạp lại danh sách |

### Ba tầng KHÔNG sửa được

| tầng | vì sao bất biến |
|---|---|
| **Checkpoint** `tcn_dialect-hoa-de_20260721_160609.pt` + `models.json` (`id`, `dialect`) | Tên file là một phần của **hồ sơ thí nghiệm**. Đổi nó là cắt đứt đường truy ngược từ model đang chạy về dữ liệu đã huấn luyện nó. |
| **Split đã versioned** `processed/splits/versions/<v>/` + manifest ghi `dialect` | Một split đã công bố **mô tả một thí nghiệm đã chạy xong**. Sửa nó là làm sai lệch hồ sơ, không phải cập nhật. |
| **Phiên bản SOT đã ký** | Bất biến theo đúng thiết kế — chữ ký sẽ hỏng. |

---

## 2. Hệ quả số một: `dialect_id` là BẤT BIẾN

Vì ba tầng trên không sửa được, **không được cung cấp chức năng "đổi dialect_id"**.
Có làm cũng chỉ đổi được 7/10 tầng, và 3 tầng còn lại sẽ trỏ vào một khoá không
còn tồn tại — đúng kiểu hỏng âm thầm mà tài liệu kia mô tả.

Đây chính là lý do **phải tách hai trường**:

| thao tác | chạm mấy tầng | rủi ro |
|---|---|---|
| đổi `display_name` (`Miền Bắc` → `Bắc Bộ`) | **1** — một `UPDATE` một hàng | không |
| đổi `dialect_id` (`bac` → `mien-bac`) | **10**, 3 trong đó bất khả | cao |

Tách ra thì 99% nhu cầu đổi tên rơi vào dòng đầu. Gõ sai tên hiển thị? Sửa một
ô. Gõ sai slug? Xử lý bằng **gộp**, không bằng đổi tên.

---

## 3. Năm thao tác được hỗ trợ

### 3.1 TẠO — có duyệt

```
user gõ "Miền Tây"
   -> slug hoá: mien-tay        (ASCII, thường, bỏ dấu — vì nó là tên thư mục)
   -> đã tồn tại mien-tay?
        có  -> 409, KHÔNG tạo, trả về tên đang dùng để người dùng tự quyết
        không -> INSERT status='pending', created_by=<user_id>
   -> chỉ chính tài khoản đó thấy trong thư viện nhãn
   -> admin duyệt -> status='approved' -> mọi người thấy
```

Hai chi tiết dễ bỏ:

- **Đua nhau tạo.** Hai người cùng gõ "Miền Tây" một lúc: PRIMARY KEY làm người
  thứ hai thất bại, bắt lỗi rồi trả về hàng đã có. Không cần khoá gì thêm — đây
  lại là một điểm mà CSV không tự làm được còn Postgres thì có sẵn.
- **`registry_version` phải tăng** ở mỗi lần đổi, nếu không frontend đang cache
  sẽ không biết có cái mới.

### 3.2 DÙNG KHI ĐANG CHỜ DUYỆT

Người tạo được thu mẫu ngay — đó là mục đích của nút này. Nghĩa là **thư mục vật
lý (tầng 4, 5) ra đời trước khi admin duyệt**.

Điều đó chấp nhận được, vì `pending` là khái niệm ở tầng **danh mục**, không phải
tầng **lưu trữ**. Từ chối một phương ngữ không phải là mất dữ liệu — nó là một
lần gộp.

### 3.3 ĐỔI TÊN HIỂN THỊ

Một `UPDATE dialects SET display_name = ...`. Không đụng bất kỳ tầng nào khác.
Không cần job, không cần duyệt lại.

### 3.4 VÔ HIỆU HOÁ (`is_active = 0`)

Dành cho `testdatase`: biến khỏi mọi dropdown, **dữ liệu và thư mục giữ nguyên**,
truy vấn lịch sử vẫn chạy. Không ai phải chọn giữa "xoá mất lịch sử" và "để rác
trong menu".

### 3.5 GỘP (A → B) — thao tác nặng duy nhất

Đây là cách xử lý cho: admin từ chối một phương ngữ chờ duyệt, hoặc phát hiện
`mien-bac` và `bac` là một.

Chạy như **Celery task có trạng thái**, theo thứ tự "rẻ và hoàn tác được trước,
đắt và khó hoàn tác sau":

```
1. Postgres, MỘT transaction:
     UPDATE classes  SET dialect=B WHERE dialect=A
     UPDATE samples  SET dialect=B, file_path=replace(...), storage_key=replace(...)
     UPDATE raw_uploads ...
     INSERT INTO dialect_aliases(old_id=A, new_id=B, merged_at=now())
     UPDATE dialects SET is_active=0, merged_into=B WHERE dialect_id=A
   -> hỏng ở đây thì rollback, chưa file nào bị đụng

2. Di chuyển thư mục (tầng 4, 5): features/vn/A/*  ->  features/vn/B/
   -> hỏng giữa chừng thì DB đã trỏ sang B; task retry và tiếp tục ĐÚNG CHỖ
      vì thao tác này idempotent (thư mục đã chuyển thì bỏ qua)

3. Sidecar (tầng 7): ghi lại khoá dialect trong metadata.json + sample_*.json
   -> chạy sau cùng trong nhóm cục bộ vì nó nhiều file nhất và ít hại nhất
      nếu chậm: không ai đọc sidecar để phục vụ request

4. Drive (tầng 8): dispatch task riêng, best-effort + retry
   -> KHÔNG chặn kết quả trả về cho admin
```

**Không đụng tầng bất biến.** Thay vào đó là bảng tra ngược:

```sql
CREATE TABLE dialect_aliases (
    old_dialect_id TEXT PRIMARY KEY,
    new_dialect_id TEXT NOT NULL REFERENCES dialects(dialect_id),
    merged_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    merged_by      UUID REFERENCES users(id)
);
```

Nhờ nó, một checkpoint tên `tcn_dialect-mien-bac_*.pt` hay một manifest split ghi
`dialect: mien-bac` **vẫn tra ngược được** sau khi `mien-bac` đã gộp vào `bac`.
Hồ sơ thí nghiệm giữ nguyên chữ nó đã ghi; hệ thống biết chữ đó bây giờ nghĩa là gì.

### 3.6 XOÁ THẬT

Chỉ cho phép khi **0 lớp, 0 mẫu, 0 thư mục**. Ngoài ra luôn dùng 3.4 hoặc 3.5.

---

## 4. Bảng dữ liệu

```sql
CREATE TABLE dialects (
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    dialect_id    TEXT NOT NULL,              -- slug ASCII, BẤT BIẾN
    display_name  TEXT NOT NULL,              -- có dấu, sửa thoải mái
    language      TEXT NOT NULL DEFAULT 'vn',
    is_alphabet   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    merged_into   TEXT REFERENCES dialects(dialect_id),
    created_by    UUID REFERENCES users(id),
    approved_by   UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at   TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, dialect_id)
);
```

`PRIMARY KEY (tenant_id, dialect_id)` chứ không phải `dialect_id` đơn: trường A
và trường B đều có quyền có phương ngữ "mien-tay" của riêng họ.

---

## 5. Đường lưu trữ và multitenant — quyết định phải chốt NGAY

Hôm nay: `dataset/features/<lang>/<dialect>/...`
Nhiều tenant: `dataset/<tenant>/features/<lang>/<dialect>/...`

**Đây là thay đổi đắt nhất trong cả kế hoạch multitenant**, vì nó viết lại
`file_path` + `storage_key` của **mọi hàng** và di chuyển **mọi file**. Làm khi
có 3860 mẫu thì là một lần chạy script; làm khi có 100k mẫu và khách hàng đang
dùng thì là một cuộc di trú có downtime.

Ba lựa chọn:

| | đổi layout ngay | đổi khi có tenant thứ 2 | không bao giờ tách thư mục |
|---|---|---|---|
| công bây giờ | 1 script + cập nhật đường dẫn | 0 | 0 |
| công về sau | 0 | rất lớn, có downtime | phải lọc theo cột ở mọi truy vấn file |
| xoá dữ liệu 1 tenant | `rm -rf` 1 thư mục | như trên | phải quét và lọc — nghĩa vụ pháp lý của SaaS |

Không cần chốt hôm nay, nhưng **phải chốt trước khi có tenant thứ hai**, và câu
trả lời nên nằm cùng chỗ với [`MULTITENANT_PREP.md`](MULTITENANT_PREP.md).

---

## 6. Chuyện dấu tiếng Việt — nói cho hết một lần

**Postgres đã lưu UTF-8 sẵn.** `postgres:17` mặc định `initdb` là UTF8, và bằng
chứng chạy thật: giao diện đang hiện `rang muối`, `Hòa Đê`, `Cần Thơ` đúng dấu,
dữ liệu đó đi qua DB. Không có việc gì phải làm ở tầng database.

Chỗ **thật sự** không chịu được dấu là **tên thư mục** — và đó là lý do duy nhất
`dialect_id` phải ASCII, không phải vì database.

Bộ huấn luyện **không gãy vì dấu**, vì nó không bao giờ khoá theo chữ có dấu:
`dataset_loader.py` ánh xạ `class_idx - 1` sang chỉ số tensor (số nguyên);
`label_original` (có dấu) chỉ đi theo để ghi log và phân tích.

| chỗ dấu có thể gãy | tình trạng |
|---|---|
| tên thư mục / tên file | **rủi ro thật** → giữ quy tắc ASCII cho khoá |
| console Windows (cp1252) | đã xử lý — `scripts/_console.py` ép UTF-8 |
| đọc/ghi CSV | đã xử lý — đọc `utf-8-sig`, ghi `utf-8` |
| tên thư mục Drive | đã xử lý — `_drive_safe_name` giữ dấu, bỏ `/\:*?"<>\|` |
| nhãn trên biểu đồ | không có rủi ro — không dùng matplotlib, vẽ ở frontend |

Kết luận: **giữ nguyên quy tắc "ASCII cho khoá, có dấu cho hiển thị"**. Nó đã
đúng sẵn và chính nó làm bộ train miễn nhiễm; việc cần làm chỉ là tách rõ hai
trường thay vì trộn như hiện nay.

---

## 7. Thứ tự an toàn của mọi thao tác ghi

Một nguyên tắc chung, không riêng phương ngữ — rút từ lỗi đã xảy ra trong dự án
này (dispatch Drive trước khi có hàng CSV, xoá lớp trước khi xoá mẫu):

```
Postgres (transaction)  ->  CSV (FileLock)  ->  file cục bộ  ->  sidecar  ->  Drive
     hoàn tác được            hoàn tác được      chậm            nhiều       xa, hay lỗi
```

Đi ngược thứ tự này là cách sinh ra dữ liệu mồ côi. Mọi bước sau bước 1 phải
**idempotent** để task retry được mà không nhân đôi.

---

## 8. Kiểm tra

Ngoài T1–T4 ở tài liệu kia, vòng đời này cần thêm:

| | bất biến | bắt được |
|---|---|---|
| **T5** | mọi `file_path` trong samples phải khớp `features/<lang>/<dialect>/...` với đúng `dialect` của hàng đó | gộp chạy nửa chừng: DB đã đổi, thư mục chưa |
| **T6** | mọi `dialect` trong sidecar phải khớp `dialect` của hàng tương ứng | tầng 7 bị bỏ sót |
| **T7** | mọi `dialect` xuất hiện trong checkpoint/manifest split phải có trong `dialects` **hoặc** `dialect_aliases` | tra ngược đứt sau một lần gộp |
| **T8** | không `dialect_id` nào có `status='pending'` mà đã quá N ngày | yêu cầu tạo bị bỏ quên, người thu chờ mãi |

T5 và T6 nên chạy trong `verify_deployment.py` — chúng bắt đúng trạng thái nửa
vời mà một task gộp thất bại để lại, và đó là thứ không ai phát hiện bằng mắt.
