import { useState, useCallback, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearAuthToken } from "../api/axiosClient";
import { logout as apiLogout } from "../api/auth";
import { useAuth, hasSessionHint } from "../contexts/AuthContext";
import { usePresence } from "../hooks/usePresence";
import { useIdleLogout } from "../hooks/useIdleLogout";
import WarningBanner from "./WarningBanner";
import type { ReactNode } from "react";
import Button from "./ui/Button";
import { ChipIcon, HandIcon, HomeIcon, RefreshIcon, TagIcon, UploadIcon } from "./ui/Icons";
import { useToast } from "../hooks/useToast";
import { requestNewSession } from "../utils/session";
import Footer from "./Footer";

const AUTH_EVENT = "voya:auth-change";

export type FlatNavItem = { name: string; href: string; icon: ReactNode; end?: boolean };
export type NavSection = {
  section: true;
  name: string;
  icon: ReactNode;
  children: FlatNavItem[];
};
export type AnyNavItem = FlatNavItem | NavSection;

export default function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();
  const location = useLocation();
  // User comes from the single shared AuthProvider (no duplicate /auth/me here).
  const { user } = useAuth();
  // Presence heartbeat + opt-in precise geolocation for the admin monitor.
  usePresence(!!user);
  // Inactivity auto-logout (default 90 min of no real interaction → sign out).
  useIdleLogout(!!user);
  // Synchronous session hint just for instant chrome painting (sidebar/header)
  // so a logged-in reload doesn't flash the guest layout while /auth/me is in
  // flight. No network — reads the token/cookie hint and updates on auth events.
  const [hasToken, setHasToken] = useState<boolean>(() => hasSessionHint());
  const AUTH_PAGE_PATHS = ["/login", "/register", "/forgot-password", "/reset-password"];
  const isAuthPage = AUTH_PAGE_PATHS.includes(location.pathname);

  useEffect(() => {
    const syncAuthState = () => {
      setHasToken(hasSessionHint());
    };

    window.addEventListener(AUTH_EVENT, syncAuthState);
    window.addEventListener("storage", syncAuthState);

    return () => {
      window.removeEventListener(AUTH_EVENT, syncAuthState);
      window.removeEventListener("storage", syncAuthState);
    };
  }, []);

  const navIconClass = "h-5 w-5";
  const baseNavigation: AnyNavItem[] = [
    { name: "Trang chủ", href: "/", icon: <HomeIcon className={navIconClass} />, end: true },
    { name: "Đóng góp dữ liệu", href: "/upload", icon: <UploadIcon className={navIconClass} /> },
    { name: "Thư viện nhãn", href: "/labels", icon: <TagIcon className={navIconClass} /> },
    { name: "Nhận dạng realtime", href: "/realtime", icon: <HandIcon className={navIconClass} /> },
    { name: "Huấn luyện model", href: "/training", icon: <ChipIcon className={navIconClass} /> },
  ];

  const adminNavigation: AnyNavItem[] = [
    {
      section: true,
      name: "Quản trị",
      icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>,
      children: [
        { name: "Quản lý dữ liệu", href: "/admin/data", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2 1.5 3 5 3s5-1 5-3V7M4 7c0 2 1.5 3 5 3s5-1 5-3M4 7c0-2 1.5-3 5-3s5 1 5 3m0 5c0 2 1.5 3 5 3s5-1 5-3V7c0-2-1.5-3-5-3s-5 1-5 3" /></svg> },
        { name: "Quản lý người dùng", href: "/admin/users", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg> },
        { name: "Giám sát tài nguyên", href: "/admin/resources", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
        { name: "Phiên hoạt động", href: "/admin/activity", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-3.13a4 4 0 10-4-4 4 4 0 004 4zm6 0a3 3 0 10-3-3" /></svg> },
        { name: "SOT & thiết bị", href: "/admin/sot", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg> },
        { name: "Thùng rác", href: "/trash", icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg> },
      ]
    }
  ];

  // A signed-in contributor gets their own Trash link (their soft-deleted
  // recordings); admins already have it inside the "Quản trị" section above.
  const userTrashItem: FlatNavItem = {
    name: "Thùng rác",
    href: "/trash",
    icon: <svg className={navIconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>,
  };
  const navigation: AnyNavItem[] = user?.is_admin
    ? [...baseNavigation, ...adminNavigation]
    : user
      ? [...baseNavigation, userTrashItem]
      : baseNavigation;

  const handleNewSession = useCallback(() => {
    setSidebarOpen(false);
    // Trước đây nút này gọi window.location.reload(). Reload thật sự có cấp
    // session_id mới, nhưng mọi chỗ hiển thị phiên đều đang tắt (SessionPanel
    // nằm sau cờ SHOW_ADVANCED), nên màn hình sau reload y hệt trước đó và
    // người dùng tưởng nút hỏng. Giờ chỉ nơi đang thu mới reset — kèm toast xác
    // nhận để luôn có phản hồi thấy được.
    requestNewSession();
    toast.success("Đã bắt đầu phiên thu mới");
  }, [toast]);

  const handleLogout = useCallback(async () => {
    setSidebarOpen(false);
    // Revoke the refresh token + clear the httpOnly cookies server-side, then
    // clear local state (also emits AUTH_EVENT so AuthProvider drops the user).
    await apiLogout();
    clearAuthToken();
    setHasToken(false);
    navigate("/");
  }, [navigate]);

  const NavItem = ({ item }: { item: FlatNavItem }) => (
    <NavLink
      to={item.href}
      end={item.end}
      className={({ isActive }) =>
        `group flex items-center px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200 ${isActive
          ? "bg-gradient-to-r from-ctu-navy to-ctu-blue text-white shadow-lg shadow-ctu-navy/25"
          : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/60"
        }`
      }
      onClick={() => setSidebarOpen(false)}
    >
      <span className="mr-3 flex items-center">{item.icon}</span>
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
        <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-400 shrink-0">
          {item.icon}
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
              `group flex items-center pl-8 pr-4 py-2.5 text-sm font-medium rounded-xl transition-all duration-200 ${isActive
                ? "bg-gradient-to-r from-ctu-navy to-ctu-blue text-white shadow-lg shadow-ctu-navy/25"
                : "text-slate-500 hover:text-slate-900 hover:bg-slate-100/60"
              }`
            }
            onClick={() => setSidebarOpen(false)}
          >
            <span className="mr-3 flex items-center">{child.icon}</span>
            {child.name}
          </NavLink>
        ))}
      </div>
    </div>
  );

  if (isAuthPage) {
    // Auth pages (login/register/forgot-password/reset-password) render
    // their own full-page shell (background, card, in-card links back to
    // other auth pages) — no app chrome (sidebar/header) needed here.
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen relative flex bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20">
      {user && <WarningBanner key={user.id} />}
      {hasToken && (
        <div
          className={`fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${sidebarOpen ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {hasToken && (
        <aside
          className={`fixed inset-y-0 left-0 z-50 w-[min(18rem,82vw)] max-w-72 transform border-r border-slate-200/60 bg-white/80 shadow-xl backdrop-blur-xl transition-all duration-300 ease-in-out overflow-y-auto ${sidebarOpen ? "translate-x-0" : "-translate-x-full"
            } lg:static lg:translate-x-0 lg:overflow-visible ${sidebarOpen ? "lg:w-72 lg:max-w-72" : "lg:w-0 lg:max-w-0"}`}
        >
          <div className="flex h-dvh lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto flex-col">
          <div className="flex items-center justify-between h-16 px-6 border-b border-slate-200/50">
            <div className="flex items-center min-w-0">
              <div className="w-10 h-10 bg-gradient-to-br from-ctu-navy to-ctu-blue rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-lg shrink-0">
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
                <div className={`w-2 h-2 rounded-full ${hasToken ? "bg-emerald-400 animate-pulse" : "bg-slate-300"}`} />
                <span>{hasToken ? "Đã đăng nhập" : "Chế độ khách"}</span>
              </div>

              <Button
                size="sm"
                onClick={handleNewSession}
                title="Tải lại trang và bắt đầu một phiên làm việc mới"
                className="w-full justify-center gap-1.5 px-3 py-2 text-xs sm:text-sm"
              >
                <RefreshIcon className="h-4 w-4" />
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
              Dự án nghiên cứu khoa học - Trường Công nghệ Thông tin và Truyền thông
            </div>
          </div>
        </div>
        </aside>
      )}

      <div className="flex-1 flex flex-col min-w-0 pt-14">
        <header className="fixed top-0 left-0 right-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-slate-200/60 bg-white/80 px-3 shadow-sm backdrop-blur-xl sm:px-4 lg:px-8">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            {hasToken && (
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
            )}
            <div className="flex min-w-0 items-center gap-2 cursor-pointer" onClick={() => navigate("/")}>
              <img src="logo.png" alt="Đại học Cần Thơ" className="h-7 w-7 sm:h-8 sm:w-8 shrink-0 object-contain" />
              <h1 className="truncate text-sm font-bold font-display sm:text-base lg:text-lg">
                <span className="text-ctu-blue">CTU</span>
                <span className="text-ctu-blue-light">.SignBridge</span>
              </h1>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 sm:gap-3 w-auto min-w-0 justify-end flex-nowrap overflow-x-auto">
            <div className="hidden sm:flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${hasToken ? "bg-emerald-400 animate-pulse" : "bg-slate-300"}`} />
              <span className="text-sm text-slate-600">{hasToken ? "Đã đăng nhập" : "Chế độ khách"}</span>
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

            <Button
              size="sm"
              onClick={handleNewSession}
              title="Tải lại trang và bắt đầu một phiên làm việc mới"
              className="whitespace-nowrap gap-1.5 px-3 py-2 text-xs sm:text-sm"
            >
              <RefreshIcon className="h-4 w-4" />
              Phiên mới
            </Button>
          </div>
        </header>

        <main className="flex-1 p-3 sm:p-4 lg:p-8 overflow-visible lg:overflow-auto min-w-0">
          <div className="max-w-7xl mx-auto w-full min-w-0 animate-fade-in">
            {children}
          </div>
        </main>
        <Footer />
      </div>
    </div>
  );
}
