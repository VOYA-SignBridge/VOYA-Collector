# Thí nghiệm cách ly tenant — bằng chứng thực nghiệm

> ## TRẠNG THÁI: `BLOCKED` — KHÔNG TRÍCH DẪN SỐ LIỆU Ở §7
>
> **Lượt đo ngày 15/08/2026 đã bị LOẠI KHỎI PHÂN TÍCH.** Không phải vì kết quả
> xấu, mà vì phép đo không chứng minh được rằng dụng cụ đang chạm đúng đối
> tượng: đối chứng dương đối với các tài nguyên đọc từ **hệ tệp** không đạt.
>
> Tài khoản `iso_user_a` không đọc được lớp và mẫu **của chính nó** (404). Khi
> đó, mọi kết quả "đã chặn" ở nhóm đối kháng không phân định được giữa *cách ly
> hoạt động đúng* và *tài khoản vốn không đọc được gì*. Một phép đo không thể
> thất bại thì không đo gì cả.
>
> Nguyên nhân: đường đọc lớp/mẫu không thuần PostgreSQL — `list_classes()` đọc
> `labels.csv` trên đĩa — trong khi fixture chỉ ghi vào PostgreSQL, và backend đo
> khi ấy không mount cây dataset nào.
>
> **Phần nào còn giá trị.** Trong 630 lần thử đối kháng, 390 ca trả `403` và 120
> ca trả `401` đi qua đường PostgreSQL và tầng xác thực thật (tenant, thành
> viên, billing) — chúng vẫn là bằng chứng hợp lệ cho những đường đó. 120 ca
> `404` trên đường lớp/mẫu thì không, vì chúng trả 404 cho **cả chủ sở hữu**.
> Không được dùng 390 ca kia để cứu 120 ca này.
>
> **Blocker hiện tại:** chưa tồn tại bước nào tạo ra cùng một fixture logic trên
> cả PostgreSQL lẫn kho tệp. `seed_measurement_datastore.py` ghi CSV và tệp;
> `seed_isolation_fixture.py` ghi PostgreSQL; không bộ nào phủ cả hai. Giao thức
> đã được bổ sung đối chứng dương theo từng phương thức, fixture hệ tệp
> dùng-một-lần và kiểm hậu điều kiện trên cả cơ sở dữ liệu lẫn hệ tệp; phép đo
> sẽ được thực hiện lại sau khi bước gieo nhất quán hoàn tất.
>
> Không có CTIVR/UASR/SVSR định lượng mới cho tới khi đối chứng dương đạt.

*Số liệu thô của lượt đã bị loại: `MEASUREMENT_tenant_isolation.json`.
Fixture: `MEASUREMENT_tenant_isolation_fixture.json`.*

Tài liệu này mô tả một phép ĐO, không phải một bộ kiểm thử. Bộ test trả lời "có
hồi quy không"; phép đo trả lời "tỉ lệ vi phạm là bao nhiêu". Chỉ cái thứ hai
lên bảng trong quyển.

---

## 1. Vì sao cần phép đo này khi đã có bộ test RLS

Chương 2 đã lập luận rằng kiểm siêu dữ liệu — "chính sách có tồn tại không",
"`FORCE ROW LEVEL SECURITY` đã bật chưa" — là chưa đủ. Một chính sách tồn tại
vẫn có thể không được hỏi tới, vì truy vấn đi đường khác, vì vai chạy có
`BYPASSRLS`, hoặc vì tầng ứng dụng đặt sai ngữ cảnh.

Phép kiểm có giá trị hơn là **chạy hành vi thật bằng đúng vai runtime**: đặt
ngữ cảnh tenant A, rồi thử đọc và ghi tài nguyên của tenant B qua chính API mà
người dùng dùng. Bộ test RLS hiện có kiểm ở tầng CSDL; phép đo này bổ sung một
lớp bằng chứng từ **phía API**, tức là qua toàn bộ chuỗi xác thực → phân giải
tenant → phân quyền → truy vấn.

## 2. Môi trường

