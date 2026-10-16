# Bàn giao: gieo fixture nhất quán DB + CSV + tệp

**Một nhiệm vụ duy nhất.** Biến `scripts/seed_measurement_datastore.py` thành nơi
tạo VÀ tự chứng minh một fixture đo nhất quán trên cả ba kho. Khi bước này xanh,
phần isolation còn lại mới đáng chạy.

```
P1  latency     CLOSED / PUBLISHABLE   docs/00-thesis/MEASUREMENT_api_latency.{md,json}
P0  isolation   BLOCKED                fixture cross-store seeding chưa hoàn tất
```

Không có CTIVR/UASR/SVSR định lượng mới cho tới khi blocker này đóng.

---

## 1. Vì sao đây là blocker chứ không phải món nợ

Đường đọc lớp/mẫu **không thuần PostgreSQL**: `list_classes()` gọi `load_labels()`
và hàm đó đọc `labels.csv` trên đĩa. Hiện có hai bộ gieo, mỗi bộ phủ một kho:

```
seed_measurement_datastore.py   ->  CSV + tệp      (không chạm psycopg2)
seed_isolation_fixture.py       ->  PostgreSQL     (tenant, user, membership, 1 class + 1 sample)
```

Không bộ nào phủ cả hai. Hậu quả đã đo được: tài khoản `iso_user_a` nhận `404`
khi đọc lớp và mẫu **của chính nó**, nên mọi ca "đã chặn" ở nhóm đối kháng không
phân định được giữa *cách ly đúng* và *tài khoản không đọc được gì*.

## 2. Giao dịch có bù trừ

PostgreSQL và hệ tệp không nằm chung một giao dịch ACID được, nên seeder cần một
giao thức tường minh:

```
 1  sinh fixture_id mới
 2  dựng cây trong thư mục TẠM
 3  ghi labels.csv + samples.csv + tệp mẫu
 4  mở giao dịch DB
 5  bảo đảm tenant / user / membership tồn tại
 6  ghi đủ 8 class + 8 sample tương ứng
 7  COMMIT
 8  mở giao dịch DB MỚI để đọc lại
 9  đối chiếu DB <-> CSV <-> tệp
10  chỉ khi tất cả khớp mới ghi  fixture.json
                                 .tenant-isolation-fixture
                                 status = READY
```

Bước 4–9 hỏng bất kỳ chỗ nào:

```
status = FAILED
   -> chưa COMMIT thì rollback
   -> đã COMMIT thì dọn bù trừ, CHỈ các đối tượng thuộc fixture_id này
   -> xoá cây tạm
   -> TUYỆT ĐỐI không tạo marker READY
```

**Marker là bước cuối cùng.** `isolation_backend.sh` chỉ được nhận cây đã có
marker `READY`; không bao giờ mount một fixture đang tạo dở.

## 3. Tám đối tượng, một danh tính chuẩn

```
iso_a: control_read  control_update  control_delete  target
iso_b: control_read  control_update  control_delete  target
```

Mỗi đối tượng mang một danh tính duy nhất dùng xuyên ba kho:

```
fixture_id · tenant_id · role · class_uid · sample_uid
```

Seeder **không** được sinh một UID cho CSV rồi một UID khác cho DB và ánh xạ lại
sau. Ràng buộc của cơ sở dữ liệu là **một phần của hợp đồng fixture**, không phải
một lỗi phát hiện sau khi CSV đã ghi xong.

Bằng chứng cho điều đó, đã gặp thật: `sample_uid` từng được đặt là
`sacont702c2f` — 12 ký tự, có `s`/`o`/`t` không phải hex. `samples_uid_is_hex10`
đòi `^[0-9a-f]{10}$`, nên PostgreSQL từ chối còn CSV thì nhận. Cây fixture có bốn
mẫu mà cơ sở dữ liệu không có mẫu nào, và điều đó chỉ lộ khi đối chiếu tay.

Đã sửa: `sample_uid` = `<tenant a|b><vai trò c|d|e|f><8 hex>`, ví dụ
`ac55cf2662`. `class_uid` dùng tên ngắn khác nhau ở ĐẦU (`read`/`upd`/`del`/
`targ`) — lấy sáu ký tự đầu của tên vai trò cho ra `contro` cho cả ba đối chứng,
mười ký tự đầu giống hệt nhau.

## 4. Preflight — kiểm trước khi ghi

Đừng để PostgreSQL phát hiện thứ mà seeder tự biết được:

```
sample_uid khớp ^[0-9a-f]{10}$
class_uid  đôi một khác nhau
sample_uid đôi một khác nhau
tên vai trò phân giải ra ID khác nhau
không alias control_* nào trùng nhau sau khi cắt ngắn
```

## 5. Validator — sau khi ghi

Kiểm cả **thiếu lẫn thừa**, không chỉ "hàng mong đợi có tồn tại":

```
DB   : 8/8 class · 8/8 sample
CSV  : 8/8 class · 8/8 sample
Tệp  : 8/8 tệp mẫu tồn tại

DB.class_uid  == CSV.class_uid      (hai chiều)
DB.sample_uid == CSV.sample_uid     (hai chiều)
DB.tenant_id  == tenant của fixture
hash tệp      == hash trong manifest
```

## 6. Thu hẹp `seed_isolation_fixture.py`

Sau thay đổi:

```
seed_measurement_datastore.py  = SOT của fixture đo
seed_isolation_fixture.py      = nghỉ hưu, HOẶC chỉ còn helper tenant-user-membership
```

Phần tạo class/sample trong đó phải bỏ — để lại là dựng sẵn nguồn trôi tiếp
theo. Nếu nó đang có helper đúng cho tenant/user/membership thì **tái dùng hoặc
tách ra dùng chung**, đừng viết lại SQL lần thứ hai.

## 7. Sau khi seeder xanh mới chạm runner

Theo thứ tự, trong `adversarial_isolation.py`:

1. parser canonical cho `fixture.json` → một biểu diễn nội bộ duy nhất
2. chụp `target_integrity_before`
3. đối chứng dương theo read / update / delete, kiểm **ngữ nghĩa** không chỉ mã:
   - `read` trả đúng tài nguyên mong đợi
   - `update` thật sự đổi trạng thái ở nơi API có trách nhiệm cập nhật
   - `delete` thật sự biến mất ở các kho mà hợp đồng xoá yêu cầu
4. checkpoint `targets_before_controls == targets_after_controls`
5. pha đối kháng
6. hậu điều kiện PostgreSQL + CSV + hash tệp
7. `target_integrity_after` + bốn trường artifact

### Thời điểm tính `dataset_fixture_hash`

**Sau khi đối chiếu ba kho đạt, TRƯỚC khi chạy đối chứng dương.**

`control_update` và `control_delete` được thiết kế để làm biến đổi đối tượng
control, nên băm cả thư mục sau pha đối chứng rồi so với ban đầu sẽ luôn khác —
và khác biệt ấy là *mong đợi*, không phải hỏng. Hash này đại diện cho **trạng
thái ban đầu** của fixture; còn `target_integrity_before/after` đại diện riêng
cho tính bất biến của mục tiêu đối kháng.

Băm **manifest chuẩn hoá** — định danh DB cần thiết + dòng CSV + hash tệp —
không băm timestamp, đường dẫn tuyệt đối hay siêu dữ liệu hệ tệp, nếu không cùng
một fixture logic dựng lại sẽ cho hash khác một cách vô ích.

### Luật `measurement_status`

```
measurement_status = OK   chỉ khi ĐỒNG THỜI:
    positive_control_passed
&&  targets_untouched_after_controls
&&  environment_fingerprint_unchanged
&&  indeterminate == 0
&&  postconditions_passed
```

Sai một điều kiện thì chỉ số phải là chuỗi `NOT_PUBLISHABLE`, không phải `NaN`
rồi vẫn in bảng đẹp.

## 8. Những gì đã sẵn, không cần làm lại

Trong `adversarial_isolation.py`:

- nhóm `P` (đối chứng dương) chặn trước khi in bất kỳ tỉ lệ nào, thoát mã 4
- `NOT_PUBLISHABLE` dạng chuỗi ghi vào artifact khi đối chứng trượt
- hậu điều kiện ba miền: hàng DB, dòng CSV, băm nội dung tệp
- `--dataset-fixture`, `--sample-a`
- chốt OpenAPI kiểm cả **đường dẫn lẫn động từ**, thoát mã 3
- mẫu số CTIVR là số lần thử **kết luận được**, kèm `ctivr_ly_do_loai_tru`
- nhóm `X` (ngoại lệ công khai) tách khỏi mọi tỉ lệ

Trong `isolation_backend.sh`: mount cây dùng-một-lần qua `DATASET_ROOT`, từ chối
đường dẫn trông như kho thật, xác minh danh tính runtime bằng cách hỏi CSDL.

`scripts/seed_isolation_dataset.py` — bản trùng do tôi viết — **đã xoá**.
