# Kho văn bản pháp lý: mô hình, lưu trữ, quy trình

*Cập nhật 2026-08-08 · schema v6*

Tài liệu này trả lời bốn câu hỏi: **văn bản nằm ở đâu**, **phiên bản đánh thế
nào**, **ai làm gì trong một lần cập nhật**, và **chỗ nào máy làm hộ được, chỗ
nào không**.

---

## 1. Khoảng trống mà v5 lấp

Trước v5, hệ thống có đủ bộ máy chấp thuận: bảng `legal_documents`, bảng
`user_consents`, đối chiếu số hiệu ở server, đánh dấu rút thay vì xoá. Chạy
đúng, có test, không hở.

Nhưng **thân văn bản không được lưu ở đâu cả.** `register_document(body=...)`
băm nội dung rồi vứt; cột `url` trỏ tới "một file tĩnh do nginx phục vụ" — file
chưa từng tồn tại.

Ba hệ quả, và cái thứ ba là cái nghiêm trọng:

1. `content_hash` không đối chiếu được với gì. Một hash không có bản gốc để so
   là một cột dữ liệu, không phải một phép kiểm.
2. Ô "Tôi đồng ý" ở biểu mẫu đăng ký trỏ tới 404.
3. **Một dòng chấp thuận trỏ tới `(kind, version)`. Nếu cặp đó không mở ra được
   bản văn nào thì dòng ấy chỉ là một con số.** Cả bộ máy bằng chứng chạy vòng
   quanh một khoảng trống.

Ngoài ra `signdb` sản xuất có **0 dòng** trong `legal_documents`, nên cưỡng chế
chưa từng bật: mọi tài khoản tới nay được tạo mà không có chấp thuận nào. Đó là
tình trạng đúng-theo-thiết-kế (*công bố chính là hành động bật cưỡng chế*)
nhưng không ai muốn nó kéo dài.

---

## 2. Mô hình thật tế: một văn bản pháp lý là bản ghi CHỈ-THÊM

Cách các tổ chức quản lý điều khoản dịch vụ trên thực tế — và cách hệ thống này
làm theo:

### 2.1 Bốn khái niệm không được lẫn

| Khái niệm | Là gì | Ở đâu trong hệ thống |
|---|---|---|
| **Loại** (`kind`) | Một *thể loại* văn bản, tồn tại vĩnh viễn | `legal.KINDS` — 4 giá trị, cố định trong mã |
| **Phiên bản** (`version`) | Một *bản văn cụ thể*, bất biến sau khi công bố | một dòng `legal_documents` |
| **Ngày hiệu lực** (`effective_from`) | Từ lúc nào bản đó là bản đang áp dụng | cột trên cùng dòng |
| **Chấp thuận** (`user_consents`) | Ai đồng ý với bản NÀO, lúc nào | một dòng, trỏ tới `(kind, version)` |

Sai lầm phổ biến là gộp hai khái niệm giữa: coi "phiên bản hiện tại" là một ô
để ghi đè. Khi đó lịch sử biến mất và mọi chữ ký cũ trỏ vào hư không.

### 2.2 Bốn loại, và vì sao tách ra

| Loại | Hỏi khi nào | Bắt buộc | Vì sao tách riêng |
|---|---|---|---|
| `terms` | đăng ký | có | quy tắc sử dụng dịch vụ |
| `privacy` | đăng ký | có | xử lý dữ liệu của **người dùng** |
| `data_contribution` | lần đóng góp đầu tiên | để đóng góp | dữ liệu sinh trắc của **người ký** |
| `guardian` | người ký dưới 18 tuổi | trong ca đó | người giám hộ đồng ý |

Ranh giới đáng nói nhất là `data_contribution`. Gộp nó vào lúc đăng ký sẽ thu
được một chữ ký cho việc người ta chưa hình dung: ở đây "đóng góp" nghĩa là
**quay video bàn tay và khuôn mặt của một con người** vào một tập dữ liệu
nghiên cứu. Đó là thứ phải hỏi khi họ đang đứng trước webcam, không phải khi
đang điền email.

