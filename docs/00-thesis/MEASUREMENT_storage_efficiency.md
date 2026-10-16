# Phép đo hiệu quả lưu trữ — Kết quả mong đợi số 5 của proposal

*Phía landmark đo 15/08/2026. Phép đo ghép cặp video ↔ landmark chạy 16/08/2026,
200 clip QIPEDC. Không chạm cơ sở dữ liệu, không chạm nguồn migration.*

Proposal cam kết ở Expected Outcome 5: *"reduces per-sample storage by **over
90%** vs. raw video"*.

**Kết luận: cam kết được xác nhận trên tổng dung lượng và trên trung vị, nhưng
KHÔNG đúng cho mọi mẫu.** Con số phải công bố là **92,2 %** (ghép cặp, khớp thời
lượng, n = 54), không phải một con số cao hơn.

---

## 1. Phía landmark — đo thật, n = 3.871

```
dataset/features/  (đã chuẩn hoá)
    n = 3.871 tệp .npz          tổng = 146,0 MiB
    trung bình = 38,6 KiB       trung vị = 42,6 KiB
    p5  = 14,1 KiB              p95     = 82,8 KiB

dataset/raw/       (kho raw, TRƯỚC chuẩn hoá)
    n = 440 tệp .npz            tổng = 10,2 MiB
    trung vị = 27,5 KiB
```

Con số "≈ 44 KB/mẫu" đang lưu hành trong `LUANVAN_TONGHOP.md` là **đúng**: trung
vị đo lại được 42,6 KiB.

Phân bố rộng hơn nhiều so với một con số đơn lẻ gợi ý — p5 tới p95 là 14,1 → 82,8
KiB, gấp gần **sáu lần**. Nguyên nhân sẽ trở lại ở §4: `.npz` là định dạng nén, và
một chuỗi mà một tay vắng mặt phần lớn thời gian gồm nhiều số 0 liên tiếp nên nén
rất tốt.

Tham số thu để tái lập: `TARGET_FRAMES = 60`, `CAPTURE_FRAME_WIDTH = 1280`, 126
chiều mỗi khung (21 điểm mốc × 3 toạ độ × 2 tay).

## 2. Vì sao không đo được trên dữ liệu của chính hệ thống

**Không có tệp video nào trong kho dữ liệu.** 8.784 tệp `.npz`, 0 video.

* `dataset/raw/` — bất chấp cái tên — chứa `.npz` (kho landmark trước chuẩn hoá).
* `dataset/raw_videos/uploads.csv` **chỉ có dòng tiêu đề**, và không có cột kích
  thước, nên kể cả khi đã từng có lượt tải thì kích thước gốc cũng không lưu lại.

Điều này **không phải thiếu sót của phép đo — nó là hệ quả trực tiếp của thiết
kế**: trình duyệt trích xuất điểm mốc ngay tại máy người dùng và chỉ gửi lên
`.npz`. Video thô chưa bao giờ rời khỏi trình duyệt. Đó chính là cơ chế tạo ra
hiệu quả lưu trữ, và cũng chính là lý do không còn gì để cân đo ngược lại.

Nên phải đo ghép cặp trên một nguồn video bên ngoài — §3.

### Bản dựng xem trước KHÔNG dùng làm mốc được

Kho có 6 tệp `preview_single-*.mp4` do chính nền tảng sinh ra: trung vị 28,9 KiB —
**nhỏ hơn cả trung vị `.npz`**. Dùng chúng làm mốc "video thô" cho kết luận ngược
hẳn. Lý do hiển nhiên khi nhìn nội dung: khung xương vẽ trên nền phẳng, gần như
không có kết cấu. Ghi lại để không ai dùng nhầm sáu tệp này.

## 3. Phép đo ghép cặp — 200 clip QIPEDC

Chạy chính pipeline MediaPipe Hands của nền tảng trên 200 clip lấy ngẫu nhiên từ
4.363 clip QIPEDC, so **từng cặp cùng một đoạn ký hiệu**.

```
mẫu       200 clip · 124,5 MiB · seed 20260816
clip      trung vị 3,85 s · 30 fps · 1280×720
```

Hai cách quy chiếu, khác nhau ở chỗ có khớp thời lượng hay không:

| | landmark đủ khung *(khớp thời lượng)* | landmark 60 khung *(định dạng nền tảng)* |
|---|---|---|
| tổng video | 124,5 MiB | 124,5 MiB |
| tổng landmark | 5,57 MiB | 2,98 MiB |
| **giảm trên tổng** | **95,5 %** | 97,6 % |
| giảm, trung vị/mẫu | 96,2 % | 97,8 % |
| giảm, p5 | 90,2 % | 93,7 % |
| giảm, tệ nhất | 87,8 % | 91,5 % |

