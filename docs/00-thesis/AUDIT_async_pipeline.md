# Audit pipeline bất đồng bộ — cam kết O6

*Audit đọc mã, 16/08/2026. **Không phải phép đo**: không chạy benchmark, không đo
throughput. Câu hỏi là workload nào thực sự chạy nền, cơ chế retry/idempotency
nào thực sự tồn tại, và phần nào của đề cương mới ở mức thiết kế.*

Mỗi năng lực phải đi đủ chuỗi, không dừng ở `@celery_app.task`:

```
đường nghiệp vụ -> enqueue -> task đã đăng ký -> worker thực thi -> tác dụng phụ bền
```

---

## 1. Bảng chính

| Năng lực | Hiện thực | Nối Celery | Retry | Idempotency | Trạng thái |
|---|---|---|---|---|---|
| **Ingestion** | `tasks.enqueue_process_video` → `processing.pipeline.process_video_job` | ✓ `routers/upload.py:262` | ✗ **không có** | ✗ **không** | **OPERATIONAL** |
| **Segmentation** | cắt cửa sổ trong `pipeline.py` (stride, ngưỡng hoạt động, completeness) | ✓ *gián tiếp* — chạy trong task ingestion | kế thừa ingestion | kế thừa ingestion | **OPERATIONAL (nhúng)** |
| **Augmentation** | `processing.augmenter.generate_augmented_sequences` | ✓ *gián tiếp* — `pipeline.py:208` | kế thừa ingestion | kế thừa ingestion | **OPERATIONAL (nhúng)** |
| **Cloud synchronization** | 11 task trong `export_tasks.py` + `sync_tasks.py` | ✓ 21 điểm enqueue | ✓ `self.retry` 8 chỗ | ⚠ một phần | **OPERATIONAL** |

Hai trục ngang:

| Trục | Trạng thái | Vì sao |
|---|---|---|
| **Retry** | **PARTIAL** | Cloud sync có retry Celery thật; ingestion **không có** |
| **Idempotency** | **PARTIAL** | ghi DB/CSV theo khoá thì bền; tạo mẫu và tải Drive thì **không** |

## 2. Ingestion — chạy nền thật, nhưng không retry

```
routers/upload.py:262   enqueue_process_video.delay(...)
tasks.py:19             @celery_app.task(bind=True)
tasks.py:44             process_video_job(...)
```

Chuỗi đủ và có tác dụng phụ bền (ghi `.npz`, hàng CSV, hàng PostgreSQL). Đây là
workload bất đồng bộ **thật**, không phải helper gọi đồng bộ.

**Nhưng:** khai báo task là `@celery_app.task(bind=True)` — không `max_retries`,
không `autoretry_for`, và khối `except` **ném lại** sau khi ghi log. Một lượt xử
lý video hỏng vì lỗi thoáng qua (Drive chập, hết bộ nhớ tạm) là **mất hẳn**;
không có lượt thử lại, không có trạng thái thất bại để ai đó dọn.

Tương phản với `export_tasks.py`, nơi tám chỗ gọi `self.retry(...)` thật.

## 3. Segmentation và Augmentation — nhúng, không tự lên lịch được

Cả hai **có chạy trên worker** — chúng nằm trong thân `process_video_job`, thứ
chỉ được gọi từ task Celery. Nên chúng là bất đồng bộ theo nghĩa "không chặn
request".

Segmentation là thật, không phải cắt đều: `pipeline.py` dựng cửa sổ theo `stride`,
tính điểm hoạt động `_window_activity_mean_abs_diff`, lọc theo `completeness`,
dừng ở đoạn outro không có tay, và giữ một nhóm cửa sổ tốt nhất để bù cho đủ số
mẫu tối thiểu.

Augmentation gọi `generate_augmented_sequences(seq_arr, config={"n": aug_n})`, với
hệ số riêng cho video (`video_augment_per_seq`) khác với luồng thu trực tiếp.

**Giới hạn phải nêu:** không có task Celery riêng cho hai bước này, nên không
enqueue lại một mình được. Muốn chạy lại augmentation phải chạy lại **toàn bộ**
đường ingestion từ video gốc. Không nên mô tả chúng như bốn giai đoạn độc lập
trong một pipeline có thể điều phối riêng từng chặng.

## 4. Cloud synchronization — trục hoàn chỉnh nhất

11 task, 21 điểm enqueue, retry thật:

```
export_samples_to_sheets        max_retries=3   self.retry(exc=exc)
export_labels_to_sheets         max_retries=3   self.retry(exc=exc)
mirror_catalog_csvs_to_drive    max_retries=3   self.retry(exc=exc)
upload_npz_to_gdrive_task       max_retries=5   self.retry(exc=exc)
upload_raw_video_to_gdrive_task max_retries=5
upload_npz_batch_to_gdrive_task max_retries=3   self.retry(args=[failed], countdown=30)
delete_gdrive_paths_task        max_retries=3   self.retry(...)
delete_gdrive_files_task        max_retries=3   self.retry(...)
move_gdrive_paths_task          max_retries=3   self.retry(...)
reconcile_samples_csv_task      max_retries=2
download_missing_files_to_local (sync_tasks)
```

`upload_npz_batch_to_gdrive_task` thử lại **chỉ phần đã hỏng** (`args=[failed]`),
không thử lại cả lô — đây là thiết kế retry tốt.

