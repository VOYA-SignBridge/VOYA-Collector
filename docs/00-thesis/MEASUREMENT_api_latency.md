# Đánh giá độ trễ API trong môi trường kiểm soát

*Đây KHÔNG phải thí nghiệm cô lập hiệu năng.* Chương 2 đã tự đặt giới hạn: có
hạn mức và giới hạn tần suất không chứng minh được rằng một tenant không làm
chậm tenant khác. Muốn khẳng định điều đó phải có thí nghiệm tải riêng — tạo tải
ở tenant A rồi quan sát độ trễ của tenant B. Tài liệu này không làm việc đó và
không được trích dẫn như thể có làm.*

*Chạy ngày 15/08/2026. Số liệu thô: `MEASUREMENT_api_latency.json` (môi trường
test, bảng chính) và `MEASUREMENT_api_latency_production.json` (đối chiếu).*

---

## 1. Giao thức

```
khởi động    50 lượt / điểm cuối / lượt chạy, KHÔNG tính vào thống kê
đo           1.000 lượt / điểm cuối / lượt chạy
đồng thời    1
lặp lại      3 lượt chạy độc lập
gộp          trung vị của BA giá trị p50/p95/p99, KHÔNG gộp 3.000 mẫu
```

Ba lượt được giữ riêng trong artifact. Gộp 3.000 mẫu lại sẽ giấu một lượt bất
thường: nếu lượt hai chậm gấp đôi vì máy bận việc khác, tổng mẫu vẫn cho một con
số trông hợp lý và không ai biết. Ba giá trị đặt cạnh nhau thì bất thường tự lộ,
còn trung vị thì không bị một lượt hỏng kéo đi.

Đồng thời = 1 vì đây là **độ trễ cơ sở**, không phải phép thử tải. Nó trả lời
"một yêu cầu tốn bao lâu khi không có ai tranh chấp", không trả lời "hệ thống
chịu được bao nhiêu yêu cầu mỗi giây".

### Ngưỡng công bố phân vị

Một phân vị chỉ có nghĩa khi đuôi của nó có đủ quan sát đứng sau. Yêu cầu tối
thiểu **5 quan sát trong đuôi**:

| phân vị | đuôi | cần ít nhất |
|---|---|---|
| p95 | 5% | 100 lượt phục vụ |
| p99 | 1% | 500 lượt phục vụ |

Thiếu thì để trống, không in. Với n = 1.000 thì p99 tựa trên 10 quan sát cuối.

## 2. Môi trường đo chính

| | |
|---|---|
| Container | `voya_backend_perf` — **riêng**, không phải container thí nghiệm cách ly |
| Ảnh ứng dụng | cùng ảnh với sản xuất |
| Cơ sở dữ liệu | `signdb_test` |
| `DATASET_ROOT` | cây rỗng do container tự tạo, **không mount fixture nào** |
| Kết nối | keep-alive, một kết nối cho cả lượt chạy |
| Vai runtime | `voya_test_app` (không `SUPERUSER`, không `BYPASSRLS`) |
| Gunicorn workers | 2 |
| Máy chủ | `127.0.0.1` — IPv4 cố định |
| Giới hạn tần suất | **cấu hình của môi trường đo, đã nâng trần** |
| Tài khoản | `perf_user` — vai **thường**, tenant `default` |

Hai điểm cần nói rõ vì chúng dễ bị hiểu sai:

**Nâng trần tần suất là một thuộc tính của môi trường đo, không phải "tắt một cơ
chế sản xuất rồi coi như nó không tồn tại".** Trần thật vẫn đang chạy trên sản
xuất — mục 5 dưới đây đo được nó chặn 868/1.200 lượt. Lý do nâng ở môi trường
test là kỹ thuật: 429 rơi vào nhóm không kết luận được và sẽ bào mỏng cỡ mẫu tới
mức không công bố được phân vị nào.

**Tài khoản đo là vai thường, không phải quản trị.** Đường quản trị đi nhánh mã
khác và bỏ qua một phần lọc theo tenant, tức sẽ đo một đoạn mã không phải đoạn
người dùng thật đi qua.

