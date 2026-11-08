# Review mã backend — 2026-08-08

Mỗi mục: **lỗi là gì → vì sao nó là lỗi → đã xử lý thế nào**. Không mục nào là
suy đoán; mỗi mục kèm bằng chứng đo được hoặc một test đã đỏ trước khi xanh.

Chia ba phần, và phần A đứng trước vì đó là mã tôi vừa viết:

- **A.** Lỗi trong mã tôi viết trong hai phiên gần nhất — 10 mục
- **B.** Lỗi có sẵn, phát hiện khi review — 6 mục
- **C.** Lộn xộn về cấu trúc — 5 mục, kèm số đo

---

## A. Lỗi trong mã tôi viết

### A1 — Nhật ký kiểm toán không trả lời được câu hỏi chính của nó

**Lỗi.** `audit.hash_ip(request, salt=actor_id)` băm địa chỉ IP kèm muối là mã
người thực hiện.

**Vì sao là lỗi.** Cùng một địa chỉ IP dưới ba tài khoản cho ra ba bản băm khác
nhau. Câu hỏi đắt giá nhất mà một nhật ký kiểm toán phải trả lời — *"có phải
cùng một nơi vừa thử ba tài khoản quản trị không"* — trở thành không trả lời
được. Tôi chép mẫu này từ `routers/auth.py` mà không xét rằng hai chỗ hỏi hai
câu khác nhau: ở đó, bằng chứng đồng ý là của từng người và việc **không** đối
chiếu được giữa các tài khoản là tính năng.

**Xử lý.** Bỏ muối theo người thực hiện. Bản băm ổn định theo IP.
`backend/app/audit.py`.

### A2 — Bản băm IP đảo ngược được

**Lỗi.** Cùng hàm trên dùng `sha256(ip)` trần.

**Vì sao là lỗi.** Không gian IPv4 có 4 tỉ giá trị; duyệt cạn hết trong vài
giây. Bản băm không che gì cả, chỉ tạo cảm giác đã che — và cảm giác đó nguy
hiểm hơn việc lưu thẳng địa chỉ IP, vì nó khiến người ta thôi cảnh giác.

**Xử lý.** HMAC-SHA256 khoá bằng pepper ngoài cơ sở dữ liệu, tách miền bằng
tiền tố `audit-ip\0`. Không có pepper thì trả `None` — cùng lập luận đã viết
cho mã OTP trong `app/tokens.py`.

### A3 — Hạn ngạch "mỗi ngày" reset lúc 7 giờ sáng

**Lỗi.** `trial.py` tính khoá theo ngày và vị trí bit theo giờ UTC.

**Vì sao là lỗi.** Người dùng ở Việt Nam. Ranh giới ngày UTC là **07:00 giờ
Việt Nam**: ai dùng lúc 6 giờ sáng bị chặn rồi được mở lại một tiếng sau, còn
câu "quay lại vào ngày mai" trong thông báo là sai.

**Xử lý.** Thêm `TRIAL_RESET_UTC_OFFSET_HOURS` mặc định `7`. Cả khoá theo ngày
lẫn vị trí bit đều tính theo giờ địa phương — phải cùng hệ quy chiếu, nếu không
hai phút cách nhau một ngày sẽ đập vào cùng một bit. Dùng độ lệch cố định chứ
không phải tên vùng vì `zoneinfo` cần gói `tzdata` không có trong image
`python:slim`, và Việt Nam không có giờ mùa hè.

**Hệ quả lên test.** `test_a_new_day_resets` chuyển sang đỏ. Nó dùng
23:59 → 00:00 **UTC** làm ranh giới, tức là chính nó đang khẳng định hành vi
vừa được sửa đi. Ý định của test vẫn đúng ("sang ngày là hạn ngạch mới"), chỉ
hai mốc thời gian là không còn diễn đạt được ý đó — nên hai mốc giờ được TÍNH
từ độ lệch cấu hình thay vì viết cứng. Thêm hai test mới ghim chiều ngược lại:
`test_the_day_boundary_is_local_midnight_not_utc` đỏ ngay nếu ai đó bỏ độ lệch
đi, và `test_the_reset_time_carries_its_timezone` bắt trường hợp `resets_at`
mất múi giờ (giao diện sẽ hiểu nhầm thành giờ máy khách và đồng hồ đếm ngược
lệch đúng 7 tiếng).

### A4 — Cổng gác dựng lại dataclass theo thứ tự tham số

**Lỗi.** `access_gate` sửa kết quả của `peek()` bằng
`grant.__class__(False, grant.minutes_used, grant.minutes_limit, ...)`.