### 2.3 Quy tắc bất biến

**Nội dung của một số hiệu đã công bố không bao giờ thay đổi.** Kể cả sửa lỗi
chính tả. Muốn đổi thì công bố số hiệu mới.

Cưỡng chế ở **hai tầng**, và cả hai đều cần:

* `legal.register_document` từ chối ghi đè khi hash khác → thông điệp đọc được;
* trigger `trg_legal_documents_freeze` trên bảng → đúng kể cả khi mã ứng dụng
  sai, kể cả khi ai đó mở `psql`.

Cột nào đóng băng, cột nào không:

| Cột | Sửa được? | Lý do |
|---|---|---|
| `kind`, `version`, `body`, `content_hash` | **không** | bộ tứ mà một chấp thuận trỏ tới |
| `effective_from` | chỉ khi bản **chưa** tới hạn | dời lịch một bản chưa công bố là lên lịch lại; dời một bản đã áp dụng là viết lại lịch sử |
| `url`, `title`, `requires_reconsent`, `change_summary` | có | siêu dữ liệu vận hành, không phải bản văn |

### 2.4 Đánh số phiên bản: dùng NGÀY, không dùng semver

Quy ước của hệ thống này: `YYYY-MM-DD`, ví dụ `2026-08-08`.

Lý do: semver trả lời "thay đổi này phá vỡ tương thích tới mức nào" — một câu
hỏi về API. Với văn bản pháp lý, câu hỏi người ta thực sự hỏi là *"bản áp dụng
cho tôi hồi tháng ba là bản nào"*, và ngày trả lời thẳng câu đó. Nếu phải công
bố hai bản trong một ngày, thêm hậu tố: `2026-08-08b`.

Cột `requires_reconsent` mới là thứ mang ý nghĩa "phá vỡ tương thích", và nó là
một boolean tách bạch thay vì trốn trong quy ước đánh số.

---

## 3. Lưu ở đâu, và vì sao

### 3.1 Thân văn bản nằm trong cơ sở dữ liệu

Ba phương án từng cân nhắc:

| Phương án | Vì sao **không** chọn |
|---|---|
| File tĩnh do nginx phục vụ | Đây là thiết kế cũ. Chữ ký và bản văn được ký phải sao lưu, khôi phục và nhân bản **cùng nhau**; tách ra hai hệ thống lưu trữ nghĩa là mỗi lần khôi phục là một cơ hội để chúng lệch nhau — và cái lệch đó chỉ lộ ra đúng lúc có người hỏi "bản tôi ký hồi đó viết gì". |
| Nhúng thẳng vào mã nguồn | Đổi điều khoản thành một lần triển khai. Bộ phận pháp chế không có đường ra sản phẩm mà không qua kỹ thuật. |
| **Cột `body` trong `legal_documents`** ← chọn | Một nguồn sự thật, một đường sao lưu, một giao dịch. Đọc lại bản cũ là một câu `SELECT`. |

Cái giá: bản văn đi qua JSON. Chấp nhận được — nó luôn kèm `content_hash` để
bên đọc tự đối chiếu.

### 3.2 Kho tài liệu trên đĩa (v6)

Từ v6, **mỗi bản văn cũng tồn tại như một tệp**, và cơ sở dữ liệu giữ địa chỉ
của nó.

```
<DATASET_ROOT>/legal/<kind>/<hash[0:2]>/<hash>.md
```

**Tên tệp LÀ mã băm nội dung.** Không phải quy ước đặt tên cho đẹp — nó mua ba
thứ mà `terms-2026-08-08.md` không có:

| Tính chất | Vì sao có |
|---|---|
| **Bất biến** | Đường dẫn sinh ra TỪ nội dung, nên không tráo nội dung mà giữ nguyên địa chỉ được |
| **Khử trùng lặp** | Lưu bản nháp trùng bản đã công bố không tốn byte nào |
| **Kiểm toàn vẹn không cần siêu dữ liệu** | Băm lại tệp và so với tên nó là đủ |

