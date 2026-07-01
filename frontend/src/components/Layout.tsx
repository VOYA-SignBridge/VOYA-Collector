import { useState, useCallback, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearAuthToken, loadAuthToken } from "../api/axiosClient";
import { me as fetchMe } from "../api/auth";
import type { AuthUser } from "../api/auth";
import type { ReactNode } from "react";
import Button from "./ui/Button";

const AUTH_EVENT = "voya:auth-change";

export type FlatNavItem = { name: string; href: string; icon: string; end?: boolean };
export type NavSection = {
  section: true;
  name: string;
  icon: string;
  children: FlatNavItem[];
};
export type AnyNavItem = FlatNavItem | NavSection;

export default function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [hasToken, setHasToken] = useState<boolean>(() => !!loadAuthToken());
  const [user, setUser] = useState<AuthUser | null>(null);
  const isAuthPage = location.pathname === "/login" || location.pathname === "/register";

  useEffect(() => {
    const syncAuthState = () => {
      setHasToken(!!loadAuthToken());
    };

    window.addEventListener(AUTH_EVENT, syncAuthState);
    window.addEventListener("storage", syncAuthState);

    return () => {
      window.removeEventListener(AUTH_EVENT, syncAuthState);
      window.removeEventListener("storage", syncAuthState);
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function loadUser() {
      if (!hasToken) {
        setUser(null);
        return;
      }
      try {
        const u = await fetchMe();
        if (mounted) setUser(u);
      } catch (err) {
        if (mounted) setUser(null);
      }
    }

    loadUser();
    return () => {
      mounted = false;
    };
  }, [hasToken]);

  const navigation: AnyNavItem[] = [
    { name: "Trang chủ", href: "/", icon: "🏠", end: true },
    { name: "Đóng góp dữ liệu", href: "/upload", icon: "📤" },
    { name: "Thư viện nhãn", href: "/labels", icon: "🏷️" },
    { name: "Nhận dạng realtime", href: "/realtime", icon: "🖐️" },
    { name: "Huấn luyện model", href: "/training", icon: "🚀" },
    // AI Studio removed
  ];

  const handleNewSession = useCallback(() => {
    setSidebarOpen(false);
    navigate(0);
  }, [navigate]);

  const handleLogout = useCallback(() => {
    setSidebarOpen(false);
    clearAuthToken();
    setHasToken(false);
    navigate("/login");
  }, [navigate]);

  const NavItem = ({ item }: { item: FlatNavItem }) => (
    <NavLink
      to={item.href}
      end={item.end}
      className={({ isActive }) =>
        `group flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200 ${
          isActive
            ? "bg-gradient-to-r from-indigo-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/25"
            : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/60"
        }`
      }
      onClick={() => setSidebarOpen(false)}
    >
      <span className="mr-3 text-lg">{item.icon}</span>
      {item.name}
      <div className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </NavLink>
  );

  const SectionNavItem = ({ item }: { item: NavSection }) => (
    <div className="mt-3">
      <div className="px-4 py-2 flex items-center gap-2">
        <div className="flex-1 h-px bg-slate-200" />
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 shrink-0">
          <span className="mr-1">{item.icon}</span>
          {item.name}
        </span>
        <div className="flex-1 h-px bg-slate-200" />
      </div>
      <div className="space-y-1">
        {item.children.map((child) => (
          <NavLink
            key={child.href}
            to={child.href}
            end={child.end}
            className={({ isActive }) =>
              `group flex items-center pl-8 pr-4 py-2.5 text-sm font-medium rounded-xl transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-r from-indigo-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/25"
                  : "text-slate-500 hover:text-slate-900 hover:bg-slate-100/60"
              }`
            }
            onClick={() => setSidebarOpen(false)}
          >
            <span className="mr-3 text-base">{child.icon}</span>
            {child.name}
          </NavLink>
        ))}
      </div>
    </div>
  );

  if (isAuthPage) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20 overflow-x-hidden">
        <header className="fixed top-0 left-0 right-0 z-40 flex h-14 items-center justify-end border-b border-slate-200/60 bg-white/85 px-3 shadow-sm backdrop-blur-xl sm:px-4 lg:px-8">
          <nav className="flex items-center gap-2 rounded-full border border-slate-200/70 bg-slate-50/90 p-1 shadow-sm">
            <NavLink
              to="/login"
              className={({ isActive }) =>
                [
                  "inline-flex items-center rounded-full px-3.5 py-1.5 text-sm font-semibold transition-all duration-200 whitespace-nowrap",
                  isActive
                    ? "bg-gradient-to-r from-sky-600 to-indigo-600 text-white shadow-lg shadow-sky-500/25"
                    : "border border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100",
                ].join(" ")
              }
            >
              Đăng nhập
            </NavLink>
            <NavLink
              to="/register"
              className={({ isActive }) =>
                [
                  "inline-flex items-center rounded-full px-3.5 py-1.5 text-sm font-semibold transition-all duration-200 whitespace-nowrap",
                  isActive
                    ? "bg-gradient-to-r from-violet-600 to-cyan-500 text-white shadow-lg shadow-violet-500/25"
                    : "border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100",
                ].join(" ")
              }
            >
              Đăng ký
            </NavLink>
          </nav>
        </header>

        <main className="min-h-[calc(100dvh-3.5rem)] pt-14">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative flex bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20 overflow-x-hidden">
      <div
        className={`fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          sidebarOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-[min(18rem,82vw)] max-w-72 transform border-r border-slate-200/60 bg-white/80 shadow-xl backdrop-blur-xl transition-all duration-300 ease-in-out overflow-y-auto ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } lg:static lg:translate-x-0 lg:overflow-hidden ${sidebarOpen ? "lg:w-72 lg:max-w-72" : "lg:w-0 lg:max-w-0"}`}
      >
        <div className="flex h-dvh lg:h-full flex-col">
          <div className="flex items-center justify-between h-16 px-6 border-b border-slate-200/50">
            <div className="flex items-center min-w-0">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-cyan-500 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-lg shrink-0">
                {user?.username ? user.username.charAt(0).toUpperCase() : "C"}
              </div>
              <div className="ml-3 min-w-0">
                <div className="text-slate-800 font-semibold text-lg truncate">{user?.username ?? "CTU"}</div>
                <div className="text-slate-500 text-xs truncate">SignBridge</div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              aria-label="Đóng sidebar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2">
            {navigation.map((item) =>
              "section" in item && item.section ? (
                <SectionNavItem key={item.name} item={item} />
              ) : (
                <NavItem key={(item as FlatNavItem).name} item={item as FlatNavItem} />
              )
            )}
          </nav>

          <div className="mt-auto border-t border-slate-200/50 p-4">
            <div className="space-y-3 lg:hidden">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span>Đã kết nối</span>
              </div>

              <Button size="sm" onClick={handleNewSession} className="w-full justify-center px-3 py-2 text-xs sm:text-sm">
                Phiên mới
              </Button>

              {hasToken ? (
                <Button
                  size="sm"
                  variant="danger"
                  onClick={handleLogout}
                  className="w-full justify-center px-3 py-2 text-xs sm:text-sm"
                >
                  Đăng xuất
                </Button>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Button size="sm" onClick={() => navigate("/login")} className="w-full justify-center px-3 py-2 text-xs sm:text-sm">
                    Đăng nhập
                  </Button>
                  <Button size="sm" onClick={() => navigate("/register")} className="w-full justify-center px-3 py-2 text-xs sm:text-sm">
                    Đăng ký
                  </Button>
                </div>
              )}
            </div>

            <div className="hidden lg:block pt-4 text-xs text-slate-500 text-center">
              Phiên bản 1.0.0 © 2024 Voya Inc.
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 pt-14">
        <header className="fixed top-0 left-0 right-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-slate-200/60 bg-white/80 px-3 shadow-sm backdrop-blur-xl sm:px-4 lg:px-8">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen((current) => !current)}
              className="btn btn-ghost p-2 text-slate-600 hover:text-slate-900"
              aria-label="Toggle sidebar"
              aria-expanded={sidebarOpen}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent sm:text-base lg:text-xl">
                CTU.SignBridge
              </h1>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 sm:gap-3 w-auto min-w-0 justify-end flex-nowrap overflow-x-auto">
            <div className="hidden sm:flex items-center space-x-2">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-sm text-slate-600">Đã kết nối</span>
            </div>

            {hasToken ? (
              <Button size="sm" onClick={handleLogout} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                Đăng xuất
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Button size="sm" onClick={() => navigate("/login")} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                  Đăng nhập
                </Button>
                <Button size="sm" onClick={() => navigate("/register")} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                  Đăng ký
                </Button>
              </div>
            )}

            <Button size="sm" onClick={handleNewSession} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
              Phiên mới
            </Button>
          </div>
        </header>

        <main className="flex-1 p-3 sm:p-4 lg:p-8 overflow-visible lg:overflow-auto min-w-0">
          <div className="max-w-7xl mx-auto w-full min-w-0 animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
