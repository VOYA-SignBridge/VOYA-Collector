import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { saveAuthToken } from "../api/axiosClient";

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
    <div className="min-h-[calc(100dvh-3.5rem)] flex items-start sm:items-center justify-center px-3 sm:px-4 py-3 sm:py-8">
      <div className="relative w-full max-w-6xl overflow-hidden rounded-[1.5rem] sm:rounded-[2rem] border border-white/60 bg-white/75 shadow-[0_30px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl">
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] lg:min-h-[720px]">
          <aside className="order-1 lg:order-1 relative overflow-hidden bg-gradient-to-br from-indigo-600 via-violet-600 to-cyan-500 px-5 py-6 sm:px-8 sm:py-8 lg:px-10 lg:py-12 text-white">
            <div className="absolute inset-0 opacity-20">
              <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white blur-3xl" />
              <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-cyan-300 blur-3xl" />
            </div>

            <div className="relative flex h-full flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-2 text-xs sm:text-sm backdrop-blur">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-300 animate-pulse" />
                  Login bảo mật cho VOYA
                </div>

                <h1 className="mt-5 sm:mt-8 max-w-md text-2xl font-semibold leading-tight tracking-tight sm:text-4xl">
                  Đăng nhập để quản lý dữ liệu nhanh hơn.
                </h1>

                <p className="mt-3 sm:mt-5 max-w-xl text-sm leading-6 text-white/85 sm:text-base sm:leading-7">
                  Quản lý phiên thu thập, theo dõi dataset theo user, và mở khóa
                  quyền admin khi cần duyệt hoặc xoá mẫu.
                </p>
              </div>

              {/* <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur">
                  <div className="text-sm text-white/70">Quyền user</div>
                  <div className="mt-1 text-lg font-medium">Upload và xem dữ liệu của mình</div>
                </div>
                <div className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur">
                  <div className="text-sm text-white/70">Quyền admin</div>
                  <div className="mt-1 text-lg font-medium">Quản lý toàn bộ dataset</div>
                </div>
              </div> */}
            </div>
          </aside>

          <section className="order-2 lg:order-2 px-5 py-6 sm:px-8 sm:py-8 lg:px-12 lg:py-14">
            <div className="mx-auto flex h-full max-w-xl flex-col justify-center">
              <div className="mb-5 sm:mb-8">
                <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900">
                  Chào mừng quay lại
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  Đăng nhập bằng username hoặc email.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Username hoặc email
                  </span>
                  <input
                    value={form.identifier}
                    onChange={(e) => setForm((prev) => ({ ...prev, identifier: e.target.value }))}
                    type="text"
                    autoComplete="username"
                    placeholder="vd: minh123 hoặc minh@example.com"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">
                    Mật khẩu
                  </span>
                  <div className="relative">
                    <input
                      value={form.password}
                      onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      placeholder="••••••••"
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
                    {loading ? "Đang đăng nhập..." : "Đăng nhập"}
                  </span>
                </button>

                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-sm text-slate-500">
                  <span>Chưa có tài khoản?</span>
                  <Link to="/register" className="font-medium text-indigo-600 hover:text-indigo-700">
                    Tạo tài khoản
                  </Link>
                </div>
              </form>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}