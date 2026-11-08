# CI/CD

> Viết 2026-09-11, sau khi phát hiện kho có hai workflow mà **chưa cái nào từng
> chạy trên mã đang chạy thật**.

## 1. Tình trạng trước ngày 11/09/2026

Kho có `.github/workflows/ci.yml` và `build_docker.yml` từ 12/08. Nhìn vào kho
thì có vẻ đã có cổng kiểm. Thực tế:

| Sự thật | Hệ quả |
|---|---|
| `ci.yml` chỉ kích hoạt trên `main` | Công việc nằm trên `deploy_ctu_ver-2.2.1`, đi trước `main` **253 commit** — cổng chưa soi một dòng nào trong bốn tháng |
| `ci.yml` chỉ tồn tại trên nhánh làm việc, không có trên `origin/main` | Trên GitHub, workflow duy nhất đang sống là bản cũ |
| `build_docker.yml` bản trên `main` chạy trên **mỗi pull request** và đẩy `:latest` | Một PR chưa ai duyệt ghi đè ảnh mà máy sản xuất kéo về |
| Bản ấy liệt kê `:latest` **hai lần**, không có tag theo commit | Không truy được ảnh về commit — gốc rễ của "healthy nhưng chạy mã cũ" |
| Cả ba tệp compose đều `build:` với tag **cục bộ** | Ảnh đẩy lên Docker Hub **không ai kéo về**; mọi lượt triển khai dựng lại tại chỗ |

Một cổng không bao giờ kích hoạt không phải cổng lỏng — nó là cổng **không tồn
tại**, và tệ hơn ở chỗ nhìn vào kho thì tưởng là có.

## 2. Các job của `ci.yml`

Kích hoạt:
- **mọi lần push lên bất kỳ nhánh nào** (từ 08/11/2026);
- PR vào `main`;
- chạy tay bằng `workflow_dispatch`.

Riêng push lên `main` thì `build_docker.yml` gọi lại tệp này trước khi dựng ảnh.

| Job | Kiểm gì | Thời gian |
|---|---|---|
| `frontend` | Kiểu, i18n, test, dựng, lint (chặn lỗi, trần 54 cảnh báo) | ~2 phút |
| `backend` | Phụ thuộc không xung đột, migration, phân quyền, **nâng cấp từ lược đồ bản trước**, pytest trên CSDL mới | ~15 phút |
| `wiring` | Script, cấu hình, tài liệu khớp với mã (xem dưới) | ~2 phút |
| `images` | Dựng thử 3 ảnh, không đẩy. Chỉ chạy ở PR và nhánh khác `main` | ~10 phút |
| `hygiene` | LF, `.env`, lớp phủ registry, sao lưu/khôi phục | ~3 phút |

### `frontend`

`npm ci` → kiểm kiểu → **cổng i18n** → vitest → dựng → lint (tư vấn).

- Dùng `npm run typecheck`, **không** `npx tsc --noEmit`: lệnh sau đọc
  `tsconfig.json` gốc (`files: []` + hai project reference) nên kiểm **không tệp
  nào**, thoát 0, và trông y hệt một lượt kiểm sạch.
- Bước **dựng thật** giữ lại vì `tsc -b` bắt được lớp lỗi mà `typecheck` không
  bắt, và kho này đã từng ở trạng thái dựng-không-được trong khi kiểm kiểu xanh.
- Lint chạy nhưng `continue-on-error: true`. Đo 11/09: **85 lỗi, 55 cảnh báo**.
  Bật chặn ngay thì mọi PR đỏ vì nợ có sẵn, và phản ứng tất yếu của người đang
  vội là tắt cổng — mất luôn cả những cổng đang có ích. Ba lỗi `rules-of-hooks`
  trong `DataSplitVisualization.tsx` là lỗi thật; sửa xong nhóm đó thì đổi
  `continue-on-error` thành `false`.

### `backend`

Postgres 16 + Redis 7 dựng mới → `app.cli.migrate --to <APP_SCHEMA_VERSION>` →
**cấp vai bằng `app.cli.provision_db_roles`** → kiểm nợ lược đồ → pytest.

