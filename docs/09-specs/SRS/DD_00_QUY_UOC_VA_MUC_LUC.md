# Từ điển dữ liệu (Data Dictionary) — Quy ước và mục lục

*Trích trực tiếp từ **cơ sở dữ liệu đang chạy** ngày **18/08/2026** bằng truy vấn
`information_schema.columns` và `pg_catalog.pg_constraint`. Không chép lại từ tài
liệu cũ — bản dump lược đồ trong `docs/02-data/db/schema_erd.sql` là ảnh chụp
10/08/2026 và **đã lệch** (44 bảng so với 57 hiện tại).*

---

## 1. Quy mô lược đồ (đo ngày 18/08/2026)

| Chỉ số | Giá trị |
|---|---:|
| Tổng số bảng vật lý | **58** |
| Bảng nghiệp vụ | **57** |
| Bảng kỹ thuật (`schema_migrations`) | 1 |
| Tổng số cột | **628** |
| Bảng mang cột `tenant_id` | **35** |
| Bảng bật chính sách bảo mật mức hàng (RLS) | **34** |
| Bảng bật cờ cưỡng chế với chủ sở hữu (FORCE RLS) | **34 / 34 = 100 %** |
| **Độ phủ cách ly** | **34 / 35 ≈ 97,1 %** |
| Bảng có `tenant_id` nhưng **không** bật RLS | **1** — `tenant_purges` |

> **Thay đổi so với ảnh chụp 10/08/2026 ghi ở Phụ lục A:** con số cũ là 32/34 ≈
> 94,1 % và nêu **hai** bảng hở (`tenants`, `tenant_purges`). Bảng `tenants` **nay
> đã bật RLS**, nên chỉ còn `tenant_purges`. Số bảng có `tenant_id` cũng tăng từ 34
> lên 35. Ghi lại chênh lệch này thay vì sửa lặng lẽ, vì Phụ lục A và Chương 3 đang
> trích con số cũ.

---

## 2. Khung bảng — giữ nguyên năm cột, không đổi

Mọi bảng trong bộ tệp này dùng **đúng năm cột** sau, theo đúng thứ tự:

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| Tên cột trong CSDL | Kiểu dữ liệu PostgreSQL | Độ dài / độ rộng khai báo | Ràng buộc | Ý nghĩa nghiệp vụ |

## 3. Quy ước đọc cột **Field Length**

PostgreSQL không khai báo độ dài cho phần lớn kiểu, khác với ví dụ `Int(10)` hay
`Varchar2(30)` của Oracle. Quy ước dùng thống nhất:

| Kiểu | Ghi ở cột Field Length |
|---|---|
| `varchar(n)` | **n** — số ký tự tối đa |
| `integer` | **32** (bit) |
| `smallint` | **16** (bit) |
| `bigint` | **64** (bit) |
| `numeric(p,s)` | **p,s** |
| `text`, `uuid`, `timestamptz`, `boolean`, `jsonb`, `ARRAY`, `date` | **—** (không có độ dài khai báo) |

**Lưu ý về `text`:** kiểu `text` của PostgreSQL **không giới hạn độ dài** và
**không chậm hơn** `varchar(n)`. Việc lược đồ dùng `text` cho phần lớn cột chuỗi là
lựa chọn có chủ đích, không phải thiếu sót — giới hạn độ dài, nếu cần, được đặt ở
tầng kiểm định dữ liệu (Pydantic) chứ không ở tầng lưu trữ.

## 4. Quy ước đọc cột **Constraint**

| Ký hiệu | Nghĩa |
|---|---|
| `Primary key` | Khoá chính |
| `Primary key (kép)` | Khoá chính gồm nhiều cột |
| `Foreign key → bảng.cột` | Khoá ngoại đơn |
| `Foreign key kép → bảng(cột1, cột2)` | **Khoá ngoại ghép mang định danh tổ chức** — cơ chế làm việc trỏ chéo tổ chức bất khả thi ở tầng ràng buộc |
| `Unique` | Ràng buộc duy nhất |
| `Not null` | Bắt buộc có giá trị |
| `Null` | Cho phép rỗng |
| `Default <giá trị>` | Giá trị mặc định do CSDL đặt |
| `Check` | Có ràng buộc kiểm tra giá trị |

## 5. Bộ tệp — bảy nhóm mô-đun

