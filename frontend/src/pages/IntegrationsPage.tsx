/**
 * Khoá API và webhook.
 *
 * Ràng buộc thiết kế trung tâm: **bí mật chỉ hiện một lần**. Backend chỉ lưu
 * băm của khoá và không endpoint nào đọc lại bí mật webhook, nên nếu người
 * dùng đóng hộp thoại mà chưa sao chép thì không có đường nào lấy lại — chỉ
 * còn cách cấp cái mới.
 *
 * Giao diện phải nói điều đó THẲNG và làm việc sao chép thành thao tác dễ nhất
 * trên màn hình. Một dòng chữ nhỏ "hãy lưu lại" ở góc là cách chắc chắn để
 * người ta bỏ lỡ; ở đây bí mật nằm trong một khối riêng, có nút sao chép, và
 * hộp thoại phải bấm "Tôi đã lưu" mới đóng được.
 */

import { useCallback, useEffect, useState } from "react";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useToast } from "../hooks/useToast";
import { Trans, useI18n } from "../i18n";
import {
  createApiKey,
  createWebhook,
  deleteWebhook,
  fetchApiKeys,
  fetchDeliveries,
  fetchEventTypes,
  fetchWebhooks,
  revokeApiKey,
  sendTestEvent,
  type ApiKey,
  type Delivery,
  type Webhook,
} from "../api/integrations";

function fmtDate(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString("vi-VN");
}

/**
 * Khối hiện một bí mật đúng một lần.
 *
 * `navigator.clipboard` không có trong ngữ cảnh không bảo mật (http trên máy
 * khác localhost) — đúng cấu hình của bản triển khai CTU hiện tại. Nên nút sao
 * chép phải xử lý được trường hợp vắng mặt thay vì ném lỗi, và văn bản luôn
 * chọn được bằng tay để người dùng còn đường thứ hai.
 */
function SecretOnce({
  title,
  secret,
  onDismiss,
}: {
  title: string;
  secret: string;
  onDismiss: () => void;
}) {
  const { t } = useI18n();
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      toast.success("Đã sao chép");
    } catch {
      toast.error("Trình duyệt không cho sao chép tự động — hãy bôi đen và copy tay.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <h3 className="text-lg font-bold text-slate-900">{title}</h3>
        <p className="mt-1 text-sm text-slate-600">
          {t("Đây là lần")} <strong>{t("duy nhất")}</strong> {t("giá trị này hiện ra. Máy chủ chỉ lưu bản băm, nên không ai — kể cả quản trị viên — đọc lại được. Nếu mất, hãy thu hồi và cấp lại.")}
        </p>
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <code className="block break-all font-mono text-sm text-slate-900 select-all">
            {secret}
          </code>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => void copy()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {t("Sao chép")}
          </button>
          <button
            type="button"
            onClick={onDismiss}
            disabled={!copied}
            title={copied ? undefined : t("Hãy sao chép trước khi đóng")}
            className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Tôi đã lưu")}
          </button>
        </div>
      </div>
    </div>
  );
}

