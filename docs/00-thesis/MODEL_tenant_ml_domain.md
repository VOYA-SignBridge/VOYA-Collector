# Tenant như một miền dữ liệu–ML khép kín, Community như miền dùng chung ngoại lệ

*Mô hình thống nhất cho Chương 3 và Chương 4. Lập 16/08/2026.*

**Mỗi mục đều gắn nhãn trạng thái.** Đây là bài học xuyên suốt đợt đo: mô tả kiến
trúc mà không tách *thiết kế* khỏi *đã hiện thực* là cách nhanh nhất để một câu
trong Chương 3 bị bác bằng chính mã nguồn.

```
✓   có, và ĐƯỢC CƯỠNG CHẾ theo phạm vi tenant
△   ĐÃ HIỆN THỰC và đang chạy, nhưng phạm vi sở hữu khác đích (theo máy)
◌   có THIẾT KẾ + DDL trong kho mã, KHÔNG tồn tại trong CSDL đang chạy
○   mới là KIẾN TRÚC ĐÍCH, chưa có mã
```

Bốn mức, không phải hai — và ranh giới đắt nhất nằm giữa `△` và `◌`.

`△` nói "chạy thật, chỉ khác ranh giới sở hữu". `◌` nói "có bản vẽ và có DDL,
nhưng bảng không nằm trong cơ sở dữ liệu đang chạy". Hai câu ấy nghe gần nhau và
chịu được hai lượt chất vấn rất khác nhau: câu đầu mời hội đồng hỏi *"cho xem
`tenant_id` của bảng đó"*, câu sau thì không.

Bản trước của tệp này xếp `model_versions` vào `△` kèm lập luận rằng gộp nó với
`○` sẽ "khiến người đọc tưởng model registry chưa được xây". Lo lắng ấy hợp lý,
nhưng bản sửa cho nó không phải là đôn lên một mức: phép đo ngày 16\08\2026 cho
thấy bảng đó không tồn tại trong CSDL chạy thật. `◌` giữ được đúng điều cần giữ —
công việc thiết kế là có thật — mà không khẳng định một thứ mở `psql` ra là thấy
sai.

Chỗ duy nhất còn ở `△` là **thẩm quyền ký SOT**: nó chạy thật, chỉ neo theo MÁY
chứ không theo tenant.

---

## 1. Mô hình đích

```
                         CTU-SignBridge
                              │
              ┌───────────────┴───────────────┐
         TENANT DATA                     COMMUNITY
              │                               │
      ┌───────┴────────┐              đóng góp trực tiếp
  Tenant A          Tenant B                  │
      │                │                      │
 Live Capture      Live Capture               │
 Upload            Upload                     │
      │                │                      │
 private A         private B                  │
      │                │                      │
      └── công bố có chọn lọc ────────────────┤
                                              ↓
                                     Community Dataset
```

Nguyên tắc mặc định — **thu ở tenant nào thì thuộc tenant đó**:

```
CaptureOrUpload(r, T)  ⇒  OwnerScope(r) = T

CommunityVisible(r)    ⇒  DirectCommunityContribution(r)
                        ∨ ExplicitlyPublishedByTenant(r)
```

Community **không** phải đích mặc định của capture/upload. Nó là một đường khác.

## 1b. Community, `default`, và tenant thường — ba thứ khác nhau

**Nghiệp vụ:** Community là *miền dữ liệu dùng chung* của CTU-SignBridge.
**Kỹ thuật:** nó được materialize bằng một **tenant dự trữ**, để tái dùng đúng
RLS/RBAC/tenant scoping thay vì tạo một đường truy cập đặc biệt đi vòng qua cách
ly. Hai câu này không mâu thuẫn.

Đã xác minh trên `signdb_test`:

```
community    tenant_type=COMMUNITY      is_system_reserved=TRUE
default      tenant_type=ORGANIZATION   is_system_reserved=FALSE
```

