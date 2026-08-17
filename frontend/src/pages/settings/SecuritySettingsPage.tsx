/**
 * Bảo mật — `/settings/security`.
 *
 * Một cửa cho mọi thứ trả lời câu "tài khoản của tôi có an toàn không"
 * --------------------------------------------------------------------
 * Trước 16/08/2026 trang này chỉ có xác thực hai bước và **một khối chữ tên
 * "Quên mật khẩu?" không có nút nào**. Người muốn đổi mật khẩu định kỳ phải giả
 * vờ quên nó, chờ thư, rồi bấm liên kết; còn "Xác minh liên hệ" thì nằm ở một
 * mục thứ ba trong thanh Cài đặt, ngang hàng với Tổ chức và Gói dịch vụ.
 *
 * Ba việc ấy trả lời **cùng một câu hỏi**: tài khoản này có an toàn không, và
 * tôi có lấy lại được nó không. Người đi tìm chúng đi tìm chữ "Bảo mật". Nên
 * chúng ở đây, theo thứ tự cấp bách giảm dần:
 *
 *     1. Đổi mật khẩu       việc thường xuyên nhất, và là việc gấp khi nghi ngờ
 *     2. Xác minh liên hệ   điều kiện để lấy lại tài khoản — vô hình cho tới
 *                           lúc cần, mà lúc cần thì đã muộn
 *     3. Xác thực hai bước  lớp thêm, không phải lớp nền
 *
 * Vì sao KHÔNG bắt buộc bật 2FA mới cho đổi mật khẩu
 * ---------------------------------------------------
 * Đó là yêu cầu ban đầu, và nó tạo một đường khoá cửa: người dùng chính của hệ
 * thống này là người khiếm thính/khiếm ngôn, và một người không có điện thoại
 * thông minh sẽ vĩnh viễn không đổi được mật khẩu. Hướng hỏng đó tệ hơn thứ nó
 * định chặn. Máy chủ vì vậy đòi **mật khẩu hiện tại luôn luôn**, và yếu tố thứ
 * hai **chỉ khi đã bật** — với mã khôi phục luôn thay được mã TOTP.
 *
 * Trang này là ĐÍCH của thông báo loại `security`. Đó là lý do nó phải có đường
 * dẫn riêng thay vì là một tab lưu trong state.
 */

import { useCallback, useState } from "react";

import TwoFactorSection from "../../components/account/TwoFactorSection";
import ContactVerificationSection from "../../components/account/ContactVerificationSection";
import Button from "../../components/ui/Button";
import { AlertTriangleIcon } from "../../components/ui/Icons";
import { changePassword } from "../../api/auth";
import { useToast } from "../../hooks/useToast";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";

export default function SecuritySettingsPage() {
  const { t } = useI18n();

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-900">{t("Bảo mật")}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {t("Đổi mật khẩu, xác minh địa chỉ liên hệ, và bật lớp bảo vệ thứ hai.")}
        </p>
      </header>

      <PasswordSection />
      <ContactVerificationSection />
      <TwoFactorSection />
    </section>
  );
}

// ------------------------------------------------------------ đổi mật khẩu

/**
 * Ô nhập mã chỉ hiện SAU KHI máy chủ nói là cần.
 *
 * Cách khác là hỏi `/2fa/status` lúc dựng rồi tự quyết định — và đó là hai
 * nguồn sự thật cho cùng một câu hỏi. Chúng lệch nhau ngay khi người dùng bật
 * 2FA ở một tab khác: giao diện không hiện ô mã, máy chủ vẫn đòi, và người dùng
 * gặp một lỗi đỏ không nói được phải làm gì.
 *
 * Nên: gửi trước, và mở ô mã khi máy chủ trả `detail.code === "2fa_required"`.
 * Máy chủ là nơi duy nhất biết sự thật, và câu trả lời của nó mang theo hướng
 * dẫn cho bước kế.
 */
