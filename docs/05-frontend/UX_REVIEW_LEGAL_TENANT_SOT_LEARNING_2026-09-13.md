# Kế hoạch UX: văn bản pháp lý, tổ chức, SOT và hướng dẫn học tập

Ngày: 13/09/2026. Trạng thái: đề xuất để triển khai, chưa thay đổi chức năng ứng dụng.

## 1. Mục tiêu và giới hạn

Giúp người dùng trả lời được ba câu hỏi trên mỗi màn hình: **Tôi đang ở đâu? Tôi có thể làm gì? Bước tiếp theo là gì?**

Phạm vi ưu tiên: Legal Document (trang đọc, đồng thuận và quản trị), tenant (tổ chức, thành viên, ngữ cảnh dữ liệu), SOT (vận hành dữ liệu chuẩn). Bổ sung định hướng trung tâm hướng dẫn thao tác và nội dung học tập dành cho giáo viên, học sinh và cộng đồng người Điếc/khiếm thính, người gặp khó khăn giao tiếp bằng lời nói. Không suy ra mọi người dùng trong các nhóm này có cùng nhu cầu, khả năng đọc hay ngôn ngữ ký hiệu.

Các phần thu thập, nhận dạng, huấn luyện hiện có được tái sử dụng; chỉ sửa điểm giao tiếp liên quan đến phạm vi tổ chức, hướng dẫn hoặc quyền riêng tư khi cần. Chưa mở rộng thành một hệ quản lý học tập đầy đủ.

Nguồn bằng chứng: mã nguồn hiện tại; kết quả kiểm tra frontend ở lượt review trước; phần kiểm tra chạy thật sẽ ghi riêng bên dưới. Không coi unit test xanh là bằng chứng trải nghiệm trên điện thoại tốt. Tài khoản quản trị nền tảng cũng không đại diện cho quyền của giáo viên/học sinh.

## 2. Những vấn đề cần xử lý trước khi làm đẹp

| Mã | Ưu tiên | Bằng chứng từ mã | Hệ quả và cách xử lý |
|---|---|---|---|
| TEN-01 | P1 | `OrgLayout.tsx` chỉ tìm membership theo `tenantId`, vẫn dựng `Outlet`; `OrgWorkPages.tsx` khẳng định đích dữ liệu theo URL; `tenant_middleware.py` dùng `users.active_tenant_id`. | Người thuộc cả A và B có thể mở đường dẫn A trong khi ngữ cảnh máy chủ là B. Không có cảnh báo nếu membership A hợp lệ. Đối chiếu ngữ cảnh từ máy chủ trước khi dựng trang con; chưa xác minh thì không cho ghi. Đây là rủi ro nhầm đích dữ liệu, chưa phải bằng chứng đọc vượt quyền. |
| TEN-02 | P1 | `AdminTenantsPage.tsx`: `loadTenants` phụ thuộc `toast`; lỗi tải gọi `toast.error`. Bundle production cho thấy React Compiler memoize object toast theo context, nhưng context vẫn đổi khi danh sách toast đổi. | Khi API tải tổ chức lỗi: thêm toast → context đổi → callback đổi → effect tải lại → lại lỗi. Có nguy cơ vòng gọi API/thông báo khi mất kết nối. Không kết luận cứ render là lặp trên bản production. Cần ổn định callback theo `addToast`, kiểm tra đường lỗi với provider thật và số lần gọi API. |
| TEN-03 | P1 | Khi đổi `selected`, `AdminTenantsPage.tsx` chưa xóa dữ liệu chi tiết cũ trước `loadDetail`; lỗi từng request được đổi thành mảng rỗng. | Trong lúc tải B, thành viên A có thể nằm dưới tiêu đề B. Một lỗi mạng có thể bị hiểu là “chưa có thành viên”. Lưu dữ liệu kèm tenant ID, có loading/error riêng từng khối, khóa thao tác cho đến khi chi tiết khớp tổ chức. |
| LEG-01 | P1 | `AdminLegalPage.tsx` lấy `doc.body` rồi dựng `Markdown`; upload file ở backend lưu `body=""`; `DocumentViewer.tsx` đã hỗ trợ file nhưng chưa dùng ở preview này. | Nút “Xem” của bản PDF/DOCX có thể mở nội dung trống. Preview phải giữ đầy đủ document và chọn viewer theo `body_format`, có quyền xem bản chưa hiệu lực đúng theo API. |
| LEG-02 | P1 | `backend/app/legal.py:list_documents` tính `is_effective` bằng `effective_from <= now()`; UI diễn giải thành “đang áp dụng”. | Nhiều bản lịch sử có thể cùng hiện “đang áp dụng”. Trả trạng thái rõ: bản hiện hành, đã thay thế, lên lịch; xác định bản hiện hành theo quy tắc backend đang dùng, không tự tạo quy tắc thứ hai ở UI. |
| LEG-03 | P2 | `LegalDocumentPage.tsx` không reset `doc` lúc đổi loại/phiên bản; khi fetch lỗi vẫn có nhánh `!loading && doc`. | Sau khi đọc A rồi mở B lỗi, nội dung A có thể hiện dưới tiêu đề B. Hiển thị nội dung chỉ khi khớp khóa truy vấn; phân biệt 404, mất mạng, không có quyền. |
| LEG-04 | P2 | `UploadDocumentForm.tsx` gửi `datetime-local` không offset; biểu mẫu không chỉ rõ múi giờ. | Người dùng không biết thời điểm công bố theo giờ nào. Chốt múi giờ hiển thị, gửi timestamp có offset, preview ngày giờ trước công bố. Chưa kết luận lệch bao nhiêu giờ nếu chưa đối chiếu cấu hình DB/runtime. |
| LEG-05 | P1 | Endpoint upload gọi `_require_sudo`; `UploadDocumentForm.tsx` chỉ hiện lỗi; `uploadDocument` không xử lý xác thực lại; phần gọi `useSudo` ở trang cha chưa nối vào biểu mẫu upload. | Một phiên chưa nâng quyền bấm công bố sẽ mắc ở thông báo cần nhập lại mật khẩu nhưng không có bước nhập tại luồng đó. Nối luồng xác thực lại và thử lại sau thành công, giữ nguyên tệp/biểu mẫu. Test hiện tại mới kiểm tra hiện thông báo lỗi. |
| SOT-01 | P1 | Modal khóa riêng trong `SotAdminPage.tsx` đóng khi bấm nền; nút Copy không chờ `clipboard.writeText` và luôn báo thành công. | Có thể mất khóa chỉ hiển thị một lần hoặc tưởng đã sao chép khi trình duyệt từ chối. Giữ modal đến xác nhận lưu, báo kết quả clipboard thực tế và có phương án lưu thủ công. Không tạo khóa để tái hiện lỗi trên dữ liệu thật. |
| SOT-02 | P2 | `SotAdminPage.tsx` hiển thị `Verify`, `publish`, `schema`, `raw_uploads`, `signed_by`, fingerprint; lỗi overview chỉ toast, sau đó tiếp tục dựng dữ liệu mặc định. | Khó hiểu và có thể lẫn “chưa có dữ liệu” với “không tải được”. Thêm kết luận bằng tiếng Việt, thời điểm kiểm tra, hành động tiếp theo và lỗi giữ trên trang. |

