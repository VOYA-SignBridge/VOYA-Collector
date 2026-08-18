# PHỤ LỤC D: BỘ CA KIỂM THỬ CHI TIẾT

*Chương 4 §5.1 trình bày các ca kiểm thử đại diện. Phụ lục này chứa bộ đầy đủ,
tổ chức theo nhóm, kèm ánh xạ tới tệp kiểm thử thật trong mã nguồn — để mỗi dòng
trong bảng đều truy được về mã đang chạy.*

---

## 1. Quy ước đọc

| Cột | Nội dung |
|---|---|
| **Mã** | `TC<nghiệp vụ><thứ tự>` |
| **Tiền điều kiện** | Trạng thái hệ thống trước khi chạy ca |
| **Dữ liệu vào / Hành động** | Thứ được cấp cho hệ thống |
| **Kết quả mong đợi** | Hợp đồng mà ca này ghim |
| **Tệp kiểm thử** | Nơi ca này sống trong mã nguồn |

**Trạng thái tổng.** Ở **lượt chạy đầy đủ ngày 17/08/2026**, mọi ca dưới đây đều
**Đạt**: 2.550 xanh / 0 đỏ / 1 bỏ qua trên 2.551 ca thu thập, 20 ph 49 s, trên
bản sao cơ sở dữ liệu sản xuất. Cột kết quả vì thế được lược bỏ để bảng đọc được.

Lượt chạy ấy **không xanh ngay từ đầu**: nó bắt đầu với 6 ca đỏ và một lượt chạy
không hoàn tất được. Toàn bộ quá trình đưa về xanh — gồm hai lỗi ở mã sản xuất và
một bất biến tĩnh thêm mới để chặn tái diễn — ghi ở Chương 4 §6.4, và đó là phần
đáng đọc hơn con số 0 đỏ.

**Nguyên tắc "mỗi khẳng định trung tâm có một phản chứng"** thể hiện trong bộ ca
này thành các cặp: một ca khẳng định "chủ sở hữu làm được", một ca khẳng định
"người khác không làm được". Đọc riêng một vế là đọc sai.

---

## 2. Nhóm A — Cách ly tổ chức ở tầng cơ sở dữ liệu

Đây là nhóm ghim đóng góp lõi của luận văn.

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCA01 | Hai tổ chức có dữ liệu | Truy vấn bảng mẫu **không đặt ngữ cảnh tổ chức** | **0 hàng** — không phải mọi hàng | `test_tenant_isolation.py` |
| TCA02 | Ngữ cảnh = tổ chức A | `DELETE FROM samples` **không điều kiện** | Chỉ chạm dữ liệu của A; dữ liệu của B nguyên vẹn | `test_tenant_isolation.py` |
| TCA03 | Ngữ cảnh = tổ chức A | Ghi một hàng mang định danh tổ chức B | Bị mệnh đề kiểm ghi chặn | `test_tenant_isolation.py` |
| TCA04 | Hai tổ chức thật, có dữ liệu hai chiều | Đọc chéo theo **cả hai chiều** | Mỗi chiều đều bị chặn | `test_two_tenant_proof.py` |
| TCA05 | — | Kiểm thuộc tính của vai chạy ứng dụng | **Không** có quyền vượt chính sách; **không** có quyền thay đổi cấu trúc | `test_db_role_isolation.py` |
| TCA06 | — | Thử phát lệnh vô hiệu hoá chính sách bằng vai ứng dụng | Bị từ chối | `test_db_role_isolation.py` |
| TCA07 | Danh sách bảng chịu ranh giới tổ chức | Kiểm khoá ngoại của từng bảng | Mọi bảng có khoá ngoại mang định danh tổ chức | `test_tenant_foreign_keys.py` |
| TCA08 | Cùng một kết nối | Yêu cầu của tổ chức A, rồi tới yêu cầu của tổ chức B | Ngữ cảnh **không rò** sang yêu cầu sau | `test_tenant_isolation.py` |
| TCA09 | Lược đồ hiện hành | So sánh hình dạng lược đồ với khai báo | Khớp; không có bảng hay cột lệch | `test_schema_shape.py` |
| **TCA09b** | Lược đồ hiện hành | Đối chiếu **danh sách bảng mang định danh tổ chức** với **thứ tự dọn dữ liệu tổ chức** | Mọi bảng mang định danh tổ chức đều có trong thứ tự dọn | `test_schema_shape.py::test_tenant_purge_order_covers_every_tenant_table` — đỏ 17/08/2026 vì thiếu `training_metrics`, **đã vá** |
| TCA10 | Lược đồ có sẵn **dữ liệu** | Chạy lệnh di trú | Đúng trên bảng đã có dữ liệu, không chỉ trên bảng trống | `test_schema_backfill.py` |
| TCA11 | — | Chạy lệnh di trú **hai lần liên tiếp** | Lần hai không đổi gì — tính lũy đẳng của lệnh di trú | `test_schema_evolution.py` |

