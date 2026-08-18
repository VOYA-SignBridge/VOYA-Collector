# ĐẶC TẢ 28 HÌNH CHƯƠNG 3 — BẢN TIẾNG ANH (khung rút gọn cuối cùng)

> **Bám theo:** *Chapter 3 — Solution Design and Implementation*, đánh số hình
> **Figure 3.1 – 3.28**. Tài liệu này **không sửa nội dung chương**; nó chỉ nói mỗi
> hình phải vẽ gì.
>
> **Ngôn ngữ nhãn:** mọi nhãn trong hình viết **tiếng Anh**, khớp từng chữ với thuật
> ngữ trong chương. Phần hướng dẫn viết tiếng Việt. Khối bố cục trong tài liệu này
> **chép thẳng vào hình được**.
>
> **Mốc dữ liệu:** mọi con số đo trên `signdb` đang chạy ngày **18/08/2026**, lược đồ
> phiên bản 5 — khớp với các con số đã ghi trong chương (59 bảng + 1 view · 36 bảng
> thuộc tổ chức · 35 chính sách RLS · 123 khoá ngoại · 24 khoá ghép · 6 trigger ·
> 15 dịch vụ).
>
> **Thay thế:** tài liệu này thay cho `HUONG_DAN_VE_42_HINH_CHUONG3.md` (viết cho
> khung 42 hình bản tiếng Việt trước đó). Giữ hay xoá tệp cũ là quyết định của tác giả.

---

## 0. Quy ước chung — đọc trước khi vẽ hình đầu tiên

### 0.1 Loại hình và công cụ

*Bảng 0-1: Phân loại 28 hình*

| Loại | Công cụ đề xuất | Các hình |
|---|---|---|
| Sơ đồ ngữ cảnh | draw.io | 3.1, 3.2 |
| Activity diagram | PlantUML | 3.3, 3.21, 3.27 |
| Infographic | draw.io | 3.4, 3.8, 3.12, 3.25 |
| Use case diagram | PlantUML | 3.5, 3.6, 3.7, 3.9, 3.10 |
| Sơ đồ kiến trúc / khối | draw.io | 3.11, 3.20 |
| Mô hình dữ liệu | PowerDesigner | 3.13, 3.14, 3.15–3.18 |
| Sequence diagram | PlantUML | 3.19, 3.22, 3.23, 3.26 |
| State machine | PlantUML | 3.24 |
| Deployment diagram | draw.io | 3.28 |

### 0.2 Quy ước trắng đen — **bắt buộc**

Bản in là trắng đen. **Không dùng màu** để phân biệt bất cứ thứ gì.

*Bảng 0-2: Cách phân biệt khi in trắng đen*

| Cần phân biệt | Cách ĐÚNG | Cách SAI |
|---|---|---|
| Luồng chính vs ngoại lệ | nét liền vs **nét đứt** | đen vs đỏ |
| Actor người vs hệ thống | người que vs **hộp `«system»`** | xanh vs xám |
| **Đã hiện thực vs thiết kế đích** | nét liền vs **nét đứt + `«target design»`** | đậm vs mờ |
| Phân hệ nghiên cứu vs phần còn lại | **viền đậm gấp đôi** | tô nền |
| Vùng trách nhiệm | **swimlane** có tên | nền khác nhau |

Với PlantUML, thêm `skinparam monochrome true` vào mọi mã nguồn.

### 0.3 Ba trạng thái hiện thực — ký hiệu thống nhất toàn chương

Chương trình bày cả phần đã chạy lẫn phần ở mức thiết kế. **Hình không được làm hai
thứ đó trông giống nhau.**

| Ký hiệu | Nghĩa | Vẽ bằng |
|:--:|---|---|
| **(mặc định)** | Đã hiện thực | nét liền |
| **`«partial»`** | Có cấu trúc và bề mặt, chưa phân vùng dữ liệu đầy đủ | nét liền + nhãn |
| **`«target design»`** | Chưa có trong lược đồ vật lý đang chạy | **nét đứt** + nhãn |

Ba thứ **bắt buộc** mang nhãn ở mọi hình chúng xuất hiện:

* **Workspace / Project** → `«partial»` — chương ghi rõ *"their membership structures
  are available, although the main VSL data entities are not yet fully partitioned at
  those lower levels"*.
* **Dataset Version / Sample Revision** → `«target design»` — chương ghi rõ *"remains
  part of the target design rather than the current runtime implementation"*.
* **Community Data Commons** → `«target design»` — tenant dự trữ đã có, dữ liệu chưa có.

### 0.4 Bốn thuật ngữ dễ vẽ sai

1. **System Catalogue ≠ Community.** *System Catalogue* là cấu hình tham chiếu do nền
   tảng quản lý (ba bảng `community_*` — **tên bảng là di sản**). **Community là một
   tenant dự trữ**, một hàng của bảng tổ chức với `tenant_type = 'COMMUNITY'`. Vẽ
   Community thành mặt phẳng ngoài cây tenant là **sai** — chương nói rõ nó *"uses the
   same tenant isolation and authorization mechanisms as organization-owned data"*.
2. **Tenant lịch sử `default` không phải Community**, cũng không phải nguồn dữ liệu
   chung. Chương gọi nó là *"a normal tenant"*.
3. **Signer ≠ Registered User.** Hai actor tách biệt, hai cạnh khác nhau tới Sample.
4. **Registry Version ≠ Dataset Version.** Registry Version ghim **label space**;
   Dataset Version ghim **nội dung bộ dữ liệu** và **chưa tồn tại**.

### 0.5 Bộ nhãn tiếng Anh chuẩn — dùng nguyên văn trong hình

*Bảng 0-3: Thuật ngữ khoá — chép đúng, không dịch lại*

| Khái niệm | Nhãn dùng trong hình |
|---|---|
| Phân hệ nghiên cứu | `VSL Data Collection and Management Subsystem` |
| Nền tảng bao ngoài | `CTU.SignBridge` |
| Bốn nhóm chức năng | `F1 Tenant and Access Management` · `F2 VSL Vocabulary Management` · `F3 VSL Data Collection and Sample Management` · `F4 Data Processing, Provenance and Integrity` |
| Sáu lớp người dùng | `Registered User` · `Data Contributor` · `Data Editor / Researcher` · `Tenant Administrator` · `Platform Administrator` · `Signer` |
| Cây phạm vi | `System` → `Tenant` → `Workspace` → `Project` |
| Bốn mô-đun dữ liệu | `Module A: Tenant and Authorization` · `Module B: Vocabulary and Registry` · `Module C: Collection and Sample` · `Module D: Governance and Platform` |
| Hai đường thu | `Direct Camera Collection` · `Existing Data Import` |

---

# PHẦN I — TỔNG QUAN VÀ YÊU CẦU (Figure 3.1 – 3.5)

## FIGURE 3.1 — Problem Context of Multi-Organizational VSL Data Collection

**Loại:** sơ đồ ngữ cảnh · **Công cụ:** draw.io

**Phải thể hiện:**

```
┌─ Organization A ──────┐ ┌─ Organization B ──────┐ ┌─ Organization C ──────┐
│  Members              │ │  Members              │ │  Members              │
│  Vocabulary           │ │  Vocabulary           │ │  Vocabulary           │
│  Signers              │ │  Signers              │ │  Signers              │
│  Collection Sessions  │ │  Collection Sessions  │ │  Collection Sessions  │
│  Samples              │ │  Samples              │ │  Samples              │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
        ╎                          ╎                          ╎
        └──────────────────────────┴──────────────────────────┘
                                   ▼
        ┌──────────────────────────────────────────────────────┐
        │  VSL Data Collection and Management Subsystem         │
        │  (shared deployment · shared infrastructure)          │
        └──────────────────────────────────────────────────────┘
                                   │
                                   ▼   managed data only
        ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
          Downstream Research      Downstream Recognition        ← nét đứt
```

* Ba khối tổ chức có **viền đậm liền** — đây là *visible data boundary* mà chương yêu cầu.
* **Không có mũi tên ngang** giữa ba khối tổ chức.
* Hai khối hạ nguồn vẽ **nét đứt**, nằm **ngoài** khung phân hệ.

**Điểm phải nhìn thấy được:** ba tổ chức **dùng chung một bản triển khai** nhưng
**không có đường dữ liệu nào nối ngang**. Đây là hình minh hoạ trực tiếp cho câu
*"share the same software deployment, while their data and administrative
responsibilities must remain independent"*.

**Không được vẽ:** một khối "shared data" nằm giữa ba tổ chức.

**Caption:** *Figure 3.1. Problem context of multi-organizational VSL data collection.*

---

## FIGURE 3.2 — Context of the Proposed Subsystem within CTU.SignBridge

**Loại:** sơ đồ ngữ cảnh hai lớp · **Công cụ:** draw.io

**Phải thể hiện:**

