# ExecuTorch mobile export

Pipeline này xuất checkpoint PyTorch của VOYA sang ExecuTorch `.pte` để ứng
dụng mobile có thể nhận diện ngay trên thiết bị, không cần gọi API server.
Hiện pipeline hỗ trợ TCN, HD-GCN/HandGCN và model ASL tĩnh.

Với HD-GCN, input mobile là `float32[1,60,126]`: 60 frame, mỗi frame gồm
21 landmark tay trái và 21 landmark tay phải, mỗi landmark có `(x,y,z)`.
Output là logits `float32[1,num_classes]`.

## Vì sao dùng môi trường riêng

Môi trường train hiện tại dùng PyTorch 2.6 + CUDA. ExecuTorch 1.4.1 cần
PyTorch mới hơn, vì vậy không nâng cấp Python global. Docker image bên dưới chỉ
dùng CPU để export và kiểm tra parity; training vẫn dùng CUDA như trước.

## 1. Train checkpoint mới

Chạy từ repo root:

```powershell
python -m processed.train_utils.train_tcn --epochs 80 --batch_size 32
```

Checkpoint mới phải có 39 lớp. Script export mặc định sẽ từ chối checkpoint cũ
4 lớp.

## 2. Dùng virtualenv riêng trên Windows

Thiết lập một lần:

```powershell
py -3.12 -m venv .venv-executorch
.\.venv-executorch\Scripts\python.exe -m pip install --upgrade pip
.\.venv-executorch\Scripts\python.exe -m pip install -r processed/mobile/requirements-executorch.txt
```

Export, thay tên checkpoint trong lệnh:

```powershell
.\.venv-executorch\Scripts\python.exe `
  -m processed.mobile.export_executorch `
  --checkpoint processed/train_utils/outputs/tcn_YYYYMMDD_HHMMSS.pt `
  --output processed/mobile/artifacts/voya_tcn_fp32.pte `
  --verify-samples 64
```

Không cần activate virtualenv và không thay đổi môi trường CUDA dùng để train.

### Xuất model HD-GCN/HandGCN

Kiến trúc HD-GCN cần để dựng lại checkpoint đã được lưu trong
`processed/mobile/models`. Vì vậy lệnh export không còn phụ thuộc repo HandGCN
khác:

```powershell
.\.venv-executorch\Scripts\python.exe `
  -m processed.mobile.export_handgcn_executorch `
  --checkpoint path\to\handgcn_checkpoint.pt `
  --output processed\mobile\artifacts\voya_handgcn_fp32.pte `
  --verify-samples 64
```

Kết quả gồm đúng bộ file gửi cho ứng dụng mobile:

- `.pte`: model ExecuTorch để tích hợp vào Android/iOS.
- `_labels.json`: ánh xạ nhãn phẳng, ví dụ `{"0": "A", "1": "Â"}`.
- `_metadata.json`: input/output shape, preprocessing contract, phiên bản,
  checksum và kết quả so sánh với model PyTorch.

Không dùng trường `idx_to_label` giàu thông tin trong metadata để hiển thị nhãn
trên mobile. Mobile nên đọc `_labels.json` để tránh nhầm object nhãn với chuỗi.

Exporter chỉ nhận checkpoint có `model_type` là `HandGCN`, `HD-GCN` hoặc
`HDGCN`, load trọng số bằng `strict=True`, rồi yêu cầu dự đoán top-1 của
PyTorch và ExecuTorch giống nhau 100% trên các mẫu kiểm tra.

`--source-root` chỉ còn dùng để kiểm tra tương thích với một repo HandGCN cũ;
quy trình thông thường không cần tham số này.

## 3. Docker (tùy chọn)

```powershell
docker build -t voya-executorch processed/mobile
```

Sau khi image build thành công, export và kiểm tra parity:

Thay tên checkpoint trong lệnh:

```powershell
docker run --rm `
  -v "${PWD}:/workspace" `
  -w /workspace `
  voya-executorch `
  python -m processed.mobile.export_executorch `
  --checkpoint processed/train_utils/outputs/tcn_YYYYMMDD_HHMMSS.pt `
  --output processed/mobile/artifacts/voya_tcn_fp32.pte `
  --verify-samples 64
```

Lệnh tạo hai file:

- `voya_tcn_fp32.pte`: model dùng trên mobile.
- `voya_tcn_fp32.json`: shape, label map, checksum và kết quả parity.

Export chỉ thành công khi dự đoán top-1 của PyTorch và ExecuTorch giống nhau
100% trên các mẫu kiểm tra.

## Smoke test bằng checkpoint cũ

Chỉ để kiểm tra hạ tầng, có thể thêm `--allow-class-mismatch`. Không đưa model
4 lớp này vào ứng dụng thật.