Thí nghiệm KHÔNG chạy trên cơ sở dữ liệu sản xuất. Bộ thử cố tình phát `DELETE`
tenant, `DELETE` mẫu và `DELETE` lớp; cả ba phải bị chặn, nhưng phép đo tồn tại
chính vì điều đó chưa được chứng minh. Nếu cách ly thủng, phép đo sẽ chứng minh
bằng cách xoá thật.

| | |
|---|---|
| Ảnh ứng dụng | cùng ảnh với sản xuất, chỉ khác biến môi trường |
| Cơ sở dữ liệu | `signdb_test` (schema v5, 59 bảng) |
| PostgreSQL | 17.10 |
| Vai runtime | `voya_test_app` |
| `rolsuper` | `false` |
| `rolbypassrls` | `false` |
| RLS | chính sách thật trên lược đồ thật, không mock |
| Commit | `f882414` (cây làm việc còn thay đổi chưa commit — ghi trong artifact) |

Danh tính runtime được xác nhận bằng cách **hỏi cơ sở dữ liệu**
(`current_database()`, `current_user`, `pg_roles`), không bằng cách đọc lại
chuỗi DSN đã truyền vào. Ngoài ra hai vai test đã bị thu hồi quyền `CONNECT`
vào `signdb` ở tầng PostgreSQL, nên một DSN viết sai bị chính cơ sở dữ liệu từ
chối chứ không phải trông chờ một lớp mã bắt được.

Dựng lại bằng `scripts/isolation_backend.sh up`.

## 3. Fixture

Hai tenant thật, mỗi bên có tài khoản, workspace, project, lớp và mẫu.

Điều kiện quan trọng nhất của fixture: **tài nguyên của B phải TỒN TẠI**. Nếu
không, máy chủ trả 404 vì không có gì để trả, và bộ đo sẽ chấm là "đã chặn" —
một điểm tuyệt đối kiếm được từ hư không. Nói cách khác, fixture phải làm cho
phép thử *có khả năng thành công sai*; một bộ đo không thể thất bại thì không đo
gì cả.

Script gieo kết thúc bằng khẳng định mỗi bên đọc được tài nguyên của chính mình,
và chỉ khi đó phép đo mới được phép chạy.

## 4. Ma trận phép thử

| nhóm | ý nghĩa | chỉ số |
|---|---|---|
| A | đúng tenant, **sai quyền** | UASR |
| B | đúng quyền, **sai tenant** | CTIVR |
| C | sai cả hai | CTIVR |
| X | đường công khai/cộng đồng | không tính vào chỉ số nào |

Các chiều đã thử: đọc tài nguyên của B; sửa (`PUT`); xoá (`DELETE`); tạo tài
nguyên con mang `tenant_id` của B trong thân yêu cầu (ca mà `WITH CHECK` phải
bắt, khác ca đọc mà `USING` bắt); đoán định danh không tồn tại; gọi khi chưa
đăng nhập; gọi bằng token rác; đọc hồ sơ và danh sách thành viên của tenant B;
tự nâng gói; liệt kê mọi tenant; xoá và treo tenant B.

**Ngoại lệ công khai được kiểm riêng.** Bất biến của hệ thống là: chéo-tenant
mặc định bị cấm, còn công khai và cộng đồng là ngoại lệ *tường minh*. Gộp chúng
vào cùng mẫu số sẽ đếm mỗi lượt đọc bảng giá thành một vụ xuyên tenant. Nhưng
cũng không bỏ qua: một ngoại lệ ngừng hoạt động là hồi quy chức năng.

## 5. Ba kết cục, không phải hai

```
CHẶN            401 / 403 / 404 sau khi đường dẫn đã được xác minh là có thật
VI PHẠM         yêu cầu trái tenant thành công, hoặc tạo ra thay đổi dữ liệu
KHÔNG KẾT LUẬN  429, 5xx, timeout, lỗi truyền, 4xx khác
```

**5xx không được tính là chặn.** Một lỗi máy chủ có thể xảy ra *sau* khi tác
dụng phụ đã ghi xuống đĩa; đếm nó thành "đã chặn" là cách nhanh nhất để công bố
CTIVR = 0 cho một hệ thống đang rò.