```
╔══════════════ CTU.SignBridge ══════════════════════════════════════════╗
║                                                                         ║
║  ╔═══ VSL Data Collection and Management Subsystem ═══╗   ← VIỀN ĐẬM   ║
║  ║      (developed in this thesis)                     ║     GẤP ĐÔI    ║
║  ║   ┌──────────────────┐  ┌──────────────────┐        ║                ║
║  ║   │ Tenant and Access│  │ Vocabulary        │       ║                ║
║  ║   └──────────────────┘  └──────────────────┘        ║                ║
║  ║   ┌──────────────────┐  ┌──────────────────┐        ║                ║
║  ║   │ Signer and       │  │ Collection and   │        ║                ║
║  ║   │ Session          │  │ Sample           │        ║                ║
║  ║   └──────────────────┘  └──────────────────┘        ║                ║
║  ║   ┌───────────────────────────────────────┐         ║                ║
║  ║   │ Provenance and Integrity              │         ║                ║
║  ║   └───────────────────────────────────────┘         ║                ║
║  ╚═════════════════════════════════════════════════════╝                ║
║                              │ managed VSL data                          ║
║                              ▼                                           ║
║   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ┐   ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐                      ║
║   │ Downstream       │   │ Real-Time Recognition │   ← nét đứt           ║
║   │ Training         │   │                       │   «downstream»        ║
║   └ ─ ─ ─ ─ ─ ─ ─ ─ ┘   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘                      ║
╚═════════════════════════════════════════════════════════════════════════╝
```

* Khối phân hệ nghiên cứu là **thứ duy nhất** trong hình có viền đậm gấp đôi.
* Hai khối hạ nguồn nét đứt, có nhãn `«downstream»`.

**Điểm phải nhìn thấy được:** ranh giới giữa **thứ luận văn thiết kế** và **thứ chỉ
tiêu thụ dữ liệu**. Nếu hai lớp trông ngang nhau, hội đồng sẽ hỏi *"đề tài là quản lý
dữ liệu hay huấn luyện?"* — và đó là câu hỏi tác giả tự tạo ra cho mình.

**Caption:** *Figure 3.2. Context of the proposed subsystem within CTU.SignBridge.*

---

## FIGURE 3.3 — General Operational Workflow

**Loại:** activity diagram · **Công cụ:** PlantUML

**Phải thể hiện — mười bước, ba điểm rẽ có guard:**

```
● start
↓ Authentication
↓ Resolve Tenant and Permission
◇ [permission not granted] ──→ Reject and record audit evidence ──→ ⊗
↓ [permission granted]
↓ Browse or Manage Vocabulary
↓ Select Signer and Collection Context
   📎 note: identified when that information is available
▬ fork
   ├─ Camera Collection      : landmark sequence produced IN THE BROWSER
   └─ Existing Recording Import : SOURCE PRESERVED BEFORE derived processing
▬ join
↓ Validation                 : organizational scope and relationships
◇ [cross-organization relationship detected] ──→ Reject ──→ ⊗
↓ [valid]
↓ Processing                 : delegated to background worker when long-running
▯ Managed Sample             ← object node
↓ Review and Management      : browse · update · soft-delete · restore
↓ Export or Downstream Use
◉ end
```

**Bốn ghi chú bắt buộc trên hình:**
1. Ở nhánh camera: *"landmark sequence produced in the browser before submission"*.
2. Ở nhánh import: *"source file accepted and preserved before derived processing"*.
3. Ở bước Processing: *"the user does not need to keep the original HTTP request open"*.
4. Ở bước Validation: *"organizational scope validated on the server"*.

**Điểm phải nhìn thấy được:** hai đường thu **hội tụ** vào cùng một `Managed Sample`
nhưng **khác nhau ở khâu source preservation** — đúng câu của chương: *"differ in
source preservation and reprocessing capability"*.

**Caption:** *Figure 3.3. General operational workflow.*

---

## FIGURE 3.4 — Functional Overview of the Proposed Subsystem

**Loại:** infographic · **Công cụ:** draw.io

**Phải thể hiện:**

```
                    ┌──────────────────────────────────┐
                    │  F1 Tenant and Access Management │
                    │  Organizations · Members ·        │
                    │  Workspace · Project · Roles      │
                    └──────────────────────────────────┘
                                   ▲
  ┌────────────────────────┐       │       ┌────────────────────────────┐
  │ F4 Data Processing,    │◄──┌───────────┐──►│ F2 VSL Vocabulary      │
  │ Provenance & Integrity │   │  MANAGED  │   │ Management             │
  │ Async processing ·     │   │  VSL DATA │   │ Languages · Dialects · │
  │ Provenance · Export ·  │   │           │   │ Regions · Sign Classes │
  │ Catalogue versions ·   │   └───────────┘   │ Catalogue states       │
  │ Integrity verification │       │           └────────────────────────┘
  └────────────────────────┘       ▼
                    ┌───────────────────────────────────────┐
                    │ F3 VSL Data Collection and Sample Mgmt│
                    │ Signers · Sessions · Direct collection│
                    │ Data import · Sample lifecycle        │
                    └───────────────────────────────────────┘
```

* Khối tâm `MANAGED VSL DATA` vẽ đậm nhất.
* Bốn khối chức năng ghi đúng mã **F1–F4** và mô tả rút từ Table 3.1.
* Ở góc dưới phải, thêm **một khối nét đứt** nhỏ: `Downstream Training / Recognition`
  với nhãn *"consume managed data — not the primary design object"*.

**Điểm phải nhìn thấy được:** bốn chức năng **xoay quanh dữ liệu**, không xếp tuần
tự. Đó là lý do chúng là bốn *chức năng* chứ không phải bốn *giai đoạn*.

**Caption:** *Figure 3.4. Functional overview of the proposed subsystem.*

---

## FIGURE 3.5 — UML Actor Diagram

**Loại:** use case diagram (phần actor) · **Công cụ:** PlantUML

**Phải thể hiện — ba nhánh tách biệt:**

```
              ┌─────────────────┐
              │ Registered User │   «general actor»
              └────────▲────────┘
                       │ generalization (tam giác rỗng, nét liền)
        ┌──────────────┼──────────────────┐
        │              │                  │
┌───────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│Data Contributor│ │Data Editor /     │ │Tenant Administrator  │
│               │ │Researcher        │ │                      │
└───────────────┘ └──────────────────┘ └──────────────────────┘


┌────────────────────────┐        ┌──────────────────────────┐
│ Platform Administrator │        │ Signer                   │
│                        │        │ «data subject»           │
│ (SEPARATE — no         │        │ (SEPARATE — may not have │
│  generalization link)  │        │  a platform account)     │
└────────────────────────┘        └──────────────────────────┘
```

**Hai ranh giới phải nhìn thấy được:**

1. **Platform Administrator KHÔNG nối vào nhánh Registered User.** Chương ghi rõ nó
   *"performs explicitly authorized platform-wide operations and is distinct from a
   Tenant Administrator"*. Nếu vẽ đường kế thừa, hình nói rằng quản trị nền tảng là
   một dạng chuyên biệt của người dùng tổ chức — sai mô hình quyền.
2. **Signer đứng riêng và không có cung nào tới nhóm người dùng.** Chương ghi:
   *"The signer may not have a platform account."* Đây là lý do chủ thể dữ liệu được
   mô hình hoá tách khỏi tài khoản vận hành.

**Caption:** *Figure 3.5. UML actor diagram.*

---

# PHẦN II — USE CASE (Figure 3.6, 3.7, 3.9, 3.10) VÀ INFOGRAPHIC 3.8

> **Quy ước chung cho bốn sơ đồ use case:** actor người vẽ **người que**; actor hệ
> thống vẽ **hộp `«system»`** và đặt **ngoài** khung phân hệ; tên use case **trùng
> từng chữ** với Table 3.3–3.6; mỗi use case ghi kèm mã `UCxx`.

## FIGURE 3.6 — Use Case Diagram: Tenant and Access Management

**Loại:** use case diagram · **Công cụ:** PlantUML

**Actor:** `Registered User` · `Tenant Administrator` · `Platform Administrator`
**Actor phụ (ngoài khung):** `Messaging Service «system»`

**Use case trong khung — đúng sáu, theo Table 3.3:**

```
UC01  Register and Sign In
UC02  Manage Tenant
UC03  Manage Members
UC04  Manage Workspace and Project        «partial»
UC05  Manage Roles and Permissions
UC06  Confirm Sensitive Administrative Action
```

**Quan hệ:**

| Từ | Loại | Tới | Guard |
|---|---|---|---|
| UC03 Manage Members | `«include»` | *Send invitation* (qua `Messaging Service`) | — |
| UC06 Confirm Sensitive Administrative Action | `«extend»` | UC02 Manage Tenant | *when the action is destructive* |
| UC06 | `«extend»` | UC05 Manage Roles and Permissions | *when the action is sensitive* |

**Ghi chú gấp góc bắt buộc — đặt cạnh khung, chép nguyên công thức của chương:**

```
Allow(u, a, s) = Authenticated(u) ∧ ScopeValid(s) ∧ PermissionGranted(u, a, s)

Membership alone does not satisfy the permission condition.
```

**Ghi chú thứ hai — đặt cạnh UC04:** *"membership structure available; principal VSL
data entities not yet partitioned at Workspace or Project level"*.

**Điểm phải nhìn thấy được:** **không có cung nào** cho phép Tenant Administrator
thêm thành viên trực tiếp. Đường duy nhất đi qua UC03 và cần `Messaging Service`, tức
cần **chính người được mời hành động**.

**Caption:** *Figure 3.6. Use case diagram: tenant and access management.*

---

## FIGURE 3.7 — Use Case Diagram: VSL Vocabulary Management

**Loại:** use case diagram · **Công cụ:** PlantUML

**Actor:** `Data Contributor` · `Data Editor / Researcher` · `Platform Administrator`

**Use case — đúng bốn, theo Table 3.4:**

