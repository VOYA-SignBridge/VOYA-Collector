# Truy vết cam kết đề cương → hiện thực → bằng chứng

*Lập 16/08/2026. Trả lời trực tiếp câu hỏi "so với đề cương ban đầu, em đã hoàn
thành được bao nhiêu?".*

Mỗi cam kết phải trả lời được năm câu: **Đã làm? Bằng chứng đâu? Chương nào?
Bảng/hình nào? Giới hạn gì?**

Thay đổi so với đề cương **không phải thất bại** — nhưng phải trả lời được: thiết
kế ban đầu là gì, vì sao đổi, thiết kế cuối tốt hơn ở đâu, mục tiêu nghiên cứu
còn được đáp ứng không, bằng chứng nằm ở đâu.

---

## Bảng truy vết

| # | Cam kết | Trạng thái cuối | Bằng chứng chính | Giới hạn |
|---|---|---|---|---|
| O1 | Kiến trúc đa tenant | **Đạt / tinh chỉnh** | `Tenant → Workspace → Project`; 59 bảng, 34 mang `tenant_id` | workspace/project chưa có bề mặt vận hành đầy đủ |
| O2 | Cách ly tenant | **Chờ kiểm chứng cuối** | RLS + vai runtime; `test_file_backed_tenant_isolation.py` 12 pass | P0-B chưa chạy lại |
| O3 | RBAC nhiều phạm vi | **Đạt một phần** | gán vai system + tenant | `ws=0 prj=0`; Casbin shadow |
| O4 | Phân loại VSL | **Đạt** | language/dialect/region + registry có phiên bản | — |
| O5 | Hiệu quả lưu trữ | **Đạt** | 92,2% trên 54 cặp hợp lệ | QIPEDC ≠ luồng webcam |
| O6 | Xử lý bất đồng bộ | **Đạt, hạn chế độ tin cậy** | 4/4 workload operational | retry/idempotency không đồng đều |
| O7 | SOT ký + phiên bản | **Đạt, giới hạn thứ tự phiên bản** | 9 kịch bản: 8 thoả + S7 giới hạn | chưa cưỡng chế đơn điệu |
| O8 | Đánh giá 4 trục | **Phần lớn đạt** | chức năng + lưu trữ + độ trễ + SOT | cách ly còn chờ |

*Nhận dạng thời gian thực là **hạng mục demo hạ nguồn**, không phải một objective
riêng — xem §7. Không nâng thành O9.*

<details><summary>Bảng cũ (giữ để đối chiếu)</summary>

| # | Cam kết | Hiện thực | Bằng chứng | Trạng thái |
|---|---|---|---|---|
| O1 | Kiến trúc SaaS đa tenant | `Tenant → Workspace → Project` | lược đồ 59 bảng, 34 bảng mang `tenant_id` | **Đạt, đã tinh chỉnh** (xem §1) |
| O2 | Cách ly dữ liệu tenant | RLS + ngữ cảnh tenant | bộ test RLS xanh; đo đối kháng **BLOCKED** | **Chưa đóng** |
| O3 | RBAC ba phạm vi | Casbin 4 miền, 13 vai | `sys=4 ten=10 **ws=0 prj=0**`, `mode=shadow` | **Đạt một phần** (§2) |
| O4 | Phân loại VSL + phương ngữ | registry/dialect/region/tenant ext | test chức năng | **Vượt đề cương** |
| O5 | Giảm dung lượng > 90% | biểu diễn điểm mốc `.npz` | ghép cặp QIPEDC → **92,2%** (n=54 khớp thời lượng, đạt ngưỡng phát hiện) | **ĐẠT** (§11) |
| O6 | Xử lý bất đồng bộ Celery/Redis | 4/4 năng lực chạy trên worker | audit 6 trục; hạn chế ở độ tin cậy, không ở năng lực | **Đạt, có hạn chế độ tin cậy** (§10) |
| O7 | SOT ký + phiên bản | hash + chữ ký + version | ma trận 9 ca qua `sync_from_sot`: 8 thoả, **1 giới hạn (S7)** | **Đạt, trừ đơn điệu phiên bản** (§6) |
| O8 | Đánh giá 4 trục | latency đóng; 3 trục còn lại | Chương 4 | **Một phần** |

</details>

---

