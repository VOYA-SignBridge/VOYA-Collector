import { useEffect, useMemo, useState } from "react";
import type { SessionStats } from "../types";
import { useI18n } from "../i18n";

interface SessionSummaryProps {
  sessionId: string;
  stats: SessionStats;
  onClose: () => void;
}

export default function SessionSummary({ sessionId, stats, onClose }: SessionSummaryProps) {
  const { t } = useI18n();
  const [Recharts, setRecharts] = useState<typeof import("recharts") | null>(null);

  useEffect(() => {
    let mounted = true;
    import("recharts").then((mod) => {
      if (mounted) setRecharts(mod);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const chartData = useMemo(
    () => Object.entries(stats.labelsCount).map(([label, count]) => ({ label, count })),
    [stats.labelsCount]
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white p-4 sm:p-6 rounded-lg w-full max-w-[calc(100vw-1.5rem)] sm:max-w-3xl max-h-[calc(100dvh-1.5rem)] sm:max-h-[85vh] overflow-y-auto shadow-lg">
        <h2 className="text-xl sm:text-2xl font-bold mb-3">{t("Tổng kết phiên thu")}</h2>
        <p className="text-gray-700 mb-1 break-all">
          <b>{t("Mã phiên:")}</b> {sessionId}
        </p>
        <p className="text-gray-700 mb-1">
          <b>{t("Tổng số mẫu:")}</b> {stats.totalSamples}
        </p>
        <p className="text-gray-700 mb-1">
          <b>{t("Tổng khung hình:")}</b> {stats.totalFrames}
        </p>
        <p className="text-gray-700 mb-4">
          <b>{t("Khung hình trung bình mỗi mẫu:")}</b> {stats.avgFrames.toFixed(1)}
        </p>

        <h3 className="font-semibold mb-2 text-sm sm:text-base">{t("Số mẫu theo từng nhãn")}</h3>
        <div className="h-[220px] sm:h-[250px]">
        {Recharts ? (
          <Recharts.ResponsiveContainer width="100%" height="100%">
            <Recharts.BarChart data={chartData}>
              <Recharts.CartesianGrid strokeDasharray="3 3" />
              <Recharts.XAxis dataKey="label" />
              <Recharts.YAxis />
              <Recharts.Tooltip />
              <Recharts.Bar dataKey="count" fill="#3b82f6" />
            </Recharts.BarChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-center text-sm text-gray-500">{t("Đang tải biểu đồ…")}</div>
        )}
        </div>

        <div className="mt-5 flex justify-end">
          <button className="w-full sm:w-auto bg-blue-600 text-white px-4 py-2 rounded" onClick={onClose}>
            {t("Đóng")}
          </button>
        </div>
      </div>
    </div>
  );
}
