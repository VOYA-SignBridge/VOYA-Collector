# Chuyển SignBridge sang PC Windows tại trường

Ngày kiểm tra: 13/10/2026. Đây là kế hoạch dựa trên kiểm kê nguồn, chưa phải biên bản đã backup/restore thành công.

## Phạm vi đã chốt

- Nguồn: `E:\CTU_ProjectOutside\VOYA-Collector`, Windows + Docker Linux containers.
- Đích: PC Windows RTX 5060 tại trường; thao tác qua UltraViewer, không cần SSH.
- Giữ đúng URL `https://signbrigde.mainhatminh.id.vn` (chữ `brigde`).
- Dùng lại Cloudflare Tunnel hiện có. Giữ DNS/hostname nếu route hiện tại vẫn đúng.
- Restore vào thư mục và Compose project mới; giữ nguyên bản cũ trên cả hai máy.
- Chuyển toàn bộ dữ liệu ứng dụng, mọi tenant, dữ liệu cloud liên quan và lịch sử backup. Không coi việc chỉ chép source hoặc dump một DB là hoàn tất.

## Kết quả kiểm tra máy nguồn

| Hạng mục | Kết quả |
|---|---|
| PostgreSQL | 4 database không phải template: `signdb`, `signdb_test`, `other_signdb`, `postgres`; tổng khoảng 57 MiB theo pg_database_size |
| `processed` | 65.252 file, khoảng 3,071 GiB |
| `dataset` | 20.113 file, khoảng 0,293 GiB |
| `dataset_deploy` | 2.126 file, khoảng 0,045 GiB |
| Source/config | Nhiều thay đổi tracked và untracked; phải giữ working tree thực tế |
| Google Drive | `USE_GOOGLE_DRIVE=1`; chưa kiểm kê dung lượng hoặc tải bản sao cloud |
| Named volumes | PostgreSQL, Redis, Grafana, Loki, Prometheus |
| Mount bổ sung | `pg-backup` có anonymous volume tại `/var/lib/postgresql/data`; phải kiểm tra nội dung, không mặc định coi là đã có trong bundle |
| Ổ workspace | Khoảng 51,43 GiB trống lúc kiểm tra; chưa đo dung lượng Docker volumes/image/Drive |
| Backup preflight | Đạt Linux Docker, RAM/disk và bind mounts với `strict=False` |
| Deploy preflight | Dừng ở `POSTGRES_PASSWORD must have at least 16 characters`; chưa chứng minh các kiểm tra sau đều đạt |
| Live audit | 31 PASS / 2 WARN / 1 FAIL; schema v8, checksum migration và 4.213/4.213 NPZ đạt; FAIL đối chiếu backfill phân quyền RBAC |
| Cảnh báo audit | Ổ dữ liệu đã dùng khoảng 89%; consent snapshot 28 ngày tuổi so với ngưỡng 7 ngày |
| Unit test ops | 21/21 đạt ngoài sandbox; dùng dữ liệu giả, không phải full restore drill |

Số liệu file là kiểm kê khi hệ thống đang chạy, chỉ để ước lượng. Manifest của lần backup cuối mới là mốc đối chiếu chính thức.

## Gói dữ liệu cần chuyển

### 1. Bundle phục hồi ứng dụng

Script `scripts/backup.py` hiện có tạo:

- Dump mọi database không phải template, gồm dữ liệu mọi tenant; roles, password hashes, owner và quyền.
- `workspace.tar.gz`: working tree hiện tại, `.env`, dataset, video/NPZ có trên đĩa, CSV, legal, processed/checkpoints/model, cấu hình, credentials/cache Drive và các thư mục khác trong workspace không bị loại trừ.
- Archive các named volume Redis/Grafana/Loki/Prometheus khai báo trong Compose. PostgreSQL được phục hồi bằng logical dump, không copy nóng volume database.
- `manifest.json`, SHA-256 và số dòng từng bảng tại thời điểm snapshot.

### 2. Dữ liệu bổ sung để đáp ứng “tất cả dữ liệu”

Bundle trên KHÔNG tự bao gồm:

- File chỉ nằm trên Google Drive: cần bản sao riêng của toàn bộ cây dữ liệu ứng dụng và file ngoài cây đó được DB tham chiếu. Kiểm kê file ID, parent ID, tên, kích thước và checksum khi có; đối chiếu bản tải về. Không tải lên lại thành các file mới nếu ứng dụng vẫn dùng file ID cũ. Credentials/token không thay thế bản sao dữ liệu cloud.
- `backups/` và các backup mirror: sao chép riêng lịch sử backup, kiểm tra checksum. Không nhét archive bổ sung vào thư mục bundle vì verifier từ chối file ngoài manifest.
- `.git`: giữ riêng lịch sử Git nếu cần bảo toàn toàn bộ repo; working tree chưa commit đã nằm trong bundle.
- Anonymous volume phát hiện trên `pg-backup`, dữ liệu ngoài Compose, file trong writable layer của container, cấu hình cloudflared bên ngoài workspace: kiểm kê và lưu riêng phần có giá trị. Không xuất Docker inspect thô có thể lộ token.
- Docker images đang chạy: nên export riêng các image ID thực tế để giữ khả năng tái lập đúng bản live, nhất là source hiện có thể khác image. `deploy.py --restore` mặc định build lại source, không tự dùng archive image.

Không cần chuyển `node_modules`, `.venv*`, build cache vì có thể dựng lại. Nếu cần bảo toàn các thay đổi thủ công trong dependency/container, phải nhận diện và lưu riêng trước.

Giữ các artifact bổ sung ở thư mục ngang hàng với bundle. Dữ liệu chứa khóa, credentials và thông tin người dùng: dùng ổ/transport mã hóa, không đưa vào GitHub hoặc link chia sẻ công khai.

## Trình tự chuyển

### A. Chuẩn bị máy Windows trường qua UltraViewer

1. Kiểm tra bản Windows còn được Docker hỗ trợ, WSL2, Docker Desktop ở chế độ Linux containers, Python 3.11+, driver NVIDIA và quyền ghi thư mục đích.
2. Chọn ổ dữ liệu thực tế, ví dụ `D:\SignBridge`; kiểm tra riêng dung lượng ổ chứa Docker Desktop VHDX. Cần chỗ cho bundle, bản giải nén, DB/volumes, images/build cache và bản dự phòng. Chưa có đủ số liệu để chốt tổng dung lượng.
3. Tắt sleep/hibernate khi vận hành. Kiểm tra Docker và cloudflared có hoạt động sau reboot; không mặc định Windows service của Docker tự chạy Linux engine trước đăng nhập.
4. Cài cloudflared nhưng CHƯA chạy connector production của tunnel này.
5. Kiểm tra cổng Nginx và các cổng publish khác có bị deployment cũ chiếm không. Project mới không tự giải quyết xung đột port. Không xóa deployment cũ.
6. Máy phải kết nối outbound được tới Cloudflare Tunnel trên TCP/UDP 7844.

Các lệnh chỉ đọc để lấy thông tin máy đích:

```powershell
winver
wsl --status
docker version
docker compose version
docker info --format '{{.OSType}} {{.Architecture}} {{.MemTotal}}'
python --version
nvidia-smi
Get-PSDrive -PSProvider FileSystem
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

### B. Chuẩn bị khả năng restore trước giờ ngừng ghi

- Xử lý lỗi mật khẩu PostgreSQL của deploy preflight theo kế hoạch đồng bộ password DB, DSN và Compose. Chỉ đổi `.env` không thay password trong PostgreSQL đã tồn tại; dump roles còn có thể khôi phục password cũ. Không tự xoay signing keys/token secrets và không bỏ qua validation.
- Chạy kiểm tra schema/RBAC/file trên nguồn; chuẩn bị sửa lỗi thực sự trước khi cutover. Source mới và image đang chạy phải được đối chiếu; không gộp một lần nâng cấp chưa kiểm thử vào việc chuyển host mà không kiểm tra.
- Lập danh sách Google Drive và tải bản sao ban đầu. Tiếp tục dùng cùng Drive trên máy mới để giữ file ID/quyền, nhưng vẫn tạo bản sao độc lập để đáp ứng yêu cầu toàn bộ dữ liệu.
- Backup thử/restore thử dùng project cô lập. Không chạy worker/trainer/beat trên bản thử nếu nó còn trỏ vào Drive production; chúng có thể ghi lên cloud ngay cả khi chưa bật tunnel.
- Giải quyết các điều kiện còn thiếu trước khi chạy lệnh restore dưới đây. Script hiện tại kiểm tra strict trước khi restore; chưa thể chạy thành công với cấu hình nguồn đang bị chặn.

### C. Tạo bản cuối trong khoảng bảo trì

> **Cập nhật 16/10/2026 (tự động hoá):** cả quy trình A–G giờ gói trong `HOST_TRANSFER.md` § "Quy trình chuyển server, từ đầu đến cuối": máy cũ `rotate-db-password` → `create F:/ --zip --keep-stopped` → `TAT_MAY_CU.bat`; máy trường `1_KHOI_PHUC_MAY_MOI.bat` rồi `2_BAT_DOMAIN_MAY_MOI.bat` (hai file nằm sẵn trong gói). Lỗi `POSTGRES_PASSWORD` ở mục B được xử lý bằng `rotate-db-password`.

> **Cập nhật 16/10/2026:** mục "Dữ liệu bổ sung" ở trên (Drive, `backups/`, `.git`, anonymous volume, cloudflared, images) nay được gom tự động bằng `scripts/migration_pack.py` thành một gói có manifest chung. Dùng `migration_pack.py create F:/ --allow-downtime --zip --keep-stopped` thay cho lệnh `backup.py` ở bước 4; mang sang máy trường file `F:/SignBridge_ChuyenServer/SignBridge_ChuyenServer_<ngày>_<giờ>.zip` cùng file `.zip.sha256` đi kèm, rồi `migration_pack.py unzip` trên máy đích. Xem `HOST_TRANSFER.md` § "Gói chuyển server đầy đủ". Các bước dừng writer/connector dưới đây vẫn giữ nguyên.

1. Ngừng nhận upload/thay đổi dữ liệu, đợi mọi task đang chạy kết thúc. Kiểm tra cả task chờ, task reserved/scheduled, trainer và các chương trình ngoài Docker. Dừng scheduler trước khi chốt. Không flush Redis để làm mất task.
2. Dừng connector cloudflared trên máy cũ; không xóa tunnel/DNS và không xoay token trong bước này.
3. Dừng mọi công cụ ngoài Docker còn sửa source/dataset/Drive. Chốt bản sao Drive cuối cùng và đối chiếu dữ liệu sau khi các writer đã dừng.
4. Tạo bundle cuối, giữ các writer dừng sau khi thành công:

```powershell
# Chạy từ E:\CTU_ProjectOutside\VOYA-Collector.
# Ví dụ đường dẫn: phải chọn thư mục mới, ngoài workspace, đủ chỗ trống.
python scripts/backup.py E:/SignBridge-transfer/ctu-final-20261013 --allow-downtime --accept-external-storage --keep-stopped
python scripts/backup.py E:/SignBridge-transfer/ctu-final-20261013 --verify-only
```

`--accept-external-storage` chỉ xác nhận máy đích tiếp tục dùng cùng Drive; KHÔNG tải backup Drive. `--keep-stopped` giữ ứng dụng nguồn dừng sau thành công, còn PostgreSQL vẫn chạy. Script có thể khởi động lại các service đã dừng nếu backup lỗi; phải kiểm tra trạng thái trước khi thử lại và luôn dùng tên bundle mới.

Backup có dừng dịch vụ trong suốt dump/copy/verify; 300 giây là timeout drain, không phải cam kết tổng thời gian gián đoạn.

### D. Chuyển file sang PC trường

- Dùng SSD/USB mã hóa, hoặc kênh truyền file riêng sẵn có trên hai máy; nếu dùng Drive để vận chuyển thì mã hóa archive chứa secrets trước khi upload. SSH không bắt buộc.
- Chuyển nguyên thư mục bundle, các bản sao bổ sung, và bộ công cụ `scripts/backup.py`, `scripts/deploy.py`, toàn bộ `scripts/ops/` đặt trong một thư mục công cụ riêng.
- Chạy `--verify-only` trên máy đích. Không chỉnh sửa nội dung bundle. Đối chiếu checksum riêng cho Drive archive, lịch sử backup, Git và image archives.

### E. Restore vào project mới

Ví dụ dưới đây chỉ dùng SAU KHI lỗi cấu hình đã được giải quyết và kiểm tra restore thử đạt. Thay ổ/path theo máy thật; thư mục cha phải có sẵn, `--root` chưa được tồn tại, project name chưa từng dùng.

```powershell
# Chạy từ thư mục công cụ đã mang sang máy trường.
python scripts/backup.py D:/SignBridge-transfer/ctu-final-20261013 --verify-only
python scripts/deploy.py --restore D:/SignBridge-transfer/ctu-final-20261013 --root D:/SignBridge/ctu-20261013 --project signbridge-ctu-20261013 --public-url https://signbrigde.mainhatminh.id.vn --allow-downtime --accept-external-storage
```

Script khôi phục database/roles, so số dòng từng bảng và phục hồi declared named volumes; sau đó build/migrate/kiểm tra và khởi động ứng dụng. Nó không khôi phục các bản sao bổ sung hoặc cài cloudflared. Nó có thể bắt đầu worker/beat trước khi tunnel bật; chỉ làm trên bản cuối khi nguồn đã ngừng ghi.

Giữ `VITE_BASE_PATH=/`, `VITE_API_URL=` và `COOKIE_PATH_PREFIX=` cho domain gốc này. Script destination_settings chưa tự chuẩn hóa ba biến đó theo URL, dù nguồn hiện có giá trị phù hợp. Nếu đổi cổng đích phải điều chỉnh cấu hình triển khai trước bước tạo container.

Nếu có lỗi, giữ project/thư mục lỗi để điều tra. Không `docker compose down -v`, không overwrite volume/dataset của bản cũ.

### F. Kiểm tra và kích hoạt GPU

- Trước hết kiểm tra restore, giao diện, tài khoản/quyền, video cũ, file download, số mẫu, model/checkpoint và quyền truy cập Drive.
- Docker Desktop Windows cần WSL2 backend để đưa NVIDIA GPU vào Linux containers.
- Source backend hiện pin `torch==2.7.1+cu128`; realtime image cài bản CPU. Overlay `docker-compose.gpu.yml` hiện cấp GPU cho **trainer**. Có RTX 5060 không đồng nghĩa mọi service tự dùng GPU.
- Kiểm tra GPU trong container và chạy phép tính PyTorch CUDA thực sự cùng một bài inference/train nhỏ trước khi bật `--gpu` trong quy trình đã kiểm thử. Chỉ `nvidia-smi` hoặc `torch.cuda.is_available()` chưa đủ chứng minh kernel tương thích.

### G. Chuyển tunnel sau khi máy mới đã đạt kiểm tra

1. Xác nhận connector cũ đã offline và writer cũ vẫn dừng.
2. Lấy lệnh cài connector của CHÍNH tunnel hiện có từ Cloudflare dashboard, chọn Windows. Nhập token trực tiếp trên máy trường, không dán vào chat/tài liệu/Git.
3. Nếu giữ route `http://localhost:80`, cloudflared phải chạy trên Windows host và Nginx mới phải publish ở port 80. Nếu dùng Docker cho cloudflared, `localhost` là chính container; cần địa chỉ service/network phù hợp.
4. Bật connector trên máy trường. Không chạy hai connector cùng tunnel tới hai database độc lập: Cloudflare có thể gửi request về cả hai máy.
5. Kiểm tra tunnel Healthy, HTTPS và truy cập qua 4G: đăng nhập/refresh, quyền tenant, dữ liệu cũ, upload, camera, realtime, model và email reset. Nếu thử HTTP localhost khi cookie Secure=1 thì đăng nhập có thể thất bại; không hạ bảo mật production chỉ để thử localhost.
6. Kiểm tra reboot, Docker/container/connector tự hoạt động. Người dùng tiếp tục dùng đúng URL cũ; không cần đổi DNS nếu giữ nguyên tunnel/route.