- Dùng `app.cli.migrate`, **không** `ensure_tables()`: từ 12/08 `ensure_tables()`
  chỉ còn THÊM; phần một chiều (bỏ bảng cũ, chép dữ liệu sang `memberships`, bỏ
  chỉ mục toàn cục) chỉ chạy dưới lệnh migration. Gọi `ensure_tables()` ở đây sẽ
  để lại `tenant_members` là BẢNG chứ không phải view.
- `EXPECTED_DATABASE` bắt buộc — chốt chặn đích, sau sự cố migration chạy nhầm
  lên sản xuất ngày 12/08.
- Phiên bản đích hỏi chính mã chứ không viết cứng trong YAML: một con số trong
  workflow sẽ trôi khỏi `APP_SCHEMA_VERSION` ngay lần bump đầu tiên, và trôi
  trong im lặng.

### `wiring`: những thứ nằm giữa các phần

Không bộ test nào của backend hay frontend đọc những thứ này, nên chúng hỏng
mà không ai biết cho tới lúc dùng. Cả ba lỗi của ngày 08/11/2026 đều thuộc
loại này.

| Bước | Bắt lỗi gì | Lỗi thật đã gặp |
|---|---|---|
| `actionlint` | Workflow sai cú pháp, sai biểu thức, `needs` trỏ vào job không có | |
| `scripts/check_app_imports.py` | Mã **ngoài** `backend/app` (CI, script, PowerShell, test) gọi module hoặc tên không tồn tại | Đợt tái cấu trúc dời 9 module; CI và công cụ chuyển server vẫn gọi đường cũ |
| `scripts/check_compose_contracts.py` | Chuỗi bảo trì `voya.py` → `nginx.conf.d/` → mount → `nginx.conf` còn nối; tệp cấu hình được gắn vào container phải có trong git; mọi `COPY` trong Dockerfile trỏ vào tệp có thật | Mất dòng gắn `nginx.conf.d`: người dùng nhận lỗi 502 thay vì trang bảo trì |
| `scripts/check_docs.py` | Không có luận văn, báo cáo hay tên người ký trong repo; không có email thật; không có tệp lẻ ở gốc `docs/`; không có liên kết hỏng (trừ `11-worklog/`) | Tài liệu công khai từng chứa email sinh viên và tên người ký |
| Cú pháp Python, shell, PowerShell | Lỗi cú pháp trong script chỉ chạy tay | |
| `docker compose config` | 5 tổ hợp tệp compose mà máy thật dùng phải gộp được với `.env.example` | |
| `nginx -t` | Cấu hình nginx hợp lệ | |

Chạy trên máy mình trước khi push:

```bash
python scripts/check_app_imports.py
python scripts/check_compose_contracts.py
python scripts/check_docs.py
```

### Nâng cấp từ lược đồ bản trước (trong job `backend`)

Máy chạy web không dựng lược đồ từ số không mà **nâng** từ lược đồ bản trước. Bước này lấy mã của bản trước bằng `git worktree`: commit cha nếu đang ở `main`, hoặc điểm rẽ nhánh với `main` nếu ở nhánh khác. Mã đó dựng một CSDL riêng, rồi mã hiện tại nâng nó lên và kiểm nợ lược đồ. Không tải ảnh nào, chỉ tốn vài chục giây.

## 2b. `security.yml`: quét bảo mật (chế độ cảnh báo)

Chạy mỗi thứ Hai, ở mỗi PR vào `main`, và chạy tay được. **Không chặn PR nào**: kết quả ghi vào trang Summary của lượt chạy.

| Job | Quét gì |
|---|---|
| gitleaks | Bí mật lọt vào git. PR: chỉ commit mới. Hằng tuần: toàn bộ lịch sử. Báo nhầm đã kiểm khai trong `.gitleaks.toml` |
| pip-audit | Lỗ hổng đã công bố trong `backend/requirements.txt` |
| npm audit | Lỗ hổng trong gói frontend chạy thật |
| Trivy | Lỗ hổng trong 3 ảnh đã phát hành trên Docker Hub (chỉ theo lịch) |