### Đợt 0 — kết quả đối chiếu mã (13/09/2026, sau khi khôi phục CSDL)

| Mã | Kết luận | Bằng chứng đã kiểm |
|---|---|---|
| TEN-01 | **Đúng** | `GET /tenants/mine` không trả về tổ chức đang hoạt động (`TenantMembershipRow` chỉ có `is_home`); `OrgLayout` chỉ tìm membership theo `:tenantId` rồi dựng `Outlet`. Chú thích đầu tệp nói "tự đưa về `/org`" — mã chỉ hiện cảnh báo khi KHÔNG có membership, còn có membership ở A trong khi máy chủ ở B thì im lặng. |
| TEN-02 | **Đúng, và rộng hơn** | `useToast()` trả `toast` là object mới mỗi render, không memo; `loadTenants` có `toast` trong deps. Lỗi gốc nằm ở `hooks/useToast.tsx`, ảnh hưởng mọi trang đưa `toast` vào deps, không riêng trang tổ chức. |
| TEN-03 | **Một nửa** | Đua request ĐÃ được chặn bằng bộ đếm `detailRun` (chỉ lượt mới nhất ghi state). Còn lại đúng: dữ liệu A vẫn hiện dưới tiêu đề B trong lúc tải; `allSettled` đổi mọi lỗi thành `[]`/`null`. |
| LEG-01 | **Đúng** | `openPreview` → `setPreview({ body: doc.body })` → `<Markdown>`; `legal_admin.py:277` lưu `body=""`, `body_format="file"` cho tệp tải lên. Preview tệp trắng. |
| LEG-02 | **Đúng** | `legal.py:210` `d.effective_from <= now() AS is_effective`; `AdminLegalPage.tsx:328` dịch thành "đang áp dụng" cho MỌI bản quá khứ. Nhánh còn lại ghi "đã lên lịch" — nên bản đã thay thế cũng hiện "đang áp dụng". |
| LEG-03 | **Đúng** | `setDoc` chỉ gọi khi thành công; nhánh lỗi không xoá `doc`; render `!loading && error` VÀ `!loading && doc` là hai khối độc lập nên cùng hiện. |
| LEG-04 | **Đúng, đo được lệch** | Biểu mẫu gửi `datetime-local` không offset; máy chủ đọc `fromisoformat` naive. Container backend và Postgres đều **UTC** (đo: `time.tzname=('UTC','UTC')`, `SHOW timezone=Etc/UTC`). Người ở Việt Nam nhập 09:00 → hiệu lực 16:00 giờ Việt Nam: **lệch 7 giờ**. Chú thích trong biểu mẫu ("múi giờ của máy chủ, đúng nơi quyết định") mô tả sai thực tế. |
| LEG-05 | **Đúng** | `UploadDocumentForm` chỉ nhận `onDone`; `ensureSudo` ở `AdminLegalPage.tsx:292` được nối vào biểu mẫu KHÁC. Endpoint upload gọi `_require_sudo` (`legal_admin.py:252`). |
| SOT-01 | **Đúng** | `SotAdminPage.tsx:404` nền `onClick={() => setGeneratedKey(null)}`; dòng 419 `navigator.clipboard?.writeText(...)` không `await`, `toast.success` vô điều kiện (kể cả khi `clipboard` là `undefined` trên HTTP thường). |
| SOT-02 | **Đúng** | Lỗi overview chỉ `toast.error` rồi trang dựng tiếp với `overview=null`; nhãn kỹ thuật giữ nguyên. |