## §1. `Workspace = Tenant` → `Tenant ⊃ Workspace ⊃ Project`

**Đề cương** xem workspace chính là tenant. **Hiện thực cuối** tách ba tầng.

Đây là *tinh chỉnh thiết kế*, không phải bỏ cam kết. Lý do: hai thứ khác nhau bị
gộp làm một trong bản đầu —

* **Tenant** — ranh giới **quản trị và cách ly** cao nhất. Là thứ RLS bảo vệ, là
  thứ hoá đơn tính theo, là thứ không được rò sang nhau.
* **Workspace** — không gian **tổ chức công việc** bên trong một tenant.
* **Project** — phạm vi hoạt động hẹp hơn nữa.

Gộp hai khái niệm này buộc mọi ranh giới tổ chức công việc phải trở thành một
ranh giới cách ly, tức là mỗi nhóm công việc mới lại là một tenant mới — không
dùng được cho một trường có nhiều lớp cùng thu dữ liệu.

Mục tiêu đa tenant của đề cương **được giữ nguyên**; nó chỉ được đặt vào đúng
tầng.

**Giới hạn phải nêu:** hai bảng `workspaces` và `projects` tồn tại trong lược đồ,
nhưng API **không có một endpoint nào** cho chúng (đối chiếu `/openapi.json`: 0
đường chứa `workspace` hoặc `project`). Vì vậy tầng giữa và tầng dưới hiện là
**cấu trúc dữ liệu, chưa phải bề mặt vận hành**, và không có gì để kiểm chứng
cách ly ở hai tầng đó từ bên ngoài.

## §2. RBAC ba phạm vi — bằng chứng hiện có nói gì

Hai con số lấy từ log khởi động của chính ứng dụng:

```
[CASBIN] nap policy: 329 p, 14 g (sys=4 ten=10 ws=0 prj=0)
[STARTUP][AUTHZ] mode=shadow
```

Đọc thẳng:

* Phạm vi **system** có 4 gán vai, **tenant** có 10. Phạm vi **workspace** và
  **project** có **0** — hai miền được khai báo trong mô hình Casbin nhưng chưa
  có một gán vai nào. Khớp với §1: chưa có endpoint thì cũng chưa có ai được cấp
  quyền ở đó.
* `mode=shadow` nghĩa là Casbin **tính toán quyết định nhưng không cưỡng chế**.
  Quyết định thực tế vẫn do đường phân quyền cũ đưa ra.

### Phát biểu chính thức — Đạt một phần

> **Đạt một phần.** Mô hình dữ liệu và kiến trúc phân quyền hỗ trợ một hệ phân
> cấp mở rộng được, nhưng cưỡng chế ở thời gian chạy hiện chỉ chứng minh được ở
> phạm vi **system** và **tenant**; phạm vi **workspace/project chưa có bề mặt
> API nghiệp vụ và chưa có gán vai thực tế**. Casbin đang chạy chế độ shadow nên
> chưa phải nơi ra quyết định cưỡng chế.

**Không** được phát biểu "hệ thống cưỡng chế RBAC ở ba phạm vi". Điểm này nên
nói ra trước khi hội đồng tự phát hiện.

**Không xây thêm workspace/project chỉ để khớp đề cương.** Ghi deviation trung
thực tốt hơn nhiều so với dựng vội hai tầng phân quyền chưa có bề mặt nghiệp vụ.

Ma trận cần dựng (10–20 ca, có chủ đích) phải chứng minh **phạm vi thực sự làm
đổi quyền hiệu dụng**, không chỉ chứng minh bảng vai tồn tại. Với `ws=0 prj=0`
hiện nay, ma trận đó sẽ chỉ phủ được phạm vi system và tenant — và đó chính là
kết quả cần báo cáo trung thực.

## §3. MediaPipe — Holistic hay Hands

**Đã xác định bằng mã, không phải bằng trí nhớ.**

```
package.json          có CẢ @mediapipe/hands VÀ @mediapipe/holistic
frontend/src, backend  0 dòng import @mediapipe/holistic
đường thu + nhận dạng  chỉ dùng @mediapipe/hands
biểu diễn lưu trữ      126 chiều/khung = 21 điểm × 3 toạ độ × 2 bàn tay
```

`@mediapipe/holistic` là **phụ thuộc thừa** trong `package.json`, không được mã
nào dùng. Nó chính là nguồn gốc mâu thuẫn giữa đề cương và Chương 2.

