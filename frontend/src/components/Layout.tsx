import { useState, useCallback, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearAuthToken } from "../api/axiosClient";
import { logout as apiLogout, isTenantAdmin } from "../api/auth";
import NotificationBell from "./NotificationBell";
import LanguageSwitcher from "./LanguageSwitcher";
import { useAuth, hasSessionHint } from "../contexts/AuthContext";
import { usePresence } from "../hooks/usePresence";
import { useIdleLogout } from "../hooks/useIdleLogout";
import WarningBanner from "./WarningBanner";
import type { ReactNode } from "react";
import Button from "./ui/Button";
import { BuildingIcon, ChipIcon, ClipboardCheckIcon, ClockIcon, GearIcon, HandIcon, HomeIcon, ShieldIcon, TagIcon, TrashIcon, UploadIcon } from "./ui/Icons";
import Footer from "./Footer";
import { prefetchProps } from "../routes/prefetch";
import { useI18n } from "../i18n";

const AUTH_EVENT = "voya:auth-change";

export type FlatNavItem = {
  name: string; href: string; icon: ReactNode; end?: boolean;
  /** Số việc đang chờ. `0` hoặc thiếu thì không vẽ gì — huy hiệu luôn sáng là
   *  huy hiệu người ta thôi nhìn. */
  badge?: number;
};
export type NavSection = {
  section: true;
  name: string;
  icon: ReactNode;
  children: FlatNavItem[];
};
export type AnyNavItem = FlatNavItem | NavSection;

