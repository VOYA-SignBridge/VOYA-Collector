import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";
import {
  BuildingIcon, ChartBarIcon, ClipboardCheckIcon, FolderIcon, LinkIcon,
  ScrollTextIcon, SplitIcon, UsersIcon,
} from "../../components/ui/Icons";
import type { ReactNode } from "react";

/**
 * Console của QUẢN TRỊ TỔ CHỨC — `/console`.
 *
 * Vì sao nó tách khỏi `/admin` và khỏi `/settings`
 * -------------------------------------------------
 * Hệ thống có hai thẩm quyền **không lồng nhau**, và trước trang này chúng dùng
 * chung hai chỗ ở:
 *
 * * `/admin` là console của **quản trị nền tảng** — phạm vi mọi tổ chức. Một
 *   quản trị viên tổ chức không vào được, và không nên vào.
 * * `/settings` là "tài khoản của tôi" — nơi một cá nhân sửa hồ sơ, mật khẩu,
 *   đồng thuận. Việc điều hành một tổ chức bị nhét vào đó dưới đúng một mục
 *   ("Tổ chức"), ngang hàng với "Ngôn ngữ & hiển thị".
 *
 * Hệ quả cụ thể chứ không chỉ là lộn xộn: người điều hành một tổ chức — duyệt
 * thành viên, chia hạn mức cho từng nhóm, lấy dữ liệu ra — phải đi qua một menu
 * mang tên "Cài đặt" và tự đoán mục nào là việc của mình. Console này gom đúng
 * những việc đó vào một chỗ, ở phạm vi **một tổ chức**.
 *
 * Ranh giới A7 ≠ A8 phải nhìn thấy được từ thanh bên
 * ----------------------------------------------------
 * Không mục nào ở đây chạm sang tổ chức khác. Đường đưa người vào tổ chức ở
 * console này là **lời mời**, không phải gán trực tiếp theo mã tài khoản — mã
 * tài khoản không phải bí mật, và cho gán trực tiếp là mở đường kéo bất kỳ ai
 * trên hệ thống vào tổ chức mình mà họ không hay biết.
 *
 * Vỏ console KHÔNG phải hàng rào quyền
 * -------------------------------------
 * Việc một trang nằm dưới `/console` không tự nó chặn ai. Quyền vẫn do máy chủ
 * cưỡng chế (`require_tenant_admin`). Thanh bên chỉ ẩn thứ người dùng chắc chắn
 * không bấm được, để họ không đi vào một ngõ cụt có sẵn nhãn.
 *
 * @i18n-key-table — `key` của từng mục là KHOÁ từ điển, dịch bằng `t(item.key)`.
 */

type Item = { key: string; href: string; icon: ReactNode; end?: boolean };

const ICON = "h-4 w-4 shrink-0";

const ITEMS: Item[] = [
  { key: "Tổng quan", href: "/console", icon: <ChartBarIcon className={ICON} />, end: true },
  { key: "Thành viên & lời mời", href: "/console/members", icon: <UsersIcon className={ICON} /> },
  { key: "Workspace & Project", href: "/console/workspaces", icon: <FolderIcon className={ICON} /> },
  { key: "Cấp phát tài nguyên", href: "/console/allocations", icon: <SplitIcon className={ICON} /> },
  { key: "Gói & hạn mức", href: "/console/billing", icon: <ClipboardCheckIcon className={ICON} /> },
  { key: "Tích hợp", href: "/console/integrations", icon: <LinkIcon className={ICON} /> },
  { key: "Chính sách áp dụng", href: "/console/policies", icon: <ScrollTextIcon className={ICON} /> },
];

export default function ConsoleLayout() {
  const { t } = useI18n();
  const { user } = useAuth();

  return (
    <div className="mx-auto w-full max-w-7xl">
      <div className="mb-6 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          <BuildingIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {t("Console tổ chức")}
          </h1>
          <p className="text-sm text-slate-500">
            {t("Điều hành tổ chức {ten} — thành viên, phạm vi làm việc và hạn mức.", {
              ten: user?.tenant_id ?? "—",
            })}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <nav aria-label={t("Mục console tổ chức")} className="lg:sticky lg:top-6 lg:self-start">
          <ul className="space-y-1">
            {ITEMS.map((item) => (
              <li key={item.href}>
                <NavLink
                  to={item.href}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? "bg-ctu-blue/10 font-medium text-ctu-blue"
                        : "text-slate-600 hover:bg-slate-100"
                    }`
                  }
                >
                  {item.icon}
                  {t(item.key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
