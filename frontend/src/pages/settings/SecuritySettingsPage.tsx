import TwoFactorSection from "../../components/account/TwoFactorSection";
import { useI18n } from "../../i18n";

/**
 * Bảo mật — `/settings/security`.
 *
 * Tách khỏi trang Tài khoản, nơi xác thực hai bước từng nằm lẫn giữa đổi tên
 * đăng nhập và ký chấp thuận pháp lý. Ba việc đó không cùng một loại: hai việc
 * đầu là hồ sơ, việc thứ ba là điều khoản, còn 2FA là thứ người ta tìm đến khi
 * nghi tài khoản có vấn đề — và lúc đó họ tìm chữ "Bảo mật", không phải "Tài
 * khoản".
 *
 * Trang này là ĐÍCH của thông báo loại `security`. Đó là lý do nó phải có
 * đường dẫn riêng thay vì là một tab lưu trong state.
 */
export default function SecuritySettingsPage() {
  const { t } = useI18n();

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-900">{t("Bảo mật")}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {t("Lớp bảo vệ thứ hai cho tài khoản, và cách lấy lại quyền truy cập nếu mất thiết bị.")}
        </p>
      </header>

      <TwoFactorSection />

      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
        <p className="font-medium text-slate-900">{t("Quên mật khẩu?")}</p>
        <p className="mt-1">
          {t(
            "Đổi mật khẩu qua luồng khôi phục sẽ thu hồi mọi phiên đăng nhập trên mọi thiết bị — kể cả phiên của người có thể đã chiếm được tài khoản.",
          )}
        </p>
      </div>
    </section>
  );
}
