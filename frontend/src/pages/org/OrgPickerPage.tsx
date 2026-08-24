/**
 * `/org` — chọn tổ chức để vào.
 *
 * Vì sao có thêm một lớp thay vì vào thẳng
 * -----------------------------------------
 * Một tài khoản có thể thuộc NHIỀU tổ chức. Trước trang này, giao diện ngầm
 * giả định mỗi người đúng một tổ chức: thanh bên hiện tên tổ chức nhà, và không
 * có đường nào tới những tổ chức còn lại. Người được mời vào tổ chức thứ hai
 * không có cách nào đi tới đó.
 *
 * Lớp này là chỗ liệt kê và chọn — cùng vai trò với trang tổ chức của GitHub.
 * Nó cố ý MỎNG: không thống kê, không biểu đồ, chỉ danh sách và một cú bấm.
 *
 * Chọn xong thì phạm vi đổi ở MÁY CHỦ
 * ------------------------------------
 * `switchTenant` ghi `users.active_tenant_id`. Đoạn `/org/<id>` trên thanh địa
 * chỉ chỉ là bản sao của trạng thái ấy — gõ tay một mã khác vào đó không đổi
 * được phạm vi, vì `tenant_middleware` không đọc đường dẫn.
 *
 * Hệ quả: sau khi bấm, mọi dữ liệu đang giữ trong bộ nhớ trang là của tổ chức
 * CŨ. Điều hướng cứng (`window.location`) chứ không `navigate()` là cách rẻ
 * nhất để không phải đi tìm từng chỗ nhớ đệm — và nó cũng đúng về mặt ngữ
 * nghĩa: đổi tổ chức là đổi toàn bộ ngữ cảnh, không phải chuyển trang.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  createOwnTenant, listMyTenants, parseRole, roleLabel, switchTenant,
  type TenantMembershipRow,
} from "../../api/tenants";
import { fetchPlans, type Plan } from "../../api/billing";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";
import { ArrowLeftIcon, BuildingIcon, UsersIcon } from "../../components/ui/Icons";

export default function OrgPickerPage() {
  const { t } = useI18n();

  const [rows, setRows] = useState<TenantMembershipRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [entering, setEntering] = useState("");

  // Tự lập tổ chức.
  const [plans, setPlans] = useState<Plan[]>([]);
  const [ten, setTen] = useState("");
  const [goi, setGoi] = useState("free");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listMyTenants());
      setError("");
    } catch (err) {
      setError(friendlyError(err, t("Không tải được danh sách tổ chức.")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    // Bảng giá công khai, không cần đăng nhập. Hỏng thì im: người dùng vẫn tạo
    // được tổ chức trên gói mặc định, chỉ là không thấy mô tả các gói.
    void fetchPlans()
      .then((ds) => {
        setPlans(ds);
        const tuPhucVu = ds.find((p) => p.is_self_serve);
        if (tuPhucVu) setGoi(tuPhucVu.plan_code);
      })
      .catch(() => setPlans([]));
  }, []);

  const tuPhucVu = plans.filter((p) => p.is_self_serve);
  const soDangSoHuu = rows.filter((r) => r.role === "admin").length;

  const enter = async (tenantId: string) => {
    setEntering(tenantId);
    try {
      await switchTenant(tenantId);
      // Nạp lại cả trang: xem §docstring — đổi tổ chức là đổi ngữ cảnh, và mọi
      // thứ đang nhớ đệm trong bộ nhớ đều thuộc về tổ chức cũ.
      const base =
        (window as unknown as { __ENV__?: { VITE_BASE_PATH?: string } }).__ENV__
          ?.VITE_BASE_PATH || "/";
      window.location.assign(`${base.replace(/\/$/, "")}/org/${tenantId}`);
    } catch (err) {
      setError(friendlyError(err, t("Không vào được tổ chức này.")));
      setEntering("");
    }
  };

  const tao = async () => {
    setCreating(true);
    try {
      const t = await createOwnTenant({ display_name: ten.trim(), plan_code: goi });
      await enter(t.tenant_id);
    } catch (err) {
      setError(friendlyError(err, t("Không tạo được tổ chức.")));
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-ctu-blue"
      >
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        {t("Về Cộng đồng")}
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          <BuildingIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {t("Tổ chức")}
          </h1>
          <p className="text-sm text-slate-500">
            {t("Chọn tổ chức bạn muốn làm việc trong đó.")}
          </p>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">{t("Đang tải…")}</p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 px-6 py-10 text-center">
          <span className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-400">
            <UsersIcon className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="text-sm font-medium text-slate-700">
            {t("Bạn chưa thuộc tổ chức nào.")}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {t("Bạn vẫn đóng góp được ở Cộng đồng. Để vào một tổ chức, hãy chờ lời mời hoặc tự lập tổ chức của bạn.")}
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.tenant_id}>
              <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-900">
                    {row.display_name || row.tenant_id}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {roleLabel(parseRole(row.role ?? ""))}
                    {row.is_home ? ` · ${t("Tổ chức chính của bạn")}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void enter(row.tenant_id)}
                  disabled={Boolean(entering)}
                  className="shrink-0 rounded-lg bg-ctu-blue px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-ctu-blue/90 disabled:opacity-60"
                >
                  {entering === row.tenant_id ? t("Đang vào…") : t("Vào")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Tự lập tổ chức.

          Đặt SAU danh sách, không phải trước: phần lớn lượt mở trang này là để
          đi vào một tổ chức đã có, và một biểu mẫu đứng trên đầu sẽ chen vào
          giữa người dùng và việc họ tới đây để làm. */}
      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="font-medium text-slate-900">{t("Lập tổ chức của bạn")}</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          {t("Bạn sẽ là quản trị viên của tổ chức mới. Dữ liệu đã đóng góp ở nơi khác không bị chuyển đi.")}
        </p>

        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            value={ten}
            onChange={(e) => setTen(e.target.value)}
            placeholder={t("Tên tổ chức, ví dụ: Khoa Công nghệ Thông tin")}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={creating || !ten.trim()}
            onClick={() => void tao()}
            className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ctu-blue/90 disabled:opacity-50"
          >
            {creating ? t("Đang lập…") : t("Lập tổ chức")}
          </button>
        </div>

        {/* Gói. Chỉ gói TỰ PHỤC VỤ mới chọn được — số còn lại vẫn hiện, vì giấu
            chúng đi sẽ khiến người dùng tưởng nền tảng không có gì hơn. */}
        {plans.length > 0 && (
          <fieldset className="mt-4">
            <legend className="text-xs font-medium text-slate-600">{t("Gói dịch vụ")}</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {plans.map((p) => {
                const chonDuoc = p.is_self_serve;
                return (
                  <label
                    key={p.plan_code}
                    className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${
                      chonDuoc
                        ? goi === p.plan_code
                          ? "border-ctu-blue bg-ctu-blue/5 cursor-pointer"
                          : "border-slate-200 cursor-pointer hover:bg-slate-50"
                        : "border-slate-100 bg-slate-50 text-slate-400"
                    }`}
                  >
                    <input
                      type="radio"
                      name="plan"
                      className="mt-1"
                      value={p.plan_code}
                      checked={goi === p.plan_code}
                      disabled={!chonDuoc}
                      onChange={() => setGoi(p.plan_code)}
                    />
                    <span className="min-w-0">
                      <span className="block font-medium">{p.display_name}</span>
                      <span className="block text-xs">
                        {chonDuoc
                          ? t("Tự đăng ký được. Tối đa {n} tổ chức.", { n: "3" })
                          : t("Liên hệ quản trị viên nền tảng để nâng cấp.")}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}

        {tuPhucVu.length > 0 && soDangSoHuu >= 3 && (
          <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {t("Bạn đang sở hữu {n} tổ chức — đã chạm trần của gói tự đăng ký.", {
              n: String(soDangSoHuu),
            })}
          </p>
        )}
      </div>
    </div>
  );
}
