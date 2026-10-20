import { useState, useEffect } from "react";
import apiClient from "../api/axiosClient";
import { XIcon, CheckIcon, CloudIcon } from "./ui/Icons";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";

interface SyncGDriveModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SyncStatus {
  state: string;
  current: number;
  total: number;
  downloaded: number;
  skipped: number;
  errors: number;
  status?: string;
}

export default function SyncGDriveModal({ isOpen, onClose }: SyncGDriveModalProps) {
  const { t } = useI18n();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      startSync();
    } else {
      setTaskId(null);
      setStatus(null);
      setError(null);
    }
  }, [isOpen]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    
    if (taskId && status?.state !== "SUCCESS" && status?.state !== "FAILURE") {
      interval = setInterval(async () => {
        try {
          const res = await apiClient.get<SyncStatus>(`/api/v1/admin/sync-status/${taskId}`);
          setStatus(res.data);
          
          if (res.data.state === "SUCCESS" || res.data.state === "FAILURE") {
            clearInterval(interval);
          }
        } catch (err: any) {
          setError(friendlyError(err, t("Lỗi khi lấy trạng thái đồng bộ")));
          clearInterval(interval);
        }
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [taskId, status?.state]);

  const startSync = async () => {
    try {
      setStatus(null);
      setError(null);
      const res = await apiClient.post("/api/v1/admin/sync-local");
      setTaskId(res.data.task_id);
    } catch (err: any) {
      setError(friendlyError(err, t("Lỗi khi khởi chạy tiến trình đồng bộ")));
    }
  };

  if (!isOpen) return null;

  const getPercentage = () => {
    if (!status || status.total === 0) return 0;
    return Math.min(Math.round((status.current / status.total) * 100), 100);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <CloudIcon className="inline h-5 w-5 mr-1.5 -mt-0.5"  aria-hidden="true" /> {t("Đồng bộ Google Drive")}
          </h3>
          {(status?.state === "SUCCESS" || status?.state === "FAILURE" || error) && (
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
            >
              <XIcon className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto">
          {error ? (
            <div className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-100">
              <strong>{t("Lỗi:")}</strong> {error}
            </div>
          ) : !status ? (
            <div className="text-center py-8">
              <div className="w-10 h-10 border-4 border-ctu-blue border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-slate-600 font-medium">{t("Đang khởi tạo tiến trình...")}</p>
            </div>
          ) : (
            <div className="space-y-6">
              
              {/* Status Header */}
              <div className="text-center">
                {status.state === "PENDING" && <p className="text-amber-600 font-semibold text-lg animate-pulse">{t("Đang chuẩn bị dữ liệu...")}</p>}
                {status.state === "PROGRESS" && <p className="text-ctu-blue font-semibold text-lg">{t("Đang tiến hành đồng bộ...")}</p>}
                {status.state === "SUCCESS" && <p className="text-sky-700 font-bold text-xl flex justify-center items-center gap-2"><CheckIcon className="w-6 h-6" /> {t("Đồng bộ hoàn tất!")}</p>}
                {status.state === "FAILURE" && (
                  <p className="text-rose-600 font-bold text-lg">
                    {t("Đồng bộ thất bại: {chi_tiet}", { chi_tiet: status.status ?? "" })}
                  </p>
                )}
              </div>

              {/* Progress Bar */}
              {(status.state === "PROGRESS" || status.state === "SUCCESS") && (
                <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100 shadow-inner">
                  <div className="flex justify-between text-sm font-medium mb-2 text-slate-700">
                    <span>{t("Tiến độ kiểm tra & tải file")}</span>
                    <span className={status.state === "SUCCESS" ? "text-sky-700" : "text-ctu-blue"}>{getPercentage()}%</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-3 mb-2 overflow-hidden">
                    <div 
                      className={`h-3 rounded-full transition-all duration-300 ease-out ${status.state === "SUCCESS" ? "bg-sky-600" : "bg-ctu-blue"}`}
                      style={{ width: `${getPercentage()}%` }}
                    ></div>
                  </div>
                  <p className="text-xs text-slate-500 text-center">
                    {t("Đã xử lý:")} <span className="font-semibold text-slate-700">{status.current}</span> / <span className="font-semibold text-slate-700">{status.total}</span> file
                  </p>
                </div>
              )}

              {/* Results Table */}
              {(status.state === "PROGRESS" || status.state === "SUCCESS") && (
                <div className="mt-4 border border-slate-100 rounded-xl overflow-hidden">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-700 border-b border-slate-100">
                      <tr>
                        <th className="px-4 py-3 font-semibold">{t("Thống kê kết quả")}</th>
                        <th className="px-4 py-3 font-semibold text-right">{t("Số lượng")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      <tr className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-4 py-3 text-slate-700 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-sky-600"></span>
                          {t("Tải về thành công")}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-sky-700">{status.downloaded}</td>
                      </tr>
                      <tr className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-4 py-3 text-slate-700 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                          {t("Bỏ qua (đã có sẵn)")}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-slate-600">{status.skipped}</td>
                      </tr>
                      <tr className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-4 py-3 text-slate-700 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                          {t("Lỗi tải file")}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-rose-600">{status.errors}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            disabled={status?.state === "PROGRESS" || status?.state === "PENDING" || (!status && !error)}
            className="px-6 py-2 bg-slate-200 text-slate-700 rounded-lg font-semibold hover:bg-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t("Đóng")}
          </button>
        </div>

      </div>
    </div>
  );
}
