# Community Data Commons — thiết kế, CHƯA triển khai

> Chốt 2026-08-06. Trạng thái: **0 dòng mã**. Tài liệu này tồn tại để (a) giành
> lại đúng nghĩa của chữ "Community", (b) chốt các quyết định chính sách trước
> khi có dòng mã đầu tiên, (c) làm đóng góp thiết kế cho luận văn.

## 0. Sai lầm đã sửa

Ba bảng `community_dialects`, `community_profiles`, `community_versions` **không
phải** Community. Chúng là **System Catalog**: mẫu cấu hình do hệ thống quản lý
(phương ngữ nào tồn tại, profile nhận dạng nào tồn tại) để clone cho tenant mới.
Chúng không chứa video, landmark, consent record, attribution hay licence.

Tệ hơn, 8 endpoint quản trị catalog từng được gắn ở `/vocabulary/community` — vừa
gọi sai tên, vừa **chiếm mất namespace** mà commons thật sẽ cần.

Đã sửa (2026-08-06):

| | trước | sau |
|---|---|---|
| endpoint | `/vocabulary/community/*` | `/vocabulary/catalog/*` |
| router | `community_router` | `catalog_router` |
| service | `seed_community`, `community_snapshot`, `publish_community_version`, `clone_community_to_tenant`, … | `seed_system_catalog`, `system_catalog_snapshot`, `publish_catalog_version`, `clone_catalog_to_tenant`, … |
| bảng vật lý | `community_*` | **giữ nguyên** |

Bảng vật lý giữ tên cũ có chủ đích: đổi tên bảng là **migration cần cửa sổ
deploy**, còn tên domain thì phải hết sai **ngay**. Đừng "sửa" tên hàm ngược lại
cho khớp tên bảng.

Ba guard trong `backend/tests/test_system_catalog_api.py` canh ranh giới này:

- `test_catalog_holds_configuration_only_never_contributed_data` — fail nếu bảng
  catalog mọc cột kiểu `storage_key` / `consent_id` / `contributor_id`;
- `test_community_is_a_reserved_tenant_under_the_same_rules` — Community LÀ một
  tenant dự trữ (§10 đã đảo 12/08/2026), và nó phải chịu đúng RLS / RBAC /
  cách ly tenant như mọi tenant khác;
- `test_the_catalog_router_no_longer_squats_on_the_community_namespace`.

## 1. Ba lớp độc lập

```
┌────────────────────────┐
│     System Catalog     │  cấu hình do hệ thống quản lý
│  dialect / profile     │  KHÔNG có mẫu nghiên cứu
└───────────┬────────────┘
            │ clone CẤU HÌNH (một lần)
            ▼
┌──────────────────────┐        ┌─────────────┐
│       Tenant         │        │ Individual  │
│ Workspace / Project  │        │ contributor │
└──────────┬───────────┘        └──────┬──────┘
           │ contribution request      │ contribution
           └────────────┬──────────────┘
                        ▼
              ┌──────────────────────┐
              │ Community Submission │  pending review
              └──────────┬───────────┘
                         │ approve
                         ▼
              ┌──────────────────────┐
              │ Community Data       │  immutable releases
              │ Commons              │
              └──────────┬───────────┘
                         │ licensed access GRANT (không clone)
                ┌────────┴────────┐
                ▼                 ▼
          Researchers          Tenants
```

**Ranh giới quan trọng nhất trong toàn bộ tài liệu này:**

```
System catalog   → clone cấu hình
Community data   → grant quyền đọc có điều kiện, KHÔNG clone file
```

## 2. Vì sao không clone dữ liệu Community vào tenant

Clone file là mô hình đúng cho **cấu hình** và sai cho **dữ liệu**. Nếu clone:

- không biết tenant đang giữ bản nào;
- không thu hồi được quyền truy cập;
- không cập nhật được điều khoản;
- mất dấu nguồn gốc;
- tenant hiểu nhầm bản clone là tài sản của mình;
- một file tồn tại hàng chục bản không kiểm soát.

Thay vào đó: **Community sở hữu canonical object, tenant nhận access grant.**

## 3. Trạng thái dữ liệu tenant

Một file vừa tải lên **không** tự động thành Community data.

