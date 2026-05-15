# Realtime sign recognition

This demo loads the latest TCN checkpoint and runs realtime recognition from a webcam (or a video file) using MediaPipe Hands to extract features compatible with training (126 dims: left 21x3 + right 21x3).

## Install

Activate your venv, then install deps from the repo root:

```powershell
pip install -r processed/requirements-realtime.txt
```

This runtime also needs PyTorch and NumPy, and they are included in `processed/requirements-realtime.txt`.

## Run

- Webcam:
```powershell
python processed/realtime/run_realtime.py
```
- Video file:
```powershell
python processed/realtime/run_realtime.py --video path/to/video.mp4
```
- Use a specific checkpoint:
```powershell
python processed/realtime/run_realtime.py --checkpoint processed/train_utils/outputs/tcn_YYYYMMDD_HHMMSS.pt
```

Keys: press `q` to quit.

## Notes
- The script expects model input dim = 126; a warning is shown if different. Adjust extractor if your training features differ.
- It applies a sliding window (default 60 frames) and EMA smoothing of logits.
- Labels are read from `train_model/processed/analysis/index_to_label.json` for display.

## Debounce / ổn định nhãn

Để giảm nhảy nhãn ở đầu stream (và khi model chưa chắc), realtime dùng cơ chế “debounce”:

- Chỉ **chốt/switch nhãn** khi model dự đoán **cùng một nhãn** với độ tự tin `--confidence_threshold` **liên tiếp `--stable_frames` lần**.
- Nếu bạn dùng `--every > 1` (chỉ inference mỗi N frame), thì “liên tiếp” ở đây là **liên tiếp các lần inference**, nên số frame tương đương xấp xỉ $stable\_frames \times every$.
- `--hold_frames` giữ nhãn thêm một số frame khi confidence giảm/tạm mất tín hiệu.