**Vì sao là lỗi.** Đổi thứ tự trường trong `TrialState` sẽ khiến câu này lặng
lẽ gán nhầm giá trị sang trường khác, không lỗi, không cảnh báo. Đây là cổng
gác truy cập. Nguyên nhân sâu hơn: `peek()` trả `allowed=True` cho người chưa
có phiếu, nên bất biến phải được vá ở nơi gọi thay vì ở nơi định nghĩa.

**Xử lý.** Thêm `TrialState.requiring_grant()` dùng `dataclasses.replace` theo
TÊN trường, đặt cạnh định nghĩa kiểu. Nơi gọi còn một dòng.

### A5 — Cảnh báo giả ở mỗi lần khởi động

**Lỗi.** Guard xoá bảng chết viết
`IF to_regclass('public.user_profiles') IS NOT NULL AND (SELECT count(*) FROM user_profiles) = 0`.

**Vì sao là lỗi.** PL/pgSQL **lập kế hoạch cả biểu thức điều kiện trước khi
chạy**, nên câu `SELECT ... FROM user_profiles` vẫn bị phân tích ngay cả khi vế
trái đã đủ kết luận. Sau khi bảng bị xoá, mỗi lần khởi động đẻ một cảnh báo
`relation does not exist`. Vô hại, nhưng đúng loại báo động giả mà rồi người ta
tắt đi — và cùng lúc tắt luôn những cảnh báo thật.

**Xử lý.** Hai `IF` lồng nhau, câu đếm chạy qua `EXECUTE` nên chỉ được lập kế
hoạch khi thực sự tới lượt.

### A6 — Sáu bảng mới ra đời không có khoá ngoại tenant

**Lỗi.** Vòng lặp gắn khoá ngoại `tenant_id` nằm giữa `MIGRATION_STATEMENTS`,
còn `CREATE TABLE` của các bảng v3 nằm cuối danh sách.

**Vì sao là lỗi.** Lượt chạy đầu tiên đi qua chỗ các bảng chưa tồn tại, bỏ qua
đúng như thiết kế, và sáu bảng mới ra đời không có khoá ngoại. Trên máy đang
chạy, lỗi **tự lành ở lần khởi động thứ hai** — nghĩa là nó sẽ không bao giờ lộ
ra trong lúc phát triển và chỉ hiện hình ở một lần cài mới.

**Xử lý.** Tách vòng lặp thành hằng số `TENANT_FK_LOOP_SQL`, phát hai lần —
cùng một hằng số, không phải hai bản chép. `schema_debt()` là thứ bắt được lỗi
này ngay sau lượt chạy đầu.

### A7 — Dọn tenant tạm sẽ thất bại

**Lỗi.** Thêm sáu bảng vào `TENANT_SCOPED_TABLES` khiến chúng có khoá ngoại
`ON DELETE RESTRICT` tới `tenants`, nhưng `_TENANT_PURGE_ORDER` trong
`conftest.py` không được cập nhật.

**Vì sao là lỗi.** Chưa hỏng ngay, vì chưa test nào tạo phiên thu cho tenant
tạm. Nó sẽ hỏng lần đầu có ai làm thế, và triệu chứng là một tenant rác nằm lại
trong danh sách của người vận hành.

**Xử lý.** Chèn sáu bảng vào **đúng vị trí phụ thuộc** chứ không nối vào cuối —
`capture_sessions` tham chiếu `classes` và `signers` nên phải xoá trước hai
bảng đó. Thêm `test_tenant_purge_order_covers_every_tenant_table` để hai danh
sách không trôi ra khỏi nhau.

### A8 — Backfill bịa ra người ký

**Lỗi.** Câu dựng `capture_sessions` lấy `array_agg(signer_id)[1]`, tức là giá
trị đầu tiên bắt gặp.

**Vì sao là lỗi.** 15 nhóm `(class, session_id)` chứa **nhiều người ký khác
nhau**. Ghi một trong số họ vào `capture_sessions.signer_id` tạo ra khẳng định
sai: "phiên này do S010 thực hiện" trong khi thực tế có hai người. Đây đúng
kiểu bịa mà tôi vừa từ chối ở ba chỗ khác trong cùng migration.

**Xử lý.** Chỉ điền khi cả nhóm đồng nhất, còn lại để NULL. Kết quả:
**150/250 phiên** dám khẳng định người ký. NULL đọc được là "không đồng nhất";
một khẳng định sai thì không đọc ra được gì.

### A9 — Giải pickle không qua bộ nạp đã kiểm