```
UC07  Browse Vocabulary
UC08  Manage Sign Classes          ← creation · viewing · updating ·
                                     deactivation · controlled merging
UC09  Manage Dialect and Region
UC10  Manage Vocabulary Version
```

**Phân actor:** `Data Contributor` chỉ nối tới UC07. `Data Editor / Researcher` nối
tới UC07–UC10. `Platform Administrator` nối tới UC09 (phần cấu hình tham chiếu do
nền tảng quản lý) và UC10.

**Ghi chú gấp góc bắt buộc — hai cái:**

1. Cạnh UC08:
```
ClassIdentity = (Organization, Label, Language, Dialect, Region)
```
2. Cạnh UC09:
```
"Unclassified" ≠ "Common"
Unclassified : regional classification NOT YET established
Common       : deliberately verified as NOT requiring regional differentiation
```

**Ghi chú thứ ba — cạnh UC08, về merging:** *"class merging retains a mapping so that
references to previous definitions remain interpretable"*.

**Điểm phải nhìn thấy được:** UC08 là **một** use case bao gồm cả merging, không tách
thành năm use case CRUD. Chương nói rõ: *"includes creation, viewing, updating,
deactivation, and controlled merging where required"*.

**Caption:** *Figure 3.7. Use case diagram: VSL vocabulary management.*

---

## FIGURE 3.8 — Sign-Class Identity Infographic

**Loại:** infographic · **Công cụ:** draw.io

**Phải thể hiện — năm chiều toả ra từ tâm:**

```
                        Language
                            ▲
                            │
        Label ◄─────┌───────────────┐─────► Dialect
                    │   SIGN CLASS  │
                    │               │
        Organization ◄──└───────────────┘──► Region
```

**Bảng đối chứng đặt ngay dưới hình — bắt buộc có, vì nó là thứ chứng minh mô hình:**

```
╔═══ VALID — both classes coexist ════════════════════════════════════════╗
║  (Org-1, "xin-chao", VSL, hoa-de, can-tho)     ✓ accepted               ║
║  (Org-1, "xin-chao", VSL, hoa-de, ha-noi)      ✓ accepted               ║
║                                    └──────────┘ differs by REGION only  ║
╚═════════════════════════════════════════════════════════════════════════╝

╔═══ REJECTED — duplicate within the same context ════════════════════════╗
║  (Org-1, "xin-chao", VSL, hoa-de, can-tho)     ✓ accepted               ║
║  (Org-1, "xin-chao", VSL, hoa-de, can-tho)     ✗ rejected               ║
╚═════════════════════════════════════════════════════════════════════════╝
```

**Khối thứ ba — phân biệt hai giá trị đặc biệt:**

```
Region = "Unclassified"  →  classification NOT YET established
Region = "Common"        →  verified as NOT requiring differentiation
                            ⚠ these two are NOT interchangeable
```

**Điểm phải nhìn thấy được:** Region là **một phần của identity**, không phải thuộc
tính mô tả. Chương diễn đạt điều này bằng câu *"permits valid regional variants of the
same sign while preventing duplicate definitions within the same context"* — bảng đối
chứng hai chiều ở trên là hình ảnh của đúng câu đó.

**Caption:** *Figure 3.8. Sign-class identity model.*

---

## FIGURE 3.9 — Use Case Diagram: VSL Data Collection and Management

**Loại:** use case diagram · **Công cụ:** PlantUML

**Actor chính:** `Data Contributor` · `Data Editor / Researcher`
**Actor phụ (ngoài khung):** `Replica Storage «system»`
**Actor liên quan, KHÔNG nối cung:** `Signer «data subject»` — vẽ cạnh khung, nối bằng
**nét chấm** có nhãn `represented in`, tới UC11.

**Use case — đúng sáu, theo Table 3.5:**

```
UC11  Manage Signers                ← creation · viewing · updating ·
                                      deactivation · identity consolidation
UC12  Manage Collection Sessions    ← creating · viewing · updating ·
                                      closing · lifecycle management
UC13  Collect Sample from Camera
UC14  Import Existing Data
UC15  Manage Samples                ← browsing · detail · metadata update ·
                                      soft deletion · restoration · quality review
UC16  Monitor Processing
```

**Ghi chú gấp góc bắt buộc — đặt giữa UC13 và UC14, đây là điểm quan trọng nhất:**

```
UC13 Collect Sample from Camera
     browser produces the landmark sequence BEFORE submission
     ⚠ source video is NOT retained → NOT reprocessable

UC14 Import Existing Data
     source recording PRESERVED BEFORE derived processing
     ⚠ reprocessable
```

**Ghi chú thứ hai — đặt cạnh khung, chép nguyên câu của chương:** *"The subsystem shall
prevent sample operations from establishing cross-organization relationships with
vocabulary classes, signers, or collection contexts belonging to another tenant."*

**Không được vẽ:** `Background Worker` / `Processing Worker` làm actor. Nó là thành
phần **bên trong** ranh giới phân hệ; nó xuất hiện ở Figure 3.22 và 3.23.

**Caption:** *Figure 3.9. Use case diagram: VSL data collection and management.*

---

## FIGURE 3.10 — Use Case Diagram: Data Processing, Provenance and Integrity

**Loại:** use case diagram · **Công cụ:** PlantUML

**Actor:** `Data Editor / Researcher` · `Tenant Administrator` · `Platform Administrator`
**Actor phụ (ngoài khung):** `Authoritative Artifact Publisher «system»` ·
`Replica Storage «system»`

**Use case — đúng bốn, theo Table 3.6:**

```
UC17  Export Managed VSL Data
UC18  Inspect Data Provenance
UC19  Verify Authoritative Data
UC20  Synchronize Authoritative Data
```

* `Authoritative Artifact Publisher` nối vào UC19 bằng **mũi tên đi VÀO phân hệ**, nhãn
  *"pulled and verified by the subsystem"* — hệ thống **kéo** tạo tác về rồi tự xác
  minh, publisher **không gọi vào** hệ thống.

**Ghi chú gấp góc bắt buộc — cạnh UC18, chép nguyên tinh thần của chương:**

```
J → R_v          catalogue version identifies the LABEL SPACE used by a job

DatasetVersion → { SampleRevision_1 , … , SampleRevision_n }
                 «target design» — NOT an existing physical relationship
```

Vẽ dòng thứ hai bằng **nét đứt**.

**Điểm phải nhìn thấy được:** ranh giới giữa cái đã có (ghim label space) và cái chưa
có (ghim nội dung bộ dữ liệu). Chương nói thẳng: *"The physical runtime model does not
yet implement an immutable Dataset Version to Sample Revision relationship."*

**Caption:** *Figure 3.10. Use case diagram: data processing, provenance and integrity.*

---

# PHẦN III — KIẾN TRÚC (Figure 3.11 – 3.12)

## FIGURE 3.11 — Detailed Application Architecture

**Loại:** sơ đồ khối phân tầng · **Công cụ:** draw.io

**Phải thể hiện — năm tầng, đúng theo gợi ý của chương:**

```
┌─ PRESENTATION ──────────────────────────────────────────────────────┐
│  Web Client              Collection Interface                        │
│                          (client-side landmark extraction)           │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌─ APPLICATION ───────────────────────────────────────────────────────┐
│  Tenant and Authorization    │  Vocabulary                           │
│  Collection and Sample Mgmt  │  Provenance and Integrity             │
└──────────┬───────────────────────────────────┬───────────────────────┘
           │ synchronous                       │ delegated
           ▼                                   ▼
┌─ DATA ───────────────────────┐   ┌─ PROCESSING ───────────────────┐
│  PostgreSQL                  │   │  Task Queue                    │
│  Artifact Storage            │◄──│  Worker                        │
└──────────────────────────────┘   └────────────────────────────────┘
           │
           ▼
┌─ EXTERNAL OR DOWNSTREAM ────────────────────────────────────────────┐
│  Messaging  │  Replica Storage  │  Training  │  Recognition          │
│                                    └──── nét đứt «downstream» ────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Hai ghi chú bắt buộc:**
1. Cạnh tầng Application: *"a modular application rather than many independent business
   microservices"* — chép nguyên câu của chương, vì đây là quyết định kiến trúc dễ bị
   hiểu nhầm nhất khi nhìn Figure 3.28 với 15 container.
2. Cạnh tầng Processing: *"workloads with distinct resource needs and lifecycles run as
   separate services"*.

**Điểm phải nhìn thấy được:** phân tách **container** ở tầng vận hành **không** đồng
nghĩa phân tách **nghiệp vụ** thành vi dịch vụ. Figure 3.11 và Figure 3.28 phải đọc
được cùng nhau mà không mâu thuẫn.

**Caption:** *Figure 3.11. Detailed application architecture.*

---

## FIGURE 3.12 — Multi-Layer Tenant Isolation

**Loại:** infographic tầng xếp chồng · **Công cụ:** draw.io

**Phải thể hiện — sáu tầng theo đúng thứ tự chương đưa, mỗi tầng ghi *bịt lối vòng nào*:**

| # | Layer | What it closes | Nếu bỏ tầng này |
|---|---|---|---|
| 1 | `Authentication` | Unauthenticated access | Không có chủ thể để phân quyền |
| 2 | `Scoped Authorization` | Right user, wrong scope | Thành viên làm được mọi việc ở mọi phạm vi |
| 3 | `Transaction Organizational Context` | Context leaking across pooled connections | Yêu cầu kế tiếp chạy với ngữ cảnh của yêu cầu trước |
| 4 | `Row-Level Security` | Query written without a scope filter | Mọi truy vấn viết thiếu đều rò, và rò im lặng |
| 5 | `Composite Referential Constraints` | Relationship linking objects across organizations | Cơ sở dữ liệu không phản đối, vì khoá vẫn tồn tại |
| 6 | `Organization-Aware Artifact Access` | Data leaving the relational plane | Cách ly ở tầng CSDL không tự lan sang hệ tệp |

* Vẽ **một mũi tên tấn công** xuyên từ trên xuống, bị chặn ở từng tầng.
* Tầng 3, 4, 5 vẽ **viền đậm** kèm nhãn `database-enforced`.
* Tầng 6 vẽ viền **nét chấm** kèm nhãn *"lower assurance: storage layout + application
  checks"*.
* Ghi ở góc: **`24 composite foreign-key relationships`** và
  **`Row-Level Security on 35 of 36 organization-scoped tables`**.

**Ghi chú gấp góc — chép nguyên hai công thức của chương:**

```
Authorization = May the user perform this action?
Isolation     = Which organization-owned records may the operation access?
```

**Điểm phải nhìn thấy được:** sáu tầng **không phải sáu lớp giống nhau chồng lên cho
chắc** — mỗi tầng bịt **một lối vòng khác nhau** mà năm tầng còn lại để hở.

**Caption:** *Figure 3.12. Multi-layer tenant isolation.*

---

# PHẦN IV — MÔ HÌNH DỮ LIỆU (Figure 3.13 – 3.18)

## FIGURE 3.13 — Conceptual Data Model

**Loại:** CDM, ký pháp **Crow's Foot** · **Công cụ:** PowerDesigner

**Quy tắc cứng — chương đã ghi rõ:** *"Do not include SQL types, indexes, RLS policies,
or triggers."* Chỉ thực thể, thuộc tính nghiệp vụ, và lực lượng quan hệ.

**Hai mươi thực thể — đúng danh sách chương liệt kê, không thêm không bớt:**

```
NHÓM TỔ CHỨC VÀ QUYỀN
   Tenant · Workspace «partial» · Project «partial»
   User · Membership · Role · Permission