Đánh dấu: **Đạt, có tinh chỉnh hiện thực** — không phải thất bại. Đề cương ghi
Holistic, hiện thực cuối dùng Hands, và bằng chứng mã nguồn đã khép sự mơ hồ.

*Gỡ `@mediapipe/holistic` khỏi `package.json`: hợp lý nhưng **hoãn**. Sát ngày
bảo vệ, cleanup này chỉ được làm kèm một lượt frontend build/test — nó là dọn dẹp
tính nhất quán, không được phép sinh hồi quy.*

Câu nên dùng trong luận văn:

> Thiết kế được tinh chỉnh sang MediaPipe Hands vì pipeline cuối chỉ sử dụng
> thông tin bàn tay; thu nhận tư thế toàn thân và biểu cảm khuôn mặt vẫn nằm
> ngoài phạm vi triển khai.

Đề cương, Chương 2, Chương 3, mã và slide phải dùng **cùng một thuật ngữ**. Nên
gỡ `@mediapipe/holistic` khỏi `package.json` để mã tự nói đúng.

## §4. Không dùng lập luận "điểm mốc = ẩn danh"

Đề cương lập luận rằng điểm mốc không giữ diện mạo nên người đóng góp trở nên
ẩn danh. Claim này quá mạnh và không đứng được: biểu diễn điểm mốc vẫn liên kết
với danh tính, phiên thu, siêu dữ liệu, và bản thân dáng ký hiệu là một đặc
trưng cá nhân.

Câu thay thế:

> biểu diễn điểm mốc có thể giảm mức phơi bày hình ảnh trực tiếp so với video
> thô, nhưng không được coi là ẩn danh một cách mặc nhiên.

Điều này cũng nhất quán với việc hệ thống có bảng `signer_consents` và cơ chế
rút đồng thuận — nếu dữ liệu đã ẩn danh thì các cơ chế ấy không có đối tượng.

## §5. Giới hạn tuyên bố cho từng trục đánh giá

| trục | được nói | KHÔNG được nói |
|---|---|---|
| cách ly | các đường API đã khảo sát cưỡng chế ranh giới tenant dưới vai runtime của ứng dụng — **ở Mức I** (kẻ tấn công là người dùng API, không có credential CSDL) | toàn hệ thống bảo đảm tuyệt đối; "không phụ thuộc tính đúng đắn của tầng ứng dụng"; an toàn cả khi vai CSDL bị chiếm (**Mức II — KHÔNG đạt**) |
| SOT | cung cấp xác minh phát-hiện-giả-mạo và chấp nhận fail-closed cho phiên bản đã ký | *guarantee* tuyệt đối; "dữ liệu không thể bị sửa"; chống hồi quy phiên bản |

## §6. O7 — SOT: ba thuộc tính, đừng trộn

```
Toàn vẹn (integrity)              ĐẠT
Xác thực nguồn (authenticity)     ĐẠT
Đơn điệu phiên bản (monotonic)    CHƯA CƯỠNG CHẾ
```

| Thuộc tính | Trạng thái |
|---|---|
| Signed integrity / Tamper evidence | **Đạt** |
| Trusted authority (S4) | **Đạt** — `verify_with_authorized()` trả TÊN khoá, không trả boolean |
| Fail-closed verify (S2/S3/S5/S6) | **Đạt** |
| Versioned artifacts | **Đạt** |
| Monotonic versioning (S7) | **Một phần / chưa cưỡng chế** |

**Không báo "SOT 9/9 đạt".** Phép đo hợp lệ ở cả chín ca; thuộc tính bảo mật đạt
ở tám. S7 cho thấy một `LATEST` **ký hợp lệ bằng khoá tin cậy** vẫn trỏ ngược về
bản cũ được: tài nguyên chỉ có ở bản mới **không bị xoá**, nhưng giá trị trên khoá
dùng chung **bị ghi đè lùi** (`hello-v2` → `hello`).

Không sửa SOT sát ngày bảo vệ chỉ để biến S7 thành xanh. Chi tiết, câu Chương 4
và vân tay nguồn: `MEASUREMENT_sot_integrity.md`.

## §7. Community — mặt phẳng ngoại lệ, KHÔNG phải view toàn cục