```
PRIVATE  →  TENANT_SHARED  →  COMMUNITY_CANDIDATE  →  COMMUNITY_PUBLISHED
```

Quy trình đóng góp, không phải một nút "Share":

```
DRAFT → SUBMITTED → UNDER_REVIEW → CHANGES_REQUESTED
                                 → APPROVED → PUBLISHED
                                            → SUSPENDED / WITHDRAWN / REVOKED
```

Kiểm duyệt gồm **ba** loại kiểm tra tách biệt: quyền/consent, chất lượng dữ liệu,
và điều phối cộng đồng. Trộn ba cái vào một bước duyệt là cách chắc chắn để một
mẫu thiếu consent lọt qua vì "chất lượng tốt".

## 4. Chính sách sử dụng — bốn loại, không phải một cờ `is_commercial`

| loại | ví dụ | mặc định |
|---|---|---|
| A — nghiên cứu phi thương mại | luận văn, bài báo, benchmark, giảng dạy | **cho phép** |
| B — nội bộ tổ chức | prototype, kiểm thử, đánh giá triển khai | cho phép, cấm bán/chia sẻ lại |
| C — thương mại | model cho sản phẩm trả phí, API tính phí | **phải xin giấy phép riêng** |
| D — bán lại / tái phân phối | bán, cho thuê, cấp phép lại, mirror công khai | **cấm** |

**"Không được bán dữ liệu" là quá hẹp.** Tenant có thể không bán file mà vẫn trục
lợi: bán dataset đã đổi tên, bán bản đã làm sạch, bán feature/`.npz`, bán quyền
truy cập API, gộp với dữ liệu riêng rồi bán, huấn luyện model thương mại, bán
embedding, dùng để quảng bá sản phẩm.

Điều khoản phải nói rõ:

> Commercial use includes training, fine-tuning, evaluating, or operating a model
> as part of a paid product, paid API, licensed software, advertising service, or
> revenue-generating activity.

Nếu chỉ ghi "không được bán dữ liệu", họ vẫn lập luận được rằng họ bán **model**
chứ không bán dataset.

## 5. Giấy phép — hai tầng

Một giấy phép dữ liệu **không** tự giải quyết hết các lớp quyền của video ngôn
ngữ ký hiệu: quyền CSDL, quyền tác giả, **quyền hình ảnh của người biểu diễn**,
quyền riêng tư, sự đồng ý tham gia nghiên cứu, điều khoản nền tảng.

| | vì sao không đủ |
|---|---|
| CC0 | từ bỏ tối đa quyền — cho phép cả thương mại. Mâu thuẫn trực tiếp với mục tiêu |
| ODbL | attribution + share-alike, **không** cấm thương mại |
| CC BY-NC 4.0 | gần nhất, nhưng "phi thương mại" cần diễn giải, không xử lý consent/quyền hình ảnh, không nói rõ model có phải bản phái sinh không |

**Phương án: hai tầng.**

```
Community dataset access is governed by:
  1. The applicable content licence (ví dụ CC BY-NC 4.0); and
  2. The CTU-SignBridge Community Data Use Agreement.
```

**Không** sửa văn bản pháp lý của Creative Commons rồi vẫn gọi nó là CC BY-NC.

Giấy phép CC nhìn chung **không thể đơn phương thu hồi** với người đã nhận hợp lệ
và tiếp tục tuân thủ. Consent form phải nói rõ điều này trước khi ai đó ký.

> Đây chưa phải tư vấn pháp lý. Trước khi công bố dataset thật, văn bản phải được
> trường hoặc người có chuyên môn pháp lý xem xét.

## 6. Licence profile theo từng release

Không áp một giấy phép duy nhất cho toàn bộ commons.

| mức | tải xuống | huấn luyện | thương mại | tái phân phối |
|---|---|---|---|---|
| Public Research | có | có | không | có điều kiện |
| Controlled Research | có điều kiện | có | không | không |
| Platform Only | **không** | có | không | không |
| Restricted | không / giới hạn | có điều kiện | không | không |
| Commercial Agreement | theo hợp đồng | có | có | thường không |

Với video VSL **có khuôn mặt và danh tính**: nghiêng về `Controlled Research`
hoặc `Platform Only`, không cho tải tự do.

## 7. Quyền theo từng loại đầu ra

