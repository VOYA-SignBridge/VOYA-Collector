import { Link } from "react-router-dom";
import {
  BuildingIcon, ChartBarIcon, DatabaseIcon, GearIcon, HardDriveIcon, InboxIcon,
  ScrollTextIcon, ServerIcon, TrashIcon, UsersIcon,
} from "../../components/ui/Icons";
import PageHeader from "../../components/ui/PageHeader";
import { useI18n } from "../../i18n";
import type { ReactNode } from "react";

/**
 * Trang chủ console quản trị — `/admin`.
 *
 * Vì sao console cần một trang chủ: khi mười mục quản trị còn nằm trong thanh
 * bên chung, `/admin` không tồn tại như một nơi — người ta đi thẳng tới
 * `/admin/users` từ một liên kết. Tách thành console thì phải có chỗ để "vào",
 * và một cửa vào dẫn thẳng tới trang đầu tiên trong danh sách là một cửa vào
 * nói dối về thứ tự ưu tiên.
 *
 * Trang này cố ý **không có số liệu**. Một bảng điều khiển chỉ số cần nguồn dữ
 * liệu thật, chu kỳ làm mới và một câu trả lời cho "số này tính từ lúc nào" —
 * ba thứ chưa có. Vẽ ô số trống hoặc số giả là dựng một thứ trông như đo đạc mà
 * không đo gì; `/admin/resources` mới là nơi có số thật.
 *
 * @i18n-key-table — chữ trong `CARDS` là KHOÁ từ điển, dịch ở chỗ dựng bằng
 * `t(card.key)` / `t(card.desc)`. Bảng nằm ngoài component nên không gọi hook
 * được; dịch sẵn tại đây sẽ đóng băng ngôn ngữ ở lần nạp mô-đun.
 */

type Card = { key: string; desc: string; href: string; icon: ReactNode };

const ICON = "h-5 w-5";

const CARDS: Card[] = [
  { key: "Hỗ trợ", desc: "Phiếu người dùng gửi lên, và trả lời.", href: "/admin/support", icon: <InboxIcon className={ICON} /> },
  { key: "Quản lý người dùng", desc: "Tài khoản, vai trò, thu hồi phiên.", href: "/admin/users", icon: <UsersIcon className={ICON} /> },
  { key: "Quản lý dữ liệu", desc: "Nhãn, mẫu, đồng bộ và xuất bản.", href: "/admin/data", icon: <DatabaseIcon className={ICON} /> },
  { key: "Giám sát tài nguyên", desc: "CPU, RAM, đĩa, GPU của máy chủ.", href: "/admin/resources", icon: <ServerIcon className={ICON} /> },
  { key: "Phiên hoạt động", desc: "Ai đang online, và nhật ký kiểm toán.", href: "/admin/activity", icon: <HardDriveIcon className={ICON} /> },
  { key: "Tổ chức", desc: "Tạo tổ chức, mời thành viên, hạn mức.", href: "/admin/tenants", icon: <BuildingIcon className={ICON} /> },
  { key: "Gói & thanh toán", desc: "Gói dịch vụ, hạn mức, tình trạng đăng ký.", href: "/admin/billing", icon: <ChartBarIcon className={ICON} /> },
  { key: "Văn bản pháp lý", desc: "Soạn, công bố và theo dõi đồng thuận.", href: "/admin/legal", icon: <ScrollTextIcon className={ICON} /> },
  { key: "Từ vựng & phương ngữ", desc: "Duyệt đề xuất từ người đóng góp.", href: "/admin/vocabulary", icon: <ScrollTextIcon className={ICON} /> },
  { key: "SOT & thiết bị", desc: "Máy được phép ghi vào nguồn sự thật.", href: "/admin/sot", icon: <GearIcon className={ICON} /> },
  { key: "Thùng rác", desc: "Bản ghi đã xoá mềm của toàn hệ thống.", href: "/admin/trash", icon: <TrashIcon className={ICON} /> },
];

export default function AdminHomePage() {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Console quản trị")}
        subtitle={t("Các thao tác ảnh hưởng tới dữ liệu và tài khoản của người khác.")}
      />

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => (
          <li key={card.href}>
            <Link
              to={card.href}
              className="flex h-full flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-ctu-blue hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2"
            >
              <span className="flex items-center gap-2.5 font-semibold text-slate-900">
                <span className="text-ctu-blue">{card.icon}</span>
                {t(card.key)}
              </span>
              <span className="text-sm leading-relaxed text-slate-600">{t(card.desc)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