NHÓM TỪ VỰNG
   Sign Class · Language · Dialect · Region

NHÓM THU NHẬN
   Signer · Capture Session · Sample · Raw Upload

NHÓM PHIÊN BẢN VÀ QUẢN TRỊ
   Registry Version · Legal Document · User Consent · Signer Consent · Audit Event
```

**Quan hệ then chốt, ghi lực lượng Crow's Foot:**

```
Tenant       ──1──<──n── Workspace ──1──<──n── Project
Tenant       ──1──<──n── Sign Class
Tenant       ──1──<──n── Signer
User         ──1──<──n── Membership ──n──>──1── Tenant
Membership   ──1──<──n── Role Assignment ──n──>──1── Role
Role         ──n──>──<──n── Permission
Signer       ──1──<──n── Capture Session ──1──<──n── Sample
Sign Class   ──1──<──n── Sample
Sign Class   ──n──>──1── Language / Dialect / Region
Raw Upload   ──1──<──n── Sample          ← xem cảnh báo bên dưới
Registry Version ──1──<──n── (downstream job)
Legal Document ──1──<──n── User Consent
Legal Document ──1──<──n── Signer Consent
Signer         ──1──<──n── Signer Consent
```

**Bốn quy tắc bắt buộc:**

1. **User và Signer là hai thực thể riêng**, và **Sample nối tới cả hai** bằng **hai
   cạnh khác nhau**: một cạnh `operator` tới User, một cạnh `participant` tới Signer.
   Chương ghi: *"the software operator and the participant represented in the data may
   be different individuals"*.
2. **User Consent và Signer Consent là hai thực thể riêng.** Chương ghi: *"they
   represent different subjects and different legal meanings"*. Gộp là sai về ngữ
   nghĩa pháp lý.
3. **Workspace và Project mang nhãn `«partial»`.**
4. **Dataset, Dataset Version, Sample Revision** — chương cho phép hiện **chỉ như
   Target Design**. Nếu vẽ, đặt ở **một vùng riêng nét đứt** có tiêu đề
   `Target Design — not part of the current operational physical schema`. Nếu không
   chắc trình bày được rõ ràng, **bỏ hẳn ba thực thể này khỏi Figure 3.13** và chỉ nêu
   ở Figure 3.10 — như thế an toàn hơn.

**Cảnh báo về quan hệ `Raw Upload ─ Sample`:** ở CDM đây là quan hệ nghiệp vụ hợp lệ
và vẽ được. Nhưng ở **PDM (Figure 3.17)** nó **không được vẽ như khoá ngoại**, vì lược
đồ vật lý không có ràng buộc đó. Giữ nhất quán bằng cách ghi chú ở CDM: *"business
relationship; not enforced by a physical foreign key"*.

**Caption:** *Figure 3.13. Conceptual data model.*

---

## FIGURE 3.14 — Logical Data Model Overview

**Loại:** sơ đồ tổng quan LDM · **Công cụ:** PowerDesigner hoặc draw.io

**Phải thể hiện — bốn chuỗi quan hệ mà chương nêu đích danh, xếp thành bốn dải:**

```
DẢI 1 — ORGANIZATIONAL HIERARCHY
   Tenant ──> Workspace ──> Project
   ⚠ Tenant = enforced data boundary
   ⚠ Workspace / Project = «partial»

DẢI 2 — AUTHORIZATION CHAIN
   User ──> Membership ──> Role Assignment ──> Role ──> Permission
   ⚠ Role Assignment attaches to MEMBERSHIP, not to a (user, scope) pair

DẢI 3 — COLLECTION MODEL
   Signer ──> Capture Session ──> Sample <── Sign Class

DẢI 4 — VOCABULARY MODEL
   Sign Class <── Language
   Sign Class <── Dialect
   Sign Class <── Region

DẢI 5 — GOVERNANCE MODEL
   Legal Document ──> User Consent      (account-level)
   Legal Document ──> Signer Consent    (participant-level)
```

* Ô `Tenant` ở Dải 1 vẽ **viền đậm nhất toàn hình**, nhãn `enforced data boundary`.
* Vẽ **một cung tự trỏ** ở `Membership`, nhãn *"child membership requires parent
  membership"*.
* Bốn mô-đun A–D đánh dấu bằng **khung nét mảnh bao quanh nhóm thực thể tương ứng**,
  ghi tên mô-đun ở góc, để nối được với Figure 3.15–3.18.

**Điểm phải nhìn thấy được:** cây phạm vi có **bốn cấp** nhưng **chỉ Tenant là ranh
giới dữ liệu được cưỡng chế**. Vẽ bốn cấp trông đều nhau là nói quá.

**Caption:** *Figure 3.14. Logical data model overview.*

---

## FIGURE 3.15 — PDM Module A: Tenant and Authorization

**Loại:** PDM · **Công cụ:** PowerDesigner, **sinh từ lược đồ thật**

**Bảng phải có — 18 bảng, đúng theo Table 3.9 mở rộng:**

```
users · tenants · workspaces · projects · project_allocations
memberships · roles · permissions · role_permissions · role_assignments
tenant_invitations
refresh_tokens · password_reset_tokens · verification_codes
user_totp · user_recovery_codes · user_action_passcodes · api_keys

+ tenant_members  ⟨VIEW⟩   ← vẽ NÉT ĐỨT, nhãn «view»
```

**Bốn điểm bắt buộc:**

1. **`memberships` là MỘT bảng đa hình**, có cột `scope_level` nhận
   `TENANT | WORKSPACE | PROJECT`, ba cột phạm vi, và **khoá ngoại tự trỏ ghép**
   `(parent_membership_id, user_id)`.
   **KHÔNG vẽ** `workspace_members` hay `project_members` — hai bảng đó **không tồn tại**.
2. **`role_assignments` không có cột `tenant_id` và không bật RLS.** Ghi chú:
   *"scope inherited through membership; composite FK (membership_id, user_id) ensures
   the assignment and the membership belong to the same person"*.
   Cột `membership_id` **cho phép trống** — trống nghĩa là gán vai cấp `SYSTEM`.
3. **`roles.tenant_id` cho phép trống** — trống nghĩa là vai dựng sẵn của nền tảng.
   Ghi chú: *"platform-defined roles and tenant-specific roles share one table"*.
4. **`tenant_members` là VIEW**, không phải bảng.

**Ký hiệu bắt buộc trên hình:** bảng có RLS ghi khuôn chữ `«RLS»`; bảng có trigger ghi
`«trigger»`. Trong mô-đun này có **bốn** trigger: trên `memberships`,
`role_assignments`, `role_permissions`, `roles`.

**Caption:** *Figure 3.15. PDM Module A: tenant and authorization.*

---

## FIGURE 3.16 — PDM Module B: Vocabulary and Registry

**Loại:** PDM · **Công cụ:** PowerDesigner

**Bảng phải có — 11 bảng, chia ba vùng:**

```
VÙNG 1 — PLATFORM CATALOGUE  (no tenant column, no RLS)
   languages · regions

VÙNG 2 — TENANT-SCOPED VOCABULARY  (tenant column + RLS)
   dialects · dialect_aliases · recognition_profiles
   vocabulary_groups · vocabulary_registry_meta · registry_versions