Một dataset sinh ra nhiều thứ, và một cờ duy nhất không mô tả nổi:

```
Raw video → Frames → Landmarks → NPZ features → Model → Prediction service
```

| đối tượng | tạo | xuất | bán |
|---|---|---|---|
| video gốc | — | có điều kiện | không |
| frame trích xuất | có | không | không |
| keypoint / npz | có | có điều kiện | không |
| annotation mới | có | có điều kiện | không |
| model nghiên cứu | có | có | không |
| bài báo / thống kê tổng hợp | có | có | có thể |
| model thương mại | không | không | không, trừ thoả thuận riêng |

## 8. Bảng đề xuất

```
community_datasets           (id, slug, name, governance_status, steward_user_id,
                              default_license_id, access_policy_id)
community_dataset_releases   (id, dataset_id, version, content_hash, manifest_json,
                              license_snapshot_json, consent_policy_snapshot_json,
                              item_count, published_at, published_by, status)
community_dataset_items      (release_id, community_object_id, source_contribution_id,
                              source_sample_id, attribution_id, consent_record_id, checksum)
community_objects            (object_id, storage_key, content_hash, media_type,
                              size_bytes, access_level, license_id)
community_contributions      (submission_id, source_tenant_id, source_workspace_id,
                              source_project_id, submitted_by, contribution_type,
                              proposed_license, declared_rights_holder, consent_basis,
                              contains_personal_data, contains_identifiable_faces,
                              commercial_use_allowed, redistribution_allowed,
                              review_status, reviewed_by, review_notes)
community_access_grants      (id, tenant_id, release_id, purpose_code,
                              can_view_metadata, can_stream, can_download, can_derive,
                              can_train, can_export_model, can_use_commercially,
                              can_redistribute, expires_at, accepted_terms_version,
                              accepted_by, accepted_at, revoked_at)
community_usage_events       (id, tenant_id, user_id, release_id, object_id, action,
                              project_id, purpose_code, occurred_at, ip_hash, request_id)
project_dataset_bindings     (project_id, source_type TENANT|COMMUNITY,
                              tenant_dataset_id, community_release_id, grant_id,
                              attached_by, attached_at)
```

Mặc định của grant:

```
can_download         = false
can_train            = true
can_derive_features  = true
can_redistribute     = false
can_use_commercially = false
```

Release đã công bố **không sửa trực tiếp**: `v1.0 → v1.1 → v2.0`.

## 9. Kiểm tra khi project đọc dữ liệu Community

Sáu câu hỏi, không phải một:

1. User có quyền trong tenant không?
2. User có quyền trong workspace/project không?
3. Tenant còn grant với release này không?
4. Mục đích của project có khớp `purpose_code` của grant không?
5. Grant đã hết hạn hoặc bị thu hồi chưa?
6. Action hiện tại có nằm trong grant không?

Không phải `if user.is_authenticated: allow()`.

## 10. Community LÀ một tenant dự trữ — và vì sao điều đó an toàn

> **Đảo quyết định, 12/08/2026.** Bản trước của mục này viết: *"Không triển khai
> `tenant_id = 'COMMUNITY_TENANT'`"*. PDM v5 làm ngược lại, và quyết định v5
> được giữ. Mục này ghi lại cả hai vế: vì sao đảo, và rủi ro cũ được xử ra sao.

Community được triển khai như một **tenant dự trữ**:

```
tenant_id           = 'community'
tenant_type         = 'COMMUNITY'      -- phân biệt với ORGANIZATION
is_system_reserved  = TRUE             -- nhãn, KHÔNG phải quyền
```

Kèm một chỉ mục duy nhất: `uq_tenants_single_community` — nhiều nhất **một**
tenant cộng đồng tồn tại.

### Vì sao đảo

Cách kia — Community là một mức phạm vi thứ năm bên cạnh
SYSTEM/TENANT/WORKSPACE/PROJECT — đòi một trục phân quyền song song: domain
riêng cho Casbin, bảng thành viên riêng, chuỗi thống trị phạm vi riêng, RLS
riêng. Bốn cơ chế nhân đôi, và mỗi cái là một chỗ để hai nhánh trôi khỏi nhau.