| | vai trò |
|---|---|
| `community` | **miền dùng chung chính thức**, tenant dự trữ, vẫn chịu RLS/RBAC |
| `default` | **nguồn bootstrap / seed**, corpus khởi tạo — *không* phải Community, *không* phải tenant toàn cục, *không* có quyền xuyên tenant |
| tenant thường | miền vận hành độc lập |

### `PUBLIC_TENANT_ID = "default"` — hệ quả phải nói thẳng

`/classes/community-stats` hiện đọc `Data(default)`, **không** đọc
`Data(community)`. Bản vá đã bịt được rò rỉ thật:

```
trước:  aggregate(mọi tenant)      ← rò quy mô mọi tổ chức
sau:    aggregate(một tenant được chỉ định tường minh)
```

Nhưng về ngữ nghĩa, **tên endpoint không phản ánh đúng nguồn dữ liệu**. Không gọi
`default` là "Community" chỉ để khớp tên. Ba hướng, chọn sau bảo vệ:

```
A.  community-stats  ->  tenant_id=community   (có thể trả 0 nếu Community trống)
B.  đổi tên          ->  public-corpus-stats   (nếu chủ đích là công bố corpus default)
C.  chính sách public corpus riêng, gọi đúng tên và thẩm quyền
```

### Bootstrap ≠ fallback

Đây là ranh giới quan trọng nhất của `default`:

```
Seed(T, S, V)  ⇒  snapshot/pin(S, V)  ∧  OwnerScope(kết quả) = T
RuntimeRead(T) ⇒  chỉ DataVisibleTo(T)         KHÔNG fallback(seed_source)
```

Kế thừa xảy ra **một lần, lúc khởi tạo**, có provenance. Sau đó tenant không còn
phụ thuộc động vào nguồn seed. Ba hành vi **sai**:

```
Tenant A không thấy class  ->  rơi về default
Tenant A truy vấn          ->  UNION(private A, default, community) ngầm
default/community đổi      ->  dữ liệu Tenant A tự đổi theo
```

Tenant được bootstrap nên ghi: `seed_source`, `seed_version`, `seeded_at`,
`license_reference`, `terms_reference` — và nếu chặt hơn thì thêm
`seed_manifest_hash`, `seed_snapshot_id`, `attribution_reference`,
`consent_basis`. **Trạng thái: THIẾT KẾ.**

### Community cũng phải hỏi quyền

`community_member` **không** tự nó cho phép mọi hành động. Community là tenant nên
vẫn đi qua `chủ thể + phạm vi + quyền cụ thể → cho/từ chối`. Một endpoint đọc công
khai phải là **một chính sách công khai cụ thể**, không phải hệ quả của việc tên
tenant là COMMUNITY.

## 2. Vòng đời trong một tenant

```
Live Capture ──┐
               ├─→ Working Dataset ─→ Dataset Version ─→ Training Job
Upload ────────┘                                              ↓
                                                        Model Version
                                                              ↓
                                                       Model Registry
                                                              ↓
                                              active_version / rollback
                                                              ↓
                                                          Inference
```

## 3. Trạng thái hiện thực — hai mặt phẳng, và chúng KHÔNG cùng phạm vi

Đây là phát hiện quan trọng nhất của mục này.

| Lớp | Bảng | Phạm vi | Trạng thái |
|---|---|---|---|
| Thu nhận | `classes`, `samples` | **`tenant_id`** | **ĐÃ CƯỠNG CHẾ** (RLS + cổng CSV) |
| Việc huấn luyện (ứng dụng) | `training_jobs` | **`tenant_id`** | **ĐÃ CƯỠNG CHẾ** |
| Bộ dữ liệu | `datasets` | `created_by`, `owner_user_id` → `users` | **KHÔNG có `tenant_id`** — và **không có bảng** trong CSDL đang chạy |
| Phiên bản bộ dữ liệu | `dataset_versions` | qua `dataset_id` | nt. |
| Thí nghiệm | `experiments` | `created_by` → `users` | nt. |
| Model | `model_versions` | qua `experiment_id` | nt. |