**Community không phải "một tenant bình thường được công khai".** Nó là mặt phẳng
dữ liệu dùng chung ngoại lệ của hệ thống. Việc hiện thực nó bằng một tenant được
chỉ định qua `PUBLIC_TENANT_ID` chỉ là cách kỹ thuật để **tái dùng chính cơ chế
cách ly tenant** thay vì viết một cơ chế phân quyền thứ hai.

Bất biến:

```
Tenant A private  ─X→  Tenant B private
Tenant B private  ─X→  Tenant A private

PublicView = Data(CommunityScope)
         KHÔNG PHẢI  union(Data(mọi tenant))
```

Hai nguồn dữ liệu của Community:

```
người đóng góp  ──────────────────────────────→  Community
Tenant A private ── tenant chủ động công bố ──→  Community
```

Với nguồn thứ hai, dữ liệu gốc **vẫn thuộc Tenant A**; công bố chỉ cấp quyền đưa
một tài nguyên/phiên bản cụ thể vào Community, và tenant giữ quyền thu hồi theo
chính sách. **Thu hồi không có nghĩa xoá dữ liệu riêng của tenant.**

### Trạng thái `/classes/community-stats`

```
cross-tenant oracle        CLOSED
community/public scoping   ACHIEVED
unscoped access            CLOSED
publication lifecycle      PARTIAL
identifier exposure        CLOSED
```

Lịch sử, ngắn gọn:

> Ban đầu endpoint tổng hợp trực tiếp trên kho dùng chung xuyên tenant.
> Implementation sau đó được chuyển sang một Community/public scope được chỉ định
> tường minh và truy cập bằng tenant-scoped loader.

Ba đường sai đều bị chặn và có test khoá: không `_unscoped`, không phạm vi người
gọi, không đường lùi khi thiếu cấu hình (trả 0).

### Publication lifecycle — theo hiện trạng, không theo thiết kế

`docs/01-architecture/COMMUNITY_DATA_COMMONS.md` tự ghi ở dòng đầu:
**"thiết kế, CHƯA triển khai"**. Cụ thể:

| | trạng thái |
|---|---|
| Community như một scope được chỉ định | **Đạt** — `PUBLIC_TENANT_ID`, vai `community_member`/`community_curator` ghim theo `tenant_type=COMMUNITY` |
| Đóng góp trực tiếp vào Community | **Đạt ở dạng lõi** — nền tảng đã nhận dữ liệu có đích đến là phạm vi dùng chung |
| Tenant chủ động publish/withdraw từng tài nguyên | **Một phần / chưa cưỡng chế end-to-end** |
| Cách ly ngược (không lần về tenant nguồn) | **Đạt** ở các đường đã khảo sát |

Phát biểu chính xác cho dòng thứ ba — **không** gọi là "chưa triển khai", vì
promoter có thật; cũng **không** gọi là "đạt", vì thiếu workflow và thu hồi:

> Tenant-to-Community publication exists as an **administrative/CLI capability**,
> but is not exposed as an operational application workflow; **withdrawal of
> published resources is not implemented.**

Bằng chứng: `global_common_promoter.py` là một kịch bản CLI (`argparse --promote`)
đặt cờ `is_common_global`; **không router nào gọi nó**, và **không có
`withdraw`/`unpublish` tương ứng** ở đâu trong mã — mọi kết quả `withdrawn_at`
tìm được đều thuộc cơ chế **đồng thuận**, một cơ chế khác hẳn.

**Đính chính một điều tôi từng ghi sai:** các bảng `community_*` trong
`vocabulary_registry` **không phải** Community Data Commons. Chính mã nguồn nói
rõ — chúng là mặt phẳng **danh mục hệ thống**, giữ tên `community_*` vì đổi tên là
một migration; *"this holds no contributed data — no video, no landmarks, no
consent record, no attribution"*.

### Nếu hội đồng hỏi "Community có phải là tenant không?"

> Về nghiệp vụ, không. Community là mặt phẳng dữ liệu dùng chung ngoại lệ của
> CTU-SignBridge. Trong implementation, mặt phẳng này được materialize bằng một
> scope/tenant được chỉ định riêng để tái sử dụng cơ chế tenant isolation. Dữ liệu
> có thể được đóng góp trực tiếp cho Community hoặc được một tenant chủ động công
> bố từ phạm vi riêng; việc công bố không chuyển ownership của dữ liệu gốc, và
> tenant vẫn giữ quyền thu hồi theo policy.