**Lỗi.** `_record_output_contract` gọi `torch.load(path, weights_only=False)`
trực tiếp.

**Vì sao là lỗi.** Giải pickle là **thực thi mã** trong file. Kho mã này có sẵn
`app/checkpoint_io.py` tồn tại đúng vì lý do đó: nó kiểm đường dẫn nằm trong
các gốc cho phép, chặn symlink trỏ ra ngoài, rồi mới thử chế độ an toàn trước.

**Xử lý.** Gọi `checkpoint_io.load_checkpoint`.

### A10 — Test của tôi để lại rác và xanh sai

**Lỗi.** `test_real_email_identities.py` bản đầu không có fixture
`ensure_tables()` và ghi bằng `db._execute` thay vì con trỏ rollback.

**Vì sao là lỗi.** Chạy trên cơ sở dữ liệu chưa có ràng buộc, câu `INSERT` chữ
hoa **thành công**, và hàng `MAINHATMINH1004@GMAIL.COM` nằm lại. Test khẳng
định "cơ sở dữ liệu phải từ chối" mà lúc nó không từ chối thì lại để lại hậu
quả — đó là test tự phá dữ liệu.

**Xử lý.** Fixture `ensure_tables()` ở cấp module, và mọi test cố tình ghi đều
dùng `rollback_cursor`.

---

## B. Lỗi có sẵn, phát hiện khi review

### B1 — `users` yếu hơn `tenant_invitations` ở cùng một bất biến

**Lỗi.** `create_user` hạ chữ thường địa chỉ email, nhưng **cơ sở dữ liệu không
ép**. `tenant_invitations` thì có `CHECK (email = lower(email))`.

**Vì sao là lỗi.** `create_user` là MỘT đường ghi. Đồng bộ CSV, công cụ quản
trị, và mọi endpoint viết sau đều ghi thẳng vào `users`. Nếu một hàng lọt vào
với chữ hoa thì `uq_users_tenant_email` (đánh trên cột thô) coi `A@x.com` và
`a@x.com` là hai địa chỉ khác nhau, và `_fetch_user_by_login` tra bằng
`lower(email) = ...` kèm `LIMIT 1` **không có ORDER BY** — hàng nào được trả về
là do Postgres quyết định. Mật khẩu và quyền của một người khi đó phụ thuộc vào
một thứ không xác định.

**Xử lý.** Thêm `users_email_lower` (v3.12b). Đã đo trước: 10/10 tài khoản hiện
có đều chữ thường, nên ràng buộc áp được ngay. Test
`test_co_so_du_lieu_tu_tu_choi_dia_chi_viet_hoa` **đỏ trước khi xanh**, và lúc
đỏ nó tạo ra đúng hai tài khoản cho một người — bằng chứng lỗi là thật.

### B2 — Cổng bảo mật báo động giả vì đọc cả văn xuôi

**Lỗi.** `test_only_the_loader_may_pass_weights_only_false` grep chuỗi
`weights_only=False` trong toàn bộ nội dung file `app/**.py`.

**Vì sao là lỗi.** Tìm-chuỗi không phân biệt được mã với chú thích. Nó bắt phải
đoạn docstring đang **giải thích chính rủi ro đó**. Đồng thời nó bỏ lọt
`weights_only = False` viết có dấu cách. Sai cả hai chiều.

**Xử lý.** Kiểm bằng AST: duyệt `ast.Call`, tìm keyword `weights_only` có giá
trị hằng `False`. Chặt hơn và không báo giả.

### B3 — Hai hệ thống migration, một cái chết

**Lỗi.** `backend/migrations/` có 8 file `.sql` đánh số mà không mã nào chạy.
Kiểm bằng `grep -rn "migrations/" backend/app/`: tham chiếu duy nhất là một
dòng chú thích.

**Vì sao là lỗi.** Chúng **trông như** một hệ thống migration đang hoạt động.
Ai đó chạy `psql -f 001_create_production_schema.sql` lên cơ sở dữ liệu hiện
tại sẽ để lại một lược đồ nửa vời.

**Xử lý.** `backend/migrations/README.md` nói rõ đừng chạy, nguồn sự thật ở
đâu, và cách kiểm lược đồ. Giữ file lại vì chúng ghi lược đồ từng có; xoá thì
git vẫn giữ nhưng ít ai nghĩ tới việc đi tìm.

### B4 — Bộ test ghi vào cơ sở dữ liệu sản xuất

**Lỗi.** `DATABASE_URL` của bộ test trỏ thẳng vào `signdb`.

