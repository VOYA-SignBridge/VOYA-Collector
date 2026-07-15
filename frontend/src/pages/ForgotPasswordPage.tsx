import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/auth";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { MailIcon } from "../components/auth/AuthInput";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [sent, setSent] = useState(false);

  const canSubmit = useMemo(() => identifier.trim().length > 0 && !loading, [identifier, loading]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError("");

    try {
      const minWait = new Promise((resolve) => setTimeout(resolve, 800));
      const resetTask = forgotPassword(identifier.trim());

      await Promise.all([resetTask, minWait]);

      setSent(true);
    } catch (err: unknown) {
      const error = err as Record<string, unknown> | null;
      const response = error?.response as Record<string, unknown> | undefined;
      const data = response?.data as Record<string, unknown> | undefined;

      const detail =
        (typeof data?.detail === "string" && data.detail) ||
        (typeof error?.userMessage === "string" && error.userMessage) ||
        "Không thể gửi yêu cầu. Vui lòng thử lại.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Quên mật khẩu"
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Nhớ ra mật khẩu rồi?</span>
          <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            Quay lại đăng nhập →
          </Link>
        </div>
      }
    >
      {sent ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-relaxed text-emerald-800">
          Nếu tài khoản với thông tin bạn vừa nhập tồn tại, chúng tôi đã gửi email hướng dẫn đặt lại
          mật khẩu. Vui lòng kiểm tra hộp thư đến (và cả mục spam).
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm leading-relaxed text-slate-600">
            Nhập email hoặc tên đăng nhập của bạn. Chúng tôi sẽ gửi một liên kết để đặt lại mật khẩu.
          </p>

          <AuthInput
            label="Tên đăng nhập hoặc email"
            icon={<MailIcon />}
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            type="text"
            autoComplete="username"
            placeholder="vd: minh123 hoặc minh@example.com"
          />

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
            {loading ? "Đang gửi..." : "Gửi hướng dẫn đặt lại mật khẩu"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
