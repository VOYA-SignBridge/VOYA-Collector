# Backup, chuyển host và deploy

## Hợp đồng vận hành

- Python **3.11+**, Docker Engine Linux + Compose v2. Máy đích cần Internet để pull/build image, tối thiểu 6 GiB RAM cho Docker; train có thể cần nhiều hơn. Mặc định CPU; `--gpu` yêu cầu NVIDIA Container Toolkit và GPU tương thích, không tự cài driver.
- Hai entrypoint: `scripts/backup.py`, `scripts/deploy.py`. Logic dùng chung ở `scripts/ops/`; kiểm thử ở `scripts/ops/tests/`. Dùng luồng này cho chuyển host/CD; `deploy.sh` cũ không có hợp đồng full-host backup này.
- Backup chứa **database mọi tenant + roles/password hashes**, source hiện tại kể cả thay đổi chưa commit, `.env`, dataset/video/NPZ/legal/CSV, processed/checkpoints, gdrive credentials/cache, certs/config và named volumes Redis/Grafana/Loki/Prometheus.
- Không bao gồm `.git`, dependency/cache (`node_modules`, `.venv*`, `__pycache__`, pytest/mypy cache), thư mục `backups` và các mount đích backup/mirror. Không xuất image Docker. Bind mount dữ liệu ngoài workspace bị chặn để tránh bỏ sót; chuyển dữ liệu đó vào workspace và cập nhật Compose trước.
- Xuất **mọi database không phải template**, kể cả database phụ và `postgres`; mỗi DB có dump `--create`, số dòng từng bảng và kích thước. Khôi phục database owner/ACL/settings, quyền bảng/RLS và roles. Tablespace tùy chỉnh cần mapping host riêng nên bị chặn, không âm thầm bỏ qua.
- Google Drive là **ngoại vi**: bundle không tải toàn bộ dữ liệu cloud. `--accept-external-storage` chỉ xác nhận host mới tiếp tục truy cập cùng Drive. Muốn bản độc lập/offline phải xuất cloud riêng; không xem cờ này là bằng chứng cloud đã backup.
- File bundle có SHA-256 + kích thước; thiếu/hỏng file, thiếu volume, path traversal, symlink/device, tên không portable đều bị từ chối. Manifest ghi sau cùng. SHA-256 phát hiện hỏng khi truyền, **không xác thực người tạo**: chỉ restore bundle tin cậy.
- Bundle chứa bí mật và dữ liệu cá nhân: lưu trên ổ mã hóa, giới hạn ACL tài khoản vận hành (Windows chmod không thay thế ACL), truyền qua SSH/SFTP; không commit/upload GitHub Actions artifacts. Không xóa bản tốt cũ tự động.
- Backup dừng writer tối đa 300s để drain rồi mới dump/copy. Nếu có service bị SIGKILL/OOM thì hủy; không công bố backup hoàn chỉnh. Không train/upload/chỉnh source bằng công cụ ngoài Docker trong lúc backup. Chuẩn bị maintenance window; lịch cũ `pg-backup` chỉ là DB/legal, **không thay thế** full-host bundle.

## Máy hiện tại: kiểm tra và backup

Chạy trong repo. Windows có thể thay `python` bằng `.venv/Scripts/python.exe`; Linux dùng `python3`.

```powershell
python scripts/deploy.py --check
python scripts/backup.py E:/voya-transfer/host-20260921 --allow-downtime --accept-external-storage
python scripts/backup.py E:/voya-transfer/host-20260921 --verify-only
```

Đường dẫn bundle phải **chưa tồn tại, ngoài repo**, không nằm trong bất kỳ kho dữ liệu đang snapshot. Thư mục cha có thể tạo tự động. Không dùng lại tên cũ sau một lần thất bại; giữ thư mục lỗi để chẩn đoán, không coi là backup hợp lệ khi chưa có manifest.

Backup vẫn cho phép lưu dữ liệu chưa hoàn hảo để cứu hộ; **deploy** mới là cổng chặn schema/RBAC/file sai. Không tự sửa/cấp quyền người dùng hay tự xoay khóa để ép kiểm tra pass.

