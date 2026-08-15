# Kiểm thử: luồng chạy, chuẩn viết, danh mục test case

*Cập nhật 2026-08-10 · backend 1.696 test (97 tệp) · frontend 363 test (45 tệp)*

Tài liệu này trả lời ba câu: **chạy test thế nào**, **một lượt chạy diễn ra
những gì**, và **từng bộ test canh cái gì**.

---

## 1. Chạy test

### 1.0 Hai nền chạy khác nhau, và chúng trả lời hai câu khác nhau

| Nền | Dùng để | Số mới nhất |
|---|---|---|
| **Bản sao sản xuất** (`signdb_test`) | hồi quy: thay đổi có phá dữ liệu thật không | **1.696** xanh / 0 đỏ |
| **CSDL dựng từ số không** (`signdb_ci`) | CI: mã có chạy trên một máy MỚI không | **1.681** xanh / 0 đỏ / 15 skip |

Chênh lệch 15 test giữa hai cột là **skip**, không phải đỏ: chủ yếu là test trích
npz từ video (kho clip 2,7 GB không có trên nền CI) và vài test cần dữ liệu thật.
Chúng hiện ra trong báo cáo chứ không biến mất.

Lần đầu chạy trên nền thứ hai (2026-08-10, để dựng CI) cho **22 đỏ**, và không
cái nào là lỗi của test: `ensure_tables()` dựng ra một lược đồ thiếu 2 bảng, 7
khoá ngoại và 14 cột so với máy đang chạy — tức mọi máy triển khai mới đều nhận
một lược đồ yếu hơn, trong im lặng. Đã vá. Chi tiết ở §1.2.

**Dựng lược đồ bằng `python -m app.cli.migrate --to <N>`, không phải
`ensure_tables()`.** Từ 12/08/2026 `ensure_tables()` chỉ còn THÊM: phần một
chiều — chép dữ liệu sang `memberships`, bỏ 6 bảng phân quyền cũ, bỏ chỉ mục
duy nhất toàn cục — chỉ chạy dưới lệnh migration. Gọi `ensure_tables()` trên
một cơ sở dữ liệu trống sẽ để lại `tenant_members` là **BẢNG** chứ không phải
view, và bộ test đỏ theo cách không nói ra nguyên nhân. Lệnh này bắt buộc đặt
`EXPECTED_DATABASE`.

Bộ test tự lo phần đó: `conftest.pytest_sessionstart` gọi `migrate_database()`
một lần trước mọi fixture, nên khoảng ba mươi tệp test có fixture riêng gọi
`ensure_tables()` vẫn đúng — tới lượt chúng thì cơ sở dữ liệu đã ở phiên bản
hiện hành và "thêm cho đủ" là vừa đủ.

**Bước GRANT là bắt buộc trên nền thứ hai.** Bộ test chạy dưới vai `voya_app`
(không phải superuser — superuser được miễn RLS vô điều kiện), nhưng lược đồ
được dựng bằng vai DDL, và Postgres không tự cấp quyền trên bảng mới cho vai
khác. Thiếu GRANT → **41 lỗi chỉ trong 3 tệp**, tất cả là
`permission denied for table users`, một thông báo trỏ thẳng vào mã ứng dụng
trong khi nguyên nhân nằm ở phân quyền.

```bash
# sau bước dựng lược đồ, TRƯỚC khi chạy pytest
psql "$MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
GRANT USAGE ON SCHEMA public TO voya_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO voya_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voya_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO voya_app;
SQL
```

`.github/workflows/ci.yml` làm đúng chuỗi này, kèm một bước kiểm
`schema_debt()` rỗng **trước** khi chạy test nào — cổng đó bắt đúng lớp lỗi trên
và bắt sớm hơn.

### 1.0b ĐỪNG SỬA TỆP `.py` TRONG LÚC SUITE ĐANG CHẠY

Kho được bind-mount **sống** vào container. `inspect.getsource()` đọc lại tệp từ
đĩa theo số dòng ghi lúc import, nên một lượt sửa giữa chừng làm nó trả về **thân
của một hàm khác**. Đã mắc 2026-08-10: `test_history_query_exposes_the_column`
đỏ với thông báo về `superseded_at` trong khi thân hàm in ra là
`insert_training_metric`. Không phải hồi quy — chạy lại khi tệp đứng yên thì
xanh. Tệp `.md` thì sửa thoải mái.

### 1.1 Backend — trong container, trên mạng compose

```bash
docker run --rm --network voya-collector_voya_network \
  -v "E:/CTU_ProjectOutside/VOYA-Collector:/src" \
  -v "E:/CTU_ProjectOutside/Videos:/testvideos:ro" \
  -w /src/backend -e PYTHONPATH=/src/backend \
  -e VOYA_TEST_VIDEO=/testvideos/D0001B.mp4 \
  -e DATABASE_URL="postgresql://voya_app:<mật khẩu>@postgres:5432/signdb_test" \
  -e MIGRATION_DATABASE_URL="postgresql://admin:admin@postgres:5432/signdb_test" \
  -e VOYA_APP_DB_PASSWORD="<mật khẩu>" \
  -e REDIS_URL="redis://redis:6379/13" \
  -e CELERY_BROKER_URL="redis://redis:6379/13" \
  -e CELERY_RESULT_BACKEND="redis://redis:6379/13" \
  -e TTS_REDIS_URL="redis://redis:6379/13" \
  voya_backend_test:latest python -m pytest
```

Năm chi tiết trong dòng lệnh trên là bắt buộc, không phải tuỳ chọn:

| Chi tiết | Vì sao |
|---|---|
| `voya_backend_test:latest` | ảnh riêng dựng từ `backend/Dockerfile.test`. Ảnh sản xuất **không** có `pytest`. Ảnh này hay cũ hơn `requirements-dev.txt` và khi đó suite chết ngay lúc thu thập — dựng lại trước khi nghi ngờ mã. |
| `--network voya-collector_voya_network` | tên máy chủ `postgres` và `redis` chỉ phân giải được bên trong mạng compose. |
| `signdb_test` | **bản sao** của cơ sở dữ liệu sản xuất. Không phải `signdb`. Xem §2.4. |
| `redis://redis:6379/**13**` | không gian riêng cho test. Dùng chung DB 0 với ứng dụng đang chạy sẽ làm bộ đếm rate-limit trôi qua các lượt chạy và một tệp test sẽ bắt đầu trả 429 ở lượt thứ N. |
| `VOYA_TEST_VIDEO` | **mount `/testvideos` thôi là CHƯA đủ.** `test_real_hand_video_extracts_seqlen_x_126_sequences` `skipif` theo biến môi trường này, không theo sự tồn tại của thư mục. Thiếu nó thì test trích npz từ clip thật lặng lẽ skip — kiểu skip tệ nhất, vì trông như "máy không hỗ trợ" trong khi đây là máy DUY NHẤT chạy được nó. |

Chạy một tệp, một lớp, một test:

```bash
... python -m pytest tests/test_legal_repository.py -q
... python -m pytest tests/test_legal_repository.py::TestTheBodyIsStored -q
... python -m pytest -k "consent and not admin" -q
```

### 1.2 Frontend — trên máy

```bash
cd frontend
npx vitest run                 # toàn bộ
npx vitest run src/pages       # một thư mục
npm run typecheck              # kiểm kiểu, KHÔNG bỏ qua  ← không phải `npx tsc --noEmit`
npm run build                  # bản dựng thật
```

Kiểm kiểu là một cổng riêng chứ không phải phần phụ của test: nó bắt được loại
lỗi mà vitest không bắt — ví dụ một `await` đặt trong hàm cập nhật state, thứ
chạy được trong test nhưng sai về ngữ nghĩa React.

> ### `npx tsc --noEmit` KIỂM KHÔNG TỆP NÀO. Đừng dùng.
>
> `frontend/tsconfig.json` là `{"files": [], "references": [...]}`. Không có
> `-b` thì tsc đọc đúng tệp đó, thấy không có tệp nguồn nào, và **thoát 0** —
> nhìn y hệt một lượt kiểm sạch.
>
> Đây là lời giải cho câu đã ghi trong sổ tay từ lâu: *"`npm run build` từng
> hỏng mà `tsc --noEmit` không bắt"*. `build` chạy `tsc -b`, nên nó theo project
> reference và kiểm thật.
>
> Đo được: đợt quét emoji 2026-08-09 giấu **14 lỗi kiểu** sau lỗ hổng này.
> `npm run typecheck` (= `tsc -b --noEmit`) bày cả 14 ra ngay lượt chạy đầu.

### 1.3 Bộ nghiên cứu chạy như tiến trình con

Phần lớn suite thuộc pipeline nghiên cứu là **script độc lập**: tệp thuần
stdlib với một `main()` in PASS/FAIL và trả mã thoát, chạy được trong container
huấn luyện mà không cần pytest.

Pytest không thu được gì từ chúng (không có hàm `test_*`), nên một lệnh
`pytest backend/tests` từng báo thành công trong khi ~200 phép khẳng định không
hề chạy. Chúng bị loại khỏi bước thu thập và được `test_research_suites.py`
chạy như tiến trình con, khẳng định mã thoát.

---

## 2. Một lượt chạy diễn ra những gì

```
┌─ pytest_sessionstart ─────────────────────────────────────────┐
│ 1. ensure_tables()      chạy toàn bộ migration lên signdb_test │
│ 2. chụp ảnh vạch xuất phát: khoá chính của 26 bảng             │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌─ thu thập ─────────────────────────────────────────────────────┐
│ conftest.py điền biến môi trường còn TRỐNG (setdefault)        │
│ loại các script nghiên cứu độc lập khỏi danh sách thu thập     │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌─ chạy ─────────────────────────────────────────────────────────┐
│ fixture module: ensure_tables() (idempotent)                   │
│ fixture hàm:    dựng dữ liệu → test → dọn dữ liệu của mình     │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌─ pytest_terminal_summary ──────────────────────────────────────┐
│ 3. chụp ảnh lần hai, lấy HIỆU                                  │
│ 4. IN RA mọi hàng bộ test đã tạo                               │
│ 5. xoá chúng, lá-trước-gốc                                     │
│ 6. chụp lần ba để kiểm: "0 hàng còn sót"                       │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 Sổ dấu vết — và giới hạn của nó

Ba bước cuối là **sổ dấu vết** (`tests/conftest.py`). Bước 4 là thứ quan trọng
nhất: *thấy được* dấu vết trước khi nó biến mất. Một lượt chạy im lặng rồi tự
dọn thì không phân biệt được với một lượt chạy không tạo gì cả.

Kết quả mong muốn cuối mỗi lượt:

```
====================================================================
  SO DAU VET: bo test khong de lai hang nao. Sach.
====================================================================
```

hoặc, khi có tạo và đã dọn xong:

```
  SO DAU VET — bo test da tao 11 hang tren 1 bang
  audit_log                +11    11, 12, 13 (+8 nua)
  Da xoa 11/11 hang.
  Kiem lai: 0 hang con sot.
