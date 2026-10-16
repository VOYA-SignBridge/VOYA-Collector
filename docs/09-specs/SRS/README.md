# SRS — CTU.SignBridge (VOYA-Collector)

*Đặc tả yêu cầu phần mềm (Software Requirements Specification), viết theo cấu trúc
IEEE 830 rút gọn — cùng bộ đề mục với bản SRS mẫu được dùng làm khuôn.*

**Ngày lập:** 17/08/2026 · **Phiên bản:** 1.0 · **Nhánh mã nguồn:** `deploy_ctu_ver-2.2.1`

---

## 1. Bộ tệp

| # | Tệp | Đề mục tương ứng trong khuôn mẫu |
|---|---|---|
| 01 | [01_PRODUCT_FUNCTIONS.md](01_PRODUCT_FUNCTIONS.md) | Product Functions |
| 02 | [02_USER_CLASSES_AND_CHARACTERISTICS.md](02_USER_CLASSES_AND_CHARACTERISTICS.md) | User Classes and Characteristics |
| 03 | [03_OPERATING_ENVIRONMENT.md](03_OPERATING_ENVIRONMENT.md) | Operating Environment |
| 04 | [04_DESIGN_AND_IMPLEMENTATION_CONSTRAINTS.md](04_DESIGN_AND_IMPLEMENTATION_CONSTRAINTS.md) | Design and Implementation Constraints |
| 05 | [05_EXTERNAL_INTERFACE_REQUIREMENTS.md](05_EXTERNAL_INTERFACE_REQUIREMENTS.md) | Specific Requirements → External Interface Requirements (User / Hardware / Software / Communications Interfaces) |
| 06 | [06_NONFUNCTIONAL_REQUIREMENTS.md](06_NONFUNCTIONAL_REQUIREMENTS.md) | Nonfunctional Requirements (Performance · Reliability · Safety and Security · Adaptability and Portability) |
| 07 | [07_BUSINESS_RULES.md](07_BUSINESS_RULES.md) | Business Rules |
| 08 | [08_SOFTWARE_DESIGN_ARCHITECTURE.md](08_SOFTWARE_DESIGN_ARCHITECTURE.md) | Software Design → Application Architecture |
| 09 | [09_DATA_DESIGN_AND_DICTIONARY.md](09_DATA_DESIGN_AND_DICTIONARY.md) | Software Design → Data Design (CDM · mô hình logic · ba miền dữ liệu · hai mặt phẳng lưu trữ) |
| DD | [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md) | **Data Dictionary — quy ước 5 cột + mục lục**, trích từ CSDL đang chạy 18/08/2026 |
| DD.1 | [DD_01_M1_DANH_TINH.md](DD_01_M1_DANH_TINH.md) | M1 Danh tính & Truy cập — 7 bảng, 56 cột |
| DD.2 | [DD_02_M2_TO_CHUC.md](DD_02_M2_TO_CHUC.md) | M2 Tổ chức & Phân quyền — 9 bảng, 97 cột |
| DD.3 | [DD_03_M3_KHO_MAU.md](DD_03_M3_KHO_MAU.md) | M3 Kho dữ liệu mẫu — 6 bảng, 112 cột |
| DD.4 | [DD_04_M4_DANH_MUC.md](DD_04_M4_DANH_MUC.md) | M4 Danh mục & Registry — 11 bảng, 75 cột |
| DD.5 | [DD_05_M5_HUAN_LUYEN.md](DD_05_M5_HUAN_LUYEN.md) | M5 Huấn luyện & Mô hình — 3 bảng, 33 cột |
| DD.6 | [DD_06_M6_DICH_VU.md](DD_06_M6_DICH_VU.md) | M6 Dịch vụ tổ chức & Tích hợp — 11 bảng, 134 cột |
| DD.7 | [DD_07_M7_PHAP_LY.md](DD_07_M7_PHAP_LY.md) | M7 Pháp lý, Kiểm toán & Nền tảng — 10 bảng, 115 cột |
| 10 | [10_DETAILED_DESIGN.md](10_DETAILED_DESIGN.md) | Detailed Design — **mục lục** + khung trình bày + bản đồ màn hình ↔ nghiệp vụ |
| 10.1 | [10_1_DETAILED_DESIGN_NV1.md](10_1_DETAILED_DESIGN_NV1.md) | NV1 Danh tính và quyền truy cập — 9 chức năng, UC101–UC114 |
| 10.2 | [10_2_DETAILED_DESIGN_NV2.md](10_2_DETAILED_DESIGN_NV2.md) | NV2 Thu thập và quản lý dữ liệu mẫu — 7 chức năng, UC201–UC213 |
| 10.3 | [10_3_DETAILED_DESIGN_NV3.md](10_3_DETAILED_DESIGN_NV3.md) | NV3 Danh mục từ vựng và phương ngữ — 6 chức năng, UC301–UC310 |
| 10.4 | [10_4_DETAILED_DESIGN_NV4.md](10_4_DETAILED_DESIGN_NV4.md) | NV4 Huấn luyện, đánh giá và suy luận — 9 chức năng, UC401–UC409 |
| 10.5 | [10_5_DETAILED_DESIGN_NV5.md](10_5_DETAILED_DESIGN_NV5.md) | NV5 Tổ chức và đăng ký dịch vụ — 4 chức năng, UC501–UC508 |
| 10.6 | [10_6_DETAILED_DESIGN_NV6.md](10_6_DETAILED_DESIGN_NV6.md) | NV6 Quản trị người dùng và chính sách — 5 chức năng, UC601–UC609 |
| 10.7 | [10_7_DETAILED_DESIGN_NV7.md](10_7_DETAILED_DESIGN_NV7.md) | NV7 Vận hành hệ thống và nguồn sự thật — 5 chức năng, UC701–UC706 |
| 10.8 | [10_8_DETAILED_DESIGN_NV8.md](10_8_DETAILED_DESIGN_NV8.md) | NV8 Hỗ trợ và tích hợp — 5 chức năng, UC801–UC806 |

