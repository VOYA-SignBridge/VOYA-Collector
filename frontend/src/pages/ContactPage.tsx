import { Link } from "react-router-dom";
import PageHeader from "../components/ui/PageHeader";
import { useAuth } from "../contexts/AuthContext";
import { useI18n } from "../i18n";
import { contactEmail } from "../lib/publicConfig";

/**
 * Liên hệ — trang công khai.
 *
 * Địa chỉ email liên hệ KHÔNG viết cứng trong mã: người vận hành đặt
 * `VITE_CONTACT_EMAIL` lúc triển khai. Chưa đặt thì trang nói thẳng cách khác để
 * được hỗ trợ, chứ không hiện một địa chỉ bịa ra hay một ô trống.
 */
export default function ContactPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const email = contactEmail();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <PageHeader
        title={t("Liên hệ")}
        subtitle={t("Cách nhận hỗ trợ và liên lạc với nhóm thực hiện dự án.")}
      />

      <section aria-labelledby="contact-help" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 id="contact-help" className="text-lg font-semibold text-slate-900">{t("Cần hỗ trợ?")}</h2>
        {user ? (
          <p className="text-slate-700">
            {t("Gửi một yêu cầu hỗ trợ trong ứng dụng để người trực nhận được ngay.")}{" "}
            <Link to="/settings/support" className="font-semibold text-ctu-blue hover:underline">{t("Mở Hỗ trợ")}</Link>
          </p>
        ) : (
          <p className="text-slate-700">
            {t("Nếu quên mật khẩu, dùng Quên mật khẩu ở trang đăng nhập.")}{" "}
            <Link to="/login" className="font-semibold text-ctu-blue hover:underline">{t("Đăng nhập")}</Link>
            {" · "}
            <Link to="/forgot-password" className="font-semibold text-ctu-blue hover:underline">{t("Quên mật khẩu?")}</Link>
          </p>
        )}
        {email ? (
          <p className="text-slate-700">
            {t("Hoặc gửi thư tới")}{" "}
            <a href={`mailto:${email}`} className="font-semibold text-ctu-blue hover:underline">{email}</a>
          </p>
        ) : (
          <p className="text-sm text-slate-500">
            {t("Địa chỉ email liên hệ chưa được thiết lập. Hãy hỏi người giới thiệu bạn dùng hệ thống.")}
          </p>
        )}
      </section>

      <section aria-labelledby="contact-who" className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 id="contact-who" className="text-lg font-semibold text-slate-900">{t("Đơn vị thực hiện")}</h2>
        <p className="text-slate-700">
          {t("Dự án nghiên cứu khoa học - Trường Công nghệ Thông tin và Truyền thông, Đại học Cần Thơ")}
        </p>
        <p className="text-slate-700">{t("Khu II, Đ. 3/2, Xuân Khánh, Ninh Kiều, Cần Thơ")}</p>
        <p className="text-sm">
          <a href="https://www.ctu.edu.vn" target="_blank" rel="noopener noreferrer" className="font-semibold text-ctu-blue hover:underline">
            ctu.edu.vn
          </a>
        </p>
      </section>

      <p className="text-sm text-slate-600">
        <Link to="/faq" className="font-semibold text-ctu-blue hover:underline">{t("Hỏi đáp")}</Link>
        {" · "}
        <Link to="/about" className="font-semibold text-ctu-blue hover:underline">{t("Giới thiệu")}</Link>
      </p>
    </div>
  );
}