VÙNG 3 — SYSTEM CATALOGUE  (no tenant column, no RLS)
   community_dialects · community_profiles · community_versions
   ⚠ table names are LEGACY — this is the System Catalogue,
     NOT the Community tenant
```

**Ba điểm bắt buộc:**

1. **Một mũi tên một chiều** từ Vùng 3 sang Vùng 2, nhãn:
   *"copied once when initializing tenant data"*.
   **Một mũi tên gạch chéo** theo chiều ngược, nhãn: *"no runtime fallback"*.
2. Ghi chú riêng, chữ đậm: *"Community is a reserved tenant — a row in `tenants` with
   `tenant_type = 'COMMUNITY'` — not these three tables."*
3. Khoá duy nhất **năm cột** của `classes` phải hiện trên hình dù `classes` thuộc
   Module C: vẽ nó ở rìa Vùng 2 như một tham chiếu, ghi
   `UNIQUE (tenant_id, slug, language, dialect, region)`.

**Ghi chú về `registry_versions`:** *"immutable by application convention; no database
trigger enforces it"* — phân biệt với `legal_documents` ở Module D, nơi tính bất biến
**có** trigger.

**Caption:** *Figure 3.16. PDM Module B: vocabulary and registry.*

---

## FIGURE 3.17 — PDM Module C: Collection and Sample

**Loại:** PDM · **Công cụ:** PowerDesigner

**Bảng phải có — 6 bảng cốt lõi cộng 3 bảng liên quan:**

```
signers · signer_aliases · capture_sessions · classes · raw_uploads · samples
training_jobs · training_job_classes · training_metrics    (liên quan, vẽ mờ ở rìa)
```

**Năm điểm bắt buộc — đây là hình quan trọng nhất trong bốn hình PDM:**

1. **Vẽ RÕ khoá ngoại ghép, ghi cặp cột trên cạnh:**
```
samples(tenant_id, class_uid)          → classes(tenant_id, class_uid)
samples(tenant_id, signer_id)          → signers(tenant_id, signer_id)
samples(tenant_id, dialect)            → dialects(tenant_id, dialect_id)
capture_sessions(tenant_id, class_uid) → classes(tenant_id, class_uid)
capture_sessions(tenant_id, signer_id) → signers(tenant_id, signer_id)
raw_uploads(tenant_id, class_uid)      → classes(tenant_id, class_uid)
signer_aliases(tenant_id, new_signer_id) → signers(tenant_id, signer_id)
training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)
```
   Ghi chú chung cho nhóm này, chép nguyên công thức của chương:
```
Reference(A, B) ⇒ Organization(A) = Organization(B)
```

2. **HAI cạnh khác nhau từ `samples`:** một tới `signers` (participant), một tới
   `users` qua cột tài khoản vận hành (operator). Đây là **điểm phải nhìn thấy được**
   của hình.

3. **KHÔNG vẽ khoá ngoại từ `raw_uploads` tới `samples`.** Lược đồ vật lý không có
   ràng buộc đó. Nếu muốn thể hiện quan hệ nghiệp vụ, vẽ **nét chấm mảnh** kèm nhãn
   *"business relationship; not enforced by a physical foreign key"*.

4. **`classes` ghi khoá duy nhất năm cột** ngay trên bảng.

5. **`capture_sessions` là thực thể có vòng đời riêng**, không phải thuộc tính của
   `samples` — chương ghi: *"an independent lifecycle entity rather than as a simple
   sample attribute"*. Vẽ nó ngang hàng với `samples`, không lồng vào.

**Caption:** *Figure 3.17. PDM Module C: collection and sample.*

---

## FIGURE 3.18 — PDM Module D: Governance and Platform

**Loại:** PDM · **Công cụ:** PowerDesigner

**Bảng phải có — 21 bảng, chia ba cụm:**

```
CỤM PHÁP LÝ VÀ ĐỒNG THUẬN
   legal_documents  «trigger: immutable after publication»
   legal_document_drafts
   legal_document_events  «trigger: append-only»
   user_consents · signer_consents

CỤM DỊCH VỤ TỔ CHỨC
   plans · tenant_subscriptions · tenant_usage_daily
   tenant_exports · tenant_purges
   webhook_endpoints · webhook_deliveries
   support_tickets · support_messages · notifications · event_outbox

CỤM NỀN TẢNG
   audit_log · platform_settings · sot_authorized_keys
   schema_migrations · google_sheets_sync_status
```

**Bốn điểm bắt buộc:**

1. **`user_consents` và `signer_consents` vẽ tách bạch**, mỗi bảng một ghi chú:
   * `user_consents` → *"account-level document acknowledgement"*
   * `signer_consents` → *"participant-level data-use consent — governs data release"*
2. **Cả hai nối tới `legal_documents` bằng khoá ghép `(kind, version)`.** Ghi rõ cặp
   cột trên cạnh. **KHÔNG vẽ** một bảng `legal_document_versions` riêng — nó không tồn
   tại; định danh nghiệp vụ nằm trên chính bảng văn bản.
3. **`tenant_purges` đánh dấu là ngoại lệ duy nhất** không bật RLY trong số 36 bảng
   thuộc tổ chức. Ghi chú ngắn ngay trên bảng.
4. **Hai trigger của mô-đun này** ghi khuôn chữ `«trigger»`, cộng với bốn trigger ở
   Module A là **đủ sáu** — khớp câu của chương *"six database triggers"*.

**Caption:** *Figure 3.18. PDM Module D: governance and platform.*

---

## PHỤ LỤC C — PDM đầy đủ

Hình PDM đầy đủ **59 bảng và 1 view** đặt ở Phụ lục C, sinh trực tiếp từ lược đồ.
Trong thân chương chỉ vẽ **cột khoá và cột ràng buộc**; danh sách cột đầy đủ nằm ở
Data Dictionary.

---

# PHẦN V — TRÌNH BÀY DATA DICTIONARY (Table 3.13 – 3.22 và Phụ lục C)

## V.1 Hai mức từ điển dữ liệu — đừng lẫn

Chương có **hai** mức trình bày từ điển dữ liệu, và chúng khác nhau về mục đích:

| | Trong thân chương (Table 3.13–3.22) | Trong Phụ lục C |
|---|---|---|
| Cấp độ | **Khái niệm** — thuộc tính nghiệp vụ | **Vật lý** — từng trường |
| Cột | `Attribute` · `Description` | `Field Name` · `Data Type` · `Constraint` · `Description` |
| Phạm vi | 10 thực thể quan trọng nhất | **59 bảng · 636 trường** |
| Mục đích | Người đọc hiểu **thực thể làm gì** | Người đọc **dựng lại được lược đồ** |

Chương đã ghi đúng ranh giới này: *"The main chapter presents the most important
entities. The complete field-level Data Dictionary for all physical tables is provided
in Appendix C."*

**Tệp đã có sẵn cho Phụ lục C:** [PHU_LUC_A2_TU_DIEN_DU_LIEU.md](PHU_LUC_A2_TU_DIEN_DU_LIEU.md)
— 59 bảng, 636 trường, phần diễn giải đã viết đủ. Chỉ cần đổi tiêu đề phụ lục cho khớp
đánh số mới và dịch sang tiếng Anh nếu quyển nộp bằng tiếng Anh.

## V.2 Khuôn trình bày bảng từ điển — dùng cho CẢ hai mức

Mỗi bảng từ điển trình bày như **một bảng có dải tiêu đề**, theo mẫu:

```
╔══════════════════════════════════════════════════════════════════════╗
║                          T E N A N T                                  ║   ← dải tiêu đề
╠═══════════════╦═══════════════╦═══════════════╦══════════════════════╣      nền đậm, chữ trắng
║  Field Name   ║  Data Type    ║  Constraint   ║  Description         ║   ← hàng tiêu đề cột
╠═══════════════╬═══════════════╬═══════════════╬══════════════════════╣      nền đậm, chữ trắng
║ tenant_id     ║ Text          ║ Primary key   ║ Stable organizational║
║               ║               ║               ║ identity             ║
╟───────────────╫───────────────╫───────────────╫──────────────────────╢
║ display_name  ║ Text          ║ Required      ║ Human-readable       ║
║               ║               ║               ║ organization name    ║
╚═══════════════╩═══════════════╩═══════════════╩══════════════════════╝
```

**Sáu quy tắc trình bày:**

1. **Dải tiêu đề mang tên bảng**, nền đậm, chữ trắng, canh giữa, gộp cả bốn cột.
2. **Hàng tiêu đề cột** cùng kiểu nền đậm chữ trắng.
3. **Cột `Constraint` ghi đủ**, theo thứ tự: `Primary key` · `Foreign key → <bảng đích>` ·
   `Unique` · `Required` · `Default: <giá trị>` · `Values: <tập giá trị>`. Trống thì để
   trống hẳn, **không ghi dấu gạch**.
4. **Khoá ngoại ghép** ghi rõ: `Foreign key → classes (composite)`. Đây là cơ chế quan
   trọng nhất của lược đồ, không được rút gọn thành `Foreign key`.
5. **Trường cho phép trống** phải nói rõ trong `Description` **giá trị trống nghĩa là
   gì**. Ví dụ: `storage_url` trống = *"not yet replicated"*, **không** phải *"sample
   is broken"*. Một trường trống không có định nghĩa nghiệp vụ là một trường sẽ bị đọc sai.
6. **Số thứ tự trường giữ theo `ordinal_position` thật.** Số khuyết là trường đã bị
   gỡ; giữ nguyên khoảng trống để đối chiếu với cơ sở dữ liệu không lệch.

## V.3 Mười bảng từ điển của thân chương

Mười bảng Table 3.13–3.22 giữ **hai cột** `Attribute | Description` như chương đã viết.
Áp dụng cùng kiểu dải tiêu đề ở §V.2, chỉ khác số cột.

| Table | Thực thể | Ghi chú trình bày bắt buộc |
|---|---|---|
| 3.13 | `Tenant` | Ghi rõ `Tenant Type` phân biệt tổ chức thường và **Community** |
| 3.14 | `Membership` | `Scope Level` nhận ba giá trị; `Parent Membership` là quan hệ tự trỏ |
| 3.15 | `Role Assignment` | Nhấn `Membership` là **cái mang phạm vi**, không phải cặp (user, scope) |
| 3.16 | `Sign Class` | Năm thuộc tính đầu hợp thành **identity**, đánh dấu nhóm |
| 3.17 | `Signer` | Ghi rõ `Linked User` là **tuỳ chọn** — signer có thể không có tài khoản |
| 3.18 | `Capture Session` | Phân biệt `Signer` (participant) với `Operator` (account) |
| 3.19 | `Sample` | Trình bày **theo nhóm thuộc tính**, không liệt kê 42 trường ở thân chương |
| 3.20 | `Registry Version` | Ghi `Snapshot` là **label space**, không phải nội dung bộ dữ liệu |
| 3.21 | `Signer Consent` | Ghi `Withdrawn Time` và hệ quả: chỉ tác động tới bản phát hành **sau đó** |
| 3.22 | `Audit Event` | Phân biệt `Actor` với `Actor Snapshot` — bản chụp lịch sử **không đổi theo** |

**Riêng Table 3.19 (`Sample`)** — chương đã chọn trình bày **theo nhóm thuộc tính**
(`Identity` / `Acquisition` / `Vocabulary` / `Signer` / `Sequence` / `Quality` /
`Storage` / `Processing` / `Provenance` / `Lifecycle`). Giữ nguyên cách này ở thân
chương; 42 trường chi tiết nằm ở Phụ lục C. Đây là quyết định trình bày đúng: một bảng
42 dòng trong thân chương là một bảng không ai đọc.

---

# PHẦN VI — THIẾT KẾ CHỨC NĂNG CHI TIẾT (Figure 3.19 – 3.26)

## FIGURE 3.19 — Sequence Diagram: Tenant-Scoped Authorization

**Loại:** sequence diagram · **Công cụ:** PlantUML

**Đường đời — sáu, theo đúng thứ tự:**
`User` · `Web Client` · `Application Backend` · `Authorization Service` ·
`PostgreSQL` · `Audit Store`

**Trình tự — bám đúng 12 bước của Algorithm 3.1:**

```
 1  User → Web Client            : request protected operation
 2  Web Client → Backend         : HTTPS request
 3  Backend                      : [1] Authenticate the user
 4  Backend → Authorization      : [2] Resolve the requested organizational scope
    alt [scope unavailable]      : [3] REJECT ──────────────────────────► ⊗
 5  Authorization → PostgreSQL   : [4] Resolve active membership
 6  Authorization → PostgreSQL   : [5] Resolve applicable role assignments
 7  Authorization                : [6] Evaluate required permission
    alt [permission absent]      : [7] REJECT ──────────────────────────► ⊗
 8  Backend → User               : [8] Require identity confirmation
    (chỉ khi hành động thuộc loại sensitive)
 9  Backend → PostgreSQL         : [9] Establish organizational context
                                       for the database transaction