Lượt đo đầu tiên (08/11/2026):

| Nguồn | Kết quả |
|---|---|
| Python | 20/153 gói có lỗ hổng. Đáng lo nhất: `python-multipart 0.0.6`, `starlette 0.27`, `fastapi 0.95` (đường tải tệp lên và mọi request), `python-jose 3.3.0` (JWT), `pillow` |
| npm | 8 lỗ hổng ở gói chạy thật, 7 mức cao |
| gitleaks | 0 bí mật thật |
| Trivy, ảnh frontend | 0 lỗ hổng mức cao |

Trả xong nợ nhóm nào thì bỏ `continue-on-error` của job đó để nó bắt đầu chặn.

## 2c. Dependabot (`.github/dependabot.yml`)

Mỗi thứ Hai, Dependabot mở PR cập nhật gói (pip, npm, ảnh gốc Docker; GitHub Actions thì mỗi tháng). Bản nhỏ gộp một PR cho mỗi hệ sinh thái. CI kiểm các PR này như mọi PR khác. `torch` và `kombu >= 5.7` bị loại có chủ ý; lý do ghi ngay trong tệp.

## 2d. Ảnh ổn định giữa các lần dựng

- Cache dựng ảnh nằm trên Docker Hub (`:buildcache`), không ở cache của GitHub (giới hạn 10 GB, mà riêng lớp thư viện backend đã 8 GB).
- Ảnh gốc (python, node, nginx) ghim theo digest; Dependabot đề xuất digest mới.

Nhờ hai điều này, lớp thư viện nặng chỉ đổi khi danh sách gói đổi. Máy chạy web bật chế độ kéo ảnh (`VOYA_REGISTRY_NS` trong `.env`, xem [TRIEN_KHAI_TU_DAU.md](TRIEN_KHAI_TU_DAU.md) bước 7) thì mỗi lần cập nhật chỉ tải lớp mã.

### `hygiene`

Ba thứ mà không bài test nào bắt được:

1. **Script shell phải là LF.** Đọc `git ls-files --eol` (byte đã cam kết),
   không `grep` trên thư mục làm việc — trên Windows cùng một blob LF checkout
   ra CRLF, nên đọc thư mục làm việc là hỏi máy của người chạy chứ không hỏi
   kho. Sự cố 27/08: entrypoint CRLF → `exec: no such file or directory`,
   frontend crash-loop; mã đúng, tệp đúng, hai byte vô hình sai.
2. **Không có `.env` nào bị cam kết.** `.gitignore` chỉ ngăn `git add` vô ý — nó
   không ngăn `git add -f`, và không nói gì về tệp đã lỡ vào kho từ trước.
3. **`docker-compose.registry.yml` phủ hết service tự dựng ảnh**
   (`scripts/check_registry_overlay.py`).

## 3. Vì sao bước cấp vai KHÔNG còn là `GRANT` viết tay

Bản trước dùng `GRANT ... ON ALL TABLES IN SCHEMA public TO voya_app`. Nó làm bộ
test chạy được, và nó cũng lặng lẽ phá một thứ mà bộ test có nhiệm vụ canh:
`tenant_purges` thuộc mặt phẳng **điều khiển**, và
`test_vai_ung_dung_khong_cham_duoc_bang_dieu_khien` đòi vai ứng dụng **không** có
quyền trực tiếp trên nó. Một câu GRANT quét sạch mọi bảng thì cấp luôn cả bảng đó.

Đo 11/09 trên máy: đúng test ấy đỏ với thông báo *"vai ung dung VAN co quyen truc
tiep tren bang dieu khien: {'voya_app.tenant_purges': [...]}"*, và xanh trở lại
ngay sau khi chạy đường cấp vai thật. Nếu để nguyên khối GRANT, CI sẽ đỏ ở đúng
chỗ ấy — và cách "sửa" hiển nhiên nhất (cấp thêm quyền) chính là cách xoá mất
ranh giới.

