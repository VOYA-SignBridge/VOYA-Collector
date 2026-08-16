# Ma trận giả mạo SOT — kết quả đo

*Đo 16/08/2026. Chạy qua đúng đường consumer của ứng dụng
(`app.sot.reader_sync.sync_from_sot`), không phải qua helper.*

```
9/9 kịch bản thực thi và cho kết quả xác định
8   thoả thuộc tính mong đợi
1   phát hiện GIỚI HẠN THẬT (S7 — hồi quy phiên bản)
```

**Không đọc kết quả này là "SOT 9/9 đạt".** Phép đo hợp lệ ở cả chín ca; thuộc
tính bảo mật thì đạt ở tám. Ca thứ chín tìm ra một giới hạn có thật, và đó là
phần đáng giá nhất của lượt đo.

---

## 1. Ma trận

| Ca | Thuộc tính kiểm tra | Kết quả | Đánh giá |
|---|---|---|---|
| S1 | artifact + manifest + chữ ký đều hợp lệ | ACCEPT | **Đạt** |
| S2 | đổi ĐÚNG một byte trong artifact sau khi ký | REJECT | **Đạt** |
| S3 | sửa hash trong manifest, giữ chữ ký cũ | REJECT | **Đạt** |
| S4 | chữ ký hợp lệ về mật mã, người ký KHÔNG tin cậy | REJECT | **Đạt** |
| S5 | chữ ký hỏng | REJECT | **Đạt** |
| S6 | thiếu chữ ký khi chính sách đòi ký | REJECT | **Đạt** |
| S7 | hồi quy phiên bản | ACCEPT; không xoá tài nguyên mới, nhưng giá trị dùng chung bị lùi | **GIỚI HẠN** |
| S8 | phiên bản mới, nguồn tin cậy | ACCEPT | **Đạt** |
| S9 | công bố chỉ bổ sung, giữ hàng có sẵn trên máy chủ | ACCEPT | **Đạt** |

Thông báo từ chối lấy nguyên văn từ hệ, ghi trong `MEASUREMENT_sot_integrity.json`.

## 2. Vì sao S4 quan trọng hơn một phép kiểm hash

Kẻ tấn công dựng được một dataset khác, tính hash đúng, viết manifest đúng, rồi
tự ký bằng khoá Ed25519 **của hắn**. Chữ ký ấy hợp lệ về mật mã.

Nếu hệ chỉ hỏi *"chữ ký có hợp lệ không"* mà không hỏi *"hợp lệ theo khoá công
khai NÀO"* thì tính toàn vẹn đúng còn thẩm quyền sai. Hợp đồng phải là bốn vế:

```
ValidArtifact = IntegrityValid AND SignatureValid
                AND SignerTrusted AND VersionPolicyValid
```

S4 đo vế thứ ba và **đạt**: `verify_with_authorized()` trả về tên khoá đã đăng ký
chứ không trả boolean, nên "ai ký" là một phần của kết quả xác minh.

Vế thứ tư là chỗ S7 tìm ra giới hạn.

## 3. S7 — chi tiết, vì đây là phát hiện

Hợp đồng có hai vế, và chúng không giống nhau:

* (a) hệ có **từ chối** lùi phiên bản không?
* (b) nếu chấp nhận, việc lùi có **phá huỷ** trạng thái mới hơn không?

Đo được vế (b) cần hai lượt đồng bộ thật — phải có v2 **đã vào** cơ sở dữ liệu
rồi mới biết nó mất hay còn. Nên ca này nằm ngoài ma trận tham số.

Kịch bản: v2 đang hiện hành, rồi `LATEST` được **ký hợp lệ bằng khoá tin cậy**
trỏ ngược về v1. Mọi hash và chữ ký đều đúng — đây là ca về *thẩm quyền phiên
bản*, không phải về *toàn vẹn*.

```
v2 hiện hành:  c1 = "hello-v2"   c2   c3 = "chi-co-o-v2"
        ↓  LATEST hợp lệ trỏ về v1
consumer:      ACCEPT
        ↓
c3 (chỉ có ở v2)          CÒN
c1 (khoá dùng chung)      "hello-v2"  ->  "hello"     ← lùi
hàng có sẵn trên máy chủ  CÒN
```

Kết luận chính xác: **lùi phiên bản không xoá tài nguyên, nhưng ghi đè lùi giá
trị trên khoá dùng chung.** Ngữ nghĩa superset giữ được vế "không phá huỷ"; nó
không giữ được vế "trạng thái mới hơn thắng".

Đừng gọi đây là "non-destructive" theo nghĩa rộng — `hello-v2 → hello` là mất
trạng thái mới hơn, dù không có `DELETE` nào chạy.

## 4. Ba thuộc tính, đừng trộn

```
Toàn vẹn (integrity)              ĐẠT
Xác thực nguồn (authenticity)     ĐẠT
Đơn điệu phiên bản (monotonic)    CHƯA CƯỠNG CHẾ
```

Câu dùng cho Chương 4:

> Cơ chế SOT phát hiện thay đổi đối với artifact hoặc manifest, từ chối chữ ký
> không hợp lệ hoặc không thuộc nguồn tin cậy, và xử lý fail-closed trong các
> tình huống xác minh được kiểm thử. Tuy nhiên, kiểm thử hồi quy phiên bản cho
> thấy một `LATEST` được ký hợp lệ vẫn có thể trỏ về phiên bản cũ. Cơ chế hợp
> nhất không xoá tài nguyên chỉ xuất hiện ở phiên bản mới hơn, nhưng các giá trị
> dùng chung giữa hai phiên bản có thể bị ghi đè bởi giá trị cũ. Vì vậy, cơ chế
> hiện tại cung cấp tính toàn vẹn và xác thực nguồn phát hành, nhưng **chưa cưỡng
> chế tính đơn điệu theo phiên bản**.

**Không** được nói *"dữ liệu không thể bị sửa"*. Hash và chữ ký cho **bằng chứng
giả mạo** (tamper evidence), không làm kho thành **chống giả mạo** (tamper-proof).

## 5. Truy vết cam kết O7

| Thuộc tính | Trạng thái |
|---|---|
| Signed integrity | **Đạt** |
| Tamper evidence | **Đạt** |
| Trusted authority | **Đạt** |
| Fail-closed verify | **Đạt** |
| Versioned artifacts | **Đạt** |
| Monotonic versioning | **Một phần / chưa cưỡng chế** |

Không sửa SOT sát ngày bảo vệ chỉ để biến S7 thành xanh. Một giới hạn đo được và
nêu rõ phòng thủ tốt hơn một bản vá vội chưa có thiết kế.

## 6. Phương pháp

**Một biến mỗi lần.** Mỗi kịch bản xuất phát từ một SOT **hợp lệ** rồi đổi đúng
một thứ. Một artifact "hỏng đủ thứ" bị từ chối không nói được cơ chế nào đã bắt,
và vẫn xanh kể cả khi hai trong ba cơ chế đã chết. S2 đổi `hello` → `hellp`:
không đổi độ dài, không đổi số dòng.

**Hậu điều kiện so trạng thái, không đếm lượt ghi.** Bộ test SOT sẵn có khẳng
định `total_upserts == 0` trên một catalog **rỗng**. Điều đó bỏ lọt một cách hỏng
thật: một lượt ghi đè hàng đang có rồi mới báo lỗi vẫn cho tổng bằng số cũ. Ở đây
catalog được **gieo sẵn**, chụp trạng thái trước, so sâu sau khi từ chối —
`state_before == state_after`.

**Quan hệ với 10 tệp test SOT sẵn có.** Chúng đã chạy qua đường consumer thật
(`sync_from_sot`, 25 lần ở 4 tệp), nên bài học *"hàm lá đúng không có nghĩa
workflow thật dùng hàm lá đúng cách"* ở SOT đã được xử lý sẵn — khác với trường
hợp cách ly tenant. Tệp này không chép lại chúng; nó thêm hậu điều kiện so trạng
thái, ca S6, và một artifact hợp nhất.

## 7. Vân tay nguồn — đọc kỹ trước khi trích dẫn

```
source_commit_base    f882414af302529f6dd9d8206aa9f0974986cd45
worktree_dirty        true
worktree_diff_sha256  2a3e5d5e501502c35c8b9d53ac6fddc3436b57edb6985be49a092770752ecc8a
source_tree_sha256    80daa72c2b92c904354f63c8997ab5144dd04a852f65775b3c368d673ee918fa
```

`source_commit_base` **không** định danh duy nhất implementation đã đo. Cây làm
việc còn thay đổi chưa commit, nên hai lượt đo cùng `HEAD` có thể chạy trên hai
implementation khác nhau — đúng kiểu sai lệch mà loạt phép đo này đã bắt nhiều
lần.

Thứ định danh được là `source_tree_sha256`: băm nội dung toàn bộ `backend/app/`,
độc lập với git sạch hay bẩn. Khi trích dẫn, gọi commit là **commit nền**.

Khi cây ngừng thay đổi, chạy lại và ghi lại vân tay.

## 8. Tái lập

```bash
sh scripts/measure_sot_integrity.sh
```

Wrapper lấy trạng thái git ở **host** (container test không cài `git`, nên bản
đầu ghi `source_commit: null` — im lặng mất đúng trường dùng để chứng minh phép
đo chạy trên bản mã nào) rồi ghi `.measurement/source_fingerprint.json`; phép đo
đọc tệp đó. Vắng tệp thì `worktree_dirty` ghi `"unknown"`, **không** ghi `false`
— một cây bẩn bị báo sạch còn tệ hơn không báo gì.

Kết quả: `MEASUREMENT_sot_integrity.json`, một bản ghi cho mỗi ca kèm lý do từ
chối nguyên văn.

**Không đo throughput ký/xác minh** — đề cương cam kết tính đúng đắn và toàn vẹn
ở trục này, không cam kết hiệu năng mật mã.