10  Backend → PostgreSQL         : [10] Execute the operation
11  PostgreSQL                   : [11] Apply row isolation and
                                        referential constraints        ← self-message
12  Backend → Audit Store        : [12] Record audit evidence
```

**Ba yếu tố trình bày bắt buộc:**

1. Bước 9–11 đặt trong **một khung `group`** nhãn *"single transaction scope — context
   disappears when the transaction ends"*.
2. Bước 11 vẽ bằng **self-message** trên đường đời cơ sở dữ liệu, chữ đậm — đây là chỗ
   cách ly được cưỡng chế, và nó nằm ở **cơ sở dữ liệu**, không ở ứng dụng.
3. Bước 8 vẽ trong khung `opt` với guard `[action is sensitive]`.

**Ba nhánh `alt` phải có:**

| Nhánh | Kết quả | Ghi chú trên hình |
|---|---|---|
| No authenticated session | reject at step 3 | không tới được tầng phân quyền |
| Authenticated, **wrong tenant** | **zero rows returned** | chặn ở bước 11, **không** ở tầng ứng dụng |
| **Community tenant** | **same path, no shortcut** | trạng thái dự trữ **không** bỏ qua phép kiểm quyền |

**Điểm phải nhìn thấy được:** nhánh thứ ba. Chương ghi rõ: *"Community follows the same
permission process because it is represented as a tenant rather than as an unrestricted
global scope."*

**Caption:** *Figure 3.19. Sequence diagram: tenant-scoped authorization.*

---

## FIGURE 3.20 — Audit and Operational Logging Architecture

**Loại:** sơ đồ khối hai cột · **Công cụ:** draw.io

**Phải thể hiện — hai đường song song, KHÔNG giao nhau:**

```
      AUDIT PATH                          OPERATIONAL OBSERVABILITY PATH
      (durable evidence)                  (diagnostics)

   Business Action                      Application and Worker Logs
         ↓                                        ↓
   Audit Classification                  Log Collector
         ↓                                        ↓
   Structured Audit Store                Central Operational Log Store
         ↓                                        ↓
   Tenant or Platform Audit Review       Monitoring Dashboard
```

**Ghi chú gấp góc — chép nguyên công thức của chương, đặt ở cột trái:**

```
AuditEvent = (Actor, Scope, Action, Target, Time, Detail)
```

**Bảng so sánh đặt dưới hình — bắt buộc có, vì đây là thứ hình một mình không nói được:**

| | Audit Path | Operational Path |
|---|---|---|
| Purpose | **Durable evidence** for security and governance | Diagnostics, monitoring, troubleshooting |
| Examples | Membership changes · role changes · sensitive administrative actions · legal publication · consent changes · exports · destructive lifecycle actions | Service failures · worker errors · request processing · infrastructure events |
| Queried dimensions | Actor · Action · Scope · Target · Time — **structured fields** | Free-form, time-indexed |
| Retention driver | Governance requirement | Storage capacity |
| Must survive | **Yes** — including destructive tenant operations | Not required |

**Điểm phải nhìn thấy được:** hai đường **không thay thế được cho nhau**. Chương ghi:
*"The audit path should therefore remain separate from the operational observability
path."* Nếu hình vẽ chúng đổ vào cùng một kho, hình đã nói ngược với chương.

**Ghi chú thứ hai — đặt ở cột trái:** *"frequently queried dimensions remain structured
fields; less common contextual information is stored as structured event details"*.

**Caption:** *Figure 3.20. Audit and operational logging architecture.*

---

## FIGURE 3.21 — Sign-Class Management Workflow

**Loại:** activity diagram · **Công cụ:** PlantUML

**Phải thể hiện — chuỗi quyết định đúng theo gợi ý của chương:**

```
● start
↓ Submit sign-class definition
◇ [tenant context invalid] ──────────────────► Reject ──► ⊗
↓ [valid tenant]
◇ [language not in catalogue] ───────────────► Reject ──► ⊗
↓ [valid language]
◇ [dialect not valid for this tenant] ───────► Reject ──► ⊗
↓ [valid dialect]
◇ [region not valid] ────────────────────────► Reject ──► ⊗
↓ [valid region]
↓ Normalize label
↓ DUPLICATE CHECK on the full class identity
◇ [active duplicate exists] ─────────────────► Reject ──► ⊗
↓ [no duplicate]
↓ Create or Update Sign Class
◇ [registry state must advance] ─► Publish New Registry State ─┐
↓ [no version change needed]                                    │
↓ ◄─────────────────────────────────────────────────────────────┘
↓ Record audit evidence
◉ end
```

**Ghi chú gấp góc bắt buộc — chép nguyên hai công thức của chương:**

```
Identity(c) = (O_c , L_c , G_c , D_c , R_c)

An active duplicate exists when
    ∃ c′ : Identity(c′) = Identity(c) ∧ Active(c′) = 1
