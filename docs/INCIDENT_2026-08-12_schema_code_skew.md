# Sự cố 12/08/2026 — migration PDM v5 chạy nhầm lên sản xuất

**Mức độ:** cao (lệch lược đồ ↔ mã), **không** mất dữ liệu
**Thời lượng lệch:** từ lúc migration chạy tới lúc triển khai ảnh mới
**Phát hiện bởi:** chính người gây ra, trong bước kiểm tra tiếp theo của cùng phiên

---

## 1. Chuyện gì đã xảy ra

Trong lúc kiểm chứng lược đồ PDM v5 trên **bản sao**, một lệnh chạy
`ensure_tables()` trong container dùng-một-lần:

```
docker compose run --rm --no-deps \
  -e POSTGRES_DB=authz_v5 \
  --entrypoint python backend -c "... ensure_tables() ..."
```

Ý định: dựng lược đồ v5 lên cơ sở dữ liệu `authz_v5`.
Thực tế: nó chạy lên **`signdb` của sản xuất**.

`POSTGRES_DB` **không** phải nguồn mà ứng dụng dùng để dựng DSN. Ứng dụng đọc
`MIGRATION_DATABASE_URL` (và `DATABASE_URL`), cả hai đều đến từ `.env` và cả hai
đều trỏ `…/signdb`. Biến truyền vào bị bỏ qua trong im lặng.

Kết quả: sản xuất chuyển sang lược đồ v5 — `memberships` và `role_assignments`
ra đời, sáu bảng cũ bị bỏ, `tenant_members` thành view — trong khi **ảnh đang
chạy vẫn là mã cũ**.

## 2. Vì sao nó không bị chặn

Ba lớp lẽ ra phải chặn, và không lớp nào tồn tại:

| Lớp | Trạng thái lúc đó |
|---|---|
| Nói ra đích trước khi ghi | **Không có.** Không dòng log nào nêu database đang nối tới |
| Xác minh đích khớp ý định | **Không có.** Không có cách nào tuyên bố "tôi định ghi vào X" |
| Tách migration phá huỷ khỏi startup | **Không có.** `ensure_tables()` làm cả hai |

Điều biến một lỗi gõ thành sự cố không phải là biến môi trường sai tên. Đó là
chuyện **không bước nào nói ra nó đang sắp ghi vào đâu** — nên không có khoảnh
khắc nào để nhận ra trước khi bảng đã bị bỏ.

Đáng nói thêm: mọi lượt chạy DDL TRƯỚC đó trong cùng phiên đều an toàn, vì
chúng dùng một kết nối `psycopg2` tự dựng với `dbname` nêu tường minh. Lượt gây
sự cố là lượt ĐẦU TIÊN dùng chính mã ứng dụng để chạy migration — và đó chính
là lượt mất quyền kiểm soát đích.

## 3. Thiệt hại

**Không mất dữ liệu.** Đo ngay sau đó:

```
memberships       PROJECT 10 · TENANT 10 · WORKSPACE 10
role_assignments  SYSTEM 4 · SCOPED 10
tenant_members    (view) 10 dòng
```

Đúng bằng số liệu đã kiểm chứng trên bản sao trước đó. Bản thân lượt di trú
chạy đúng như thiết kế.

**Sản xuất vẫn phục vụ.** Bốn service healthy, không lỗi trong log. Hỏng hóc là
*tiềm ẩn*: mã cũ chỉ chạm các bảng đã bị bỏ khi nạp lại policy Casbin (lúc khởi
động lại) hoặc khi có lệnh ghi thành viên. Không sự kiện nào trong hai loại đó
xảy ra trong cửa sổ lệch.

**Rủi ro thật:** một lần khởi động lại ngoài ý muốn. Nên chỉ dẫn vận hành trong
suốt cửa sổ đó là *đừng khởi động lại stack*.

## 4. Đã sửa gì

### 4.1 Chốt chặn đích — `_assert_expected_database()`

Ở `app/storage/metadata_db.py`, chạy trong `_migration_cursor()` trước mọi DDL.
Hai lớp, cố ý khác nhau:

**Banner chạy vô điều kiện.** Biến đích thành thứ đọc được ở dòng log đầu tiên:

```
[MIGRATION-TARGET] database=signdb user=admin server=172.18.0.3:5432 expected=(khong dat)
```

