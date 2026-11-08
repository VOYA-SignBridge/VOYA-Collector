# Vòng đời hạ tầng: dựng → triển khai → chạy → sao lưu → nâng cấp → gỡ

*Cập nhật 2026-08-10.*

## 1. Trạng thái từng giai đoạn

| Giai đoạn | Trạng thái | Ở đâu |
|---|---|---|
| Dựng ảnh | **đủ** | `.github/workflows/ci.yml` (kiểm) + `build_docker.yml` (đẩy) |
| Triển khai | có | `scripts/deploy.sh`, `cli/verify_deployment.py`, `check_deploy_freshness.py` |
| Chạy & giám sát | có | 14/14 healthcheck, Prometheus/Grafana/Loki |
| Sao lưu & khôi phục | có **diễn tập** | `docs/06-operations/BACKUP_RESTORE.md`, `pg_backup.sh --drill` |
| **Môi trường thử** | **có** *(mới 10/08)* | `docker-compose.staging.yml`, `scripts/staging.sh` |
| Migration có đường lùi | **không** | xem §5 |
| Triển khai không gián đoạn | **không** | xem §5 |
| Xoay khoá bí mật | **không** | xem §5 |
| RPO/RTO công bố | **có** *(mới 10/08)* | §4 |
| Chính sách lưu log | **có** *(mới 10/08)* | §6 |

---

## 2. Môi trường thử

```bash
./scripts/staging.sh up       # dựng
./scripts/staging.sh check    # trạng thái + kiểm nợ lược đồ
./scripts/staging.sh reset    # xoá sạch, dựng lại từ số không
./scripts/staging.sh down     # dừng, giữ dữ liệu
```

Mở ở `http://127.0.0.1:8080` (chỉ loopback).

**Cách ly bằng tên dự án compose, không phải bằng tên tài nguyên.** Chạy dưới
`-p voya-staging`, nên container, volume và network đều mang tiền tố riêng
(`voya-staging_postgres_data` so với `voya-collector_postgres_data`). Staging
không thể chạm vào volume sản xuất kể cả khi gõ nhầm lệnh — điều mà việc đổi tên
từng tài nguyên trong tệp overlay **không** bảo đảm được, vì bỏ sót một dòng là
đủ để hai stack dùng chung một volume.

### Staging khởi động từ CSDL trống, và đó là điểm mạnh

Không chép dữ liệu sản xuất sang. Hai lý do, lý do thứ hai quan trọng hơn:

1. Dữ liệu thật ở đây là **khuôn mặt và bàn tay của người thật**. Nhân bản chúng
   sang một môi trường lỏng hơn là mở rộng bề mặt rủi ro mà không ai đồng ý.
2. **Khởi động sạch chính là thứ đáng thử nhất.** Kịch bản "máy thứ hai" đã hỏng
   trong im lặng suốt nhiều tháng: `ensure_tables()` dựng ra lược đồ thiếu 2
   bảng, 7 khoá ngoại và 14 cột so với máy đang chạy. Staging chạy đúng đường đó
   mỗi lần `reset`, và `staging.sh check` kiểm bằng `schema_debt()`.

### Ba thứ staging cố ý làm khác

| | Vì sao |
|---|---|
| `USE_GOOGLE_DRIVE=0` | không có `gdrive/` trên máy thử; `sot-init` bỏ qua sạch sẽ và trả 0. **Không** nới phép kiểm chữ ký để đạt điều này |
| `SMTP_HOST=` rỗng | thư ghi ra log thay vì gửi. Một thư "gói sắp hết hạn" từ staging tới người dùng thật chỉ cần xảy ra một lần |
| `SUBSCRIPTION_SWEEP_ENABLED=0` | lượt quét đổi trạng thái thanh toán và gửi thư — không nên tự chạy ở nơi người ta bấm thử |

---

## 3. Cổng trước khi triển khai

Bốn phép kiểm, theo thứ tự, không bỏ phép nào:

```bash
# 1. CI xanh trên PR  (tự động — .github/workflows/ci.yml)
# 2. Staging dựng lại được từ số không
./scripts/staging.sh reset && ./scripts/staging.sh check
# 3. Nợ lược đồ phải rỗng sau BA lần boot liên tiếp
# 4. Sau khi triển khai
docker compose exec backend python -m app.cli.verify_deployment
```

---

## 4. RPO / RTO — con số, không phải lời hứa

| Chỉ số | Cam kết | Đo bằng |
|---|---|---|
| **RPO** (mất tối đa bao nhiêu dữ liệu) | **24 giờ** cho Postgres | `pg-backup` chạy hằng ngày — đo được từ lịch |
| | **~0** cho mẫu đã thu | `dataset/samples.csv` là nguồn sự thật, ghi đồng bộ ngay lúc thu |
| **RTO** (bao lâu thì chạy lại được) | **CHƯA ĐO** | xem dưới |

RPO là con số **suy ra từ lịch chạy**, nên nó đúng chừng nào `pg-backup` còn
chạy. RTO thì khác: nó chỉ biết được bằng cách bấm đồng hồ trong một lần khôi
phục thật. Diễn tập `pg_restore.sh --drill` đã chạy và **ĐẠT** (44 bảng, 0
lệch), nhưng **thời gian không được ghi lại** — nên ở đây không có con số, và
viết một con số ước lượng vào ô đó là biến một chỗ trống thành một lời hứa.