```

**Ghi chú thứ hai — ở nhánh merging:** *"class merging retains a mapping so that
references to previous definitions remain interpretable"* — nhấn rằng gộp lớp **không
xoá lịch sử**.

**Điểm phải nhìn thấy được:** phép kiểm trùng chạy trên **toàn bộ năm chiều identity**,
và bốn phép kiểm trước nó là kiểm **tính hợp lệ của từng chiều**. Bỏ chiều `Region` ra
khỏi phép kiểm trùng sẽ khiến hệ thống từ chối đúng những biến thể vùng miền mà nó cần
cho phép.

**Caption:** *Figure 3.21. Sign-class management workflow.*

---

## FIGURE 3.22 — Direct Camera Collection Sequence Diagram

**Loại:** sequence diagram · **Công cụ:** PlantUML

**Đường đời — bảy:**
`Data Contributor` · `Web Client` · `Landmark Extractor «client-side»` ·
`Application Backend` · `PostgreSQL` · `Task Queue` · `Background Worker`

**Ánh xạ đúng 14 bước của Algorithm 3.2:**

| Bước | Thông điệp trên hình |
|---|---|
| [1] Resolve organization and permission | Web Client → Backend → PostgreSQL |
| [2] Load the selected sign class | Backend → PostgreSQL |
| [3] Load signer and collection-session information | Backend → PostgreSQL |
| [4] Request camera access | Web Client → Data Contributor |
| [5] Extract landmarks for each frame | **`loop`** trên `Landmark Extractor` |
| [6] Build the landmark sequence | Web Client tự gọi |
| [7] Compute available acquisition indicators | Web Client tự gọi |
| [8] Allow the contributor to review the sequence | Web Client → Data Contributor |
| [9] Submit the sequence and metadata | Web Client → Backend |
| [10] Validate all organization-scoped relationships | Backend → PostgreSQL |
| [11] Create the managed sample | Backend → PostgreSQL |
| [12] Schedule additional processing when required | Backend → Task Queue |
| [13] Persist the derived artifact | Background Worker → Artifact Storage |
| [14] Update the processing state | Background Worker → PostgreSQL |

**Bốn yếu tố trình bày bắt buộc:**

1. **Khối `Landmark Extractor` mang nhãn `«client-side»`**, và có ghi chú:
```
d = 2 × 21 × 3 = 126 geometric dimensions per frame
X ∈ ℝ^(T × 126)
```
2. **Vòng lặp bước [5] phải có điều kiện thoát ghi bằng số:**
   `loop [until T frames captured or contributor stops]`.
3. **Ghi chú về giữ dữ liệu cục bộ**, chép nguyên tinh thần của chương: *"the local
   sequence is kept until the server confirms successful submission, so a temporary
   network failure does not immediately destroy the acquisition"*.
4. **Ranh giới đồng bộ / bất đồng bộ** vẽ bằng đường kẻ ngang giữa bước [12] và [13].

**Nhánh ngoại lệ (khung `alt`, nét đứt):** mất mạng ở bước [9] → **không có bản ghi nào
ở phía máy chủ**, dữ liệu vẫn ở phía máy khách và gửi lại được.

**Điểm phải nhìn thấy được:** **không có thông điệp nào mang video**. Đây là hệ quả
trực tiếp của việc trích điểm mốc chạy ở phía máy khách.

**Caption:** *Figure 3.22. Direct camera collection sequence diagram.*

---

## FIGURE 3.23 — Existing Recording Processing Sequence Diagram

**Loại:** sequence diagram · **Công cụ:** PlantUML

**Đường đời — bảy:**
`Data Contributor` · `Web Client` · `Application Backend` · `Source Storage` ·
`PostgreSQL` · `Task Queue` · `Background Worker`

**Ánh xạ đúng 9 bước của Algorithm 3.3:**

| Bước | Thông điệp | Ghi chú bắt buộc |
|---|---|---|
| [1] Validate permission and file type | Backend tự gọi | tệp không hợp lệ **không chặn** các tệp còn lại |
| [2] **Preserve the source recording** | Backend → Source Storage | **TRƯỚC mọi bước dẫn xuất** |
| [3] Record source metadata | Backend → PostgreSQL | |
| [4] Create the processing task | Backend → Task Queue | ranh giới đồng bộ / bất đồng bộ |
| [5] Extract the required representation | Worker tự gọi | **ở phía máy chủ** — khác Figure 3.22 |
| [6] Normalize the derived data | Worker tự gọi | |
| [7] Compute processing and quality information | Worker tự gọi | |
| [8] Persist the derived artifact | Worker → Artifact Storage | |
| [9] Update the sample state | Worker → PostgreSQL | |

**Ghi chú gấp góc bắt buộc — đặt ở bước [2], chép nguyên câu của chương:** *"the
original source is stored before derived processing begins so that extraction can be
repeated if subsequent processing fails"*.

**Điểm phải nhìn thấy được:** đặt cạnh Figure 3.22, hai hình phải cho thấy ngay
**bước trích đặc trưng nằm ở hai đường đời khác nhau** — máy khách ở hình trước, máy
chủ ở hình này. Và chỉ hình này có `Source Storage`, tức chỉ đường này **xử lý lại
được**.

**Caption:** *Figure 3.23. Existing recording processing sequence diagram.*

---

## FIGURE 3.24 — Sample Lifecycle State Diagram

**Loại:** state machine diagram · **Công cụ:** PlantUML

**Sáu trạng thái — chương yêu cầu *"at least acquisition, processing, usable data,
failure, soft deletion, and restoration"*:**

```
        ●
        ↓ [sample submitted]
   ┌──────────────┐
   │  ACQUIRED    │
   └──────┬───────┘
          ↓ [worker picks up the task]
   ┌──────────────┐
   │  PROCESSING  │──[processing error]──────────────┐
   └──────┬───────┘                                  ▼
          ↓ [processing complete]            ┌──────────────┐
   ┌──────────────┐                          │   FAILED     │
   │   USABLE     │                          └──────┬───────┘
   └──────┬───────┘                                 │
          ↓ [soft delete]                           │ [reprocess]
   ┌──────────────┐                                 │  ⚠ import path only
   │ SOFT-DELETED │◄──────────────────────┐         │
   └──────┬───────┘                       │         ▼
          │                               │   (back to PROCESSING)
          │ [restore] ────────────────────┘
          │           (back to USABLE)
          ↓ [permanent removal]
   ┌──────────────┐
   │   REMOVED    │   ← final state, no outgoing transition
   └──────┬───────┘
          ◉
```

**Bốn ghi chú bắt buộc:**

1. Cung `SOFT-DELETED → USABLE` là **khôi phục được** — đây là lý do dữ liệu vẫn được
   giữ ở trạng thái đã xoá mềm.
2. Cung `SOFT-DELETED → REMOVED` là **thao tác duy nhất chạm tới tạo tác trên lưu trữ**.
3. Cung `FAILED → PROCESSING` **chỉ tồn tại với đường import**, vì chỉ đường đó giữ bản
   nguồn. Ghi nhãn `[import path only]` trên cung.
4. `FAILED` **không sinh dữ liệu rác** — bản ghi mẫu vẫn tồn tại kèm lý do thất bại.

**Lưu ý trước khi vẽ — chương đã dặn:** *"The exact state names in the final diagram
should follow the production implementation."* Đối chiếu lại tên trạng thái với cột
trạng thái thật của bảng mẫu trước khi chốt nhãn trên hình.

**Caption:** *Figure 3.24. Sample lifecycle state diagram.*

---

## FIGURE 3.25 — Processing and Provenance Flow

**Loại:** infographic dòng chảy · **Công cụ:** draw.io

**Phải thể hiện — chuỗi bảy khối theo đúng gợi ý của chương:**

```
Source / Camera → Collection → Sample → Background Processing
     → Managed Artifact → Registry State → Export or Downstream Use
```

**Khối chú giải đặt dưới chuỗi — chép nguyên tuple provenance của chương:**

```
P = (Signer, Operator, Session, Class, Acquisition, Processing, Artifact, RegistryState)
```

**Ghi chú gấp góc bắt buộc — hai cái, và cả hai đều quan trọng:**

1. Cạnh tuple: *"Not every historical sample contains all elements of this tuple.
   Missing provenance remains **unknown** rather than being inferred from unrelated
   metadata."*
2. Cạnh khối `Registry State`, vẽ **hai dòng, dòng dưới nét đứt**:
```
   J → R_v                                        ← implemented
       identifies the label space used by a job

   DatasetVersion → { SampleRevision_1 … n }      ← «target design»
       would identify the complete immutable sample set
```

**Điểm phải nhìn thấy được:** ranh giới giữa **cái đã ghim được** (không gian nhãn) và
**cái chưa** (nội dung bộ dữ liệu). Chương nói thẳng *"That relationship remains part of
the target design and is not represented as an existing physical relationship."* — hình
phải nói đúng chừng đó, không hơn.

**Caption:** *Figure 3.25. Processing and provenance flow.*

---

## FIGURE 3.26 — Authoritative Data Verification and Synchronization

**Loại:** sequence diagram hoặc activity hai làn · **Công cụ:** PlantUML

**Hai làn:**
`Authoritative Artifact Publisher` (giữ khoá riêng) ·
`Subsystem` (chỉ có khoá công khai được tin cậy)

**Phải thể hiện:**

```
LÀN 1 — PUBLISHER
  ● → Build artifacts → Compute content hash for each artifact
    → Write manifest → SIGN the manifest → Publish → ⊗

LÀN 2 — SUBSYSTEM  (at startup and on demand)
  ● → Retrieve the published artifacts
  ↓ Recompute content hashes and compare with the manifest
  ◇ [H(f_i) ≠ h_i] ─────────────────────► FAIL CLOSED ──► ◉
  ↓ [all hashes match]
  ↓ Verify the manifest signature
  ◇ [Verify(pk, M, σ) = False] ─────────► FAIL CLOSED ──► ◉
  ↓ [signature valid]
  ↓ Check that the signing key is an accepted authority
  ◇ [key not trusted] ──────────────────► FAIL CLOSED ──► ◉
  ↓ [trusted authority]
  ↓ Synchronize — additive only, never destructive
  ↓ Allow dependent components to start
  ◉