```

**Giới hạn phải biết:** sổ theo dõi những hàng được **TẠO** ra. Nó **không**
phục hồi những hàng bị **XOÁ**. Một fixture chạy `DELETE FROM <bảng nền tảng>`
sẽ phá dữ liệu trên bản sao và sổ không nói gì cả.

Đúng một chỗ từng như vậy: `test_legal_consent.py` xoá sạch `legal_documents`
để kiểm hành vi "chưa công bố gì". Nó nay tự **chụp và phục hồi** bảng đó ở
phạm vi module. Hai chỗ khác trông giống (`test_tenant_isolation.py`,
`test_two_tenant_proof.py`) thì an toàn: chúng chạy trong phạm vi RLS nên câu
`DELETE` không điều kiện chỉ chạm dữ liệu của tenant thử nghiệm — và đó chính
là điều chúng đang kiểm.

### 2.2 Vì sao ảnh chụp nằm ở `sessionstart` chứ không ở fixture

Hai lỗi đã mắc và đã sửa, ghi lại vì cả hai đều lặng lẽ:

1. Finalizer của fixture cấp session chạy **sau** khi trình báo cáo terminal
   đóng → báo cáo không in ra dòng nào.
2. Fixture cấp session chạy **trước** mọi fixture module gọi `ensure_tables()`.
   Trên một cơ sở dữ liệu chưa migrate, ảnh chụp đầu thiếu 250 hàng
   `capture_sessions`, 10 hàng `tenant_members` và 2 hàng `signers` do chính
   migration sinh ra — rồi bước dọn coi chúng là dấu vết của bộ test và xoá đi.
   **Chạy suite một lần sẽ huỷ kết quả backfill.**

### 2.3 Test chạy trên cơ sở dữ liệu THẬT

Không có mock cơ sở dữ liệu. Test chạy trên PostgreSQL thật vì phần lớn bất
biến của hệ thống này *là* bất biến của cơ sở dữ liệu: RLS, khoá ngoại, chỉ mục
duy nhất bộ phận, trigger. Một bản giả sẽ đi qua hết và không kiểm được gì.

Cái giá: test chậm hơn, và phải cẩn thận với dữ liệu.

### 2.4 `signdb_test` là bản sao, không phải cơ sở dữ liệu rỗng

Bản sao mang dữ liệu sản xuất thật. Đó là chủ ý — nó bắt được những thứ một
cơ sở dữ liệu rỗng không bắt được, ví dụ một migration chạy đúng trên bảng
trống nhưng vỡ trên bảng đã có 3.860 hàng.

Hai hệ quả:

* **Test không được viết cứng dữ liệu sẵn có.** `_register()` ở
  `test_signup_no_longer_lands_in_bootstrap.py` đọc số hiệu điều khoản *đang
  hiệu lực* thay vì viết cứng `"1.0"`, chính vì bản sao có văn bản thật.
* **Sổ dấu vết chỉ BÁO CÁO, không xoá, khi phát hiện đang chạy trên `signdb`.**
  Hiệu hai lần chụp trên cơ sở dữ liệu sản xuất bao gồm cả hàng do người dùng
  thật tạo trong lúc suite chạy.

#### Dựng lại `signdb_test`

Bản sao hay bị xoá đi để lấy chỗ trống (nó khoảng 15 MB). Dựng lại bằng
`TEMPLATE`, **không** bằng `CREATE DATABASE` rỗng:

```bash
docker exec voya_postgres psql -U admin -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity \
   WHERE datname='signdb' AND pid<>pg_backend_pid()"
docker exec voya_postgres psql -U admin -d postgres -c \
  "CREATE DATABASE signdb_test WITH TEMPLATE signdb OWNER admin"
```

`pg_terminate_backend` là bắt buộc: Postgres từ chối dùng một cơ sở dữ liệu làm
template khi còn kết nối nào mở tới nó, và stack đang chạy thì luôn còn.

**Một cơ sở dữ liệu rỗng KHÔNG chạy được suite.** Đo 2026-08-09: tạo
`signdb_test` rỗng rồi chạy suite cho **549 lỗi / 34 đỏ**, và mọi thông báo đều
trỏ vào mã ứng dụng chứ không trỏ vào cơ sở dữ liệu. Migration dựng được bảng,
nhưng vai `voya_app` không có quyền trên các bảng vừa dựng trong một cơ sở dữ
liệu mới — `TEMPLATE` mang theo cả quyền. Cùng đợt đó, khi cơ sở dữ liệu **không
tồn tại** thì triệu chứng cũng y hệt. Nếu thấy hàng trăm ERROR cùng lúc, hãy
nghi cơ sở dữ liệu trước khi nghi mã.

---

## 3. Chuẩn viết test

Áp dụng chuẩn Google (*Software Engineering at Google*, ch. 11–12):

### 3.1 Một test, một hành vi

Sai:

```python
def test_publishing():
    doc = publish(...)
    assert doc.version == "1.0"
    assert doc.body == "..."
    with pytest.raises(...): publish_again_with_different_body()
