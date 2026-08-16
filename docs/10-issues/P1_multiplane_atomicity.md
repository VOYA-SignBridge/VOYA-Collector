# P1 — Ghi nhiều mặt phẳng không nguyên tử (DB / CSV / hệ tệp)

**Mở:** 16/08/2026 · **Mức:** P1 · **Cam kết liên quan:** P2 (tenant isolation),
P7 (signed SOT) — *không phải một claim riêng trong đề cương*

## Đã sửa

```
CSV không còn bị ghi TRƯỚC khi PostgreSQL từ chối
```

`sync_reassign_sample` trước đây chạy `di chuyển tệp -> ghi CSV -> ghi DB`, và
khối `except` chỉ hoàn nguyên phần tệp. Một lượt bị `fk_samples_class_tenant`
từ chối để lại:

```
HTTP 400          người gọi thấy "thất bại"
PostgreSQL        không đổi
samples.csv       ĐÃ ĐỔI, không hoàn nguyên
tệp .npz          đã về chỗ cũ  -> file_path treo
```

Và vì đường đọc lấy từ CSV, tenant B nhìn thấy mẫu của A trong lớp của B — do
một request đã báo lỗi. Thứ tự nay là `di chuyển tệp -> ghi DB -> ghi CSV`:
PostgreSQL là nơi ràng buộc được cưỡng chế, nên nó phải là **cửa ải**.

Bằng chứng: `backend/tests/test_reassign_multiplane_order.py` — 7/7, dùng tiêm
lỗi thay vì dựng một ràng buộc cụ thể, để phép thử kiểm **vũ đạo** chứ không
kiểm một ràng buộc có thể bị đổi tên.

## CHƯA sửa

```
PostgreSQL đã commit  ->  ghi CSV hỏng  ->  hai mặt phẳng lệch theo chiều NGƯỢC
```

Đặc tả bằng `test_ghi_CSV_hong_SAU_khi_DB_commit_van_lech`. Phép thử ấy khẳng
định hành vi **không mong muốn** một cách có kiểm chứng, để khoảng hở là một
tuyên bố chứ không phải một điều chưa ai để ý. Khi đóng, nó phải được **viết
lại** cho hành vi mới — đỏ lên là tín hiệu đúng, không phải hồi quy.

## Đừng đọc nhầm

Bất kỳ ai đọc "P0-B đã đóng" đều **không** được hiểu là tính nguyên tử đã giải
quyết. P0-B đóng đúng **một** chiều hỏng, chiều đã đo được. Chiều còn lại vẫn mở.

## Phạm vi thật sự của vấn đề

Không chỉ `sync_reassign_sample`. Mọi hàm chạm nhiều mặt phẳng đều có hình dạng
này — chín hàm ghi trong `catalog_sync.py`, cộng các đường ghi ảnh/manifest/xuất
chưa rà. Cần một lượt audit riêng (nhóm **G**), không gộp vào P0.

## Hướng đóng (chưa chọn)

1. **Staging + bù trừ** — ghi CSV ra tệp tạm, `os.replace()` sau khi DB commit;
   thất bại thì có bước bù trừ tường minh.
2. **Một nguồn chân lý duy nhất** — PostgreSQL là chân lý, CSV thành artifact
   dẫn xuất dựng lại được. Sạch hơn về mặt kiến trúc, nhưng đụng SOT (P7) và
   đường xuất, nên là một quyết định kiến trúc chứ không phải một bản vá.

Phương án 2 đáng cân nhắc **cùng lúc với RED-3 (SOT per workspace)** — hai việc
hỏi cùng một câu: cái gì là chân lý, và ai được ghi vào nó.