Cột "Phạm vi" của bốn hàng cuối mô tả **DDL trong kho mã**, không mô tả một bảng
đang tồn tại. Giữ lại vì nó cho thấy mô hình sở hữu mà thiết kế cũ đã chọn — và
mô hình ấy đúng là theo người dùng, không theo tenant. Nhưng đọc bảng này mà kết
luận "hệ thống có một model registry sở hữu theo người dùng" là sai: chưa có
hàng nào, chưa có bảng nào.

```
grep -c tenant_id backend/app/storage/experiment_tracking_db.py
0
```

Nửa **thu nhận** dữ liệu đã là miền của tenant. Nửa **ML lifecycle** — bộ dữ liệu,
phiên bản, thí nghiệm, model registry — hiện thuộc **người dùng**, không thuộc
tenant. Hai đường huấn luyện tồn tại song song và không cùng mô hình phạm vi:

```
routers/training.py    -> training_tasks.run_training_job(job_id)      tenant_id ✓
routers/experiments.py -> train_task.run_training_job(experiment_id)   tenant_id ✗
```

**Hệ quả cho luận văn:** câu *"mỗi tenant là một miền ML khép kín"* hiện **chỉ
đúng cho nửa thu nhận**. Không được phát biểu nó cho toàn vòng đời.

## 4. Ba bất biến và mức cưỡng chế thật

| | Bất biến | Trạng thái |
|---|---|---|
| I1 | Dữ liệu thu nhận trong tenant thuộc đúng tenant đó | **✓ Enforced** — `tenant_id` + RLS + cổng CSV fail-closed |
| I2 | Huấn luyện chỉ dùng dữ liệu nhìn thấy trong tenant | **△ Partially enforced** — `training_jobs` có tenant; nhánh `experiments` không |
| I3 | Artifact/model theo cùng tenant với training job | **△ Partially enforced** — sở hữu ghi theo *người dùng* |
| I4 | Rollback đổi active version, không phá lịch sử | **○ Architectural design / not enforced** — xem §5 |
| I5 | Community không đọc ngược private tenant | **✓ Enforced on evaluated paths** |
| I6 | Thẩm quyền SOT cô lập theo tenant | **○ Not enforced** — thẩm quyền ký hiện **theo máy** |

I2 và I3 là chỗ phải nói thật: lược đồ hiện **không ngăn** một job trên đường
`experiments` đọc dữ liệu ngoài phạm vi tenant, vì mặt phẳng ấy không có khái niệm
tenant. Không có bằng chứng nó **đã** xảy ra — nhưng cũng không có ràng buộc nào
chặn.

## 5. `latest` và `active` là hai khái niệm khác nhau

Đây là chỗ phải phân biệt rõ với lỗi hồi quy SOT (S7):

```
Model versions:  v1  v2  v3        latest_version = v3
Admin rollback:  active_version = v2

v3 KHÔNG bị xoá.  v2 KHÔNG ghi đè v3.
Chỉ con trỏ triển khai đổi.
```

`latest = phiên bản mới nhất đã tạo` · `active = phiên bản đang phục vụ`.
`latest_version = v3` cùng lúc với `active_version = v2` là **hợp lệ**.

Rollback là **lựa chọn**, không phải **đột biến phá huỷ**. Không dùng `DELETE v5`
để rollback.

**Trạng thái:** DDL của `model_versions` có `is_published` / `published_at`, và
`routers/experiments.py` có `POST /models/{version_id}/promote` — nên khái niệm
giai đoạn đã được **thiết kế** đến mức endpoint. Nhưng router đó không được nối
vào ứng dụng và bảng không được tạo, nên hiện chưa có đường chạy nào. Con trỏ
`active_version` tách khỏi `latest`, cùng nhật ký kiểm toán
(`who/when/tenant/model/from→to/reason`), cũng là **THIẾT KẾ**, chưa hiện thực.