function PasswordSection() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [code, setCode] = useState("");
  const [needsCode, setNeedsCode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const mismatch = again.length > 0 && next !== again;
  const canSave =
    !busy && current.length >= 1 && next.length >= 8 && next === again;

  const submit = useCallback(async () => {
    if (!canSave) return;
    setBusy(true);
    setError("");
    try {
      const res = await changePassword({
        currentPassword: current,
        newPassword: next,
        code: needsCode ? code.trim() : undefined,
      });
      toast.success(res.message);
      setCurrent("");
      setNext("");
      setAgain("");
      setCode("");
      setNeedsCode(false);
      // KHÔNG tự đá người dùng về trang đăng nhập ở đây. Máy chủ đã thu hồi mọi
      // phiên, nên lượt gọi API kế tiếp sẽ nhận 401 và bộ chặn của axios đưa họ
      // ra. Tự điều hướng là làm cùng một việc ở hai chỗ, và hai chỗ ấy sẽ lệch
      // nhau vào ngày quy tắc thu hồi đổi.
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      const codeName =
        detail && typeof detail === "object"
          ? (detail as { code?: string }).code
          : undefined;
      if (codeName === "2fa_required") {
        setNeedsCode(true);
        setError(t("Tài khoản đang bật xác thực hai bước. Nhập mã 6 chữ số, hoặc một mã khôi phục."));
      } else {
        setError(friendlyError(err, t("Không đổi được mật khẩu.")));
      }
    } finally {
      setBusy(false);
    }
  }, [canSave, current, next, code, needsCode, toast, t]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h3 className="text-lg font-semibold text-slate-900">{t("Đổi mật khẩu")}</h3>
      <p className="mt-1 text-sm text-slate-600">
        {t("Cần mật khẩu hiện tại. Sau khi đổi, mọi thiết bị sẽ bị đăng xuất — kể cả thiết bị bạn đang dùng — nên bạn sẽ phải đăng nhập lại.")}
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="min-w-0 sm:col-span-2">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            {t("Mật khẩu hiện tại")}
          </span>
          <input
            type="password"
            value={current}
            autoComplete="current-password"
            onChange={(e) => setCurrent(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
          />
        </label>

        <label className="min-w-0">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            {t("Mật khẩu mới")}
          </span>
          <input
            type="password"
            value={next}
            autoComplete="new-password"
            onChange={(e) => setNext(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
          />
        </label>

        <label className="min-w-0">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            {t("Nhập lại mật khẩu mới")}
          </span>
          <input
            type="password"
            value={again}
            autoComplete="new-password"
            onChange={(e) => setAgain(e.target.value)}
            className={`w-full rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${
              mismatch
                ? "border-red-300 focus:border-red-400 focus:ring-red-400"
                : "border-slate-300 focus:border-ctu-blue focus:ring-ctu-blue"
            }`}
          />
        </label>

        {needsCode && (
          <label className="min-w-0 sm:col-span-2">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              {t("Mã xác thực hai bước, hoặc mã khôi phục")}
            </span>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={32}
              placeholder="123456"
              className="w-full rounded-xl border border-slate-300 px-3 py-2 font-mono text-sm tracking-widest focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
            />
          </label>
        )}
      </div>

      {/* Điều kiện nói ra NGAY CẠNH nút, không phải bằng chữ xám dưới đáy. Một
          cái nút mờ đi mà không nói vì sao là chỗ người dùng bấm ba lần rồi bỏ
          cuộc — đúng thứ đã xảy ra ở ô soạn phiếu hỗ trợ. */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button loading={busy} disabled={!canSave} onClick={() => void submit()}>
          {t("Đổi mật khẩu")}
        </Button>
        {!canSave && !busy && (
          <span className="text-xs text-slate-500">
            {current.length < 1
              ? t("Nhập mật khẩu hiện tại.")
              : next.length < 8
                ? t("Mật khẩu mới cần ít nhất 8 ký tự.")
                : mismatch || again.length === 0
                  ? t("Hai ô mật khẩu mới phải giống nhau.")
                  : ""}
          </span>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
        {t("Quên mật khẩu hiện tại? Hãy đăng xuất rồi dùng \"Quên mật khẩu\" ở màn hình đăng nhập. Nếu bạn cũng không mở được hộp thư, hãy liên hệ quản trị viên — họ mở lại được cửa mà không cần biết mật khẩu của bạn.")}
      </p>
    </section>
  );
}