> **Nguyên tắc:** môi trường CI phải dựng bằng **cùng đường mà sản xuất dựng**.
> Một lối tắt trong CI không chỉ kiểm thiếu — nó kiểm một hệ thống **khác**.

Hệ quả về thứ tự: cấp vai chạy **sau** migration, vì lệnh này cấp quyền trên các
bảng đang có và đặt `ALTER DEFAULT PRIVILEGES` cho bảng sinh thêm về sau. Đã kiểm
rằng migration không phụ thuộc vào sự tồn tại của `voya_app` (không câu nào trong
`metadata_db.py` hay `migrate.py` nhắc tới vai ấy), nên đảo thứ tự là an toàn.

## 4. Ảnh: `build_docker.yml`

Dựng **ba** ảnh (`voya_backend`, `voya_frontend`, `voya_realtime_service`) theo
ma trận, đẩy lên Docker Hub.

| Nhánh | Tag nhận được |
|---|---|
| `main` | `sha-<short>`, `branch-main`, **`latest`** |
| `deploy_ctu_*` | `sha-<short>`, `branch-<tên>` — **không** đụng `latest` |

`latest` chỉ di chuyển từ `main`. Một commit trên nhánh phát hành vẫn triển khai
được (ghim theo sha) mà không bao giờ tự động đổi thứ máy sản xuất kéo về.

**Secret cần có trên GitHub:** `DOCKER_USERNAME`, `DOCKER_PASSWORD`.

## 5. Triển khai một ảnh đã ghim

```bash
# Trên máy deploy, một lần: đặt namespace Docker Hub
echo 'VOYA_REGISTRY_NS=<ten-tai-khoan-docker-hub>' >> .env

# Mỗi lần triển khai
bash scripts/deploy.sh --image-tag=sha-6be6843
```

Đây là **một chế độ của `deploy.sh`**, không phải script riêng — có chủ ý. Mọi
thứ đắt giá trong `deploy.sh` nằm ngoài lệnh `up`: pre-flight bắt lỗi cấu hình
trước khi tốn 15 phút dựng ảnh, dò GPU thật, ghi `COMPOSE_FILE` vào `.env`,
**dừng ứng dụng trước migration**, và cổng kiểm lược đồ **hai lần** (trước và sau
khi ứng dụng lên). Một script thứ hai sẽ phải chép lại tất cả, và bản chép sẽ
trôi khỏi bản gốc ngay lần đầu có ai sửa một guard ở đây mà quên cái kia.

Chế độ này:

- thêm `-f docker-compose.registry.yml`, bỏ `--build`;
- **kéo ảnh trước khi dừng bất cứ thứ gì** — tag gõ sai, hết hạn đăng nhập hay
  mạng chết đều làm lệnh dừng lại *trong khi hệ thống cũ vẫn đang chạy*;
- in ra tag đang chạy trước lần này, kèm đúng lệnh để lùi về;
- ghi `VOYA_IMAGE_TAG` vào `.env` — vừa để lệnh `docker compose` trần còn dùng
  được (lớp phủ dùng cú pháp biến **bắt buộc**, thiếu biến là mọi lệnh compose
  trần trong thư mục này chết, kể cả `ps` và `logs`), vừa để `.env` ghi lại máy
  này đang chạy tag nào, đọc được bằng một lệnh `grep`.

Không cắt đường lùi `.tar` ở chế độ này: đường lùi chính là tag trước đó, nằm
trên registry, bất biến, và `docker_gc.sh` không chạm tới được — đúng lý do khối
`save_rollback` phải ghi ra ngoài kho ảnh (một tag **cục bộ** thì GC xoá được, và
đã xoá thật hôm 15/08).

`scripts/deploy.sh` không kèm cờ này thì vẫn dựng tại chỗ như cũ. Đường đang chạy
tốt không đổi; đường mới phải tự chứng minh trước.

## 6. Bộ test sẽ đỏ ở đâu trong lượt CI đầu tiên

Đo 11/09/2026 trên `signdb_test` dựng mới: **2763 đạt, 7 hỏng, 1 lỗi, 1 bỏ qua**
(19 phút 57 giây). Frontend: **469/469 đạt**, i18n phủ 100%, dựng thành công.

