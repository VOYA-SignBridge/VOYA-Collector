/**
 * `/moderation` — hàng đợi kiểm duyệt.
 *
 * Vì sao ở CẤP CAO NHẤT chứ không nằm trong `/admin`
 * ---------------------------------------------------
 * Người kiểm duyệt là chuyên gia được mời, không phải người vận hành nền tảng.
 * `/admin` bọc trong `ProtectedRoute requireAdmin`, nên đặt trang này ở đó sẽ
 * chặn đúng những người nó sinh ra để phục vụ — họ giữ `community_reviewer`
 * chứ không giữ `is_admin`.
 *
 * Ẩn/hiện KHÔNG phải chặn: thanh bên chỉ hiện mục này với người có quyền, còn
 * `require_moderator` ở máy chủ mới là thứ cưỡng chế. Gõ thẳng địa chỉ vào
 * trình duyệt sẽ tới trang và nhận 403 từ API — đúng như vậy.
 *
 * Từ chối bắt buộc có lý do
 * --------------------------
 * Ô lý do mở ra ngay tại dòng, và nút chỉ bật khi đã gõ gì đó. Máy chủ cũng
 * cưỡng chế — hai lớp, vì lớp ở giao diện chỉ là phép lịch sự và một lệnh
 * `curl` không đọc nó.
 */

import { useCallback, useEffect, useState } from "react";

import {
  approveSession, fetchQueue, rejectSession, type PendingSession,
} from "../api/moderation";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import { useToast } from "../hooks/useToast";
import { ClipboardCheckIcon, UsersIcon } from "../components/ui/Icons";

function nguoiDongGop(s: PendingSession): string {
  return (s.contributor_email || s.contributor_name || "—").trim();
}

function khiNao(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export default function ModerationPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [items, setItems] = useState<PendingSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  /** Phiên đang mở ô lý do, và nội dung lý do đó. */
  const [rejecting, setRejecting] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = await fetchQueue();
      setItems(q.items);
      setTotal(q.count);
      setError("");
    } catch (err) {
      setError(friendlyError(err, t("Không tải được hàng đợi kiểm duyệt.")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const quyetDinh = async (s: PendingSession, duyet: boolean) => {
    setBusy(s.capture_session_id);
    try {
      if (duyet) {
        await approveSession(s.capture_session_id);
        toast.success(t("Đã duyệt và công khai."));
      } else {
        await rejectSession(s.capture_session_id, note);
        toast.success(t("Đã từ chối. Dữ liệu vẫn thuộc về người đóng góp."));
      }
      setRejecting("");
      setNote("");
      // Nạp lại cả hàng đợi thay vì gỡ một dòng khỏi state: người khác cũng
      // đang duyệt, và một danh sách chỉ tự sửa ở phía mình sẽ dần lệch khỏi
      // con số trên huy hiệu.
      await load();
    } catch (err) {
      toast.error(friendlyError(err, t("Không ghi được quyết định.")));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="mx-auto w-full max-w-5xl">
      <div className="mb-6 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          <ClipboardCheckIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {t("Kiểm duyệt")}
          </h1>
          <p className="text-sm text-slate-500">
            {t("Dữ liệu chờ duyệt trước khi công khai cho mọi người.")}
          </p>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">{t("Đang tải…")}</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 px-6 py-12 text-center">
          <span className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-400">
            <ClipboardCheckIcon className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="text-sm font-medium text-slate-700">
            {t("Không có gì đang chờ duyệt.")}
          </p>
        </div>
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-500">
            {t("{n} lượt thu đang chờ.", { n: String(total) })}
          </p>
          <ul className="space-y-3">
            {items.map((s) => {
              const dangTuChoi = rejecting === s.capture_session_id;
              const dangBan = busy === s.capture_session_id;
              return (
                <li
                  key={s.capture_session_id}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900">
                        {s.label_original || "—"}
                        {s.dialect ? (
                          <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs font-normal text-slate-600">
                            {s.dialect}
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                        <span className="inline-flex items-center gap-1">
                          <UsersIcon className="h-3.5 w-3.5" aria-hidden="true" />
                          {nguoiDongGop(s)}
                        </span>
                        <span>{t("{n} mẫu", { n: String(s.sample_count) })}</span>
                        <span>{khiNao(s.captured_at)}</span>
                      </p>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        disabled={dangBan}
                        onClick={() => void quyetDinh(s, true)}
                        className="rounded-lg bg-ctu-blue px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-ctu-blue/90 disabled:opacity-60"
                      >
                        {t("Duyệt")}
                      </button>
                      <button
                        type="button"
                        disabled={dangBan}
                        onClick={() => {
                          setRejecting(dangTuChoi ? "" : s.capture_session_id);
                          setNote("");
                        }}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                      >
                        {t("Từ chối")}
                      </button>
                    </div>
                  </div>

                  {dangTuChoi && (
                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <label className="block text-xs font-medium text-slate-600">
                        {t("Lý do từ chối — người đóng góp sẽ đọc câu này")}
                      </label>
                      <div className="mt-1.5 flex gap-2">
                        <input
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          placeholder={t("Ví dụ: tay ra khỏi khung hình ở giữa cử chỉ.")}
                          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                        />
                        <button
                          type="button"
                          disabled={dangBan || !note.trim()}
                          onClick={() => void quyetDinh(s, false)}
                          className="shrink-0 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                        >
                          {t("Xác nhận từ chối")}
                        </button>
                      </div>
                      <p className="mt-1.5 text-xs text-slate-500">
                        {t("Từ chối không xoá dữ liệu. Người đóng góp vẫn dùng được cho riêng họ.")}
                      </p>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