| Tệp | Nhóm | Số bảng | Số cột |
|---|---|:--:|:--:|
| [DD_01_M1_DANH_TINH.md](DD_01_M1_DANH_TINH.md) | M1 — Danh tính & Truy cập | 7 | 56 |
| [DD_02_M2_TO_CHUC.md](DD_02_M2_TO_CHUC.md) | M2 — Tổ chức & Phân quyền | 9 | 97 |
| [DD_03_M3_KHO_MAU.md](DD_03_M3_KHO_MAU.md) | M3 — Kho dữ liệu mẫu | 6 | 112 |
| [DD_04_M4_DANH_MUC.md](DD_04_M4_DANH_MUC.md) | M4 — Danh mục & Registry | 11 | 75 |
| [DD_05_M5_HUAN_LUYEN.md](DD_05_M5_HUAN_LUYEN.md) | M5 — Huấn luyện & Mô hình | 3 | 33 |
| [DD_06_M6_DICH_VU.md](DD_06_M6_DICH_VU.md) | M6 — Dịch vụ tổ chức & Tích hợp | 11 | 134 |
| [DD_07_M7_PHAP_LY.md](DD_07_M7_PHAP_LY.md) | M7 — Pháp lý, Kiểm toán & Nền tảng | 10 | 115 |
| | **Tổng** | **57** | **622** |

*Sáu cột còn lại (628 − 622) thuộc bảng kỹ thuật `schema_migrations`, không nằm
trong mô hình nghiệp vụ.*

---

## 6. Ba điều cần biết trước khi đọc từ điển

**Thứ nhất — khoá ngoại ghép là cơ chế cách ly, không phải trang trí.** Quan hệ từ
mẫu tới lớp **không** đi qua một cột đơn mà qua cặp `(tenant_id, class_uid)`. Lý
do: một khoá ngoại đơn cho phép mẫu của tổ chức A trỏ tới lớp của tổ chức B — cơ
sở dữ liệu không phản đối, vì khoá vẫn tồn tại. Khoá ghép làm việc đó **bất khả
thi ở tầng ràng buộc**.

**Thứ hai — mọi token, mã một lần và khoá API lưu ở dạng BĂM.** Cột tên
`*_hash` không lưu giá trị gốc. Mất thì tạo mới, không khôi phục được.

**Thứ ba — cột dấu thời gian dạng `*_at` mang hai nghĩa khác nhau, đừng lẫn.**
`created_at` là *sự kiện đã xảy ra*; `deleted_at` / `revoked_at` / `withdrawn_at`
là **cờ trạng thái đội lốt dấu thời gian** — rỗng nghĩa là *chưa*, có giá trị nghĩa
là *rồi, vào lúc đó*. Đây là lý do lược đồ **không có** cột trạng thái ba giá trị
riêng: cột dấu thời gian là *thời điểm cờ boolean lật*, không phải một trạng thái
độc lập.

---

## 7. Nguồn và cách tái lập

```bash
# 1) Danh sách cột, kiểu, độ dài, nullable, default
docker exec voya_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAF'|' -c "
SELECT c.table_name, c.ordinal_position, c.column_name, c.data_type,
       COALESCE(c.character_maximum_length::text, c.numeric_precision::text, ''),
       c.is_nullable, COALESCE(c.column_default,'')
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_name=c.table_name AND t.table_schema=c.table_schema
WHERE c.table_schema='public' AND t.table_type='BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;"

# 2) Ràng buộc — dùng pg_constraint, KHÔNG dùng information_schema
docker exec voya_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAF'|' -c "
SELECT rel.relname, con.contype,
       (SELECT string_agg(a.attname, ',' ORDER BY x.ord)
          FROM unnest(con.conkey) WITH ORDINALITY AS x(attnum, ord)
          JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=x.attnum),
       COALESCE(fr.relname,''),
       COALESCE((SELECT string_agg(a2.attname, ',' ORDER BY y.ord)
          FROM unnest(con.confkey) WITH ORDINALITY AS y(attnum, ord)
          JOIN pg_attribute a2 ON a2.attrelid=con.confrelid AND a2.attnum=y.attnum),'')
FROM pg_constraint con
JOIN pg_class rel ON rel.oid=con.conrelid
JOIN pg_namespace ns ON ns.oid=rel.relnamespace
LEFT JOIN pg_class fr ON fr.oid=con.confrelid
WHERE ns.nspname='public' AND con.contype IN ('p','f','u','c')
ORDER BY rel.relname, con.contype;"
```

> **Vì sao bước 2 phải dùng `pg_constraint` chứ không dùng `information_schema`:**
> khung nhìn `constraint_column_usage` **không giữ được cặp cột** của khoá ngoại
> ghép — nó nhân chéo mọi cột nguồn với mọi cột đích, nên một khoá ghép hai cột cho
> ra bốn dòng sai. Đã gặp thật khi dựng bộ tệp này: `capture_sessions.class_uid`
> hiện ra như thể trỏ tới `classes.tenant_id`. Con số 22 khoá ngoại ghép **chỉ đúng**
> khi đọc bằng `pg_constraint`.
