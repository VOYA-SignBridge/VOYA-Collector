# Sao lưu và khôi phục

*Cập nhật 2026-08-08.*

Tài liệu này mô tả cách hệ thống được sao lưu, cách kiểm chứng bản sao lưu còn
dùng được, và cách khôi phục khi cần. Đọc mục [Khôi phục khẩn](#khôi-phục-khẩn)
trước nếu đang có sự cố; phần còn lại là để đọc lúc bình thường.

## Cái gì được sao lưu

Hệ thống có **hai** kho dữ liệu bền, không phải một.

| Kho | Nội dung | Sao lưu thành |
|---|---|---|
| Postgres `signdb` | 44 bảng: mẫu, lớp, người dùng, tenant, thanh toán, nhật ký kiểm toán, siêu dữ liệu văn bản pháp lý | `signdb_<stamp>.dump` (`pg_dump -Fc`) |
| `dataset/legal/` | **Thân** văn bản pháp lý, định địa chỉ bằng nội dung | `legal_<stamp>.tar.gz` |

Sao lưu một trong hai là sao lưu một nửa. Từ v6, `legal_documents` chỉ giữ
`storage_key`; thân văn bản nằm trên đĩa. Khôi phục thiếu kho tệp sẽ cho ra một
cơ sở dữ liệu khẳng định người dùng đã ký một văn bản mà không ai đọc lại được
văn bản đó — với dữ liệu chấp thuận thì đó là mất bằng chứng, không phải mất
tiện nghi.

### Cái gì KHÔNG được sao lưu, và vì sao

- **`dataset/features/**/*.npz`** — hàng nghìn tệp đặc trưng, đã đồng bộ lên
  Google Drive và dựng lại được từ `dataset/raw/`. Nhân đôi chúng vào một kho
  sao lưu theo ngày sẽ lấp đầy đĩa trong vài tuần mà không mua thêm gì.
- **Redis** — chỉ chứa trạng thái phù du: hàng đợi Celery, giới hạn tần suất,
  phiên. Mất Redis là mất tiện nghi, không phải mất dữ liệu. (Ngoại lệ đáng chú
  ý: `sec:log`, xem [OBSERVABILITY_PLAN.md](OBSERVABILITY_PLAN.md).)
- **Ảnh Docker và mã nguồn** — nằm trong git và trong registry.

## Service `pg-backup`

Định nghĩa trong `docker-compose.yml`, chạy `scripts/pg_backup.sh` trên ảnh
`postgres:17` (phiên bản client phải khớp server; xem ghi chú trong compose).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `BACKUP_INTERVAL_SECONDS` | `86400` | Chu kỳ giữa hai lượt |
| `BACKUP_KEEP_DAYS` | `14` | Giữ bao nhiêu ngày trước khi dọn |
| `BACKUP_HOST_DIR` | `./backups` | Thư mục trên **máy chủ**, không phải named volume |
| `LEGAL_STORE_DIR` | `/dataset/legal` | Kho văn bản, gắn chỉ-đọc |
| `BACKUP_PASSPHRASE` | *(trống)* | Trống = **không mã hoá**. Đặt ≥ 16 ký tự để bật AES-256 |
| `BACKUP_MIRROR_HOST_DIR` | `./backups` | Đường dẫn trên **máy chủ** cho bản sao thứ hai |
| `BACKUP_MIRROR_DIR` | *(trống)* | Đường dẫn **trong container**; trống = không chép bản thứ hai |

Thư mục sao lưu là **bind mount tới ổ đĩa chủ**, cố ý. Một bản sao lưu nằm
trong volume do Docker quản lý sẽ biến mất cùng `docker compose down -v` — đúng
lệnh mà người ta gõ khi đang cuống vì hỏng thứ gì đó.

### Bật service

```bash
docker compose up -d --no-deps pg-backup
docker compose logs -f pg-backup      # lượt đầu chạy ngay, không chờ hết chu kỳ
```

## Mã hoá và bản sao ngoài ổ

Cả hai **mặc định TẮT**, và cả hai in cảnh báo ở mỗi lần khởi động. Đó là chủ ý:
chọn không mã hoá phải là một quyết định, không phải một điều bị quên.

```
[pg-backup …] CẢNH BÁO: mã hoá TẮT — bản dump chứa email, số điện thoại, băm mật
[pg-backup …]           khẩu và chữ ký chấp thuận ở dạng đọc thẳng được.
[pg-backup …] CẢNH BÁO: chưa có bản sao ngoài. Thư mục sao lưu nằm CÙNG Ổ với
[pg-backup …]           dữ liệu, nên một sự cố ổ đĩa mất cả hai.
```

### Bật mã hoá

```dotenv
# .env  — tối thiểu 16 ký tự
BACKUP_PASSPHRASE=<chuỗi ngẫu nhiên dài, KHÔNG cất cùng ổ với bản sao lưu>
```

Rồi `docker compose up -d --force-recreate --no-deps pg-backup` (đổi `.env`
cần **force-recreate**, `restart` không nạp lại biến môi trường).

Tệp trở thành `signdb_<stamp>.dump.gpg` và `legal_<stamp>.tar.gz.gpg`. AES-256
qua gpg đối xứng, có kiểm toàn vẹn MDC — nên `gpg -d` phát hiện được cả tệp cụt
lẫn tệp bị sửa, không chỉ "sai mật khẩu".

**Thứ tự trong script là một phần của tính đúng:** tự kiểm chạy **trước** khi mã
hoá (`pg_restore` không đọc được tệp đã mã hoá), rồi bản đã mã hoá được **giải
mã thử một lượt** trước khi xoá bản rõ. Không có bước giải mã thử đó, thứ được
kiểm và thứ được giữ lại là hai tệp khác nhau — và cái được giữ chưa từng ai
đọc thử.

Mã hoá hỏng thì **bản rõ ở lại** kèm cảnh báo. Có một bản sao lưu dùng được mà
chưa mã hoá vẫn hơn không có bản nào.

> **MẤT MẬT KHẨU LÀ MẤT BẢN SAO LƯU.** Không có cửa sau. Cất mật khẩu ở nơi
> **không** nằm cùng ổ với bản sao lưu — nếu không thì cùng một sự cố lấy đi cả
> hai, và mã hoá chỉ đổi cách bạn mất dữ liệu chứ không ngăn được.

Khôi phục cần đúng biến đó trong môi trường; `pg_restore.sh` tự giải mã ra thư
mục tạm (`mktemp -d`) và **xoá khi thoát**, kể cả khi bị Ctrl-C. Thiếu mật khẩu
hoặc sai mật khẩu đều thoát 1 kèm câu giải thích, không âm thầm bỏ qua.

### Bật bản sao ngoài ổ

```dotenv
# .env — ví dụ với một ổ ngoài gắn ở F:
BACKUP_MIRROR_HOST_DIR=F:/voya_backups
BACKUP_MIRROR_DIR=/mirror
```

Hai biến chứ không phải một, vì chúng nói hai chuyện khác nhau: một là đường
dẫn trên **máy chủ**, một là đường dẫn **trong container**. Gộp lại là cách
chắc chắn để một hôm nào đó chép bản sao lưu vào một thư mục nằm ngay trên ổ
vừa hỏng.

Bản sao ngoài dọn theo cùng `BACKUP_KEEP_DAYS`. Chép hỏng **không** làm hỏng
lượt sao lưu — bản tại chỗ đã ghi xong và đã tự kiểm — nhưng nó kêu to, vì "có
bản ngoài" là điều người ta tin vào đúng lúc không kiểm lại được nữa.

**Chưa có bản sao ngoài MÁY.** Ổ ngoài cứu được sự cố ổ đĩa, không cứu được
cháy, trộm, hay mã độc tống tiền chạy với quyền ghi lên ổ đang gắn. Bước tiếp
theo là một bản ở máy khác hoặc ở dịch vụ lưu trữ — quyết định đó có ràng buộc
về dữ liệu cá nhân, và nếu chọn đám mây thì **phải bật mã hoá trước**.

### Ba lớp tự kiểm

1. **`pg_restore -f /dev/null`** trên bản dump vừa ghi — giải nén toàn bộ khối
   dữ liệu, tức chạm tới byte cuối cùng. Không đạt thì tệp bị đổi tên `.CORRUPT`
   chứ không bị xoá.

   > **Đừng thay bằng `pg_restore --list`.** Ở định dạng custom, mục lục nằm ở
   > *đầu* tệp, nên `--list` trả về 0 trên một bản dump bị cắt mất nửa sau — tức
   > nó mù với đúng kiểu hỏng mà bước tự kiểm tồn tại để bắt (hết đĩa, container
   > bị giết giữa chừng). Đã đo 2026-08-08: bản 585 KB cắt còn 200 KB →
   > `--list` cho 0 "đạt", `-f /dev/null` cho 1 "hỏng".
2. **Đối chiếu khoá kho pháp lý.** Mọi `storage_key` đang được một hàng trỏ tới
   phải có tệp tương ứng trong bản `.tar.gz`. Không đạt → `.CORRUPT`.
3. **Healthcheck** hỏi "có bản dump nào mới hơn hai chu kỳ không". Kiểm "tiến
   trình còn sống" thì vô dụng: một vòng lặp `sleep` vẫn sống nguyên khi mọi
   lượt dump đều thất bại, và đó chính là kiểu hỏng cần phát hiện.

Ba lớp này chứng minh bản sao lưu *đọc được*. Chúng không chứng minh nó *khôi
phục được* — việc đó là của diễn tập.

## Thứ tự hai kho, và vì sao nó quan trọng

Hai kho không thể chụp cùng một khoảnh khắc. Bất biến cần giữ là **mọi khoá
trong bản dump đều có tệp trong bản lưu trữ**; chiều ngược lại (lưu trữ có tệp
thừa) chỉ là blob mồ côi, vô hại.

```
T1  pg_dump                       ảnh chụp cơ sở dữ liệu
T2  đọc danh sách storage_key     ⊇ danh sách trong bản dump (T2 > T1)
T3  tar dataset/legal/            ⊇ mọi tệp tồn tại ở T2 (T3 > T2)
```

Bước T3 an toàn nhờ hai tính chất của kho tệp: blob được ghi **trước** hàng cơ
sở dữ liệu, và tên tệp là băm nội dung nên không bao giờ bị ghi đè. Một văn bản
công bố sau T2 nằm ngoài phép đối chiếu — đúng như mong muốn, vì nó cũng nằm
ngoài bản dump.

Làm ngược lại (nén tệp trước, dump sau) sẽ hỏng: một văn bản công bố xen giữa
sẽ có hàng trong bản dump mà không có tệp trong bản lưu trữ.

### Khoảng hở còn lại

Dọn rác kho tệp (`python -m app.cli.legal_store --gc --apply`) xoá blob không còn
ai trỏ tới **và** đã nguội quá 24 giờ. Nếu ai đó chạy `gc --apply` đúng khoảng
giữa T1 và T3 cho một blob vừa mất tham chiếu ở T2, bản dump ở T1 sẽ trỏ vào
tệp không còn. Cửa sổ này rộng vài giây, cần một lượt gc thủ công chen đúng vào
đó, và `legal_documents` có trigger chỉ-thêm nên bản đã công bố không mất tham
chiếu được. **Đừng chạy `gc --apply` trong lúc `pg-backup` đang chạy một lượt.**

## Diễn tập khôi phục

> Một script khôi phục chạy đúng một lần trong đời, vào ngày tệ nhất, bởi một
> người đang cuống. Nếu lần chạy đầu tiên của nó cũng là lần đầu tiên nó được
> thử thì nó không phải kế hoạch khôi phục — nó là một hy vọng.

`scripts/pg_restore.sh` mặc định chạy chế độ **diễn tập**: dựng bản sao lưu vào
một cơ sở dữ liệu nháp, đếm từng bảng, đối chiếu với bản đang chạy, băm lại
từng bản văn pháp lý, rồi xoá cơ sở dữ liệu nháp. Không đụng dữ liệu thật.

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network voya-collector_voya_network \
  -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=<mật khẩu> -e POSTGRES_DB=signdb \
  -e BACKUP_DIR=/backups \
  -v "E:/CTU_ProjectOutside/VOYA-Collector/scripts/pg_restore.sh:/usr/local/bin/pg_restore.sh:ro" \
  -v "E:/CTU_ProjectOutside/VOYA-Collector/backups:/backups" \
  --entrypoint /bin/sh postgres:17 /usr/local/bin/pg_restore.sh --drill
```

Trên Git Bash phải đặt `MSYS_NO_PATHCONV=1` trước lệnh, nếu không MSYS đổi
`/backups` thành đường dẫn Windows và docker từ chối.

Lượt diễn tập đầu tiên trong lịch sử dự án: **2026-08-08, ĐẠT** — 44 bảng dựng
lại được, 0 bảng lệch số dòng, 4/4 bản văn pháp lý khớp băm. Đường hỏng cũng đã
kiểm: sửa một byte trong bản văn → `SAI BĂM`, mã thoát 1; cắt cụt bản dump →
thất bại lúc dựng, mã thoát 1.

Đọc kết quả:

| Dòng | Nghĩa |
|---|---|
| `lệch  <bảng>: sao lưu N / đang chạy M` | **Bình thường.** Bản sao lưu chụp ở quá khứ, hệ thống vẫn chạy tiếp. |
| `RỖNG  <bảng>` | **Hỏng.** Bảng có cấu trúc nhưng không có dòng nào. Đây là dấu vết của một lượt dump bị RLS lọc. |
| `THIẾU BẢNG <bảng>` | **Hỏng.** Bản dump không đầy đủ. |
| `SAI BĂM <khoá>` | **Hỏng.** Tệp pháp lý không còn đúng nội dung tên nó tuyên bố. |

**Nhịp đề nghị: mỗi tháng một lần, và bắt buộc sau mỗi lần đổi schema lớn.**

Xem các lượt đang có:

```bash
... /usr/local/bin/pg_restore.sh --list
```

## Vì sao vai kết nối phải vượt được RLS

Hơn hai mươi bảng bật `FORCE ROW LEVEL SECURITY`, tức **kể cả chủ sở hữu bảng
cũng bị chính sách ràng buộc**. Vị từ là:

```sql
current_setting('app.system_scope', true) = 'on' OR tenant_id = current_setting('app.tenant_id', true)
```

Một kết nối không đặt GUC nào thì cả hai vế đều NULL → **không dòng nào khớp**.

Hôm nay `pg-backup` kết nối bằng `POSTGRES_USER=admin`, vốn là superuser
(`rolsuper=t, rolbypassrls=t`), nên nó đọc được mọi dòng. Ngoài ra `pg_dump`
đặt `row_security = off` và Postgres sẽ **báo lỗi** thay vì lặng lẽ trả bảng
rỗng, nên hôm nay có hai lớp bảo vệ.

Cả hai đều là hành vi của hôm nay. Một lượt "siết quyền" tương lai đổi service
này sang vai ứng dụng hạn chế sẽ phá cả hai. Vì vậy `pg_backup.sh` **khẳng định
tường minh** ở bước tiền kiểm rằng vai kết nối có `rolsuper` hoặc
`rolbypassrls`, và **thoát hẳn** nếu không — container chuyển sang trạng thái
restarting, ai nhìn `docker compose ps` cũng thấy. Một service đang "up" mà mọi
lượt dump đều lỗi thì không ai thấy cho tới ngày cần khôi phục.

Nếu bạn cố tình muốn dùng vai hạn chế: cấp `ALTER ROLE <vai> BYPASSRLS`. Đừng
gỡ phép khẳng định.

## Khôi phục khẩn

### 1. Xác định phạm vi

Mất cơ sở dữ liệu, mất kho tệp, hay cả hai? Kiểm nhanh:

```bash
docker exec voya_postgres psql -U admin -d signdb -Atc "SELECT count(*) FROM samples;"
docker exec voya_backend python -m app.cli.legal_store --verify
```

### 2. Chọn lượt sao lưu và diễn tập TRƯỚC

Kể cả đang khẩn. Diễn tập mất vài phút và loại trừ khả năng đè dữ liệu hỏng
bằng một bản sao lưu cũng hỏng.

```bash
... /usr/local/bin/pg_restore.sh --list
... /usr/local/bin/pg_restore.sh --drill --stamp 20260808_231500
```

### 3. Dừng thứ đang ghi vào cơ sở dữ liệu

```bash
docker compose stop backend worker celery-beat trainer realtime_service
```

Không có bước này, một lượt ghi từ Celery chen vào giữa lúc khôi phục sẽ để lại
trạng thái không ai giải thích được.

### 4. Khôi phục cơ sở dữ liệu

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network voya-collector_voya_network \
  -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=<mật khẩu> -e POSTGRES_DB=signdb \
  -e BACKUP_DIR=/backups -e CONFIRM=RESTORE-signdb \
  -v "E:/CTU_ProjectOutside/VOYA-Collector/scripts/pg_restore.sh:/usr/local/bin/pg_restore.sh:ro" \
  -v "E:/CTU_ProjectOutside/VOYA-Collector/backups:/backups" \
  --entrypoint /bin/sh postgres:17 \
  /usr/local/bin/pg_restore.sh --force-into-production --stamp 20260808_231500
```

Tổ hợp cờ `--clean --if-exists --exit-on-error` đã được kiểm trên cơ sở dữ liệu
**đã có sẵn dữ liệu** (2026-08-09): dựng đè thành công, `samples` về đúng 3.860
dòng. `--exit-on-error` quan trọng vì mặc định `pg_restore` chạy tiếp qua lỗi
rồi trả 0 — một lượt khôi phục "thành công" mà bỏ sót nửa số bảng là kiểu hỏng
tệ nhất.

Script sẽ **tự dump trạng thái hiện tại trước** vào
`signdb_pre_restore_<stamp>.dump` và dừng hẳn nếu bản dump an toàn đó không ghi
được. Trạng thái hiện tại, kể cả hỏng, là bằng chứng — và là đường lui duy nhất
nếu khôi phục nhầm lượt.

### 5. Khôi phục kho tệp pháp lý

Bước này **thủ công có chủ ý**: nó ghi đè lên `dataset/`, và một script tự động
giải nén đè lên dữ liệu gốc là một script có thể phá hỏng đúng thứ nó bảo vệ.

```bash
tar -xzf backups/legal_20260808_231500.tar.gz -C dataset/legal/
docker exec voya_backend python -m app.cli.legal_store --verify
```

Giải nén là **chỉ-thêm** trên thực tế: tên tệp là băm nội dung, nên tệp trùng
tên có nội dung trùng. Không có nguy cơ đè mất bản khác.

### 6. Bật lại và kiểm chứng

```bash
docker compose start backend worker celery-beat trainer realtime_service
docker exec voya_backend python -m app.cli.verify_deployment
```

Kỳ vọng: 22 PASS / 1 WARN / 0 FAIL. WARN là ba lớp từ vựng chưa có mẫu, hợp lệ.

### 7. Đối chiếu SOT

Postgres là **bản sao** của `dataset/labels.csv` và `dataset/samples.csv`, không
phải nguồn sự thật. Sau khôi phục, hai bên có thể lệch nếu bản dump cũ hơn CSV.

```bash
docker exec voya_backend python -m app.cli.verify_deployment
```

Xem `docs/99-archive/QUICK_REFERENCE.md` về đường đồng bộ CSV → DB.

## Ranh giới trách nhiệm

| Mục | Hiện trạng |
|---|---|
| RPO (mất tối đa bao nhiêu dữ liệu) | 24 giờ — bằng chu kỳ sao lưu |
| RTO (khôi phục mất bao lâu) | ~15 phút cho cơ sở dữ liệu + kho tệp, chưa tính thời gian phát hiện sự cố |
| Bản sao ở ổ khác | **Cơ chế đã có, mặc định TẮT.** `BACKUP_MIRROR_HOST_DIR` + `BACKUP_MIRROR_DIR`. Chưa bật thì `./backups` vẫn nằm cùng ổ với `./dataset`. |
| Bản sao ở **máy** khác | **Chưa có.** Ổ ngoài không cứu được cháy, trộm, hay mã độc tống tiền có quyền ghi lên ổ đang gắn. |
| Mã hoá bản sao lưu | **Cơ chế đã có, mặc định TẮT.** `BACKUP_PASSPHRASE` bật AES-256. Chưa đặt thì bản dump vẫn ở dạng rõ. |

Ba dòng cuối là nợ đã biết, không phải sơ suất — và hai trong ba giờ chỉ còn
chờ **một quyết định cộng một dòng `.env`**, không còn chờ mã.

Quyết định còn lại thuộc về người vận hành vì nó không phải câu hỏi kỹ thuật:
cất khoá ở đâu để một sự cố không lấy đi cả khoá lẫn bản sao lưu, và đặt bản
sao ngoài ở đâu cho hợp với ràng buộc về dữ liệu cá nhân của một chương trình
giáo dục đặc biệt.

**Vòng tròn đã được kiểm, không phải chỉ được viết:** mã hoá → giải mã thử →
diễn tập khôi phục từ chính bản đã mã hoá, trên bản sao `signdb_test`
(2026-08-09): 44 bảng, 0 bảng lệch số dòng, 4/4 bản văn pháp lý khớp băm. Sai
mật khẩu và thiếu mật khẩu đều thoát 1 kèm câu giải thích.