## 2. Quy ước trung thực — đọc trước khi trích dẫn

Bản SRS này mô tả **hệ thống đang chạy**, không mô tả hệ thống mong muốn. Vì vậy
mọi phát biểu mang một trong ba trạng thái sau, và **ba trạng thái không suy ra
lẫn nhau**:

| Ký hiệu | Nghĩa |
|:--:|---|
| **✓ Đã cài đặt** | Có mã, có đường chạy thật, kiểm chứng được từ bên ngoài (điểm cuối API, màn hình, lệnh vận hành) |
| **△ Một phần** | Có cơ chế nhưng còn khoảng trống đã biết; khoảng trống được nêu đích danh ngay tại chỗ |
| **○ Chưa cài đặt** | Có mô hình dữ liệu hoặc có thiết kế, **chưa** có bề mặt vận hành. Không được đọc là "sắp có" |

Ba quy tắc bổ sung, áp dụng cho toàn bộ bộ tệp:

1. **Số liệu phải có ngày chụp.** Số hàng trong cơ sở dữ liệu, số dòng mã, độ phủ
   — tất cả thay đổi theo ngày. Con số không kèm ngày là con số không kiểm chứng
   được.
2. **Phép đo khác bộ kiểm thử.** Bộ kiểm thử trả lời *"có hồi quy không"*; phép
   đo trả lời *"tỉ lệ là bao nhiêu"*. Chỉ số liệu từ phép đo có đối chứng dương
   mới được đưa vào phần Nonfunctional.
3. **Giới hạn nêu tại chỗ, không dồn xuống cuối.** Mỗi mục tự nêu điều nó không
   chứng minh được.

## 3. Nguồn dữ liệu của bản SRS

| Nguồn | Dùng cho |
|---|---|
| `docs/00-thesis/quyen/02_CHUONG1_MO_TA_BAI_TOAN.md` | Chức năng, tác nhân, yêu cầu phi chức năng, ràng buộc |
| `docs/00-thesis/quyen/04_CHUONG3_THIET_KE_VA_CAI_DAT.md` | Kiến trúc ứng dụng, thiết kế dữ liệu, thiết kế chức năng |
| `docs/00-thesis/quyen/PHU_LUC_A_MO_HINH_DU_LIEU.md` | Từ điển dữ liệu, độ phủ cách ly |
| `docs/00-thesis/quyen/PHU_LUC_B_CAI_DAT_HE_THONG.md` | Môi trường vận hành, quy trình triển khai |
| `docs/09-specs/USE_CASE_SPECIFICATION.md` | Mã use case UC101–UC806 |
| `docs/00-thesis/MEASUREMENT_*.md` / `.json` | Số liệu hiệu năng, hiệu quả lưu trữ, toàn vẹn nguồn sự thật |
| `frontend/src/App.tsx`, `frontend/src/pages/`, `frontend/src/components/` | Danh sách màn hình và thành phần giao diện |
| `backend/requirements.txt`, `frontend/package.json`, `docker-compose*.yml` | Công nghệ và phiên bản |

## 4. Phạm vi của bản SRS

Đối tượng đặc tả là **nền tảng CTU.SignBridge** ở mức toàn hệ thống. Riêng phần
được luận văn thiết kế và đánh giá là **phân hệ thu thập và quản lý dữ liệu**;
các thành phần huấn luyện và nhận dạng có mặt trong SRS vì chúng là bên tiêu thụ
dữ liệu ở hạ nguồn và có ảnh hưởng tới yêu cầu giao diện, chứ không phải vì luận
văn đánh giá chất lượng mô hình.
