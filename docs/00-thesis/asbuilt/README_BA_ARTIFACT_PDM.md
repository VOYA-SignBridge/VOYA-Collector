# Ba artifact mô hình dữ liệu — quy ước bắt buộc

Quyển dùng **ba** artifact, không phải hai. Artifact thứ ba là thứ giữ hai cái
đầu khỏi bị đọc nhầm thành nhau.

| Artifact | Trả lời câu hỏi | Nguồn |
|---|---|---|
| **PDM hiện thực** (as-built) | Hệ thống ĐANG CÓ gì | reverse trực tiếp từ lược đồ CSDL của revision đóng băng |
| **PDM kiến trúc mở rộng** (target/extended) | Thiết kế HƯỚNG TỚI gì | tệp DDL thiết kế + mô hình PowerDesigner cũ |
| **Ma trận sai khác** | Cái gì đã có, cái gì mới là thiết kế, **vì sao** | `ASBUILT_INVENTORY.md`, sinh tự động |

Ma trận là artifact quan trọng nhất trong ba. Không có nó, hai mô hình kia chỉ là
hai hình vẽ giống nhau, và người đọc không có cách nào biết hình nào mô tả một
CSDL mở ra xem được.

## Thứ tự thao tác, không đảo được

```
1. đóng băng revision Git
2. dựng signdb_test bằng ĐÚNG đường runtime hiện tại
3. reverse lược đồ đó   -> as-built
4. đối chiếu ensure_tables()
5. phân loại chênh lệch
6. chỉ nhóm `runtime` + `view` vào As-built PDM
7. SAU ĐÓ mới dựng target/extended
```

Bước 3 trước bước 4, không ngược lại:

```
lược đồ CSDL      "hệ thống ĐANG CÓ gì"       <- nguồn as-built
ensure_tables()   "mã HIỆN MUỐN tạo gì"       <- nguồn ĐỐI CHIẾU
```

Hai câu này không luôn cùng đáp án. Vụ chỉ mục bốn cột (17/08/2026) là bằng
chứng: mã đã chuyển sang khoá năm cột, nhưng chỉ mục cũ vẫn nằm trong CSDL cho
tới khi một câu `DROP` thật sự chạy. Một mô hình vẽ từ `ensure_tables()` không
thấy chỉ mục ấy — tức là vẽ **as-intended** rồi dán nhãn **as-built**.

Khi hai nguồn lệch, **không bên nào tự động thắng**. Phải điều tra lý do trước.

## Sáu phân loại — nghĩa đã khoá

| | nghĩa | vào As-built PDM? |
|---|---|---|
| `runtime` | đối tượng vật lý tồn tại và thuộc lược đồ runtime hiện hành | có |
| `view` | đối tượng runtime materialize dưới dạng **view** | có, **vẽ khác bảng** |
| `legacy` | CSDL còn đối tượng nhưng ý định lược đồ hiện tại không còn tạo | **không** — tồn dư, phải điều tra |
| `declared` | ý định lược đồ runtime có, ảnh chụp CSDL chưa materialize | không |
| `target-only` | chỉ thuộc **thiết kế/DDL** không tham gia runtime | không — sang Target PDM |
| `historical` | chỉ tìm thấy trong **bản chụp/backup lịch sử**; không được xem là ý định lược đồ runtime, cũng không phải kiến trúc mục tiêu hiện hành | không — và **không** sang Target |

Nhóm `historical` tách khỏi `target-only` vì hai loại chứng cứ ngược chiều nhau:

```
DDL trong backend/migrations/*.sql   "một lược đồ TỪNG ĐỊNH hiện thực gì"
CREATE TABLE trong một pg_dump       "CSDL TRƯỚC ĐÂY đã từng có gì"
```

Gộp chúng sẽ đưa `user_profiles` — chỉ có trong `backup.sql`, đầu ra `pg_dump`
ngày 30/07/2026 — vào Target PDM dưới nhãn "cấu phần kiến trúc mục tiêu", trong
khi sự thật ngược lại: nó là thứ **đã bị loại bỏ**.