```

Đúng — mỗi khẳng định một tên, nên khi đỏ thì tên test đã nói ra chuyện gì hỏng:

```python
def test_readDocument_afterPublishing_returnsTheBodyVerbatim(): ...
def test_changingContentUnderTheSameVersion_isRefused(): ...
```

### 3.2 Tên nói ra hợp đồng

`methodName_stateUnderTest_expectedBehavior`. Đọc tên là biết test canh gì mà
không phải mở thân hàm.

Với các tệp cũ hơn viết theo lối câu tiếng Anh
(`test_an_attacker_cannot_lock_the_real_user_out`) thì giữ nguyên — đổi tên
hàng loạt là một diff lớn không thêm thông tin nào.

### 3.3 DAMP hơn DRY

Test được **đọc** nhiều hơn được **sửa**. Lặp lại ba dòng dựng dữ liệu ở năm
test tốt hơn một hàm trợ giúp mà người đọc phải nhảy vào mới hiểu test đang nói
gì. Ngoại lệ: dọn dẹp — xem §3.6.

### 3.4 Không có logic trong test

Không `if`, không vòng lặp tính toán giá trị mong đợi. Một test có nhánh là một
test cần test.

Vòng lặp *khẳng định trên một tập cố định* thì được:

```python
for kind in legal.KINDS:
    assert ("GET", f"/legal/{kind}") in PUBLIC_ROUTES, kind