**Ghi chú về TCA05.** Đây là ca dễ bị bỏ qua nhất và nguy hiểm nhất nếu thiếu:
nếu bộ kiểm thử chạy dưới vai siêu người dùng, **mọi ca cách ly khác đều cho kết
quả "đạt" giả**, vì cơ sở dữ liệu miễn trừ chính sách vô điều kiện cho vai đó.
TCA05 vì thế là **điều kiện tiên quyết** của cả nhóm A, không phải một ca ngang
hàng.

---

## 3. Nhóm B — Xác thực, phân quyền và cổng truy cập

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCB01 | — | Liệt kê toàn bộ điểm cuối, đối chiếu danh sách công khai | Bề mặt công khai **thật** khớp danh sách khai báo | `test_access_gate.py` |
| TCB02 | — | Kiểm các đường công khai | **Không** đường công khai nào có tham số đường dẫn | `test_access_gate.py` |
| TCB03 | Có tài khoản | Đăng ký tự phục vụ | Tài khoản **không** rơi vào tổ chức mồi — ba mắt xích, mỗi mắt một ca | `test_signup_no_longer_lands_in_bootstrap.py` |
| TCB04 | Có tài khoản | Sai mật khẩu nhiều lần từ một IP | Hoãn tăng dần theo cặp (tài khoản, IP) | `test_login_rate_limit.py` |
| TCB05 | Có tài khoản | Kẻ khác cố tình sai mật khẩu để khoá tài khoản đó | **Không khoá được** tài khoản của người khác | `test_login_rate_limit.py` |
| TCB06 | Đăng nhập nhiều thiết bị | Đăng xuất một thiết bị | Chỉ phiên đó bị thu hồi | `test_tokens.py` |
| TCB07 | Đăng nhập nhiều thiết bị | Đổi mật khẩu | **Mọi** phiên bị thu hồi | `test_tokens.py` |
| TCB08 | — | Kiểm cookie phiên | Cờ chỉ-máy-chủ được đặt; có cơ chế chống giả mạo yêu cầu | `test_cookie_auth.py` |
| TCB09 | — | Sinh mã một lần | Mã lưu **dạng băm**, có hạn, dùng một lần | `test_otp.py` |
| TCB10 | Tài khoản chưa xác thực địa chỉ | Thao tác cần địa chỉ đã xác thực | Bị chặn | `test_email_verification_gate.py` |
| TCB11 | — | Yêu cầu đặt lại mật khẩu với tiêu đề máy chủ giả mạo | Liên kết chỉ trỏ tới máy chủ trong danh sách cho phép | `test_password_reset.py` |
| TCB12 | Khách vãng lai | Dùng thử vượt số phút mỗi ngày | Bị từ chối kèm giới hạn | `test_trial_and_sudo.py` |
| TCB13 | Đã đăng nhập | Thao tác không hoàn tác được, **chưa** xác thực lại | Bị từ chối; cửa sổ nâng quyền có hạn | `test_trial_and_sudo.py` |
| TCB14 | — | Gửi tiêu đề địa chỉ IP do phía gọi tự đặt | **Không** ảnh hưởng bộ đếm — chỉ tin tiêu đề từ proxy trong danh sách | `test_client_ip.py` |
| TCB15 | — | Gửi tải trọng quá lớn, đầu vào lạ | Bị từ chối trước khi vào tầng nghiệp vụ | `test_security_hardening.py` |
| TCB16 | Bật xác thực hai yếu tố | Nhập mã sinh theo **vector thử của tiêu chuẩn** | Chấp nhận đúng theo tiêu chuẩn, không chỉ "đăng nhập được" | `test_two_factor.py` |

