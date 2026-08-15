# Console quản trị & Trung tâm Cài đặt

*Viết 2026-08-10. Trả lời hai lời phàn nàn cụ thể: thanh bên "chưa tối ưu và
không có thanh setting", và "phần admin nên có nút riêng để chuyển hoàn toàn
qua chức năng admin".*

---

## 1. Vấn đề đo được

Thanh bên cũ có **11 mục cho người dùng thường và 21 cho quản trị viên**. Trong
đó sáu mục — Tài khoản, Tổ chức, Xác minh liên hệ, Gói dịch vụ, Tích hợp, Hỗ trợ
— là thiết lập **một lần trong đời**, nằm ngang hàng với Đóng góp dữ liệu và
Huấn luyện model, tức công việc **hằng ngày**.

Hệ quả không phải là "xấu" mà là **không đọc được trong một cái liếc**: mọi thứ
quan trọng như nhau thì không có gì quan trọng. Nút "Tạo tổ chức" đã tồn tại và
đã được nối dây đúng, nhưng nó là mục thứ 14 trong một danh sách 21 mục — nên
báo cáo "không có chỗ tạo tổ chức" là chính xác về mặt trải nghiệm, dù sai về
mặt mã nguồn.

## 2. Ba tầng, và ranh giới giữa chúng

```
Ứng dụng          Cài đặt                     Console quản trị
(việc hằng ngày)  (thiết lập một lần)          (vận hành hệ thống)
─────────────     ─────────────────            ──────────────────
Trang chủ         /settings/account            /admin
Đóng góp dữ liệu  /settings/security           /admin/users
Thư viện nhãn     /settings/contact            /admin/data
Nhận dạng         /settings/organization       /admin/resources
Huấn luyện        /settings/billing            /admin/activity
Thùng rác         /settings/integrations *     /admin/support
⚙ Cài đặt ────────┘ /settings/support           /admin/sot
                   /settings/language          /admin/vocabulary
                                               /admin/legal
                                               /admin/tenants
                                               /admin/billing
                                               /admin/trash
```

`*` Tích hợp chỉ hiện với quản trị viên: máy chủ đòi vai biên tập, nên hiện mục
đó cho người không có quyền là mời họ bấm vào một trang chắc chắn 403 — một ngõ
cụt có sẵn nhãn.

**Thanh bên chính giờ chỉ còn việc cần làm**, cộng đúng một lối vào Cài đặt.

## 3. Console quản trị (`components/AdminShell.tsx`)

Yêu cầu: *"Admin sẽ có 1 mode chuyển chế độ sang hẳn riêng 1 console luôn, là
nguyên giao diện khác hoàn toàn so với user và sẽ có nút thoát về."*

Ba quyết định:

**Không dùng lại header của ứng dụng.** Dùng chung thì console lại trông giống
chỗ cũ, và cả bản tách này thành vô nghĩa. Console có thanh đầu riêng, nền tối
(`slate-950`), và một phù hiệu `CONSOLE QUẢN TRỊ` màu hổ phách.

**ĐÚNG MỘT lối ra, luôn ở cùng chỗ.** Vào được một chế độ mà không thấy đường ra
là cách nhanh nhất khiến người ta ngại bấm vào. Nút "Thoát về ứng dụng" nằm cố
định góc phải thanh đầu.

**Nội dung trang được bọc trong một tấm SÁNG.** Mười trang quản trị được viết cho
nền sáng. Đi sửa màu từng trang cho hợp nền tối là mười dịp làm hỏng độ tương
phản ở chỗ không ai kiểm. Vỏ tối + ruột sáng cho ra cảm giác "console" mà không
đụng vào bất kỳ trang nào.

> **Vỏ này KHÔNG phải hàng rào quyền.** Quyền vẫn do máy chủ quyết ở từng
> endpoint (`require_admin`). Một người không phải quản trị viên gõ thẳng
> `/admin/...` vào thanh địa chỉ sẽ gặp `ProtectedRoute requireAdmin` rồi tới 403
> của máy chủ. Điều này được ghim bằng một bài test có tên nói đúng như vậy, để
> không ai đọc mã rồi tưởng đã có kiểm soát truy cập ở đây.

## 4. Trung tâm Cài đặt (`pages/settings/SettingsLayout.tsx`)

Khuôn quen thuộc từ Facebook/Google: một mục **Cài đặt** ở thanh bên chính, mở ra
một trang có thanh điều hướng con bên trái.

**Mỗi mục là một ROUTE riêng, không phải một tab trong `useState`.**
`/settings/security` phải chia sẻ được, đánh dấu được, quay-lại được — và thông
báo bảo mật trỏ tới trang này **bằng đường dẫn**. Một tab lưu trong state làm
hỏng cả bốn.

Xác minh liên hệ và Hỗ trợ đã chuyển vào đây theo đúng yêu cầu.

## 5. Kiểm chứng

| Tệp | Số test | Canh gì |
|---|---|---|
| `src/components/__tests__/AdminShell.test.tsx` | 6 | phù hiệu, **đúng một** lối ra, 12 liên kết thật, bản dịch, và **không phải hàng rào quyền** |
| `src/pages/settings/__tests__/SettingsLayout.test.tsx` | 4 | mỗi mục là liên kết có `href`, 8 mục cho admin / 7 cho người thường, bản dịch |

```bash
cd frontend && npx vitest run src/components/__tests__/AdminShell.test.tsx src/pages/settings
```

## 6. Chưa làm

* **Không có bảng số trên `/admin`.** Một bảng điều khiển chỉ số cần nguồn dữ
  liệu thật, chu kỳ làm mới, và câu trả lời cho "số này tính từ lúc nào" — ba thứ
  chưa có. Vẽ ô số trống hoặc số giả là dựng một thứ trông như đo đạc mà không đo
  gì; `/admin/resources` mới là nơi có số thật.
* **Chưa có phím tắt chuyển chế độ.** Chỉ có nút.
