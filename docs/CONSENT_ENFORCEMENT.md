# Thực thi phạm vi đồng thuận

> Trạng thái: **đã hiện thực** 2026-08-09. Mã: `backend/app/consent_gate.py`,
> `backend/app/cli/consent_snapshot.py`. Test: `backend/tests/test_consent_gate.py`
> (43 trường hợp).

## 1. Vấn đề mà nó sửa

Bảng `signer_consents` có từ lược đồ v3.4 và được thiết kế đúng: ba mức phạm vi
tăng dần, `withdrawn_at`, người ghi nhận, bằng chứng, tên người giám hộ, và một
ràng buộc "một đồng thuận còn hiệu lực cho mỗi cặp người-ký × mức".

Cho tới 2026-08-09, **toàn bộ mã đọc bảng đó chỉ có ba nơi**: lớp ghi CSDL
(`storage/metadata_db.py`), khai báo RLS (`storage/rls.py`), và tác vụ xoá tenant
(`tenant_lifecycle.py`). Không nơi nào ở đường xuất dữ liệu, đường huấn luyện,
đường tạo split, hay đường đóng gói phát hành nghiên cứu.

Hệ quả, đo được chứ không suy đoán:

- một người ký chỉ đồng ý `internal_training` thì dữ liệu của họ **vẫn** đi vào
  bản phát hành nghiên cứu;
- một người đã rút đồng thuận thì `withdrawn_at` được ghi và **không có gì xảy
  ra tiếp theo**.

Ghi nhận đồng thuận mà không thực thi thì **tệ hơn không ghi**: nó tạo ra hồ sơ
trông như đã tuân thủ, trong khi hành vi thật của hệ thống bỏ qua hoàn toàn.

## 2. Quy tắc

Ba mức là một cái **thang**, không phải ba ô đánh dấu rời nhau:

```
internal_training  <  research_release  <  public_library
```

Đồng ý mức cao bao hàm mức thấp. Đồng ý mức thấp **không** kéo theo mức cao.

Với mỗi mẫu, hỏi người ký của nó:

| Tình trạng người ký | Kết quả |
|---|---|
| Có đồng thuận còn hiệu lực | Cho phép tới đúng mức cao nhất đã cấp |
| Từng có, nay đã rút hết | **Chặn ở MỌI mức**, kể cả nội bộ |
| Chưa từng có dòng nào | Chỉ `internal_training`, và chỉ khi bật cờ kế thừa |
| Mẫu không có `signer_id` | Như trên — nội bộ thì kế thừa, phát hành thì **không bao giờ** |

### Vì sao có cờ kế thừa

Đo trên dữ liệu sản xuất 2026-08-09: **3.860 mẫu, 0 dòng** trong
`signer_consents`, và **56,6%** số mẫu không có `signer_id`. Thực thi chặt tuyệt
đối ở mọi mức sẽ loại 100% kho dữ liệu ra khỏi cả huấn luyện nội bộ — tức là làm
hỏng hệ thống đang chạy để sửa một lỗ hổng về *phát hành*.

Ranh giới đặt ở chỗ nó thật sự quan trọng: **nội bộ thì kế thừa, ra ngoài thì
phải xin phép.** Dữ liệu đã thu chính là để huấn luyện nội bộ; đưa nó vào một
bản phát hành nghiên cứu hay thư viện công khai là một **mục đích mới**, và mục
đích mới cần đồng thuận mới.

Cái mà cờ kế thừa **không** che: một lần rút đồng thuận. Người từng ký rồi rút
thì bị chặn ở mọi mức bất kể cờ. Đây là lý do `SignerConsent.has_any_record` tồn
tại — không có nó, "đã rút" và "chưa từng ký" trông giống hệt nhau.

```bash
CONSENT_GRANDFATHER_INTERNAL=1   # mặc định
CONSENT_GRANDFATHER_INTERNAL=0   # chặt tuyệt đối; hôm nay = tập huấn luyện RỖNG
```

