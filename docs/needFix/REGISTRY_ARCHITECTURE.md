# Danh mục từ vựng — ba mặt phẳng Community / Tenant / Artifact

Ngày 2026-08-01. Kiến trúc do chủ dự án chốt, và phần **lát A** đã cài đặt xong.
Tài liệu này ghi *đã làm gì*, *vì sao thiết kế như vậy*, và *còn nợ gì*.

```
Community Registry  --clone MỘT LẦN-->  Tenant Registry  --pin-->  Dataset/Campaign
   (mẫu, admin HT)                       (tenant tự sửa)             (bất biến)
                                                                        |
                                                                    Split / Model
                                                                 (kiểm version+hash)
```

Luật xuyên suốt: **runtime KHÔNG bao giờ fallback ngược về Community**, và thiếu
dữ liệu thì **DỪNG**, không suy đoán.

---

## 1. Vì sao phải làm ngay, không đợi sau merge

Ba lỗi thật, không phải giả định:

| # | lỗi | hậu quả đã đo được |
|---|---|---|
| 1 | Danh sách profile **gắn cứng ở hai nơi** và đã lệch nhau | `seed_from_csv` có 6 (kèm `legacy_unassigned`), `processed/shared/vocabulary.py` có 5. Script chạy trước khi dựng stack lấy bản 5 → **7 lớp `spa` bị lọc khỏi split trong im lặng** |
| 2 | `registry_version` là **bộ đếm bị ghi đè**, snapshot là **một file bị ghi đè** | "dataset pin v2" **không thực hiện được**: nội dung v2 biến mất ngay khi v3 ghi. Cả tầng pin/hash trong sơ đồ không dựng được trên nền này |
| 3 | Không có khái niệm thành viên tenant | sửa danh mục chỉ kiểm `is_admin` toàn hệ thống — hoặc không tenant nào tự quản được, hoặc mọi admin hệ thống thành editor của mọi tenant |

Lỗi 2 rẻ khi sửa bây giờ (`version = 2`, **chưa dataset nào pin gì**) và rất đắt
nếu để muộn: khi đã có dataset khai "tôi pin v2" mà v2 không còn, dữ liệu nói dối
và không phát hiện được. Cùng loại "rẻ bây giờ, đắt sau" với `class_idx` ở đợt
chuẩn bị multitenant.

---

## 2. System Catalog — mẫu cấu hình, admin hệ thống sở hữu

> **ĐỔI TÊN 2026-08-06.** Mặt phẳng này trước đây gọi là "Community". Sai: nó
> chứa **cấu hình** (phương ngữ nào, profile nào tồn tại), không chứa dữ liệu ai
> đóng góp — không video, không landmark, không consent, không attribution.
> "Community" trong CTU-SignBridge là **Community Data Commons**, một thứ khác
> hẳn và **chưa tồn tại**: xem `COMMUNITY_DATA_COMMONS.md`.
>
> Hàm và endpoint đã đổi sang `*_catalog_*` / `/vocabulary/catalog`. **Tên bảng
> vật lý giữ nguyên `community_*`** vì đổi tên bảng là migration cần cửa sổ
> deploy. Đừng sửa tên hàm ngược lại cho khớp tên bảng.

Ba bảng **riêng**, không phải một `tenant_id` đặc biệt:

```
community_dialects (dialect_id PK, display_name, language, is_alphabet,
                    display_order, is_active, note, updated_by, updated_at)
community_profiles (profile_id PK, display_name, is_trainable,
                    display_order, is_active, note, updated_by, updated_at)
community_versions (version PK, content_hash, snapshot JSONB, note, created_by)
```

**Vì sao bảng riêng chứ không phải `tenant_id = '__community__'`:** luật "tenant
không bao giờ đọc được mẫu chung" khi đó cưỡng chế được bằng **tên bảng trong
câu truy vấn**, thay vì bằng việc nhớ thêm một mệnh đề `WHERE`. Quên một `WHERE`
là chuyện thường; gõ nhầm tên bảng thì không.

**"Admin tùy chỉnh ban đầu, tránh bị lộ"** được thoả bằng:

- `seed_community()` đọc `config/dialects.seed.csv` + `config/profiles.seed.csv`
  **chỉ ở lần cài đầu** (`ON CONFLICT DO NOTHING`). Sau đó admin sửa trong app,
  và **redeploy không ghi đè** thay đổi đó → không cần sửa code để đổi mẫu.
