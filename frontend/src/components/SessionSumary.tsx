import { useEffect, useMemo, useState } from "react";
import type { SessionStats } from "../types";
import { ChartBarIcon } from "./ui/Icons";

interface SessionSummaryProps {
  sessionId: string;
  stats: SessionStats;
  onClose: () => void;
}

export default function SessionSummary({ sessionId, stats, onClose }: SessionSummaryProps) {
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
        <h2 className="mb-3 flex items-center gap-2 text-xl font-bold sm:text-2xl"><ChartBarIcon className="h-5 w-5 text-ctu-blue" /> Tổng kết phiên thu</h2>
        <p className="text-gray-700 mb-1 break-all">
          <b>Session ID:</b> {sessionId}
        </p>
        <p className="text-gray-700 mb-1">
          <b>Total Samples:</b> {stats.totalSamples}
        </p>
        <p className="text-gray-700 mb-1">
          <b>Total Frames:</b> {stats.totalFrames}
        </p>
        <p className="text-gray-700 mb-4">
          <b>Average Frames per Sample:</b> {stats.avgFrames.toFixed(1)}
        </p>

        <h3 className="mb-2 text-sm font-semibold sm:text-base">Số mẫu theo từng nhãn</h3>
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
          <div className="h-full flex items-center justify-center text-center text-sm text-gray-500">Loading chart…</div>
        )}
        </div>

        <div className="mt-5 flex justify-end">
          <button className="w-full sm:w-auto bg-blue-600 text-white px-4 py-2 rounded" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