**`EXPECTED_DATABASE` là lớp chặn, và chỉ bật khi được yêu cầu.**
`ensure_tables()` chạy hợp lệ ở mỗi lần khởi động backend trên sản xuất, nên một
chốt chặn luôn-bật sẽ chặn cả đường đi đúng. Ai chạy migration bằng tay thì đặt
nó:

```
EXPECTED_DATABASE='authz_v5' nhung dang noi toi 'signdb'. Khong chay DDL nao.
Sua DSN (MIGRATION_DATABASE_URL/DATABASE_URL) chu khong phai POSTGRES_DB —
bien do KHONG duoc dung de dung DSN.
```

Thông điệp nêu **cả hai** tên, và nói thẳng biến nào mới là biến đúng — vì người
đọc nó đang hoảng và không nên phải đi tìm.

So bằng `current_database()` chứ không bằng chuỗi DSN: DSN viết được bằng nhiều
dạng và so chuỗi sẽ vừa bỏ sót vừa báo nhầm. `current_database()` là câu trả lời
của chính máy chủ về nơi phiên này đang đứng.

Đã chứng minh bằng cách chạy lại **đúng lệnh gây sự cố**, có thêm biến chốt: nó
bị từ chối.

### 4.2 Test hồi quy — `backend/tests/test_rls_write_gate.py`

`TestMigrationTargetGuard`: từ chối khi lệch, cho qua khi khớp, im lặng khi
không đặt, và **luôn** in banner.

## 5. Bài học khác rút ra trong cùng lượt

### 5.1 Hai phép đo "đạt" mà không chứng minh gì

Khi dò cổng RLS phần ghi, hai lần đo liên tiếp đều trông như thành công:

1. `INSERT … SELECT … FROM users` trả `INSERT 0 0` — trông như đã chặn. Thật ra
   câu SELECT nguồn đã bị RLS lọc sạch; **không có gì bị từ chối, chỉ là không
   có gì để chèn.**
2. Sửa thành `VALUES` cố định thì vướng bẫy khác: mọi user trong hệ đều đã là
   thành viên tenant đích, nên lệnh va vào **chỉ mục duy nhất** chứ không phải
   policy. Vẫn ra lỗi, vẫn trông như đã chặn.

Chỉ khi dựng dữ liệu mới hoàn toàn — hai tenant và một user chưa thuộc tenant
nào — thì `pytest.raises(InsufficientPrivilege)` mới có nghĩa, vì
`InsufficientPrivilege` là mã lỗi RIÊNG của vi phạm row-level security, khác với
`UniqueViolation`.

Bài học chung: **một phép thử an ninh phải chứng minh cơ chế nó tuyên bố, không
phải chỉ ra kết quả trông giống thành công.**

### 5.2 Sentinel viết sai thì fail-closed

Phát hiện tình cờ: `app.system_scope` chỉ nhận đúng chuỗi `'on'`, và `'1'` bị
từ chối. Hành vi đúng, và đã được ghim thành test — nếu vị từ từng được nới
thành "khác rỗng thì coi như hệ thống", mọi giá trị rác sẽ mở toang cách ly
tenant.

### 5.3 Hai cảnh báo vĩnh viễn do câu lệnh cũ còn sót

Lượt kiểm idempotency trên bản sao lộ ra ba câu lệnh trong
`MIGRATION_STATEMENTS` không còn chạy được sau v5: câu chèn ba role hạt giống
(cột `name` đã đổi tên) và hai `CREATE INDEX` trên `tenant_members` (giờ là
view). Cả ba đã được gỡ, kèm chú thích nói rõ chỉ mục đã chuyển sang bảng nền.

Cái giá thật của tiếng ồn đó không phải dung lượng log mà là **dạy người vận
hành bỏ qua cảnh báo của `ensure_tables`** — và cảnh báo tiếp theo có thể là
thật.

### 5.4 Bốn cảnh báo đua đồng thời, lộ ra ở chính lượt kiểm sau triển khai

Nhật ký khởi động sau deploy có bốn cảnh báo, và phải lọc qua chúng mới tìm ra
cảnh báo thật:

```
constraint "ck_support_author_kind" ... already exists
constraint "ck_support_author_kind_matches" ... already exists
trigger "trg_legal_documents_freeze" ... already exists
tuple concurrently updated : CREATE OR REPLACE FUNCTION legal_documents_freeze()
```