**Container đo phải TÁCH khỏi container thí nghiệm cách ly.** Không phải phòng
xa — hai sự cố đã xảy ra trong cùng một buổi. `voya_backend_iso` bị dựng lại lúc
16:54:14 giữa một lượt benchmark kết thúc lúc 16:57:37, và 213 lượt hỏng đi
thẳng vào bảng như thể là thuộc tính của máy chủ. Sau đó, khi cây fixture cách ly
được mount, `/classes/list` nhảy từ 22 byte lên 2.154 byte: cùng URL, cùng bảng,
khối lượng công việc khác hẳn. Trường hợp thứ hai nguy hiểm hơn — một container
sập thì thấy ngay, một workload bị đổi thì cho ra con số hoàn toàn đẹp.

Chốt chặn: vân tay container (id, `StartedAt`, ảnh, biến cấu hình, lệnh chạy)
được đọc trước và sau lượt đo. Khác nhau thì `measurement_status = INVALIDATED`
và không tổng hợp phân vị.

**`127.0.0.1` chứ không phải `localhost`.** Cổng chỉ mở trên IPv4; `localhost`
phân giải ra `::1` trước và mỗi lượt phải chờ hết hạn rồi mới lùi lại. Một lượt
đo mắc lỗi này cho p50 của `/health` là 2.063 ms — gấp 29 lần con số thật — và
bảng kết quả khi đó trông hoàn toàn bình thường.

## 3. Ba lớp đường đi

Không trộn vào nhau, vì mỗi lớp trả lời một câu khác nhau.

| lớp | trả lời câu gì |
|---|---|
| công khai | chi phí cơ sở của HTTP + backend, gần như không chạm CSDL |
| xác thực/đọc | thêm chi phí xác thực, phân giải tenant, truy vấn |
| theo tenant | đường dữ liệu thật, đi qua RLS |

Tên đường lấy từ `/openapi.json` của chính máy chủ. Một lượt đo trước đó dùng
tên nhớ theo lối REST quen thuộc — `/api/v1/labels`, `/api/v1/classes`,
`/api/v1/tenants/me` — và cả ba trả 404 trong khi bảng vẫn in ra một kết quả tử
tế cho các đường còn lại.

## 4. Kết quả — môi trường test

*Điền từ `MEASUREMENT_api_latency.json`, trung vị của 3 lượt, đơn vị mili giây.*

| lớp | điểm cuối | p50 | p95 | p99 | thân | quy mô |
|---|---|---|---|---|---|---|
| công khai | `/health` | 4,4 | 6,4 | 8,1 | 79 B | — |
| công khai | `/api/v1/billing/plans` | 6,8 | 8,8 | 10,7 | 2.419 B | 4 mục |
| xác thực/đọc | `/api/v1/auth/me` | 20,8 | 24,3 | 27,7 | 202 B | — |
| xác thực/đọc | `/api/v1/billing/me` | 28,3 | 33,1 | 39,4 | 1.729 B | — |
| theo tenant | `/api/v1/vocabulary/registry` | 16,3 | 18,9 | 25,9 | 4.499 B | — |
| theo tenant | `/api/v1/training/dataset-info` | 21,3 | 25,0 | 29,4 | 132 B | — |
| theo tenant | `/api/v1/classes/list` | 5,2 | 6,4 | 7,7 | 22 B | **0 mục** |

`measurement_status = OK`, vân tay container khớp trước/sau, 21.000/21.000 lượt
phục vụ, 0 lỗi ứng dụng, 0 lỗi truyền, 0 lượt bị giới hạn tần suất.

Ba lượt độc lập bám nhau rất sát — p50 của `/health` là 4,5 / 4,3 / 4,4 ms, của
`/billing/me` là 28,3 / 28,5 / 28,2 ms. Không lượt nào lệch, nên trung vị ba giá
trị không che giấu gì.