function ApiKeysSection() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<"read" | "write">("read");
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setKeys(await fetchApiKeys());
    } catch {
      toast.error("Không tải được danh sách khoá API.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      const created = await createApiKey({ name: name.trim(), scopes });
      setRevealed(created.key);
      setName("");
      await load();
    } catch (err) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Không cấp được khoá.";
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (key: ApiKey) => {
    if (!window.confirm(t("Thu hồi khoá {prefix}…? Mọi hệ thống đang dùng nó sẽ mất quyền ngay.", { prefix: key.prefix })))
      return;
    try {
      await revokeApiKey(key.key_id);
      toast.success("Đã thu hồi");
      await load();
    } catch {
      toast.error("Không thu hồi được khoá.");
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900">{t("Khoá API")}</h3>
      <p className="mt-1 text-sm text-slate-500">
        <Trans
          k="Dùng để hệ thống khác gọi nền tảng mà không cần trình duyệt. Gửi kèm header {header}. Khoá không bao giờ có quyền quản trị nền tảng."
          vars={{
            header: (
              <code className="rounded bg-slate-100 px-1 font-mono text-xs">
                Authorization: Bearer voya_…
              </code>
            ),
          }}
        />
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex-1 min-w-[12rem]">
          <span className="mb-1 block text-xs font-medium text-slate-600">{t("Tên gợi nhớ")}</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("vd: đồng bộ đêm")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none"
          />
        </label>
        <label>
          <span className="mb-1 block text-xs font-medium text-slate-600">{t("Quyền")}</span>
          <select
            value={scopes}
            onChange={(e) => setScopes(e.target.value as "read" | "write")}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none"
          >
            <option value="read">{t("Chỉ đọc")}</option>
            <option value="write">{t("Đọc và ghi")}</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => void create()}
          disabled={busy}
          className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white hover:bg-ctu-navy disabled:opacity-50"
        >
          {t("Cấp khoá mới")}
        </button>
      </div>

      {loading ? (
        <LoadingSpinner size="sm" />
      ) : keys.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">{t("Chưa có khoá nào.")}</p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4 font-medium">{t("Khoá")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Tên")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Quyền")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Dùng lần cuối")}</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {keys.map((key) => (
                <tr key={key.key_id}>
                  <td className="py-2.5 pr-4">
                    <code className="font-mono text-xs text-slate-800">{key.prefix}…</code>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-700">{key.name || "—"}</td>
                  <td className="py-2.5 pr-4">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                      {key.scopes === "write" ? t("đọc + ghi") : t("chỉ đọc")}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-500">{fmtDate(key.last_used_at)}</td>
                  <td className="py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => void revoke(key)}
                      className="text-sm font-medium text-red-600 hover:underline"
                    >
                      {t("Thu hồi")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {revealed ? (
        <SecretOnce
          title={t("Khoá API mới")}
          secret={revealed}
          onDismiss={() => setRevealed(null)}
        />
      ) : null}
    </section>
  );
}

function WebhooksSection() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<Record<string, Delivery[]>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hookList, types] = await Promise.all([fetchWebhooks(), fetchEventTypes()]);
      setHooks(hookList);
      setEventTypes(types);
    } catch {
      toast.error("Không tải được danh sách webhook.");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      const created = await createWebhook({
        url: url.trim(),
        // Rỗng nghĩa là NHẬN TẤT CẢ, khớp quy ước `*` của backend. Gửi chuỗi
        // rỗng sẽ bị từ chối là loại sự kiện không hợp lệ.
        event_types: selected.length ? selected.join(",") : "*",
        description: "",
      });
      setRevealed(created.secret);
      setUrl("");
      setSelected([]);
      await load();
    } catch (err) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Không tạo được webhook.";
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (hook: Webhook) => {
    if (!window.confirm(t("Xoá webhook tới {url}?", { url: hook.url }))) return;
    try {
      await deleteWebhook(hook.endpoint_id);
      toast.success("Đã xoá");
      await load();
    } catch {
      toast.error("Không xoá được webhook.");
    }
  };

  const test = async (hook: Webhook) => {
    try {
      await sendTestEvent(hook.endpoint_id);
      toast.success("Đã xếp một sự kiện thử vào hàng giao (tối đa một phút).");
    } catch {
      toast.error("Không gửi được sự kiện thử.");
    }
  };

  const showDeliveries = async (hook: Webhook) => {
    try {
      // Lấy dữ liệu TRƯỚC, đặt trạng thái SAU. Hàm cập nhật truyền cho
      // `setState` phải thuần và đồng bộ — React gọi nó lại nhiều lần và
      // không chờ Promise nào cả.
      const rows = await fetchDeliveries(hook.endpoint_id);
      setDeliveries((prev) => ({ ...prev, [hook.endpoint_id]: rows }));
    } catch {
      toast.error("Không tải được lịch sử giao.");
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900">Webhook</h3>
      <p className="mt-1 text-sm text-slate-500">
        <Trans
          k="Nền tảng gọi ngược về hệ thống của bạn khi có việc xảy ra. Mỗi lần giao mang header {header} là HMAC-SHA256 của {than}; hãy kiểm cả dấu thời gian để từ chối thư phát lại."
          vars={{
            header: (
              <code className="rounded bg-slate-100 px-1 font-mono text-xs">
                X-Voya-Signature
              </code>
            ),
            than: (
              <code className="rounded bg-slate-100 px-1 font-mono text-xs">
                {t("&lt;timestamp&gt;.&lt;thân thư&gt;")}
              </code>
            ),
          }}
        />
      </p>

      <div className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">{t("URL nhận")}</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://he-thong-cua-ban.vn/voya-hook"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none"
          />
        </label>
        <fieldset>
          <legend className="mb-1.5 text-xs font-medium text-slate-600">
            {t("Sự kiện muốn nhận (bỏ trống = tất cả)")}
          </legend>
          <div className="flex flex-wrap gap-2">
            {eventTypes.map((type) => {
              const active = selected.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setSelected((prev) =>
                      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
                    )
                  }
                  className={`rounded-full border px-3 py-1 font-mono text-xs transition-colors ${
                    active
                      ? "border-ctu-blue bg-ctu-blue text-white"
                      : "border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {type}
                </button>
              );
            })}
          </div>
        </fieldset>
        <button
          type="button"
          onClick={() => void create()}
          disabled={busy || !url.trim()}
          className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white hover:bg-ctu-navy disabled:opacity-50"
        >
          {t("Thêm webhook")}
        </button>
      </div>

      {loading ? (
        <LoadingSpinner size="sm" />
      ) : hooks.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">{t("Chưa có webhook nào.")}</p>
      ) : (
        <ul className="mt-6 space-y-3">
          {hooks.map((hook) => (
            <li key={hook.endpoint_id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="break-all font-mono text-sm text-slate-900">{hook.url}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {hook.event_types === "*" ? t("tất cả sự kiện") : hook.event_types}
                    {" · "}
                    thành công gần nhất: {fmtDate(hook.last_success_at)}
                  </div>
                  {!hook.is_active ? (
                    <div className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-800">
                      Đã tự tắt: {hook.disabled_reason}
                    </div>
                  ) : hook.failure_streak > 0 ? (
                    <div className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                      {hook.failure_streak} lần giao hỏng liên tiếp
                    </div>
                  ) : null}
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => void test(hook)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {t("Gửi thử")}
                  </button>
                  <button
                    type="button"
                    onClick={() => void showDeliveries(hook)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {t("Lịch sử")}
                  </button>
                  <button
                    type="button"
                    onClick={() => void remove(hook)}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 hover:underline"
                  >
                    {t("Xoá")}
                  </button>
                </div>
              </div>

              {deliveries[hook.endpoint_id] ? (
                <div className="mt-3 overflow-x-auto border-t border-slate-100 pt-3">
                  {deliveries[hook.endpoint_id].length === 0 ? (
                    <p className="text-xs text-slate-500">{t("Chưa có lần giao nào.")}</p>
                  ) : (
                    <table className="w-full text-xs">
                      <tbody className="divide-y divide-slate-100">
                        {deliveries[hook.endpoint_id].map((d) => (
                          <tr key={d.delivery_id}>
                            <td className="py-1.5 pr-3 font-mono text-slate-700">
                              {d.event_type}
                            </td>
                            <td className="py-1.5 pr-3">
                              <span
                                className={
                                  d.status === "delivered"
                                    ? "text-sky-800"
                                    : d.status === "failed"
                                      ? "text-red-700"
                                      : "text-slate-500"
                                }
                              >
                                {d.status}
                              </span>
                            </td>
                            <td className="py-1.5 pr-3 tabular-nums text-slate-500">
                              {d.attempts} lần
                            </td>
                            <td className="py-1.5 pr-3 text-slate-500">
                              {d.last_status_code ?? d.last_error ?? "—"}
                            </td>
                            <td className="py-1.5 text-slate-400">{fmtDate(d.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {revealed ? (
        <SecretOnce
          title={t("Bí mật ký webhook")}
          secret={revealed}
          onDismiss={() => setRevealed(null)}
        />
      ) : null}
    </section>
  );
}

export default function IntegrationsPage() {
  const { t } = useI18n();
  return (
    <div className="space-y-6 p-4">
      <PageHeader
        title={t("Tích hợp")}
        subtitle={t("Khoá API và webhook cho hệ thống của tổ chức")}
      />
      <ApiKeysSection />
      <WebhooksSection />
    </div>
  );
}