### Một bằng chứng O2 mới, đáng giá

Ngoài `Tenant A ↛ Tenant B`, giờ có thêm:

```
public endpoint -> chỉ Community scope
thay đổi dữ liệu riêng của A/B  ->  bốn con số KHÔNG đổi
```

Đây chứng minh **ngoại lệ Community không phá cách ly tenant** — thêm vào P0-B.

### `default` KHÔNG phải Community — đã xác minh

```
community    tenant_type=COMMUNITY      is_system_reserved=TRUE
default      tenant_type=ORGANIZATION   is_system_reserved=FALSE
PUBLIC_TENANT_ID = "default"
```

Tenant dự trữ `community` **tồn tại thật**. Nhưng `/classes/community-stats` đang
đọc `Data(default)`, **không** đọc `Data(community)`.

Nên phát biểu đúng: bản vá đã thu endpoint từ *unscoped* xuống *một tenant được
chỉ định tường minh* — đó là một sửa lỗi bảo mật thật. Nó **chưa** biến endpoint
thành thống kê Community thật.

`default` đóng vai **nguồn bootstrap/seed** để khởi tạo tenant mới, không phải
Community, không phải tenant toàn cục, không có quyền xuyên tenant. Ranh giới then
chốt: **bootstrap inheritance ≠ runtime fallback** — kế thừa xảy ra một lần lúc
khởi tạo và có provenance, không phải một cơ chế rơi-về-nguồn trong lúc chạy.

Chi tiết, cùng ba hướng xử lý tên endpoint: `MODEL_tenant_ml_domain.md` §1b.

**Hệ quả cho P0-B:** đừng dùng `/classes/community-stats` đọc `default` làm bằng
chứng cho "ngoại lệ Community". Nó chứng minh endpoint đã được thu hẹp về một
tenant tường minh — không hơn. Community thật phải đánh giá theo reserved tenant
`community` và hợp đồng quyền của chính nó.

## §8. Ba claim phải hạ, đồng bộ ở Abstract và Kết luận

| | KHÔNG viết | Viết |
|---|---|---|
| RBAC | "triển khai RBAC ở system, tenant, workspace và project" | "kiến trúc và lược đồ hỗ trợ phân quyền theo nhiều phạm vi; implementation hiện có assignment vận hành ở **system và tenant**, còn workspace/project đã được mô hình hoá nhưng chưa có bề mặt vận hành đầy đủ" |
| Async | "pipeline bảo đảm retry an toàn và idempotent" | "pipeline thực hiện bất đồng bộ ingestion, segmentation, augmentation và cloud synchronization; **retry và idempotency hiện chưa đồng đều** giữa các workload" |
| SOT | "signed versioning bảo đảm trạng thái mới nhất luôn thắng" | "signed manifests cung cấp tamper evidence và xác thực nguồn; **phiên bản cũ hợp lệ hiện vẫn có thể ghi đè giá trị chung** do chưa cưỡng chế monotonic version ordering" |

## §9. Trình tự P0-B — không rút gọn

```
admin.py:394, 395  ->  caller count = 0
        ↓
mọi xfail migration được giải quyết và GỠ marker
        ↓
test_file_backed_tenant_isolation.py  toàn PASS
        ↓
ghi source_tree_sha256
        ↓
build image  ->  ghi image digest
        ↓
╔═══════════════════════════════════════════════╗
║  ĐÓNG BĂNG THỰC NGHIỆM — KHÔNG SỬA MÃ NGUỒN   ║
╚═══════════════════════════════════════════════╝
        ↓
KIỂM LẠI source_tree_sha256 NGAY TRƯỚC KHI GIEO FIXTURE
   lệch  -> INVALIDATE lượt chuẩn bị, rebuild, làm lại từ đầu
   khớp  -> đi tiếp
        ↓
gieo fixture xuyên kho MỚI
        ↓
đối chứng dương  ->  checkpoint mục tiêu
        ↓
pha đối kháng
        ↓
hậu điều kiện DB + CSV + tệp
```