Mẫu số là số lần thử **kết luận được**, không phải tổng số lần thử: để ca không
kết luận được trong mẫu số sẽ kéo tỉ lệ vi phạm xuống, tức càng nhiều ca mờ thì
con số càng đẹp. Và dù mẫu số đã đúng, **không công bố khi số ca mờ khác 0**.

## 6. Chốt chặn đường dẫn — và vì sao nó bắt buộc

Trước khi phát yêu cầu nào, bộ đo đối chiếu mọi đường dẫn và **động từ** với
`/openapi.json` của chính máy chủ; sai thì thoát mã 3 và không chạy.

Lý do: một hệ cách ly tốt thường trả 404 thay vì 403 để không tiết lộ rằng tài
nguyên có tồn tại. Nhưng một đường dẫn gõ sai *cũng* trả 404. Từ phía khách,
hai thứ đó không phân biệt được, nên bộ đo sẽ chấm điểm tuyệt đối cho chính lỗi
của nó.

Điều này không phải giả thiết. Bản đầu của bộ đo nhắm vào `/api/v1/samples/…` và
`POST /api/v1/classes` — cả hai không tồn tại. Khi thêm chốt, nó lập tức chặn
lượt chạy và chỉ ra năm phép thử dùng sai động từ: `/classes/{id}` chỉ nhận
`DELETE` và `PUT`, `/dataset/samples/{id}` chỉ nhận `DELETE`.

## 7. Kết quả — ĐÃ BỊ LOẠI, giữ lại để đối chiếu

> Toàn bộ mục này thuộc lượt đo bị loại (xem khối trạng thái đầu tài liệu).
> Giữ lại vì phân bố mã trả về là thứ chỉ ra chính xác phần nào của phép đo
> không chạm tới lớp cách ly nào. **Không trích dẫn CTIVR/UASR/SVSR ở đây.**

**720 phép thử: 630 đối kháng + 90 ngoại lệ công khai.**

| nhóm | lượt | chặn | vi phạm | không kết luận |
|---|---|---|---|---|
| A — đúng tenant, sai quyền | 150 | 150 | 0 | 0 |
| B — đúng quyền, sai tenant | 390 | 390 | 0 | 0 |
| C — sai cả hai | 90 | 90 | 0 | 0 |

```
CTIVR = 0,0000      0 vi phạm / 480 lần thử kết luận được (nhóm B + C)
UASR  = 0,0000      0 vi phạm / 150
SVSR  = 0,0000      0 vi phạm / 630
không kết luận = 0  ->  đủ điều kiện công bố
```

Phân bố mã trả về: `403 × 390`, `404 × 120`, `401 × 120`, `200 × 90`.

**Mẫu số CTIVR là 480 chứ không phải 630** vì nhóm A nhắm vào tài nguyên của
*chính tenant mình* bằng một vai không đủ quyền — theo định nghĩa nó không thể
là vi phạm xuyên tenant, mà là vi phạm phân quyền, và đi vào UASR.

**Tính không phân biệt được**: tài nguyên của tenant khác và tài nguyên không
tồn tại đều trả `404`. Đạt.

**Ngoại lệ công khai**: bảng giá, văn bản pháp lý, thống kê cộng đồng — đều đạt.

## 8. Hậu điều kiện

Mã HTTP là chưa đủ. `DELETE` trả 404 không chứng minh được là không có gì bị
xoá: một xử lý có thể xoá hàng rồi mới ngã ở bước kiểm quyền. Sau khi bắn xong,
đọc lại cơ sở dữ liệu:

| tenant | tenant còn | lớp còn | mẫu còn | vân tay nội dung lớp |
|---|---|---|---|---|
| `iso_a` | có | có | có | `d80ee93a3494fead` |
| `iso_b` | có | có | có | `665069939b3d5391` |

Vân tay là băm của `label_original|slug|dialect`, để bắt cả `UPDATE` lén mà phép
đếm bỏ qua.

## 9. Giới hạn của tuyên bố

