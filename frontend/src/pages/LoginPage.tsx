import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { safeRedirectTarget } from "../utils/redirect";
import { login } from "../api/auth";
import { notifyAuthChange } from "../api/axiosClient";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, UserIcon } from "../components/auth/AuthInput";
import LoadingScreen from "../components/LoadingScreen";

type FormState = {
  identifier: string;
  password: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const destination = safeRedirectTarget(searchParams.get("next"));
  const [form, setForm] = useState<FormState>({ identifier: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [showLoading, setShowLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);

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
      await login({
        identifier: form.identifier.trim(),
        password: form.password,
      });

      notifyAuthChange();

      // Giữ màn hình chờ để không nháy lại form trong lúc điều hướng, nhưng
      // KHÔNG chờ cứng 3 giây như trước — route đích đã có Suspense fallback
      // riêng, nên độ trễ đó chỉ làm mọi lần đăng nhập chậm đi vô ích.
      setShowLoading(true);
      navigate(destination, { replace: true });
    } catch (err: unknown) {
      const error = err as Record<string, unknown> | null;
      const response = error?.response as Record<string, unknown> | undefined;
      const data = response?.data as Record<string, unknown> | undefined;

      const detail =
        (typeof data?.detail === "string" && data.detail) ||
        (typeof error?.userMessage === "string" && error.userMessage) ||
        (typeof error?.message === "string" && error.message) ||
        "Không thể đăng nhập";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  // After successful login, show the wave loading screen
  if (showLoading) {
    return <LoadingScreen label="Đang chuẩn bị giao diện…" />;
  }

  return (
    <AuthShell
      title="Đăng nhập"
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Chưa có tài khoản?</span>
          <Link
            to={searchParams.get("next") ? `/register?next=${encodeURIComponent(searchParams.get("next")!)}` : "/register"}
            className="font-semibold text-ctu-blue hover:text-ctu-navy"
          >
            Tạo tài khoản →
          </Link>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <AuthInput
          label="Tên đăng nhập hoặc email"
          icon={<UserIcon />}
          value={form.identifier}
          onChange={(e) => setForm((prev) => ({ ...prev, identifier: e.target.value }))}
          type="text"
          autoComplete="username"
          placeholder="vd: minh123 hoặc minh@example.com"
        />

        <AuthInput
          label="Mật khẩu"
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
              {showPassword ? "Ẩn" : "Hiện"}
            </button>
          }
        />

        <div className="text-right">
          <Link to="/forgot-password" className="text-sm font-semibold text-ctu-blue hover:text-ctu-navy">
            Quên mật khẩu?
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
          {loading ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </AuthShell>
  );
}

