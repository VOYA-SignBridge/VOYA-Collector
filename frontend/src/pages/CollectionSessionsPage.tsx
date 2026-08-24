/**
 * Lần thu (UC12 — Manage Collection Sessions).
 *
 * Trước trang này, một phiên thu chỉ nhìn thấy được gián tiếp: mở chi tiết một
 * nhãn thì thấy các lần quay CỦA NHÃN ĐÓ. Không có chỗ nào trả lời "hôm qua tôi
 * thu những gì", "phiên nào chưa đóng", hay "ai đã thu phiên này" — dù bảng
 * `capture_sessions` đã ghi đủ từ lâu.
 *
 * Hai điều màn hình này cố ý làm khác thói quen:
 *
 *  - **Ô trống là ô trống.** Người ký, người thu, ghi chú — thiếu thì hiện
 *    "chưa ghi nhận" màu nhạt chứ không điền một cái tên hợp lý. 100/250 phiên
 *    trong kho hiện không có người ký, và đó là dữ kiện cần thấy chứ không phải
 *    lỗi cần che.
 *  - **Phạm vi do máy chủ quyết.** Trang hiển thị đúng `scope` mà máy chủ trả
 *    về, không phải cái nó xin. Người dùng thường xin `tenant` sẽ nhận 403, và
 *    một giao diện tự tin rằng mình đang xem cả tổ chức trong khi thực ra chỉ
 *    thấy phần mình là giao diện nói dối.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/ui/PageHeader";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Badge from "../components/ui/Badge";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../contexts/AuthContext";
import { isTenantAdmin } from "../api/auth";
import {
  getSessions,
  updateSession,
  type CollectionSession,
  type SessionsResponse,
} from "../api/sessions";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import { CameraIcon, ClockIcon, SearchIcon, TagIcon, UsersIcon } from "../components/ui/Icons";

function Unrecorded() {
  const { t } = useI18n();
  return <span className="italic text-slate-400">{t("chưa ghi nhận")}</span>;
}

function Stat({ label, value, icon }: { label: string; value: ReactNode; icon: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          {icon}
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      </div>
      <div className="mt-3 text-2xl font-bold tabular-nums text-slate-900">{value}</div>
    </div>
  );
}

function fmt(v: string | null): string {
  if (!v) return "";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : d.toLocaleString();
}

/** Khoảng thời gian một phiên kéo dài. Không đoán khi thiếu một trong hai mốc. */
function duration(a: string | null, b: string | null, t: (k: string, v?: Record<string, string>) => string): string | null {
  if (!a || !b) return null;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (!isFinite(ms) || ms < 0) return null;
  const min = Math.floor(ms / 60000);
  const sec = Math.round((ms % 60000) / 1000);
  return min > 0 ? t("{p} phút {g} giây", { p: String(min), g: String(sec) }) : t("{g} giây", { g: String(sec) });
}

