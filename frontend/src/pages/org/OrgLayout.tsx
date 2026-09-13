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
 * lệch với dữ liệu bên dưới.
 *
 * Vỏ này ĐỐI CHIẾU hai thứ trước khi dựng trang con (TEN-01, 13/09/2026):
 *   1. tài khoản có membership ở `:tenantId` không (`/tenants/mine`);
 *   2. máy chủ ĐANG lấy phạm vi ở tổ chức nào (`/tenants/me`).
 * Người thuộc cả A và B mở liên kết `/org/A` trong khi máy chủ ở B: bản trước
 * thấy membership A hợp lệ, im lặng dựng `Outlet`, và mọi lượt ghi vào B dưới
 * tiêu đề A. Nay vỏ chặn trang con và bắt CHỌN tường minh — chuyển sang A hay ở
 * lại B — như hộp "Choose an account" của Google. Không tự đổi ngầm: hai tab mở
 * hai tổ chức sẽ giành nhau `active_tenant_id`, và tab thua sẽ ghi nhầm mà
 * không hay biết.
 *
 * Không xác nhận được ngữ cảnh (API `/me` lỗi) thì cũng chặn, kèm nút thử lại:
 * trang con lúc đó không tải được gì, còn một lượt ghi "mù" thì có thể.
 *
 * Vỏ KHÔNG phải hàng rào quyền. Quyền vẫn do máy chủ cưỡng chế; thanh bên chỉ
 * ẩn thứ người dùng chắc chắn không bấm được.
 *
 * @i18n-key-table — `key` của từng mục là KHOÁ từ điển, dịch bằng `t(item.key)`.
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { fetchMyTenant, listMyTenants, switchTenant, type TenantMembershipRow } from "../../api/tenants";
import Button from "../../components/ui/Button";
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

  const [rows, setRows] = useState<TenantMembershipRow[]>([]);
  const [row, setRow] = useState<TenantMembershipRow | null>(null);
  /** Tổ chức máy chủ ĐANG lấy phạm vi; `null` = chưa xác nhận được. */
  const [active, setActive] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [switching, setSwitching] = useState(false);

  const load = useCallback(async () => {
    setChecked(false);
    const [mine, me] = await Promise.allSettled([listMyTenants(), fetchMyTenant()]);
    if (mine.status === "fulfilled") {
      setRows(mine.value);
      setRow(mine.value.find((x) => x.tenant_id === tenantId) ?? null);
    } else {
      // Không tải được danh sách thì KHÔNG kết luận là không thuộc tổ chức:
      // một lượt mạng trượt sẽ đá người dùng ra khỏi màn hình họ đang làm việc.
      setRow(null);
    }
    setActive(me.status === "fulfilled" ? me.value.tenant_id : null);
    setChecked(true);
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  const ten = row?.display_name || tenantId || "—";
  const activeRow = rows.find((x) => x.tenant_id === active) ?? null;
  const activeName = activeRow?.display_name || active || "—";

  /** Ngữ cảnh máy chủ chưa biết: KHÔNG dựng trang con. */
  const unverified = checked && active === null;
  /** Liên kết chỉ một tổ chức, máy chủ đang ở tổ chức khác. */
  const mismatch = checked && active !== null && active !== tenantId;

  const switchHere = async () => {
    setSwitching(true);
    try {
      await switchTenant(tenantId);
      // Dữ liệu mọi trang con đang giữ là của tổ chức cũ; nạp lại toàn bộ là
      // cách duy nhất chắc chắn không còn response cũ nào ghi đè.
      window.location.reload();
    } catch {
      setSwitching(false);
      await load();
    }
  };

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

      {checked && !row && !mismatch && !unverified && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("Không xác nhận được bạn thuộc tổ chức này. Dữ liệu hiển thị có thể không phải của tổ chức trên tiêu đề.")}{" "}
          <Link to="/org" className="font-medium underline">
            {t("Chọn lại tổ chức")}
          </Link>
        </p>
      )}

      {unverified && (
        <section
          role="alert"
          data-testid="org-context-unverified"
          className="rounded-xl border border-amber-200 bg-amber-50 p-5"
        >
          <h2 className="font-semibold text-amber-900">
            {t("Chưa xác nhận được bạn đang làm việc ở tổ chức nào")}
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            {t("Không kết nối được với máy chủ để kiểm tra ngữ cảnh. Trang chưa mở để tránh ghi dữ liệu nhầm tổ chức.")}
          </p>
          <div className="mt-3">
            <Button variant="secondary" onClick={() => void load()}>{t("Thử lại")}</Button>
          </div>
        </section>
      )}

      {mismatch && (
        <section
          role="alertdialog"
          aria-labelledby="org-mismatch-title"
          data-testid="org-context-mismatch"
          className="rounded-xl border border-amber-200 bg-amber-50 p-5"
        >
          <h2 id="org-mismatch-title" className="font-semibold text-amber-900">
            {t("Liên kết này thuộc {a}, nhưng bạn đang làm việc tại {b}", { a: ten, b: activeName })}
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            {t("Nếu tiếp tục ở đây, mọi dữ liệu bạn ghi sẽ vào {b}. Hãy chọn nơi bạn muốn làm việc.", { b: activeName })}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {row ? (
              <Button onClick={() => void switchHere()} disabled={switching}>
                {switching ? t("Đang chuyển…") : t("Chuyển sang {a}", { a: ten })}
              </Button>
            ) : (
              <p className="text-sm text-amber-800">
                {t("Bạn không phải thành viên của tổ chức trên liên kết này.")}
              </p>
            )}
            {active && (
              <Link
                to={`/org/${encodeURIComponent(active)}`}
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {t("Ở lại {b}", { b: activeName })}
              </Link>
            )}
          </div>
        </section>
      )}

      {!unverified && !mismatch && (
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
      )}
    </div>
  );
}
