import { type FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api/auth";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon } from "../components/auth/AuthInput";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [done, setDone] = useState(false);

  const passwordError =
    password.length > 0 && password.length < 8 ? "Mật khẩu phải có ít nhất 8 ký tự." : "";
  const confirmPasswordError =
    confirmPassword.length > 0 && password !== confirmPassword ? "Mật khẩu xác nhận không khớp." : "";

  const canSubmit = useMemo(
    () => password.length >= 8 && password === confirmPassword && !loading,
    [password, confirmPassword, loading]
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitAttempted(true);
    if (!canSubmit) return;

    setLoading(true);
    setError("");

    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err: unknown) {
      const error = err as Record<string, unknown> | null;
      const response = error?.response as Record<string, unknown> | undefined;
      const data = response?.data as Record<string, unknown> | undefined;

      const detail =
        (typeof data?.detail === "string" && data.detail) ||
        (typeof error?.userMessage === "string" && error.userMessage) ||
        "Không thể đặt lại mật khẩu. Vui lòng thử lại.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Đặt lại mật khẩu"
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Nhớ ra mật khẩu rồi?</span>
          <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            Quay lại đăng nhập →
          </Link>
        </div>
      }
    >
      {!token ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Liên kết đặt lại mật khẩu bị thiếu hoặc không hợp lệ. Vui lòng yêu cầu một liên kết mới.
          </div>
          <Link
            to="/forgot-password"
            className="block w-full rounded-xl bg-ctu-blue px-5 py-3.5 text-center font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy"
          >
            Yêu cầu liên kết mới →
          </Link>
        </div>
      ) : done ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            Mật khẩu đã được đặt lại thành công. Bạn có thể đăng nhập bằng mật khẩu mới ngay bây giờ.
          </div>
          <Link
            to="/login"
            className="block w-full rounded-xl bg-ctu-blue px-5 py-3.5 text-center font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy"
          >
            Đăng nhập →
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <AuthInput
            label="Mật khẩu mới"
            icon={<LockIcon />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Tối thiểu 8 ký tự"
            error={passwordError || (submitAttempted && !password ? "Vui lòng nhập mật khẩu mới." : "")}
          />

          <AuthInput
            label="Xác nhận mật khẩu mới"
            icon={<LockIcon />}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Nhập lại mật khẩu mới"
            error={confirmPasswordError}
            trailing={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="rounded-lg px-3 py-1.5 text-xs font-semibold text-ctu-blue hover:bg-ctu-blue/10"
              >
                {showPassword ? "Ẩn" : "Hiện"}
              </button>
            }
          />

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Đang đặt lại..." : "Đặt lại mật khẩu"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