```

### 3.5 Mỗi khẳng định trung tâm có một phản chứng

Test khẳng định "X bị chặn" phải đi kèm test khẳng định "Y được cho qua". Không
có nó, một bản vá chặn *mọi thứ* vẫn xanh.

Ví dụ trong `test_legal_repository.py`:

| Khẳng định | Phản chứng |
|---|---|
| sửa `body` bị chặn | sửa `title` được cho qua |
| dời lịch bản đã hiệu lực bị chặn | dời lịch bản chưa tới hạn được cho qua |
| đường công khai không thấy bản tương lai | đường quản trị thấy |

### 3.6 Dọn dẹp là chỗ DUY NHẤT ưu tiên DRY

Bốn bản gần giống nhau của cùng một hàm dọn từng tồn tại ở bốn tệp, và ba trong
bốn viết cho hình dạng **cũ** của một lượt đăng ký. Mỗi lượt chạy suite để lại
hàng chục tenant mồ côi, và sổ dấu vết bắt được ở ba lượt liên tiếp trước khi
nguyên nhân thật lộ ra.

Nay có đúng một bản: `conftest.purge_registered_account(username)`. Nó tự tra
id, tự tìm tenant mà lượt đăng ký tạo ra, và **chỉ xoá tenant có cờ
`is_self_serve`** — một tenant do lời mời cấp thuộc về fixture khác, và xoá nó
là dọn sang phần của người khác.

### 3.7 Test tự dọn thứ mình tạo, không xoá sạch bảng

Với bảng áp cho cả nền tảng (`legal_documents`, `plans`, `platform_settings`):
dùng số hiệu/khoá riêng cho từng test và xoá đúng khoá đó. Nếu buộc phải xoá
sạch, **chụp và phục hồi** ở phạm vi module.

---

## 4. Danh mục test — backend (97 tệp)

### 4.1 Cách ly nhiều tổ chức và lược đồ

| Tệp | Canh gì |
|---|---|
| `test_tenant_isolation.py` | RLS: `DELETE FROM samples` không điều kiện chỉ chạm tenant hiện tại; `WITH CHECK` chặn ghi sang tenant khác |
| `test_two_tenant_proof.py` | như trên, dựng hai tenant thật và chứng minh từng chiều |
| `test_db_role_isolation.py` | vai `voya_app` không có BYPASSRLS; DDL chỉ vai migration làm được |
| `test_tenant_foreign_keys.py` | mọi bảng trong `TENANT_SCOPED_TABLES` có khoá ngoại tenant — bắt lỗi "vòng lặp chạy trước khi bảng tồn tại" |
| `test_schema_shape.py`, `test_schema_constraints.py`, `test_schema_evolution.py`, `test_schema_v4.py` | hình dạng lược đồ, ràng buộc, và migration chạy được nhiều lần |
| `test_schema_backfill.py` | migration đúng trên bảng ĐÃ CÓ dữ liệu, không chỉ trên bảng trống |

### 4.2 Xác thực, quyền, cổng truy cập

| Tệp | Canh gì |
|---|---|
| `test_access_gate.py` | mặc-định-từ-chối; bề mặt công khai thật KHỚP `PUBLIC_ROUTES`; không đường công khai nào có tham số |
| `test_signup_no_longer_lands_in_bootstrap.py` | lỗ hổng đã vá: đăng ký tự phục vụ không rơi vào tenant gốc; ba mắt xích, mỗi mắt một test |
| `test_login_rate_limit.py` | hoãn tăng dần theo cặp (tài khoản, IP); **người khác không khoá được tài khoản của bạn** |
| `test_cookie_auth.py`, `test_tokens.py` | vòng đời phiên, cookie httpOnly, CSRF |
| `test_otp.py`, `test_email_verification_gate.py` | mã một lần, có hạn, lưu dạng băm |
| `test_password_reset.py` | luồng quên mật khẩu |
| `test_trial_and_sudo.py` | phiếu dùng thử theo phút; cửa sổ nâng quyền 5 phút |
| `test_security_hardening.py` | tiêu đề bảo mật, kích thước tải lên, đầu vào lạ |
| `test_audit_log.py` | thao tác quản trị để lại dấu; hành động qua khoá API vẫn ghi được; **ghi được ở tầng nền tảng nhưng FAIL-CLOSED khi không có phạm vi nào**; `log_security_event` xuống cả bảng bền; Postgres chết không kéo theo nhánh Redis |
| `test_admin_audit_api.py` | đường ĐỌC của nhật ký kiểm toán: hình dạng, lọc theo tiền tố, mới-nhất-trước, chỉ quản trị viên; **một lượt purge thật để lại dòng đọc được** |
| `test_client_ip.py` | `X-Forwarded-For` chỉ tin từ proxy trong danh sách |

### 4.3 Pháp lý và chấp thuận

| Tệp | Canh gì |
|---|---|
| `test_legal_consent.py` | chấp thuận ghi BẢN NÀO; cưỡng chế bật bằng cách công bố; sửa nội dung dưới cùng số hiệu bị từ chối; **`GET /legal/me/consents`** — bản đã ký ≠ bản hiện hành, "đã ký bản cũ" ≠ "chưa ký bao giờ", `withdrawable` khớp hành vi thật của máy chủ, `guardian` không mời ký một lần |
| `test_legal_repository.py` | **v5** — thân văn bản lưu và đọc lại được; trigger bất biến; hẹn giờ; xuất xứ chấp thuận; bề mặt đọc công khai |
| `test_legal_admin_api.py` | công bố cần nâng quyền; bị từ chối thì KHÔNG ghi gì; sổ kiểm toán mang hash chứ không mang bản văn; lịch sử chấp thuận không lộ băm IP |
| `test_backfill_consents.py` | mặc định không ghi gì; `--apply` cần `--note`; dòng ghi ra tự nhận là ghi hộ; không đè lên chữ ký thật |
| `test_legal_store.py` | **v6** — tên tệp là băm nội dung; khử trùng lặp; an toàn đường dẫn; dọn rác đòi *cả hai* điều kiện (không tham chiếu **và** đủ 24h tuổi) |
| `test_legal_drafts.py` | **v6** — vòng đời nháp; **sổ đăng bạ giữ blob sống trước dọn rác** (nếu không, `pg_backup.sh` đánh dấu mọi bản sao lưu là `.CORRUPT`); **tranh chấp ghi bằng hai luồng THẬT**; bảng chuyển trạng thái; `uq_legal_effective`; sổ đăng bạ chỉ-thêm và không mang nội dung |

### 4.4 Mặt phẳng thương mại (v4)

| Tệp | Canh gì |
|---|---|
| `test_plans_and_quotas.py` | `NULL` = không giới hạn; chạm trần trả 402; hạn mức đọc từ bảng nguồn chứ không từ bộ đếm |
| `test_plan_administration.py` | sửa bảng giá qua API |
| `test_tenant_lifecycle.py`, `test_tenant_lifecycle_and_usage.py` | xuất dữ liệu; xoá vĩnh viễn với ba chốt chặn; số đo mức dùng theo ngày |
| `test_api_keys_and_webhooks.py` | khoá lưu dạng băm; chữ ký HMAC gồm mốc thời gian (chống phát lại); lịch thử lại; tự tắt sau chuỗi lỗi |
| `test_webhook_event_wiring.py` | quét AST: mọi sự kiện khai báo đều có chỗ phát thật |

### 4.5 Dữ liệu, xử lý, huấn luyện

| Tệp | Canh gì |
|---|---|
| `test_video_pipeline.py`, `test_upload_camera_training.py` | luồng tải lên → trích đặc trưng → lưu |
| `test_quality.py`, `test_coordinate_space.py`, `test_normalization_parity.py` | chỉ số chất lượng; không gian toạ độ; chuẩn hoá giống nhau ở mọi đường |
| `test_augmentation_geometry.py` | phép tăng cường không phá cấu trúc bàn tay |
| `test_signer_disjoint_split.py`, `test_split_safety.py`, `test_manifest.py` | cùng một người không nằm ở cả tập huấn luyện lẫn kiểm thử |
| `test_training_lifecycle.py`, `test_promotion_supersede.py`, `test_frozen_artifacts.py` | vòng đời phiên huấn luyện; thăng hạng mô hình; hiện vật đóng băng |
| `test_raw_archive.py` | kho raw ghi TRƯỚC chuẩn hoá |
| `test_registry_planes.py`, `test_vocabulary_registry.py`, `test_vocabulary_v2.py` | ba mặt phẳng danh mục; phiên bản bất biến; **không** có đường dự phòng âm thầm |

### 4.6 SOT (nguồn sự thật ký số)

`test_sot_*.py` — 10 tệp: khoá ký, kê khai, đồng bộ, lược đồ, tích hợp thật với
Google Drive. Tệp `test_sot_integration.py` cần mạng; nó **có thể đỏ do trục
trặc mạng Drive** và xanh lại khi chạy riêng — kiểm tra lại trước khi coi là hồi
quy.

### 4.7 Vận hành

| Tệp | Canh gì |
|---|---|
| `test_observability.py`, `test_logging_config.py` | log có cấu trúc; **mã bí mật không bao giờ vào log** |
| `test_disk_watermark.py`, `test_optimizations.py` | ngưỡng đĩa, bộ nhớ |
| `test_deploy_fixes.py`, `test_init_db_fallback.py`, `test_startup_sync*.py` | khởi động, migration lúc boot, đồng bộ đầu vòng đời |
| `test_real_email_identities.py` | ba địa chỉ thư thật dùng cho kiểm thử gửi thư |

---

## 4bis. Ba cái bẫy "đỏ giả" tìm được ngày 2026-08-09

Cả ba đều cho ra một test đỏ mà triệu chứng **không hề gợi tới nguyên nhân**.

### Đĩa đầy làm test đồng bộ đỏ, và nó trông như lỗi mã

`test_sync_tasks.py` có hai test đỏ với `mock_download.call_count == 0` — đọc
lên y hệt "tác vụ không tìm thấy tệp nào để tải". Nguyên nhân thật:
`_disk_over_watermark()` thấy ổ dữ liệu ≥ 95% và **dừng vòng lặp**, đúng như
thiết kế chống tràn. Ổ E của máy này lúc đó ở 96%.

Đã thêm fixture `room_on_disk` (autouse) giả định ổ còn chỗ, cộng một test
riêng cho chính cơ chế chống tràn — nơi việc dừng lại là **kết quả mong đợi**
chứ không phải một điều kiện môi trường lẻn vào từ bên ngoài.

> Quy tắc: một test khẳng định "hành vi X xảy ra" phải **ghim mọi cửa chặn nằm
> trước X**. Nếu không, nó chỉ đúng trên máy của người viết.

### Khẳng định bằng phép trừ trên một cơ sở dữ liệu có sẵn dữ liệu

`test_consentCoverage_stopsCountingStaleConsentsAfterAReconsentRelease` khẳng
định `after["accepted"] == before["accepted"] - 1`. Phép trừ đó chỉ đúng nếu
tài khoản của test là chấp thuận hợp lệ **duy nhất** trong bảng.

Bộ test chạy trên **bản sao dữ liệu thật**, nơi đã có hàng chục chấp thuận — và
một lần công bố `requires_reconsent` làm tất cả cũ đi cùng lúc. Đo được: 11 → 0,
test đỏ vì số học chứ không phải vì hành vi.

Sửa bằng cách khẳng định điều docstring thật sự nói: `after < before`, tài
khoản đó chuyển từ có sang không (`has_consent`), và `missing` tăng. Ba khẳng
định đó đúng bất kể bảng có bao nhiêu dòng.

> Quy tắc: trên bản sao dữ liệu thật, **đừng khẳng định con số tuyệt đối hay
> hiệu số**. Khẳng định chiều thay đổi, và khẳng định ở mức bản ghi mà test tự
> tạo ra.

### Đăng ký thiếu số hiệu chấp thuận → 400, sáu test đỏ ở ba tệp

Công bố điều khoản **chính là** hành động bật cưỡng chế chấp thuận. Sau khi văn
bản pháp lý lên bản sao dữ liệu, mọi `POST /auth/register` không kèm
`accepted_terms_version` đều nhận 400 `consent_required`. Sáu test viết trước
đợt đó không hề biết.

`conftest.registration_consents()` đọc số hiệu **đang hiệu lực** rồi trả về các
trường tương ứng — nên nó đúng cả trên bản triển khai chưa công bố gì (không
đóng góp trường nào) lẫn bản công bố bản mới ngày mai. Viết cứng số hiệu sẽ cho
409 `stale_version`, tức là đổi một kiểu đỏ giả lấy một kiểu khác.

---

## 4ter. Hai cái bẫy tìm được ngày 2026-08-10 — về chính BỘ TEST

### Đừng gọi `rename_user` trong test: nó ghi vào `dataset/samples.csv` THẬT

`account_rename.rename_user` viết lại **nguồn sự thật** — tệp sản xuất, không
phải bản sao Postgres. Một test gọi nó vừa sửa dữ liệu thật của người dùng, vừa
làm **treo bộ test 8 phút** vì phải viết lại 3.860 dòng.

Cùng loại với bài học đã ghi ở §2.4: *bản sao Postgres không che được đường ghi
tệp*. Bản sao CSDL bảo vệ bảng, không bảo vệ đĩa.

Cách thay thế cho tính chất "nhãn tác giả không đổi theo lượt đổi tên": kiểm
bằng **cấu trúc** — khẳng định `support_messages` không xuất hiện trong
`app/account_rename.py`. Vừa an toàn, vừa chứng minh mạnh hơn (nó ghim rằng
*không có đường nào* để lượt đổi tên chạm tới bảng đó, chứ không chỉ rằng một
lần chạy cụ thể đã không chạm).

### jsdom báo `navigator.language = "en-US"`

Bốn test của khung đa ngôn ngữ đỏ vì khung **tự chọn tiếng Anh** — đúng như
thiết kế, và test mới là chỗ sai. Phải ghim `navigator.language` cho từng test:

```ts
Object.defineProperty(window.navigator, "language", { value, configurable: true });
```

Không ghim thì kết quả đổi tuỳ máy chạy, và đó là kiểu đỏ giả tốn nhiều giờ nhất
để chẩn đoán vì nó không tái lập được trên máy người khác.

### Một lần treo KHÔNG phải lỗi mã: cả stack đã tắt

Lượt chạy đầu tiên hôm đó treo 10 phút, không in một dòng nào. Nguyên nhân:
`docker ps` rỗng — Postgres và Redis không chạy. `connect_postgres` thử lần lượt
6 tên máy chủ trước khi bỏ cuộc, và thông báo lỗi cuối cùng nói `host=localhost`,
làm nó **trông như** lỗi cấu hình DSN.

Kiểm `docker ps` trước khi chẩn đoán một lượt treo.

### Biến thể ngày 2026-08-10: stack biến mất GIỮA CHỪNG

Cùng nguyên nhân, triệu chứng ngược hẳn — không treo, mà **26 đỏ + 208 lỗi**.
Bộ test chạy trót lọt 1.551 test rồi mới sập hàng loạt, vì container bị rút ra
từ dưới chân lúc đang chạy (`docker info` sau đó báo `containers=0`; volume và
image còn nguyên, nên không mất dữ liệu).

Một đống đỏ **trông** giống hồi quy hơn một lượt treo rất nhiều, và đó là chỗ
bẫy. Dấu hiệu phân biệt nằm trong log, không nằm ở số lượng:

```
Postgres host lookup failed for postgres, trying next candidate
Redis connection failed: Error -2 ... Name or service not known.
```

Tên máy chủ **không phân giải được** thì đó là mạng, không phải mã. Một hồi quy
thật không làm DNS hỏng.

Chạy lại sau khi `docker compose up -d postgres redis`: **1807 xanh, 0 đỏ**.

### Đừng nối `| tail` vào một lượt chạy nền

Lượt trên được gọi là `pytest -q 2>&1 | tail -25`, nên tệp output chỉ còn 25
dòng cuối: đủ để biết *có* đỏ, không đủ để biết *vì sao*. Chẩn đoán phải chạy
lại từ đầu — 13 phút cho một thông tin lẽ ra đã có sẵn.

Ghi cả lượt vào tệp rồi mới `tail` khi đọc:

```bash
docker run ... python -m pytest -q > "$LOG" 2>&1; echo "exit=$?"; tail -12 "$LOG"
```

---

## 5. Danh mục test — frontend (42 tệp)

| Nhóm | Tệp | Canh gì |
|---|---|---|
| Pháp lý | `Markdown.test.tsx` | cú pháp dùng trong văn bản pháp lý; **nội dung không trở thành mã chạy được** (`<script>`, `javascript:`, `data:`, `//`) |
| | `DraftEditor.test.tsx` | **409 phải GIỮ NGUYÊN bài đang gõ**; bảng chuyển trạng thái; nâng quyền rồi thử lại; xem trước dựng phần đang gõ |
| | `LegalDocumentPage.test.tsx` | dựng thân văn bản; `?version=` mở đúng bản đã ký; nói rõ "chưa công bố" thay vì trang trắng |
| | `RegisterPage.consent.test.tsx` | gửi kèm số hiệu vừa đọc; khoá nút khi chưa tích; xử lý `stale_version`; **vẫn chạy khi chưa công bố gì** |
| | `AdminLegalPage.test.tsx` | tách "đã đồng ý" khỏi "người dùng tự bấm"; "đã lên lịch" ≠ "đang áp dụng"; hỏi lại mật khẩu |
| | `AccountPage.test.tsx` | ký gửi bản ĐANG hiệu lực chứ không phải bản đã ký; nút khoá tới khi xác nhận đã đọc; rút phải qua bước xác nhận và **không hứa xoá tệp**; `guardian` không có nút ký; đổi tên phát `notifyAuthChange` để thanh bên không giữ tên cũ |
| Điều hướng | `RouteErrorBoundary.test.tsx` | nút quay lại vào một chunk lazy đã 404 không làm trắng trang; cờ tải lại không tự xoá khi có lỗi |
| | `useBackClosesOverlay.test.tsx` | nút quay lại đóng lớp phủ thay vì rời trang |
| | `useIdleLogout.test.tsx` | hết hạn phiên sau 3 giờ không thao tác |
| Thương mại | `BillingPage.test.tsx` | "không giới hạn" không bị vẽ thành thanh 0% |
| | `IntegrationsPage.test.tsx` | khoá API hiện đúng MỘT lần lúc tạo |
| Tổ chức | `AdminTenantsPage.test.tsx` | con số dòng sẽ mất hiện TRƯỚC ô xác nhận; nút xoá khoá tới khi gõ đúng mã; lý do chặn nhắc nguyên văn từ máy chủ; **phản hồi của tổ chức cũ về muộn không ghi đè tổ chức đang chọn**; 403 ở xem-trước-xoá không làm hỏng ba mục còn lại; mã mời hiện một lần |
| Dùng thử ẩn danh | `TrialGate.test.tsx` | **không dựng runtime khi chưa có phiếu** — dựng là bật camera của khách rồi mọi API trả 401; hết phút thì gỡ runtime xuống; đồng hồ chạy theo SỰ KIỆN từ header phản hồi, không phải một vòng gọi nữa |
| Gói & thanh toán | `AdminBillingPage.test.tsx` | **ô trống = KHÔNG GIỚI HẠN**, và trần không cho null thì chặn nút Lưu; chỉ gửi trường đã đổi; `sudo_required` → hỏi → thử lại ĐÚNG một lần; treo tổ chức không có lý do thì không treo |
| Xác minh & lời mời | `VerifyContactPage.test.tsx` | **mỗi lần chỉ một luồng mã mở** — `/verify/confirm` thử `verify_phone` trước, nên hai thử thách cùng sống sẽ ăn mòn lượt thử của nhau; SMS chưa bật thì nói ra thay vì để bấm rồi 503; 429 mở ô nhập mã vì mã cũ còn sống |
| | `ForgotPasswordPage.test.tsx` | **không khẳng định tài khoản tồn tại** — câu chung của máy chủ hiện nguyên văn; lọc ký tự lạ khỏi mã dán vào; xoá mã sai sau mỗi lần từ chối; nói rõ phiên cũ đã bị thu hồi. Cộng thêm **ranh giới ba bước**: không có lối tắt "đã có mã", bước mã không hỏi lại tên đăng nhập hay mật khẩu, bước mật khẩu không còn ô mã, vé hết hạn đưa về bước 1 chứ không phải bước 2 |
| | `InvitationPage.test.tsx` | mã đọc từ **fragment**, mã ở query string bị gỡ khỏi thanh địa chỉ; mã sang trang đăng ký qua state của router chứ không qua URL |
| | `useResendCountdown.test.ts` | đếm theo **đồng hồ tường** — tab ngủ 40 giây rồi tỉnh phải còn 20, không phải 59 |
| Kiểm toán | `AdminActivityPage.audit.test.tsx` | nhật ký bền hiện được và lọc theo tiền tố; **không nằm trong vòng poll 3 giây**; băm nguồn chỉ hiện 8 ký tự |
| Dữ liệu | `LabelsPage*.test.tsx`, `LabelDetailPage.test.tsx` | danh sách nhãn, điều hướng, chi tiết phiên |
| Trình xem | `viewer/__tests__/*` (7 tệp) | dựng khung xương, độ sâu bàn tay, điều khiển phát |
| Hạ tầng | `axiosClient.test.ts`, `nginxRouteCoverage.test.ts`, `subpathAssets.test.ts` | đường cơ sở `/voya`; mọi route API có mục nginx tương ứng |
| Tiện ích | `utils/*.test.ts`, `config/capture.test.ts` | hàm thuần |