Cách lấp: chạy `time ./scripts/pg_restore.sh --drill` một lần và ghi kết quả
vào chính ô này.

**Điều kiện để hai con số trên đúng**, và cả hai đều chưa thoả:

- `BACKUP_PASSPHRASE` / `BACKUP_MIRROR_*` — cơ chế mã hoá và bản sao ổ khác đã
  có, **mặc định TẮT**. Chưa bật thì bản sao lưu nằm cùng một ổ với dữ liệu gốc,
  và RPO 24 giờ không sống sót qua một lần hỏng ổ.
- **Chưa có bản sao ngoài máy.** Cháy phòng máy là mất cả hai.

Nói ra ở đây chứ không giấu: một RPO công bố mà điều kiện chưa thoả thì tệ hơn
không công bố.

---

## 5. Ba thứ vẫn chưa có, và vì sao chúng không dễ

### Migration không có đường lùi

Không hàm `downgrade` nào trong kho. Mọi thay đổi lược đồ là luỹ tiến
(`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`), nên **lùi mã** được
mà **lùi lược đồ** thì không.

Điều này ít nguy hiểm hơn vẻ ngoài của nó, vì mọi câu đều cộng thêm chứ không
lấy đi: mã cũ chạy được trên lược đồ mới. Nhưng nó ngừng đúng nếu có ai đó viết
một câu `DROP COLUMN` — và không có gì trong kho ngăn việc đó.

**Luật cần giữ:** không `DROP` cột hay bảng trong `MIGRATION_STATEMENTS`. Muốn
bỏ một cột thì để nó lại và ngừng đọc; dọn dẹp là một đợt riêng, sau khi mọi
bản triển khai đã lên mã mới.

### Triển khai vẫn gián đoạn

Dựng lại container là có downtime. Không nghiêm trọng với quy mô hiện tại (một
trường, giờ hành chính), nhưng phải nói ra thay vì để người đọc tự cho rằng có.

### Không có quy trình xoay khoá bí mật

Khoá SOT (Ed25519), `JWT_SECRET`, `OTP_PEPPER`, khoá API của tenant — không cái
nào có hạn dùng, không cái nào có đường xoay. Đây là **khoảng trống thật**, và
nó lớn dần theo thời gian: một khoá không bao giờ xoay là một khoá mà mọi lần rò
rỉ trong quá khứ vẫn còn giá trị.

Thứ tự nên làm khi có thời gian: khoá API tenant (đã có `revoked_at`, gần nhất
với việc xoay được) → khoá SOT (cần hỗ trợ nhiều khoá cùng lúc trong
`effective_authorized_keys`) → `JWT_SECRET` (cần chấp nhận hai khoá trong thời
gian chuyển tiếp).

---

## 6. Chính sách lưu log

Đây là chính sách **đang có hiệu lực**, đọc thẳng từ cấu hình chứ không từ ý
định — hai con số đầu tôi viết sai ở bản nháp và phải sửa sau khi mở tệp ra.

| Nguồn | Giữ bao lâu | Cưỡng chế bởi |
|---|---|---|
| Loki (log ứng dụng) | **7 ngày** | `limits_config.retention_period: 168h` + `compactor.retention_enabled: true` trong `logging/loki-config.yaml` |
| Prometheus (số đo) | **7 ngày** | `--storage.tsdb.retention.time=7d` trong `docker-compose.yml` |
| `audit_log` (Postgres) | **không xoá** | có chủ ý — đây là bằng chứng |
| `webhook_deliveries` | 30 ngày | `saas_tasks.cleanup_saas_artifacts` |
| Bản xuất của tenant | 7 ngày | `TENANT_EXPORT_TTL_DAYS` |

**7 ngày là ngắn**, và đáng bàn: một sự cố phát hiện muộn hơn một tuần thì không
còn log để dò. Nâng lên 30 ngày là đổi một dòng, cái giá là dung lượng — và ổ E
đang ở 87,5%, nên đó là quyết định phải cân với chỗ trống chứ không phải một
lựa chọn miễn phí.

**`audit_log` không nằm trong chính sách xoá**, và đó là điểm khác biệt cần giữ:
log ứng dụng là công cụ chẩn đoán, còn sổ kiểm toán là bằng chứng về việc ai đã
làm gì. Xoá nó theo lịch là xoá đúng thứ mà nó tồn tại để giữ.

---

## 7. Gỡ bỏ

Xoá một tenant là thao tác **không hoàn tác được duy nhất** trong hệ thống, nên
nó có ba phanh: xoá mềm trước, ân hạn `TENANT_PURGE_GRACE_DAYS` (30 ngày), và
`confirm_tenant_id` phải gõ đúng — một chuỗi, không phải một cờ boolean, vì cờ
boolean bị vượt qua bởi mọi thứ từ lỡ tay tới một script chạy sai biến.

`purge-preview` đếm trước từng bảng. "Bạn có chắc không?" mà không kèm "3.860
mẫu, 63 lớp, 10 tài khoản" là một câu hỏi người ta bấm qua theo phản xạ.
