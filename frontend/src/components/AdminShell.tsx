import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  ArrowRightIcon, BuildingIcon, ChartBarIcon, DatabaseIcon, GearIcon, HardDriveIcon,
  InboxIcon, ScrollTextIcon, ServerIcon, TrashIcon, UsersIcon,
} from "./ui/Icons";
import { useI18n } from "../i18n";
import { useAdminAttention } from "../hooks/useAdminAttention";

/**
 * Console quản trị — một VỎ RIÊNG, không phải một nhóm trong thanh bên.
 *
 * Vì sao tách hẳn
 * ----------------
 * Bản trước nhồi mười mục quản trị vào cuối thanh bên của người dùng, dưới một
 * cái nhãn "QUẢN TRỊ". Kết quả là một người có quyền quản trị lúc nào cũng nhìn
 * thấy cả hai vai cùng lúc, và không có ranh giới nào giữa "tôi đang đóng góp
 * dữ liệu" với "tôi đang xoá dữ liệu của người khác". Ranh giới đó không phải
 * chuyện thẩm mỹ: hai vai có mức hậu quả khác nhau một bậc.
 *
 * Nên console này **trông khác hẳn**: nền tối thay vì sáng, tên khác, và một
 * nút thoát duy nhất. Nhìn một cái là biết mình đang ở đâu, kể cả khi liếc qua.
 *
 * Điều KHÔNG được nhầm: đây là ranh giới của **giao diện**, không phải của
 * quyền. Quyền vẫn do máy chủ quyết ở từng endpoint (`require_admin`). Một
 * người không phải quản trị viên gõ thẳng `/admin/...` vào thanh địa chỉ sẽ
 * gặp `ProtectedRoute requireAdmin` rồi tới 403 của máy chủ — vỏ này không
 * phải thứ giữ họ lại.
 *
 * @i18n-key-table — chữ trong `ADMIN_NAV` là KHOÁ từ điển, dịch bằng
 * `t(item.key)` lúc dựng.
 */

const ICON = "h-5 w-5 shrink-0";

type AdminNavItem = { key: string; href: string; icon: ReactNode; end?: boolean };

const ADMIN_NAV: AdminNavItem[] = [
  { key: "Tổng quan", href: "/admin", icon: <ChartBarIcon className={ICON} />, end: true },
  { key: "Quản lý dữ liệu", href: "/admin/data", icon: <DatabaseIcon className={ICON} /> },
  { key: "Quản lý người dùng", href: "/admin/users", icon: <UsersIcon className={ICON} /> },
  { key: "Hỗ trợ", href: "/admin/support", icon: <InboxIcon className={ICON} /> },
  { key: "Giám sát tài nguyên", href: "/admin/resources", icon: <ServerIcon className={ICON} /> },
  { key: "Phiên hoạt động", href: "/admin/activity", icon: <HardDriveIcon className={ICON} /> },
  { key: "SOT & thiết bị", href: "/admin/sot", icon: <GearIcon className={ICON} /> },
  { key: "Từ vựng & phương ngữ", href: "/admin/vocabulary", icon: <ScrollTextIcon className={ICON} /> },
  { key: "Văn bản pháp lý", href: "/admin/legal", icon: <ScrollTextIcon className={ICON} /> },
  { key: "Tổ chức", href: "/admin/tenants", icon: <BuildingIcon className={ICON} /> },
  { key: "Gói & thanh toán", href: "/admin/billing", icon: <ChartBarIcon className={ICON} /> },
  { key: "Thùng rác", href: "/admin/trash", icon: <TrashIcon className={ICON} /> },
];

export default function AdminShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { t } = useI18n();
  // Đặt ở VỎ chứ không ở từng trang: huy hiệu phải đúng cả khi quản trị viên
  // đang đứng ở một mục khác — đó chính là lúc nó có ích.
  const { counts } = useAdminAttention();

  return (
    <div className="min-h-dvh bg-slate-950 text-slate-100">
      {/* Thanh đầu. Cố ý KHÔNG dùng lại header của ứng dụng: dùng chung thì
          console lại trông giống chỗ cũ, và cả bản tách này thành vô nghĩa. */}
      <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/95 px-3 backdrop-blur sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={t("Mở hoặc đóng thanh điều hướng")}
            className="rounded-lg p-2 text-slate-300 hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 lg:hidden"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="rounded-md bg-amber-400/15 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-amber-300">
            {t("Console quản trị")}
          </span>
          <span className="hidden truncate text-sm text-slate-400 sm:block">
            CTU<span className="text-sky-400">.SignBridge</span>
          </span>
        </div>

        {/* Lối ra. MỘT nút, luôn ở cùng chỗ — vào được một chế độ mà không thấy
            đường ra là cách nhanh nhất khiến người ta ngại bấm vào. */}
        <button
          type="button"
          onClick={() => navigate("/")}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-sky-500 hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 sm:text-sm"
        >
          <ArrowRightIcon className="h-4 w-4 rotate-180" aria-hidden="true" />
          {t("Thoát về ứng dụng")}
        </button>
      </header>

      <div className="flex pt-14">
        <aside
          className={`fixed inset-y-0 left-0 top-14 z-30 w-64 transform border-r border-slate-800 bg-slate-900 transition-transform lg:static lg:translate-x-0 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <nav className="flex h-full flex-col gap-1 overflow-y-auto p-3">
            {ADMIN_NAV.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                end={item.end}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 ${
                    isActive
                      ? "bg-sky-500/15 text-sky-300"
                      : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                  }`
                }
              >
                {item.icon}
                <span className="truncate">{t(item.key)}</span>
                {/* Huy hiệu chỉ hiện khi CÓ việc. Một số 0 hiển thị ra là một
                    huy hiệu luôn sáng, và một huy hiệu luôn sáng thì không còn
                    nói được điều gì. */}
                {counts[item.href] > 0 ? (
                  <span
                    className="ml-auto inline-flex min-w-[1.25rem] shrink-0 items-center justify-center rounded-full bg-amber-400 px-1.5 py-0.5 text-[11px] font-bold tabular-nums text-slate-900"
                    /* Con số một mình không nói nó là số gì — người dùng trình
                       đọc màn hình nghe thấy "Hỗ trợ 3" mà không rõ 3 cái gì. */
                    aria-label={t("{n} việc đang chờ", { n: counts[item.href] })}
                  >
                    {counts[item.href] > 99 ? "99+" : counts[item.href]}
                  </span>
                ) : null}
              </NavLink>
            ))}
          </nav>
        </aside>

        {open && (
          <button
            type="button"
            aria-label={t("Đóng thanh điều hướng")}
            onClick={() => setOpen(false)}
            className="fixed inset-0 top-14 z-20 bg-black/60 lg:hidden"
          />
        )}

        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {/* Nội dung các trang quản trị được viết cho nền SÁNG. Bọc trong một
              tấm sáng thay vì đi sửa màu từng trang: đổi 10 trang để hợp nền
              tối là 10 dịp làm hỏng độ tương phản ở chỗ không ai kiểm. */}
          <div className="mx-auto w-full max-w-7xl rounded-2xl bg-slate-50 p-4 text-slate-900 shadow-2xl sm:p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
