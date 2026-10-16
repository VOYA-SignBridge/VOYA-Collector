# Triển khai trên máy thứ hai

> Viết 2026-08-09 sau khi hai máy của dự án chạy hai đời GPU khác nhau.
> Máy A: RTX 3050 Laptop (Ampere, `sm_86`). Máy B: RTX 5060 Ti (Blackwell, `sm_120`).

## 1. Một lệnh

```bash
bash scripts/deploy.sh
```

Nó tự làm ba việc mà trước đây phải nhớ:

| Việc | Vì sao không để người nhớ |
|---|---|
| **Dò GPU thật** rồi mới thêm `docker-compose.gpu.yml` | `driver: nvidia` được giải quyết lúc TẠO container. Thêm overlay trên máy không có NVIDIA Container Toolkit thì trainer chết ngay với *"could not select device driver"*, kéo sập cả lượt triển khai. Thiếu overlay trên máy CÓ card thì mọi thứ vẫn "healthy" và huấn luyện lặng lẽ chạy bằng CPU. |
| **Luôn kèm `docker-compose.prod.yml`** | Chỉ tệp gốc thì **không dịch vụ nào có `mem_limit`**. Trên máy 12 GB với trainer 4 GB, đó chính là tình trạng đã giết `dockerd` một lần. |
| **Gieo `deploy/public_hosts.txt`** từ tệp mẫu | Tệp này gitignored (tên tunnel máy này khác máy kia). Thiếu nó = danh sách rỗng = thư đặt lại mật khẩu lặng lẽ lùi về `FRONTEND_BASE_URL`. |

**Đừng gõ ba `-f` bằng tay.** Đã hỏng ba lần vì chuyện đó — lần gần nhất
(2026-08-09) để lại một stack **lệch đôi**: 3 container dựng bằng lệnh đủ ba
tệp, 11 container còn lại dựng lại sau đó bằng `docker compose up -d` trần.
`docker compose ls` vẫn báo đủ ba tệp và che mất chuyện đó.

## 2. Pre-flight — hỏng sớm thay vì hỏng sau 15 phút

`deploy.sh` kiểm trước khi dựng ảnh, và thoát mã 3 nếu không đạt:

- `.env` có tồn tại không;
- `SECRET_KEY` / `AUTH_TOKEN_SECRET_KEY` — **FAIL** nếu ngắn hơn 32 ký tự và
  `APP_ENV=production` (backend sẽ từ chối khởi động, nhưng chỉ sau khi ảnh đã
  dựng xong), cảnh báo nếu môi trường khác;
- `POSTGRES_PASSWORD`, `VOYA_APP_DB_PASSWORD` có giá trị;
- `FRONTEND_BASE_URL` không rỗng;
- Docker daemon có trả lời không.

Sinh khoá: `openssl rand -hex 32`.

## 2b. Migration là một BƯỚC RIÊNG, và nó chạy trước ứng dụng

Từ 12/08/2026, `deploy.sh` chạy theo thứ tự:

```
dựng ảnh  →  chỉ postgres + redis lên  →  MIGRATION  →  cả stack lên
```

Bước migration gọi `python -m app.cli.migrate --to <N>` trong một container
dùng-một-lần, với `EXPECTED_DATABASE` lấy từ **DSN** chứ không phải từ
`POSTGRES_DB`. Nếu nó không xong, `deploy.sh` **dừng hẳn với mã thoát 4** và
không dựng gì thêm — container cũ vẫn chạy mã cũ, triển khai không nằm ở trạng
thái nửa vời.

**Vì sao phải nhớ điều này.** Backend bây giờ **từ chối khởi động** khi phiên
bản lược đồ không khớp ảnh, ở cả hai chiều. Nếu bạn dựng stack bằng
`docker compose up -d` trần trên một máy chưa migrate, triệu chứng sẽ là
backend restart liên tục với dòng:

```
[SCHEMA-VERSION] db=(chua dong dau) anh ho tro=[5..5] -> TU CHOI KHOI DONG
```

