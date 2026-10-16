/**
 * "Đang làm việc tại: <tổ chức>" — chip nhỏ trên thanh đầu trang.
 *
 * Kế hoạch UX 13/09/2026 §4: ba câu người dùng phải trả lời được trên MỌI
 * màn hình, và câu đầu là "tôi đang ở đâu?". Trước đây tên tổ chức chỉ hiện
 * bên trong `/org/:tenantId`; ở trang thu dữ liệu, trang nhận dạng hay trang
 * cài đặt thì không có gì nói người dùng đang ghi vào tổ chức nào — trong khi
 * phạm vi ghi (`users.active_tenant_id`) vẫn đang có hiệu lực ở đó.
 *
 * Nguồn: `/tenants/me` — tổ chức mà máy chủ ĐANG lấy phạm vi, không phải một
 * giá trị giao diện tự nhớ. Lỗi thì chip biến mất chứ không chặn thanh đầu.
 * Mẫu: bộ chọn workspace của Slack, menu tổ chức của GitHub, vùng của AWS.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchMyTenant } from "../api/tenants";
import { useI18n } from "../i18n";
import { BuildingIcon } from "./ui/Icons";

export default function WorkingContextChip({ className = "" }: { className?: string }) {
  const { t } = useI18n();
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMyTenant()
      .then((me) => {
        if (cancelled) return;
        const label = me.tenant_id === "community"
          ? t("Cộng đồng")
          : me.display_name || me.tenant_id;
        setName(label);
      })
      .catch(() => {
        if (!cancelled) setName(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ hỏi máy chủ một lần khi dựng
  }, []);

  if (!name) return null;

  return (
    <div
      data-testid="working-context"
      className={`flex min-w-0 items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 py-1 pl-2 pr-1 text-xs text-slate-700 ${className}`}
    >
      <BuildingIcon className="h-3.5 w-3.5 shrink-0 text-ctu-blue" aria-hidden="true" />
      <span className="hidden sm:inline text-slate-500">{t("Đang làm việc tại:")}</span>
      <span className="max-w-[10rem] truncate font-medium" title={name}>{name}</span>
      <Link
        to="/org"
        className="rounded-full px-2 py-0.5 font-medium text-ctu-blue hover:bg-ctu-blue/10"
      >
        {t("Đổi")}
      </Link>
    </div>
  );
}