## 4. Nhóm C — Nhật ký kiểm toán

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCC01 | — | Thực hiện một thao tác quản trị | Để lại dấu vết ở **cả hai** tầng ghi | `test_audit_log.py` |
| TCC02 | Ghi kiểm toán **không có phạm vi** | — | **Từ chối ghi** — fail-closed | `test_audit_log.py` |
| TCC03 | Hành động qua khoá API | — | Vẫn ghi được nhật ký | `test_audit_log.py` |
| TCC04 | Cơ sở dữ liệu không phản hồi | Ghi sự kiện bảo mật | Nhánh ghi còn lại **không** bị kéo theo | `test_audit_log.py` |
| TCC05 | Có bản ghi kiểm toán | Đọc qua API | Đúng hình dạng; lọc theo tiền tố; mới nhất trước; chỉ quản trị viên đọc được | `test_admin_audit_api.py` |
| TCC06 | Thực hiện một lượt dọn dữ liệu thật | Đọc nhật ký | Để lại một dòng đọc được | `test_admin_audit_api.py` |

## 5. Nhóm D — Pháp lý và đồng thuận

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCD01 | Có văn bản đã công bố | Chấp thuận | Ghi nhận **đúng phiên bản** đã ký, không phải phiên bản hiện hành | `test_legal_consent.py` |
| TCD02 | Có bản đã công bố | Sửa nội dung dưới **cùng số hiệu phiên bản** | Từ chối ở tầng cơ sở dữ liệu | `test_legal_consent.py` |
| TCD03 | Tài khoản đã ký bản cũ | Đọc trạng thái đồng thuận | Phân biệt **"đã ký bản cũ"** với **"chưa ký bao giờ"** | `test_legal_consent.py` |
| TCD04 | — | Đọc cờ cho phép rút | Khớp **hành vi thật** của máy chủ, không phải một hằng số ở giao diện | `test_legal_consent.py` |
| TCD05 | Có bản thảo đã duyệt | Công bố **không** nâng quyền | Từ chối, và **không ghi gì** | `test_legal_admin_api.py` |
| TCD06 | Công bố thành công | Đọc sổ kiểm toán | Sổ mang **mã băm nội dung**, không mang bản văn | `test_legal_admin_api.py` |
| TCD07 | Có lịch sử chấp thuận | Đọc | **Không lộ** mã băm địa chỉ IP | `test_legal_admin_api.py` |
| TCD08 | — | Lưu thân văn bản | Tên tệp là **mã băm nội dung**; nội dung trùng thì khử trùng lặp | `test_legal_store.py` |
| TCD09 | Có blob không còn tham chiếu | Dọn rác | Chỉ dọn khi **cả hai** điều kiện đúng: không còn tham chiếu **và** đủ tuổi | `test_legal_store.py` |
| TCD10 | Hai luồng cùng ghi một bản thảo | — | Tranh chấp được xử lý đúng — kiểm bằng **hai luồng thật** | `test_legal_drafts.py` |
| TCD11 | — | Chạy công cụ ghi bù chấp thuận không tham số | **Không ghi gì** — chế độ mặc định là không tác động | `test_backfill_consents.py` |
| TCD12 | — | Chạy công cụ ghi bù có tham số áp dụng | Đòi ghi chú lý do; dòng ghi ra **tự nhận là ghi hộ**; không đè lên chữ ký thật | `test_backfill_consents.py` |

