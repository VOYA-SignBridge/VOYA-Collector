/**
 * "Bạn đang làm việc tại tổ chức X — nhãn này thuộc kho cộng đồng."
 *
 * Vì sao có nó: phạm vi dữ liệu theo tổ chức đang làm việc (`users.active_tenant_id`,
 * xem tenant_middleware.py). Tài khoản có tổ chức riêng mở một nhãn cộng đồng thì
 * máy chủ trả 404 — đúng theo cách ly, nhưng với người dùng trông như nhãn biến
 * mất. Trước 15/09/2026 trang chỉ hiện "Không tìm thấy", không nói vì sao, không
 * có lối ra. Thành phần này chỉ hiện khi (a) tổ chức đang làm việc KHÔNG phải cộng
 * đồng và (b) người này là thành viên cộng đồng; một nút chuyển phạm vi rồi tải lại.
 */
import { useEffect, useState } from "react";
import { fetchMyTenant, listMyTenants, switchTenant } from "../api/tenants";
import { useI18n } from "../i18n";

const isCommunity = (row: { tenant_id: string; tenant_type: string | null }) =>
  row.tenant_type === "COMMUNITY" || row.tenant_id === "default";

export default function CommunitySwitchHint({ reason }: { reason?: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<{ here: string; community: string; communityLabel: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [me, mine] = await Promise.all([fetchMyTenant(), listMyTenants()]);
        if (cancelled) return;
        const community = mine.find(isCommunity);
        if (!community || isCommunity({ tenant_id: me.tenant_id, tenant_type: null })) return;
        setState({
          here: me.display_name || me.tenant_id,
          community: community.tenant_id,
          communityLabel: community.display_name || t("Cộng đồng"),
        });
      } catch {
        // Không có dữ liệu thì không gợi ý — thông báo lỗi gốc vẫn còn.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  if (!state) return null;

  const go = async () => {
    setBusy(true);
    try {
      await switchTenant(state.community);
      window.location.reload();
    } catch {
      setBusy(false);
    }
  };

  return (
    <div
      className="rounded-xl border border-ctu-blue/30 bg-ctu-blue/5 px-4 py-3 text-sm text-slate-800"
      data-testid="community-switch-hint"
    >
      <p>
        {t("Bạn đang làm việc tại {org}. {what} — dữ liệu ở đó chỉ thấy khi chuyển sang kho cộng đồng.", {
          org: state.here,
          what: reason || t("Nội dung này thuộc kho cộng đồng"),
        })}
      </p>
      <button
        type="button"
        onClick={go}
        disabled={busy}
        className="mt-2 rounded-lg bg-ctu-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-ctu-navy disabled:opacity-50"
      >
        {busy ? t("Đang chuyển…") : t("Chuyển sang {name}", { name: state.communityLabel })}
      </button>
    </div>
  );
}