**Chưa có tuyên bố định lượng nào được phép rút ra.** Lượt đo đã bị loại; xem
khối trạng thái đầu tài liệu. Câu từng viết ở đây — *"0 vi phạm trên 480 lần thử
xuyên tenant kết luận được"* — đã được rút lại vì đối chứng dương không đạt.

Điều duy nhất còn đứng, và chỉ ở mức định tính: các đường đọc từ PostgreSQL
(tenant, thành viên, billing) từ chối truy cập chéo tenant bằng `403`, và các
lượt gọi không có ngữ cảnh hợp lệ bị từ chối bằng `401`, dưới vai runtime không
có `SUPERUSER` và không có `BYPASSRLS`. Không kèm tỉ lệ, vì mẫu số của một phép
đo có đối chứng dương trượt thì không nói lên điều gì.

Ngoài ra, không được rút ra những điều sau — kể cả sau khi phép đo được chạy lại:

* **Cách ly phạm vi workspace/project chưa được chứng minh.** Bảng `workspaces`
  và `projects` tồn tại trong lược đồ, nhưng API **không có một endpoint nào**
  cho chúng, nên không có gì để thử từ phía ngoài. Điều này được ghi thẳng vào
  artifact ở trường `khong_kiem_duoc`.
* **Chưa chứng minh cô lập hiệu năng.** Có hạn mức và giới hạn tần suất không
  phải bằng chứng cho việc một tenant không làm chậm tenant khác; muốn tuyên bố
  điều đó phải có thí nghiệm tải riêng — tạo tải ở A rồi quan sát B.
* **Chưa chứng minh cách ly trước một vai ứng dụng bị chiếm.** Phép đo này chạy
  ở Mức I: cách ly được cưỡng chế bởi cơ sở dữ liệu khi ngữ cảnh tenant do ứng
  dụng khai báo là đúng. Vai `voya_app` tự khai `app.tenant_id`, nên kẻ chiếm
  được vai đó vẫn đặt được ngữ cảnh tuỳ ý. Xem `TENANT_ISOLATION_AND_AUTHZ.md`
  §4.3 và §10.
* **Bề mặt đã thử là hữu hạn.** 630 phép thử phủ các đường trong ma trận ở §4,
  không phủ toàn bộ 344 đường của API.

## 10. Dựng lại

```sh
bash scripts/provision_test_db_roles.sh          # một lần, cấp phát vai test
sh   scripts/isolation_backend.sh up             # backend riêng -> signdb_test
docker cp scripts/seed_isolation_fixture.py voya_backend_iso:/tmp/
docker exec voya_backend_iso python /tmp/seed_isolation_fixture.py
# đăng nhập iso_user_a / iso_user_b (mật khẩu in trong fixture) để lấy token
docker exec voya_backend_iso python /tmp/adv.py --base http://127.0.0.1:8000 \
    --tenant-a iso_a --tenant-b iso_b --token-a "$TA" --token-b "$TB" \
    --class-a … --class-b … --sample-b … --repeat 30 \
    --dsn "$DATABASE_URL" --fixture /tmp/iso_fixture.json --json /tmp/iso_report.json
sh   scripts/isolation_backend.sh down
```

## 11. Việc còn nợ

* `seed_isolation_fixture.py`: một lượt tạo `perf_user` đã in ra thành công
  nhưng hàng không có trong cơ sở dữ liệu, kể cả khi đọc bằng `admin`
  (superuser, không chịu RLS). Chèn lại bằng đúng đoạn mã ấy thì thành công.
  **Nguyên nhân chưa xác định.** Không ảnh hưởng tới kết quả ở §7 — fixture
  dùng cho phép đo đã được khẳng định lại bằng truy vấn sau khi bắn — nhưng
  đây là một lỗi chưa đóng.

---

## 12. Ghi chú lưu giữ artifact — 16/08/2026