- `assert_system_admin()` là guard **riêng**, cố ý không dùng chung với guard
  của tenant, để không kiểm tra phạm-vi-tenant nào có thể bị nhầm thành quyền
  trên mẫu chung.
- Không endpoint nào trả bảng community về cho người dùng tenant.

`config/profiles.seed.csv` là file **mới**: trước đó danh sách profile nằm gắn
cứng trong `seed_from_csv()`. Đó chính là bản sao thứ hai gây lỗi #1.

---

## 3. Mặt phẳng Tenant — clone một lần, rồi độc lập

`clone_community_to_tenant(tenant_id)` là **nơi duy nhất** đọc mặt phẳng
community thay mặt một tenant. Nó:

1. `publish_community_version()` → chốt mẫu thành version bất biến;
2. copy dialects + profiles sang `dialects` / `recognition_profiles` của tenant
   (`ON CONFLICT DO NOTHING` → chạy lại không đè sửa đổi của tenant);
3. ghi `tenants.cloned_from_community_version` — để sau này còn trả lời được
   "lúc tenant này bắt đầu thì mẫu chung trông như thế nào";
4. `_bump()` → sinh registry version đầu tiên của tenant.

Sau bước này **không có đường quay lại**. Một tenant mất registry phải **báo lỗi
to**, không được lặng lẽ mượn từ vựng của mẫu chung.

### Phân quyền trong tenant

```
tenant_members (tenant_id, user_id, role CHECK IN ('admin','editor','viewer'))
```

`can_edit_registry(tenant_id, user_id, is_system_admin)`:

- **admin/editor CỦA CHÍNH tenant đó** → sửa được;
- viewer, người ngoài → không;
- admin hệ thống → được, nhưng đó là **thẩm quyền khác**, kiểm riêng.

Hai thẩm quyền tách nhau có chủ đích: editor của tenant A **không bao giờ** có
quyền ở tenant B — đó là toàn bộ lý do tồn tại của mặt phẳng tenant.

---

## 4. Version bất biến + hash

```
registry_versions (tenant_id, version, content_hash, snapshot JSONB,
                   note, created_by, created_at,
                   PRIMARY KEY (tenant_id, version))
```

Hàng **chỉ ghi một lần, không bao giờ UPDATE/DELETE** (có test canh).
`vocabulary_registry_meta.version` giữ vai trò **con trỏ** tới version hiện tại.

Mỗi lần chốt, ghi **hai** file:

- `dataset/vocabulary_registry.json` — con trỏ hiện tại, bị ghi đè mỗi lần;
- `dataset/registry_versions/<tenant>_v<N>.json` — bản đóng băng, **ghi một lần,
  không bao giờ ghi lại** (`if not frozen.exists()`).

Bản đóng băng chính là thứ làm cho "pin v2" sống sót khi v3 xuất hiện.

### Version = trạng thái nội dung, không phải số lần chạy

`init_db()` clone lại mỗi lần backend khởi động. Bản đầu tôi viết làm version
**tăng mỗi lần boot** dù không có gì đổi — pin v2 sẽ trôi xa bản của người đọc
mà chẳng vì lý do gì. Đã sửa: nếu hash trùng version **mới nhất** thì giữ nguyên.

Đã kiểm: chạy `init_db` **4 lần liên tiếp** → vẫn `v4`, community vẫn `v1`.
Đổi `display_name` một phương ngữ → `v5`; đổi về → `v6`.

So sánh chỉ với version **mới nhất**, không phải toàn bộ lịch sử — cố ý. Nếu so
với cả lịch sử thì sửa-rồi-hoàn-tác sẽ làm sống lại `v1` thành "hiện tại", số
version hết đơn điệu theo thời gian, và "pin bản cũ" trở nên không phân biệt
được với "pin bản hiện tại". **Version là một điểm trên dòng thời gian, không
phải một content hash.**

### Kiểm pin

`verify_pinned_snapshot(tenant, version, hash)` raise `RegistryPinError` khi:

- version không tồn tại → artifact trỏ tới một danh mục **không còn**;
- hash lệch → hàng bị sửa, hoặc phục hồi từ database khác.

