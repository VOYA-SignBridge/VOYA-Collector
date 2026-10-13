# Công cụ training

Các script trong thư mục này chuẩn bị split, chạy thí nghiệm và xác nhận rằng
artifact training có thể tái lập. Chúng không phục vụ HTTP request trực tiếp.

| File | Chức năng | Tác dụng phụ đáng chú ý |
|---|---|---|
| `export_augmentation_contract.py` | Xuất cấu hình augmentation đang dùng thành JSON/Markdown để nghiên cứu có thể truy vết | Ghi artifact vào `reports/` |
| `make_loso_splits.py` | Tạo fold leave-one-signer-out hoặc matched protocol | Tạo CSV và metadata trong `processed/splits/` |
| `run_loso_experiment.py` | Lần lượt gọi trainer cho các fold/seed chưa chạy | Chạy nhiều tiến trình training, tạo checkpoint và result |
| `run_feature_ablation.sh` | Chạy ba cấu hình feature trên GPU trong container | Tốn GPU; ghi log/checkpoint vào `reports/feature_ablation/` |
| `verify_checkpoint_contract.py` | Kiểm tra checkpoint có đủ metadata và tương thích feature/dataset | Chủ yếu chỉ đọc |
| `verify_determinism.py` | Train lặp lại để kiểm tra cùng seed có cho kết quả giống nhau | Chạy training và ghi báo cáo/checkpoint tạm |
| `verify_loso_splits.py` | Kiểm tra người test không lọt vào train/val và matched split giữ đúng bất biến | Chỉ đọc các CSV split |

Ví dụ:

```powershell
python scripts/training/make_loso_splits.py --help
python scripts/training/verify_loso_splits.py --help
```

Các script bắt đầu bằng `run_` hoặc `verify_determinism.py` có thể chạy lâu và
dùng nhiều CPU/GPU. Hãy đọc `--help` và chọn output riêng trước khi chạy.