## 5. Idempotency — trục yếu nhất, và retry làm nó nguy hiểm hơn

Chạy hai lần cùng một tác vụ logic **không** cho cùng một trạng thái logic ở hai
chỗ:

**(a) Tạo mẫu không idempotent.**

```python
dataset_samples.py:697   sample_uid = uuid.uuid4().hex[:10]
```

Định danh **ngẫu nhiên**, không dẫn xuất từ nội dung. Chạy lại ingestion trên
cùng một video sinh ra một bộ `sample_uid` hoàn toàn mới → **nhân đôi mẫu**,
không có ràng buộc nào chặn. Không có khoá idempotency, không có hash nội dung,
không có phép kiểm "đã xử lý video này chưa".

Hiện tại ingestion **không có retry**, nên rủi ro này chưa hiện thực hoá tự động
— nhưng nó hiện thực hoá ngay khi ai đó thêm retry, hoặc khi người dùng tải lại
cùng một video.

**(b) Tải Drive có retry nhưng không thay thế.**

```python
gdrive_client.py:903   def upload_to_gdrive(..., replace_existing: bool = False)
export_tasks.py:441    storage_url = upload_to_gdrive(local_path, storage_key)
```

Không truyền `replace_existing=True`. Task này **có** `max_retries=5`. Nếu lượt
tải thành công rồi bước sau hỏng (`update_sample_gdrive_url` hoặc
`update_sample_row`), `self.retry` chạy lại **toàn bộ thân task** → tải lên lần
nữa → **đối tượng Drive trùng lặp**.

Đây đúng dạng nguy hiểm: *retry mà không idempotent thì chính retry gây hỏng.*

**(c) Chỗ idempotent thật.** Các bước ghi ngược lại đều theo khoá:
`update_sample_gdrive_url(sample_uid, …)` và `update_sample_row(sample_uid, …)`
là cập nhật theo khoá chính, chạy lại bao nhiêu lần cũng cho cùng trạng thái.
`upload_npz_to_gdrive_task` cũng trả `{"status": "skipped"}` khi tệp cục bộ không
còn, thay vì hỏng.

Nên bức tranh chính xác: **đường ghi siêu dữ liệu idempotent, đường tạo tài
nguyên và tải đối tượng thì không.**

## 6. Lệch so với đề cương

Đề cương mô tả pipeline bất đồng bộ gồm ingestion, segmentation, augmentation và
đồng bộ đám mây. Bốn năng lực **đều tồn tại và đều thực thi trên worker**. Không
có năng lực nào ở mức "chỉ có khung sườn".

Ba điều chỉnh cần nêu trung thực:

1. **Segmentation và augmentation không phải giai đoạn độc lập.** Chúng nhúng
   trong task ingestion, không có điểm enqueue riêng, nên không điều phối, không
   thử lại và không mở rộng độc lập được.
2. **Retry không đồng đều.** Đồng bộ đám mây có retry Celery thật; ingestion —
   workload tốn kém nhất — thì không có. Một lượt hỏng là mất hẳn.
3. **Idempotency chưa đủ để dựa vào.** Không có khoá idempotency cho việc tạo
   mẫu, và một đường tải có retry lại dùng chế độ không thay thế.

Câu dùng cho Chương 4:

> Bốn năng lực xử lý bất đồng bộ trong đề cương đều được hiện thực và thực thi
> trên tiến trình nền. Tuy nhiên, segmentation và augmentation được nhúng trong
> tác vụ ingestion thay vì tồn tại như các giai đoạn có thể điều phối độc lập; cơ
> chế thử lại chỉ được cưỡng chế ở nhánh đồng bộ đám mây; và hệ thống **chưa cung
> cấp bảo đảm idempotency** cho việc tạo mẫu hay tải đối tượng lên kho đám mây.

**Không** nói "pipeline bất đồng bộ đầy đủ với retry và idempotency".

## 7. Ngoài phạm vi, cố ý

Không đo `jobs/s`, thông lượng hàng đợi, khả năng mở rộng worker hay
autoscaling — đề cương bản cuối đã loại triển khai phân tán quy mô lớn khỏi phạm
vi. Không có dead-letter queue, và **không mở thêm phạm vi** để dựng nó: đề cương
không cam kết.

## 8. Trạng thái O6

```
Ingestion               OPERATIONAL
Segmentation            OPERATIONAL (nhúng trong ingestion)
Augmentation            OPERATIONAL (nhúng trong ingestion)
Cloud synchronization   OPERATIONAL
Retry                   PARTIAL       (không có ở ingestion)
Idempotency             PARTIAL       (tạo mẫu và tải Drive: không)
```

## 9. Tái lập

```bash
grep -rn "@celery_app.task" backend/app/ --include=*.py      # task đã đăng ký
grep -rn "\.delay(\|\.apply_async(" backend/app/ --include=*.py   # điểm enqueue
grep -rn "self.retry\|autoretry_for" backend/app/ --include=*.py  # retry THẬT
```

Đối chiếu hai danh sách đầu: một task không xuất hiện ở danh sách thứ hai là
*implemented but not wired*. Danh sách thứ ba phân biệt retry của Celery với việc
người gọi tự thử lại hoặc một beat định kỳ chạy lại — chỉ cái đầu chứng minh
được ngữ nghĩa retry của hàng đợi.