Cả hai **luôn fatal**. Xuống nước thành "dùng tạm registry hiện tại" chính là
thứ mà cả cơ chế pin sinh ra để ngăn.

---

## 5. Không còn fallback trong `processed/shared/vocabulary.py`

| | trước | sau |
|---|---|---|
| thiếu snapshot | trả `_FALLBACK_PROFILES` (5 mục, đã lệch) | **raise `RegistrySnapshotMissing`** |
| `VOCABULARY_REGISTRY_PATH` trỏ sai | âm thầm rơi về snapshot khác | **raise** — pin là độc quyền |
| registry rỗng | không phân biệt được với thiếu | trả `()`, hợp lệ (tenant chưa cấu hình) |
| `RECOGNITION_PROFILES` | hằng số tính lúc import | **`__getattr__` lười** — import không nổ, *đọc tên* mới đòi registry thật |

`VOCABULARY_REGISTRY_PATH` là **độc quyền** chứ không phải "ưu tiên đầu": nó là
cách một caller pin đúng một snapshot; đọc sang registry khác chỉ vì file đó
thiếu chính là kiểu thay thế âm thầm mà module này sinh ra để chặn. Lỗi này do
chính test bắt được sau khi tôi viết bản đầu.

`__getattr__` lười vì tính lúc import sẽ làm **mọi** caller nổ, kể cả người chỉ
cần `MOTION_TYPES`.

### `trainable_profiles()` vs `recognition_profiles()`

Bỏ fallback làm lộ một chỗ gộp lẫn khái niệm đã tồn tại từ trước:
`legacy_unassigned` **có** trong registry (nó là sentinel đánh dấu hàng chưa
phân loại) nhưng **không train được**. Hai tập này chỉ tình cờ trùng nhau khi
danh sách còn là tuple 5 phần tử bỏ sót sentinel.

- `recognition_profiles()` — mọi profile **đã đăng ký**;
- `trainable_profiles()` — tập mà một nhãn `profile_specific` được phép nêu.

`validate_label_v2`, `label_key_v2` và `select_rows_for_profile` đều hỏi tập
**hẹp hơn**. Nếu không, "lớp này thuộc vùng chưa-phân-loại" sẽ được chấp nhận
như một phép gán thật.

### Clone repo dùng được mà không bịa

```bash
python -m app.cli.export_registry_snapshot --bootstrap   # không cần database
```

Dựng snapshot từ `config/*.seed.csv`, đóng dấu `"source": "community_seed"`,
`registry_version: 0`. Artifact dựng từ nó **ghi lại nguồn gốc đó** — nên đây là
bootstrap tường minh, không phải fallback âm thầm. Muốn có nó thì phải **gõ**
`--bootstrap`; bản âm thầm của đúng việc này là nguyên nhân lỗi #1.

Hai bản hash (stdlib trong CLI, backend trong registry) có test canh phải khớp.

---

## 6. Thứ tự hiển thị

`ORDER BY profile_id` cho ra thứ tự abc (`alphabet, central, hoa_de, …`) trong
khi ý định là thứ tự địa lý (`alphabet, north, central, south, hoa_de`).
`alphabet` đứng đầu **chỉ do may mắn về chính tả** — thêm một profile tên bắt đầu
bằng "aa" là mọi dropdown đảo lộn. Đã thêm cột `display_order` cho cả
`recognition_profiles` và `dialects`, và seed CSV mang giá trị đó.

---

## 7. Đã chạy thật

```
[VOCAB] community version 1 published (4b79adfcb4cc)
[VOCAB] tenant default cloned from community v1: {'dialects': 9, 'profiles': 6}
[DB_INIT] vocabulary FK: {'classes': 'exists', 'samples': 'exists'}
[STARTUP_SYNC] classes/samples/raw_uploads -> khong thieu hang nao
```

- 4 lần chạy liên tiếp → version **không trôi**;
- đổi nội dung → version mới; `get_registry_version('default', 4)` **vẫn đọc được**;
- hash sai → `RegistryPinError`; version không tồn tại → `RegistryPinError`;
- dữ liệu nguyên: 63 lớp, 3860 mẫu, 9 phương ngữ, 6 profile.

Kiểm thử: `backend/tests/test_registry_planes.py` (28 test) +
`test_dialect_registry_migration.py` (11). Tổng các suite liên quan: **229 pass**.