### `legacy = 0` và `declared = 0` KHÔNG có nghĩa "lược đồ đồng bộ hoàn toàn"

Ở ảnh chụp hiện tại cả hai đều bằng không, và đó là kết quả tốt: CSDL và ý định
lược đồ runtime đang hội tụ **về mặt tồn tại của đối tượng**.

Nhưng phép đo chỉ so **tên bảng**. Nó không so ràng buộc, chỉ mục, policy,
trigger, hay ý định ngữ nghĩa. Câu được phép viết:

> Không phát hiện bảng runtime bị tồn dư hoặc bảng runtime được khai báo nhưng
> chưa materialize trong ảnh chụp được đo.

Câu **không** được phép viết: *"lược đồ đã đồng bộ hoàn toàn."*

Nhóm `view` được tách ra sau khi công cụ xếp `tenant_members` vào `declared`.
Bảng đó **có** materialize — dưới dạng VIEW trên `memberships`, kèm
`security_invoker`, đúng như PDM v5 quy định. "Chưa materialize" không chỉ sai;
nó mời người đọc đi tạo một bảng chồng lên một view đang phục vụ.

## Bốn lỗi của chính công cụ này, ghi lại để không lặp

Công cụ đo cũng là một thứ phải bị nghi ngờ. Bản đầu của
`scripts/reverse_asbuilt_schema.py` sai bốn chỗ, và cả bốn đều **cho ra kết quả
trông hợp lý**:

1. **Bảy "bảng" tên `ch`, `does`, `if`, `listing`, `sai`, `statements`.** Biểu
   thức khớp cụm `CREATE TABLE` trong VĂN XUÔI chú thích rồi lấy từ kế tiếp. Đã
   sửa bằng cách bắt buộc có dấu `(` sau tên bảng.
2. **`schema_migrations` bị xếp là tồn dư.** Mã VẪN tạo nó, qua
   `CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE}` — tên dựng bằng nội suy
   chuỗi, thứ một phép quét văn bản không thấy. Đây là kết luận nguy hiểm nhất
   trong năm nhóm: nó mời người đọc đi xoá một bảng đang dùng.
3. **`tenant_members` bị xếp là chưa materialize** — xem trên.
4. **Báo cây làm việc "sạch" trong khi `git rev-parse` đã thất bại.** Hai phép
   đọc để độc lập nhau, nên một lượt hỏng vẫn trả về giá trị trấn an. Một công cụ
   hỏng đưa ra con số yên tâm còn tệ hơn một công cụ im lặng.

Ba lỗi đầu tạo ra một ma trận sai khác **bịa**, và ma trận ấy sẽ đi thẳng vào
luận văn dưới dạng "đối tượng tồn dư đã phát hiện". Lỗi thứ tư làm mất luôn khả
năng biết phép chụp có hợp lệ hay không.

Giới hạn còn lại đã ghi thẳng trong tệp kết quả: tên bảng dựng động phức tạp hơn
một hằng chuỗi vẫn không giải được, và mục nào trong danh sách "chưa giải được"
nghĩa là ma trận **chưa đầy đủ**, không phải "không có gì".

## Sáu miền = sáu diagram

Không vẽ 58 bảng lên một hình. Một model duy nhất, nhiều diagram:

```
PDM-A  Tenant, IAM, Authorization
PDM-B  Danh mục VSL
PDM-C  Người ký, phiên thu, mẫu
PDM-D  Huấn luyện và hiện vật
PDM-E  Pháp lý, đồng thuận, kiểm toán
PDM-F  Control plane
```

Target/Extended dùng **đúng sáu miền đó**, để so được từng cặp `AsBuilt-C ↔
Target-C`. Thêm một sơ đồ tổng quan chỉ hiện bảng và quan hệ cấp cao, không bung
cột.