**Vì sao là lỗi.** Ba lần dữ liệu test rò vào dữ liệu thật, và ba lần vá
teardown đều không chạm tới gốc: bộ test đang ghi vào cơ sở dữ liệu thật.

**Xử lý.** Nhân bản `signdb` sang `signdb_test` (~10 giây) và trỏ bộ test vào
bản sao. Vẫn là Postgres thật với đúng dữ liệu thật nên RLS và chỉ mục duy nhất
bộ phận vẫn chứng minh được. Kèm hai bẫy đã trả giá:

- **`GRANT` không đi theo `pg_dump`.** Thiếu nó, mọi test chết vì
  `permission denied`, trông hệt như lỗi mã.
- **`DATABASE_URL` phải là `voya_app`, không được là `admin`.** `admin` là
  superuser **có BYPASSRLS**, nên mọi test cô lập tenant tất yếu đỏ. Tôi đã tự
  mắc: 12 đỏ, trong đó 9 là do chạy sai vai chứ không phải hồi quy.

### B5 — "Migration đã chạy" ≠ "ràng buộc đang bảo vệ"

**Lỗi.** `_run_ddl` hạ mọi thất bại DDL xuống một dòng log cảnh báo.

**Vì sao là lỗi.** Đó là đánh đổi ĐÚNG cho đường khởi động — một câu hỏng không
được làm chết cả stack. Nhưng hệ quả là một ràng buộc không áp được (vì còn
hàng vi phạm) sẽ vắng mặt trong im lặng, và hệ thống trông khoẻ mạnh.

**Xử lý.** `missing_integrity_constraints()` và `schema_debt()` báo cáo trạng
thái THẬT của ràng buộc, đọc từ `pg_constraint` chứ không từ việc migration có
chạy hay không. Ba nơi — migration, kiểm toán, test — cùng đọc một hằng số
`INTEGRITY_FK_SPECS` nên không trôi ra khỏi nhau.

### B7 — Ba test chỉ xanh ở lần chạy đầu tiên

**Lỗi.** Fixture `client` trong `test_trial_and_sudo.py` dựng `TestClient` mà
không đặt IP riêng cho mỗi lượt gọi, nên mọi request đến từ `127.0.0.1`.

**Vì sao là lỗi.** Thùng đếm rate-limit nằm trong Redis và **sống qua các lần
chạy suite**. Sau vài lượt chạy, 271 khoá `ratelimit:*` tích lại khiến
`POST /trial/start` trả 429, và ba test ở `TestTrialEndpoints` chuyển sang đỏ.
Triệu chứng — "cấp phiếu không idempotent" — trông hệt như một lỗi mã, và tôi
đã suýt đi tìm hồi quy trong `access_gate` trước khi đo. Bằng chứng phân định:
xoá 278 khoá `ratelimit:*` + `act:rate:*` rồi chạy lại thì 6/6 xanh ngay.

Đây là loại đỏ tốn nhiều giờ nhất, vì nó phụ thuộc vào việc trước đó ai đã chạy
gì. Một test chỉ đúng nếu nó cho cùng kết quả ở lần thứ nhất và lần thứ mười.

**Xử lý.** Bọc `TestClient` để mỗi lượt gọi mang một `X-Forwarded-For` mới —
cùng khuôn đã dùng ở `test_password_reset.py` và `test_email_verification_gate.py`.
Dọn Redis trước mỗi lần chạy cũng chữa được, nhưng nó bắt người chạy phải nhớ.
Kiểm chứng bằng ba lượt chạy liên tiếp **không dọn Redis**: 32/32 xanh cả ba.

Cookie không bị ảnh hưởng: lớp bọc uỷ nhiệm cho `TestClient` bên trong nên bình
đựng cookie giữ nguyên, và gói dùng thử định danh khách bằng cookie chứ không
bằng IP.

### B6 — `_fetch_user_by_login` không dùng được chỉ mục

**Lỗi.** `WHERE lower(username) = %s OR lower(email) = %s`, trong khi chỉ mục
duy nhất đánh trên cột thô.

**Vì sao là lỗi.** Mỗi lần đăng nhập là một lần quét toàn bảng. Với 10 tài
khoản thì không đáng kể; với một nền tảng SaaS thì đây là đường nóng nhất.

**Xử lý.** Chưa sửa — ghi lại ở đây. Cách sửa: chỉ mục hàm trên
`lower(email)` và `lower(username)`. Chưa làm vì chưa có số đo cho thấy nó là
điểm nghẽn, và thêm chỉ mục không đo là đoán.

---

## C. Lộn xộn về cấu trúc — kèm số đo