**Ghi chú về TCD11–TCD12.** Một công cụ ghi bù dữ liệu pháp lý mà mặc định **ghi**
là một công cụ nguy hiểm. Mặc định không tác động, và bản ghi sinh ra phải tự
khai là do máy ghi hộ — nếu không, sáu tháng sau sẽ không ai phân biệt được một
chấp thuận thật với một chấp thuận suy ra.

## 6. Nhóm E — Thương mại và vòng đời tổ chức

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCE01 | Gói có hạn mức **rỗng** | Ghi vượt mọi ngưỡng | Cho phép — rỗng nghĩa là **không giới hạn** | `test_plans_and_quotas.py` |
| TCE02 | Gói có hạn mức cụ thể | Chạm trần | Trả mã từ chối vì hạn mức | `test_plans_and_quotas.py` |
| TCE03 | — | Đọc hạn mức | Đọc từ **bảng nguồn**, không từ bộ đếm | `test_plans_and_quotas.py` |
| TCE04 | Tổ chức quá hạn thanh toán | Ghi dữ liệu | **Cho phép** — trạng thái thương mại tách khỏi trạng thái quản trị | `test_tenant_lifecycle.py` |
| TCE05 | — | Xuất dữ liệu tổ chức | Chỉ chứa dữ liệu của tổ chức đó | `test_tenant_lifecycle.py` |
| TCE06 | — | Dọn sạch dữ liệu tổ chức | Đòi **ba chốt chặn** trước khi thực hiện | `test_tenant_lifecycle.py` |
| TCE07 | Có hoạt động trong ngày | Đọc số đo mức dùng | Khớp hoạt động thực tế | `test_tenant_lifecycle_and_usage.py` |
| TCE08 | — | Tạo khoá API | Lưu **mã băm**; giá trị khoá hiện đúng một lần | `test_api_keys_and_webhooks.py` |
| TCE09 | Có điểm nhận webhook | Gửi sự kiện | Chữ ký gồm **mốc thời gian** — chống phát lại | `test_api_keys_and_webhooks.py` |
| TCE10 | Điểm nhận hỏng liên tục | Gửi nhiều lần | Có lịch thử lại; **tự tắt** sau chuỗi lỗi | `test_api_keys_and_webhooks.py` |
| TCE11 | — | Quét cây cú pháp mã nguồn | Mọi sự kiện được **khai báo** đều có chỗ **phát thật** | `test_webhook_event_wiring.py` |

**Ghi chú về TCE11.** Đây là dạng kiểm thử bắt được lớp lỗi "khai báo mà quên nối
dây" — thứ không kiểm thử hành vi nào bắt được, vì hành vi ấy chưa bao giờ được
kích hoạt.

