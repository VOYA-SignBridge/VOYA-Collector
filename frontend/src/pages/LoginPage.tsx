import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { saveAuthToken } from "../api/axiosClient";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, UserIcon } from "../components/auth/AuthInput";

type FormState = {
  identifier: string;
  password: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>({ identifier: "", password: "" });
  const [loading, setLoading] = useState(false);
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
      const res = await login({
        identifier: form.identifier.trim(),
        password: form.password,
      });

      saveAuthToken(res.access_token);
      navigate("/upload", { replace: true });
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

  return (
    <AuthShell
      title="Đăng nhập"
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Chưa có tài khoản?</span>
          <Link to="/register" className="font-semibold text-ctu-blue hover:text-ctu-navy">
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
          className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </AuthShell>
  );
}
