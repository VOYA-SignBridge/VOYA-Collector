# Triển khai từ đầu trên một máy Windows

Dành cho người lần đầu dựng web. Lệnh gõ trong **Git Bash**. Lệnh `VOYA.bat` trong Git Bash gõ dạng `cmd //c "VOYA.bat ..."`. Bấm đúp `VOYA.bat` sẽ mở menu có sẵn mọi lệnh.

| Tình huống | Làm |
|---|---|
| Máy mới, chưa có dữ liệu | Bước 0, rồi **Đường 1** |
| Chuyển web đang chạy sang máy khác, mang theo dữ liệu | Bước 0, rồi **Đường 2** |

## Bước 0. Chuẩn bị máy

**Cài:** Git for Windows, Python 3.11+ (đánh dấu *Add Python to PATH*), Docker Desktop (WSL2). Có card NVIDIA thì cài thêm driver NVIDIA.

**Cấu hình:**
- RAM tối thiểu 12 GB.
- Docker Desktop → **Settings → Resources → Advanced → Disk image location**: chọn ổ còn **ít nhất 100 GB trống**. Kiểm lại mục này sau mỗi lần Docker Desktop tự cập nhật, vì nó từng tự đổi về ổ C.
- Tắt chế độ ngủ. Mở PowerShell **với quyền Administrator** và gõ:
  ```powershell
  powercfg /change standby-timeout-ac 0
  powercfg /change hibernate-timeout-ac 0
  ```

**Kiểm tra:**

```bash
git --version
python --version
docker version
docker compose version
```

Lệnh nào cũng phải in số phiên bản. Riêng `docker version` phải có cả phần `Server`; thiếu nghĩa là Docker Desktop chưa chạy.

## Đường 1. Máy trống

### 1. Lấy mã

```bash
cd /d
git clone https://github.com/VOYA-SignBridge/VOYA-Collector.git
cd VOYA-Collector
git switch main
```

### 2. Tạo `.env`

```bash
cp .env.example .env
notepad .env
```

Tạo chuỗi ngẫu nhiên bằng lệnh dưới, mỗi giá trị chạy một lần:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Phải sửa:**

| Dòng | Điền |
|---|---|
| `SECRET_KEY`, `AUTH_TOKEN_SECRET_KEY` | Hai chuỗi ngẫu nhiên khác nhau |
| `POSTGRES_PASSWORD` | Mật khẩu DB, ít nhất 16 ký tự. Sửa luôn `admin:admin` trong `MIGRATION_DATABASE_URL` thành `admin:<mật khẩu này>` |
| `VOYA_APP_DB_PASSWORD` | Mật khẩu khác. Điền cùng giá trị vào chỗ `CHANGE_ME` trong `DATABASE_URL` |
| `VOYA_CONTROL_DB_PASSWORD` | Mật khẩu khác nữa. Điền cùng giá trị vào `CONTROL_DATABASE_URL` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Tài khoản quản trị đầu tiên, được tự tạo lúc khởi động |
| `GRAFANA_ADMIN_PASSWORD` | Mật khẩu trang giám sát |
| `FRONTEND_BASE_URL` | Địa chỉ web, ví dụ `https://signbridge.mainhatminh.id.vn`. Chạy trong máy thì để `http://localhost` |
| `CORS_ALLOWED_ORIGINS` | Thêm địa chỉ web vào cuối dòng, cách nhau bằng dấu phẩy |
| `APP_ENV` | `production` khi mở ra Internet |

**Tuỳ chọn:**

| Dòng | Ghi chú |
|---|---|
| `USE_GOOGLE_DRIVE` | `0` nếu chưa có Drive hoặc đây là máy thử. Đặt `1` thì phải chép `credentials.json` và `token.json` vào `gdrive/` |
| `SMTP_*` | Để gửi thư. Để trống thì không gửi; liên kết chỉ ghi vào log |
| `COOKIE_SECURE` | **Để `0`.** Cookie tự bảo mật khi người dùng vào qua HTTPS |