Cả mục 5 này vì vậy nên đọc là **đặc tả hành vi rollback mong muốn**, không phải
mô tả một cơ chế đang vận hành.

Đối chiếu với S7 của SOT: ở SOT, một bản cũ hợp lệ **ghi đè giá trị chung** — đó
chính là kiểu rollback phá huỷ mà mô hình model registry phải tránh.

## 6. SOT theo phạm vi

Mô hình đích:

```
Tenant A SOT   → dataset versions A, model artifacts A, manifests A
Tenant B SOT   → ... của B
Community SOT  → dataset/model versions của Community
```

`SOTAuthority = TenantScope`; một tenant không được dùng SOT của mình để tạo
phiên bản có thẩm quyền cho tenant khác.

**Trạng thái: CHƯA CƯỠNG CHẾ.** Mô hình thật hiện là

```
artifact ─ký bởi─→ khoá của MÁY ─→ verify_with_authorized() ─→ máy được uỷ quyền
```

chứ chưa phải `artifact của Tenant A ─→ thẩm quyền ký của Tenant A`.

Nên câu *"mỗi tenant có SOT riêng"*, hiểu theo nghĩa **thẩm quyền mật mã riêng**,
hiện **không đúng**. Câu dùng được:

> Các artifact có thể được tổ chức và truy xuất theo phạm vi nghiệp vụ, nhưng cơ
> chế xác thực SOT hiện sử dụng khoá Ed25519 theo **máy/authority triển khai**;
> cryptographic signing authority chưa được phân tách thành trust domain riêng cho
> từng tenant.

Đây là **giới hạn phạm vi**, không phải thất bại của SOT integrity. SOT vẫn chứng
minh được toàn vẹn manifest/phiên bản, xác minh người ký được uỷ quyền, bằng chứng
giả mạo, và fail-closed — xem `MEASUREMENT_sot_integrity.md`. Nó chỉ **không**
chứng minh thẩm quyền ký theo tenant.

Ghi chú: `test_sot_tenant_scope.py` và cột SOT theo tenant tồn tại, nhưng đừng để
chúng khiến người đọc suy ra quá mức — chúng nói về *tổ chức dữ liệu*, không nói
về *thẩm quyền mật mã*.

## 7. Công bố sang Community — projection, không phải mount

```
Tenant A SOT / Dataset A3
        ↓  publication record
Community Dataset Version C7   ← Community SOT ký C7
```

Community **không** mount trực tiếp Dataset A3 rồi coi đó là SOT của mình. Phải có
bản ghi công bố giữ provenance nội bộ (`C7 ← A3 / các tài nguyên được chọn`), còn
Community SOT ký **C7**, không ký hộ Tenant A.

Ví dụ phạm vi huấn luyện Community:

```
Tenant A  1000 mẫu   (900 riêng + 100 công bố)
Tenant B   500 mẫu   (450 riêng +  50 công bố)
đóng góp trực tiếp   300

Community training dataset ≤ 100 + 50 + 300 = 450        KHÔNG PHẢI 1800
```

**Trạng thái: THIẾT KẾ.** Chưa có đường huấn luyện Community, chưa có bản ghi
công bố ở mức tài nguyên (xem `PROPOSAL_COMMITMENT_TRACEABILITY.md` §7).

## 8. Thu hồi không viết lại quá khứ

Tenant A công bố mẫu X → Community Dataset v5 dùng X → Model M5 học từ X. Sau đó
A thu hồi X.

```
thu hồi X  ⇒  X không vào Community Dataset v6+
              X không còn tải/công khai được

NHƯNG        Dataset v5 và Model M5 giữ provenance rằng chúng
             hình thành khi X còn hợp lệ
```

Không thể giả vờ M5 chưa từng học X. Việc có xoá model dẫn xuất hay không là quyết
định **quản trị/pháp lý**, không giải quyết được bằng một câu `DELETE`.

**Trạng thái: THIẾT KẾ.** Chưa có thu hồi ở mức tài nguyên.

## 9. Câu dùng cho Chương 3

