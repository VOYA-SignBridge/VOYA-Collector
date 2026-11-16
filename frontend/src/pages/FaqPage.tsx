import { Link } from "react-router-dom";
import PageHeader from "../components/ui/PageHeader";
import { useI18n } from "../i18n";

/**
 * Hỏi đáp — trang công khai.
 *
 * `<details>` gốc chứ không phải thành phần tự dựng: bàn phím (Enter/Space) và trình
 * đọc màn hình dùng được không cần thêm mã. Câu trả lời chỉ nói điều hệ thống THẬT
 * SỰ làm; mỗi câu nhắc tới một nút hay mục có thật trong ứng dụng.
 */
export default function FaqPage() {
  const { t } = useI18n();

  const items: { q: string; a: string }[] = [
    {
      q: t("CTU.SignBridge là gì?"),
      a: t("Nền tảng của Trường Công nghệ Thông tin và Truyền thông, Đại học Cần Thơ, thu thập ký hiệu do cộng đồng đóng góp để huấn luyện máy nhận dạng Ngôn ngữ Ký hiệu Việt Nam."),
    },
    {
      q: t("Ai đóng góp được?"),
      a: t("Bất kỳ ai có tài khoản và đồng ý với điều khoản sử dụng. Bạn không cần biết lập trình; chỉ cần làm được ký hiệu trước camera."),
    },
    {
      q: t("Tôi cần chuẩn bị gì để ghi một ký hiệu?"),
      a: t("Một máy tính hoặc điện thoại có camera và trình duyệt mới (Chrome, Edge, Firefox hoặc Safari). Đứng nơi đủ sáng, nền đơn giản, để hai tay nằm trọn trong khung hình. Khi trình duyệt hỏi, hãy cho phép dùng camera."),
    },
    {
      q: t("Camera không hoạt động thì sao?"),
      a: t("Kiểm tra biểu tượng camera cạnh thanh địa chỉ và cho phép trang này dùng camera, rồi tải lại trang. Đảm bảo không có ứng dụng nào khác đang dùng camera."),
    },
    {
      q: t("Dữ liệu của tôi được dùng vào việc gì?"),
      a: t("Để huấn luyện và đánh giá mô hình nhận dạng ký hiệu. Mỗi bản ghi mới chờ người kiểm duyệt xem xét. Chi tiết nằm trong Chính sách quyền riêng tư."),
    },
    {
      q: t("Tôi xem, tải về hoặc rút lại dữ liệu ở đâu?"),
      a: t("Sau khi đăng nhập, vào Cài đặt: mục Dữ liệu của tôi để tải về, mục Đồng thuận để xem và rút đồng thuận."),
    },
    {
      q: t("Tôi quên mật khẩu?"),
      a: t("Ở trang đăng nhập, chọn Quên mật khẩu và làm theo hướng dẫn để nhận liên kết đặt lại qua email. Nếu không nhận được email, hãy liên hệ quản trị viên."),
    },
    {
      q: t("Tôi mất điện thoại dùng cho xác thực hai bước?"),
      a: t("Dùng một mã khôi phục bạn đã lưu khi bật tính năng này. Nếu không còn mã nào, hãy liên hệ quản trị viên để được gỡ xác thực hai bước."),
    },
    {
      q: t("Ghi nhớ đăng nhập có an toàn không?"),
      a: t("Chỉ nên bật trên thiết bị của riêng bạn. Ở Cài đặt, mục Bảo mật cho bạn xem mọi thiết bị đang đăng nhập và đăng xuất từng thiết bị."),
    },
    {
      q: t("Tôi đổi được tên đăng nhập không?"),
      a: t("Không. Tên đăng nhập gắn với dữ liệu bạn đã đóng góp nên không đổi được. Bạn đổi được ảnh đại diện và địa chỉ email; cần sửa tên đăng nhập, hãy liên hệ quản trị viên."),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader
        title={t("Hỏi đáp")}
        subtitle={t("Những câu hỏi thường gặp. Không thấy câu trả lời? Hãy liên hệ chúng tôi.")}
      />

      <div className="space-y-3">
        {items.map((item) => (
          <details key={item.q} className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <summary className="cursor-pointer list-none font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue [&::-webkit-details-marker]:hidden">
              {item.q}
            </summary>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{item.a}</p>
          </details>
        ))}
      </div>

      <p className="text-sm text-slate-600">
        {t("Cần thêm trợ giúp?")}{" "}
        <Link to="/contact" className="font-semibold text-ctu-blue hover:underline">{t("Liên hệ")}</Link>
      </p>
    </div>
  );
}
