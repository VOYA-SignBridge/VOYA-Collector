/**
 * `/org/:tenantId/settings` — nơi ở mới của những gì từng là cả console.
 *
 * Vì sao chúng lùi xuống một tầng
 * --------------------------------
 * Bảy mục cũ đều là **cấu hình**: chia nhóm, đặt hạn mức, chọn gói, nối dịch vụ
 * ngoài, ghi quy định. Không mục nào là việc làm hằng ngày. Đặt chúng làm màn
 * hình chính của một tổ chức khiến tổ chức trông như một bảng điều khiển hành
 * chính, trong khi lý do nó tồn tại là để thu và gán nhãn dữ liệu.
 *
 * Cấu hình là thứ người ta chạm vài lần rồi thôi, nên nó thuộc về Cài đặt.
 *
 * Đổi chữ, không đổi mô hình
 * ---------------------------
 * "Workspace & Project" → **Nhóm & lớp**. "Cấp phát tài nguyên" → **Hạn mức**.
 * "Chính sách áp dụng" → **Quy định**. "Tích hợp" → **Kết nối ngoài**.
 *
 * Bảng dữ liệu bên dưới vẫn là `workspaces` và `projects`; API, cột và tài liệu
 * kỹ thuật giữ nguyên tên tiếng Anh. Chỉ nhãn trên màn hình đổi — người dùng
 * của một trường học không cần học từ vựng SaaS để chia lớp cho sinh viên.
 *
 * @i18n-key-table — `key` của từng mục là KHOÁ từ điển, dịch bằng `t(item.key)`.
 */

import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useI18n } from "../../i18n";
import {
  ClipboardCheckIcon, FolderIcon, LinkIcon, ScrollTextIcon, SplitIcon,
} from "../../components/ui/Icons";

type Item = { key: string; to: string; icon: ReactNode; end?: boolean };

const ICON = "h-4 w-4 shrink-0";

const ITEMS: Item[] = [
  { key: "Nhóm & lớp", to: "", icon: <FolderIcon className={ICON} />, end: true },
  { key: "Hạn mức", to: "allocations", icon: <SplitIcon className={ICON} /> },
  { key: "Gói dịch vụ", to: "billing", icon: <ClipboardCheckIcon className={ICON} /> },
  { key: "Kết nối ngoài", to: "integrations", icon: <LinkIcon className={ICON} /> },
  { key: "Quy định", to: "policies", icon: <ScrollTextIcon className={ICON} /> },
];

export default function OrgSettingsLayout() {
  const { t } = useI18n();

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-900">{t("Cài đặt tổ chức")}</h2>
      <p className="mt-0.5 text-sm text-slate-500">
        {t("Những thứ đặt một lần rồi ít khi đụng lại.")}
      </p>

      {/* Thanh ngang, không phải thanh bên thứ hai: hai thanh dọc lồng nhau đẩy
          nội dung vào một cột hẹp và làm người đọc mất dấu mình đang ở tầng
          nào. */}
      <nav
        aria-label={t("Mục cài đặt tổ chức")}
        className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-200 pb-px"
      >
        {ITEMS.map((item) => (
          <NavLink
            key={item.to || "_index"}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-2 rounded-t-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "border-b-2 border-ctu-blue font-medium text-ctu-blue"
                  : "border-b-2 border-transparent text-slate-600 hover:bg-slate-50"
              }`
            }
          >
            {item.icon}
            {t(item.key)}
          </NavLink>
        ))}
      </nav>

      <div className="mt-5">
        <Outlet />
      </div>
    </div>
  );
}