---

## 6. Cạm bẫy đã mắc, ghi lại để không mắc lại

| Bẫy | Triệu chứng | Cách tránh |
|---|---|---|
| Ảnh `voya_backend_test` cũ hơn `requirements-dev.txt` | suite chết lúc **thu thập**, không phải lúc chạy | dựng lại ảnh trước khi nghi ngờ mã |
| Dùng chung Redis DB 0 | một tệp bắt đầu trả 429 ở lượt chạy thứ N | `redis://redis:6379/13`; mỗi request một IP mới qua `fresh_client_ip()` |
| `TestClient` mặc định | peer là `("testclient", 50000)`, không phải IP → `X-Forwarded-For` bị bỏ qua → mọi test dồn vào một xô | bọc app bằng `LoopbackPeer` |
| Ghi đè `require_admin` bằng `{"id": "t"}` | `published_by` là khoá ngoại UUID → INSERT vỡ, và lỗi đọc như lỗi endpoint | tạo tài khoản quản trị **thật** trong fixture |
| Bọc `fireEvent.click` trong `act(async …)` | test treo, không báo lỗi | `fireEvent` đã tự bọc `act` rồi — đừng lồng |
| Viết cứng số hiệu điều khoản trong test | 409 `stale_version`, đỏ vì lý do không liên quan | đọc bản đang hiệu lực từ `legal.current_document()` |
| Fixture xoá sạch bảng nền tảng | bản sao lệch khỏi sản xuất, sổ dấu vết im lặng | chụp và phục hồi ở phạm vi module |
| Chạy CLI ghi dữ liệu **song song** với suite | sổ dấu vết coi hàng vừa ghi là dấu vết của test và xoá đi | chạy tuần tự |
| `%` trong `LIKE` với `_fetch_all` | `IndexError: tuple index out of range`, thường bị `except` nuốt thành một dòng WARN — **phép kiểm không bao giờ chạy** | viết `%%`; `params=()` mặc định vẫn khác `None` nên psycopg2 vẫn nội suy |
| Test không đặt `LEGAL_STORE_ROOT` | ghi vào `dataset/legal` thật | fixture `temp_store` với `tmp_path` |
| Kiểm khoá lạc quan bằng hai lời gọi tuần tự | chỉ chứng minh câu `WHERE revision` có mặt, không chứng minh hai giao dịch chồng nhau không cùng thắng | `ThreadPoolExecutor` với hai luồng thật |
| Trigger chỉ-thêm + khoá ngoại `ON DELETE SET NULL` | `SET NULL` phát ra UPDATE → trigger chặn → **xoá bản ghi cha thất bại** | sổ đăng bạ không có khoá ngoại; giữ `actor_label` thay thế |
| Bọc `<input>` bên trong `<label>` | `getByLabelText` không tìm thấy ô, vì chữ của dòng gợi ý và dòng lỗi cũng nằm trong thẻ và bị tính vào TÊN của ô | nối bằng `htmlFor`; gợi ý và lỗi thuộc `aria-describedby`. Đây là lỗi tiếp cận thật, không chỉ lỗi test |
| `vi.mock` một module rồi thêm export mới vào module đó | `No "X" export is defined on the mock` — đỏ ở tệp test không liên quan | factory mock phải liệt kê đủ, hoặc `vi.importActual` rồi trải ra |
| Dọn dẹp viết ở CUỐI thân test | một `assert` đỏ nhảy ra trước khi tới đó, dữ liệu nằm lại | dọn ở fixture, sau `yield` |

---

## 7. Cổng trước khi triển khai

Bốn phép kiểm, chạy theo thứ tự, và không bỏ phép nào:

```bash
# 1. Backend
docker run ... voya_backend_test:latest python -m pytest      # kỳ vọng: 0 đỏ
#    và sổ dấu vết báo "0 hang con sot"

# 2. Frontend
cd frontend && npx vitest run                                  # kỳ vọng: 0 đỏ
              npm run typecheck                                # kỳ vọng: im lặng
              #   KHÔNG phải `npx tsc --noEmit` — lệnh đó kiểm không tệp nào
              npm run build                                    # kỳ vọng: build xong

# 3. Nợ lược đồ — phải sạch sau BA lần boot liên tiếp
docker compose exec backend python -c \
  "from app.storage.metadata_db import schema_debt; print(schema_debt())"

# 4. Kiểm tra triển khai
docker compose exec backend python -m app.cli.verify_deployment
```

Phép 3 chạy **ba** lần vì một lớp lỗi cụ thể chỉ hiện ở lần cài mới rồi tự lành
ở lần boot thứ hai — nghĩa là nó không bao giờ lộ ra lúc phát triển. Xem chú
thích `TENANT_FK_LOOP_SQL` trong `metadata_db.py`.