Mục 8 (đăng nhập, ảnh màn hình, đa vai) chưa thực hiện: sáng 13/09 CSDL rỗng do volume bị xoá; đã khôi phục cuối ngày (xem `docs/06-operations/BACKUP_RESTORE.md`).

### Đợt 1 — đã làm (13–14/09/2026)

| Mã | Cách sửa | Mẫu tham chiếu | Bằng chứng |
|---|---|---|---|
| LEG-04 | `utils/effectiveFrom.ts`: gửi ISO **có offset**; dòng xem trước "Có hiệu lực lúc 09:00 20/08/2026 — Asia/Ho_Chi_Minh (UTC+07:00)" ngay dưới ô nhập. | Google Calendar, Stripe: giờ hẹn luôn kèm múi giờ. | 7 test FE; test BE `honoursTheBrowserOffset` (09:00+07 → 02:00Z). |
| TEN-02 | Sửa ở gốc `hooks/useToast.tsx`: `toast` memo theo `addToast`. | — | Tiêm lỗi: mã cũ gọi API **84 lần/150 ms** khi mất kết nối; mới: 1. |
| TEN-01 | `OrgLayout` đối chiếu `/tenants/me` (ngữ cảnh máy chủ) với `:tenantId`; lệch → **chặn** trang con, hộp chọn tường minh "Chuyển sang A / Ở lại B"; không xác nhận được → chặn + Thử lại. Không tự đổi ngầm (hai tab giành ngữ cảnh). | Google "Choose an account"; GitHub hộp xác nhận đổi ngữ cảnh. | 5 test. |
| LEG-05 | `UploadDocumentForm` nhận `ensureSudo`; bị 403 `sudo_required` → hỏi mật khẩu → gửi lại **cùng payload**, tệp giữ nguyên. | GitHub sudo mode. | 2 test. |
| LEG-01 | Preview giữ nguyên document, dựng bằng `DocumentViewer` theo `body_format`; **thêm endpoint** `GET /admin/legal/documents/{kind}/{version}/file` vì đường công khai từ chối bản đã lên lịch (phát hiện thêm ở Đợt 1). | — | 3 test BE + 1 FE. |
| LEG-02 | Backend tính `status ∈ {current, superseded, scheduled}` bằng đúng quy tắc `read_document`; UI ba nhãn khác chữ, không chỉ khác màu. | GitHub Releases "Latest"; Stripe API versions "Current/Legacy". | Test BE: chỉ một bản `current`. |
| LEG-03 | `setDoc(null)` trước khi tải; 404 / 401–403 / không phản hồi là ba câu khác nhau. | — | Test điều hướng thật; tiêm lỗi đỏ đúng chỗ. |
| SOT-01 | `components/sot/PrivateKeyModal`: không đóng khi bấm nền/Escape; "Đã sao chép" chỉ sau `await writeText` thành công; thất bại thì chọn sẵn + tải `.key`; nút đóng mở sau khi chép được hoặc tự xác nhận. | GitHub PAT "You won't be able to see it again"; AWS access key "Download .csv → Done". | 6 test. |
| TEN-03 | Đổi lựa chọn → xoá chi tiết cũ; lỗi **từng khối** + Thử lại; `<fieldset disabled>` khoá mọi thao tác tới khi chi tiết khớp tổ chức. | — | 2 test (request treo). |
| SOT-02 | `utils/sotStatus.ts`: 7 kết luận một câu (đang kiểm / không kết nối / chưa công bố / nguồn lạ / chưa kiểm / không đạt / đạt) + việc cần làm + "Kiểm tra lúc …"; lỗi tổng quan giữ trên trang có Thử lại; đổi nhãn theo bảng §5 (phần đầu). | Trang status kiểu GitHub/Vercel: một câu kết luận trước mọi con số. | 5 test bảng trạng thái. |