Cột **quy mô** là số mục mà preflight nhìn thấy ngay trước lượt đo. Nó có mặt vì
`/classes/list` đã từng trả 22 byte rồi 2.154 byte trên cùng một URL, chỉ vì một
thí nghiệm khác mount cây dataset — bảng độ trễ không hề đổi hình dạng.

> **Bắt buộc đọc kèm bảng.** `/classes/list` trả về **0 mục**. Con số 5,2 ms đại
> diện cho *đường xử lý tenant-scoped với tập kết quả rỗng* — xác thực, phân giải
> tenant, truy vấn, tuần tự hoá một danh sách trống. Nó **không** phải hiệu năng
> truy vấn một danh mục có dữ liệu, và không được dùng để suy ra bất cứ điều gì
> về khả năng mở rộng theo số lớp. Muốn tuyên bố điều đó thì phải là một thí
> nghiệm khác, với danh mục được nạp ở nhiều quy mô.

**`/classes/list` trả về tập rỗng (22 byte).** Tenant `default` có 63 lớp nhưng
tài khoản đo không thấy lớp nào; endpoint chỉ nhận `language` và `dialect`, không
có phân trang, nên đây không phải lỗi gọi thiếu tham số. Con số của nó vẫn đo
được chi phí đường truy vấn có RLS, nhưng **không** đại diện cho một danh mục có
dữ liệu. Số byte được ghi vào artifact chính là để người đọc thấy điều đó.

## 5. Đối chiếu với sản xuất — KHÔNG quy đổi

| môi trường | workers | điểm cuối | p50 | p95 | mục đích |
|---|---|---|---|---|---|
| Test | 2 | `/health` | 4,4 | 6,4 | phép đo chính |
| Production | 4 | `/health` | 10,3 | — | đối chiếu triển khai |
| Test | 2 | `/billing/plans` | 6,8 | 8,8 | phép đo chính |
| Production | 4 | `/billing/plans` | 15,5 | — | đối chiếu triển khai |

Sản xuất chậm hơn khoảng 2,3 lần ở cả hai đường, dù có gấp đôi số worker. Đây là
**khác biệt quan sát được giữa hai môi trường**, và tài liệu này dừng ở đó.

Không liệt kê nguyên nhân khả dĩ. Mọi yếu tố có thể nghĩ tới — kích thước dữ
liệu, tải nền, tầng mạng phía trước — đều chưa được cô lập bằng thực nghiệm, và
viết chúng ra dưới dạng "có thể do…" sẽ khiến người đọc chọn lấy một cái làm lời
giải. Chính buổi đo này đã có một lần như vậy: một cơ chế nghe hợp lý, tương
thích với dữ liệu, và sai (xem §6).

Cũng không nhân tỉ số 2,3× cho các điểm cuối khác. Việc nó đi ngược chiều với số
worker là bằng chứng đủ rõ rằng quan hệ giữa hai môi trường không phải một hệ số.

Bảng này **không có cột hệ số**, và số của môi trường test **không** được điều
chỉnh theo số của sản xuất.

Lý do: thời gian đáp ứng không tỉ lệ tuyến tính theo số worker. Các điểm cuối có
cấu trúc xử lý khác nhau — `/health` gần như không chạm cơ sở dữ liệu, còn
`/billing/me` chạy tám câu đếm. Pool kết nối, bộ đệm, bộ lập lịch, tải nền và
kích thước dữ liệu đều khác giữa hai môi trường. Lấy tỉ lệ từ hai điểm cuối rồi
nhân cho các điểm cuối khác sẽ biến một phép **đo** thành một phép **ước lượng**,
và không còn cách nào chỉ cho người đọc biết ranh giới nằm ở đâu.

Nếu sản xuất nhanh hơn hay chậm hơn, điều đó chỉ được diễn giải là **khác biệt
quan sát được giữa hai môi trường**.

**p95 và p99 của sản xuất để trống, và đó là kết quả chứ không phải thiếu sót.**
Trần tần suất thật chặn 868/1.200 lượt, để lại khoảng 66 và 44 lượt phục vụ mỗi
lượt chạy — dưới ngưỡng ở mục 1. Trần này không được nới trên sản xuất.

