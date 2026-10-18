# Capture, quyền dữ liệu và export — 23/09/2026

## Quyết định đã chốt

- `private`: chỉ tài khoản đóng góp được xem, không có ngoại lệ admin/editor.
- Chủ phiên là người được đổi visibility. Không tự chuyển dữ liệu cũ sang public.
- Quyền sửa cả lần quay phải kiểm **mọi mẫu**, không chỉ mẫu gốc: `session_id` do client gửi có thể trùng giữa hai người.
- Thư viện nhãn JSON/CSV là **danh mục**, không phải tập đặc trưng để train.
- Xuất cá nhân là gói NPZ đầy đủ; thiếu/hỏng/sai checksum thì job thất bại, không công bố ZIP thiếu mẫu.
- Xuất toàn bộ tổ chức bị chặn khi chứa private của người khác (kể cả metadata). Đây là chặn rõ ràng, không phải tự lọc và báo gói đầy đủ. Backup vận hành ở cấp host là quyền hạ tầng riêng, vẫn cần lưu an toàn.

## Các đường đã sửa

Danh sách phiên thu và phiên legacy; thư viện lần quay; frames/provenance/preview/MP4; tải NPZ; danh sách thùng rác; hàng đợi/quyết định kiểm duyệt; đặt hàng/chạy/tải gói xuất tổ chức. Viewer và tệp tải dùng `private, no-store` để không tiếp tục phục vụ cache mới sau khi thu hồi chia sẻ.

Dữ liệu cũ thiếu chủ sở hữu hoặc thiếu liên kết phiên không được suy đoán là public. Mẫu có thể bị ẩn theo quy tắc mới, **không bị xóa**. Các bản đã tải/cache trước bản vá không thể thu hồi từ xa.

## Mang dữ liệu sang máy khác

Vào **Đóng góp dữ liệu → Tải dữ liệu của tôi**, tạo gói và chờ `ready`. Giải nén trên máy có cùng phiên bản repo và dependencies train. Gói gồm `samples.csv`, `samples.json`, `labels.json`, `manifest.json`, `files/*.npz`, `README.txt`.

```python
import json
from pathlib import Path
from processed.train_utils.dataset_loader import NPZSignDataset

root = Path("/path/to/extracted-export")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
dataset = NPZSignDataset(
    root / "samples.csv", root=root,
    class_uid_to_target_idx=manifest["class_uid_to_target_idx"],
    to_tensor=True,
)
```

Không cần DB/Drive của máy nguồn để đọc NPZ. Mapping target liên tục từ 0, giữ `class_uid` để đối chiếu nhãn. NPZ được giữ nguyên byte, kể cả raw landmarks nếu có. Gói hiện cần tệp NPZ **local**; cloud-only thiếu local sẽ báo lỗi, không tải một gói thiếu.

Phải chia train/val/test theo người ký/phiên **trước** huấn luyện; không tách mẫu gốc và augment của cùng phiên sang các tập khác nhau. Gói không tự tạo split, không đảm bảo đủ lớp/người ký và không phải checkpoint model. CSV giữ nguyên nội dung cho máy đọc; khi mở bằng bảng tính, nhập cột nhãn dưới dạng text.

## Bằng chứng kiểm thử

- `test_portable_export.py`: giải nén sang thư mục mới, xóa NPZ nguồn, kiểm SHA-256, nạp bằng loader thật và chạy forward/loss/backward/Adam của TCN. Đây là mô phỏng đổi máy bằng relocation, chưa phải chạy trên máy vật lý thứ hai.
- Test capture/upload kiểm contract, tenant, hierarchy, định dạng video và nối dữ liệu train. Một số bước camera/MediaPipe/Celery được giả lập; không coi đây là chứng nhận camera vật lý.
- Test quyền gồm mixed-owner session, admin không đọc private, thay visibility có hiệu lực với truy vấn mới, chặn file download trực tiếp và tenant export.
- Sidebar giữ nguyên route/quyền, chia Dữ liệu/Công cụ/Cá nhân, hàng 44px, focus bàn phím, Escape, drawer mobile và chỉ một mục active ở Cài đặt/Hỗ trợ. Không thêm thư viện. Test component và build đã chạy; chưa đo Lighthouse/WCAG hoặc kiểm trực quan trên điện thoại thật.

## Giới hạn trước khi deploy

- Chưa deploy/rebuild container đang phục vụ người dùng trong lượt này.
- Cần smoke test camera và upload video thật trên bản đã rebuild, bằng tài khoản chủ mẫu, người khác và admin.
- Không tuyên bố toàn bộ suite/project đều sạch từ một nhóm test. Lượt full frontend trước đó có lỗi ngoài nhóm đang sửa; phải chạy lại toàn bộ cổng CI trước release.
- Quyền trên snapshot/split/model hoặc gói đã tạo từ phiên bản cũ cần audit riêng trước khi hứa privacy toàn hệ thống. Bản vá không xóa artifact, không thu hồi bản đã tải và không tự huấn luyện lại model.
- Quyền cấp host/DB/backup không phải mã hóa đầu-cuối chống người vận hành máy chủ.