### Mẫu vô danh không bao giờ ra khỏi nhà

Đây là **tính chất**, không phải hạn chế: không truy được về ai thì không chứng
minh được đã xin phép ai, và cũng không thi hành nổi lời rút của người đó. 56,6%
kho dữ liệu hiện nằm trong tình trạng này, và con số đó giờ **tự nó** chặn đường
phát hành thay vì chỉ nằm trong một bản báo cáo.

### Gộp người ký không làm mất đồng thuận

`filter_rows` phân giải `signer_aliases` (kể cả chuỗi A→B→C) trước khi tra đồng
thuận. Bỏ bước này thì một lần gộp sẽ **âm thầm** huỷ đồng thuận: mẫu cũ vẫn trỏ
tới id cũ, dòng đồng thuận thì gắn vào id mới.

## 3. Ảnh chụp — vì sao phải đi vòng qua một tệp

Các script dựng manifest / chia split / đóng gói phát hành chạy **trên máy chủ**,
ngoài mạng compose, và Postgres không mở cổng ra host (`docker port voya_postgres`
không trả gì). Bắt chúng nối CSDL nghĩa là biến chúng thành thứ không chạy được,
và **một cổng không chạy được là một cổng bị gỡ bỏ**.

Nên trạng thái đồng thuận được xuất thành một tệp có dấu thời gian và mã băm:

```bash
docker exec voya_backend python -m app.cli.consent_snapshot \
    --out /dataset/consent_snapshot.json

# kiểm tra ảnh chụp hiện có (thoát != 0 khi quá hạn)
docker exec voya_backend python -m app.cli.consent_snapshot --check
```

Script offline đọc tệp đó và **từ chối chạy** khi tệp vắng mặt, hỏng, sai phiên
bản, sai thang phạm vi, hoặc quá **7 ngày** tuổi. Mặc định-từ-chối, để quên chạy
lệnh xuất không âm thầm biến thành "không lọc gì cả".

Hạn 7 ngày chính là lời hứa "một lời rút đồng thuận có đường tới bản phát hành
kế tiếp", viết thành mã.

## 4. Cổng nằm ở những đâu

| Đường | Chỗ chặn | Mức mặc định |
|---|---|---|
| Huấn luyện trong ứng dụng | `training_tasks._consent_preflight` | theo `run_purpose`: `research`→`research_release`, `release`→`public_library`, còn lại→`internal_training` |
| Dựng manifest dữ liệu | `scripts/create_dataset_manifest.py --consent-scope` | `internal_training` |
| Chia split LOSO (artifact bài báo) | `scripts/make_loso_splits.py --consent-scope` | `research_release` |
| Chuỗi phát hành nghiên cứu | `scripts/prepare_research_release.py` — kiểm ở **bước 0** | dừng ngay nếu ảnh chụp hỏng/quá hạn, hoặc nếu **không có đồng thuận nào còn hiệu lực** |

Chuỗi phát hành kiểm **trước khi chạy** dù bước 3 (dựng manifest) cũng tự kiểm:
chuỗi có bảy bước và bước tốn thời gian nhất nằm *trước* bước dựng manifest. Để
nó chạy xong xác thực pilot rồi mới báo "ảnh chụp quá hạn" là bắt người ta chờ
để nhận một câu lẽ ra nói được ngay giây đầu.

### Vì sao huấn luyện phải soi LẠI, dù split đã được lọc lúc dựng

Trình huấn luyện **không** đọc `samples.csv` — nó đọc `train/val/test.csv` đã
đóng băng, có thể từ nhiều tuần trước. Một người rút đồng thuận hôm nay không
làm những tệp đó đổi một byte nào. Nên `_consent_preflight` đọc chính các đường
dẫn có trên dòng lệnh và hỏi lại ngay trước khi chạy.