Thư mục con hai ký tự đầu là thói quen của Git và mọi kho định-địa-chỉ-bằng-nội
-dung: thư mục phẳng vài nghìn mục làm chậm `readdir`.

**Đặt dưới `DATASET_ROOT`** vì `./dataset:/dataset` đã mount ở cả năm service
chạy ảnh backend — kho này không cần một dòng nào trong `docker-compose.yml`.
Ghi đè bằng `LEGAL_STORE_ROOT` khi cần (bộ test dùng đúng đường đó).

**Hai nơi, một sự thật.** Nội dung nằm ở cả `legal_documents.body` lẫn kho tệp,
và đó là chủ ý:

* `body` = **bản hồ sơ**. Đóng băng, nằm cùng `pg_dump` với những chấp thuận
  trỏ tới nó. Bỏ nó đi thì khôi phục sao lưu trên máy mới cho ra các bản ghi
  chấp thuận trỏ tới văn bản không ai có.
* kho tệp = **bản tài liệu**. Thứ công cụ quản lý thao tác lên.

`content_hash` là mối nối, và `python -m app.cli.legal_store --verify` chứng
minh hai bên trùng **từng byte**. Hai bản có một phép kiểm chứng minh chúng
bằng nhau thì không phải hai nguồn sự thật.

> **Hệ quả cho sao lưu:** từ v6, `pg_dump` một mình vẫn đủ để khôi phục *bằng
> chứng chấp thuận*, nhưng **không** khôi phục kho tệp. Sao lưu đầy đủ phải kèm
> `dataset/legal/`. `verify_deployment` có một phép kiểm riêng (`kho tai lieu`)
> báo đỏ đúng tình huống "khôi phục DB mà quên thư mục".

### 3.3 Tệp Markdown trong repo là BẢN NGUỒN, không phải bản đang chạy

`docs/legal/<kind>-<version>.md` giữ bản nguồn để soát duyệt qua pull request.
Cơ sở dữ liệu giữ bản **đã công bố**. Hai chỗ này đồng bộ bằng đúng một đường:
lệnh CLI đọc tệp rồi ghi vào bảng.

Sửa tệp sau khi đã công bố mà giữ nguyên số hiệu → lệnh thoát mã 4. Đó là hành
vi đúng, không phải phiền toái.

### 3.4 Bản dịch: mô hình đã thiết kế, CHƯA làm

Cột `language` tồn tại nhưng hiện chỉ có `'vi'`, và **bản dịch không phải là
thêm một dòng vào `legal_documents`**.

Lý do: một chấp thuận trỏ tới `(kind, version)`. Nếu bản tiếng Anh là một dòng
riêng với `version` riêng, câu hỏi "người này đồng ý bản nào" có hai câu trả
lời và không câu nào đúng hẳn. Nếu nó dùng chung `version`, khoá duy nhất
`(kind, version)` vỡ.

Mô hình đúng khi cần tới: bảng `legal_document_translations` treo dưới
`(kind, version)`, một ngôn ngữ là **bản có hiệu lực pháp lý** và các bản còn
lại là bản tham khảo. Chấp thuận vẫn trỏ tới bản gốc. Chưa dựng vì chưa có nhu
cầu thật, và một bảng dịch rỗng là một bảng sẽ trôi.

---

## 4. Quy trình một lần cập nhật văn bản

### 4.1 Vai trò

| Vai | Ai | Làm gì |
|---|---|---|
| **Người soạn** | nhóm kỹ thuật / pháp chế | viết bản thảo, mô tả bản này khác bản trước ở chỗ nào |
| **Người duyệt** | đơn vị có thẩm quyền của Trường | đọc và phê duyệt nội dung |
| **Người công bố** | quản trị viên nền tảng | bấm công bố; cần nhập lại mật khẩu |
| **Người kiểm** | vận hành | đối chiếu độ phủ chấp thuận sau đó |

