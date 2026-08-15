# Backend — hiện trạng và việc cần làm

**Ngày khảo sát:** 2026-08-06
**Mốc chặn:** sách luận văn 13/08/2026 (7 ngày), bảo vệ 18–19/08/2026
**Phạm vi:** `backend/app/`, `backend/realtime_service/app/` (12.028 dòng, 18 router)

Mọi con số trong tài liệu này đến từ việc đọc mã hoặc truy vấn Postgres đang chạy,
không từ suy đoán. Phụ lục A ghi lại lệnh để kiểm chứng lại từng khẳng định.

---

## 0. Tóm tắt điều hành

Backend **không có lỗi chức năng nào đang chảy máu**. 710 test qua, 1 skip; toàn bộ
mã nguồn chỉ còn **1 dấu `TODO`**. Vấn đề không nằm ở chỗ hỏng, mà ở chỗ **luận điểm
trung tâm của luận văn — cô lập tenant hai mặt phẳng — hiện chưa có gì trong hệ thống
chống lưng cho nó.** Có `tenant_id` trên 12 bảng và khoá ngoại đầy đủ, nhưng:

- không có một dòng nào phát `SET LOCAL` / `current_setting` trong toàn backend;
- không bảng nào bật Row Level Security;
- và role ứng dụng là **superuser + BYPASSRLS**, nên kể cả bật cũng vô hiệu.

Nói thẳng: hôm nay `tenant_id` là **một cột metadata**, không phải một **ranh giới an
ninh**. Bảy ngày tới quyết định nó thành cái nào.

Ưu tiên theo đúng thứ tự nên làm:

| Mã | Việc | Công | Rủi ro | Vì sao ở vị trí này |
|---|---|---|---|---|
| **A1** | `tenant_id` vào SOT (2 CSV + cột INSERT) | 1–2h | rất thấp | Rẻ nhất, chặn đường tái dựng-từ-CSV làm mất phân vùng |
| **A2** | Role ứng dụng không-superuser | 2–3h | trung bình | **Không có nó thì A3 là bằng chứng giả** |
| **A3** | RLS trên `samples`/`classes`/`raw_uploads` | 2–3 ngày | trung bình | Thứ được chấm |
| **A4** | Phân vùng lưu trữ theo tenant (chỉ phía ghi) | 1 ngày | thấp | Mặt phẳng thứ hai của luận điểm |
| **B1** | `torch.load(weights_only=False)` — 5 điểm gọi | 1h | thấp | Thực thi mã tuỳ ý từ file checkpoint |
| **B2** | `/realtime/predict` không auth, không rate limit | 1h | thấp | API suy luận mở |
| **B3** | Rate limit chỉ phủ `auth.py` | 2h | thấp | Mọi đường ghi khác không giới hạn |

---

## PHẦN A — Chặn luận điểm luận văn

### A1. `tenant_id` chưa có trong nguồn sự thật

**Bằng chứng**

`dataset/samples.csv` có 32 cột, `dataset/labels.csv` có 19 cột. **Không cột nào là
`tenant_id`.** (3.860 và 63 dòng dữ liệu.)