Job bị chặn thì **thất bại trước khi chuyển sang `running`** — một job chưa từng
bắt đầu, và trạng thái của nó phải nói đúng như vậy. Câu báo lỗi nói rõ phải
dựng lại split, vì đó là việc đúng: các tệp split là **đầu vào đã đóng băng**, và
một checkpoint huấn luyện trên tập nhỏ hơn tệp split khai báo là một checkpoint
nói dối về nguồn gốc của nó.

### Cổng hỏng thì sao

`_consent_preflight` nuốt ngoại lệ và cho job chạy, kèm một dòng
`logger.error("[CONSENT] pre-flight FAILED to run …")`. Đây là **đánh đổi có ý
thức** giữa "không huấn luyện được gì" và "một lượt chạy không được soi". Dấu
vết đủ to để phát hiện điều đó đã xảy ra, và có test ghim hành vi này.

## 5. Cái cổng này CỐ Ý không làm

**Không xoá gì cả.** Rút đồng thuận ở đây nghĩa là "không đi vào lượt chọn mẫu
tiếp theo", không phải "biến mất khỏi ổ đĩa".
`docs/needFix/COMMUNITY_DATA_COMMONS.md` tách bốn nghĩa của thu hồi và nói rõ vì
sao không được hứa nghĩa mạnh nhất; đây là nghĩa thứ hai trong bốn nghĩa đó.

**Không lọc bản xuất dữ liệu của tenant** (`tenant_lifecycle`). Một tổ chức xuất
dữ liệu của chính mình là **quyền mang dữ liệu đi**, không phải phát hành cho
bên thứ ba. Lọc ở đó sẽ làm hỏng đúng cái quyền mà nó phục vụ. Đây là một quyết
định, không phải chỗ làm sót.

**Không lọc bản sao Google Sheets.** Đó là bản gương vận hành của `samples.csv`
cho quản trị viên; lọc nó sẽ phá bất biến "Sheets là bản sao đúng của CSV" mà
tác vụ đối soát dựa vào.

## 6. Cầu nối: chấp thuận của TÀI KHOẢN → đồng thuận của NGƯỜI KÝ

Hai bảng, hai chủ thể, và trước 2026-08-09 không có đường nào nối chúng:

| Bảng | Chủ thể | Câu hỏi nó trả lời |
|---|---|---|
| `user_consents` | chủ tài khoản | đã ký văn bản nào, bản số mấy |
| `signer_consents` | người trong dữ liệu | cho phép dùng tới mức nào |

Đo được: **10 tài khoản** đã ký `terms` và `privacy`, và `signer_consents` có
**0 dòng**. Người dùng bấm đồng ý, hệ thống ghi nhận, rồi cổng dữ liệu vẫn đọc
ra "chưa ai cho phép gì".

### Ký `data_contribution` cấp đúng `internal_training`, không hơn

Đọc thẳng từ bản văn 2026-08-08 mục 4:

> **Có:** huấn luyện mô hình; đo và so sánh chất lượng; xây dựng bộ dữ liệu
> phục vụ nghiên cứu **của tổ chức bạn**.
>
> **Chỉ khi bạn đồng ý riêng bằng văn bản:** đưa vào bộ dữ liệu công bố cùng
> bài báo; chia sẻ cho nhóm nghiên cứu **ngoài** tổ chức bạn.

Ranh giới "chỉ khi đồng ý riêng" nằm **đúng giữa** `internal_training` và
`research_release`. Ba mức của lược đồ chính là ba đoạn đó; cầu nối chỉ thi hành
cho đúng lời bản văn đã nói. Nâng mức tự động từ một văn bản duy nhất là điều
không được làm — nó biến một lần bấm "tôi đồng ý đóng góp" thành giấy phép công
bố khuôn mặt người ta.

### Thứ tự thật: ký trước, đóng góp sau

Người ta bấm đồng ý ở màn hình pháp lý, có khi hàng tuần trước khi quay mẫu đầu
tiên. Lúc ấy chưa có hàng nào trong `signers` để treo đồng thuận vào. Nên cầu
nối được gọi ở **hai** chỗ:

1. `legal.record_consent()` — ngay khi ký, nếu đã có hồ sơ người ký.
2. `signers.resolve_signer_for_user()` — ngay sau khi lập hồ sơ ở lần đóng góp
   đầu tiên, để chấp thuận đã ký từ trước áp cho mẫu **đầu tiên** chứ không phải
   từ mẫu thứ hai trở đi.

Bản gốc là `user_consents`; `signer_consents` là bản phản chiếu. Trục trặc ở bản
phản chiếu **không** cuốn theo bản gốc — `sync_signer_consent` tự nuốt lỗi và
ghi log, và `app.cli.backfill_signer_consents` vá lại sau.

### Ký rồi thì nó ở lại

`uq_signer_consents_live` cho phép đúng một dòng còn hiệu lực cho mỗi (tenant,
người ký, mức), và cầu nối kiểm trước khi chèn. Bấm đồng ý hai lần **không** sinh
hai dòng và **không** dời `granted_at` — mốc thời gian người ta thật sự đồng ý là
bằng chứng, ghi đè nó là xoá bằng chứng.

### API

```
GET  /api/v1/legal/me/consents      tôi đã ký gì, bản số mấy, cái gì đang chờ
POST /api/v1/legal/{kind}/accept    ký (idempotent)
POST /api/v1/legal/{kind}/withdraw  rút — kéo theo signer_consents
```

`GET /me/consents` **phải** khai báo trước `GET /{kind}` trong router: FastAPI
khớp theo thứ tự khai báo và `/{kind}` nuốt trọn một đoạn đường bất kỳ.

Rút `terms` hay `privacy` bị từ chối 409: rút điều khoản mà vẫn đăng nhập được
là một trạng thái không có thật. Muốn rời hẳn thì đó là xoá tài khoản.

### Backfill cho dữ liệu cũ

```bash
docker exec voya_backend python -m app.cli.backfill_signer_consents --dry-run
docker exec voya_backend python -m app.cli.backfill_signer_consents --confirm
```

Chỉ chép sang những chấp thuận **đã có thật** và **còn hiệu lực**. Không tạo
đồng thuận mới bao giờ.

## 7. Vết còn để lại

- ~~**Chưa có màn hình cấp/rút đồng thuận.**~~ **Xong 2026-08-09 (lượt hai):**
  `/account` → "Chấp thuận của tôi", ở `frontend/src/pages/AccountPage.tsx`.
  Màn hình nói ra ba điều mà nút bấm dễ giấu nhất: mức nó cấp là
  `internal_training` chứ không phải quyền công bố; rút thì chặn ở **mọi** mức
  kể cả nội bộ; và rút **không** xoá tệp đã đóng góp (§5 — nghĩa thứ hai, không
  phải nghĩa thứ ba). Điều còn lại là dữ liệu: chưa ai bấm thì `signer_consents`
  vẫn 0 dòng và đường phát hành vẫn rỗng, đúng ý cơ chế.
- **56,6% mẫu không có `signer_id`.** Con số này không tự tốt lên. Đường thu
  mới (`signers.resolve_signer_for_user`) đã gắn signer cho mọi mẫu quay trực
  tiếp; phần cũ cần người đi điền lại. `verify_deployment` kiểm tra #10 theo dõi
  con số này mỗi lần triển khai.
- **Chưa có cột nói hai danh tính có phải một người không.** `auth_user_id` (tài
  khoản thu) và `signer_id` (người trong dữ liệu) hiện luôn trùng nhau ở đường
  quay trực tiếp, vì đường đó suy signer từ chính tài khoản. Cột phân biệt chỉ
  có nghĩa khi có luồng "thu hộ" (giáo dục đặc biệt, người giám hộ ký thay), mà
  luồng đó chưa tồn tại. Thêm cột bây giờ là thêm một cột không ai ghi và không
  ai đọc.