```

**Ghi chú gấp góc bắt buộc — chép nguyên hai công thức của chương:**

```
H(f_i) = h_i                    content integrity
Verify(pk, M, σ) = True         signature verification
```

**Ghi chú thứ hai — đặt ở ba điểm FAIL CLOSED, chép nguyên câu của chương:** *"A
reference artifact that cannot be verified is not silently replaced with another
unverified version."*

**Điểm phải nhìn thấy được:** **ba điểm dừng là ba phép kiểm khác nhau** và không thay
thế được cho nhau — toàn vẹn nội dung · tính hợp lệ của chữ ký · **thẩm quyền của khoá
ký**. Chương phân biệt hai vế đầu rõ ràng: *"Hash verification detects content
modification, while signature verification establishes that the artifact was signed by
an accepted authority."* Vế thứ ba là chỗ dễ bỏ sót nhất — một chữ ký hợp lệ về mật mã
vẫn có thể do một khoá không có thẩm quyền tạo ra.

**Caption:** *Figure 3.26. Authoritative data verification and synchronization.*

---

# PHẦN VII — CÀI ĐẶT VÀ TRIỂN KHAI (Figure 3.27 – 3.28)

## FIGURE 3.27 — Installation and Startup Procedure

**Loại:** activity diagram · **Công cụ:** PlantUML

**Phải thể hiện — tám bước theo đúng thứ tự chương đưa, mỗi bước có điểm kiểm:**

```
● start
↓ [1] Host Preparation
      persistent storage · required secrets
◇ [prerequisites missing] ──────────────────────► STOP ──► ◉
↓ [2] Persistent Services
      PostgreSQL · Redis
◇ [service unreachable] ────────────────────────► STOP ──► ◉
↓ [3] Database Migration
↓ [4] Database Role Provisioning
      📎 the application role is separated from schema-management privileges
         so that ordinary requests cannot redefine database isolation rules
↓ [5] Authoritative Artifact Verification              ← xem Figure 3.26
◇ [verification fails] ─────────────────────────► STOP ──► ◉
↓ [6] Backend and Worker
↓ [7] Frontend and Gateway
↓ [8] Health Verification
      service health · required storage access
◇ [health check fails] ─────────────────────────► report failing component ──► ◉
◉ system ready
```

**Ba ghi chú bắt buộc:**

1. Ở bước [4], chép nguyên câu của chương về tách quyền — đây là quyết định thiết kế,
   không phải chi tiết vận hành.
2. Ở bước [5]: *"reference artifacts are verified before dependent application
   components consume them"* — nhấn quan hệ **thứ tự**, không phải quan hệ gọi.
3. Ở góc hình: *"Detailed commands, configuration values, and environment variables are
   provided in Appendix E."*

**Không đưa vào hình:** lệnh shell, biến môi trường, giá trị cấu hình. Chương đã nói rõ
chúng thuộc Phụ lục E.

**Caption:** *Figure 3.27. Installation and startup procedure.*

---

## FIGURE 3.28 — Deployment Diagram

**Loại:** deployment diagram UML, **dạng nhóm** · **Công cụ:** draw.io

**Phải thể hiện — MỘT nút vật lý duy nhất, container gom thành tám nhóm:**

```
╔═══ Linux Host — Docker Compose ═══════════════════════════════════════╗
║                                                                        ║
║  ┌─ Web and Gateway ──────────┐   ┌─ Integrity Initialization ──────┐ ║
║  │ Gateway  ·  Frontend       │   │ Authoritative-data init         │ ║
║  └────────────────────────────┘   │ ⚠ runs BEFORE dependent services│ ║
║                                    │   nét đứt — one-shot container  │ ║
║  ┌─ Core Application ─────────┐   └─────────────────────────────────┘ ║
║  │ Application Backend        │                                        ║
║  └────────────────────────────┘   ┌─ Downstream Services ───────────┐ ║
║                                    │ Training  ·  Recognition        │ ║
║  ┌─ Data Services ────────────┐   │ nét đứt — «downstream»          │ ║
║  │ PostgreSQL  ·  Redis       │   └─────────────────────────────────┘ ║
║  └────────────────────────────┘                                        ║
║                                    ┌─ Observability ─────────────────┐ ║
║  ┌─ Background Processing ────┐   │ Metrics · Dashboards            │ ║
║  │ Worker  ·  Scheduler       │   │ Log store · Log collector       │ ║
║  └────────────────────────────┘   └─────────────────────────────────┘ ║
║                                                                        ║
║  ┌─ Backup ───────────────────┐                                        ║
║  │ Database backup            │                                        ║
║  └────────────────────────────┘                                        ║
╚════════════════════════════════════════════════════════════════════════╝

PERSISTENT VOLUMES — vẽ TÁCH RIÊNG, ngoài khung host
   Database data · Feature artifacts · Source recordings · Backups · Logs
```

**Bốn quy tắc vẽ:**

1. **Tổng 15 dịch vụ** — khớp câu của chương *"The deployment currently defines 15
   services"*. Đếm lại trên hình trước khi chốt.
2. Container khởi tạo toàn vẹn vẽ **nét đứt** vì nó chạy một lần rồi thoát; **mũi tên
   phụ thuộc khởi động** tới `Core Application` và `Background Processing` vẽ **khác
   kiểu** với mũi tên gọi thông thường.
3. **Persistent volumes vẽ tách hẳn** khỏi khung container — chúng sống sót qua việc
   dựng lại container.
4. Nhóm `Downstream Services` vẽ nét đứt, thống nhất với Figure 3.2 và Figure 3.11.

**Ghi chú gấp góc bắt buộc — chép nguyên câu của chương, vì đây là chỗ dễ hiểu nhầm
nhất trong cả chương:**

> *"This container separation does not mean that the business system is implemented as
> a set of independent microservices. The primary business logic remains organized
> within the main application backend."*

**Không đưa vào hình:** quan hệ container chi tiết, mạng, volume theo tên, thứ tự phụ
thuộc đầy đủ, giá trị cấu hình. Chương đã nói rõ chúng thuộc Phụ lục E.

**Caption:** *Figure 3.28. Deployment diagram.*

---

# PHẦN VIII — DANH SÁCH KIỂM TRƯỚC KHI NỘP

*Bảng VIII-1: Danh sách kiểm cho toàn bộ 28 hình*

| # | Điểm kiểm | Áp cho hình |
|---|---|---|
| 1 | Đọc được khi in **trắng đen**; không dùng màu để phân biệt | tất cả |
| 2 | Nhãn trong hình **trùng từng chữ** với thuật ngữ của chương | tất cả |
| 3 | `Workspace` / `Project` mang nhãn **`«partial»`** | 3.6, 3.13, 3.14, 3.15 |
| 4 | `Dataset Version` / `Sample Revision` vẽ **nét đứt** + `«target design»` | 3.10, 3.13, 3.25 |
| 5 | **Community vẽ như một tenant**, không phải mặt phẳng ngoài | 3.16, 3.19 |
| 6 | Ba bảng `community_*` ghi rõ là **System Catalogue** | 3.16 |
| 7 | `Signer` và `Registered User` là **hai actor tách biệt** | 3.5, 3.9, 3.13 |
| 8 | **Hai cạnh khác nhau** từ `Sample` tới participant và operator | 3.13, 3.17 |
| 9 | Hai đường thu vẽ tách bạch; **bước trích đặc trưng ở hai chỗ khác nhau** | 3.3, 3.9, 3.22, 3.23 |
| 10 | **Không vẽ** `Background Worker` làm actor trên sơ đồ use case | 3.9 |
| 11 | **Không vẽ** khoá ngoại từ `raw_uploads` tới `samples` | 3.17 |
| 12 | **Không vẽ** `workspace_members` / `project_members` | 3.15 |
| 13 | Khoá ngoại ghép **ghi cặp cột trên cạnh** | 3.15, 3.17, 3.18 |
| 14 | `User Consent` và `Signer Consent` vẽ **tách bạch** | 3.13, 3.18 |
| 15 | Mọi vòng lặp có **điều kiện thoát ghi bằng số** | 3.22 |
| 16 | Mọi nhánh rẽ có **guard trong ngoặc vuông** | 3.3, 3.21, 3.26, 3.27 |
| 17 | `Platform Administrator` **không có cung kế thừa** tới `Registered User` | 3.5 |
| 18 | Con số trên hình khớp con số trong chương | 3.12, 3.14, 3.28 |

*Bảng VIII-2: Đối chiếu con số — hình phải khớp chương*

| Con số | Giá trị | Xuất hiện ở |
|---|:--:|---|
| Bảng vật lý | **59** (+ 1 view) | §3.4.1, §3.4.2 · Figure 3.14 |
| Bảng thuộc tổ chức | **36** | §3.4.2 · Figure 3.12 |
| Bảng có Row-Level Security | **35** | §3.4.2 · Figure 3.12, 3.15–3.18 |
| Khoá ngoại | **123** | §3.4.2 |
| Khoá ngoại ghép | **24** | §3.3.2c, §3.4.2 · Figure 3.12, 3.17 |
| Trigger | **6** | §3.4.2 · Figure 3.15 (4) + Figure 3.18 (2) |
| Dịch vụ triển khai | **15** | §3.6.2 · Figure 3.28 |
| Chiều đặc trưng mỗi khung | **126** | §3.5.3 · Figure 3.22 |

**Một lưu ý cuối, quan trọng hơn mười tám điểm trên:** nếu lược đồ hoặc mã nguồn thay
đổi sau ngày 18/08/2026, **đếm lại trước khi vẽ**. Một hình mang con số cũ trông giống
hệt một hình mang con số đúng — và đó chính là lý do nó nguy hiểm.