Lượt đo lại cùng ngày, **sau khi chạy `scripts/provision_test_db_roles.sh`**:
**2764 đạt, 6 hỏng, 1 lỗi** (18 phút 24). Tổng số test không đổi (2770) và đúng
MỘT test lật từ đỏ sang xanh — `test_vai_ung_dung_khong_cham_duoc_bang_dieu_khien`.
Đó là bằng chứng trực tiếp cho mục 3 bên trên: cái đỏ ấy là chuyện cấp vai, không
phải chuyện mã. CI dùng `provision_db_roles` nên không dính nó.

Bảy cái đỏ không cùng một loại — đừng gộp chúng thành một con số:

| Test | Loại | Ghi chú |
|---|---|---|
| `test_vai_ung_dung_khong_cham_duoc_bang_dieu_khien` | **đỏ giả** | thiếu `provision_test_db_roles.sh`; đã xác nhận xanh sau khi cấp vai. CI mới không dính vì dùng `provision_db_roles` |
| `test_every_live_tenant_has_exactly_one_open_subscription` | **đỏ giả (dây chuyền)** | hàng `clone-target-*` rò ra từ lỗi ngay dưới |
| `test_clone_endpoint_control_scope` (ERROR ở teardown) | **hạ tầng test, thật** | `DELETE FROM tenants` vi phạm `fk_registry_versions_tenant`; teardown không dọn `registry_versions` trước |
| `test_exactly_these_tasks_are_platform_wide` | **thật** | `app.saas_tasks.reconcile_storage_quota` là task platform-wide **mới**, chưa ghi vào danh sách canh — một lối thoát khỏi phạm vi tenant chưa ai duyệt |
| `test_seed_covers_every_dialect_used_by_the_catalog` | **thật (dữ liệu)** | `dataset/labels.csv` có **2 dòng phương ngữ `test`** |
| `test_t1_every_dialect_in_the_data_is_registered` | **thật (dữ liệu)** | cùng gốc với dòng trên |
| `test_reader_SOT_nhan_ra_dung_nhung_cau_da_dang_ky` | **thật** | log nói thẳng: *"câu gieo dữ liệu đời cũ thất bại VÀ hậu điều kiện CHƯA đúng — đây là lỗi thật, không phải tương thích ngược"* |
| `test_required_columns_cover_every_written_column[samples]` | **thật** | `capture_session_id` được ghi nhưng không có trong `REQUIRED_COLUMNS`: một reader thiếu cột này **qua được bước xác minh rồi hỏng lúc import** |

Không cái nào làm ứng dụng không chạy được. Bốn cái "thật" đều là **test canh bắt
được trôi lệch** — đúng việc của chúng. Chúng là tồn đọng, không phải chặn triển
khai.

**Không sửa hoặc xoá test để làm xanh cổng.** Cách duy nhất được chấp nhận là sửa
nguyên nhân, hoặc ghi vào `docs/10-issues/KNOWN_ISSUES.md` kèm lý do vì sao nằm
ngoài phạm vi.

## 7. Còn thiếu gì

- **Không có CD tự động.** Có chủ ý (quyết định 11/09): CI dựng và gắn tag ảnh,
  còn triển khai vẫn do người chạy `deploy.sh` trên máy đích. Máy CTU nhiều khả
  năng không mở SSH vào từ ngoài, nên đường tự động sẽ cần self-hosted runner —
  chưa làm.
- **Lint chưa phải cổng chặn** (85 lỗi tồn đọng).
- **Quét bảo mật mới ở chế độ cảnh báo** (mục 2b): còn nợ lỗ hổng gói cần trả.
- **Chưa chạy Playwright (E2E)** trong CI: cần dựng cả stack. Vẫn chạy tay bằng
  `VOYA_UI.bat`.
- **`Dockerfile.coderefresh`** không được dựng thử (phải tải ảnh 13 GB mỗi lượt).
  Thay vào đó, `check_compose_contracts.py` kiểm mọi đường `COPY` của nó.