Cách chữa là chạy migration, không phải gỡ cổng:

```bash
EXPECTED_DATABASE=signdb docker compose run --rm backend \
  python -m app.cli.migrate --to 5
```

Hỏi trạng thái mà không đổi gì (lệnh này **không** cần `EXPECTED_DATABASE`):

```bash
docker compose run --rm backend python -m app.cli.migrate --status
```

**Máy đã chạy v5 từ trước khi có sổ đăng bạ** thì dùng `--adopt` — nó chỉ đóng
dấu, không đổi lược đồ, và tự từ chối nếu lược đồ còn thiếu đối tượng:

```bash
EXPECTED_DATABASE=signdb docker compose run --rm backend \
  python -m app.cli.migrate --adopt
```

Lý lẽ đầy đủ ở
[INCIDENT_2026-08-12_schema_code_skew.md §6](../10-issues/INCIDENT_2026-08-12_schema_code_skew.md).

## 2c. Dung lượng Docker — vì sao `prune` không giải quyết được gì

Trên WSL2 toàn bộ engine nằm trong **một tệp `.vhdx` chỉ phình, không bao giờ
tự co**. Hệ quả đo được ngày 13/08/2026:

```
dọn 45.87 GB trong Docker  →  ổ D nhận về ĐÚNG 0 byte
nén vhdx                   →  123.3 GB → 24.2 GB, ổ D +99.1 GB, trong 73 giây
```

Nên `docker system df` có thể báo hàng chục GB "reclaimable" trong khi ổ đĩa ở
99%, và lời khuyên thông thường ("cứ prune đi") đọc như đã xong trong khi chưa
sửa gì. **Prune và nén là hai việc khác nhau; chỉ việc thứ hai trả tiền về.**

Cơ chế tự thu hồi của WSL (`wsl --manage --set-sparse`) **không dùng được**:
Microsoft đã tắt nó vì nguy cơ hỏng dữ liệu, phải `--allow-unsafe` mới bật. Cơ
sở dữ liệu sản xuất nằm trong chính tệp đó, nên đây là cái giá không đáng trả.

### Ba tầng bảo vệ

| tầng | ở đâu | làm gì |
|---|---|---|
| pre-flight | `deploy.sh` | **CHẶN** build khi ổ chứa vhdx còn < 20 GB, cảnh báo < 40 GB |
| theo lịch | Task `VOYA Docker disk watch`, CN 09:00 | dọn an toàn + email khi cần |
| bằng tay | `scripts/docker_gc.sh` | `--deep` dọn sâu, `--compact` nén |

Tầng pre-flight là tầng **duy nhất** nhìn được ổ host: filesystem bên trong
vhdx vẫn báo rộng rãi khi D đã đầy, nên không thứ gì chạy trong container có
thể báo động.

### Tín hiệu: KHOẢNG CÁCH, không phải chỗ trống

`docker_watch.sh` cảnh báo theo **`vhdx trên đĩa − dung lượng Docker thật sự
dùng`**, tức "nén sẽ lấy lại được bao nhiêu". Ngày 13/08 con số đó là ~106 GB
và nén lấy về 99.1 GB. Chỗ trống thuần tuý không phân biệt được "ổ chật nhưng
nén vô ích" với "có sẵn 100 GB chờ một lượt nén".

```bash
bash scripts/docker_watch.sh --dry-run   # chi do va in
bash scripts/docker_watch.sh --install   # dang ky lai lich (khong can admin)
bash scripts/docker_gc.sh --compact      # nen that (dung stack, can bam UAC)
```

Nhật ký: `voya_backups/docker_watch.log` (kết quả) và `docker_watch_task.log`
(lượt chạy theo lịch, gồm cả lần hỏng).

### Ba cái bẫy đã trả giá

