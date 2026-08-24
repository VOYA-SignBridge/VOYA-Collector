/**
 * `/org/:tenantId` — vỏ của MỘT tổ chức.
 *
 * Thay cho `ConsoleLayout`. Ba thứ đổi, và cả ba đều là phản hồi trực tiếp về
 * bản cũ:
 *
 * 1. **Tiêu đề là TÊN tổ chức**, không phải chữ "Console tổ chức". Người dùng
 *    cần biết mình đang đứng ở đâu, không cần biết màn hình này tên là gì.
 * 2. **Việc làm hằng ngày lên trước, quản trị xuống dưới.** Bản cũ chỉ có bảy
 *    mục quản trị, nên một tổ chức là chỗ để cấu hình chứ không phải chỗ để
 *    làm việc. Thu dữ liệu và tải video là lý do tổ chức tồn tại.
 * 3. **Bỏ thuật ngữ nặng.** "Workspace & Project" → "Nhóm & lớp"; "Cấp phát
 *    tài nguyên" → "Hạn mức"; "Chính sách áp dụng" → "Quy định". Mô hình dữ
 *    liệu bên dưới không đổi — chỉ chữ trên màn hình đổi.
 *
 * Phạm vi KHÔNG do đoạn đường dẫn quyết định
 * -------------------------------------------
 * `:tenantId` ở đây là bản sao của `users.active_tenant_id` để liên kết chia sẻ
 * được. Máy chủ đọc cột, không đọc đường dẫn — nên gõ tay mã của tổ chức khác
 * vào thanh địa chỉ KHÔNG cho xem dữ liệu của họ; nó chỉ làm nhãn trên màn hình
 * lệch với dữ liệu bên dưới. Vỏ này phát hiện chuyện đó và tự đưa về `/org`.
 *
 * Vỏ KHÔNG phải hàng rào quyền. Quyền vẫn do máy chủ cưỡng chế; thanh bên chỉ
 * ẩn thứ người dùng chắc chắn không bấm được.
 *
 * @i18n-key-table — `key` của từng mục là KHOÁ từ điển, dịch bằng `t(item.key)`.
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { listMyTenants, type TenantMembershipRow } from "../../api/tenants";
import { useI18n } from "../../i18n";
import {
  ArrowLeftIcon, BuildingIcon, ChartBarIcon, ChipIcon, ClipboardCheckIcon,
  ClockIcon, FolderIcon, HandIcon, TagIcon, UploadIcon, UsersIcon,
} from "../../components/ui/Icons";

type Item = { key: string; to: string; icon: ReactNode; end?: boolean };

const ICON = "h-4 w-4 shrink-0";

/** Nhóm mục. Tiêu đề nhóm là `null` cho nhóm đầu — nó không cần nhãn. */
const GROUPS: { title: string | null; items: Item[] }[] = [
  {
    title: null,
    items: [
      { key: "Tổng quan", to: "", icon: <ChartBarIcon className={ICON} />, end: true },
    ],
  },
  {
    title: "LÀM VIỆC",
    items: [
      { key: "Đóng góp dữ liệu", to: "upload", icon: <UploadIcon className={ICON} /> },
      { key: "Thư viện nhãn", to: "labels", icon: <TagIcon className={ICON} /> },
      { key: "Lần thu", to: "sessions", icon: <ClockIcon className={ICON} /> },
      { key: "Nhận dạng realtime", to: "realtime", icon: <HandIcon className={ICON} /> },
      { key: "Huấn luyện model", to: "training", icon: <ChipIcon className={ICON} /> },
    ],
  },
  {
    title: "QUẢN LÝ",
    items: [
      { key: "Thành viên", to: "members", icon: <UsersIcon className={ICON} /> },
      { key: "Cài đặt tổ chức", to: "settings", icon: <ClipboardCheckIcon className={ICON} /> },
    ],
  },
];

export default function OrgLayout() {
  const { t } = useI18n();
  const { tenantId = "" } = useParams<{ tenantId: string }>();

  const [row, setRow] = useState<TenantMembershipRow | null>(null);
  const [checked, setChecked] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await listMyTenants();
      setRow(rows.find((x) => x.tenant_id === tenantId) ?? null);
    } catch {
      // Không tải được danh sách thì KHÔNG kết luận là không thuộc tổ chức:
      // một lượt mạng trượt sẽ đá người dùng ra khỏi màn hình họ đang làm việc.
      // Giữ nguyên vỏ, để từng trang con tự báo lỗi của nó.
      setRow(null);
    } finally {
      setChecked(true);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  const ten = row?.display_name || tenantId || "—";

  return (
    <div className="mx-auto w-full max-w-7xl">
      <Link
        to="/org"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-ctu-blue"
      >
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        {t("Đổi tổ chức")}
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          <BuildingIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold tracking-tight text-slate-900">{ten}</h1>
          <p className="text-sm text-slate-500">
            {t("Bạn đang làm việc trong tổ chức này.")}
          </p>
        </div>
      </div>

      {checked && !row && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("Không xác nhận được bạn thuộc tổ chức này. Dữ liệu hiển thị có thể không phải của tổ chức trên tiêu đề.")}{" "}
          <Link to="/org" className="font-medium underline">
            {t("Chọn lại tổ chức")}
          </Link>
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <nav aria-label={t("Mục của tổ chức")} className="lg:sticky lg:top-6 lg:self-start">
          {GROUPS.map((group) => (
            <div key={group.title ?? "_"} className={group.title ? "mt-5" : ""}>
              {group.title && (
                <p className="mb-1.5 px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {t(group.title)}
                </p>
              )}
              <ul className="space-y-1">
                {group.items.map((item) => (
                  <li key={item.to || "_index"}>
                    <NavLink
                      to={item.to}
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
            </div>
          ))}

          <Link
            to="/"
            className="mt-5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-ctu-blue"
          >
            <FolderIcon className={ICON} />
            {t("Về Cộng đồng")}
          </Link>
        </nav>

        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
