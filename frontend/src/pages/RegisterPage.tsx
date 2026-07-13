import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register, login } from "../api/auth";
import { notifyAuthChange } from "../api/axiosClient";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, MailIcon, UserIcon } from "../components/auth/AuthInput";

type FormState = {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const email = form.email.trim();
  const emailError =
    email.length > 0 && !EMAIL_PATTERN.test(email)
      ? "Email không đúng định dạng."
      : "";
  const passwordError =
    form.password.length > 0 && form.password.length < 8
      ? "Mật khẩu phải có ít nhất 8 ký tự."
      : "";
  const confirmPasswordError =
    form.confirmPassword && form.password !== form.confirmPassword
      ? "Mật khẩu xác nhận không khớp."
      : "";

  const canSubmit = useMemo(() => {
    return (
      form.username.trim().length >= 3 &&
      EMAIL_PATTERN.test(form.email.trim()) &&
      form.password.length >= 8 &&
      form.password === form.confirmPassword &&
      !loading
    );
  }, [form, loading]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitAttempted(true);
    if (!canSubmit) {
      setError("");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
      });

      // Auto-login after register: sets the auth cookies, then notify + go.
      await login({
        identifier: form.email.trim(),
        password: form.password,
      });

      notifyAuthChange();
      navigate("/upload", { replace: true });
    } catch (err: unknown) {
      const errorObj = err as {
        response?: { data?: { detail?: string } };
        userMessage?: string;
        message?: string;
      };
      const detail =
        errorObj.response?.data?.detail ||
        errorObj.userMessage ||
        errorObj.message ||
        "Không thể đăng ký";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Tạo tài khoản"
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Đã có tài khoản?</span>
          <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            Đăng nhập →
          </Link>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <AuthInput
          label="Username"
          icon={<UserIcon />}
          value={form.username}
          onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
          type="text"
          autoComplete="username"
          placeholder="vd: minh123"
        />

        <AuthInput
          label="Email"
          icon={<MailIcon />}
          value={form.email}
          onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
          type="email"
          autoComplete="email"
          placeholder="vd: minh@example.com"
          error={emailError || (submitAttempted && !email ? "Vui lòng nhập email." : "")}
        />

        <AuthInput
          label="Mật khẩu"
          icon={<LockIcon />}
          value={form.password}
          onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          placeholder="Tối thiểu 8 ký tự"
          error={passwordError || (submitAttempted && !form.password ? "Vui lòng nhập mật khẩu." : "")}
        />

        <AuthInput
          label="Xác nhận mật khẩu"
          icon={<LockIcon />}
          value={form.confirmPassword}
          onChange={(e) => setForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          placeholder="Nhập lại mật khẩu"
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
          {loading ? "Đang tạo tài khoản..." : "Tạo tài khoản"}
        </button>
      </form>
    </AuthShell>
  );
}