## 7. Nhóm F — Dữ liệu, xử lý và huấn luyện

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCF01 | Có tệp video thật | Trích đặc trưng | Ra chuỗi đúng số khung × 126 chiều | `test_video_pipeline.py` |
| TCF02 | — | Trích qua **hai đường** (webcam và tệp) | Cho **cùng** không gian toạ độ | `test_normalization_parity.py` |
| TCF03 | Chuỗi không có bàn tay | Chấm chất lượng | Độ đầy đủ = 0, **và điều đó khác với tệp rỗng** | `test_quality.py` |
| TCF04 | — | Áp phép tăng cường | **Không phá cấu trúc hình học** bàn tay | `test_augmentation_geometry.py` |
| TCF05 | Dữ liệu nhiều người ký | Chia tập | Cùng một người **không** nằm ở cả tập huấn luyện lẫn tập kiểm thử | `test_signer_disjoint_split.py` |
| TCF06 | Có lớp dưới sàn số mẫu | Chia tập | Lớp bị loại **trước** khi đánh chỉ số lớp | `test_split_safety.py` |
| TCF07 | — | Dựng bản kê bộ dữ liệu | Bản kê tái lập được tập đã dùng | `test_manifest.py` |
| TCF08 | Tải lên tệp video | — | **Bản thô ghi trước** mọi bước chuẩn hoá | `test_raw_archive.py` |
| TCF09 | Tác vụ huấn luyện | Chạy vòng đời đầy đủ | Trạng thái chuyển đúng; chỉ số phát theo chu kỳ | `test_training_lifecycle.py` |
| TCF10 | Tác vụ huấn luyện thất bại | — | **Thông báo tới chủ sở hữu tác vụ** | `test_training_notifies_owner.py` |
| TCF11 | Có mô hình mới | Thăng hạng | Bản cũ bị thay đúng cách; đường phục vụ nạp bản mới | `test_promotion_supersede.py` |
| TCF12 | Có hiện vật đã đóng băng | Sửa | Bị từ chối | `test_frozen_artifacts.py` |
| TCF13 | Tổ chức thiếu một mục danh mục | Truy vấn mục đó | **Dừng** — không có đường dự phòng âm thầm về mặt phẳng cộng đồng | `test_registry_planes.py` |
| TCF14 | Danh mục đã đổi sau khi ghim | Đọc bộ dữ liệu đã ghim | Đọc được **nội dung cũ** | `test_vocabulary_registry.py` |
| TCF15 | Lớp trùng nhãn, **khác vùng miền** | Đăng ký | **Chấp nhận** — vùng miền là một phần định danh lớp | `test_vocabulary_v2.py` |
| TCF16 | Tác vụ huấn luyện của tổ chức A | Tổ chức B đọc | Bị chặn | `test_c3_job_read_confinement.py` |
| TCF17 | Chỉ số huấn luyện của tổ chức A | Tổ chức B đọc | Bị chặn | `test_c3_metric_ownership.py` |
| TCF18 | Hiện vật đầu ra của tổ chức A | Tổ chức B truy cập qua đường lưu trữ | Bị chặn | `test_c3_storage_confinement.py` |
| **TCF19** | Bảng chỉ số huấn luyện | Chèn một hàng **không có** định danh tổ chức | Bị ràng buộc từ chối | `test_schema_constraints.py::test_training_metrics_cannot_orphan_itself` — đỏ 17/08/2026 vì ca kiểm thử còn chèn theo lược đồ cũ, **đã vá** |

## 8. Nhóm G — Nguồn sự thật ký số

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCG01 | Bản công bố hợp lệ | Đồng bộ | Chấp nhận | `test_sot_*.py` |
| TCG02 | Đổi **một byte** trong tạo tác sau khi ký | Đồng bộ | Từ chối | `test_sot_*.py` |
| TCG03 | Sửa mã băm trong bản kê, giữ chữ ký cũ | Đồng bộ | Từ chối | `test_sot_*.py` |
| TCG04 | Chữ ký hợp lệ, **người ký không được tin cậy** | Đồng bộ | Từ chối | `test_sot_*.py` |
| TCG05 | Thiếu chữ ký khi chính sách đòi ký | Đồng bộ | Từ chối | `test_sot_*.py` |
| TCG06 | Bản công bố **chỉ bổ sung** | Đồng bộ | Giữ nguyên hàng đã có trên máy chủ — **chỉ điền, không xoá** | `test_sot_*.py` |
| TCG07 | — | Kiểm danh sách cột bắt buộc | Danh sách phủ **đủ** các cột mà bước nhập sẽ ghi | `test_sot_*.py` |
| TCG08 | Máy phát hành khác | Ký bằng khoá đã đăng ký | Kết quả xác minh trả về **tên khoá**, không phải giá trị đúng/sai | `test_sot_*.py` |