### 3. Khai báo tên miền

```bash
cp deploy/public_hosts.example.txt deploy/public_hosts.txt
notepad deploy/public_hosts.txt
```

Mỗi dòng một tên miền, không ghi `https://`. Tệp có hiệu lực ngay. Thiếu tên miền ở đây thì thư quên mật khẩu chứa liên kết sai.

### 4. Dựng và chạy

```bash
bash scripts/deploy.sh
```

Lệnh này tự làm theo thứ tự: kiểm tra `.env` và dung lượng đĩa → dò GPU → dựng image (lần đầu mất 20–40 phút, cần Internet) → chạy migration DB → bật dịch vụ.

Nếu thấy dòng `[FAIL]` thì **chưa có gì bị thay đổi**. Sửa `.env` theo thông báo, rồi chạy lại.

### 5. Kiểm tra

```bash
cmd //c "VOYA.bat status"
cmd //c "VOYA.bat verify"
```

- `status`: mọi dịch vụ `healthy`.
- `verify`: các mục báo `PASS`.
- Mở `http://localhost` và đăng nhập bằng tài khoản quản trị đã khai trong `.env`.

### 6. Mở ra Internet (Cloudflare Tunnel)

1. Cloudflare → **Zero Trust → Networks → Tunnels**: chọn tunnel, hoặc tạo tunnel mới.
2. Thêm connector cho Windows. Chạy lệnh `cloudflared.exe service install <token>` mà Cloudflare đưa, trong PowerShell **với quyền Administrator**.
3. Mục **Published application routes**: thêm tên miền, trỏ tới `http://127.0.0.1:80`.
4. Thử bằng điện thoại dùng 4G: đăng nhập và thử quên mật khẩu.

> **Một tunnel chỉ được một máy chạy connector.** Nếu hai máy cùng chạy, người dùng bị chia
> sang hai cơ sở dữ liệu khác nhau.

### 7. Cập nhật bằng ảnh dựng sẵn (nên bật trên máy chạy web)

Mặc định, mỗi lần cập nhật máy chạy web **tự dựng ảnh**: tốn CPU, RAM và ổ đĩa của chính máy đó, và mất vài phút. Bật chế độ kéo ảnh thì máy chỉ **tải ảnh mà CI đã dựng và đã kiểm** cho đúng commit đó.

Thêm một dòng vào `.env`:

```
VOYA_REGISTRY_NS=tamb2203579
```

Từ đó `VOYA.bat update-git` sẽ:
1. Kiểm commit mới đã có ảnh trên Docker Hub chưa. Chưa có, tức CI chưa xong hoặc đang đỏ, thì **dừng, không đụng vào gì**.
2. Tải ảnh **trong lúc web vẫn chạy**. Lớp thư viện nặng chỉ đổi khi danh sách gói đổi, nên thường chỉ tải vài chục MB.
3. Kéo mã, bật trang bảo trì, chạy ảnh mới, kiểm sức khoẻ, tự quay về bản cũ nếu hỏng. Các bước này giống hệt khi tự dựng.

Lần **đầu tiên** kéo ảnh vẫn tải trọn bộ (khoảng 4,5 GB với backend). Các lần sau chỉ tải phần đổi.

Bỏ dòng đó đi thì máy quay lại tự dựng như cũ. `VOYA.bat update-code` (dựng từ mã đang có trên máy) không bị ảnh hưởng.

### 8. Tự bật khi khởi động máy

Chỉ làm trên máy chạy web thật:

```bash
cmd //c "VOYA.bat autostart install"
```

### 9. Cập nhật bằng nút bấm trên GitHub (tuỳ chọn)

Sau khi bật, mỗi lần `main` có bản mới và CI dựng ảnh xong, GitHub hiện nút **Review deployments**. Người được phép bấm **Approve** thì máy chạy web tự chạy `VOYA.bat update-git`: kéo ảnh, bật trang bảo trì, kiểm sức khoẻ, hỏng thì tự quay về. Không ai cần mở máy để gõ lệnh, mà vẫn chọn được giờ cập nhật.