export default function Layout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  // User comes from the single shared AuthProvider (no duplicate /auth/me here).
  const { user } = useAuth();
  // Presence heartbeat + opt-in precise geolocation for the admin monitor.
  usePresence(!!user);
  // Inactivity auto-logout (default 180 min of no real interaction → sign out;
  // stays in lockstep with the server's REFRESH_TOKEN_EXPIRE_MINUTES).
  useIdleLogout(!!user);
  // Synchronous session hint just for instant chrome painting (sidebar/header)
  // so a logged-in reload doesn't flash the guest layout while /auth/me is in
  // flight. No network — reads the token/cookie hint and updates on auth events.
  const [hasToken, setHasToken] = useState<boolean>(() => hasSessionHint());
  // Các trang dựng bằng `AuthShell` — chúng tự vẽ nền và con dấu, nên khung
  // ứng dụng (thanh bên, thanh đầu) phải rút lui. Quên thêm vào đây là lỗi im
  // lặng: trang vẫn chạy nhưng có hai lớp chrome chồng lên nhau.
  const AUTH_PAGE_PATHS = [
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/recover",
    "/invitation",
  ];
  // Console quản trị mang VỎ RIÊNG (`AdminShell`). Khung này phải rút lui hoàn
  // toàn ở đó, cùng lý do như các trang `AuthShell`: hai lớp chrome chồng nhau.
  // Dùng `startsWith` chứ không phải danh sách liệt kê — mọi trang con của
  // `/admin` đều nằm trong console, và một danh sách sẽ thiếu ngay khi thêm
  // trang mới, theo cách không ai nhận ra cho tới lúc nhìn màn hình.
  const isAuthPage =
    AUTH_PAGE_PATHS.includes(location.pathname) ||
    location.pathname === "/admin" ||
    location.pathname.startsWith("/admin/");

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
    { name: "Lần thu", href: "/sessions", icon: <ClockIcon className={navIconClass} /> },
    { name: "Nhận dạng realtime", href: "/realtime", icon: <HandIcon className={navIconClass} /> },
    { name: "Huấn luyện model", href: "/training", icon: <ChipIcon className={navIconClass} /> },
  ];

  /**
   * Thanh bên chỉ còn VIỆC CẦN LÀM, cộng đúng một lối vào Cài đặt.
   *
   * Bản trước có 11 mục cho người dùng thường và 21 cho quản trị viên, trong đó
   * sáu mục là thiết lập một lần trong đời (Tài khoản, Tổ chức, Xác minh liên
   * hệ, Gói dịch vụ, Tích hợp, Hỗ trợ) nằm ngang hàng với công việc hằng ngày.
   * Một danh sách trộn hai loại như vậy thì không liếc được — phải đọc từng
   * dòng, mỗi lần.
   *
   * Sáu mục đó giờ nằm trong `/settings`. Mười mục quản trị nằm trong console
   * riêng. Xem `pages/settings/SettingsLayout.tsx` và `components/AdminShell.tsx`.
   *
 * @i18n-key-table — `name` của mục điều hướng là KHOÁ từ điển, dịch ở
 * `NavItem`/`SectionNavItem`.
 */
  const settingsItem: FlatNavItem = {
    name: "Cài đặt",
    href: "/settings",
    icon: <GearIcon className={navIconClass} />,
  };

  // Người đóng góp thấy thùng rác của chính họ (bản ghi đã xoá mềm). Quản trị
  // viên có thùng rác toàn hệ thống trong console riêng — xem AdminShell.
  const userTrashItem: FlatNavItem = {
    name: "Thùng rác",
    href: "/trash",
    icon: <TrashIcon className={navIconClass} />,
  };

  // Console của quản trị TỔ CHỨC — khác hẳn console nền tảng ở `AdminShell`.
  //
  // Điều kiện hiện là `isTenantAdmin`, KHÔNG phải `is_admin`. Bản đầu dùng
  // `is_admin` và vì thế giấu console khỏi đúng những người nó được làm ra để
  // phục vụ: quản trị viên của một tổ chức không phải người vận hành nền tảng,
  // nên cờ đó luôn sai với họ.
  //
  // Đây vẫn chỉ là việc không mời người dùng bấm vào một trang chắc chắn 403;
  // quyền thật do `require_tenant_admin` ở máy chủ cưỡng chế.
  // Tên là "Tổ chức", không phải "Console tổ chức". Người dùng cần biết mục
  // này dẫn tới ĐÂU, không cần biết màn hình bên trong tên là gì — và "console"
  // là từ của người viết phần mềm, không phải của người dùng nó.
  //
  // Đích là `/org` (lớp CHỌN) chứ không phải thẳng vào một tổ chức: một tài
  // khoản có thể thuộc nhiều tổ chức, nên đi thẳng là đoán hộ họ.
  const consoleItem: FlatNavItem = {
    name: "Tổ chức",
    href: "/org",
    icon: <BuildingIcon className={navIconClass} />,
  };

  // Lối vào TỔ CHỨC cho người dùng thường.
  //
  // Trước đây thanh bên chỉ có `consoleItem`, và nó hiện khi `isTenantAdmin`.
  // Nghĩa là một tài khoản `editor` — tức phần lớn người dùng — không thấy chữ
  // "tổ chức" ở đâu hết: không biết mình đang thuộc tổ chức nào, không có
  // đường xin lập tổ chức riêng, không có chỗ xem ai cùng tổ chức với mình.
  // Trang `/settings/organization` đã xử lý sẵn CẢ BA trạng thái (chưa có tổ
  // chức -> thẻ gửi yêu cầu; là thành viên -> thông tin tổ chức; là quản trị
  // -> quản lý đầy đủ), nó chỉ chưa từng được ai liên kết tới.
  const organizationItem: FlatNavItem = {
    name: "Tổ chức",
    href: "/settings/organization",
    icon: <BuildingIcon className={navIconClass} />,
  };

  const coKiemDuyet = Boolean((user as { can_moderate?: boolean } | null)?.can_moderate);

  // Số phiên đang chờ, cho huy hiệu.
  //
  // CHỈ hỏi khi người này duyệt được: `/moderation/queue` trả 403 với mọi người
  // khác, nên hỏi vô điều kiện là bắt mọi phiên đăng nhập trả giá một lượt gọi
  // hỏng để vẽ một huy hiệu không bao giờ hiện.
  //
  // Hỏng thì im: một con số trang trí không được phép làm hỏng thanh điều hướng.
  const [choDuyet, setChoDuyet] = useState(0);
  useEffect(() => {
    if (!coKiemDuyet) {
      setChoDuyet(0);
      return;
    }
    let huy = false;
    void import("../api/moderation")
      .then((m) => m.fetchQueue(1))
      .then((q) => {
        if (!huy) setChoDuyet(q.count);
      })
      .catch(() => {});
    return () => {
      huy = true;
    };
  }, [coKiemDuyet]);

  // Kiểm duyệt: chỉ hiện với người BẤM ĐƯỢC.
  //
  // Điều kiện là `can_moderate` từ `/auth/me`, KHÔNG phải `is_admin`: người
  // kiểm duyệt là chuyên gia được mời và không giữ quyền quản trị nền tảng, nên
  // đọc `is_admin` sẽ giấu mục này khỏi đúng những người nó phục vụ.
  //
  // Đây là việc không mời người ta bấm vào một trang chắc chắn 403, không phải
  // một hàng rào: `require_moderator` ở máy chủ mới cưỡng chế.
  const moderationItem: FlatNavItem = {
    name: "Kiểm duyệt",
    href: "/moderation",
    icon: <ClipboardCheckIcon className={navIconClass} />,
    badge: choDuyet,
  };



  const navigation: AnyNavItem[] = user
    ? [
        ...baseNavigation,
        ...(coKiemDuyet ? [moderationItem] : []),
        ...(isTenantAdmin(user) ? [consoleItem] : [organizationItem]),
        userTrashItem,
        settingsItem,
      ]
    : baseNavigation;

  const handleLogout = useCallback(async () => {
    setSidebarOpen(false);
    // Revoke the refresh token + clear the httpOnly cookies server-side, then
    // clear local state (also emits AUTH_EVENT so AuthProvider drops the user).
    await apiLogout();
    clearAuthToken();
    setHasToken(false);
    // `replace`, không phải push. Với push, trang vừa rời khỏi vẫn nằm trong
    // lịch sử: bấm NÚT QUAY LẠI ngay sau khi đăng xuất sẽ dựng lại đúng màn
    // hình đó từ bộ nhớ — vẫn còn tên người dùng, vẫn còn dữ liệu vừa xem —
    // rồi mọi lượt gọi API bên dưới trả 401 và trang vỡ dần từng mảnh. Người
    // dùng thấy mình "vẫn đăng nhập" trong vài giây, thứ tệ hơn hẳn một màn
    // hình đăng xuất sạch sẽ.
    navigate("/", { replace: true });
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
      {...prefetchProps(item.href)}
    >
      <span className="mr-3 flex items-center">{item.icon}</span>
      {t(item.name)}
      {item.badge ? (
        <span className="ml-2 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-ctu-blue px-1.5 py-0.5 text-xs font-semibold text-white">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      ) : null}
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
          {t(item.name)}
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
            {...prefetchProps(child.href)}
          >
            <span className="mr-3 flex items-center">{child.icon}</span>
            {t(child.name)}
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

            {/* Không `lg:hidden`. Trên màn hình rộng, thứ duy nhất đóng được
                thanh bên là cái nút ba gạch ở header — và người dùng không đọc
                nó là "đóng", họ đọc nó là "mở". Một ngăn kéo mở ra mà không có
                dấu X nào trong tầm mắt thì đọc như một ngăn kéo không đóng
                được, bất kể có phím tắt nào khác hay không. */}
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              aria-label={t("Đóng thanh bên")}
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
                <div className={`w-2 h-2 rounded-full ${hasToken ? "bg-sky-400 animate-pulse" : "bg-slate-300"}`} />
                <span>{hasToken ? t("Đã đăng nhập") : t("Chế độ khách")}</span>
              </div>

              {hasToken ? (
                <Button
                  size="sm"
                  variant="danger"
                  onClick={handleLogout}
                  className="w-full justify-center px-3 py-2 text-xs sm:text-sm"
                >
                  {t("Đăng xuất")}
                </Button>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Button size="sm" onClick={() => navigate("/login")} className="w-full justify-center px-3 py-2 text-xs sm:text-sm">
                    {t("Đăng nhập")}
                  </Button>
                  <Button size="sm" onClick={() => navigate("/register")} className="w-full justify-center px-3 py-2 text-xs sm:text-sm">
                    {t("Đăng ký")}
                  </Button>
                </div>
              )}
            </div>

            <div className="hidden lg:block pt-4 text-xs text-slate-500 text-center">
              {t("Dự án nghiên cứu khoa học - Trường Công nghệ Thông tin và Truyền thông")}
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
                aria-label={t("Mở hoặc đóng thanh điều hướng")}
                aria-expanded={sidebarOpen}
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <div className="flex min-w-0 items-center gap-2 cursor-pointer" onClick={() => navigate("/")}>
              <img src="logo.png" alt={t("Đại học Cần Thơ")} className="h-7 w-7 sm:h-8 sm:w-8 shrink-0 object-contain" />
              <h1 className="truncate text-sm font-bold font-display sm:text-base lg:text-lg">
                <span className="text-ctu-blue">CTU</span>
                <span className="text-ctu-blue-light">.SignBridge</span>
              </h1>
            </div>
          </div>

          {/* KHÔNG đặt `overflow-x-auto` ở đây. Một tổ tiên có overflow khác
              `visible` sẽ cắt mọi con định vị tuyệt đối tràn ra ngoài nó —
              và bảng thả xuống của cái chuông thông báo là đúng một con như
              vậy. Triệu chứng rất dễ đọc nhầm: huy hiệu "1" vẫn hiện, bấm vào
              vẫn mở, nhưng KHÔNG THẤY GÌ, nên trông như lỗi tải dữ liệu chứ
              không phải lỗi khung. Chỗ chật trên máy hẹp đã được lo bằng
              `hidden md:flex` và các mục tự ẩn theo breakpoint. */}
          <div className="hidden md:flex items-center gap-2 sm:gap-3 w-auto min-w-0 justify-end flex-nowrap">
            <div className="hidden sm:flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${hasToken ? "bg-sky-400 animate-pulse" : "bg-slate-300"}`} />
              <span className="text-sm text-slate-600">{hasToken ? t("Đã đăng nhập") : t("Chế độ khách")}</span>
            </div>

            {/* Cả khách lẫn người đã đăng nhập: người đọc tiếng Anh gặp trang
                đăng nhập trước tiên, nên giấu nút này sau cổng đăng nhập là
                giấu nó khỏi đúng người cần nó. */}
            <LanguageSwitcher className="hidden lg:inline-flex" />

            {hasToken ? (
              <>
                {/* Chỉ dựng khi ĐÃ đăng nhập: cái chuông tự gọi API theo chu kỳ,
                    và ở chế độ khách mỗi lượt gọi là một lượt 401 vô ích. */}
                <NotificationBell />
                {user?.is_admin ? (
                  /* Lối vào console quản trị. MỘT nút, không phải mười mục
                     nhồi vào cuối thanh bên — xem AdminShell.tsx về vì sao hai
                     vai phải có ranh giới nhìn thấy được. */
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigate("/admin")}
                    className="whitespace-nowrap gap-1.5 px-3 py-2 text-xs sm:text-sm"
                  >
                    <ShieldIcon className="h-4 w-4" />
                    {t("Quản trị")}
                  </Button>
                ) : null}
                <Button size="sm" onClick={handleLogout} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                  {t("Đăng xuất")}
                </Button>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Button size="sm" onClick={() => navigate("/login")} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                  {t("Đăng nhập")}
                </Button>
                <Button size="sm" onClick={() => navigate("/register")} className="whitespace-nowrap px-3 py-2 text-xs sm:text-sm">
                  {t("Đăng ký")}
                </Button>
              </div>
            )}
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