## Máy mới: restore + tự cấu hình + deploy

Cài Python/Docker trước. Mang bundle và bộ `scripts/backup.py`, `scripts/deploy.py`, `scripts/ops/` sang máy mới (hoặc clone repo vào thư mục công cụ riêng). Thư mục `--root` đích chưa được tồn tại; thư mục cha phải có sẵn.

```bash
python3 scripts/backup.py /secure/host-20260921 --verify-only
python3 scripts/deploy.py --restore /secure/host-20260921 \
  --root /srv/voya-new --project voya-new --public-url https://sign.example.org \
  --allow-downtime --accept-external-storage
```

Tự đặt lại project/container name, URL, CORS, cookie, đường dẫn backup và allowlist host; **giữ khóa ký/token, mật khẩu DB và danh tính dữ liệu**. Biến password provision bị thiếu được lấy từ DSN tương ứng nếu DSN có password đủ mạnh; không sinh password khác và không ghi đè biến có sẵn. `--check` hoàn toàn chỉ đọc nên chỉ báo thiếu, không sửa. Kiểm tra nguồn mount, tài nguyên, port, DSN và database image trước khi tạo container. Tạo database/volumes mới, restore roles + dump, so số dòng **từng bảng** với thời điểm backup, build source, migrate theo phiên bản image, provision roles, kiểm RLS/schema/data, health check giới hạn thời gian. Gateway chỉ bật sau các cổng kiểm.

Không hỗ trợ ghi đè deployment/database/volume đã tồn tại trước lần restore. Chỉ trong **project mới tạo**, sau khi kiểm tra mọi DB đều rỗng, script tái tạo DB bootstrap trống bằng dump `--create` để giữ đúng ACL/owner/locale/settings. Không `down -v`, tự xóa dữ liệu cũ hay rollback DB khi migration lỗi. Restore thất bại để lại **project mới, ứng dụng chưa chạy** để kiểm tra; dùng tên đích/project mới cho lượt thử sạch tiếp theo. `--restore-only` chỉ khôi phục database/files/volumes, không dựng hay chạy ứng dụng. Không dùng `--restore-only` nếu muốn chạy tiếp một lệnh deploy tự động ngay sau đó; luồng bình thường đã thực hiện cả hai.

Phải xác nhận theo máy: DNS/TLS ở reverse proxy bên ngoài, SMTP/Drive credentials còn hiệu lực, firewall/NAT, dung lượng ổ Docker Desktop (có thể khác ổ workspace), GPU/driver, port trong `.env`. Sau build, deploy thử quyền ghi thực tế bằng user của image vào dataset/gdrive/processed; nếu UID chủ file Linux khác UID container, điều chỉnh quyền đúng ba kho dữ liệu ở project mới rồi kiểm tra lại, không dùng `chmod 777`. Script không thể tự biết domain hay xin quyền ở nhà cung cấp. Nếu host dùng proxy/TLS riêng thì dựng chúng trước khi mở truy cập công khai.

## Gói chuyển server đầy đủ: `scripts/migration_pack.py`

`backup.py` chỉ tạo bundle ứng dụng. Khi **chuyển server**, dùng `migration_pack.py`: nó gọi đúng `backup()` ở trên rồi gom thêm mọi thứ bundle bỏ ra, vào **một thư mục với một manifest SHA-256 phủ mọi file**.

### Tên thư mục và file zip

Mọi thứ của việc chuyển server nằm trong **một thư mục riêng** `SignBridge_ChuyenServer/` ở nơi lưu bạn chọn (ổ ngoài, vd. `F:/`). Tên gói = `SignBridge_ChuyenServer_<năm-tháng-ngày>_<giờ>h<phút>`; file zip và file kiểm tra mang **đúng tên đó**:

```
F:/SignBridge_ChuyenServer/
├── drive-cache/                                       Drive chép trước (drive-sync), create dùng lại
├── SignBridge_ChuyenServer_2026-10-20_21h00/          gói (create)
├── SignBridge_ChuyenServer_2026-10-20_21h00.zip       MỘT file để mang đi (create --zip)
└── SignBridge_ChuyenServer_2026-10-20_21h00.zip.sha256
```