Hai phép đo được chạy **tuần tự, không song song**: hai tiến trình tranh CPU của
cùng một máy sẽ làm nhiễu cả hai, và khi đó chênh lệch giữa hai môi trường sẽ
phản ánh thứ tự lịch chạy chứ không phản ánh triển khai.

## 6. Phân loại lỗi

Ba loại, không gộp, vì chúng nói về ba thứ khác nhau:

| loại | nghĩa | có chặn công bố không |
|---|---|---|
| lỗi **ứng dụng** | 4xx bất ngờ, 5xx — máy chủ đã nhận và trả lời sai | **có**, tuyệt đối |
| lỗi **truyền** | mã 0 — kết nối đứt trước khi có phản hồi | không, nhưng luôn ghi kèm tỉ lệ |
| **429** | trần tần suất — hành vi đúng | không, nhưng bào mỏng cỡ mẫu |

Bản trước gộp cả ba thành một con số "lỗi thật" và chặn công bố vì đúng một cú
đứt kết nối trong 21.000 lượt. Cám dỗ khi đó là chạy lại cho tới khi số đẹp —
tức là chọn lượt chạy theo kết quả, cách nhanh nhất để có một bảng số vô nghĩa.
Tách ra thì không cần chạy lại lần nào: tỉ lệ lỗi truyền nằm ngay trong artifact.

### Một giả thuyết đã bị bác bỏ, ghi lại để không ai dùng lại

Lượt đo ngày 15/08/2026 có 213 lượt lỗi truyền. Giả thuyết đầu tiên là **cạn dải
cổng tạm** trên Windows: mỗi kết nối đóng lại để một socket ở `TIME_WAIT` 120
giây, trong khi dải cổng động chỉ có 16.384 (`netsh int ipv4 show dynamicport
tcp`), và ở khoảng 100 lượt/giây thì 21.000 kết nối sẽ chạm trần.

Giả thuyết ấy **sai**. Đối chiếu mốc thời gian cho thấy container phục vụ lượt
đo được dựng lại lúc 16:54:14 trong khi lượt đo kết thúc lúc 16:57:37, và toàn
bộ 213 lỗi rơi vào đúng một lượt chạy của điểm cuối đang đo khi ấy.

Hai con số về `TIME_WAIT` và dải cổng đều có thật và *tương thích* với hiện
tượng — đó chính là lý do nó thuyết phục. Nhưng tương thích không phải nhân quả,
và một lời giải nghe hợp lý mà không có bằng chứng là thứ khó gỡ nhất về sau.
Chốt chặn đúng cho tai nạn này là so vân tay container, không phải keep-alive.

## 7. Giới hạn của tuyên bố

* **Đây không phải phép thử tải.** Đồng thời = 1. Nó không nói gì về thông lượng
  hay hành vi dưới tải đồng thời.
* **Đây không phải phép thử cô lập hiệu năng.** Có hạn mức và giới hạn tần suất
  không phải bằng chứng rằng một tenant không làm chậm tenant khác. Chứng minh
  điều đó đòi hỏi một bài riêng: tạo tải ở tenant A rồi quan sát độ trễ của
  tenant B.
* **Số của môi trường test không phải số của sản xuất**, và không có phép biến
  đổi nào giữa chúng được đề xuất ở đây.
* **Bảy điểm cuối là đại diện, không phải toàn bộ.** API có 344 đường.

## 8. Dựng lại

```sh
sh scripts/isolation_backend.sh up          # backend test -> signdb_test
# đăng nhập perf_user để lấy token
MSYS_NO_PATHCONV=1 python scripts/measure_api_latency.py \
    --base http://127.0.0.1:8020 --token "$T" \
    -n 1000 --runs 3 --warmup 50 --nhan test \
    --json docs/00-thesis/MEASUREMENT_api_latency.json
```

`MSYS_NO_PATHCONV=1` là bắt buộc trên Git Bash: không có nó, `--endpoint
/api/v1/...` bị dịch thành `C:/Program Files/Git/api/v1/...` và toàn bộ lượt đo
trả lỗi kết nối.