Cây pháp y `.measurement/iso-20260815-180124-d011ee` từng chứa trạng thái
split-brain quan sát được sau ca C đã bị xoá bởi một lượt seed/cleanup sau đó.
Ảnh chụp PostgreSQL trích **trước** khi cây bị xoá vẫn còn tại
`.measurement/evidence/forensic_db_rows_20260816T0148.json`
(SHA-256 `fdcd05820728bf7cd38a67421aa8f4fe651ade3c028b6ca3339237beacfd2ded`,
trích lúc 2026-08-16 01:48); artifact CSV và `.npz` gốc **không còn khả dụng để
tái kiểm trực tiếp**.

Vì vậy, các kết quả lịch sử ở §7 vẫn được giữ nguyên như quan sát tại thời điểm
đo, nhưng trạng thái file-plane của cây gốc **không còn có thể dựng lại
bit-for-bit** từ artifact hiện hữu. Hai khái niệm dưới đây từ đây trở đi không
còn trùng nhau, và không được viết như thể chúng trùng:

    historical observation              vẫn giữ nguyên giá trị, không sửa
    currently retained artifact         chỉ còn vế PostgreSQL

Nguyên nhân trực tiếp: `scripts/seed_cross_store.py` dọn theo **mặc định** mọi
thư mục `iso-*` có tệp đánh dấu. Đã sửa cùng ngày:

* dọn trở thành `--cleanup-previous`, phải xin tường minh; mặc định là GIỮ
* dọn chỉ chạm **đúng prefix** đang gieo (`iso-` không với tới `repro-`)
* tệp `.retain` trong một cây khiến mọi lệnh dọn bỏ qua cây đó
* cùng chốt chặn `.retain` được thêm vào `seed_measurement_datastore.py`

## 13. Vòng đo hồi quy — 16/08/2026 (fixture TÁI HIỆN, không phải cây pháp y)

Cây `.measurement/repro-20260816-003005-b16118` là **reproduction fixture**, sinh
mới hoàn toàn. Nó KHÔNG phải bản khôi phục của cây pháp y và không được dùng để
xác nhận lại các con số ở §7.

### 13.1 Môi trường đã đóng băng

`run_manifest.json` trong chính cây fixture. Trích yếu:

| | |
|---|---|
| `git HEAD` | `f882414a` (cây làm việc CÓ thay đổi chưa commit: 124 dòng) |
| image | `voya_backend:iso-p0-20260816` / `sha256:288496f0fe3f…` |
| container | `a2090d640d72` |
| CSDL | `signdb_test`, `current_user = voya_test_app` |
| vai | `rolsuper = false`, `rolbypassrls = false` |
| mã trong container | 8/8 tệp khớp băm với cây làm việc |
| `dataset_fixture_hash` | `949fa9bbfa243cbc…` |

Băm mã đọc từ **bên trong** container, không suy từ tag ảnh. Lần chạy trước đó
đúng phép kiểm này bắt được `catalog_sync.py` trong container còn là bản cũ.

### 13.2 Kết quả

| Ca | Nội dung | HTTP | DB | CSV | tệp | `file_path` |
|---|---|---|---|---|---|---|
| **T4** | A chủ sở hữu, mẫu A → lớp khác của A | **200** | đổi | đổi | đã chuyển | đã cập nhật |
| **T0** | A → lớp KHÔNG TỒN TẠI (mốc so sánh) | 400 | — | — | — | — |
| **T1** | A → lớp của **B** | 400 | — | — | — | — |
| **T2** | quản trị A (vượt quyền sở hữu) → mẫu của **B** | 404 | — | — | — | — |

`—` nghĩa là **không mặt phẳng nào đổi**, kiểm bằng ảnh chụp trước/sau của cả
bốn mặt phẳng, trong đó `samples.csv` đọc THÔ (không lọc tenant) để một hàng bị
ghi sai tenant vẫn nhìn thấy được.

T4 hội tụ cả ba kho: `class_uid` đổi ở cả PostgreSQL lẫn CSV, tệp `.npz` chuyển
sang `features/_tenants/iso_a/vn/bac/iso_a-target/`, và `file_path` trỏ đúng vị
trí mới — không treo.

### 13.3 Không phân biệt được tài nguyên tenant khác với tài nguyên không tồn tại

Thân phản hồi chỉ khác nhau ở **tiếng vọng của chính đầu vào người gọi cung
cấp**; sau khi chuẩn hoá phần tiếng vọng, hai thân giống hệt:

```
T0  {"detail":"Target class khongtontai0000 not found"}
T1  {"detail":"Target class isobtarg504e83 not found"}
    -> chuẩn hoá -> {"detail":"Target class <REF> not found"}   GIỐNG HỆT
```

Ở cổng đọc, hai thân **giống nhau từng byte**, không cần chuẩn hoá:

```
lớp nguồn của tenant B (CÓ THẬT)  -> 404 {"detail":"Không tìm thấy nhãn"}
lớp nguồn KHÔNG TỒN TẠI          -> 404 {"detail":"Không tìm thấy nhãn"}
```

Ca thứ hai (`T2b`) là mốc so sánh bắt buộc: một mình "T2 trả 404" không phân
biệt được *cách ly chặn* với *hỏng ở đâu đó*.

### 13.4 T2 chặn ở cổng ĐỌC, không phải cổng GHI

Sau khi `_get_class_or_404` được đưa vào phạm vi, lượt gọi của quản trị viên A
dừng ngay ở bước phân giải **lớp nguồn**, trước khi tới `sync_reassign_sample`.
Đó là kết quả đúng, nhưng nó có nghĩa là T2 **không còn** kiểm cổng phạm vi ở
phần ghi. Hai cổng vì thế được chứng minh riêng:

* cổng đọc — T2/T2b ở trên
* cổng ghi — `backend/tests/test_reassign_multiplane_order.py::
  test_mau_cua_tenant_khac_khong_phan_giai_duoc_va_KHONG_cham_tep`

Gộp lại thì một ngày cổng đọc được nới ra (endpoint quản trị mới, đường xuất) và
cổng ghi hoá ra chưa từng có ai kiểm.

### 13.5 Một lỗi trong chính bản vá, do phép thử bắt được

`sync_reassign_sample` ban đầu kiểm phạm vi **sau** khi chuẩn hoá:

```python
scope = normalize_tenant_id(tenant_id)
if not scope:            # KHÔNG BAO GIỜ đúng
    raise ...
```

`normalize_tenant_id("")` trả `"default"` (có chủ ý — nó phục vụ các hàng CSV có
trước khi tenant tồn tại), nên cổng là **mã chết**: một lượt gọi thiếu tenant sẽ
chạy lặng lẽ với toàn quyền của tenant khởi tạo. Đã sửa: kiểm tham số **thô**
trước khi chuẩn hoá. Bắt được bởi ca `tenant_id=""` — một bộ test không có ca
"phạm vi rỗng" sẽ không bao giờ thấy lỗi này.

### 13.6 Trạng thái

```
P0-A  tenant resolution
      code patched
      require_tenant path verified (middleware -> ContextVar -> router)
      HTTP regression rerun on pinned environment: T4/T0/T1/T2 PASS

P0-B  measured partial-write failure
      DB-reject ordering patched
      T3 fault-injection 7/7 PASS
      full DB/CSV/filesystem atomicity REMAINS OPEN

Forensic artifact
      original file-plane artifact lost after external seed/cleanup
      DB snapshot retained + hashed
      historical observation preserved unchanged
      fresh reproduction fixture used for regression
```

### 13.7 Dựng lại vòng đo này

```sh
sh scripts/seed_cross_store.sh --prefix repro --cleanup-previous
VOYA_ISO_IMAGE=voya_backend:iso-p0-20260816 \
VOYA_ISO_DATASET="<đường dẫn tuyệt đối tới cây repro-*>" \
  sh scripts/isolation_backend.sh up
sh scripts/run_manifest.sh voya_backend_iso <cây> > <cây>/run_manifest.json
docker run --rm --network voya-collector_voya_network -v "<repo>:/src" -w /src \
  -e VOYA_MEASURE_DSN="<DSN owner tới signdb_test>" voya_backend:iso-p0-20260816 \
  python scripts/measure_reassign_gate.py --base http://voya_backend_iso:8000 \
    --fixture /src/<cây>/fixture.json --out /src/<cây>/reassign_gate.json
```
