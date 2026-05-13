import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register, login } from "../api/auth";
import { saveAuthToken } from "../api/axiosClient";

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

      const res = await login({
        identifier: form.email.trim(),
        password: form.password,
      });

      saveAuthToken(res.access_token);
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
    <div className="min-h-[calc(100vh-2rem)] flex items-center justify-center px-4 py-8">
      <div className="relative w-full max-w-6xl overflow-hidden rounded-[2rem] border border-white/60 bg-white/70 shadow-[0_30px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl">
        <div className="grid lg:grid-cols-[0.95fr_1.05fr] min-h-[720px]">
          <section className="order-2 lg:order-1 px-6 py-8 sm:px-10 lg:px-12 lg:py-14">
            <div className="mx-auto flex h-full max-w-xl flex-col justify-center">
              <div className="mb-8">
                <h2 className="text-3xl font-semibold tracking-tight text-slate-900">
                  Tạo tài khoản mới
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  Dùng username và email riêng cho mỗi người thu thập.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Username
                  </span>
                  <input
                    value={form.username}
                    onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
                    type="text"
                    autoComplete="username"
                    placeholder="vd: minh123"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Email
                  </span>
                  <input
                    value={form.email}
                    onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                    type="email"
                    autoComplete="email"
                    placeholder="vd: minh@example.com"
                    aria-invalid={!!emailError}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                  />
                  {(emailError || (submitAttempted && !email)) ? (
                    <span className="mt-2 block text-sm text-amber-700">
                      {emailError || "Vui lòng nhập email."}
                    </span>
                  ) : null}
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Mật khẩu
                  </span>
                  <input
                    value={form.password}
                    onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Tối thiểu 8 ký tự"
                    aria-invalid={!!passwordError}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                  />
                  {(passwordError || (submitAttempted && !form.password)) ? (
                    <span className="mt-2 block text-sm text-amber-700">
                      {passwordError || "Vui lòng nhập mật khẩu."}
                    </span>
                  ) : null}
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Xác nhận mật khẩu
                  </span>
                  <div className="relative">
                    <input
                      value={form.confirmPassword}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, confirmPassword: e.target.value }))
                      }
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="Nhập lại mật khẩu"
                      aria-invalid={!!confirmPasswordError}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 pr-24 text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute inset-y-0 right-2 my-2 rounded-xl px-3 text-sm font-medium text-slate-500 hover:bg-slate-100"
                    >
                      {showPassword ? "Ẩn" : "Hiện"}
                    </button>
                  </div>
                </label>

                {confirmPasswordError ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {confirmPasswordError}
                  </div>
                ) : null}

                {error ? (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {error}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="group relative inline-flex w-full items-center justify-center overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-600 via-violet-600 to-cyan-500 px-5 py-3.5 font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <span className="absolute inset-0 bg-white/0 transition group-hover:bg-white/10" />
                  <span className="relative">
                    {loading ? "Đang tạo tài khoản..." : "Tạo tài khoản"}
                  </span>
                </button>

                <div className="flex items-center justify-between text-sm text-slate-500">
                  <span>Đã có tài khoản?</span>
                  <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-700">
                    Đăng nhập
                  </Link>
                </div>
              </form>
            </div>
          </section>

          <aside className="order-1 lg:order-2 relative overflow-hidden bg-gradient-to-br from-slate-950 via-indigo-950 to-cyan-900 px-8 py-10 text-white">
            <div className="absolute inset-0 opacity-20">
              <div className="absolute top-10 left-10 h-40 w-40 rounded-full bg-cyan-300 blur-3xl" />
              <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-indigo-400 blur-3xl" />
            </div>

            <div className="relative flex h-full flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-3 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm backdrop-blur">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-300 animate-pulse" />
                  Tài khoản cho từng người thu thập
                </div>

                <h1 className="mt-8 max-w-md text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
                  Phân quyền rõ ràng, dữ liệu sạch hơn.
                </h1>

                {/* <p className="mt-5 max-w-xl text-base leading-7 text-white/80 sm:text-lg">
                  Mỗi lần upload sẽ được gắn theo user đăng nhập. Admin có thể duyệt,
                  quản lý hoặc xoá mẫu khi cần.
                </p> */}
              </div>

              {/* <div className="grid gap-4">
                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur">
                  <div className="text-sm text-white/70">UUID user</div>
                  <div className="mt-1 text-lg font-medium">Không dùng ID tăng dần</div>
                </div>
                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur">
                  <div className="text-sm text-white/70">Backward compatible</div>
                  <div className="mt-1 text-lg font-medium">Guest upload vẫn có thể giữ nguyên</div>
                </div>
              </div> */}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
