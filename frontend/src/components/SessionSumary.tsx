import { useEffect, useMemo, useState } from "react";
import type { SessionStats } from "../types";

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
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4">
      <div className="bg-white p-6 rounded-lg w-full max-w-[700px] max-h-[85vh] overflow-y-auto shadow-lg">
        <h2 className="text-2xl font-bold mb-3">📊 Session Summary</h2>
        <p className="text-gray-700 mb-1">
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

        <h3 className="font-semibold mb-2">📈 Samples per Label</h3>
        {Recharts ? (
          <Recharts.ResponsiveContainer width="100%" height={250}>
            <Recharts.BarChart data={chartData}>
              <Recharts.CartesianGrid strokeDasharray="3 3" />
              <Recharts.XAxis dataKey="label" />
              <Recharts.YAxis />
              <Recharts.Tooltip />
              <Recharts.Bar dataKey="count" fill="#3b82f6" />
            </Recharts.BarChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div className="p-8 text-center">Loading chart…</div>
        )}

        <button className="mt-5 bg-blue-600 text-white px-4 py-2 rounded" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