**Nguồn đổi sau khi build ảnh ⇒ toàn bộ phép đo thuộc về BUILD CŨ.** Phải build
lại trước khi đi tiếp — **không** dùng kết quả "gần giống" để nối qua hai
revision. Một lượt đo nửa ở revision này nửa ở revision kia không mô tả phiên bản
nào cả.

Vì sao kiểm **hai lần**: vân tay lúc build chứng minh ảnh được dựng từ cây nào,
nhưng không chứng minh cây còn nguyên khi phép đo bắt đầu. Cây này đã đổi **ba
lần giữa lúc đang đo** trong hai ngày (`preview_render` sửa giữa lượt test,
`community_stats` sửa hai lần trong một buổi). Lần kiểm thứ hai mới khoá đúng
revision thực sự bị đo.

**Phát hiện mới trong lúc đo thì GHI, không SỬA.** Nếu P0-B lộ lỗi, nó là finding
của chính revision đó; sửa hay không quyết định **sau khi lượt đo kết thúc**. Sửa
giữa chừng làm artifact mô tả một phiên bản không tồn tại.
Đây là bài học lớn nhất xuyên suốt đợt đo: `HEAD` giống nhau không có nghĩa mã
giống nhau, và một container chạy mã cũ cho ra kết luận về một phiên bản không ai
định phát hành. Cây đã đổi **ba lần giữa lúc tôi đang đo** trong hai ngày.

### Bốn lớp bằng chứng của P0-B

| lớp | phải chứng minh |
|---|---|
| 1. Đối chứng dương | chủ sở hữu **thật sự** đọc/sửa/xoá được tài nguyên của chính mình |
| 2. Đối kháng xuyên tenant | A không đọc/sửa/xoá được của B, và ngược lại |
| 3. Ngoại lệ Community | đối chứng **hai chiều** — xem dưới |
| 4. Hậu điều kiện ba kho | PostgreSQL + CSV + băm tệp **không** bị request bị chặn làm đổi |

Bốn lớp đều xanh thì CTIVR mới có nền để công bố.

#### Lớp 3 — đối chứng HAI CHIỀU, không phải một

```
public_truoc = community_stats()

    đổi tài nguyên riêng của Tenant A
    đổi tài nguyên riêng của Tenant B

public_sau   = community_stats()
assert public_sau == public_truoc          ← ngoại lệ không phá cách ly

    đổi tài nguyên trong phạm vi Community

assert community_stats() ĐÃ ĐỔI đúng như mong đợi   ← đối chứng dương
```

**Vế thứ hai là bắt buộc.** Chỉ có vế đầu thì một endpoint luôn trả hằng `0` cũng
"đạt" — đúng họ lỗi với fixture chỉ ghi PostgreSQL khiến mọi ca đối kháng thành
404 "đã chặn". Phải chứng minh endpoint **thật sự phản ứng** với dữ liệu Community
mà **không phản ứng** với dữ liệu riêng của tenant.

So sánh **trạng thái trước/sau**, không so bốn con số một lần.

Phép kiểm này thuộc P0-B chứ không thuộc `test_file_backed_tenant_isolation.py`:
nó phải GHI vào cả PostgreSQL lẫn `labels.csv`, mà bộ test kia chạy trên kho tệp
thật — đúng cái bẫy "test ghi vào CSV thật" đã gặp. Ở P0-B nó chạy trên cây
fixture dùng-một-lần.

### O2 sau P0-B — hai trạng thái, không có ở giữa

**Nếu xanh:**

> Tenant isolation was demonstrated on the **evaluated tenant-scoped API and
> storage paths**, through runtime-role behavioral tests, cross-store positive
> controls, adversarial cross-tenant requests, and postcondition checks across
> PostgreSQL, CSV, and file storage. **The user-scoped experiment/model-tracking
> subsystem and tenant-specific cryptographic SOT authority remain outside this
> validated boundary.**

Đủ mạnh để đứng, nhưng không để hội đồng tìm được một bảng thiếu `tenant_id` rồi
bác cả kết luận.

### Ranh giới cứng của artifact P0-B

```
Out of scope: datasets, dataset_versions, experiments, and model_versions
              from the user-scoped experiment-tracking path.
```

Ghi thẳng vào artifact. Nhờ vậy, nếu P0-B đạt thì bằng chứng vẫn **hoàn toàn hợp
lệ trong đúng phạm vi nó kiểm tra** — thay vì bị bác vì một suy diễn vượt phạm vi.
Xem `MODEL_tenant_ml_domain.md` §3.