**KHÔNG** viết:

> ~~Mỗi tenant tạo thành một miền độc lập bao phủ toàn bộ vòng đời từ thu nhận dữ
> liệu đến huấn luyện, model artifact và SOT.~~

**Viết:**

> Trong implementation hiện tại, phạm vi tenant được cưỡng chế trực tiếp đối với
> lớp thu nhận và quản lý dữ liệu cốt lõi, bao gồm lớp, mẫu, các đường Live
> Capture/Upload và luồng `training_jobs`. Lớp theo dõi thực nghiệm và đăng ký
> phiên bản mô hình — `datasets`, `dataset_versions`, `experiments`,
> `model_versions` — tồn tại ở dạng **thiết kế và DDL trong kho mã, không được
> tạo trong cơ sở dữ liệu đang chạy**; router tương ứng không được nối vào ứng
> dụng. Vì vậy, mô hình mô tả một vòng đời ML theo tenant, còn phần đã hiện thực
> và đo được dừng ở lớp dữ liệu và `training_jobs`; lớp thực nghiệm/model
> registry chưa phải một năng lực đang vận hành, nên cũng không nằm trong phép
> đo cách ly.

> **Ghi chú kiểm chứng.** Khẳng định "không tồn tại trong CSDL đang chạy" là kết
> quả đo ngày 16\08\2026 trên CSDL kiểm thử, vốn được dựng bằng chính
> `ensure_tables()` của môi trường chạy thật. `backend/tests/test_c3_output_ledger.py`
> giữ một chốt hồi quy: nếu bốn bảng đó xuất hiện, bài kiểm đỏ và đoạn văn này
> phải được viết lại — chứ không âm thầm trở thành đúng.

Và Community:

> Community là một miền dùng chung được hiện thực bằng reserved tenant
> `community`, nên nó vẫn chịu cùng RLS/RBAC/tenant isolation như mọi tenant khác.
> Community nhận dữ liệu được đóng góp trực tiếp hoặc được tenant chủ động công
> bố. Dữ liệu tenant thông thường vẫn private mặc định; Community không quét xuyên
> tenant. Việc publish/withdraw từng tài nguyên mới được triển khai một phần, và
> `default` là một tenant tổ chức/nguồn bootstrap — **không** đồng nhất với
> Community.

### Sơ đồ đưa vào quyển — kiến trúc đích, rồi ánh xạ hiện thực

```
Kiến trúc đích              Hiện thực
──────────────              ────────────────────────────────────────────────
Tenant                      ✓ classes                  tenant-scoped, RLS
 ├─ Data collection         ✓ samples                  tenant-scoped, RLS
 ├─ Dataset / version       ✓ capture / upload         tenant-scoped
 ├─ Training                ✓ training_jobs            tenant-scoped
 ├─ Experiment              △ thẩm quyền ký SOT        theo MÁY, không theo tenant
 ├─ Model registry          ────────────────────────────────────────────────
 └─ SOT                     ◌ datasets                 DDL trong kho, KHÔNG có
                            ◌ dataset_versions         trong CSDL đang chạy
                            ◌ experiments
                            ◌ model_versions
                            ────────────────────────────────────────────────
                            ○ active_version / rollback pointer
                            ○ thẩm quyền ký theo tenant
                            ○ publish/withdraw mức tài nguyên
                            ○ đường huấn luyện Community
                            ○ provenance seed khi bootstrap tenant
```

Đọc bảng này — **bốn** mức, không phải ba:

| | nghĩa |
|---|---|
| `✓` | đang chạy, mang `tenant_id`, có RLS |
| `△` | đang chạy thật, nhưng ranh giới sở hữu khác đích |
| `◌` | có thiết kế và DDL trong kho mã, **không tồn tại trong CSDL đang chạy** |
| `○` | chưa có mã |

