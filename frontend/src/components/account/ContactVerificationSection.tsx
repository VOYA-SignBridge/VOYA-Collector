/**
 * Xác minh liên hệ, dựng như một khối trong trang Bảo mật.
 *
 * Chỉ là lớp vỏ quanh `VerifyContactPage` ở chế độ `embedded` — xem chú thích
 * của lá cờ đó về vì sao một cờ chứ không phải một bản sao. Tệp này tồn tại để
 * chỗ dùng đọc lên đúng nghĩa: `SecuritySettingsPage` dựng một *khối*, và nhập
 * một thứ tên là `VerifyContactPage` vào giữa nó sẽ khiến người đọc mã sau này
 * tưởng có hai trang lồng nhau.
 */

import VerifyContactPage from "../../pages/VerifyContactPage";

export default function ContactVerificationSection() {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <VerifyContactPage embedded />
    </section>
  );
}