## Điều kiện hoàn thành và quay lại

- Có bản local bundle đã verify trên cả hai máy, archive Drive đã đối chiếu, bản sao các phần bị loại trừ có manifest/checksum.
- Restore so số dòng mọi bảng của mọi DB đạt; file có trong DB tồn tại tại local hoặc Drive theo thiết kế; kiểm tra checksum và model đạt.
- Schema/RBAC/audit/health và thử nghiệp vụ trên máy mới đạt; không có hai nguồn ghi độc lập.
- Trước khi máy mới phát sinh ghi: nếu lỗi, dừng connector/service máy mới, khởi động lại stack máy cũ và connector cũ.
- Sau khi máy mới đã ghi (kể cả background task hoặc Drive): không quay về bản DB cũ trực tiếp. Ngừng ghi mới, backup phần phát sinh, đối chiếu/đồng bộ hoặc restore bản mới về máy cũ trước khi mở lại người dùng.
- Giữ nguyên máy cũ và các bản lưu cho đến khi xác nhận đủ dữ liệu và vận hành ổn. Chuyển host không phải lý do xóa lịch sử backup.

## Tài liệu tham khảo

- Hướng dẫn repo: `docs/06-operations/HOST_TRANSFER.md`.
- Docker GPU trên Windows: https://docs.docker.com/desktop/features/gpu/
- Cloudflare tunnel replicas, firewall: https://developers.cloudflare.com/tunnel/configuration/