Bảng nào không khớp miền nào rơi vào `Z_chua_phan_loai` — cố ý hiện ra thay vì
bị nhét im lặng vào một miền sẵn có. Lượt 17/08/2026: 13 bảng rơi vào Z ở lần
chạy đầu, đã phân loại hết; Z hiện rỗng.

**Một bảng được phép nằm ở nhiều diagram.** Công cụ gán mỗi bảng đúng một miền vì
nó phải sinh ra một danh sách; PowerDesigner thì không bị ràng buộc đó, và ép một
lựa chọn duy nhất sẽ làm mất quan hệ.

Trường hợp cụ thể: `signer_consents` được gán vào **C** (khoá ngoại của nó trỏ
`signers`, nên vẽ ở C thì quan hệ hiện ra) trong khi câu chuyện của nó thuộc
**E**. Đúng cách là vẽ nó ở **cả hai**: ở C như một bảng con của `signers`, ở E
như một mắt xích của chuỗi đồng thuận. Danh sách do công cụ sinh ra là điểm khởi
đầu để dựng diagram, không phải phán quyết cuối cùng về chỗ đứng của từng bảng.

## Cái gì KHÔNG vào hình PDM

PowerDesigner không biểu diễn RLS policy gọn như FK hay constraint. Đừng cố nhồi
SQL của policy vào hình:

```
PDM              cấu trúc quan hệ
Bảng riêng Ch3   RLS / FORCE RLS / phạm vi policy
Bảng riêng Ch3   trigger giữ bất biến
```

Lý do không chỉ là thẩm mỹ: `relrowsecurity` (bật) và `relforcerowsecurity` (áp
cả cho chủ sở hữu bảng) là hai thuộc tính khác nhau và hay bị gộp. Bật mà không
force thì vai sở hữu đi xuyên qua mọi policy — và vai migration chính là vai đó.
Một hình vẽ chỉ có thể nói "có RLS"; một bảng thì nói được cả hai cột.

## Data Dictionary sinh từ As-built, không sinh từ target

Trộn `datasets`, `dataset_versions`, `model_versions` vào Data Dictionary chính
là dựng sẵn đúng câu hỏi ta đang tránh: hội đồng đọc Data Dictionary, mở CSDL,
và không thấy bảng. Thực thể kiến trúc mở rộng đi vào **một phụ lục riêng**, tên
nói rõ nó là gì.

## Caption — khoá cứng, không dùng chung

Hiện thực:

> Physical Data Model of the implemented CTU.SignBridge data subsystem
> (as-built at the frozen thesis revision).
>
> Mô hình dữ liệu vật lý của phân hệ CTU.SignBridge tại revision hiện thực được
> đóng băng.

Mở rộng:

> Extended physical data model representing the intended architectural evolution.
>
> Mô hình dữ liệu vật lý mở rộng theo kiến trúc định hướng.

**Không** dùng "Mô hình dữ liệu vật lý của hệ thống" cho cả hai.

## Câu dùng trong Chương 3

> Mô hình vật lý hiện thực được tái dựng từ lược đồ cơ sở dữ liệu của revision
> được đóng băng. Mã khởi tạo lược đồ được sử dụng để đối chiếu nhằm phát hiện
> các đối tượng tồn dư hoặc các thành phần được khai báo nhưng chưa được
> materialize trong runtime.

## Chạy lại

```sh
VOYA_TEST_CMD="python scripts/reverse_asbuilt_schema.py" bash scripts/run_tests.sh
```

Sinh ra `asbuilt_schema.json` (đầy đủ, để nạp vào công cụ) và
`ASBUILT_INVENTORY.md` (để đọc). Cả hai tự khai revision và trạng thái cây làm
việc. **Nếu tệp báo cây bẩn thì phép chụp đó chưa đủ tư cách làm as-built cho bản
nộp** — commit rồi chạy lại.