export default function CollectionSessionsPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const { user } = useAuth();
  const canSeeTenant = isTenantAdmin(user);

  const [data, setData] = useState<SessionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [want, setWant] = useState<"auto" | "mine" | "tenant">("auto");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await getSessions(want));
    } catch (e) {
      toast.error(friendlyError(e, t("Không tải được danh sách lần thu")));
    } finally {
      setLoading(false);
    }
  }, [want, t, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return data?.sessions ?? [];
    return (data?.sessions ?? []).filter(
      (s) =>
        (s.label ?? "").toLowerCase().includes(q) ||
        (s.signer_name ?? "").toLowerCase().includes(q) ||
        (s.signer_id ?? "").toLowerCase().includes(q) ||
        (s.contributor ?? "").toLowerCase().includes(q) ||
        s.session_id.includes(q),
    );
  }, [data, query]);

  const close = async (s: CollectionSession) => {
    if (!window.confirm(t("Đóng phiên thu này? Sau khi đóng, không gắn thêm mẫu vào nó được nữa."))) return;
    try {
      setBusy(s.capture_session_id);
      await updateSession(s.capture_session_id, { close: true });
      toast.success(t("Đã đóng phiên thu"));
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Không đóng được phiên")));
    } finally {
      setBusy("");
    }
  };

  const totalSamples = (data?.sessions ?? []).reduce((n, s) => n + s.sample_count, 0);

  if (loading && !data) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("Lần thu")}
        subtitle={t("Mỗi lần ngồi trước máy quay cho một nhãn là một phiên: ai ký, ai thu, được bao nhiêu mẫu.")}
        actions={
          <button
            onClick={load}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {t("Làm mới")}
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("Phiên thu")} value={data?.total ?? 0} icon={<CameraIcon className="h-5 w-5" />} />
        <Stat label={t("Đang mở")} value={data?.open_count ?? 0} icon={<ClockIcon className="h-5 w-5" />} />
        <Stat label={t("Tổng mẫu")} value={totalSamples.toLocaleString("vi-VN")} icon={<TagIcon className="h-5 w-5" />} />
        <Stat
          label={t("Phạm vi")}
          value={
            <span className="text-base font-semibold">
              {data?.scope === "tenant" ? t("Cả tổ chức") : t("Của tôi")}
            </span>
          }
          icon={<UsersIcon className="h-5 w-5" />}
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Tìm theo nhãn, người ký, người thu hoặc mã phiên")}
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
            />
          </div>
          {canSeeTenant && (
            <div className="flex shrink-0 gap-1 rounded-lg border border-slate-200 p-1">
              {(["mine", "tenant"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setWant(s)}
                  className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                    (data?.scope ?? "mine") === s
                      ? "bg-ctu-blue text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {s === "mine" ? t("Của tôi") : t("Cả tổ chức")}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2.5 text-left font-medium">{t("Nhãn")}</th>
                <th className="px-3 py-2.5 text-left font-medium">{t("Người ký")}</th>
                <th className="px-3 py-2.5 text-left font-medium">{t("Người thu")}</th>
                <th className="px-3 py-2.5 text-right font-medium">{t("Mẫu")}</th>
                <th className="px-3 py-2.5 text-left font-medium">{t("Bắt đầu")}</th>
                <th className="px-3 py-2.5 text-left font-medium">{t("Kéo dài")}</th>
                <th className="px-3 py-2.5 text-left font-medium">{t("Trạng thái")}</th>
                <th className="px-3 py-2.5 text-right font-medium">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    {t("Chưa có lần thu nào.")}
                  </td>
                </tr>
              )}
              {rows.map((s) => {
                const dur = duration(s.started_at, s.ended_at, t);
                return (
                  <tr key={s.capture_session_id} className="border-t border-slate-100 hover:bg-slate-50/60">
                    <td className="px-3 py-2.5">
                      <Link
                        to={`/labels/${s.class_uid}`}
                        className="font-medium text-ctu-blue hover:underline"
                      >
                        {s.label || s.class_uid.slice(0, 8)}
                      </Link>
                      {s.dialect && (
                        <span className="ml-2 text-xs text-slate-400">{s.dialect}</span>
                      )}
                      {s.note && <p className="mt-0.5 text-xs text-slate-500">{s.note}</p>}
                    </td>
                    <td className="px-3 py-2.5 text-slate-700">
                      {s.signer_name || s.signer_id || <Unrecorded />}
                    </td>
                    <td className="px-3 py-2.5 text-slate-700">
                      {s.contributor || <Unrecorded />}
                      {s.is_mine && (
                        <span className="ml-1.5 text-xs font-medium text-ctu-blue">{t("— bạn")}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold tabular-nums text-slate-700">
                      {s.sample_count}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-500">
                      {fmt(s.started_at) || <Unrecorded />}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-500">
                      {dur ?? <Unrecorded />}
                    </td>
                    <td className="px-3 py-2.5">
                      {s.is_open ? (
                        <Badge variant="warning">{t("Đang mở")}</Badge>
                      ) : (
                        <Badge variant="default">{t("Đã đóng")}</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {s.is_open && (
                        <button
                          onClick={() => close(s)}
                          disabled={busy === s.capture_session_id}
                          className="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
                        >
                          {t("Đóng phiên")}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