Ba cái đầu là mẫu `DROP …; ADD/CREATE …` viết thành **hai câu** — khe giữa hai
câu là chỗ bốn worker gunicorn đua nhau. Cái thứ tư là hai worker cùng
`CREATE OR REPLACE FUNCTION`, đua ngay trên catalog của Postgres, thứ không
guard nào ở tầng câu lệnh chữa được.

Chú thích trong `ensure_tables()` đã dừng phạm vi khoá tư vấn ở khối phân quyền,
với lập luận rằng hai danh sách còn lại "vốn đã chịu được chạy song song". Phép
đo bác bỏ. Đã mở rộng khoá ra cả `DDL_STATEMENTS` và `MIGRATION_STATEMENTS`; đo
lại bằng **3 vòng × 4 tiến trình song song → 0 cảnh báo**.

Đây là lỗi có sẵn từ trước, không phải hồi quy của v5 — nhưng nó chỉ lộ ra khi
có người thật sự ĐỌC nhật ký khởi động, và lý do phải đọc là vì đang có sự cố.

## 6. Việc còn lại — nguyên nhân gốc chưa xử lý

**`ensure_tables()` vẫn kiêm hai vai.** Nó làm được cả việc bỏ bảng, tạo view,
backfill dữ liệu và cho role nghỉ hưu — vượt xa nghĩa "bảo đảm các bảng tồn
tại". Chốt chặn ở §4.1 chỉ chặn lỗi **nhắm sai đích**; nó không chặn được việc
một lần khởi động vô tình thực hiện migration cấu trúc lớn.

### Phương án

`authz_schema.py` đã gom sẵn mọi thao tác phá huỷ vào **một danh sách duy
nhất**: `_DATA_MIGRATION_DDL` (chép dữ liệu → bỏ 6 bảng cũ → tạo view). Nên việc
tách không phải là viết lại, mà là đặt một cổng trước đúng danh sách đó:

```
startup ensure      chỉ chạy phần CỘNG THÊM và idempotent.
                    Nếu còn việc phá huỷ chưa làm → GHI RÕ và TỪ CHỐI,
                    không tự chạy.

explicit migration  python -m app.cli.migrate — chạy mọi thứ, và là chỗ
                    duy nhất `_DATA_MIGRATION_DDL` được phép chạy.
```

`missing_objects()` đã đủ sức trả lời "còn việc gì chưa làm", nên phần phát hiện
không cần viết mới.

### Đánh đổi phải cân, và vì sao chưa tự quyết

Tách như trên **đổi hợp đồng triển khai**: một máy dựng từ số không sẽ không còn
tự lên lược đồ khi khởi động backend — `scripts/deploy.sh` phải gọi bước migrate
trước. Hai hệ quả ngược chiều nhau:

* **Được:** không lần khởi động nào có thể tự ý đổi cấu trúc. Đúng thứ đã hỏng
  ngày 12/08.
* **Mất:** thêm một bước bắt buộc mà nếu quên thì backend từ chối khởi động —
  và trên một máy mới, triệu chứng sẽ là "deploy xong nhưng không lên", đúng
  loại lỗi mà ghi chép `fresh-boot-schema-drift` đã trả giá một lần.

Cái thứ hai xử lý được (deploy.sh gọi migrate; verify_deployment báo rõ), nhưng
nó là một quyết định về quy trình vận hành chứ không phải một lựa chọn kỹ thuật
thuần tuý — nên nó chờ người quyết, không tự làm.

## 7. Vật phẩm khôi phục

Hai mốc, trên ổ đĩa thật (không phải `/tmp` của container — đó là nơi sai để
giữ vật phẩm khôi phục duy nhất, vì nó biến mất khi container bị tạo lại):

```
E:\CTU_ProjectOutside\voya_backups\
    signdb_PRE_v5_20260812_184124.dump    663K   trước di trú
    signdb_POST_v5_20260812_184124.dump   678K   v5 + dữ liệu hiện tại
```

Mốc POST là thứ khiến forward-fix an toàn hơn rollback: nếu triển khai ảnh mới
gặp sự cố, nó khôi phục về **lược đồ hiện tại + dữ liệu hiện tại**, thay vì quay
ngược về trước migration và mất mọi hoạt động phát sinh sau đó.