Hai trường hợp **không** tự cập nhật, job dừng và báo lý do:
- bản mới **đổi lược đồ CSDL**: phải làm tay, vì quay về ảnh cũ không đảo được migration;
- máy chưa ở nhánh `main`, chưa có `VOYA_REGISTRY_NS`, hoặc có tệp sửa dở.

**Điều kiện trước khi bật:** đã làm bước 7, máy chạy `main` ([CHUYEN_SANG_MAIN.md](CHUYEN_SANG_MAIN.md) mục 2), và đã chạy `VOYA.bat update-git` bằng tay ít nhất một lần thành công.

**A. Trên GitHub** (người có quyền admin repo):

| # | Vào đâu | Làm gì |
|---|---|---|
| 1 | **Settings → Environments → New environment** | Tên `production`. Bật **Required reviewers**, thêm người được duyệt. Ở **Deployment branches** chọn *Selected branches*, thêm `main` |
| 2 | Trong environment `production` → **Environment variables** | `DEPLOY_ROOT` = `D:\VOYA-Collector` (thư mục web trên máy) |
| 3 | **Settings → Secrets and variables → Actions → Variables** (biến của repo, không phải của environment) | `ENABLE_AUTO_DEPLOY` = `true`, `DEPLOY_BRANCH` = `main` |
| 4 | **Settings → Actions → General → Fork pull request workflows** | Chọn **Require approval for all outside collaborators** |

Bước 4 bắt buộc. Repo công khai, nên ai cũng mở được PR, và một PR có thể sửa workflow để chạy lệnh trên máy chạy web. Bật bước 4 thì PR của người ngoài nhóm chỉ chạy CI khi có người trong nhóm duyệt. **Đọc kỹ thay đổi trong `.github/` trước khi duyệt.**

**B. Trên máy chạy web**, cài máy chạy (runner) của GitHub:

1. Trên GitHub: **Settings → Actions → Runners → New self-hosted runner**, chọn **Windows**, **x64**. Trang này hiện sẵn các lệnh tải và cấu hình kèm một mã dùng một lần. **Không gửi mã đó cho ai.**
2. Mở PowerShell **Run as administrator**, chạy các lệnh trên trang, cài vào `C:\actions-runner`. **Không** cài vào trong thư mục web.
3. Khi `config.cmd` hỏi:
   - *labels*: gõ `voya-prod`;
   - *run as service*: `Y`;
   - *user account for the service*: tài khoản Windows **đang chạy Docker Desktop** trên máy này, kèm mật khẩu. Đừng để mặc định `NETWORK SERVICE`, vì tài khoản đó không dùng được Docker Desktop.
4. Trên GitHub, mục **Runners** phải thấy máy ở trạng thái **Idle**, nhãn có `self-hosted`, `Windows`, `voya-prod`.

**Thử:** đưa một thay đổi nhỏ lên `main` ([CHUYEN_SANG_MAIN.md](CHUYEN_SANG_MAIN.md) mục 1). Trong tab **Actions**, lượt *Build & push images* dựng ảnh xong sẽ dừng ở job **Triển khai lên máy chạy web**. Bấm **Review deployments → Approve**, rồi theo dõi log.

**Tắt:** đổi `ENABLE_AUTO_DEPLOY` thành `false`. Máy quay về cập nhật bằng tay như cũ.

Docker Desktop chỉ chạy khi tài khoản đó đã đăng nhập Windows. Nếu tài khoản bị đăng xuất, job báo lỗi ở bước cập nhật và web không bị đụng tới.

## Đường 2. Chuyển web sang máy mới, mang theo dữ liệu

**Máy cũ:** bấm đúp `VOYA.bat`, chạy lần lượt:

| Lệnh | Việc |
|---|---|
| `goi-uoc-luong` | Ước lượng dung lượng gói |
| `goi-drive` | Chép trước dữ liệu Drive. Web vẫn chạy trong lúc này |
| `goi-tao` | **Dừng web** và đóng gói DB, cấu hình, dữ liệu thành `.zip` |
| `goi-kiem` | Kiểm tra gói |

Chép tệp `.zip` và tệp `.sha256` sang máy mới bằng ổ ngoài. **Không** gửi qua chat, email hay GitHub, vì gói chứa mật khẩu và dữ liệu cá nhân.

**Máy mới:**

1. Làm Bước 0 và bước 1 của Đường 1. **Không** tạo `.env`, vì `.env` có sẵn trong gói.
2. Giải nén gói, rồi chạy:
   ```bash
   python scripts/chuyen_server/nap_goi_vao_repo.py --pack <thư mục gói đã giải nén>
   ```
   Lệnh này nạp DB, cấu hình và dữ liệu, dựng web, cài tự bật. Nếu máy đã có bản cũ, bản đó được dời vào thư mục dự phòng, không bị xoá.
3. Kiểm tra (bước 5) và chuyển tunnel (bước 6).

**Máy cũ, sau khi máy mới đã ổn:** chạy `cmd //c "VOYA.bat tat-may-cu"`. **Không bao giờ để hai máy cùng chạy web.**

Chi tiết: [HOST_TRANSFER.md](HOST_TRANSFER.md).

## Lệnh hằng ngày

| Lệnh | Dùng khi |
|---|---|
| `VOYA.bat status` | Xem tình trạng |
| `VOYA.bat logs` | Xem lỗi gần đây |
| `VOYA.bat start` | Khởi động, hoặc **áp dụng `.env` vừa sửa** |
| `VOYA.bat restart` | Khởi động lại, **không** đọc lại `.env` |
| `VOYA.bat stop` | Dừng web; dữ liệu còn nguyên |
| `VOYA.bat backup` | Sao lưu DB ngay |
| `VOYA.bat update-git` | Cập nhật lên bản mới nhất của `main` |
| `VOYA.bat rollback` | Quay về bản trước |
| `VOYA.bat maintenance on` / `off` | Bật hoặc tắt trang bảo trì |
| `VOYA.bat disk` | Xem dung lượng Docker và dọn dẹp |

## Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Sửa `.env` mà không có tác dụng | Dùng `VOYA.bat start`, không dùng `restart` |
| Backend khởi động lại liên tục, log có `TU CHOI KHOI DONG` | Chạy lại `bash scripts/deploy.sh` để migrate DB |
| Vào qua tên miền bị lỗi 502 | Trỏ route Cloudflare tới `http://127.0.0.1:80`, không dùng `localhost` |
| Không đăng nhập được qua tên miền | Thêm tên miền vào `CORS_ALLOWED_ORIGINS`, rồi `VOYA.bat start` |
| Thư quên mật khẩu chứa liên kết sai tên miền | Thêm tên miền vào `deploy/public_hosts.txt` |
| Có card NVIDIA mà huấn luyện vẫn chạy bằng CPU | Chạy lại `bash scripts/deploy.sh` |
| Web chập chờn | Máy đi ngủ: tắt chế độ ngủ (Bước 0) |
| Ổ đĩa đầy dù đã dọn Docker | `bash scripts/docker_gc.sh --compact`. Web sẽ dừng vài phút |
| Không dịch vụ nào lên, `sot-init` báo mã 4 | **Đừng nới kiểm tra.** Quản trị viên thêm khoá của máy ở trang `/admin/sot`. Máy thử thì đặt `USE_GOOGLE_DRIVE=0` |

Đọc thêm: [CHUYEN_SANG_MAIN.md](CHUYEN_SANG_MAIN.md), [DEPLOY_SECOND_MACHINE.md](DEPLOY_SECOND_MACHINE.md), [BACKUP_RESTORE.md](BACKUP_RESTORE.md).