* **Giết tiến trình `Docker Desktop` KHÔNG khởi động lại engine** — đó chỉ là
  giao diện. Muốn engine đọc lại `daemon.json` thì bắt buộc `wsl --shutdown`.
  Kiểm bằng `docker run --rm alpine cat /proc/uptime`.
* **Docker Desktop ghi đè `~/.docker/daemon.json`** bằng bản cache của nó khi
  khởi động. Sửa lúc Docker đang chạy là mất trắng.
* **Đừng bao giờ `--volumes`.** Đo tại đây: ba volume mồ côi đều 0 B, toàn bộ
  volume 403 MB. Lãi 0 byte. Và bước nén phải dừng Docker — nếu ở đó dùng
  `down` thay vì `stop` thì mọi volume thành mồ côi và cùng lệnh ấy xoá cơ sở
  dữ liệu. Xoá volume mồ côi thì xoá **theo tên**.

## 3. GPU: chip khác đời thì phải kiểm, không phải đoán

`torch.cuda.is_available()` trả lời *"có driver chạy được không"*, **không** trả
lời *"bản dựng này có kernel cho con chip đó không"*. Một wheel biên dịch cho
kiến trúc cũ vẫn báo True trên card mới, rồi **lượt phóng kernel đầu tiên** chết
giữa buổi huấn luyện với `no kernel image is available for execution on the
device` — sau khi dữ liệu đã nạp, và với một câu lỗi đọc như lỗi lập trình.

Bản đang cài phủ được cả hai máy:

```
torch 2.7.1+cu128 → sm_75 sm_80 sm_86 sm_90 sm_100 sm_120 compute_120
                              ↑ máy A                ↑ máy B
```

**Không cần đổi gì cho máy B.** Nhưng điều đó không vĩnh viễn: hạ về một wheel
`cu121` là máy B rơi xuống CPU trong im lặng — `pick_device()` cố ý lùi về CPU
để job vẫn chạy được, nên không có lỗi nào nổ ra, chỉ có huấn luyện chậm gấp
nhiều lần.

Vì thế phép so khớp được **đo tại nơi có card** (trong trainer) rồi gửi kèm ảnh
chụp GPU sang Redis, và `verify_deployment` đọc lại:

```
PASS  GPU   NVIDIA GeForce RTX 3050 Laptop GPU — 4096 MB VRAM, sm_86, torch 2.7.1+cu128 OK
FAIL  GPU   … sm_120 — torch 2.7.1+cu121 KHONG co kernel cho chip nay …
```

### 3.1 Vì sao GPU cứ "biến mất" sau vài ngày

Triệu chứng: trang Giám sát tài nguyên báo *"Huấn luyện đang chạy bằng CPU"*
trên một máy có card NVIDIA hẳn hoi, dù đã từng triển khai đúng.

Nguyên nhân **không** nằm ở phần cứng, driver hay torch. `deploy.sh` dò card
đúng và thêm `-f docker-compose.gpu.yml` đúng — nhưng cái overlay đó chỉ tồn
tại trong **argv của lượt chạy ấy**. Mọi đường khác vào stack đều đánh rơi nó:

```bash
docker compose up -d              # trần, không -f  → trainer không có GPU
docker compose restart trainer    # tương tự
```

…cộng nút Restart trong Docker Desktop, và mọi câu lệnh chép lại từ một ghi chú
cũ. **Không đường nào báo lỗi.** Trainer lên `Up (healthy)` với
`DeviceRequests = null` và huấn luyện bằng CPU chậm cỡ mười lần, không có gì ở
đâu nói ra điều đó — nó chỉ lộ ra khi có người nhìn kỹ trang giám sát.

**Cách vá:** `deploy.sh` nay ghi danh sách tệp vào `.env`, và Compose đọc
`COMPOSE_FILE` từ `.env` của thư mục dự án:

```
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:docker-compose.gpu.yml
```