Chưa làm trong Đợt 1 (thuộc Đợt 2–3): bố cục theo nhiệm vụ, wizard đăng ký máy, lịch sử kiểm tra, mobile, mục 8.

Các lỗi modal/focus/nhãn đã nêu ở lượt trước cần được xử lý trong ba khu vực này. Nhận định trước về hook trong `try/catch` là lỗi quy tắc lint, chưa đủ chứng cứ để khẳng định chính hook đó đã gây crash; vòng tải lại TEN-02 là đường lỗi cụ thể hơn cần tái hiện.

## 3. Legal: giúp đọc hiểu và quyết định dễ hơn

### Trang dành cho người đọc

Đề xuất tên điều hướng: **Quyền riêng tư & điều khoản**. Mỗi loại tài liệu có mô tả một câu “Văn bản này nói về điều gì”.

Thứ tự hiển thị:

1. Tên văn bản, đơn vị ban hành, trạng thái phiên bản, ngày hiệu lực và ngôn ngữ dễ đọc (“Tiếng Việt”, không chỉ `vi`).
2. “Những điều bạn cần biết”: 3–5 ý ngắn đã được người phụ trách nội dung duyệt; bản tóm tắt gắn với đúng phiên bản gốc.
3. Mục lục liên kết tới từng phần; hỗ trợ đọc tiếp, cỡ chữ, in/tải bản gốc.
4. Nội dung đầy đủ: HTML dễ đọc cho văn bản; PDF có “Mở riêng” và “Tải bản gốc” luôn nhìn thấy; DOCX/ODT ghi rõ cần ứng dụng tương ứng, không cho thấy khung trống.
5. “Có gì thay đổi?” và liên kết đến đúng bản người dùng đã đồng ý.
6. Hành động phù hợp trạng thái: đọc trước, ghi nhận đồng ý, hoặc xem/rút lựa chọn khi chính sách cho phép. Có kênh hỗ trợ bằng văn bản.

Tóm tắt và video giải thích không thay thế bản văn có hiệu lực. Không tự sửa nội dung điều khoản khi chỉnh giao diện. Người dùng phải phân biệt đồng ý sử dụng dịch vụ, đồng ý ghi hình, dùng dữ liệu cho huấn luyện nội bộ và chia sẻ/công bố bên ngoài. Không gộp tất cả thành một ô mặc định được tích.

Không đánh đồng kéo trang đến cuối hoặc xem hết video với đã hiểu/đã chấp thuận. Không dùng bài kiểm tra hiểu văn bản như điều kiện buộc phải vượt qua để dùng dịch vụ.

### Trang quản trị

Chuyển trang dài gồm nhiều bảng và biểu mẫu thành các mục:

- **Tổng quan**: tài liệu hiện hành, bản chờ duyệt/lên lịch, việc cần xử lý.
- **Soạn & duyệt**: một đường “Tạo phiên bản mới”, chọn viết nội dung hoặc tải tệp; tránh hai luồng trông như hai chức năng không liên quan.
- **Phiên bản**: hiện hành, đã thay thế, lên lịch; bản gốc và nội dung thay đổi.
- **Chấp thuận**: ghi rõ mẫu số và đối tượng, phân biệt người tự đồng ý với dữ liệu nhập/chuyển đổi, không chỉ đặt nhiều con số giống nhau.
- **Lịch sử thao tác**: câu dễ hiểu “Nguyễn A công bố bản X”, mã sự kiện nằm trong chi tiết.

Luồng công bố: **Nội dung → Xem trước → Kiểm tra phạm vi/ngày giờ → Xác nhận công bố**. Màn cuối nêu rõ ảnh hưởng đến ai, có yêu cầu đồng ý lại không, thời điểm nào có hiệu lực. Backend tiếp tục quyết định quyền công bố, trạng thái và tính bất biến; UI không thay hàng rào quyền.

Các API hiện tại có dấu hiệu quản lý legal ở cấp nền tảng (`system_scope`). Nếu cần quy định riêng từng trường/tổ chức, đây là phần mở rộng schema/quyền cần thiết kế riêng; không chỉ đổi tiêu đề sang tên trường rồi coi đã có legal theo tenant.

## 4. Tenant: tổ chức phải là nơi làm việc rõ ràng

### Hai nhóm giao diện riêng

| Người dùng | Nên thấy trước | Giữ trong quản trị/nâng cao |
|---|---|---|
| Quản trị nền tảng | Tìm tổ chức, trạng thái, người phụ trách, yêu cầu chờ xử lý | Đổi tổ chức chính, gắn theo ID, xuất hệ thống, xóa vĩnh viễn |
| Quản trị trường/tổ chức | Tổng quan, thành viên, nhóm/lớp, hạn mức, quy định | Vai kỹ thuật và cấu hình chuyên sâu |
| Giáo viên | Lớp/nhóm của tôi, tài liệu hướng dẫn, nội dung được giao quyền | Cấu hình máy, SOT, khóa, schema |
| Học sinh/cộng đồng | Học và thực hành, nội dung được chia sẻ, hướng dẫn, lựa chọn riêng tư | Công cụ vận hành hoặc quyền quản trị không được cấp |

