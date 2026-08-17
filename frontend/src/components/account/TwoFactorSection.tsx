/**
 * Xác thực hai bước, trên trang `/account`.
 *
 * Ba quyết định giao diện có hệ quả ngoài thẩm mỹ:
 *
 * 1. **Bật là HAI bước, và màn hình phải cho thấy điều đó.** Cấp bí mật rồi bật
 *    luôn sẽ khoá người dùng ra khỏi tài khoản của chính họ khi ứng dụng xác
 *    thực quét hỏng hoặc đồng hồ điện thoại lệch — và lúc đó họ không còn đường
 *    nào quay lại.
 *
 * 2. **Mã khôi phục hiện MỘT lần và màn hình nói rõ điều đó.** Chúng chỉ tồn
 *    tại dạng đọc được đúng khoảnh khắc này; sau đó cơ sở dữ liệu chỉ giữ băm.
 *    Một hộp thoại đóng được bằng phím Esc mà không cảnh báo là cách người dùng
 *    mất chúng.
 *
 * 3. **Không có mã QR.** Dự án không có thư viện sinh QR ở phía giao diện, và
 *    thêm một phụ thuộc chỉ để vẽ ô vuông thì không đáng. Bí mật hiện dạng nhóm
 *    4 ký tự — mọi ứng dụng xác thực đều nhập tay được, và đó cũng là đường dự
 *    phòng khi máy ảnh hỏng. Ghi rõ trong docs/03-security/TWO_FACTOR.md là hạn chế đã biết.
 */

import { useCallback, useEffect, useState } from "react";

import {
  beginTwoFactorEnrollment,
  confirmTwoFactor,
  disableTwoFactor,
  fetchTwoFactorStatus,
  regenerateRecoveryCodes,
  type TwoFactorEnrollment,
  type TwoFactorStatus,
} from "../../api/account";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import { useI18n, tr } from "../../i18n";
import {
  AlertTriangleIcon,
  CopyIcon,
  ShieldCheckIcon,
  SmartphoneIcon,
} from "../ui/Icons";

function errorText(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  // `tr` chứ không phải `t`: đây là hàm thuần ở mức module, không có hook nào
  // gọi được ở đây. Đổi lại là chuỗi sinh ra sẽ không tự dựng lại khi đổi ngôn
  // ngữ — chấp nhận được vì nó chỉ là câu lỗi hiện ra rồi biến mất.
  return detail || tr("Đã xảy ra lỗi. Vui lòng thử lại.");
}

/** Mã khôi phục — hiện một lần duy nhất, kèm lời cảnh báo đúng mức. */
function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
    } catch {
      // Chép bị chặn (không phải HTTPS, hoặc quyền bị từ chối). Mã vẫn hiện
      // trên màn hình nên người dùng chép tay được — không cần báo lỗi.
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangleIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div>
          <p className="font-semibold text-amber-900">
            {t("Lưu {n} mã này ở nơi an toàn ngay bây giờ", { n: codes.length })}
          </p>
          <p className="mt-1 text-sm text-amber-800">
            {t("Đây là lần duy nhất chúng hiển thị. Mỗi mã dùng được một lần, và chúng là đường vào duy nhất nếu bạn mất điện thoại.")}
          </p>
        </div>
      </div>

      <ul className="mt-3 grid grid-cols-2 gap-2 font-mono text-sm sm:grid-cols-2">
        {codes.map((code) => (
          <li
            key={code}
            className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-center tracking-wider text-slate-800"
          >
            {code}
          </li>
        ))}
      </ul>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={copy}>
          <CopyIcon className="h-4 w-4" />
          {copied ? t("Đã chép") : t("Chép tất cả")}
        </Button>
        <Button onClick={onDone}>{t("Tôi đã lưu xong")}</Button>
      </div>
    </div>
  );
}