**Một ca cố ý không có trong bộ kiểm thử: hồi quy phiên bản.** Nó nằm ở phép đo
(Chương 4 §5.5, kịch bản S7) chứ không ở bộ kiểm thử, vì kết quả của nó là một
**giới hạn đã biết** chứ không phải một hợp đồng đang được giữ. Đặt nó vào bộ
kiểm thử sẽ buộc phải viết một khẳng định mô tả hành vi hiện tại như thể đó là
hành vi mong muốn.

## 9. Nhóm H — Vận hành

| Mã | Tiền điều kiện | Hành động | Kết quả mong đợi | Tệp |
|---|---|---|---|---|
| TCH01 | — | Ghi nhật ký có chứa dữ liệu nhạy cảm | **Mã bí mật không bao giờ vào nhật ký** | `test_logging_config.py` |
| TCH02 | — | Đọc chỉ số phát ra | Đúng định dạng; có chỉ số cho các cảnh báo đã dựng | `test_observability.py` |
| TCH03 | Đĩa gần đầy | — | Phát cảnh báo trước khi đầy | `test_disk_watermark.py` |
| TCH04 | Khởi động trên cơ sở dữ liệu trống | — | Dựng đủ lược đồ; nợ lược đồ rỗng | `test_init_db_fallback.py` |
| TCH05 | Phiên bản lược đồ lệch | Khởi động dịch vụ | **Từ chối khởi động** — cả khi cũ hơn lẫn khi mới hơn | `test_deploy_fixes.py` |
| TCH06 | Có dữ liệu cần đối soát | Chạy đồng bộ đầu vòng đời | Nguồn sự thật và bản sao khớp nhau | `test_startup_sync*.py` |

## 10. Nhóm I — Giao diện

**58 tệp** kiểm thử, **429 ca** đếm tĩnh (17/08/2026; đếm bằng mẫu `it(` / `test(`
ở đầu dòng — con số này **chưa** phải số ca đã chạy xanh). Các nhóm chính:

| Nhóm | Ghim gì |
|---|---|
| Điều hướng và phân quyền hiển thị | Trang chỉ dành cho một vai không hiện với vai khác |
| Biểu mẫu | Kiểm tra đầu vào, thông báo lỗi, trạng thái gửi |
| Trạng thái tải và trạng thái rỗng | "Đang xử lý" là một trạng thái **hợp lệ**, không phải lỗi |
| Đa ngôn ngữ | Không có chuỗi cứng; đổi ngôn ngữ có hiệu lực trên mọi màn |
| Câu chữ về giới hạn | **Ghim đúng câu chữ** của thông báo "thu hồi không xoá khỏi lưu trữ" |

**Kiểm kiểu là một cổng riêng**, không phải phần phụ của kiểm thử: nó bắt được
loại lỗi mà bộ chạy kiểm thử không bắt — ví dụ một lời gọi bất đồng bộ đặt trong
hàm cập nhật trạng thái, thứ chạy được trong kiểm thử nhưng sai về ngữ nghĩa.

---

## 11. Sáu dạng "đỏ giả" và cách phân định

Một bộ kiểm thử hay đỏ vì lý do ngoài mã sẽ nhanh chóng bị bỏ qua. Sáu dạng dưới
đây đã gặp thật, và mỗi dạng có một dấu hiệu phân định.