“Giáo viên” và “học sinh” là vai trò sản phẩm đề xuất, không tự ánh xạ thành `admin/editor/viewer`. Phải có bảng quyền rõ trước khi cấp quyền; chọn giao diện theo vai trò không tự cấp quyền API.

### Tổ chức đang làm việc

Luôn hiện **tên tổ chức + tên lớp/nhóm nếu có**, có nút đổi tổ chức dễ thấy. ID kỹ thuật nằm trong chi tiết. Phân biệt “tổ chức chính” và “tổ chức đang làm việc”.

Khi chuyển A → B: kiểm tra quyền bằng backend, chờ chuyển thành công, hủy/bỏ các response cũ, nạp lại dữ liệu và thông báo ngữ cảnh mới. Khi mở liên kết sâu, back/forward, refresh hoặc đổi tổ chức ở tab khác, phải kiểm tra ngữ cảnh lại. Đối với thao tác ghi, cần contract xác minh ngữ cảnh đích tại máy chủ để không có khoảng đua giữa kiểm tra và ghi; không lấy URL làm quyền.

“Về Cộng đồng” cũng cần quy định rõ có đổi ngữ cảnh hay chỉ mở trang chủ. Hiện liên kết về `/` không tự gọi chuyển tenant. Nếu trang tiếp tục ghi theo tổ chức đang hoạt động thì không được hứa dữ liệu sẽ vào Cộng đồng.

### Danh sách và thành viên

- Danh sách tổ chức có tìm kiếm, lọc trạng thái; tên hiển thị đứng trước mã. Trên điện thoại dùng thẻ tóm tắt có hành động “Mở tổ chức”.
- Trang chi tiết có các mục Tổng quan / Thành viên / Lời mời / Nhóm & lớp / Cài đặt. Khu vực xóa nằm riêng cuối Cài đặt, không đứng gần thao tác thường xuyên.
- Thêm người ưu tiên email/tìm tên nếu backend cho phép. ID chỉ ở lựa chọn nâng cao của quản trị nền tảng.
- Mời thành viên theo ba bước: người nhận → quyền cụ thể → xem lại. Nêu rõ quyền truy cập dữ liệu, không chỉ tên vai.
- Đổi quyền/gỡ thành viên có xác nhận nêu người và tổ chức. Không cấp quyền chỉ bởi vô tình chọn một mục trong dropdown.
- Phân biệt “không có dữ liệu”, “đang tải”, “không có quyền” và “mất kết nối”; mỗi phần có nút thử lại.

## 5. SOT: giữ chức năng kỹ thuật, thay cách diễn đạt

Tên đề xuất: **Dữ liệu chuẩn & đồng bộ**, kèm giải thích nhỏ: “Quản lý bản dữ liệu chuẩn và các máy được phép công bố bản đó”. Chỉ người vận hành phù hợp thấy mục này. Đây không phải nơi học sinh cần sử dụng.

Màn tổng quan trả lời:

1. Có truy cập được kho bản dữ liệu chuẩn không?
2. Có bản nào đã công bố, và đã kiểm tra tính toàn vẹn chưa?
3. Máy hiện tại có quyền công bố không?
4. Nếu có vấn đề, bước tiếp theo là gì?

Các trạng thái phải riêng biệt: đang kiểm tra, chưa kiểm tra, chưa có bản công bố, không kết nối được, không xác minh được nguồn, kiểm tra thành công. Có chữ, biểu tượng và thời điểm kiểm tra; không suy từ “Drive truy cập được” ra “dữ liệu đang dùng đã đồng bộ”. API hiện tại không đủ để khẳng định mọi máy đang dùng đúng cùng phiên bản.

| Cách hiện tại | Đề xuất |
|---|---|
| Verify SOT | Kiểm tra bản dữ liệu chuẩn |
| Version đã publish | Bản dữ liệu đã công bố |
| Máy ghi / Read-only | Có quyền công bố / Chỉ đọc |
| raw_uploads / samples / classes | Tệp ghi hình gốc / Mẫu dữ liệu / Nhãn |
| signed_by / fingerprint | Máy xác nhận nguồn; mã khóa trong “Chi tiết kỹ thuật” |
| schema / manifest / sha256 | Cấu trúc dữ liệu / Danh sách tệp / Mã kiểm tra; ẩn trong “Nâng cao” |

Các mục: **Tình trạng dữ liệu / Máy được cấp quyền / Lịch sử kiểm tra / Chi tiết kỹ thuật**. Lịch sử kiểm tra là tính năng mới nếu backend chưa lưu; không dựng lịch sử giả từ trạng thái hiện tại.