Trong gói (và trong zip, dưới đúng một thư mục gốc cùng tên), thư mục được **đánh số theo thứ tự khôi phục**, tên tiếng Việt không dấu để mọi công cụ zip và đường dẫn Windows đều đọc được:

| Thư mục trong gói | Lấy từ | Lúc nào |
|---|---|---|
| `00_HUONG-DAN-KHOI-PHUC.md` | Hướng dẫn sinh riêng cho gói này, đọc trước | — |
| `01_ung-dung-va-database/` | `backup()`: mọi DB + roles, workspace (kể cả chưa commit, `.env`, dataset, video thô `raw_videos`, processed, gdrive), named volumes | writers dừng |
| `02_lich-su-git/` | `git bundle --all` + nhánh/HEAD/remotes | trước khi dừng |
| `03_google-drive/` | Toàn bộ cây `GOOGLE_DRIVE_ROOT_FOLDER_ID`, lưu theo file ID, kiểm md5; Google Sheets/Docs xuất `.xlsx/.docx`; theo cả shortcut ra ngoài cây; **mọi `*_SPREADSHEET_ID` trong `.env`** dù nằm ngoài thư mục gốc | writers dừng |
| `04_video-va-du-lieu-canh-repo/` | Thư mục **cạnh repo** thuộc hệ thống: video QIPEDC `qipedc_mau` (4.362 video), `voya_test_clips`, `voya_backups`, `voya-migration`, `voya_lop_vung_2026-08-14`, `2. BackupData_VOYA-Collector`. Khôi phục lại thành thư mục ngang hàng với app | trước khi dừng |
| `05_lich-su-backup/` | `backups/`, `BACKUP_HOST_DIR`/`BACKUP_MIRROR_HOST_DIR` nếu khác, các `--external` | writers dừng |
| `06_docker-images/` | `docker save` đúng image **container đang chạy** (theo ID nếu tag đã bị build đè) | trước khi dừng |
| `07_docker-volumes/` | Anonymous volumes của container (vd. `pg-backup`) | writers dừng |
| `08_file-trong-container/` | File ghi **bên trong** container, không nằm trên mount (`docker diff`); bỏ cache/`__pycache__` | writers dừng |
| `09_file-db-tro-ra-ngoai/` | File DB trỏ tới nhưng nằm ngoài repo | writers dừng |
| `10_cau-hinh-may-va-khoa/` | Token + ingress cloudflared, **khoá ký SOT `~/.voya`** (máy publisher), scheduled task VOYA, `.wslconfig`, `daemon.json`, phiên bản Docker/GPU | trước khi dừng |
| `11_bao-cao/db_file_refs.json` | Đối chiếu MỌI cột đường dẫn trong DB (`samples`, `raw_uploads`, `legal_*`, `training_jobs.checkpoint_path`, `tenant_exports`, `personal_exports`) với file thật: có trong repo / có trên Drive / **thiếu** | writers dừng |
| `PACK_MANIFEST.json` | SHA-256 mọi file + bảng khử trùng; ghi **sau cùng** | — |

### Quy trình chuyển server, từ đầu đến cuối

**Máy cũ** — PowerShell **Run as Administrator** (token cloudflared chỉ Admin đọc được), Docker đang chạy:

```powershell
# Một lần, trước mọi bản backup cuối: POSTGRES_PASSWORD phải >= 16 ký tự, nếu không
# restore trên máy mới dừng ở preflight. Đổi TRONG PostgreSQL trước rồi mới ghi .env,
# sau đó dựng lại container bằng `docker compose up -d` (giữ COMPOSE_FILE prod+gpu).
python scripts/migration_pack.py rotate-db-password

python scripts/deploy.py --check                                   # phải hết FAIL, máy mới sẽ chặn đúng chỗ đó
python scripts/migration_pack.py plan F:/                          # tên gói sẽ tạo + dung lượng, chỉ đọc
python scripts/migration_pack.py drive-sync F:/                    # chép Drive trước, site vẫn chạy; chạy lại được
python scripts/migration_pack.py create F:/ --allow-downtime --zip --keep-stopped   # BẢN CUỐI: dừng ghi, gói + zip + .sha256
scripts\chuyen_server\TAT_MAY_CU.bat                                # tắt tunnel (Disabled) + dừng stack; -HoanTac để bật lại
```

