# Nợ kiến trúc — tiến trình ứng dụng sản xuất vẫn có quyền đổi lược đồ

**Mở:** 15/08/2026 · **Mức độ:** nợ kiến trúc (chưa phải sự cố đang diễn ra)
**Trạng thái:** đã ghi nhận, **chưa** refactor — cố ý hoãn
**Liên quan:** [INCIDENT_2026-08-12_schema_code_skew.md](INCIDENT_2026-08-12_schema_code_skew.md)

---

## 1. Phát biểu

`ensure_tables()` chạy ở **mỗi lần một tiến trình ứng dụng khởi động** — bốn
worker gunicorn của `backend`, cộng `worker`, `trainer`, `celery_beat`,
`sot_init`. Nó chỉ được phép THÊM và bổ khuyết, không phá gì; ranh giới đó do
`startup_safe()` cưỡng chế và nó hoạt động đúng như thiết kế.

Nhưng "chỉ thêm" **không** đồng nghĩa với "vô hại". Một câu `CREATE INDEX
IF NOT EXISTS` là câu chỉ-thêm, và nó đủ sức **dựng lại một đối tượng mà
migration vừa retire**. Khi ấy đường khởi động hoàn tác việc của migration, và
không có gì trong hai bên biết chuyện đó vừa xảy ra.

## 2. Vì sao ghi hôm nay

Hai lần trong hai ngày, cùng một hình dạng, hai cửa khác nhau:

| ngày | cửa vào | hệ quả |
|---|---|---|
| 14/08 | migration gỡ chỉ mục → **khởi động lại** dựng lại | biến thể vùng bị chặn tiếp, không ai được báo |
| 15/08 | migration chạy **trong khi bản cũ còn phục vụ** | chỉ mục quay lại trong vòng ~90 giây |

Lần 14/08 đã vá đúng cách: retire thì phải **gỡ câu tạo**, thêm câu xoá là chưa
đủ. Lần 15/08 cho thấy bản vá ấy chỉ đóng được một cửa.

Số đo 15/08:

```
04:01:21  migrate --to 5 (ảnh mới) gỡ uq_classes_tenant_slug_lang_dialect
04:03     chỉ mục ĐÃ QUAY LẠI
04:07     chạy lại đúng lệnh đó, khi chỉ còn ảnh mới → gỡ sạch
04:1x     khởi động lại nhiều lần → KHÔNG quay lại nữa
```

Cơ chế nhiều khả năng: container backend **cũ** còn sống trong cửa sổ ấy, và
`--max-requests 1000 --max-requests-jitter 100` làm gunicorn thay worker định
kỳ; worker mới chạy `ensure_tables()` của ảnh cũ, ảnh cũ vẫn còn câu `CREATE`.

**Chưa tái hiện.** Ảnh cũ đã bị xoá nên thí nghiệm không dựng lại được, và
việc tái hiện trên sản xuất bị loại trừ có chủ ý. Ghi là *probable mechanism,
not reproduced*.

## 3. Vì sao đổi thứ tự triển khai là chưa đủ

`scripts/deploy.sh` nay chạy `build → dừng ứng dụng → migrate → verify → up →
verify lại`, và điều đó đóng đúng cuộc đua đã đo. Nhưng nó đóng bằng **thủ
tục**, không phải bằng **năng lực**: tiến trình ứng dụng vẫn còn quyền đổi
lược đồ, chỉ là hiện không có ai gọi nó vào đúng lúc xấu.

Mọi đường khác vẫn mở: `docker compose up -d` gõ tay, nút Restart trong Docker
Desktop, một container tự khởi động lại sau OOM, một worker được thay giữa
lúc ai đó đang chạy migration bằng tay.

## 4. Hướng đề xuất

```
Tiến trình ứng dụng sản xuất   →  KHÔNG hội tụ, KHÔNG migrate lược đồ
Tiến trình migration riêng     →  nơi DUY NHẤT được đổi lược đồ
```

`ensure_tables()` vẫn giữ được cho dev/test/bootstrap. Ở sản xuất nó nên rút
về **chỉ kiểm chứng, fail-fast**: đọc lược đồ, so với kỳ vọng của ảnh, từ chối
khởi động nếu lệch — và không ghi gì. Cổng phiên bản hiện có
(`startup-vs-explicit-migration`) đã là một nửa của việc đó; nửa còn lại là bỏ
quyền ghi.

Điều cần biến mất, phát biểu hẹp nhất có thể:

> Một lượt thay worker của gunicorn không được có khả năng phục hồi một đối
> tượng mà migration vừa retire.

## 5. Vì sao chưa làm ngay

`ensure_tables()` là đường dựng lược đồ cho máy mới, cho `signdb_test`, và cho
mọi bài kiểm tích hợp. Tách nó làm hai chế độ là việc có thật, đụng vào đường
khởi động của cả năm service, và không nên làm chung chuyến với một release
vừa đổi định danh lớp.

Chốt chặn tạm thời đang có, và cả hai đều đã đo được là hoạt động:

1. `migrate --status` kiểm **hai** tập — `required` phải có, `retired` phải
   vắng. Đây là thứ đã bắt được lỗi 15/08.
2. `deploy.sh` kiểm lại lược đồ **sau** khi ứng dụng mới đã lên, nên nếu vòng
   đời khởi động dựng lại thứ gì thì lượt triển khai sẽ nói ra.

## 6. Việc cần làm khi mở lại

- [ ] Tách `ensure_tables()` thành `bootstrap_schema()` (dev/test) và
      `assert_schema()` (sản xuất, chỉ đọc)
- [ ] Đường sản xuất mặc định là `assert_schema()`; bật ghi phải là một biến
      môi trường tường minh
- [ ] Bài kiểm: một tiến trình ứng dụng khởi động trên lược đồ vừa retire một
      đối tượng **không** được làm đối tượng ấy quay lại