Đăng ký máy bằng wizard có giải thích ai cần làm, khóa công khai là gì, khóa riêng phải lưu ở đâu. Giữ lựa chọn quản lý khóa trên máy; không đổi kiến trúc ký số chỉ để giảm số ô nhập. Luồng tạo khóa một lần phải chống đóng nhầm và chỉ báo sao chép thành công sau khi trình duyệt xác nhận. Các thao tác công bố/nhập/thu hồi cần mô tả đúng tác động và xác nhận; không thêm nút “Đồng bộ ngay” nếu chưa xác định API thật và phạm vi dữ liệu bị thay đổi.

## 6. Trung tâm hướng dẫn và học tập

Đề xuất một điểm vào **Hướng dẫn & học tập** ở điều hướng chính, đồng thời đặt liên kết trợ giúp đúng ngữ cảnh tại màn hình đang thao tác. Người xem có thể chọn cách hướng dẫn phù hợp; lựa chọn này không suy ra hoặc lưu chẩn đoán khuyết tật.

### Ba đường bắt đầu

| Đường | Mục tiêu | Nội dung khởi đầu |
|---|---|---|
| Tôi là giáo viên | Tổ chức một buổi sử dụng nền tảng và hỗ trợ học sinh | Chuẩn bị thiết bị, vào đúng tổ chức, chọn nội dung phù hợp, hướng dẫn thực hành, xử lý lỗi |
| Tôi muốn học và thực hành | Biết cách xem mẫu và luyện theo từng bước | Chọn ngôn ngữ/phương ngữ, xem mẫu, xem chậm, thử lại, tự đánh dấu đã học |
| Tôi muốn tham gia cộng đồng | Tìm hiểu, đóng góp có hiểu biết, nhận hỗ trợ | Tìm nội dung, quyền riêng tư, chuẩn bị buổi đóng góp, gửi phản hồi |

Hướng dẫn thao tác phần mềm và bài học ngôn ngữ ký hiệu là hai loại nội dung khác nhau. Bài học cần giáo viên/chuyên gia/người sử dụng ngôn ngữ ký hiệu thẩm định; dữ liệu thu thập hay đầu ra mô hình chưa tự trở thành học liệu chuẩn.

### Mẫu một hướng dẫn thao tác

Tên theo việc cần làm; ai dùng; điều kiện trước khi bắt đầu; kết quả mong đợi; 3–7 bước ngắn; mỗi bước một hành động + hình/video minh họa + dấu hiệu làm đúng; lỗi thường gặp; cách quay lại; liên kết thao tác tương ứng. Có nút “Đã hiểu”, “Xem lại”, “Tôi cần hỗ trợ”; không ép đi hết tour khi đăng nhập.

Ưu tiên 10 hướng dẫn: bắt đầu; vào/đổi tổ chức; mời/tham gia nhóm; đọc quyền riêng tư và lựa chọn đồng thuận; chọn ngôn ngữ/phương ngữ; chuẩn bị camera; xem mẫu và thực hành; xử lý không nhận dạng được; đóng góp và xem lại mẫu; gửi yêu cầu hỗ trợ bằng văn bản. Nếu chức năng “giao bài/tạo lớp học” chưa có thực sự, không viết hướng dẫn như thể nó đã hoạt động.

### Mẫu một bài học thí điểm

**Mục tiêu → Xem mẫu đã duyệt → Quan sát các điểm cần chú ý → Thực hành → Tự ôn hoặc nhận phản hồi giáo viên.**

Mỗi học liệu có ngôn ngữ/phương ngữ, người biên soạn, người duyệt, phiên bản, quyền sử dụng video, mục tiêu và mức độ. Video không che mặt hoặc bàn tay bằng phụ đề; cho xem chậm, dừng và lặp đoạn. Các khác biệt phương ngữ được ghi rõ, không quy một biến thể duy nhất là đúng cho tất cả.

AI nhận dạng hiện tại chỉ hỗ trợ thực hành. Không biến độ tin cậy mô hình thành điểm học tập hay kết luận học sinh làm sai. Khi không chắc, dùng câu “Hệ thống chưa nhận ra; bạn có thể xem mẫu và thử lại” và có đường tiếp tục không cần AI/camera.

### Định dạng dễ tiếp cận