**Cột phải cao hơn nhưng không dùng được làm luận điểm chính.** Nền tảng lưu cố
định 60 khung bất kể clip dài bao nhiêu; với clip trung vị 3,85 giây thì 60 khung
ở 30 fps chỉ là 2 giây. Phần chênh giữa hai cột **là do cắt bớt thời lượng, không
phải do biểu diễn hiệu quả hơn**. Trộn hai thứ đó lại là ghi công cho nén một việc
mà thực ra là vứt dữ liệu.

Cột trái — cùng số khung, khác cách biểu diễn — mới là phép so *pixel so với điểm
mốc*, và đó là điều Expected Outcome 5 nói.

## 4. Tiêu chí đưa vào — vì sao 200 còn 54

Đây là câu hội đồng sẽ hỏi ngay, nên phải trả lời trước khi bị hỏi. **54 không
phải chọn lọc theo kích thước tệp.**

Tiêu chí đưa vào, đặt ra **trước** khi nhìn kết quả:

```
1  clip lấy ngẫu nhiên từ 4.363 clip QIPEDC, hạt giống cố định 20260816   → 200
2  chỉ so cặp KHỚP THỜI LƯỢNG (landmark đủ khung, không phải 60 khung)    → 200
3  chỉ giữ clip MediaPipe bắt được tay ≥ 90 % số khung                    →  54
```

Bước 3 là tiêu chí **về tính hợp lệ của phép trích xuất**, không phải về dung
lượng. Lý do: khung không bắt được tay là một vector **toàn số 0**, và số 0 liên
tiếp nén gần như miễn phí. Một `.npz` nhỏ bất thường phản ánh **hỏng phát hiện**,
không phản ánh biểu diễn hiệu quả. Gộp chung sẽ thổi phồng tỉ lệ tiết kiệm bằng
chính những mẫu mà pipeline thất bại.

Vì vậy kết quả phải đọc là:

> mức giảm dung lượng **với điều kiện trích xuất điểm mốc thành công theo tiêu
> chí đưa vào ở trên**

chứ **không** phải "mọi clip QIPEDC đều giảm 92,2 %".

Bộ số trên 54 cặp còn lại:

```
n = 54    khớp thời lượng    tổng video 30,8 MiB → landmark 2,41 MiB

  giảm trên tổng      92,2 %      (12,8×)
  giảm trung vị/mẫu   91,6 %
  giảm p95            94,7 %
  giảm p5             88,9 %
  giảm tệ nhất        87,8 %
  số mẫu dưới 90 %     9 / 54
```

**Đây là bộ số phải đưa vào quyển.** Nó thấp hơn cả bốn con số ở §3 vì nó là bộ
số duy nhất không mượn tay hai hiện tượng khác (cắt thời lượng, hỏng phát hiện).

## 5. Trả lời cam kết ">90%"

| phát biểu | đúng? |
|---|---|
| giảm hơn 90 % trên **tổng dung lượng** | **đúng** — 92,2 % |
| giảm hơn 90 % ở **mẫu trung vị** | **đúng** — 91,6 % |
| giảm hơn 90 % ở **mọi mẫu** | **sai** — 9/54 mẫu nằm dưới, thấp nhất 87,8 % |

**97,6 % và 95,5 % không phải kết quả cạnh tranh.** Chúng thuộc phần *phân tích
tính hợp lệ*: mỗi con số cho thấy một cách mà phép đo có thể tự thổi phồng, và lý
do loại chúng chính là lập luận vì sao 92,2 % là ước lượng được chọn —

```
97,6 %  hưởng lợi từ CẮT THỜI LƯỢNG (60 khung so với clip 3,85 s)
95,5 %  hưởng lợi từ HỎNG PHÁT HIỆN (vector toàn số 0 nén gần như miễn phí)
92,2 %  không mượn tay hiện tượng nào  ← công bố
```

Trình bày như vậy mạnh hơn việc chỉ đưa một con số đẹp, vì nó chứng minh được
**vì sao** ước lượng này được chọn chứ không phải hai cái kia.

Câu nên dùng:

> Trên 54 cặp video–điểm mốc khớp thời lượng, biểu diễn điểm mốc giảm **92,2 %**
> tổng dung lượng so với video nguồn (trung vị mỗi mẫu 91,6 %; khoảng p5–p95
> 88,9–94,7 %). Cam kết ">90%" giữ được ở mức tổng thể và trung vị, nhưng không
> phải mọi mẫu đều vượt ngưỡng.

Bảng ước lượng theo bitrate trong bản trước của tài liệu này (1,5 / 2,5 / 5,0
Mbps → 88,4 / 93,0 / 96,5 %) **đã bị thay thế bằng số đo thật** và không được
trích dẫn nữa. Đáng ghi nhận là nó đoán đúng khoảng: video QIPEDC đo được 1,26
Mbps, và mức giảm thực 92,2 % nằm giữa hai hàng đầu của bảng ước lượng cũ.

