# Training utilities

This folder contains helpers to load the dataset and a ready-to-run TCN trainer.

## Files
- `dataset_loader.py`: Loads `.npz` feature sequences with metadata and provides a padding collate.
- `run_loader_sanity.py`: Prints a few samples from `processed/splits/train.csv` to verify shapes.
- `train_tcn.py`: Trains a Temporal Convolutional Network (TCN) classifier on the splits.
- `models/hd_gcn_lite.py`: HD-GCN variant with direct `nn.Linear` graph projections; keeps the original graph, pooling, temporal convolutions and attention.
- `export_tflite.py`: Exports an in-memory trained model directly using `litert_torch.convert(model.eval(), sample_inputs)` and `edge_model.export(...)`.

## HD-GCN Lite: direct TFLite output

Once a compatible Linux LiteRT Torch environment has been prepared separately:

```bash
python -m processed.train_utils.train_tcn --model_type hdgcn_lite --epochs 80 --batch_size 32
```

The existing trainer prerequisites still apply, including valid splits and the
pinned vocabulary registry snapshot (`VOCABULARY_REGISTRY_PATH` when needed).

Uses the same split/data arguments and graph hyperparameters as `hdgcn`.
Training restores the best validation state **in memory**, then exports float32
`handgcn_lite_*.tflite` directly. No intermediate `.pt` is written. Outputs also
include `.metadata.json` (class mapping, preprocessing/training contract, model
configuration and conversion parity checks) and the usual training `.json` summary.
The graph returns logits; preprocessing remains external and must match training.
Export shape is fixed to `[1, 60, input_dim]`, normally `[1, 60, 126]`.

To export a model from your own training code:

```python
from processed.train_utils.models import HandGCNLiteModel
from processed.train_utils.export_tflite import export_tflite

model = HandGCNLiteModel.from_config(126, num_classes, model_config)
# Train model here and restore your best in-memory state_dict, if applicable.
export_tflite(model, "handgcn_lite.tflite", sample_input=preprocessed_clip)
```

`preprocessed_clip` must be a float tensor of shape `[1, 60, 126]`. Constructing
the model alone does not train it. The exporter copies the model to CPU/eval,
checks PyTorch/TFLite output parity before writing, and leaves the caller's model
unchanged. Architecture construction/training imports no LiteRT dependency.
There is no claim of a smaller model or better accuracy than original HD-GCN.

This is currently a **CLI training/export path**. The web training job tracker,
promotion and realtime loader still consume PyTorch checkpoints; deploying a
TFLite artifact there requires separate runtime integration. The TFLite final
record uses `artifact_path` and leaves `checkpoint_path` empty intentionally.

Official conversion/environment documentation:
https://github.com/google-ai-edge/litert-torch
and https://github.com/google-ai-edge/litert-torch/blob/main/docs/pytorch_converter/README.md

Checks that need only the existing PyTorch environment:

```bash
python -m unittest processed.train_utils.test_hd_gcn_lite -v
```

The real conversion/reload test is skipped if `litert_torch` is absent. Exporter
test doubles verify control flow only and do not prove TFLite compatibility.

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

Cài dependency train:

```powershell
pip install -r processed/requirements-train.txt
```

Nếu cần cài riêng PyTorch CPU:

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
- Splits sẽ được sinh ra ở `processed/splits/{train,val,test}.csv`.
- Optional label maps ở `processed/analysis/{label_to_index.json,index_to_label.json}`.

## Quick checks
Tạo splits từ dataset hiện tại (chạy từ repo root):

```powershell
python processed/splits/make_splits.py
```

Sau đó chạy sanity để chắc loader đọc được `.npz` và CSV:

```powershell
python processed/train_utils/run_loader_sanity.py
```

## Train a TCN
Default settings work well for this dataset size and sequence length (~60 frames):

```powershell
python processed/train_utils/train_tcn.py --epochs 80 --batch_size 32 --dropout 0.3 --channels 64 --levels 3 --kernel_size 5
```

Key flags:
- `--train_csv --val_csv --test_csv`: Override split paths if needed.
- `--device`: `cuda` or `cpu` (auto-detects if CUDA is available).
- `--out_dir`: Output directory for checkpoints and metrics (default `processed/train_utils/outputs`).

Outputs:
- `tcn_YYYYMMDD_HHMMSS.pt`: Checkpoint with model state and config.
- `tcn_YYYYMMDD_HHMMSS.json`: Summary with config and final test metrics.

## Train per dialect (export one model per subset)
If you want a model that only targets a specific sign-language subset (e.g. `bac`, `nam`, `hoa-de`, `cần thơ`), you can filter by the `dialect` column in the split CSVs.

Example (North / miền Bắc):

```powershell
python processed/train_utils/train_tcn.py --dialect bac --epochs 80 --batch_size 32
```

This run will:
- Filter `train/val/test` rows to `dialect=bac`
- Build a *local* label mapping (so class indices are contiguous, macro-F1 is meaningful)
- Export files like:
	- `tcn_dialect-bac_YYYYMMDD_HHMMSS.pt`
	- `tcn_dialect-bac_YYYYMMDD_HHMMSS.json`

Notes:
- Default behavior is unchanged when you omit `--dialect`.
- Subset label maps are written under `processed/train_utils/outputs/subset_<tag>_<timestamp>/` and the checkpoint stores the path in `label_to_index_json`.

## Train per language (export one model per language)
If your dataset contains multiple languages, you can filter by `language` (or infer it from `label_key` if needed) and export a model per language.

Example (Vietnamese only):

```powershell
python processed/train_utils/train_tcn.py --filter_language vn --epochs 80 --batch_size 32
```

Notes:
- This creates a local label mapping for that language subset, so class indices are contiguous.
- You can combine language + dialect filters if you want an even smaller subset.

## Train all languages (one command)
To train one model per language automatically, use:

```powershell
python processed/train_utils/train_all_languages.py -- --epochs 80 --batch_size 32
```

## Train all dialects within each language
If you want *one model per dialect per language* (e.g. `vn/bac`, `vn/nam`, ...), run:

```powershell
python processed/train_utils/train_all_languages.py --by_dialect -- --epochs 80 --batch_size 32
```

Optional filters:
- Only certain languages:

```powershell
python processed/train_utils/train_all_languages.py --by_dialect --languages vn,en -- --epochs 80 --batch_size 32
```

- Only certain dialect names:

```powershell
python processed/train_utils/train_all_languages.py --by_dialect --dialects bac,nam -- --epochs 80 --batch_size 32
```

Options:
- Train only specific languages (in order):

```powershell
python processed/train_utils/train_all_languages.py --languages vn,en -- --epochs 80 --batch_size 32
```

- Skip languages that fail (e.g. too few classes):

```powershell
python processed/train_utils/train_all_languages.py --skip_failed -- --epochs 80 --batch_size 32
```

## Notes
- The trainer applies masked global average pooling over time to handle variable-length inputs.
- Early stopping monitors validation macro-F1 with patience 10.
- Learning rate uses cosine annealing; adjust `--epochs` to change schedule length.

## Check realtime ↔ training feature compatibility
Training code assumes features are already in the correct format. Realtime extraction currently uses raw MediaPipe landmarks (x/y/z) and concatenates `[left(21x3), right(21x3)]`.

To inspect how your dataset `.npz` features look (ranges, likely left/right ordering, whether x/y are in [0,1]):

```powershell
python processed/train_utils/check_preprocess_compat.py --csv processed/splits/train.csv --n 200
```
