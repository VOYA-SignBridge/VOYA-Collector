# Kiểm kê nguồn dataset và định danh người ký

> Trạng thái kiểm tra: 2026-10-14  
> Phạm vi: nhánh `son_arrange_repo`, commit `5fc9c33`

## 1. Kết luận ngắn

- Dataset thật **không nằm trong checkout này**. Thư mục `dataset/` chỉ còn các file khóa (`*.lock`).
- `.gitignore` loại toàn bộ `dataset/`, `*.csv`, `*.npz` và `gdrive/`; đây là chủ ý để không commit dữ liệu lớn và thông tin xác thực.
- `config/legacy_signer_mapping.json.bak_20260727_204104` là **mapping lịch sử**, không phải sổ signer hiện hành. Không xóa và cũng không đổi tên nó thành file canonical.
- Bản mapping mới nhất tìm thấy trong Git nằm ở commit `5d177dd` trên nhánh deploy. Đây là ứng viên tốt nhất để đối chiếu, nhưng chưa đủ an toàn để chép thẳng sang nhánh này khi chưa kiểm tra dataset ngoài repo và bảng PostgreSQL `signers`.
- Code coi `dataset/signers.csv` và bảng PostgreSQL `signers` là registry hiện hành. Tuy nhiên `signers.csv` chưa từng được track trong lịch sử Git đang thấy và code hiện chỉ mirror `samples.csv`, `labels.csv`, `raw_uploads.csv` lên Drive, không mirror `signers.csv`.

## 2. Trạng thái nguồn dữ liệu

| Nguồn | Trạng thái khi kiểm tra | Vai trò |
|---|---|---|
| `dataset/signers.csv` | Không có cục bộ, không có trong lịch sử Git đang thấy | Registry signer dự kiến của ứng dụng |
| PostgreSQL `signers` | Chưa đọc được vì Docker Engine không chạy | Bản mirror registry signer |
| Drive `samples.csv` / `samples2.0.csv` | Dataset ngoài repo; chưa được cung cấp/kết nối trong phiên kiểm tra | Catalog sample, có `user_id` và `signer_id` để đối chiếu |
| `config/legacy_signer_mapping.json.bak_20260727_204104` | Có trong nhánh hiện tại | Mapping cũ cho dữ liệu/manifest lịch sử |
| `config/legacy_signer_mapping.json` ở commit `5d177dd` | Có trong nhánh deploy | Mapping đã được cập nhật ngày 2026-09-15 để khớp registry production lúc đó |

Trong `.env`, `USE_GOOGLE_DRIVE=0`; không có `gdrive/credentials.json` hoặc `gdrive/token.json`. Vì vậy ứng dụng ở checkout này không thể tự đọc file trên Drive. Giá trị `GOOGLE_DRIVE_ROOT_FOLDER_ID=signbridge-storage` chỉ là cấu hình tên/ID, không phải bằng chứng rằng dữ liệu đã được tải về.

## 3. Hai thế hệ signer ID

Các thay đổi quan trọng giữa file `.bak` và mapping ngày 2026-09-15:

| Người ký | Mapping lịch sử | Mapping mới hơn ở deploy |
|---|---:|---:|
| Trân / Tran / trân | `S001` | `S015` |
| Minh / minh | `S002` | `S014` |
| Khoa | `S013` | `S002` |
| Huy | Chưa có | `S001` |
| Khang | Chưa có | `S016` |
| Trâm và biến thể | Chưa có trong file `.bak` | `S003` |
| Thu Ngân và biến thể | Chưa có trong file `.bak` | `S006` |
| Thư | Chưa có | `S008` |

Các ID `S010` và `S011` là ID tài khoản thu thập dùng chung, **không được coi là danh tính người ký**. Với dữ liệu cũ, phải ưu tiên `user_id` (tên người ký thật) rồi tra mapping phù hợp với thời điểm tạo manifest.

Mapping mới cũng ghi rõ:

- Trân và Trâm là hai người khác nhau.
- Minh và Huy tạm thời là hai người khác nhau.
- Manifest/split tạo trước 2026-09-15 vẫn mang ID cũ và phải được giải nghĩa bằng mapping lịch sử.

Do đó, thay mapping cũ bằng mapping mới trên toàn bộ dữ liệu sẽ làm sai các split signer-disjoint/LOSO cũ.

## 4. File tối thiểu cần lấy để xác minh dataset trên Drive

Không cần đưa toàn bộ video/NPZ vào Git. Trước tiên chỉ cần bản sao chỉ-đọc của metadata:

1. `samples2.0.csv` nếu Drive đang dùng suffix `2.0`; nếu không có thì lấy `samples.csv`.
2. `signers.csv` nếu file này được lưu thủ công trên Drive dù code không tự mirror nó.
3. Nếu không có `signers.csv`, xuất bảng PostgreSQL `signers` với sáu cột: `signer_id`, `display_name`, `regional_group`, `external_user_id`, `is_active`, `created_at`.
4. Các manifest/split đang thực sự dùng để train, đặc biệt file tạo trước và sau 2026-09-15.

Không cần credential/token Drive trong repo. Có thể đặt các bản export metadata vào một thư mục tạm ngoài Git hoặc cung cấp qua kết nối Drive chỉ-đọc.

## 5. Quy trình đối chiếu an toàn

1. Lập tập duy nhất của `(user_id, signer_id)` từ catalog sample trên Drive.
2. Đối chiếu `signer_id` với `dataset/signers.csv` hoặc bảng `signers` theo `external_user_id`; không ghép người chỉ vì tên gần giống nhau.
3. Đánh dấu mọi sample dùng `S010`/`S011` và suy danh tính thật từ `user_id` theo mapping lịch sử.
4. Phân loại manifest theo thời điểm/phiên bản mapping: trước 2026-09-15 dùng bảng cũ; manifest mới dùng registry mới.
5. Báo các trường hợp một tên trỏ nhiều ID, một ID trỏ nhiều tên, ID không có trong registry, hoặc thiếu `user_id`.
6. Chỉ sau khi báo cáo không còn mâu thuẫn mới tạo `config/legacy_signer_mapping.json` canonical và test lại quá trình dựng manifest/LOSO.

## 6. Snapshot dataset local được cung cấp

Đã kiểm tra chỉ-đọc tại `D:\VOYA\VOYA-Collector\dataset` ngày 2026-10-14:

- `features/` có 3.516 file NPZ (khoảng 153,5 MB), 1.794 sidecar `sample_*.json` và 39 file metadata cấp class.
- NPZ mẫu tuân theo contract chính: `sequence` và `landmarks_normalized` có shape `(60, 126)`, dtype `float32`; ngoài ra có raw landmarks và các validity mask. `meta.npy` là object array nên không được nạp từ nguồn không tin cậy với `allow_pickle=True`.
- Catalog cũ nằm tại `dataset/samples/samples.csv`, gồm 3.468 dòng, 39 class và 13 giá trị `user_id`. Code hiện tại lại đọc `dataset/samples.csv`, vì vậy mount/copy nguyên trạng sẽ không làm ứng dụng thấy catalog này.
- Catalog không có cột `signer_id`. Sidecar có signer ID, nhưng phần lớn mang `S010` hoặc `S011` là ID tài khoản thu thập dùng chung; danh tính thật phải lấy từ `user_id`.
- 3.443 dòng catalog trỏ được tới NPZ local. Có 25 dòng cùng mang storage key sai `features/vn/hoa-de/class_cat-ky_cab3132f/view`; cả 25 file thật đều tồn tại và có thể phục hồi đường dẫn một cách xác định từ `sample_uid`.
- Phép so ban đầu báo 73 NPZ không có trong catalog; 25 file thuộc nhóm lỗi đường dẫn trên. Sau khi trừ nhóm đó còn 48 orphan thật sự: 45 file của chín class `can-tho` không có sidecar và 3 file class chữ `z` có sidecar của Hoàng Anh. Chưa xóa chúng trước khi xác định provenance.
- Có 1.722 NPZ không có sidecar JSON. Đây chưa chắc là file rác: có thể là augmentation hoặc artifact sinh ở phiên bản pipeline khác, nên chưa được xóa.

Dataset local này đủ để dựng baseline và kiểm tra pipeline, nhưng phải làm trên bản staging/read-only hoặc qua manifest mới; không chỉnh trực tiếp bản mà các thành viên đang coi là nguồn dữ liệu.

## 7. Quyết định cleanup hiện tại

- **Giữ** `config/legacy_signer_mapping.json.bak_20260727_204104` và đổi vai trò của nó thành bằng chứng mapping lịch sử; không coi hậu tố `.bak` là lý do đủ để xóa.
- **Không commit** dataset thật, token, credential hoặc file NPZ/video.
- **Không chạy** script merge/migrate signer trước khi có metadata từ Drive và registry production.
- Sau khi đối chiếu xong, nên đổi tên có chủ đích thành `config/legacy_signer_mapping.pre_2026_09_15.json` trong một commit riêng, đồng thời thêm mapping hiện hành và test. Việc đổi tên chưa được thực hiện trong lần kiểm tra này.

