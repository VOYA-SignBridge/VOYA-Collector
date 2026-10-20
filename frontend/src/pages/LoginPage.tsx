import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login, loginTwoFactor } from "../api/auth";
import { notifyAuthChange } from "../api/axiosClient";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, UserIcon } from "../components/auth/AuthInput";
import LoadingScreen from "../components/LoadingScreen";
import { friendlyError } from "../lib/errors";
import { Trans, useI18n } from "../i18n";

type FormState = {
  identifier: string;
  password: string;
};

export default function LoginPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>({ identifier: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [showLoading, setShowLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  /** Vé bước hai. Khác rỗng = mật khẩu đã đúng, đang chờ mã. */
  const [challenge, setChallenge] = useState("");
  const [code, setCode] = useState("");

  const canSubmit = useMemo(
    () => form.identifier.trim().length > 0 && form.password.trim().length > 0 && !loading,
    [form.identifier, form.password, loading]
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError("");

    try {
      const result = await login({
        identifier: form.identifier.trim(),
        password: form.password,
      });

      // Tài khoản bật xác thực hai bước: chưa có phiên nào cả. Dừng ở đây và
      // hỏi mã. KHÔNG gọi `notifyAuthChange()` — làm vậy sẽ báo cho cả ứng dụng
      // rằng đã đăng nhập xong, và các màn hình khác sẽ bắt đầu gọi API bằng
      // một phiên chưa tồn tại.
      if (result.kind === "two_factor") {
        setChallenge(result.challenge);
        setLoading(false);
        return;
      }

      notifyAuthChange();

      // Bản trước ngồi chờ ĐÚNG 3 GIÂY rồi mới chuyển trang. Ba giây đó không
      // làm gì cả: `login()` đã trả về, cookie đã đặt, không có việc nền nào
      // đang chạy. Đó là 3 giây lấy của mỗi người dùng, mỗi lần đăng nhập.
      //
      // Nhưng xoá thẳng nó thì để lộ một vấn đề khác: `/upload` là chunk nạp
      // lười, nên chuyển ngay sẽ rơi vào khoảng trống của `<Suspense>` — người
      // dùng thấy màn hình chờ thứ hai ngay sau màn hình chờ thứ nhất.
      //
      // Nên: nạp trước chunk đích NGAY BÂY GIỜ, và chỉ chờ đúng bằng thời gian
      // nó cần. Sàn 400 ms để màn hình chờ không nhấp nháy trên máy nhanh;
      // trần 2,5 giây để mạng chậm không biến nó thành ngõ cụt — hết trần thì
      // chuyển trang và để `<Suspense>` lo nốt.
      setShowLoading(true);
      const warmup = import("./UploadPage").catch(() => undefined);
      const floor = new Promise((r) => setTimeout(r, 400));
      const ceiling = new Promise((r) => setTimeout(r, 2500));
      await Promise.all([floor, Promise.race([warmup, ceiling])]);
      navigate("/upload", { replace: true });
    } catch (err: unknown) {
      // `error.message` của axios ("Request failed with status code 401") từng
      // là nhánh dự phòng ở đây. Nó vừa vô nghĩa với người đăng nhập, vừa nói
      // ra mã trạng thái — thứ không việc gì phải hiện trên màn hình đăng nhập.
      //
      // `userMessage` là chuỗi do `axiosClient` tự gắn cho vài trường hợp đã
      // biết, nên nó vẫn được ưu tiên trước bộ lọc chung.
      const custom = (err as { userMessage?: unknown } | null)?.userMessage;
      setError(
        typeof custom === "string" && custom
          ? custom
          : friendlyError(err, t("Không đăng nhập được. Hãy kiểm tra lại email và mật khẩu.")),
      );
    } finally {
      setLoading(false);
    }
  };

  // After successful login, show the wave loading screen
  if (showLoading) {
    return <LoadingScreen label={t("Đang chuẩn bị giao diện…")} />;
  }

  /** Bước hai. Cùng `AuthShell` để người dùng thấy mình vẫn ở giữa một luồng. */
  const submitCode = async (e: FormEvent) => {
    e.preventDefault();
    if (loading || code.trim().length < 6) return;
    setLoading(true);
    setError("");
    try {
      await loginTwoFactor(challenge, code.trim());
      notifyAuthChange();
      setShowLoading(true);
      const warmup = import("./UploadPage").catch(() => undefined);
      const floor = new Promise((r) => setTimeout(r, 400));
      const ceiling = new Promise((r) => setTimeout(r, 2500));
      await Promise.all([floor, Promise.race([warmup, ceiling])]);
      navigate("/upload", { replace: true });
    } catch (err: unknown) {
      const custom = (err as { userMessage?: unknown } | null)?.userMessage;
      setError(
        typeof custom === "string" && custom
          ? custom
          : friendlyError(err, t("Mã không đúng hoặc đã hết hạn.")),
      );
      setLoading(false);
    }
  };

  if (challenge) {
    return (
      <AuthShell
        title={t("Xác thực hai bước")}
        footer={
          <button
            type="button"
            onClick={() => {
              setChallenge("");
              setCode("");
              setError("");
            }}
            className="text-sm font-semibold text-ctu-blue hover:text-ctu-navy"
          >
            {t("← Quay lại đăng nhập")}
          </button>
        }
      >
        <form onSubmit={submitCode} className="space-y-4">
          <p className="text-sm text-slate-600">
            <Trans
              k="Mở ứng dụng xác thực trên điện thoại và nhập mã 6 chữ số. Nếu mất điện thoại, hãy nhập một mã khôi phục dạng {mau}."
              vars={{ mau: <span className="font-mono">xxxxx-xxxxx</span> }}
            />
          </p>

          <div>
            <label
              htmlFor="tfa-login-code"
              className="block text-sm font-medium text-slate-700"
            >
              {t("Mã xác thực")}
            </label>
            <input
              id="tfa-login-code"
              value={code}
              onChange={(e) => setCode(e.target.value.trim())}
              // `one-time-code` cho phép iOS/Android gợi ý mã tự động.
              autoComplete="one-time-code"
              autoFocus
              maxLength={11}
              placeholder="000000"
              className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 text-center font-mono text-lg tracking-widest focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || code.trim().length < 6}
            className="w-full rounded-xl bg-ctu-blue px-4 py-3 font-semibold text-white transition hover:bg-ctu-navy disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2"
          >
            {loading ? t("Đang kiểm tra…") : t("Xác nhận")}
          </button>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={t("Đăng nhập")}
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("Chưa có tài khoản?")}</span>
          <Link to="/register" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            {t("Tạo tài khoản →")}
          </Link>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <AuthInput
          label={t("Tên đăng nhập hoặc email")}
          icon={<UserIcon />}
          value={form.identifier}
          onChange={(e) => setForm((prev) => ({ ...prev, identifier: e.target.value }))}
          type="text"
          autoComplete="username"
          placeholder={t("vd: minh123 hoặc minh@example.com")}
        />

        <AuthInput
          label={t("Mật khẩu")}
          icon={<LockIcon />}
          value={form.password}
          onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          placeholder="••••••••"
          trailing={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold text-ctu-blue hover:bg-ctu-blue/10"
            >
              {showPassword ? t("Ẩn") : t("Hiện")}
            </button>
          }
        />

        {/* MỘT đường khôi phục. Trước đây có hai — một gửi liên kết, một gửi mã
            — và người vừa quên mật khẩu không có cơ sở nào để chọn giữa chúng.
            Sự khác biệt là chi tiết triển khai, không phải câu hỏi cho họ. */}
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm font-semibold text-ctu-blue hover:text-ctu-navy">
            {t("Quên mật khẩu?")}
          </Link>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={!canSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && (
            <svg className="h-5 w-5 animate-spin text-white/80" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          {loading ? t("Đang đăng nhập...") : t("Đăng nhập")}
        </button>
      </form>
    </AuthShell>
  );
}