Là một tenant, Community **thừa hưởng nguyên** bốn lớp đã có và đã được kiểm:
RLS, khoá ngoại ghép, Casbin, mã hành động. Không có đường vòng nào cần viết,
nên cũng không có đường vòng nào để quên.

### Rủi ro §10 cũ nêu, và câu trả lời cho từng cái

Bản cũ nêu hai rủi ro cụ thể. Cả hai đều thật, và không cái nào tự biến mất chỉ
vì đặt tên cột là `tenant_type`.

**Rủi ro 1 — "mọi đường *user thuộc tenant này thì cho qua* âm thầm trở thành
đường vào commons".**

Đây là rủi ro thật và nó KHÔNG được giải quyết bởi `tenant_type` hay
`is_system_reserved`. Nó được giải quyết bằng một quy tắc về mã:

> Tư cách thành viên **không bao giờ** là điều kiện đủ để cho qua. Mọi phép
> kiểm phải hỏi một QUYỀN cụ thể, không hỏi "có phải thành viên không".

Đó chính là điều `app/authorization/` tồn tại để cưỡng chế: `authorize()` nhận
một mã quyền, không nhận một tenant. `access_gate._has_any_tenant_grant()` cũng
vậy — nó hỏi "có grant không", và tư cách thành viên đơn thuần **không** làm nó
trả `True`.

Cưỡng chế: `test_membership_alone_is_never_enough_in_the_community_tenant`.

**Rủi ro 2 — "mọi system admin nghiễm nhiên có quyền tenant-admin trên dữ liệu
người khác đóng góp".**

Đúng, và đó là hệ quả của thống trị phạm vi (§3 `docs/03-security/AUTHORIZATION.md`):
`platform_administrator` cầm mọi quyền ở mọi phạm vi, nên nó cầm cả quyền trong
Community. Chấp nhận điều đó là chấp nhận rằng người vận hành nền tảng có toàn
quyền kỹ thuật — vốn đã đúng với mọi tenant khác, và mọi cơ sở dữ liệu.

Cái KHÔNG chấp nhận là nó xảy ra **không dấu vết**. Nên hàng rào ở đây là kiểm
toán chứ không phải phân quyền: mọi thao tác nhạy cảm ghi `audit_log`, và các
quyền định đoạt (`platform.tenant.purge`, `platform.role.manage`) còn đòi mã
hành động cá nhân.

### `is_system_reserved` là NHÃN, không phải QUYỀN

Cột đó nói "đừng xoá tenant này, nó thuộc nền tảng". Nó **không** được đọc bởi
bất kỳ đường phân quyền nào, và không bao giờ được phép trở thành một đường
vòng — không có `if is_system_reserved: return True` ở đâu cả.

Cưỡng chế: `test_is_system_reserved_is_never_read_by_authorisation`.

### Hai vai của Community

`community_member` và `community_curator` là role dựng sẵn ở phạm vi **TENANT**,
bị ghim vào `tenant_type = 'COMMUNITY'` bằng `roles.tenant_type_constraint`.
Trigger `ct_role_assignments_scope` từ chối nếu ai đó gán chúng trong một tenant
tổ chức — nơi tập quyền được thiết kế cho không gian dùng chung sẽ mang ý nghĩa
khác hẳn.

Chúng KHÔNG phải một mức phạm vi mới. Community là một tenant, nên vai trong nó
là vai TENANT.

### Cái vẫn KHÔNG được làm

Đảo §10 không mở đường cho những thứ nó cấm vì lý do khác:

* Bảng catalog vẫn **chỉ chứa cấu hình**, không chứa dữ liệu đóng góp
  (`test_catalog_holds_configuration_only_never_contributed_data`).
* Router catalog vẫn không chiếm không gian tên `/community`
  (`test_the_catalog_router_no_longer_squats_on_the_community_namespace`).
* Dữ liệu đóng góp vào commons vẫn đi kèm consent và licence riêng (§11, §12).
  Là một tenant không làm nó thành sở hữu của nền tảng.

## 11. Sở hữu — giữ quyền, cấp phép cho nền tảng

Ba mô hình; **khuyến nghị mô hình 2**:

```
Contributor giữ quyền sở hữu
  → cấp cho CTU-SignBridge một licence
    → CTU-SignBridge cấp phép lại (có điều kiện) cho tenant/nhà nghiên cứu
```