Người soạn và người công bố **có thể** là một người trên hệ thống này (nhóm
nhỏ), nhưng người duyệt thì không nên — và cột `published_by` ghi lại ai bấm
nút để câu hỏi đó luôn có câu trả lời.

### 4.2 Các bước

```
1. SOẠN      docs/04-legal/published/terms-2026-09-01.md  (nhánh git, pull request)
2. DUYỆT     đơn vị có thẩm quyền đọc và phê duyệt
             ── mốc này KHÔNG có trong phần mềm; xem §6 ──
3. QUYẾT     có phải "đồng ý lại" không?
             mở rộng phạm vi xử lý dữ liệu  → CÓ
             làm rõ câu chữ, sửa chính tả    → KHÔNG
4. CÔNG BỐ   qua CLI hoặc /admin/legal
             hẹn giờ nếu cần báo trước
5. BÁO       nếu requires_reconsent: thông báo trước ngày hiệu lực
6. KIỂM      /admin/legal → bảng độ phủ chấp thuận
```

### 4.3 Công bố bằng CLI

```bash
# Xem đang có gì
python -m app.cli.register_legal_document --list
python -m app.cli.register_legal_document --history

# Công bố, hiệu lực ngay
python -m app.cli.register_legal_document \
    --kind terms --version 2026-09-01 \
    --file docs/04-legal/published/terms-2026-09-01.md \
    --url /legal/terms \
    --title "Điều khoản sử dụng" \
    --change-summary "Bổ sung mục về xuất dữ liệu tổ chức."

# Công bố, hẹn giờ + buộc đồng ý lại
python -m app.cli.register_legal_document \
    --kind privacy --version 2026-09-01 \
    --file docs/04-legal/published/privacy-2026-09-01.md \
    --url /legal/privacy \
    --effective-from 2026-09-01T00:00:00+07:00 \
    --requires-reconsent
```

Mã thoát: `0` xong · `2` thiếu tham số · `3` không đọc được tệp · `4` xung đột
nội dung.

### 4.4 Hẹn giờ là cách báo trước

`--effective-from` ở tương lai đặt bản mới nằm sẵn trong bảng. Đường đọc công
khai **không thấy nó** (kể cả khi đoán trúng số hiệu), `current_document` vẫn
trả bản cũ, và tới đúng thời điểm nó tự thay mà không cần ai chạy lệnh gì lúc
nửa đêm.

Người soạn vẫn đọc lại được bản đã hẹn qua `/admin/legal` — nếu không, cách duy
nhất để xem lại bản mình vừa lên lịch là chờ tới ngày.

### 4.5 `requires_reconsent`: đường phân thuỷ

Bật cờ này nghĩa là **mọi người dùng đang hoạt động bị đá ra màn hình đồng ý** ở
lần gọi API tiếp theo của họ.

Bật khi: mở rộng loại dữ liệu thu thập, thêm bên thứ ba nhận dữ liệu, đổi mục
đích xử lý, đổi thời hạn lưu trữ theo hướng dài hơn.

**Không** bật khi: sửa chính tả, làm rõ câu chữ, đổi thông tin liên hệ, sắp xếp
lại mục.

Bật nhầm không hỏng dữ liệu nhưng làm hỏng thói quen: người dùng bị hỏi lại vì
những thay đổi không đáng sẽ học cách bấm đồng ý mà không đọc, và tới lần thay
đổi thật sự đáng đọc thì họ vẫn bấm mà không đọc.

Đi kèm cờ này, `--change-summary` là **bắt buộc trên thực tế**: bắt người ta
đồng ý lại mà không nói đổi cái gì thì chữ ký thu được có giá trị bằng không.

---

## 5. Chấp thuận: chữ ký thật và dòng ghi hộ

### 5.1 Ba nguồn

`user_consents.source` nhận `'user'`, `'backfill'`, `'import'`.

* **`user`** — người dùng bấm nút. Kèm băm IP và chuỗi trình duyệt.
* **`backfill`** — người vận hành ghi hộ cho tài khoản có trước ngày công bố.
  Kèm `note` **bắt buộc** và `recorded_by`.