| # | Vấn đề | Đo được | Xử lý |
|---|---|---|---|
| C1 | `metadata_db.py` gánh 6 trách nhiệm | **2.971 dòng**, 67 hàm public, 33 `CREATE TABLE`, 44 `ADD COLUMN`, 49 chỉ mục | **Chưa tách.** Xem ghi chú dưới. |
| C2 | Khối schema v3 quá nhiều văn xuôi | **461 dòng, 46% chú thích** → còn **404 dòng, 37%** | Giữ chú thích ghi quyết định hoặc số đo; bỏ phần diễn giải lại SQL và chuyển bối cảnh dài sang §9sexies. Không ép xuống thấp hơn: những chú thích còn lại đều trả lời "vì sao 100 phiên để NULL" — bỏ chúng là bỏ đúng thứ người đọc sau cần |
| C3 | `test_schema_v3.py` gộp 4 mối quan tâm | 593 dòng | Tách thành 5 file theo chủ đề: `test_schema_shape`, `test_schema_constraints`, `test_schema_backfill`, `test_audit_log`, `test_training_output_contract` |
| C4 | `rollback_cursor` chép 3 bản | 3 file | Gom về `conftest.py`. Một bản chép đã suýt thiếu `apply_scope` — thiếu nó thì test xanh vì `InsufficientPrivilege` chứ không phải vì ràng buộc |
| C5 | Test email dùng địa chỉ giả | 22 file chứa `@example.com` | `tests/accounts.py` + `test_real_email_identities.py` dùng ba địa chỉ thật, kèm hàng rào chặn ghi vào `signdb` |

**Về C1.** Tách `metadata_db.py` là việc đúng nhưng tôi **không làm trong đợt
này**, và lý do là thật chứ không phải ngại: 67 hàm đang được import ở khắp nơi
trong 35.862 dòng backend, và một lần đổi tên module trong khi 1.300 test vừa
mới xanh sẽ trộn lẫn "hỏng vì tách file" với "hỏng vì lược đồ mới". Việc tách
nên là một thay đổi độc lập, không mang theo gì khác. Đường tách rõ ràng:
`storage/schema/tables.py` (DDL) + `storage/schema/migrations.py` +
`storage/schema/audit.py` (`schema_debt`), giữ `metadata_db.py` cho CRUD.

---

## Trạng thái test

| Lượt | Kết quả | Ghi chú |
|---|---|---|
| 1 | 1.263 qua | trước đợt review |
| 2 | 1.289 qua / **12 đỏ** | 9 đỏ do tôi chạy sai vai (`admin` có BYPASSRLS), 3 đỏ thật |
| 3 | 1.308 qua / 1 đỏ | B2 — test grep bắt phải văn xuôi |
| 4 | 1.329 qua / 1 đỏ | A3 — test cũ khẳng định ranh giới ngày theo UTC |
| 5 | 1.329 qua / 3 đỏ | B7 — bộ đếm rate-limit sót từ lượt trước |
| **6** | **1.332 qua / 0 đỏ** | |

Kiểm sau lượt cuối:

| Kiểm | Kết quả |
|---|---|
| Đối chiếu số dòng trước/sau migration | 26 bảng không đổi; `capture_sessions` +250, `tenant_members` +10, `signers` +2, `vocabulary_groups` +5 — **0 dòng mất** |
| Rác test trong bản sao sau 1.332 test | **0** |
| `signdb` thật sau cả đợt | 10 users / 3.860 samples / 63 classes — **không đổi**, và `capture_sessions` chưa tồn tại |

Dòng cuối là điểm đáng chú ý nhất: đây là lần đầu một lượt chạy suite đầy đủ
**không để lại gì trong dữ liệu thật**, vì nó không hề chạm vào dữ liệu thật.
Ba lần rò trước đó đều được vá ở tầng teardown; B4 vá ở tầng đúng.

## Chưa làm, và vì sao

- **Tách `metadata_db.py`** — xem C1.
- **Chỉ mục hàm cho đường đăng nhập** — xem B6.
- **Xoá 20 dòng `signers` rác** — cố ý không đặt `DELETE` vào đường khởi động;
  một câu xoá chạy lúc boot sẽ ăn dữ liệu thật trên một máy khác.
- **Áp migration lên `signdb` thật** — đã kiểm đầy đủ trên bản sao, nhưng đây
  là thao tác trên dữ liệu sản xuất. Backup có sẵn ở
  `E:\CTU_ProjectOutside\voya_backups\signdb_pre_schema_20260808_014839.sql`.
