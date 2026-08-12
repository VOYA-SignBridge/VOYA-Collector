import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";
import {
  BuildingIcon, ChartBarIcon, GlobeIcon, InboxIcon, LinkIcon, ShieldCheckIcon,
  ShieldIcon, UserIcon,
} from "../../components/ui/Icons";
import type { ReactNode } from "react";

/**
 * Trung tâm Cài đặt — một cửa cho mọi thứ thuộc về "tài khoản của tôi".
 *
 * Vấn đề của bản trước
 * ---------------------
 * Sáu mục — Tài khoản, Tổ chức, Xác minh liên hệ, Gói dịch vụ, Tích hợp, Hỗ trợ
 * — nằm rải trong thanh bên chính, ngang hàng với Đóng góp dữ liệu và Huấn
 * luyện model. Thanh bên vì thế dài 11 mục và không còn nói lên điều gì: công
 * việc hằng ngày lẫn với thiết lập một lần trong đời.
 *
 * Cách gom ở đây theo đúng khuôn mà người dùng đã quen từ Facebook/Google: một
 * mục **Cài đặt** ở thanh bên chính, mở ra một trang có thanh điều hướng con
 * bên trái. Lợi ích không phải là đẹp hơn — mà là **thanh bên chính giờ chỉ còn
 * việc cần làm**, nên nó đọc được trong một cái liếc.
 *
 * Vì sao mỗi mục vẫn là một ROUTE riêng chứ không phải một tab trong state
 * -------------------------------------------------------------------------
 * `/settings/security` phải chia sẻ được, đánh dấu được, và quay-lại được. Một
 * tab lưu trong `useState` mất hết cả ba, và nó còn làm hỏng một thứ cụ thể:
 * thông báo bảo mật trỏ tới trang này bằng đường dẫn.
 *
 * @i18n-key-table — `key` của từng mục cài đặt là KHOÁ từ điển, dịch bằng
 * `t(item.key)` lúc dựng.
 */

type Item = { key: string; href: string; icon: ReactNode; adminOnly?: boolean };

const ICON = "h-4 w-4 shrink-0";

const ITEMS: Item[] = [
  { key: "Tài khoản", href: "/settings/account", icon: <UserIcon className={ICON} /> },
  { key: "Bảo mật", href: "/settings/security", icon: <ShieldIcon className={ICON} /> },
  { key: "Xác minh liên hệ", href: "/settings/contact", icon: <ShieldCheckIcon className={ICON} /> },
  { key: "Tổ chức", href: "/settings/organization", icon: <BuildingIcon className={ICON} /> },
  { key: "Gói dịch vụ", href: "/settings/billing", icon: <ChartBarIcon className={ICON} /> },
  // Tích hợp đòi vai trò biên tập ở máy chủ. Hiện nó cho người không có quyền
  // là mời họ bấm vào một trang chắc chắn 403 — một ngõ cụt có sẵn nhãn.
  { key: "Tích hợp", href: "/settings/integrations", icon: <LinkIcon className={ICON} />, adminOnly: true },
  { key: "Hỗ trợ", href: "/settings/support", icon: <InboxIcon className={ICON} /> },
  { key: "Ngôn ngữ & hiển thị", href: "/settings/language", icon: <GlobeIcon className={ICON} /> },
];

export default function SettingsLayout() {
  const { user } = useAuth();
  const { t } = useI18n();
  const items = ITEMS.filter((i) => !i.adminOnly || user?.is_admin);

  return (
    <div className="mx-auto w-full max-w-6xl">
      <h1 className="mb-6 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
        {t("Cài đặt")}
      </h1>

      <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
        {/* Trên màn hình hẹp thanh này cuộn NGANG chứ không xếp chồng thành tám
            dòng đẩy nội dung xuống dưới màn hình đầu tiên. */}
        <nav
          aria-label={t("Mục cài đặt")}
          className="-mx-1 flex shrink-0 gap-1 overflow-x-auto px-1 pb-2 lg:mx-0 lg:w-60 lg:flex-col lg:overflow-visible lg:pb-0"
        >
          {items.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2 ${
                  isActive
                    ? "bg-ctu-blue/10 text-ctu-blue"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              {item.icon}
              {t(item.key)}
            </NavLink>
          ))}
        </nav>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