`SQL_UPSERT_SAMPLE` ([metadata_db.py:936-953](../../backend/app/storage/metadata_db.py#L936-L953))
liệt kê đúng 32 cột và `tenant_id` không nằm trong đó — nên mệnh đề
`ON CONFLICT DO UPDATE` cũng không đụng tới nó. Mọi hàng mới rơi vào `DEFAULT 'default'`.

**Tác động thật — không phải chuyện tuyên bố sai**

Đường nguy hiểm nằm ở [db.py:96-107](../../backend/app/db.py#L96-L107): khi
`samples.deleted_at` biến mất, `init_db()` gọi `drop_all_tables()` rồi **dựng lại toàn
bộ từ CSV**. Đường này có thật và đã từng kích hoạt.

Ngày nào có tenant thứ hai, một lần kích hoạt là **mọi hàng của tenant B sống lại
thành `default`**. Không có lỗi, không có cảnh báo, không có cách phát hiện sau đó —
CSV không giữ thông tin để khôi phục. Đây là mất phân vùng dữ liệu im lặng, hạng nặng
nhất trong các lỗi multi-tenant.

**Cách sửa**

1. Thêm cột `tenant_id` vào header cả hai CSV, backfill hằng `'default'` cho toàn bộ
   3.860 + 63 dòng. Hôm nay giá trị đúng là một hằng số — **đây là lý do duy nhất việc
   này rẻ, và cửa sổ đó đóng lại ngay khi có tenant thứ hai.**
2. Thêm `tenant_id` vào danh sách cột của `SQL_UPSERT_SAMPLE` và mệnh đề upsert của
   `classes`. Dùng `COALESCE(EXCLUDED.tenant_id, samples.tenant_id)` theo đúng khuôn
   `auth_user_id` đang dùng ([metadata_db.py:961](../../backend/app/storage/metadata_db.py#L961)),
   để một CSV mirror thiếu cột không xoá tenant của hàng đã có.
3. Dùng `ensure_samples_column()` như đã làm cho `auth_user_id`
   ([db.py:63-72](../../backend/app/db.py#L63-L72)) — migration idempotent, chạy trước
   sync mỗi lần boot.

**Kiểm chứng:** một test khẳng định header CSV chứa `tenant_id`; một test dựng lại DB
từ CSV có hàng tenant B và khẳng định nó vẫn là B.

---

### A2. Role ứng dụng là superuser — RLS sẽ bị bỏ qua hoàn toàn ⚠️

**Đây là phát hiện quan trọng nhất của đợt khảo sát.**

```
rolname | rolsuper | rolbypassrls
admin   |    t     |      t
```

`DATABASE_URL` nối bằng `admin`, và role này vừa là **superuser** vừa có
**BYPASSRLS**. Trong PostgreSQL:

> Superusers and roles with the BYPASSRLS attribute always bypass the row security
> system when accessing a table.

`ALTER TABLE ... FORCE ROW LEVEL SECURITY` **không giải quyết chuyện này**. `FORCE`
chỉ gỡ miễn trừ của **chủ bảng**; miễn trừ của superuser không đụng tới được.

**Vì sao đây là bẫy chứ không chỉ là thiếu sót**

Nếu triển khai RLS mà không sửa role trước, kết quả là:

- `pg_policies` hiện đủ policy
- `pg_tables.rowsecurity = true` trên cả 3 bảng
- Mọi truy vấn vẫn trả về **toàn bộ dữ liệu của mọi tenant**

Tức là mọi cách kiểm tra "nhìn vào cấu hình" đều báo xanh, còn hành vi thật thì bằng
không. Luận văn sẽ tuyên bố có cô lập, demo chạy đẹp, và một câu
`SELECT current_setting('is_superuser')` tại buổi bảo vệ là đủ để lật. **Trạng thái
này tệ hơn không làm RLS**, vì nó biến một khoảng trống đã biết thành một khẳng định sai.

**Cách sửa**

```sql
CREATE ROLE voya_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
  PASSWORD '...';
GRANT USAGE ON SCHEMA public TO voya_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO voya_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voya_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO voya_app;
```

rồi đổi `DATABASE_URL` sang `voya_app`.

**Rủi ro và cách kiểm soát.** Thiếu một `GRANT` thì một đường truy vấn chết lúc chạy,
không phải lúc khởi động — nên không được đổi rồi hy vọng. Ba lớp bảo vệ:

1. Chạy trọn bộ 710 test với `DATABASE_URL` trỏ role mới **trước** khi đổi thật.
2. Thêm một khẳng định lúc boot: nếu
   `SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user`
   trả về `true` **và** RLS đang bật, thì ghi log mức ERROR. Không cho cấu hình
   "policy có mà vô dụng" tồn tại âm thầm.
3. Rollback là đổi lại một dòng `DATABASE_URL` — role cũ vẫn còn nguyên.

`ensure_tables()` chạy DDL (`ALTER TABLE`, `CREATE INDEX`, thêm khoá ngoại). Phải quyết
định: hoặc giữ một role migration riêng có quyền DDL, hoặc cấp thêm quyền cho
`voya_app`. **Khuyến nghị tách**, vì role ứng dụng có `ALTER TABLE` thì nó tự tắt được
RLS của chính mình — mất hết ý nghĩa.

---

### A3. RLS — thứ thực sự được chấm

**Hiện trạng:** `rowsecurity = f` trên `samples`, `classes`, `raw_uploads`, `users`.
Grep toàn `backend/` cho `current_setting` / `SET LOCAL` / `set_config`: **0 kết quả.**
Không có bất kỳ nơi nào mang ngữ cảnh tenant trong một request.

Nghĩa là A3 **không phải** "viết mấy câu `CREATE POLICY`". Nó gồm bốn phần, và phần
thứ ba là phần bị bỏ sót trong mọi ước lượng lạc quan:

**(a) Ngữ cảnh tenant trong request.** Lấy tenant từ user đã xác thực, đặt vào một
`ContextVar`. Nơi tự nhiên là một middleware trong [main.py](../../backend/app/main.py)
sau lớp xác thực.

**(b) Truyền xuống tầng DB.** `_cursor()` và `_fetch_all()`
([metadata_db.py:14-34](../../backend/app/storage/metadata_db.py#L14-L34),
[1255-1267](../../backend/app/storage/metadata_db.py#L1255-L1267)) phát
`SET LOCAL app.tenant_id = ...` ở đầu mỗi transaction.

> **Bắt buộc `SET LOCAL`, không được dùng `SET`.** Kết nối lấy từ
> `ThreadedConnectionPool` dùng chung
> ([postgres_connection.py:104-158](../../backend/app/storage/postgres_connection.py#L104-L158)).
> `SET` bám lại trên connection và rò sang request kế tiếp — có thể là tenant khác.
> `SET LOCAL` chết theo commit/rollback, nên an toàn với pool. Đây là lỗi kinh điển
> của RLS + connection pooling và nó không tạo ra lỗi nào nhìn thấy được, chỉ tạo ra
> dữ liệu sai cho đúng một người dùng xui xẻo.

**(c) Đường "hệ thống" cho thứ không có request.** Celery worker,
`sync_missing_data_on_startup()`, CSV mirror, `bootstrap_admin_user()` — không cái nào
có request để lấy tenant. Nếu bỏ qua phần này:
`_existing_keys()` ([db.py:123-132](../../backend/app/db.py#L123-L132)) chạy dưới
policy với GUC rỗng → thấy 0 hàng → kết luận DB rỗng → **re-upsert 3.860 hàng mỗi lần
boot**. Không mất dữ liệu (`ON CONFLICT DO UPDATE` giữ `deleted_at`), nhưng là một
quả mìn hiệu năng và một nguồn hoang mang khi đọc log.

Phần này **phải thiết kế trước**, không phải phát hiện lúc chạy. Cách sạch: một
context manager `system_scope()` đặt một GUC riêng mà policy chấp nhận, dùng có chủ ý
tại đúng các điểm vào nền tảng, và có test khẳng định không router nào gọi nó.

**(d) Bộ chứng minh.** **Một tenant thì không chứng minh được cô lập.** Hiện `tenants`
chỉ có `default`, và toàn bộ 3.860 samples / 63 classes / 9 users đều thuộc nó. Phải
seed một tenant B có vài hàng thật, rồi chứng minh:

- Tenant A `SELECT` → không thấy hàng của B
- Tenant A `UPDATE ... WHERE` trúng hàng của B → 0 hàng bị đổi
- Tenant A `DELETE` trúng hàng của B → 0 hàng bị xoá
- Kết nối không có GUC → 0 hàng (fail closed, không fail open)

30 phút, nhưng nếu không có thì bước "đo và chứng minh" không có gì để đo.

**Lý lẽ phụ ủng hộ RLS.** `delete_sample()`, `delete_samples_by_class()`,
`update_sample_gdrive_url()` ([metadata_db.py:1156-1168](../../backend/app/storage/metadata_db.py#L1156-L1168))
đều **không lọc tenant**. RLS vá cả nhóm này một lượt mà không phải sửa từng hàm — và
quan trọng hơn, vá cả những hàm sẽ được viết sau này mà tác giả quên lọc.

**Phạm vi:** đúng 3 bảng — `samples`, `classes`, `raw_uploads`. Không làm cả 12.
Ba bảng có bằng chứng thuyết phục hơn mười hai bảng khai suông.

---

### A4. Phân vùng lưu trữ theo tenant

Mặt phẳng thứ hai của luận điểm: cô lập không chỉ ở hàng DB mà ở cả byte trên đĩa.

**Chỉ phía ghi.** Chốt layout, dữ liệu mới đi đúng đường, **8.784 file `.npz` hiện có
nằm nguyên chỗ** (nhiều hơn 3.860 sample vì mỗi sample sinh thêm bản augment). Hai bố
cục cùng sống — repo đã làm đúng kiểu này với kho raw contract v3, nên có tiền lệ nội
bộ để viện dẫn trong sách thay vì phải biện minh từ đầu.

Quy mô đó cũng là lý do **không** di dời file cũ: 8.784 lần đổi chỗ file là một thao
tác không nguyên tử, đứt giữa chừng thì nửa dataset không tìm được đường dẫn, và nó
không đóng góp gì cho luận điểm — thứ được chấm là dữ liệu **mới** có đi đúng phân
vùng hay không.

Đọc đường dẫn phải thử layout mới trước, rơi về layout cũ sau; và **không được** suy ra
tenant từ đường dẫn cũ — hàng DB là nguồn sự thật cho quyền sở hữu, đường dẫn chỉ là
nơi cất byte.

---

## PHẦN B — An ninh

### B1. `torch.load(weights_only=False)` — 5 điểm gọi

**Bằng chứng**

| File | Dòng |
|---|---|
| `backend/app/routers/training.py` | 96, 1054, 1216, 1402 |
| `backend/app/training_tasks.py` | 502 |

Tất cả đều `weights_only=False` **không điều kiện**. `torch.load` với
`weights_only=False` unpickle — tức là **thực thi mã tuỳ ý chứa trong file checkpoint**.

Đáng ghi nhận: `realtime_service` đã làm đúng
([model_loader.py:72-95](../../backend/realtime_service/app/model_loader.py#L72-L95)) —
thử `weights_only=True` trước, chỉ rơi về `False` khi không biểu diễn được, và có ghi
log cảnh báo. Backend chưa được nâng theo.

**Mức độ.** Đây không phải lỗ hổng từ xa: đường tải checkpoint nằm sau
`require_admin`, và checkpoint do chính hệ thống sinh ra. Rủi ro thật là **chuỗi cung
ứng** (MITRE ATLAS AML.T0010) — một checkpoint tải từ ngoài, hoặc một thư mục
checkpoint bị ghi bởi tiến trình khác, trở thành đường thực thi mã.

**Cách sửa (1 giờ).** Trước mỗi `torch.load`, kiểm cứng rằng đường dẫn đã giải quyết
nằm **bên trong** thư mục checkpoint đã cấu hình — dùng so sánh sau khi `resolve()`,
không dùng so khớp chuỗi (`..` đi xuyên qua). Và mượn nguyên khuôn thử-`True`-trước của
`model_loader.py` thay vì viết lại.

---

### B2. `/realtime/predict` không xác thực, không giới hạn tần suất

`backend/app/routers/realtime_proxy.py` có 3 endpoint (`GET /models`, `GET /health`,
`POST /predict`) và **không endpoint nào có `Depends` xác thực**. Router này được mount
ở cả `/` lẫn `/api/v1` ([main.py:240, 259](../../backend/app/main.py#L240)).

**Đính chính một khuyến nghị trước đó của tôi.** Tôi từng đề xuất "trả top-k thay vì
full softmax". Khảo sát cho thấy **việc này đã đúng sẵn**: `predict()`
([predict.py:150-160](../../backend/realtime_service/app/predict.py#L150-L160)) chỉ trả
`label`, `confidence`, `label_key` — top-1. Vector xác suất đầy đủ không rời khỏi tiến
trình. Khuyến nghị cũ dựa trên giả định chưa kiểm; bỏ nó khỏi danh sách việc.

Phần còn lại vẫn đúng: một API suy luận mở, không giới hạn, cho phép truy vấn khối
lượng lớn có hệ thống — bề mặt của model extraction (AML.T0024). Với top-1 + confidence
thì tốc độ trích xuất chậm hơn nhiều so với full softmax, nên **mức độ là trung bình,
không phải cao**.

**Cách sửa (1 giờ).** Rate limit theo IP trên `POST /predict`, tái dùng hạ tầng đã có
trong [rate_limit.py](../../backend/app/rate_limit.py) (522 dòng, đã có 2 namespace
Redis, đã xử lý đúng chuyện client không tự chọn được IP tính hạn mức).

---

### B3. Rate limit mới chỉ phủ `auth.py`

Grep `rate_limit|RateLimit|limiter` trong `backend/app/routers/`: chỉ khớp
**`auth.py`** (và một `.pyc` cũ của `trash.py` đã bị xoá — rác biên dịch, nên dọn).

Nghĩa là `upload.py` (`POST /video`, `/video/process`, `/camera`), `training.py`,
`realtime_proxy.py`, `classes.py` **không có giới hạn tần suất nào**. `upload.py` là
đường đắt nhất trong hệ thống: mỗi request ghi đĩa, chạy MediaPipe, và đẩy một task
Celery.

**Cách sửa (2 giờ).** Áp hạn mức theo người dùng lên các đường ghi. Hạn mức rộng tay —
mục tiêu là chặn vòng lặp chạy loạn và lạm dụng thô, không phải làm phiền người thu
dữ liệu thật.

---

### B4. Router mount thiếu guard và router chết (thấp)

`jobs.py` (2 endpoint `GET`) và `inference.py` (`GET /inference/classes`) được mount
nhưng **không tham chiếu xác thực nào**. Cả hai chỉ đọc metadata không nhạy cảm; ghi
nhận để rà lại, không phải việc gấp.

`experiments.py` và `dataset_exporter.py` được **import** ở
[main.py:21-22](../../backend/app/main.py#L21-L22) nhưng **không bao giờ được
`include_router`**. Mã chết — hoặc mount có chủ đích, hoặc xoá. Import treo như vậy là
loại nhầm lẫn khiến người sau tưởng endpoint đang chạy.

---

## PHẦN C — Không đụng vào trước 13/08

Đã có tài liệu đầy đủ. Viết vào sách như chương Thiết kế và Future Work thì được, code
thì không:

| Việc | Tài liệu |
|---|---|
| Community Data Commons | [COMMUNITY_DATA_COMMONS.md](../01-architecture/COMMUNITY_DATA_COMMONS.md) |
| Hệ thống consent | *(nằm trong tài liệu trên)* |
| Đổi tên bảng `community_*` → catalog | [REGISTRY_ARCHITECTURE.md](../01-architecture/REGISTRY_ARCHITECTURE.md) §2 |
| Refresh token reuse detection | [AUTH_TOKEN_LIFECYCLE.md](../03-security/AUTH_TOKEN_LIFECYCLE.md) |
| Lật `hands126_v2` | [KNOWN_ISSUES.md](../10-issues/KNOWN_ISSUES.md) |

Riêng `hands126_v2`: **kết quả đo đã có và là kết quả âm** — v2 tệ hơn trung bình và
nhiễu gấp 4,5 lần, dấu của hiệu không nhất quán. Quyết định là **không lật**. Đây là
một kết quả nghiên cứu hợp lệ, nên viết vào sách, không nên giấu.

---

## PHẦN D — Đã xong (đừng làm lại)

- **12 khoá ngoại `tenant_id`** — 12 thiếu → 0. `TENANT_SCOPED_TABLES` là nguồn duy
  nhất cho cả migration lẫn hàm rà soát; 3 lần thử phá đều bị từ chối, dữ liệu nguyên vẹn.
- **Đổi tên miền System Catalog** — hàm và tài liệu đã đổi; tên bảng vật lý giữ nguyên
  có chủ đích và có ghi chú cấm "sửa ngược".
- **Bản sao z-normalization** — cả hai bản đã có dispatch phiên bản và test ghim; v1
  vẫn là mặc định.
- **`--features_root` bị bỏ qua** — lỗi làm vô hiệu mọi thí nghiệm tiền xử lý. Đã sửa
  + 5 test hồi quy.
- **14 raw upload PENDING** — đã xoá ở cả 5 nơi, đã kiểm chéo bằng phương pháp độc lập,
  giữ lại biên bản xoá 18 KB dạng văn bản. **Bỏ mục này khỏi mọi danh sách việc.**
- **Test suite** — 710 qua, 1 skip, ~13 phút, chạy trong container trên compose network.

---

## Phụ lục A — Kiểm chứng lại

```bash
# A2: role co phai superuser khong
docker exec voya_postgres psql -U admin -d signdb -tAc \
  "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='admin';"

# A3: RLS da bat chua + so tenant thuc te
docker exec voya_postgres psql -U admin -d signdb -tAc \
  "SELECT tablename, rowsecurity FROM pg_tables
   WHERE schemaname='public' AND tablename IN ('samples','classes','raw_uploads');"
docker exec voya_postgres psql -U admin -d signdb -tAc "SELECT tenant_id FROM tenants;"

# A3(a): khong co ngu canh tenant o dau ca — phai ra 0 ket qua
grep -rn "current_setting\|SET LOCAL\|set_config" backend/ --include=*.py

# A1: SOT thieu cot
head -1 dataset/samples.csv | tr ',' '\n' | grep -c tenant_id   # -> 0

# B1: cac diem goi torch.load khong an toan
grep -rn "weights_only=False" backend/app --include=*.py

# B3: rate limit phu den dau
grep -rln "rate_limit" backend/app/routers/
```

---

## Phụ lục B — Cái tài liệu này *không* khẳng định

- Không khẳng định hệ thống đang bị tấn công hay đã bị xâm nhập. Mọi mục Phần B là bề
  mặt tấn công, không phải sự cố.
- Không khẳng định RLS là cách cô lập tenant duy nhất đúng. Nó là cách **kiểm chứng
  được ở tầng DB**, phù hợp để bảo vệ trước hội đồng — đó là tiêu chí chọn ở đây.
- Không ước lượng công sức cho Phần C. Những việc đó chưa được phân rã tới mức ước
  lượng có nghĩa.
- Ước lượng công sức ở Phần A giả định **một người làm, không bị ngắt quãng, và A2
  xong trước A3**. Nếu A2 bị bỏ qua thì A3 vẫn "xong" đúng hạn nhưng không chứng minh
  được gì.