| # | Dạng | Dấu hiệu phân định | Cách xử lý |
|---|---|---|---|
| 1 | **Đĩa đầy** | Kiểm thử đồng bộ đỏ, lan sang nhóm không liên quan | Kiểm dung lượng trước khi điều tra mã |
| 2 | **Khẳng định bằng phép trừ trên CSDL có sẵn dữ liệu** | Ca đỏ khi chạy cùng ca khác, xanh khi chạy riêng | Khẳng định theo bản ghi cụ thể, không theo hiệu số đếm |
| 3 | **Thiếu số hiệu chấp thuận khi đăng ký** | Sáu ca đỏ ở ba tệp, đều trả mã 400 | Cập nhật dữ liệu dựng của kiểm thử |
| 4 | **Kiểm thử ghi vào dữ liệu thật** | Dữ liệu sản xuất thay đổi sau lượt chạy | **Bản sao cơ sở dữ liệu không che được đường ghi tệp** — cần chốt chặn riêng |
| 5 | **Cả hạ tầng đã tắt** | Hàng loạt lỗi "không phân giải được tên máy chủ" | Kiểm hạ tầng trước |
| 6 | **Hạ tầng biến mất GIỮA CHỪNG** | 208 lỗi trông y hệt một hồi quy lớn, nhưng dạng thông báo lỗi giống dạng 5 | Phân định bằng dạng thông báo, rồi chạy lại từ đầu |
| 7 | **Đứng rất lâu vì test gọi ra dịch vụ ngoài** | Lượt chạy **đứng yên** ở một tỉ lệ phần trăm; **CPU của container gần bằng 0**; bên trong container có kết nối HTTPS mở ra ngoài | Đặt lại thời hạn và số lần thử của khách hàng dịch vụ ngoài cho lượt chạy kiểm thử |

**Dạng 7 — cách chẩn đoán và nguyên nhân thật.** Gặp ngày 17/08/2026: lượt chạy
đứng ở 62 % suốt hơn mười phút. Hai dấu hiệu phân định một **lượt bị chặn** với
một **lượt chạy chậm**:

1. **Mức chiếm CPU của container** — đo được 0,43 %. Một lượt chạy chậm vẫn tốn
   CPU; một lượt treo thì không.
2. **Các kết nối đang mở bên trong container** — bảng kết nối cho thấy một kết
   nối HTTPS **đang mở tới một địa chỉ ngoài** (cổng 443). Đó là câu trả lời:
   tiến trình không tính toán gì, nó đang **chờ mạng**.

Cách này trả lời được câu mà việc đọc nhật ký không trả lời được: pytest ở chế độ
gọn chỉ in một dấu chấm cho mỗi ca **đã xong**, nên ca đang treo **không bao giờ
xuất hiện trong nhật ký** — nhìn nhật ký sẽ tưởng lỗi nằm ở ca kế tiếp.

**Bài học chung:** một ca kiểm thử gọi ra mạng ngoài mà **không đặt thời hạn** thì
không chỉ tự hỏng — nó **giữ con tin toàn bộ lượt chạy**, và giữ theo cách không
sinh ra thông báo nào. Đây là lý do tệp tích hợp mạng phải nằm ngoài lượt chạy hồi
quy mặc định, chứ không phải vì nó hay đỏ.

**Nguyên nhân không nằm ở một tệp kiểm thử, mà ở hai giá trị mặc định nhân với
nhau.** Cấu hình khách hàng kho lưu trữ ngoài:

```
GOOGLE_DRIVE_TIMEOUT_SECONDS   mặc định 180
GOOGLE_DRIVE_NUM_RETRIES       mặc định   5
                               ─────────────
   một lượt gọi không tới đích  tối đa 900 giây = 15 phút
```

Nên lượt chạy **không hề treo** — nó đang chờ đúng như được cấu hình. Hai giá trị
ấy hợp lý cho một tác vụ nền tải tệp lớn, và **vô lý cho một lượt chạy kiểm thử**:
mỗi lượt gọi hụt đích tiêu tốn nhiều thời gian hơn cả phần còn lại của bộ kiểm thử
cộng lại.

