/**
 * "Tải dữ liệu của tôi" — tab trong Đóng góp dữ liệu (`UploadPage`).
 *
 * Khác bản xuất tổ chức ở trang Tổ chức (chỉ quản trị viên, cả tenant): đây là
 * gói CỦA RIÊNG người đang xem — samples.csv + tệp .npz thật, chỉ những dòng
 * họ tự đóng góp. Không cần chọn phạm vi vì phạm vi luôn là "của tôi".
 */
import { useCallback, useEffect, useState } from "react";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { useToast } from "../hooks/useToast";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import { DownloadIcon } from "../components/ui/Icons";
import { toneClasses, toneForStatus, FOCUS_RING } from "../theme/status";
import {
  fetchPersonalExports,
  requestPersonalExport,
  personalExportDownloadUrl,
  STATUS_LABEL,
  type PersonalExport,
} from "../api/personalExports";

function fmtBytes(n: number | null): string {
  if (!n) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function MyDataDownloadsPanel() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [rows, setRows] = useState<PersonalExport[]>([]);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await fetchPersonalExports());
    } catch (e) {
      toast.error(friendlyError(e, t("Không tải được danh sách bản xuất")));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Còn việc chưa xong thì hỏi lại mỗi 3 giây, cùng nhịp với trang Tổ chức.
  const hasPending = rows.some((r) => r.status === "pending" || r.status === "running");
  useEffect(() => {
    if (!hasPending) return;
    const id = setInterval(() => {
      fetchPersonalExports().then(setRows).catch(() => undefined);
    }, 3000);
    return () => clearInterval(id);
  }, [hasPending]);

  const request = async () => {
    try {
      setRequesting(true);
      await requestPersonalExport();
      toast.success(t("Đã đặt hàng bản xuất; theo dõi trạng thái bên dưới"));
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Không đặt được bản xuất")));
    } finally {
      setRequesting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-slate-700">{t("Tải dữ liệu của tôi")}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {t("Gói gồm samples.csv và tệp đặc trưng (.npz) thật, chỉ những mẫu bạn đã tự đóng góp.")}
            </p>
          </div>
          <button
            onClick={request}
            disabled={requesting}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium border ${toneClasses("success", "solid")} ${FOCUS_RING} disabled:opacity-50`}
          >
            <DownloadIcon className="h-4 w-4" aria-hidden="true" />
            {t("Yêu cầu bản xuất mới")}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex justify-center py-10">
            <LoadingSpinner />
          </div>
        ) : rows.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">
            {t("Chưa có bản xuất nào. Bấm \"Yêu cầu bản xuất mới\" để bắt đầu.")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2.5 text-left font-medium">{t("Yêu cầu lúc")}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t("Số mẫu")}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t("Dung lượng")}</th>
                  <th className="px-3 py-2.5 text-left font-medium">{t("Trạng thái")}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t("Thao tác")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.export_id} className="border-t border-slate-100">
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-500">
                      {new Date(r.created_at).toLocaleString("vi-VN")}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">
                      {r.sample_count ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">
                      {fmtBytes(r.size_bytes)}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant={toneForStatus(r.status)} size="sm">
                        {t(STATUS_LABEL[r.status])}
                      </Badge>
                      {r.status === "failed" && r.error && (
                        <p className="mt-0.5 text-xs text-red-600">{t("Bản xuất thất bại — hãy thử đặt lại.")}</p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {r.status === "ready" && (
                        <a
                          href={personalExportDownloadUrl(r.export_id)}
                          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium border ${toneClasses("success", "outline")}`}
                        >
                          <DownloadIcon className="h-3.5 w-3.5" aria-hidden="true" />
                          {t("Tải về")}
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