## 6. Giới hạn — phải nêu kèm mọi lần trích dẫn

> **Video QIPEDC là bản quay studio đã qua hậu kỳ và nén để phát trên web, KHÔNG
> phải luồng webcam mà CTU-SignBridge thu.** Con số này đo trên một nguồn video
> có tên và tái lập được; đừng phát biểu nó như thể đã đo trên dữ liệu của chính
> hệ thống.

Ba giới hạn cụ thể:

1. **Không khái quát sang luồng webcam của nền tảng.** Video QIPEDC đo được 1,26
   Mbps ở 720p — mã hoá để phân phối web. Cấu hình `MediaRecorder` thực tế của
   CTU-SignBridge **chưa được đo**, nên không có cơ sở để nói kết quả sẽ cao hơn
   hay thấp hơn trên dữ liệu webcam. Dung lượng còn phụ thuộc codec, nội dung
   cảnh, mức chuyển động và bộ mã hoá, không chỉ bitrate danh nghĩa. Muốn nói
   được điều gì về webcam thì phải đo bản ghi trình duyệt thật.

   > *Bản trước của tài liệu này gọi 92,2 % là "cận dưới thận trọng" dựa trên lập
   > luận bitrate. **Đã rút.** Đó là một mệnh đề toán học mạnh hơn bằng chứng.*

2. **Không ghép cặp người ký.** So cùng một đoạn ký hiệu, không phải cùng một
   người trong cùng điều kiện. Muốn khép hẳn thì cần một phiên ghi có kiểm soát
   (bật `MediaRecorder` song song đường thu hiện có, giữ cả hai) — chi phí một
   buổi, và không cần thiết cho mức tuyên bố ở §5.

3. **Tỉ lệ bắt được tay 59,2 % KHÔNG phải chỉ số của nền tảng.** Xem §6b — đây là
   quan sát về một câu hỏi khác, không thuộc kết luận lưu trữ.

## 6b. Tỉ lệ phát hiện — quan sát phụ, tách khỏi kết luận lưu trữ

Hai câu hỏi khác nhau, không được gộp vào cùng một kết luận:

| thí nghiệm | trả lời câu hỏi |
|---|---|
| lưu trữ (§3–§5) | *khi biểu diễn điểm mốc hợp lệ được tạo ra, dung lượng giảm bao nhiêu?* |
| quan sát phát hiện | *pipeline hiện tại chạy ra sao trên video NGOÀI điều kiện thu mà nền tảng thiết kế?* |

Quan sát: trên 200 clip QIPEDC, tỉ lệ khung bắt được tay có **trung vị 59,2 %**
(khoảng 23,3–100 %).

> QIPEDC là dữ liệu studio đã nén để phân phối web, không phải luồng thu có hướng
> dẫn khung hình của CTU-SignBridge. Tỉ lệ phát hiện trên tập này vì vậy **không
> được dùng để đại diện cho capture success rate của nền tảng.**

Giá trị của nó là giải thích vì sao n = 54 ở §4, và là một ghi chú về độ bền của
pipeline khi gặp dữ liệu ngoài phân bố thu — không phải một kết quả về lưu trữ.

## 7. Tái lập

```bash
# 1. rút mẫu 200 clip, hạt giống cố định
python -c "
import random, pathlib, shutil
src = pathlib.Path('E:/CTU_ProjectOutside/qipedc_mau')
vids = sorted(p.name for p in src.glob('*.mp4'))       # 4363
random.Random(20260816).shuffle(vids)
dst = pathlib.Path('qipedc_sample200'); dst.mkdir(exist_ok=True)
for v in vids[:200]: shutil.copy2(src/v, dst/v)
"

# 2. đo ghép cặp
.venv/Scripts/python.exe scripts/do_video_vs_diemmoc.py \
    --thu-muc qipedc_sample200 --tai 200 \
    --json docs/00-thesis/MEASUREMENT_storage_efficiency.json
```

Kiểm mẫu đúng là mẫu đã dùng: `sha256` của danh sách 200 mã đã sắp xếp bắt đầu
bằng `afca207fe1796c7c`.

Artifact `MEASUREMENT_storage_efficiency.json` giữ **từng dòng một trong 200
clip** (`byte`, `byte_full`, `byte_seq60`, `ty_le_phat_hien`, `giay`, `fps`), nên
mọi bảng ở trên tính lại được mà không cần chạy lại MediaPipe.

Lưu ý môi trường: `python` trần trên máy này trỏ vào `.venv_py313_backup` có numpy
dựng bằng MINGW và **segfault**. Dùng `.venv/Scripts/python.exe`.
