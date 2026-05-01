# Training utilities

This folder contains helpers to load the dataset and a ready-to-run TCN trainer.

## Files
- `dataset_loader.py`: Loads `.npz` feature sequences with metadata and provides a padding collate.
- `run_loader_sanity.py`: Prints a few samples from `train_model/processed/splits/train.csv` to verify shapes.
- `train_tcn.py`: Trains a Temporal Convolutional Network (TCN) classifier on the splits.

## Prerequisites
- Python 3.10+ (khuyến nghị) để cài dependency ổn định nhất.
- Nếu bạn chỉ train từ feature `.npz` đã có sẵn thì Python 3.8 vẫn chạy được code, nhưng nhiều wheel (numpy/matplotlib/mediapipe) có thể không còn hỗ trợ đầy đủ.
- `numpy`
- `torch` (CPU or CUDA build that matches your environment)

## Cài đặt an toàn (khuyến nghị)

Nguyên tắc:
- Không cài global vào Windows.
- Tạo 1 virtualenv riêng cho training.
- Dùng requirements đã pin version để tránh “vỡ” môi trường.

Tạo venv (chạy từ repo root):

```powershell
py -3.10 -m venv .venv-train
.\.venv-train\Scripts\activate
python -m pip install --upgrade pip
```

Cài dependency train (không gồm torch):

```powershell
pip install -r train_model/requirements-train.txt
```

Cài torch:
- CPU (an toàn/dễ nhất):

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

- CUDA: lấy đúng lệnh theo máy bạn tại https://pytorch.org/get-started/locally/

Kiểm tra môi trường:

```powershell
python -c "import numpy, torch; print('numpy', numpy.__version__); print('torch', torch.__version__)"
pip check
```

Gỡ venv khỏi session:

```powershell
deactivate
```

```powershell
pip install numpy
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

If you have CUDA, refer to https://pytorch.org/get-started/locally/ for the correct command.

## Dataset expectations
- App dữ liệu nằm ở `<repo>/dataset/`:
	- `dataset/labels.csv`
	- `dataset/samples/samples.csv`
	- `dataset/features/.../*.npz` (mỗi sample 1 file, key chính là `sequence`)
- Splits sẽ được sinh ra ở `train_model/processed/splits/{train,val,test}.csv`.
- Optional label maps ở `train_model/processed/analysis/{label_to_index.json,index_to_label.json}`.

## Quick checks
Tạo splits từ dataset hiện tại (chạy từ repo root):

```powershell
python train_model/splits/make_splits.py
```

Sau đó chạy sanity để chắc loader đọc được `.npz` và CSV:

```powershell
python train_model/train_utils/run_loader_sanity.py
```

## Train a TCN
Default settings work well for this dataset size and sequence length (~60 frames):

```powershell
python train_model/train_utils/train_tcn.py --epochs 80 --batch_size 32 --dropout 0.3 --channels 64 --levels 3 --kernel_size 5
```

Key flags:
- `--train_csv --val_csv --test_csv`: Override split paths if needed.
- `--device`: `cuda` or `cpu` (auto-detects if CUDA is available).
- `--out_dir`: Output directory for checkpoints and metrics (default `train_model/processed/train_utils/outputs`).

Outputs:
- `tcn_YYYYMMDD_HHMMSS.pt`: Checkpoint with model state and config.
- `tcn_YYYYMMDD_HHMMSS.json`: Summary with config and final test metrics.

## Train per dialect (export one model per subset)
If you want a model that only targets a specific sign-language subset (e.g. `bac`, `nam`, `hoa-de`, `cần thơ`), you can filter by the `dialect` column in the split CSVs.

Example (North / miền Bắc):

```powershell
python train_model/train_utils/train_tcn.py --dialect bac --epochs 80 --batch_size 32
```

This run will:
- Filter `train/val/test` rows to `dialect=bac`
- Build a *local* label mapping (so class indices are contiguous, macro-F1 is meaningful)
- Export files like:
	- `tcn_dialect-bac_YYYYMMDD_HHMMSS.pt`
	- `tcn_dialect-bac_YYYYMMDD_HHMMSS.json`

Notes:
- Default behavior is unchanged when you omit `--dialect`.
- Subset label maps are written under `train_model/processed/train_utils/outputs/subset_<tag>_<timestamp>/` and the checkpoint stores the path in `label_to_index_json`.

## Notes
- The trainer applies masked global average pooling over time to handle variable-length inputs.
- Early stopping monitors validation macro-F1 with patience 10.
- Learning rate uses cosine annealing; adjust `--epochs` to change schedule length.