**Chép sang máy mới**: `F:/SignBridge_ChuyenServer/SignBridge_ChuyenServer_<ngày>_<giờ>.zip` **và** `.zip.sha256`.

**Máy mới** — cần sẵn Windows + WSL2, Docker Desktop (Linux containers), Python 3.11+, driver NVIDIA nếu dùng GPU:

1. Giải nén (chuột phải → Extract All, hoặc `tar -xf <file>.zip`), mở thư mục gói.
2. Chuột phải `1_KHOI_PHUC_MAY_MOI.bat` → **Run as administrator**. Script tự: kiểm tra máy (Python, Docker Linux, cổng 80 trống, ra được cổng 7844) → kiểm SHA-256 mọi file → dò GPU → `deploy.py --restore` vào `D:\SignBridge\app` (đổi bằng `-AppRoot`) → `restore-extras` → chờ `http://127.0.0.1` và `/api/v1/health` trả 200. **Không đụng domain.** Nhật ký: `khoi-phuc_<tên gói>.log`.
3. Mở `http://localhost` trên máy mới, đăng nhập, xem dữ liệu cũ, video, model.
4. Chuột phải `2_BAT_DOMAIN_MAY_MOI.bat` → **Run as administrator**: bắt gõ `MAY CU DA TAT`, cài connector của **chính tunnel hiện có** bằng token trong gói (cài `cloudflared` qua winget nếu thiếu), chờ tunnel sẵn sàng, kiểm tra domain trả 200.

DNS và route trên Cloudflare **không đổi**: domain → tunnel → `localhost:80` của máy đang chạy connector. Hai máy cùng chạy connector = Cloudflare chia request cho hai database riêng — vì vậy `TAT_MAY_CU` đặt service **Disabled** (reboot không tự bật lại) và `2_BAT_DOMAIN` từ chối chạy nếu máy mới đã có service Cloudflared.

**Quay lại máy cũ** (chỉ khi máy mới CHƯA phát sinh dữ liệu mới): máy mới `cloudflared service uninstall`, máy cũ `TAT_MAY_CU.bat -HoanTac`. Nếu máy mới đã ghi dữ liệu thì không quay DB cũ trực tiếp — xem `CTU_WINDOWS_MIGRATION_20261013.md` § "Điều kiện hoàn thành và quay lại".

Lệnh rời vẫn dùng được khi cần chạy tay: `migration_pack.py unzip <zip> D:/` (kiểm SHA-256 + giải nén + verify), `verify`, `restore-extras`, và `deploy.py --restore` (mục "Máy mới" bên dưới).

Zip: video, `.npz`, `.dump`, `.tar.gz`, Git bundle... **lưu nguyên không nén lại** (đã nén sẵn, nén nữa chỉ tốn giờ); file khác deflate. Zip64 nên vượt 4 GiB được. Sau khi ghi, mọi mục được đọc lại kiểm CRC rồi mới đổi tên từ `.zip.part` sang `.zip`. Thư mục gói được **giữ lại** cạnh zip (cần chỗ trống gấp đôi); xoá tay khi đã chép zip sang máy mới và `unzip` đạt.

### Video đi theo gói ở đâu

| Loại video | Nằm ở | Trong gói |
|---|---|---|
| Video thô người dùng tải lên | `dataset/raw_videos/<lang>/<dialect>/<class>/` + bản trên Drive | `01_ung-dung-va-database/` + `03_google-drive/`; `11_bao-cao/db_file_refs.json` đối chiếu từng dòng `raw_uploads` |
| Video mẫu QIPEDC | `../qipedc_mau` | `04_video-va-du-lieu-canh-repo/` |
| Clip thử | `../voya_test_clips`, `dataset_deploy/` | `04_video-va-du-lieu-canh-repo/`, `01_ung-dung-va-database/` |