---

## 8. Lát B — còn nợ

| việc | vì sao chưa làm |
|---|---|
| `Workspace` / `Project` / `project_profile_bindings` | chưa có API nào cần; dựng trên nền đã có là việc thẳng |
| `dataset_versions` / `campaign_registries` (pin lúc tạo) | cần thống nhất với luồng Campaign |
| Split/Model ghi + kiểm `registry_version` + `content_hash` | **`processed/splits/make_splits.py` còn 4 dấu xung đột** — làm cùng lúc gỡ nhóm `processed/` |
| ~~Endpoint quản trị System Catalog cho admin hệ thống~~ | **XONG** — xem §9 |
| Gán `tenant_members` cho người dùng hiện có | hôm nay mới có tenant `default`; admin hệ thống vẫn vào được nên chưa chặn ai |

**Lưu ý khi làm lát B:** `registry_versions` hiện chỉ có `v4` trở đi — `v1..v3`
sinh ra trước khi bảng này tồn tại nên không có nội dung. Một artifact khai pin
`v2` sẽ **đúng đắn** bị `RegistryPinError`. Hiện chưa artifact nào khai như vậy.

---

## 9. Endpoint quản trị System Catalog (`catalog_router`)

`backend/app/routers/vocabulary.py` — prefix riêng `/vocabulary/catalog`, guard
riêng, đăng ký ở cả `/` lẫn `/api/v1`.

| method | path | việc |
|---|---|---|
| GET | `/vocabulary/catalog` | danh mục **đang sống** + `content_hash` + version chốt gần nhất |
| GET | `/vocabulary/catalog/versions` | lịch sử, **không kèm snapshot** |
| GET | `/vocabulary/catalog/versions/{version}` | một snapshot đã đóng băng |
| POST | `/vocabulary/catalog/publish` | chốt thành version bất biến |
| POST | `/vocabulary/catalog/seed` | chạy lại seed từ `config/*.seed.csv` |
| PATCH | `/vocabulary/catalog/dialects/{id}` | sửa mẫu |
| PATCH | `/vocabulary/catalog/profiles/{id}` | sửa mẫu |
| POST | `/vocabulary/catalog/clone` | dựng registry cho một tenant |

Bốn quyết định đáng ghi lại:

1. **Sửa KHÔNG publish.** Một version là hành động có chủ ý, có ghi chú kèm. Nếu
   mỗi lần gõ phím lại sinh một version thì lịch sử đầy những version không ai
   chọn tạo, và "pin version v7" mất hết ý nghĩa. `publish` là một cú bấm riêng.
2. **`publish` khử trùng lặp theo nội dung**, trả về `created: true|false` — giao
   diện báo được "đã có v7" thay vì báo thành công dối.
3. **Không sửa được `dialect_id` / `profile_id`.** Tên cột hợp lệ lấy từ danh
   sách trắng trong code, không lấy từ khoá của payload → khoá lạ là 400, không
   phải SQL được nối chuỗi. Id đặt tên thư mục, checkpoint, split manifest.
4. **`clone` kiểm tenant tồn tại trước.** `dialects.tenant_id` **không có** khoá
   ngoại sang `tenants`; gõ nhầm id sẽ thành công một nửa — hàng danh mục ghi
   dưới một tenant không ai với tới, còn `UPDATE tenants SET
   cloned_from_community_version` khớp 0 hàng nên mất luôn dấu vết nguồn gốc.

Guard: `require_admin` (cờ hệ thống) **rồi** `vr.assert_system_admin` — hai lớp
cố ý, vì mỗi lớp một mình cũng đủ để lọt nếu lớp kia bị nới. Test
`test_tenant_user_is_refused_on_every_community_route` giả lập đúng tình huống
đó: cho `require_admin` trả về người dùng thường, và vẫn phải nhận 403.

Kiểm thử: `backend/tests/test_system_catalog_api.py` (22 test, chạy với Postgres
thật, tự dọn cả dialect tạm lẫn mọi `community_versions` do test sinh ra).
`test_registry_planes.py::test_only_declared_functions_touch_the_community_plane`
nay **liệt kê mọi hàm truy vấn bảng `community_*`** thay vì đếm một danh sách
cứng — hàm mới lén đọc mẫu chung từ đường tenant sẽ đỏ ngay tại đây.