Từ đó một lệnh `docker compose up -d` trần trong thư mục này mang đúng nghĩa mà
script đã chọn — kể cả với công cụ chưa bao giờ nghe tới script.
`COMPOSE_PATH_SEPARATOR` được ghim vì mặc định của nó khác nhau theo nền tảng
(`;` trên Windows, `:` nơi khác) còn kho này triển khai trên cả hai.

Trên máy **không** có card, `deploy.sh` ghi đúng dòng đó nhưng bỏ
`docker-compose.gpu.yml`. Đưa overlay vào chỗ thiếu NVIDIA Container Toolkit
không suy giảm êm — nó giết trainer ngay với `could not select device driver
"nvidia"`.

**Kiểm nhanh xem container hiện tại có GPU thật không:**

```bash
docker inspect $(docker ps -qf name=_trainer) --format '{{json .HostConfig.DeviceRequests}}'
# null  → container này KHÔNG có GPU (dựng trước khi có overlay)
```

`restart` **không** đọc lại compose. Sau khi sửa `COMPOSE_FILE` phải dựng lại:

```bash
docker compose up -d --force-recreate trainer
```

`deploy.sh` nay cũng tự kiểm điều này và cảnh báo khi overlay có trong
`COMPOSE_FILE` mà container thì không có thiết bị nào — hai tình huống ấy nhìn
từ bên ngoài giống hệt nhau, cùng là `Up (healthy)`.

## 4. Sau khi triển khai — chạy đúng một lệnh này

```bash
docker exec voya_backend python -m app.cli.verify_deployment
```

Bốn kiểm tra dưới đây tồn tại riêng cho việc "máy này có giống máy kia không":

| Kiểm tra | Bắt được gì |
|---|---|
| `gioi han bo nho container` | Đọc cgroup **của chính backend**. `memory.max = max` nghĩa là `docker-compose.prod.yml` không được áp. Không cần docker socket. |
| `GPU` | Card có được cấp vào container không, **và** torch có kernel cho nó không. |
| `anh chup dong thuan` | Ảnh chụp đồng thuận còn hạn không (7 ngày). |
| `quy ket nguoi dong gop` | Tỉ lệ mẫu có `signer_id`. |

## 5. Những thứ KHÔNG đi theo git, phải chuẩn bị riêng

| Thứ | Hệ quả nếu thiếu |
|---|---|
| `.env` | pre-flight chặn ngay |
| `deploy/public_hosts.txt` | tự gieo từ `.example`; **phải thêm hostname của máy đó** |
| `gdrive/credentials.json`, `token.json` | `sot-init` bỏ qua sạch sẽ và stack vẫn lên với catalog rỗng — **không** chặn |
| Khoá ký SOT | chỉ cần nếu máy đó **xuất bản** SOT. `SignBridge_SE` là publisher duy nhất; máy khác chỉ đọc, và khoá công khai của nó đã nằm trong `app/sot/authorized_keys.json` (đã commit) |

**Chỉ một trường hợp làm `sot-init` chặn cả stack: chữ ký hoặc checksum không
khớp** (exit 4). Đó là cố ý và đừng nới — nó nghĩa là nguồn sự thật có thể đã bị
sửa, và khởi động worker lên trên nó còn tệ hơn không khởi động.

## 6. Bẫy đã gặp

**Kết thúc dòng CRLF.** `git config autocrlf` trên Windows biến
`docker-entrypoint.sh` thành CRLF và frontend crash-loop với `exec: no such file
or directory`. `.gitattributes` ép `*.sh` về LF — kiểm bằng
`file frontend/docker-entrypoint.sh` nếu container lặp lại.

**Ổ Docker đầy.** Docker để ở ổ D trên máy A; `vhdx` phình tới 118 GB và làm ổ D
còn 1 GB, giết `dockerd`. `vhdx` **không tự co lại** — phải `Optimize-VHD`.

**`docker compose ls` nói dối về tệp cấu hình.** Nó tổng hợp từ nhãn container
và không cho biết chúng không đồng nhất. Kiểm từng cái:

```bash
docker inspect <container> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
```