**Khử trùng:** `04_...` và `05_...` lưu mỗi nội dung (cùng kích thước + SHA-256) **một lần**. `PACK_MANIFEST.json` → `dedup` ghi bản trùng nào trỏ về bản giữ lại; `verify` từ chối nếu bản giữ lại mất; `restore-extras` tạo lại mọi bản ở đúng chỗ cũ. Đo ngày 16/10/2026: 6,41 GiB → 3,61 GiB, chủ yếu vì `Videos` trùng hoàn toàn `qipedc_mau` (2,7 GiB). Sau khi so đủ 4.362/4.362 file bằng SHA-256, `Videos` đã được chuyển vào Thùng rác (16/10/2026); test và tài liệu trỏ sang `qipedc_mau`.

`plan` liệt kê các thư mục khác cạnh repo **không** được gom (dự án khác như `AI_HandSignLanguageModel`, `Signbridge_DTC`, `backup_dataset`...); thêm bằng `--external` nếu cần.

Hợp đồng:

- Thiếu `PACK_MANIFEST.json` = gói chưa xong; nó được ghi **sau cùng**. Thừa/thiếu/sai checksum bất kỳ file nào, Drive có file lỗi tải, hay inventory Drive trỏ tới file không có trong gói đều bị `verify` từ chối.
- Drive export **chỉ đọc**, chạy trong image backend, không ghi lại `token.json`. Từ chối chạy khi chưa đặt `GOOGLE_DRIVE_ROOT_FOLDER_ID` (không xuất cả My Drive). Mỗi lần sync chỉ tải file có `modifiedTime`/md5 đổi, xoá bản cục bộ của file đã xoá trên Drive.
- Lỗi sau khi snapshot xong → khởi động lại writers, không có manifest. `--keep-stopped` chỉ giữ dừng khi **thành công**.
- Gói phải **mới, ngoài repo**, không chồng lên thư mục history nào; cần trống ≥ dữ liệu local + 10% + 20 GiB.
- Thiếu thứ không bắt buộc (không đọc được token, không có `.wslconfig`) → `WARNING` trong manifest và khi `verify`, không âm thầm bỏ qua. `--skip-images` ghi rõ gói không đầy đủ.
- Chỉ stash mới nhất là ref nên chỉ nó đi theo bundle; nhiều stash hơn sẽ có cảnh báo.

## Cấu hình cần giữ đồng bộ

| Nhóm | Hợp đồng |
|---|---|
| Database | PostgreSQL 17; `POSTGRES_DB` trùng DB trong cả ba DSN; hostname nội bộ `postgres:5432` |
| DDL | `MIGRATION_DATABASE_URL` khớp `POSTGRES_USER` + `POSTGRES_PASSWORD` |
| Runtime | `DATABASE_URL` dùng `voya_app`, khớp `VOYA_APP_DB_PASSWORD`, không superuser/BYPASSRLS |
| Control | `CONTROL_DATABASE_URL` dùng `voya_control`, khớp `VOYA_CONTROL_DB_PASSWORD`, khác password runtime |
| Secrets | Password DB ≥16, `SECRET_KEY`/`AUTH_TOKEN_SECRET_KEY` ≥32; không thay khóa khi restore |
| Public URL | `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`, `deploy/public_hosts.txt`, HTTPS → `COOKIE_SECURE=1` |
| Dữ liệu/train | Giữ dataset paths, `FEATURE_DIM`, `SEQ_LEN`, model/normalization config từ nguồn; không tự đổi thông số mô hình theo host |

## Cập nhật host đang chạy

```bash
python3 scripts/deploy.py --check
python3 scripts/deploy.py --backup-dir /secure/backups/unique-release-name --allow-downtime --accept-external-storage
```

Đã có image registry: thêm `--image-tag sha-<40-character-commit>` và `VOYA_REGISTRY_NS` trong `.env`/environment. Commit source bind-mount phải khớp image, tracked worktree phải sạch. Không sử dụng tag `latest` cho deploy tự động.

Khi lỗi sau migration, giữ maintenance để chẩn đoán. Khôi phục bản trước vào **thư mục/project mới** theo lệnh restore ở trên, kiểm tra rồi chuyển proxy/traffic; đổi riêng image không đảo được migration. Không xóa project lỗi trước khi giữ đủ log/bản lưu.