Mức `◌` được tách ra ngày 16\08\2026, sau khi phép đo cho thấy bốn bảng ấy không
được `ensure_tables()` tạo và `routers/experiments.py` không được nối vào ứng
dụng. Trước đó chúng nằm ở `△` kèm một câu dặn: *"`model_versions` tồn tại thật
với `checkpoint_hash` và lineage qua `experiment_id`; nói nó 'chưa có' là tự hạ
thấp phần đã làm được."*

Câu ấy đã bị gỡ, và lý do đáng ghi lại. Nó không chỉ dán nhãn sai — nó **dặn
người viết Chương 3 đi bảo vệ một năng lực không tồn tại**, trước một hội đồng có
quyền mở CSDL ra xem. Nhầm `◌` thành `○` chỉ làm quyển sách khiêm tốn quá mức;
nhầm `◌` thành `△` là một khẳng định sai sự thật ở chỗ dễ kiểm chứng nhất.

Chỗ đúng để không tự hạ thấp là mô tả cho đúng cái đang có: một thiết kế lược đồ
đầy đủ cho model registry, đã viết thành DDL và một router, **chưa nối vào vòng
đời chạy**. Đó là công việc thật, và mô tả như vậy không ai bắt bẻ được.

Tự chỉ ra trước thì hội đồng không bắt được lỗi *"sơ đồ vẽ tenant bao
ModelVersion nhưng bảng không có `tenant_id`"* — và, sau lần sửa này, cũng không
bắt được lỗi nặng hơn: *"bảng ấy đâu?"*

### Hai đường huấn luyện — nói đúng mức

```
Tenant-scoped   routers/training.py    -> training_tasks.run_training_job(job_id)
                                          tenant-aware

Song song       routers/experiments.py -> train_task.run_training_job(experiment_id)
                                          user-owned, không tenant-scoped
```

**Không** gọi nhánh thứ hai là "vi phạm cách ly tenant". Câu đúng:

> Không tìm thấy bằng chứng về một lần truy cập chéo tenant đã xảy ra; tuy nhiên,
> nhánh experiment tracking hiện thiếu một ràng buộc tenant-level tương đương, nên
> **thuộc tính cách ly tenant không được chứng minh cho nhánh này**.

Phân biệt *không quan sát thấy vi phạm* với *có cưỡng chế* — hai điều khác hẳn.

### Vì sao KHÔNG sửa lược đồ lúc này

Mở `tenant_id` cho bốn bảng ấy kéo theo ràng buộc sở hữu tổ hợp, RLS, migration +
backfill, lan truyền qua router và worker, rồi hợp nhất hai đường huấn luyện. Đó
là thay đổi xuyên lược đồ–router–worker–artifact, và nó có thể làm hỏng chính P0-B
và full-suite đang cần đóng. Ghi vào **giới hạn kiến trúc / hợp nhất tương lai**
là đúng hơn sửa vội.

## 10. Tóm tắt trạng thái

```
✓  I1  thu nhận thuộc tenant                 enforced
△  I2  huấn luyện trong phạm vi tenant       nhánh experiments không có tenant
△  I3  artifact thuộc chủ của job            sở hữu theo người dùng
○  I4  rollback = đổi con trỏ active         chưa có mã
✓  I5  Community không đọc ngược tenant      trên các đường đã khảo sát
○  I6  thẩm quyền ký SOT theo tenant         hiện theo MÁY

△  công bố tenant → Community                CLI, không workflow, không thu hồi
○  đường huấn luyện Community                chưa có mã
○  provenance seed khi bootstrap tenant      chưa có mã
```

### Ba phát biểu về `community-stats` — cùng đúng một lúc

```
1.  Community tồn tại thật              → reserved tenant `community`
2.  endpoint đã hết đọc xuyên tenant    → từ unscoped xuống Data(default)
3.  endpoint CHƯA phải Community stats  → vì default ≠ community
```

Nên xem nó là **sửa lỗi bảo mật thành công, nhưng tên gọi và chính sách còn
lệch**. Không dùng nó làm bằng chứng Community; cũng không mở lại mã chỉ để đổi
tên trước khi đo P0-B.