**Nếu không:**

> *Partially evidenced* — database/runtime-role isolation and selected request
> paths were verified, but the end-to-end adversarial claim was not published
> because the measurement validity conditions were not all satisfied.

Không có trạng thái "gần đạt".

Community-stats **không còn là blocker** về scoping. Full-suite FINAL chỉ chạy
**sau** P0-B, trên cây đã chứa mọi thay đổi phát sinh từ nó.

## §10. O6 — Đạt, có hạn chế về độ tin cậy

**Không phải "Partial" về năng lực.** Cả bốn workload đều operational; phần phải
hạ claim nằm ở *độ tin cậy khi lỗi* và *tính idempotent*, không nằm ở việc
pipeline có tồn tại hay không.

Câu chính thức:

> CTU-SignBridge triển khai pipeline xử lý bất đồng bộ bằng Celery cho ingestion,
> segmentation, augmentation và cloud synchronization. Segmentation và augmentation
> được thực hiện bên trong tác vụ ingestion thay vì là các stage được enqueue độc
> lập. Cloud synchronization có cơ chế retry tương đối hoàn chỉnh, trong khi
> ingestion chưa có retry policy tường minh. Tính idempotent cũng không đồng đều:
> các cập nhật metadata theo khoá ổn định có thể lặp lại an toàn, nhưng một số
> thao tác tạo mẫu và tải đối tượng lên Google Drive có thể sinh tài nguyên trùng
> khi task được thực thi lại.

Sơ đồ đúng — hai cụm, KHÔNG phải bốn stage độc lập:

```
Upload request
    ↓
enqueue_process_video
    ↓
process_video_job
    ├─ landmark extraction / ingestion
    ├─ segmentation
    ├─ augmentation
    └─ persistence
          ↓
     .npz + CSV + PostgreSQL

Cloud synchronization
    ↓
các Celery task riêng
    ↓
Google Drive / storage backend
```

### Bốn năng lực, hai trục ngang

```
Ingestion               OPERATIONAL
Segmentation            OPERATIONAL (nhúng trong ingestion)
Augmentation            OPERATIONAL (nhúng trong ingestion)
Cloud synchronization   OPERATIONAL
Retry                   PARTIAL   — ingestion KHÔNG có retry
Idempotency             PARTIAL   — tạo mẫu và tải Drive: không
```

Cả bốn năng lực đề cương nêu đều **thực thi trên worker**, không cái nào chỉ là
khung sườn. Ba điều chỉnh phải nêu:

1. **Segmentation/augmentation nhúng trong task ingestion**, không có điểm enqueue
   riêng — không điều phối hay thử lại độc lập được.
2. **Ingestion không có retry** (`@celery_app.task(bind=True)` trần, `except` ném
   lại). Một lượt hỏng là mất hẳn. Nhánh đồng bộ đám mây thì có `self.retry` thật
   ở 8 chỗ.
3. **`sample_uid = uuid.uuid4().hex[:10]`** — định danh ngẫu nhiên, không dẫn xuất
   từ nội dung, không khoá idempotency. Và `upload_to_gdrive()` mặc định
   `replace_existing=False` trong một task **có** `max_retries=5`: tải xong mà
   bước cập nhật sau hỏng thì lượt retry tạo **đối tượng Drive trùng lặp**.

Không nói "pipeline bất đồng bộ đầy đủ với retry và idempotency". Chi tiết:
`AUDIT_async_pipeline.md`.
| hiệu năng | độ trễ API trong môi trường kiểm soát | đã chứng minh cô lập hiệu năng giữa các tenant |
| lưu trữ | giảm 92,2% trên tổng, 91,6% trung vị, đo ghép cặp mẫu QIPEDC | "mọi mẫu giảm >90%"; tỉ lệ đo trên dữ liệu do chính hệ thống thu |

## §11. O5 — ĐẠT

| Cam kết | Trạng thái | Bằng chứng |
|---|---|---|
| Workflow điểm mốc cải thiện hiệu quả lưu trữ | **Đạt** | giảm 92,2% tổng dung lượng trên 54 cặp video–điểm mốc QIPEDC khớp thời lượng, đạt ngưỡng phát hiện |
| Kết quả mong đợi ">90%" | **Xác nhận** | 92,2% tổng; trung vị 91,6% |
| Khái quát sang bản ghi webcam của nền tảng | **Chưa thiết lập** | video nguồn là clip QIPEDC phân phối web |