Thông tin quan trọng luôn có bằng chữ/hình, không chỉ âm thanh. Video có lời nói cần phụ đề được soát và nội dung chữ tương ứng; video ngôn ngữ ký hiệu được chọn theo nhu cầu ngôn ngữ thật của người học. Một số người cần đồng thời phụ đề và ký hiệu, theo [hướng dẫn W3C về sign languages](https://www.w3.org/WAI/media/av/sign-languages/). Không coi phụ đề tự động chưa duyệt là bản hoàn chỉnh; xem [W3C về media accessibility](https://www.w3.org/WAI/media/av/).

Các bước ngắn, chỉ rõ đang ở bước nào và còn gì tiếp theo, phù hợp [hướng dẫn W3C về các bước rõ ràng](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o1p04-clear-steps/). Đây là định hướng thiết kế dễ hiểu chung, không đồng nhất khiếm thính với khó khăn nhận thức.

Mục tiêu giao diện: chữ nội dung khoảng 16–18 px, giãn dòng dễ đọc, nút chính vùng chạm khoảng 44 px, focus rõ, trạng thái không chỉ bằng màu; kiểm tra tương phản và reflow thực tế. Hỗ trợ giảm chuyển động, không tự phát video có tiếng, không bắt buộc nhập giọng nói. Trên mạng yếu ưu tiên ảnh/ chữ và tải video theo yêu cầu.

### Dữ liệu và quyền riêng tư

MVP hướng dẫn công khai không cần lưu tiến độ cá nhân. Tiến độ học, giao bài và nhận xét giáo viên là giai đoạn sau, có quyền riêng và phân vùng tổ chức/lớp. Không đưa video luyện tập của học sinh vào tập huấn luyện hoặc chia sẻ cộng đồng theo mặc định.

Trước khi thử với học sinh chưa thành niên: xác định người chịu trách nhiệm, quy trình đồng thuận phù hợp, ai xem video, mục đích và thời hạn lưu, cách yêu cầu xóa. Đây là yêu cầu sản phẩm cần chốt với nhà trường/người phụ trách nội dung, không phải khẳng định hệ thống đã đáp ứng một quy định pháp lý cụ thể.

## 7. Các đợt thực hiện và điều kiện nghiệm thu

### Phác thảo bố cục để duyệt trước khi lập trình

Đây là wireframe đề xuất, không phải ảnh giao diện đã triển khai. Trên điện thoại, cột phụ thu thành nút “Mục lục” hoặc “Các mục”, không đẩy nội dung chính xuống sau một thanh điều hướng dài.

```text
QUYỀN RIÊNG TƯ & ĐIỀU KHOẢN
Điều khoản sử dụng          [Hiện hành] [Bản gốc]
Đơn vị ban hành · Phiên bản · Hiệu lực
┌───────────────────────────────────────────────┐
│ Những điều bạn cần biết                       │
│ • Bạn có quyền gì?                            │
│ • Dữ liệu được dùng vào việc gì?               │
│ • Bạn có thể thay đổi lựa chọn thế nào?        │
└───────────────────────────────────────────────┘
Mục lục       Nội dung đầy đủ / video giải thích
              Có gì thay đổi từ bản trước?
              [Xem lựa chọn của tôi] [Hỗ trợ]
```

```text
TỔ CHỨC: TRƯỜNG A          [Đổi tổ chức]
Bạn đang làm việc tại: Trường A › Nhóm/Lớp B
Tổng quan | Thành viên | Nhóm & lớp | Cài đặt
┌──────────────────────┬────────────────────────┐
│ Việc cần làm         │ Hướng dẫn bắt đầu       │
│ Lời mời / yêu cầu    │ 1. Chọn đúng tổ chức    │
│ được phép xem        │ 2. Xem quyền thành viên │
│                      │ 3. Mở công việc         │
└──────────────────────┴────────────────────────┘
[Mở công việc]   [Xem hướng dẫn dành cho giáo viên]
```

```text
DỮ LIỆU CHUẨN & ĐỒNG BỘ
Tình trạng | Máy được cấp quyền | Nâng cao
┌───────────────────────────────────────────────┐
│ [Biểu tượng + kết luận bằng chữ]              │
│ Kiểm tra lúc ... · Bản ... · Nguồn ...        │
│ Việc cần làm: ...                            │
│ [Kiểm tra bản dữ liệu chuẩn]                 │
└───────────────────────────────────────────────┘
Kho dữ liệu: ...       Máy hiện tại: Chỉ đọc
Chi tiết kỹ thuật ▸   Hướng dẫn vận hành ▸
```

```text
HƯỚNG DẪN & HỌC TẬP          [Tìm việc cần làm]
[Dành cho giáo viên] [Học & thực hành] [Cộng đồng]
Hướng dẫn bắt đầu       Nội dung mới / được duyệt
┌───────────────────────────────────────────────┐
│ Bài mẫu: mục tiêu · phương ngữ · người duyệt  │
│ Xem mẫu → Quan sát → Thực hành → Ôn lại       │
│ [Video rõ mặt và tay, phụ đề không che]       │
│ [Xem chậm] [Lặp đoạn] [Hướng dẫn bằng chữ]    │
│ [Bước tiếp theo]            [Cần hỗ trợ]      │
└───────────────────────────────────────────────┘
```

Ước lượng dưới đây là khoảng công sức cho một lập trình viên quen hệ thống, cộng thời gian thiết kế/duyệt nội dung. Không phải cam kết lịch; điều chỉnh sau kiểm tra bản chạy thật. Sản xuất video ký hiệu và thẩm định chuyên môn là đường công việc riêng.

| Đợt | Công việc | Kết quả bàn giao | Công sức dự kiến |
|---|---|---|---|
| 0 | Kiểm tra trực tiếp và chốt luồng | Ảnh desktop/mobile, trạng thái lỗi, bảng quyền thật, danh sách lỗi đã tái hiện | 1–2 ngày |
| 1 | TEN-01/02/03, LEG-01/02/03/05, SOT-01 | Luồng có trạng thái đúng; kiểm thử hồi quy tập trung | 3–5 ngày |
| 2 | Legal reader/admin và tenant UI | Màn hình theo nhiệm vụ, preview đầy đủ, ngữ cảnh rõ, mobile dùng được | 5–8 ngày |
| 3 | SOT và hướng dẫn theo ngữ cảnh | Tổng quan dễ hiểu, chi tiết kỹ thuật tách riêng, luồng khóa đáng tin | 3–5 ngày |
| 4 | Trung tâm hướng dẫn MVP | 10 hướng dẫn thao tác, 2–3 bài học mẫu được duyệt; không cần hệ thống giao bài | 5–8 ngày phát triển, nội dung tính riêng |
| 5 | Thử nghiệm người dùng và chỉnh | Báo cáo tác vụ, các lỗi cản trở đã giải quyết | 2–4 ngày làm việc, lịch người tham gia tính riêng |

Các đợt 2–4 phụ thuộc độ ổn định của đợt 1. Chỉ sau thí điểm mới quyết định đầu tư lớp học, giao bài, tiến độ và phân tích kết quả.

### Tiêu chí kỹ thuật

- Đổi tổ chức nhanh A/B, mở link sâu, F5, back/forward, hai tab: tên tổ chức và phạm vi dữ liệu nhất quán; chưa xác nhận ngữ cảnh thì không cho ghi.
- Không lặp gọi API do render; lỗi từng khối không trở thành empty state; response cũ không ghi đè dữ liệu mới.
- Một loại văn bản có một bản hiện hành theo contract; bản lịch sử mở đúng; preview PDF và file khác không trắng; chuyển route lỗi không hiện tài liệu cũ.
- Ngày hiệu lực giữ cùng thời điểm giữa trình duyệt/backend, kể cả máy có múi giờ khác.
- Modal thao tác bằng bàn phím, có nhãn/focus/đóng/khôi phục focus; kiểm tra 360, 390, 768 và 1440 px, phóng to 200%, reflow đến 320 CSS px khi phù hợp.
- SOT phân biệt lỗi kết nối/chưa có bản/chưa kiểm tra; sao chép thất bại không báo thành công; không mất khóa vì click ngoài.
- Chạy test tập trung cho phần thay đổi, typecheck, build và lint. Các con số 469 test xanh / 82 lint errors ở lượt trước là baseline, không phải kết quả của triển khai mới.

### Tiêu chí thử với người dùng

Đề xuất tuyển 3–5 giáo viên và 5–8 người học/thành viên cộng đồng theo nhu cầu ngôn ngữ/thiết bị khác nhau, có hỗ trợ giao tiếp phù hợp. Đây là thí điểm định tính, không đủ để suy rộng cho toàn bộ cộng đồng.

Tác vụ: tìm văn bản hiện hành; nói lại dữ liệu được dùng vào việc gì; vào đúng tổ chức; phân biệt mời người với đổi tổ chức chính; người vận hành đọc tình trạng SOT; giáo viên tìm hướng dẫn cho buổi học; người học hoàn thành một vòng xem mẫu–thực hành.

Mục tiêu ban đầu: ít nhất 80% hoàn thành các tác vụ thông thường không cần người quan sát hướng dẫn; không có thao tác ghi nhầm tổ chức, công bố nhầm hoặc mất khóa do giao diện. Ghi thời gian, số lần bấm sai, chỗ ngập ngừng và lý do; không chỉ hỏi “có đẹp không”. Với lỗi an toàn dữ liệu, bất kỳ trường hợp nào đều phải xử lý trước khi mở rộng thí điểm.

## 8. Kiểm tra bản chạy thật

Đang chuẩn bị môi trường theo yêu cầu người dùng. Lần mở `http://localhost:8080/login` ban đầu bị từ chối kết nối; `.env` hiện cấu hình cổng HTTP 80. Docker Desktop được yêu cầu khởi động; cần xác nhận engine và dịch vụ hoạt động trước khi đăng nhập.

Chưa ghi nhận kết quả đăng nhập, ảnh giao diện hoặc kết luận kiểm thử đa vai ở đây cho đến khi thực hiện được. Không lưu mật khẩu hay cookie phiên vào tài liệu này.