export default function TwoFactorSection() {
  const { t } = useI18n();
  const [status, setStatus] = useState<TwoFactorStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [enrollment, setEnrollment] = useState<TwoFactorEnrollment | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [password, setPassword] = useState("");
  const [confirmingDisable, setConfirmingDisable] = useState(false);

  const reload = useCallback(async () => {
    try {
      setStatus(await fetchTwoFactorStatus());
      setError("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      setEnrollment(await beginTwoFactorEnrollment());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      setCodes(await confirmTwoFactor(code.trim()));
      setEnrollment(null);
      setCode("");
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setBusy(true);
    setError("");
    try {
      await disableTwoFactor(password);
      setPassword("");
      setConfirmingDisable(false);
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    setBusy(true);
    setError("");
    try {
      setCodes(await regenerateRecoveryCodes(password));
      setPassword("");
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon className="h-5 w-5 text-ctu-blue" />
          <h2 className="text-lg font-semibold text-slate-900">
            {t("Xác thực hai bước")}
          </h2>
        </div>
        {!loading && status && (
          <Badge variant={status.enabled ? "success" : "neutral"}>
            {status.enabled ? t("Đang bật") : t("Chưa bật")}
          </Badge>
        )}
      </div>

      <p className="mt-2 text-sm text-slate-600">
        {t("Sau khi bật, mỗi lần đăng nhập bạn sẽ cần thêm mã 6 chữ số từ ứng dụng xác thực trên điện thoại. Mật khẩu bị lộ một mình sẽ không đủ để vào tài khoản.")}
      </p>

      {error && (
        <div
          role="alert"
          className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && <p className="mt-4 text-sm text-slate-500">{t("Đang tải…")}</p>}

      {codes && <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />}

      {/* --- Chưa bật, chưa bắt đầu --- */}
      {!loading && status && !status.enabled && !enrollment && !codes && (
        <div className="mt-4">
          <Button onClick={start} disabled={busy}>
            <SmartphoneIcon className="h-4 w-4" />
            {t("Bật xác thực hai bước")}
          </Button>
        </div>
      )}

      {/* --- Bước 1: nhập bí mật vào ứng dụng --- */}
      {enrollment && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <p className="text-sm font-medium text-slate-800">
            {t("Bước 1 — Thêm tài khoản vào ứng dụng xác thực")}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            {t("Mở Google Authenticator, Microsoft Authenticator, Aegis hoặc tương đương, chọn “Nhập khoá thủ công” và dán chuỗi dưới đây.")}
          </p>
          <p className="mt-3 select-all break-all rounded-lg border border-slate-300 bg-white px-3 py-2 text-center font-mono text-base tracking-widest text-slate-900">
            {enrollment.secret_grouped}
          </p>

          <label
            htmlFor="totp-code"
            className="mt-4 block text-sm font-medium text-slate-800"
          >
            {t("Bước 2 — Nhập mã 6 chữ số ứng dụng đang hiện")}
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              id="totp-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-center font-mono text-lg tracking-widest focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            />
            <Button onClick={confirm} disabled={busy || code.length !== 6}>
              {t("Xác nhận")}
            </Button>
            <Button variant="secondary" onClick={() => setEnrollment(null)} disabled={busy}>
              {t("Huỷ")}
            </Button>
          </div>
        </div>
      )}

      {/* --- Đã bật --- */}
      {!loading && status?.enabled && !codes && (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
            <p className="text-sm font-medium text-slate-800">{t("Mã khôi phục")}</p>
            <p className="mt-1 text-sm text-slate-600">
              {t("Còn {n} mã chưa dùng. Cấp lại sẽ huỷ toàn bộ mã cũ ngay lập tức.", { n: status.recovery_codes_left })}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <label
              htmlFor="tfa-password"
              className="block text-sm font-medium text-slate-800"
            >
              {t("Mật khẩu hiện tại")}
            </label>
            <p className="mt-1 text-sm text-slate-600">
              {t("Bắt buộc cho cả hai thao tác dưới đây. Nếu không, người mượn được máy đang mở của bạn sẽ gỡ được lớp bảo vệ này.")}
            </p>
            <input
              id="tfa-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="mt-2 w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="secondary" onClick={regenerate} disabled={busy || !password}>
                {t("Cấp lại mã khôi phục")}
              </Button>
              {confirmingDisable ? (
                <>
                  <Button variant="danger" onClick={turnOff} disabled={busy || !password}>
                    {t("Xác nhận tắt")}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setConfirmingDisable(false)}
                    disabled={busy}
                  >
                    {t("Giữ nguyên")}
                  </Button>
                </>
              ) : (
                <Button
                  variant="danger"
                  onClick={() => setConfirmingDisable(true)}
                  disabled={busy}
                >
                  {t("Tắt xác thực hai bước")}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