Sắc thái phải giữ:

| phát biểu | đúng? |
|---|---|
| giảm >90% trên **tổng dung lượng** | **đúng** — 92,2% |
| giảm >90% ở **mẫu trung vị** | **đúng** — 91,6% |
| giảm >90% ở **mọi mẫu** | **sai** — 9/54 nằm dưới, thấp nhất 87,8% |

Tiêu chí đưa vào (đặt trước khi xem kết quả): 200 clip ngẫu nhiên hạt giống cố
định → chỉ so cặp khớp thời lượng → chỉ giữ clip đạt ngưỡng phát hiện ≥90% →
n=54. **Không** phải chọn lọc theo kích thước tệp.

Con số phải công bố là **92,2%**, không phải con số cao hơn. Hai con số cao hơn
xuất hiện trong quá trình đo và đều **bị loại có lý do**:

* **97,6%** — so `.npz` 60 khung với clip trung vị 3,85 giây. Nền tảng lưu cố
  định 60 khung bất kể độ dài, nên phần chênh này là **cắt bớt thời lượng**, không
  phải biểu diễn hiệu quả hơn.
* **95,5%** — khớp thời lượng nhưng tính cả 146 clip mà MediaPipe bắt được tay
  dưới 90%. Khung không bắt được tay là vector **toàn số 0** và nén gần như miễn
  phí; những mẫu đó là **hỏng phát hiện**, dùng chúng để nâng tỉ lệ tiết kiệm là
  lấy thất bại của hệ thống làm thành tích.

Chi tiết, giới hạn và cách tái lập: `MEASUREMENT_storage_efficiency.md`. Giới hạn
bắt buộc nêu kèm:

> Phép đo sử dụng video QIPEDC đã được nén để phân phối trên web; do đó kết quả
> **không được xem là phép đo trực tiếp đối với luồng webcam của
> CTU-SignBridge.**

Tỉ lệ bắt được tay 59,2% trên tập này là **quan sát phụ**, thuộc Threats to
Validity, không thuộc kết luận lưu trữ và **không** đại diện cho capture success
rate của nền tảng.

## §12. Điều kiện công bố P0

```
fixture_cross_store_valid       = true
positive_control_passed         = true
targets_untouched_after_control = true
indeterminate                   = 0
postconditions_passed           = true
environment_unchanged           = true
-> measurement_status = OK
```

Sai một điều kiện thì chỉ số là `NOT_PUBLISHABLE`. Xem
`HANDOFF_fixture_cross_store.md`.

## §13. Còn phải làm

| ưu tiên | việc | ghi chú |
|---|---|---|
| ~~P0-A~~ | ~~đo hiệu quả lưu trữ~~ | **xong** — 92,2%, xem §11 |
| **P0-B** | **cách ly xuyên kho** | **chặn bởi: review + commit cây làm việc** — precheck 474 pass |
| ~~P0-C~~ | ~~đối chiếu cam kết~~ | **xong** — tài liệu này |
| ~~P1-A~~ | ~~ma trận giả mạo SOT~~ | **xong** — 9 ca, 8 thoả + S7, xem §6 |
| P1-B | báo cáo test chức năng | full-suite cuối, **sau** P0-B |
| — | hợp nhất vào Chương 3/4 + rà claim ngược chiều | sau P1-B |
| — | đối chiếu 4 bản thuyết minh với `docs/TENANT_ISOLATION_AND_AUTHZ.md` | tránh hai nguồn nói lệch |
| ~~P1-C~~ | ~~kiểm workload bất đồng bộ~~ | **xong** — `AUDIT_async_pipeline.md`, xem §10 |
| ~~P1-D~~ | ~~kiểm demo nhận dạng thời gian thực~~ | **xong** — OPERATIONAL WITH PREREQUISITES, `AUDIT_realtime_recognition.md` |
| — | ~~ma trận phạm vi RBAC~~ | **bỏ** — `ws=0 prj=0`, không dựng thêm chỉ để khớp đề cương; ghi deviation ở §2 |
| — | ~~thí nghiệm lưu trữ bổ sung~~ | **đóng** — 92,2% đã đủ xác nhận |