* **`import`** — mang từ hệ thống khác sang. Chưa dùng.

Đây không phải chi tiết kế toán mà là **ranh giới đạo đức**. Người vận hành
khẳng định một điều ("những tài khoản này là của chúng tôi, chúng tôi chấp nhận
thay chúng"); người dùng bấm nút khẳng định một điều khác. Ghi cả hai vào cùng
một hình dạng dữ liệu là làm giả bằng chứng — kể cả khi lời khẳng định đầu hoàn
toàn đúng sự thật. Bản ghi sống lâu hơn hoàn cảnh biết được sự khác nhau đó.

Vì thế `consent_coverage()` trả về **hai** con số: `accepted` và
`accepted_by_user`. Trang `/admin/legal` hiện cả hai, và chênh lệch giữa chúng
được ghi chú thẳng dưới bảng.

### 5.2 Ghi hộ cho tài khoản có sẵn

```bash
# Xem sẽ chạm ai — KHÔNG ghi gì. Đây là mặc định.
python -m app.cli.backfill_consents --note "tài khoản nội bộ do nhóm phát triển tạo"

# Ghi thật
python -m app.cli.backfill_consents \
    --note "tài khoản nội bộ do nhóm phát triển tạo trước ngày công bố 2026-08-08" \
    --apply
```

Lệnh này bỏ qua tài khoản đã có chấp thuận còn hiệu lực, nên **không ghi đè
chữ ký thật bằng một dòng ghi hộ** — ghi đè ở đó là hạ cấp bằng chứng.

### 5.3 Lịch sử không bị viết lại

Đồng ý bản mới **đánh dấu** bản cũ là đã rút (`withdrawn_at`), không xoá dòng.
Chỉ mục duy nhất bộ phận `uq_consent_live` cho phép đúng một chấp thuận còn
hiệu lực cho mỗi `(người, loại)`.

Câu hỏi mà bảng này tồn tại để trả lời — *"người này đã đồng ý những gì, bản
nào, vào lúc nào"* — chỉ trả lời được nếu các câu trả lời cũ còn nguyên.

---

## 6. Chỗ phần mềm KHÔNG làm hộ được

Nói thẳng để không ai tưởng đã xong:

**Việc phê duyệt nội dung.** Bước 2 ở §4.2 không có trong phần mềm và không nên
có. Hệ thống ghi lại *ai bấm nút công bố*, không ghi lại *ai chịu trách nhiệm
về nội dung*. Hai điều đó phải trùng nhau bằng quy trình của tổ chức.

**Tính đúng đắn pháp lý của bản văn.** Bốn tệp trong `docs/legal/` là **bản thảo
kỹ thuật** — viết từ hành vi thực tế của phần mềm để mô tả đúng những gì hệ
thống làm. Chúng chưa qua rà soát pháp chế, và mỗi tệp tự nói điều đó ở dòng
đầu. Trước khi mở dịch vụ cho tổ chức ngoài Trường Đại học Cần Thơ, chúng phải
được đơn vị có thẩm quyền thẩm định.

**Thông báo cho người dùng trước ngày hiệu lực.** Hệ thống hẹn giờ được nhưng
không tự gửi thư. Nếu bật `requires_reconsent`, việc báo trước là việc của con
người.

**Xoá dữ liệu khi có người rút chấp thuận đóng góp.** Bản ghi được đánh dấu,
nhưng việc xoá tệp khỏi ổ đĩa là thao tác vận hành.

> **Cập nhật 2026-08-09 — phần "gỡ mẫu khỏi bộ dữ liệu huấn luyện" giờ TỰ ĐỘNG.**
> Trước đó `withdrawn_at` được ghi và không có gì xảy ra tiếp: không đường xuất,
> đường huấn luyện, đường tạo split hay đường phát hành nào đọc bảng
> `signer_consents`. Nay có cổng ở `app/consent_gate.py` đứng chắn cả bốn đường.
> Rút đồng thuận thì mẫu bị loại khỏi lượt chọn TIẾP THEO ở mọi mức, kể cả huấn
> luyện nội bộ.
>
> Cái vẫn còn là việc của con người: **xoá tệp**. Đó là nghĩa thứ ba trong bốn
> nghĩa của "thu hồi" ở `docs/01-architecture/COMMUNITY_DATA_COMMONS.md`, và cổng này
> chỉ thi hành nghĩa thứ hai. Chi tiết: `docs/04-legal/CONSENT_ENFORCEMENT.md`.

**Thu chấp thuận của NGƯỜI KÝ.** ~~Chưa có màn hình nào để cấp hay rút.~~

> **Cập nhật 2026-08-09 (lượt hai) — đã có màn hình.** `frontend/src/pages/AccountPage.tsx`
> tại `/account`, mục "Chấp thuận của tôi": ký, rút, và đọc lại đúng bản mình đã
> ký. Nó đứng trên ba đường vốn đã có từ trước và chưa ai gọi —
> `GET /legal/me/consents`, `POST /legal/{kind}/accept`,
> `POST /legal/{kind}/withdraw`.
>
> `GET /legal/me/consents` được mở rộng cùng lượt này để nói đủ bốn điều mà một
> màn hình trung thực cần: bản ĐÃ ký (`accepted_version`, có thể khác bản hiện
> hành), `needs_reconsent` để không gộp "đã ký bản cũ" với "chưa ký bao giờ",
> `withdrawable` để giao diện khỏi tự suy ra rồi hiện một cái nút chắc chắn 409,
> và `grants_scope` để nút bấm nói ra mức nó cấp — `internal_training`, KHÔNG
> phải quyền công bố.
>
> Việc còn lại là **dữ liệu, không phải mã**: chừng nào chưa ai bấm đồng ý thì
> `signer_consents` vẫn 0 dòng và mọi đường phát hành nghiên cứu vẫn trả về
> rỗng. Đó là kết quả đúng của cơ chế, không phải một lỗi cần sửa.

---

## 7. Tham chiếu nhanh

### Bảng

```
legal_documents
  doc_id, kind, version, effective_from, content_hash, url, title,
  requires_reconsent, body, body_format, language, change_summary,
  published_at, published_by
  UNIQUE (kind, version) · trigger trg_legal_documents_freeze

user_consents
  consent_id, user_id, kind, version, accepted_at, ip_hash, user_agent,
  withdrawn_at, source, note, recorded_by
  FK (kind, version) → legal_documents ON DELETE RESTRICT
  UNIQUE (user_id, kind) WHERE withdrawn_at IS NULL
```

Cả hai bảng **không** thuộc `TENANT_SCOPED_TABLES`: văn bản áp cho cả nền tảng,
chấp thuận gắn với tài khoản chứ không với tổ chức.

### Đường API

| Đường | Ai gọi được | Trả gì |
|---|---|---|
| `GET /legal/documents` | công khai | mục lục các bản đang hiệu lực |
| `GET /legal/{kind}` | công khai | siêu dữ liệu, **không** kèm thân |
| `GET /legal/{kind}/content?version=` | công khai | nguyên văn; chỉ bản đã hiệu lực |
| `GET /admin/legal/documents` | quản trị | mọi bản + độ phủ + loại còn thiếu |
| `GET /admin/legal/documents/{kind}/{version}` | quản trị | nguyên văn, kể cả bản hẹn giờ |
| `POST /admin/legal/documents` | quản trị **+ nâng quyền** | công bố thẳng (đường CLI) |
| `GET /admin/legal/drafts` | quản trị | bản nháp đang mở |
| `POST /admin/legal/drafts` | quản trị | mở bản nháp mới |
| `GET /admin/legal/drafts/{id}` | quản trị | bản nháp kèm thân bài |
| `PATCH /admin/legal/drafts/{id}` | quản trị | sửa — **cần `revision`** |
| `POST /admin/legal/drafts/{id}/status` | quản trị | đổi trạng thái — cần `revision` |
| `POST /admin/legal/drafts/{id}/publish` | quản trị **+ nâng quyền** | công bố từ bản nháp |
| `GET /admin/legal/events` | quản trị | sổ đăng bạ |
| `GET /admin/legal/consents/{user_id}` | quản trị | lịch sử chấp thuận một tài khoản |

Số hiệu phiên bản đi qua **tham số truy vấn**, không phải đoạn đường: cổng truy
cập chạy trước định tuyến nên chỉ khớp được đường nguyên văn.

### Trang giao diện

| Đường | Ai |
|---|---|
| `/legal/:kind` | công khai — ô "Tôi đồng ý" ở đăng ký trỏ tới đây |
| `/admin/legal` | quản trị |

### Chỗ "quên công bố" lộ ra

Cưỡng chế bật bằng cách công bố, nên "quên công bố" trông giống hệt "chạy bình
thường". Ba chỗ nó lộ ra:

1. `verify_deployment` báo đỏ khi thiếu loại bắt buộc;
2. `/admin/legal` hiện dải cảnh báo vàng;
3. một dòng WARNING trong log mỗi lượt đăng ký không thu được chấp thuận.

---

## 8. Soạn thảo: bản nháp, khoá lạc quan, sổ đăng bạ (v6)

### 8.1 Vì sao có bản nháp

Tới v5, đường duy nhất đưa nội dung vào hệ thống là một lệnh công bố. Nghĩa là
ba trạng thái đầu của vòng đời một văn bản — **đang soạn, đang rà soát, đã phê
duyệt** — không tồn tại, và một bản văn ra khỏi tay một người mà không ai đọc
lại. Đó chính là thứ quy trình ở §4.2 tồn tại để chặn, và tới v5 nó chỉ là chữ
trong tài liệu.

`legal_document_drafts` là bảng **duy nhất** trong toàn bộ mặt phẳng pháp lý
được sửa. Mọi bảng còn lại chỉ-thêm hoặc bất biến.

```
draft ──► in_review ──► approved ──► published
  ▲            │             │
  └────────────┴─────────────┘   (trả về sửa tiếp)
  │            │             │
  └──── discarded ◄──────────┘
```

Bảng chuyển hợp lệ nằm ở `legal.DRAFT_TRANSITIONS`, viết ra thành **dữ liệu**
chứ không thành chuỗi `if`: người đọc thấy ngay rằng không có đường tắt từ
`draft` thẳng tới `published`.

**Đúng một bản nháp mở cho mỗi loại** (`uq_legal_draft_open`). Cho phép nhiều
bản song song nghĩa là hai người soạn hai bản khác nhau của cùng một văn bản và
không ai hợp nhất chúng — một bài toán trộn văn bản pháp lý mà phần mềm này
không có công cụ để giải. Một bản nháp chung, với khoá lạc quan, biến nó thành
xung đột ghi phát hiện được ngay.

### 8.2 Khoá lạc quan

Mọi lượt ghi mang theo `revision` — số hiệu bản mà người soạn **đang xem**, không
phải bản họ muốn ghi. `UPDATE ... WHERE revision = %s` trả về 0 hàng khi có
người ghi trước, và API trả 409 kèm số hiệu hiện tại.

Phần quan trọng nằm ở **giao diện**: khi 409 tới, đoạn người dùng vừa gõ phải
CÒN NGUYÊN. Cách hỏng mặc định — hiện "Lưu thất bại, tải lại trang" — là vứt đi
vài nghìn chữ. Trình soạn thảo giữ nguyên ô nhập, kéo về bản của người kia để
đọc cạnh nhau, và **không tự trộn**: hợp nhất hai bản văn pháp lý là việc của
con người.

### 8.3 Sổ đăng bạ

`legal_document_events` — **chỉ thêm**, cưỡng chế bằng trigger.

Ghi **hành động** và **đối tượng**, không ghi **nội dung**. Một lượt sửa thân
bài để lại `{"fields": ["body"]}`, không để lại bản văn. Lý do: sổ này được đọc,
xuất và chuyển tiếp thường xuyên hơn bảng văn bản, nên nhét bản văn vào đây là
nhân bản một tài liệu có thể còn đang cấm phát hành sang một chỗ có quyền đọc
khác hẳn.

Bảng này **không có khoá ngoại nào** — không tới `legal_document_drafts`, và
không tới `users`. Cái thứ hai đã trả giá để học: `ON DELETE SET NULL` phát ra
một UPDATE, trigger chỉ-thêm từ chối nó, nên `DELETE FROM users` bắt đầu hỏng
cho bất kỳ ai từng xuất hiện trong sổ — tức là thêm một sổ đăng bạ đã âm thầm
làm hỏng quyền xoá tài khoản mà §6 của Chính sách quyền riêng tư hứa. Nguyên
tắc chung: **một sổ đăng bạ không được cản chính hành động nó ghi lại.** Danh
tính người thao tác còn lại ở `actor_label`.

---

## 9. Tranh chấp đồng thời: bảy tình huống và cách xử

| # | Tình huống | Cách xử | Kiểm ở đâu |
|---|---|---|---|
| 1 | Hai người sửa cùng bản nháp | `revision` + 409 kèm số hiện tại | `test_twoThreadsWritingTheSameRevision_onlyOneWins` |
| 2 | Hai lượt công bố cùng `(kind, version)` | UNIQUE sẵn có; trùng nội dung → idempotent, khác → 409 | `test_changingContentUnderTheSameVersion_is409` |
| 3 | Hai bản cùng `(kind, effective_from)` | `uq_legal_effective` → 409 rõ ràng thay vì thắng ngẫu nhiên | `test_twoVersionsWithTheSameEffectiveFrom_isRefused` |
| 4 | Đọc-rồi-ghi quanh lịch hiệu lực | `pg_advisory_xact_lock(hashtext('legal:'||kind))` | — |
| 5 | Blob ghi xong, hàng ghi hỏng | Blob mồ côi, vô hại, GC dọn sau 24h | `test_anUnreferencedOldBlob_isCollected` |
| 6 | GC chạy trúng lúc đang công bố | GC đòi **cả hai**: không tham chiếu VÀ đủ 24h tuổi | `test_aFreshUnreferencedBlob_isKept` |
| 7 | Công bố trúng lúc bản nháp bị sửa | Publish mang `revision`, khớp trong cùng giao dịch | `test_publishing_withAStaleRevision_isRefused` |

**Thứ tự ghi là một phần của tính đúng.** Blob trước, hàng sau — luôn luôn. Một
blob mồ côi thì dọn được; một hàng trỏ tới tệp không tồn tại thì không cứu
được. Và vì tên tệp là băm nội dung, ghi lại sau một lần hỏng giữa chừng là an
toàn.

**Khoá tư vấn theo `kind`, không theo bảng.** Công bố `terms` và `privacy` cùng
lúc là việc hợp lệ và không đụng nhau.

---

## 10. Lệnh vận hành kho tài liệu

```bash
python -m app.cli.legal_store --status     # kho có gì
python -m app.cli.legal_store --verify     # bảng và kho có khớp từng byte không
python -m app.cli.legal_store --backfill   # đưa bản công bố thời v5 vào kho
python -m app.cli.legal_store --gc         # liệt kê blob mồ côi (KHÔNG xoá)
python -m app.cli.legal_store --gc --apply # xoá thật
```

`--verify` là lệnh đáng chạy sau mỗi lần khôi phục sao lưu. Nó kiểm hai chiều:
mỗi hàng có con trỏ phải trỏ tới một tệp có thật, và tệp đó phải trùng **từng
byte** với cột `body`.

`--gc` mặc định **không xoá**. Đây là lệnh xoá tệp, và một lệnh xoá tệp không
nên chạy vì người ta gõ thiếu một cờ.
