# Audit nhận dạng thời gian thực

*Audit 16/08/2026. Chỉ xác minh **có tồn tại / nối dây / chạy được**, không đánh
giá độ chính xác — đề cương đã loại huấn luyện và tối ưu model khỏi phạm vi.
Nhận dạng là **demo tiện ích hạ nguồn**, không phải đóng góp chính.*

```
TRẠNG THÁI: OPERATIONAL WITH PREREQUISITES
```

Đã chạy được một lượt suy luận thật, đúng nhãn, trên mẫu thật của kho.

---

## 1. Năm trục

| Trục | Kết quả |
|---|---|
| **Exists** | ✓ dịch vụ riêng `backend/realtime_service/` + trang `/realtime` |
| **Operational path** | ✓ nối đủ, xem §2 |
| **Model artifact** | ✓ 4 checkpoint `.pt` trên đĩa, 2 được đăng ký và **đã nạp** |
| **Demoable** | ✓ suy luận thật, đúng nhãn, độ tin 99,5% — xem §4 |
| **Dependencies** | camera + MediaPipe Hands ở trình duyệt, container `voya_realtime_service`, checkpoint; **GPU không bắt buộc** |

## 2. Đường thật, đủ chặng

```
camera (trình duyệt)
   ↓  MediaPipe Hands, 21 điểm × 3 toạ độ × 2 tay
frontend/src/components/realtime/RealtimeRuntime.tsx
   ↓  pages/RealtimeRecognitionPage.tsx  ->  App.tsx:177  Route "/realtime"
frontend/src/api/realtime.ts             ->  GET /api/v1/realtime/models
   ↓
backend/app/routers/realtime_proxy.py    (httpx, semaphore, limit_predict)
   ↓  REALTIME_SERVICE_URL
voya_realtime_service : 8010             POST /predict
   ↓  app/model_loader.py + app/registry.py
checkpoint .pt  ->  idx_to_label  ->  label_key  ->  nhãn hiển thị
```

Không có chặng nào đứt. UI **có** gọi, backend **có** proxy, dịch vụ **có** nạp
model, và nhãn **có** phân giải.

Kiến trúc đáng ghi: backend chính **không** nạp model. Nó proxy sang một dịch vụ
riêng, với `httpx.AsyncClient` và semaphore riêng — *"deliberately NOT shared with
upload/training clients"*. Nghĩa là một lượt suy luận chậm không chiếm mất pool
kết nối của đường tải lên.

## 3. Ánh xạ nhãn — chỗ dễ lệch nhất, và nó đúng

Vì hệ đã đổi định danh lớp (`region` trở thành một phần của khoá lớp), trục này
phải kiểm riêng chứ không suy từ "có model là chạy".

`app/contracts.py` cưỡng chế hợp đồng checkpoint chứ không tin nó:

```
validate_checkpoint_schema()   bắt buộc có khoá `idx_to_label`
validate_labels()              len(idx_to_label) phải == num_classes
                               label_key không được trùng
                               nhãn phải khớp phạm vi model
```

Đầu ra **không** phải chỉ số thô, cũng không phải `class_uid`:

```json
{"label": "A", "confidence": 0.995, "label_key": "vn/bang-chu-cai/a"}
```

`label_key` là `language/dialect/slug` — người đọc hiểu được, và truy ngược về
lớp được. Không rò UID nội bộ ra giao diện.

## 4. Bằng chứng chạy được

Lấy **một mẫu thật của kho**, không dùng vector số 0 — một vector 0 vẫn cho ra
"thành công" mà không chứng minh đường đặc trưng đúng:

```
mẫu   dataset/features/vn/bang-chu-cai/class_a_22000be4/…sample_0bf207df54.npz
shape (60, 126) float32          ← đúng hợp đồng seq_len=60, feature_dim=126

model bang-chu-cai  ->  {"label": "A",           "confidence": 0.9952}
model hoa-de        ->  {"label": "cắt đầu cá",  "confidence": 0.6708}
```

Mẫu thuộc lớp chữ **A**, model bảng chữ cái trả **"A" với 99,5%**. Ánh xạ đúng
đầu-đến-cuối.

Model `hoa-de` trả một nhãn từ vựng khác trên cùng đầu vào — **đúng như mong
đợi**, vì đó là model của miền từ vựng khác. Ghi lại để không ai đọc nhầm thành
lỗi: nó cho thấy phạm vi model là có thật và phải chọn đúng model.

Trạng thái dịch vụ lúc đo:

```
status ok · model_source registry · model_count 2 · warmup_ok true (cả hai)
checkpoint_sha256  9c6e93c4…  /  25c2971e…
loaded_at          2026-08-15T07:12:26Z
```

## 5. Điều kiện tiên quyết — vì sao không phải OPERATIONAL trần

1. **Cần container `voya_realtime_service`.** `REALTIME_SERVICE_URL` mặc định
   `http://localhost:8010`; trong compose nó là `http://realtime_service:8010`.
   Backend không nạp model, nên thiếu dịch vụ này là mất hẳn nhận dạng.
2. **Chỉ 2 trong 4 checkpoint được đăng ký.** `config/models.json` khai
   `bang-chu-cai` và `hoa-de` (bản `20260721_160609`). Hai tệp còn lại
   (`hoa-de_20260515`, `hoa-de_20260721_131343`) nằm trên đĩa nhưng **không** vào
   registry — bản cũ, không phục vụ.
3. **Chỉ hai miền từ vựng.** Không phải nhận dạng VSL tổng quát: một model bảng
   chữ cái và một model từ vựng chuyên ngành.
4. **Cần camera + MediaPipe ở trình duyệt.** Trích đặc trưng chạy phía client;
   máy chủ chỉ nhận `60 × 126`.
5. **GPU không bắt buộc.** Compose cho phép dùng GPU khi rảnh, nhưng suy luận ở
   trên chạy được không cần.

## 6. Phát biểu cho luận văn

> Hệ thống cung cấp một đường nhận dạng thời gian thực hoàn chỉnh: trích xuất
> điểm mốc phía trình duyệt, một dịch vụ suy luận tách biệt với registry model có
> kiểm hợp đồng, và phân giải nhãn về `language/dialect/slug`. Đã xác minh chạy
> được một lượt suy luận đúng nhãn trên mẫu thật của kho. Đây là **demo tiện ích
> hạ nguồn** cho thấy dữ liệu thu được dùng được; **không** phải một đánh giá
> model, và độ chính xác không nằm trong phạm vi đề cương.

**Không** nói: "hệ thống nhận dạng ngôn ngữ ký hiệu tiếng Việt" — nó phục vụ hai
miền từ vựng hẹp. **Không** trích `0.995` như một chỉ số chất lượng: đó là một
quan sát trên **một** mẫu, không phải phép đo độ chính xác.

## 7. Tái lập

```bash
docker exec voya_realtime_service python -c "
import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8010/health',timeout=5).read().decode())"

docker cp dataset/features/vn/bang-chu-cai/<lớp>/<mẫu>.npz voya_realtime_service:/tmp/m.npz
docker exec voya_realtime_service python -c "
import json,urllib.request,numpy as np
seq=np.load('/tmp/m.npz')['sequence']
r=urllib.request.Request('http://127.0.0.1:8010/predict',
    data=json.dumps({'model_id':'bang-chu-cai',
                     'frames':np.asarray(seq,dtype=float).reshape(60,126).tolist()}).encode(),
    headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(r,timeout=20).read().decode())"
```

Container `voya_realtime_service` **không** gắn kho dữ liệu (`/dataset` rỗng), nên
phải `docker cp` mẫu vào. Không cài `curl`; dùng `urllib`.