## CI/CD GitHub

- `ci.yml`: frontend typecheck/i18n/tests/build; backend test trên PostgreSQL **17**, migration/provision/RLS; kiểm overlay; unit test ops + bài dump/restore PostgreSQL thật cô lập. Lint frontend vẫn advisory do nợ có sẵn, không được hiểu là lint đã sạch.
- `build_docker.yml` gọi CI cùng commit; tất cả job CI pass mới push đủ 3 image, SHA đầy đủ. CD chỉ chạy sau khi cả 3 image pass.
- CD **opt-in**: self-hosted runner Linux với labels `self-hosted, linux, voya-prod`, Python3.11+, Docker và quyền repo/registry. Chỉ cho nhánh tin cậy; không chạy PR tùy ý trên runner production.
- GitHub environment `production`: cấu hình approval/protected branches. Variables: `ENABLE_AUTO_DEPLOY=true`, `DEPLOY_BRANCH` (ví dụ `deploy_ctu_ver-2.2.1`), `DEPLOY_ROOT` (checkout thật đang phục vụ), `BACKUP_ROOT` (ngoài checkout), `ACCEPT_EXTERNAL_STORAGE=true` chỉ khi chấp nhận cùng Drive. Secrets: `DOCKER_USERNAME`, `DOCKER_PASSWORD` (token quyền push/pull).
- Bootstrap các script mới lên host trước khi bật CD. Host phải có checkout sạch và `.env` riêng; không chạy `actions/checkout`/clean vào thư mục dữ liệu live.
- CD: audit → full backup với writer dừng → checkout đúng SHA → pull image → migration → audit → mở gateway. Không cancel lượt production đang chạy. `--prepared-backup` là giao thức nội bộ cho CD, yêu cầu writer còn dừng và số dòng chưa đổi.
- Chưa xác nhận runner/secrets/environment trên GitHub của host này; thêm workflow **không đồng nghĩa CD đã được kích hoạt**.

## Kết quả thực tế 2026-09-21/22 (không thay thế lần kiểm tra mới)

- Stack đang healthy. Read-only audit image đang chạy: **33 PASS, 1 FAIL**; 4.213/4.213 NPZ tồn tại, CSV/DB khớp; schema v8, migration checksum và RLS đạt.
- FAIL: backfill RBAC chưa khớp legacy permissions. Cần người chịu trách nhiệm xem `python -m app.cli.backfill_authz --actor <account>` (dry-run), xác nhận trước khi `--apply`; không tự cấp quyền trong deploy.
- Preflight cấu hình còn thiếu/không đủ mạnh `VOYA_CONTROL_DB_PASSWORD`. Nếu password hợp lệ đã nằm trong `CONTROL_DATABASE_URL`, đồng bộ biến này, không xoay ngẫu nhiên. Một lỗi được sửa có thể làm lộ lỗi kế tiếp; chạy lại `--check` đến khi đạt.
- Cluster host còn **2 database người dùng ngoài DB chính** và có database ACL riêng; backup mới đã bao phủ chúng thay vì chỉ lấy `signdb`.
- Đã thử dump/restore thật bằng hai container PG17 tạm, không port/volume production: nhiều database, Unicode, số dòng, database ACL/settings, roles/RLS và chặn restore đè đều đạt. Chưa chạy full-host backup/restore hoặc redeploy production trong lần sửa này.
- **21/21** unit test ops đạt. Workflow YAML parse được, registry overlay phủ đủ 7 service dùng image ứng dụng.
- Frontend regression: **538 pass, 20 fail / 558 test**, 3 file lỗi / 74 file. Vì vậy CI chưa xanh và sẽ chặn phát hành; không tắt các test này để deploy.
- Freshness check: backend/frontend image cũ hơn source đang có; realtime image đạt phép kiểm. Healthy không chứng minh bản code mới đã triển khai.

## Test lại

```bash
python3 -m unittest discover -s scripts/ops/tests -v
python3 scripts/ops/tests/restore_drill.py
```