**Bài học đáng giữ:** giá trị mặc định của một khách hàng dịch vụ ngoài là thứ
được chọn cho **đường chạy sản xuất**, và nó theo nguyên xi vào môi trường kiểm
thử vì không ai nghĩ tới việc đặt lại. Cách xử lý đúng là hạ thời hạn và số lần
thử cho lượt chạy kiểm thử, chứ không phải loại dần từng tệp — loại tệp là chữa
triệu chứng, và triệu chứng sẽ mọc lại ở tệp tiếp theo có gọi ra ngoài. Thực tế đã
đúng như vậy: loại trừ `test_sot_integration.py` — tệp duy nhất mà tài liệu quy
trình cảnh báo — thì lượt chạy dừng lại ở **đúng cùng một mốc 62 %**.

Hai lưu ý về công cụ, cùng thuộc loại "trông như đang kiểm nhưng không kiểm gì":

* **Đừng nối lệnh cắt bớt đầu ra vào một lượt chạy nền** — nó làm mất phần đầu
  của báo cáo, chính là chỗ ghi số ca thu thập được.
* **Lệnh kiểm kiểu mặc định thường dùng kiểm không tệp nào** với cấu hình của dự
  án này, và vẫn thoát thành công. Một lần quét mã từng giấu **14 lỗi kiểu** sau
  lỗ hổng đó. Dùng lệnh kiểm kiểu của dự án.

---

## 12. Ba lớp lỗi mà bộ kiểm thử đã bắt được

Đưa vào phụ lục vì đây là bằng chứng thực chất hơn con số "0 đỏ": một bộ kiểm thử
chỉ có giá trị nếu nó **từng bắt được lỗi thật**.

| Lỗi | Triệu chứng khi dùng bình thường | Ai bắt được |
|---|---|---|
| Lược đồ dựng trên máy mới thiếu **2 bảng, 7 khoá ngoại, 14 cột** | **Không có triệu chứng** — mọi máy mới nhận lược đồ yếu hơn trong im lặng | Nền chạy thứ hai (22 ca đỏ) |
| **Ba hàm truy vấn thiếu điều kiện lọc theo tổ chức** | Không có triệu chứng cho tới khi có tổ chức thứ hai | Rà soát + nhóm ca TCA |
| **Sáu cột thiếu** trong danh sách kiểm bản công bố | Bản công bố lược đồ thiếu **qua được** khâu xác minh, rồi hỏng giữa chừng lúc nhập | Nhóm ca TCG07 |
| **Rò mã băm mật khẩu** qua đường trả về của API | Không có triệu chứng | Nhóm ca TCB |
| **Dọn dữ liệu tổ chức để sót bảng chỉ số huấn luyện** | Không có triệu chứng — thao tác báo thành công, dữ liệu còn nguyên | `test_schema_shape.py::test_tenant_purge_order_covers_every_tenant_table`, 17/08/2026 |

Năm lỗi này đều thuộc loại **không sinh triệu chứng khi dùng bình thường** — và
đó chính là loại lỗi mà một bộ kiểm thử đáng có mặt để bắt.

**Lỗi cuối bảng đáng nói riêng**, vì nó cho thấy một ca kiểm thử được thiết kế
đúng sẽ bắt lỗi ở đâu. Ca `test_tenant_purge_order_covers_every_tenant_table`
không kiểm một hành vi; nó kiểm một **bất biến giữa hai danh sách**: mọi bảng mang
định danh tổ chức phải có mặt trong thứ tự dọn dữ liệu tổ chức. Nhờ vậy, khoảnh
khắc một bảng được gắn cột định danh tổ chức mà quên đưa vào danh sách dọn, ca này
đỏ ngay — kể cả khi chưa ai từng chạy thao tác dọn. Một ca kiểm thử hành vi thông
thường sẽ không bao giờ bắt được điều đó, vì đường dọn **vẫn chạy xong và vẫn báo
thành công**.

Thông báo lỗi của ca này còn nói luôn cách sửa đúng: *"thêm vào đúng vị trí phụ
thuộc — nối vào cuối sẽ hỏng vì con phải đi trước cha"*. Đó là chuẩn mực đáng theo
cho mọi ca kiểm thử bất biến: nêu **cái sai**, và nêu **cách sửa không tạo ra lỗi
mới**.