Mô hình 1 (chuyển hẳn quyền cho nền tảng) mạnh nhưng phức tạp pháp lý và không
hợp với nền tảng cộng đồng. Mô hình 3 (nền tảng chỉ là trung gian kỹ thuật, ai
dùng phải xin từng người đóng góp) không vận hành nổi khi số người đóng góp tăng.

## 12. Bốn lớp hạn chế bán lại

**Không có giải pháp kỹ thuật nào bảo đảm tuyệt đối** rằng người đã thấy hoặc tải
dữ liệu sẽ không sao chép. Phải kết hợp:

1. **Pháp lý** — Data Use Agreement, cấm bán/cấp phép lại, nghĩa vụ xoá khi hết
   hạn, quyền đình chỉ.
2. **Truy cập** — duyệt tenant/project, khai báo mục đích, grant có hạn, signed
   URL, không cho tải nếu không cần.
3. **Truy vết** — audit log bất biến, ai đọc file nào, watermark/fingerprint trên
   bản xuất, `export_id` trong manifest.
4. **Giảm thiểu dữ liệu** — ưu tiên streaming, đưa keypoint thay vì video khi đủ,
   pseudonymize signer, tách consent record khỏi sample.

Mức mạnh nhất: **bring the compute to the data, not the data to the tenant** —
tenant gửi job huấn luyện tới nơi chứa dữ liệu. Future Work.

## 13. Thu hồi — bốn việc khác nhau

Đừng gộp: thu hồi **quyền truy cập** ≠ gỡ khỏi **release mới** ≠ **xoá khỏi
storage** ≠ thu hồi **giấy phép đã cấp**.

Không được hứa "xoá là biến mất hoàn toàn". Với dữ liệu đã phát hành theo giấy
phép không thể thu hồi, hệ thống không bảo đảm được mọi bản sao biến mất. Consent
form phải nói rõ giới hạn này **trước** khi người tham gia ký.

## 14. Vai trò

`community_contributor` · `community_reviewer` · `community_steward` ·
`community_auditor` · `system_admin`

Nguyên tắc quan trọng nhất: **quyền quản trị hạ tầng không đồng nghĩa với quyền
khai thác dữ liệu.** `system_admin` vận hành hệ thống, không nghiễm nhiên có
quyền tải mọi video.

Reviewer không tự xuất bản (nguyên tắc bốn mắt). Auditor chỉ đọc log.

## 15. Phạm vi cho luận văn hiện tại

> Sách nộp **13/08/2026**. Phần dưới là ranh giới thực tế, không phải mong muốn.

**Không triển khai trong luận văn này** — đây là chương thiết kế / Future Work:
hợp đồng điện tử, licensing thương mại, revenue sharing, secure compute
environment, watermark động, phát hiện dữ liệu bị bán lại, machine unlearning,
consent revocation propagation, institutional review workflow, license
compatibility engine.

**Đã làm được và nên tính điểm ngay bây giờ:**

- tách bạch System Catalog vs Community Data Commons (tài liệu này + rename +
  3 guard test);
- 12 khoá ngoại `tenant_id` → `tenants` (nền cho cô lập tenant ở tầng DB);
- artifact registry với version bất biến + content hash + pin.

**Lõi được chấm vẫn là cô lập tenant trên hai mặt phẳng dữ liệu** (`workspace_id`
+ RLS ở DB, phân vùng file/cloud ở storage). Tính tới 2026-08-06: **0 bảng bật
RLS, 0 policy, 0 cột `workspace_id`**. Đó mới là việc phải làm tiếp, không phải
commons này.

## 16. Chính sách một câu

> Dữ liệu Community mặc định được dùng cho nghiên cứu, giáo dục và các hoạt động
> phi thương mại. Người sử dụng không được bán, cấp phép lại, tái phân phối, cung
> cấp quyền truy cập có thu phí, hoặc thương mại hoá dataset, feature, model hay
> dịch vụ tạo ra từ dữ liệu Community nếu chưa có thoả thuận riêng.

Mục tiêu **không** phải "không ai được tạo ra giá trị", mà là: không tenant nào
chiếm dụng tài sản cộng đồng, bán lại hoặc độc quyền khai thác mà không có sự cho
phép và cơ chế hoàn trả lợi ích phù hợp.
