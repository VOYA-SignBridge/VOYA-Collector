/**
 * Tạo tổ chức, ngay tại chỗ.
 *
 * Bản trước ở đây là `RequestOrganizationCard`: nó mở một PHIẾU HỖ TRỢ và người
 * dùng ngồi đợi quản trị viên nền tảng lập tổ chức hộ. Lý do khi đó là thật —
 * `POST /tenants` đòi quyền nền tảng, nên một nút gọi thẳng nó chỉ là một nút
 * luôn 403 — nhưng nó bỏ ngỏ bốn câu hỏi thay vì trả lời chúng.
 *
 * Giờ chúng đã có câu trả lời, ở `POST /tenants/self-serve`: ai cũng tạo được
 * khi nền tảng mở tự phục vụ, mỗi tài khoản MỘT tổ chức, chỉ gói tự phục vụ,
 * và cùng bộ giới hạn tần suất với các endpoint danh mục. Nên chỗ này là một
 * cái nút thật.
 *
 * Điều màn hình phải nói thẳng: tạo tổ chức mới ĐỔI nơi dữ liệu MỚI rơi vào.
 * Dữ liệu đã đóng góp ở lại tổ chức cũ. Người dùng phải biết điều đó TRƯỚC khi
 * bấm, chứ không phải phát hiện ra khi thư viện của họ trông như trống rỗng.
 */
import { useEffect, useState } from "react";
import { createOwnTenant } from "../../api/tenants";
import { fetchPlans, formatPrice, type Plan } from "../../api/billing";
import Button from "../ui/Button";
import { BuildingIcon, AlertTriangleIcon } from "../ui/Icons";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";

export default function CreateOrganizationCard({
  onCreated,
  warnDataStays = false,
}: {
  onCreated?: () => void;
  /** Bật khi người dùng ĐANG ở trong một tổ chức khác. */
  warnDataStays?: boolean;
}) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [planCode, setPlanCode] = useState("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchPlans()
      .then((rows) => {
        setPlans(rows);
        const first = rows.find((p) => p.is_self_serve);
        if (first) setPlanCode(first.plan_code);
      })
      .catch(() => setPlans([]));
  }, []);

  const canSend = name.trim().length >= 2 && !busy;

  const submit = async () => {
    if (!canSend) return;
    setBusy(true);
    setError("");
    try {
      await createOwnTenant({
        display_name: name.trim(),
        ...(planCode ? { plan_code: planCode } : {}),
      });
      onCreated?.();
      // Tổ chức nhà vừa đổi — phiên hiện tại vẫn mang phạm vi cũ cho tới khi
      // nạp lại. Nạp lại thẳng thay vì cập nhật từng mảnh trạng thái: mọi màn
      // hình đều đọc phạm vi này, và một nửa số đó cập nhật là nửa còn lại sai.
      window.location.reload();
    } catch (err) {
      setError(friendlyError(err, t("Không tạo được tổ chức")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ctu-blue/10 text-ctu-blue">
          <BuildingIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Tạo tổ chức của bạn")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Bạn sẽ là quản trị viên và mời được người khác vào cùng thu dữ liệu.")}
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        <div>
          <label htmlFor="org-name" className="mb-1 block text-sm font-medium text-slate-700">
            {t("Tên tổ chức")}
          </label>
          <input
            id="org-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("vd: Khoa CNTT - Trường ABC")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
          />
        </div>

        {plans.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("Gói dịch vụ")}
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {plans.map((p) => {
                const selectable = p.is_self_serve;
                const active = planCode === p.plan_code;
                return (
                  <button
                    key={p.plan_code}
                    type="button"
                    disabled={!selectable}
                    onClick={() => selectable && setPlanCode(p.plan_code)}
                    className={`rounded-xl border p-3 text-left transition-colors ${
                      active
                        ? "border-ctu-blue bg-ctu-blue/5 ring-1 ring-ctu-blue"
                        : selectable
                          ? "border-slate-200 bg-white hover:border-ctu-blue/50"
                          : "cursor-not-allowed border-slate-200 bg-slate-100 opacity-60"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-900">{p.display_name}</span>
                      <span className="text-xs font-medium text-slate-600">
                        {formatPrice(p.price_cents, p.currency)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {p.max_seats === null
                        ? t("Không giới hạn thành viên")
                        : t("Tối đa {n} thành viên", { n: String(p.max_seats) })}
                    </p>
                    {!selectable && (
                      <p className="mt-1 text-[11px] font-medium text-slate-500">
                        {t("Liên hệ để nâng cấp sau khi đăng ký")}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {warnDataStays && (
          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
            <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              {t("Dữ liệu bạn đã đóng góp Ở LẠI tổ chức hiện tại. Tổ chức mới bắt đầu từ trống, và dữ liệu bạn thu từ nay sẽ thuộc về nó.")}
            </span>
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <Button onClick={submit} disabled={!canSend}>
          {busy ? t("Đang tạo…") : t("Tạo tổ chức")}
        </Button>
      </div>
    </div>
  );
}
