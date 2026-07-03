> [!WARNING]
> **DEPRECATED (2026-07):** Cơ chế hậu tố `2.0` là giải pháp tạm để dev/prod không ghi đè nhau khi dùng chung Google Drive.
> Nguyên nhân gốc đã được xử lý bằng **tách môi trường** (root folder Drive riêng per-environment + guard fail-fast) và **cấu trúc Drive v2** (versioning nằm ở path) — xem [`docs/database/erd_v2_unified_design.md`](database/erd_v2_unified_design.md) §11.2 & §12.
> Thực hiện revert theo hướng dẫn bên dưới ở **GĐ 3** của Roadmap v2.

# Google Drive suffix 2.0

Temporary change: only Google Drive catalog snapshots use a `2.0` suffix on the final filename.

Examples:
- `labels.csv` -> `labels2.0.csv`
- `samples.csv` -> `samples2.0.csv`
- `sample_xxx.npz` stays `sample_xxx.npz`
- `upload_xxx.mp4` stays `upload_xxx.mp4`

Where to revert later:
- [backend/app/config.py](../backend/app/config.py): change `gdrive_filename_suffix` from `"2.0"` to an empty string or your desired suffix.
- [backend/app/storage/gdrive_client.py](../backend/app/storage/gdrive_client.py): `apply_gdrive_suffix_to_remote_path()` is the single place that appends the suffix before upload.
- [backend/app/storage/catalog_mirror.py](../backend/app/storage/catalog_mirror.py): catalog CSVs are uploaded as `labels2.0.csv` / `samples2.0.csv` and replace the previous snapshot only.
- [backend/app/storage/gdrive_client.py](../backend/app/storage/gdrive_client.py): `replace_existing=True` is used only for catalog snapshots; raw/live uploads create new objects instead of overwriting.
- [backend/app/dataset_samples.py](../backend/app/dataset_samples.py): live-capture `storage_key` stays in the normal `features/.../sample_xxx.npz` form.
- [backend/app/routers/upload.py](../backend/app/routers/upload.py): raw video `storage_key` stays in the normal `raw_videos/.../upload_xxx.mp4` form.

Note:
- Local dataset files are unchanged. Only Google Drive catalog snapshot names are affected.