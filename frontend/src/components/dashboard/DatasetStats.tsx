import { useEffect, useMemo, useState } from "react";
import type { Session } from "../../types";

const COLORS = ["#60a5fa", "#f59e0b", "#34d399", "#f87171", "#a78bfa"];

export default function DatasetStats({ sessions }: { sessions: Session[] }) {
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

  const { labelCount, userCount } = useMemo(() => {
    const lc: Record<string, number> = {};
    const uc: Record<string, number> = {};
    sessions.forEach((s: Session) => {
      (s.labels || []).forEach((l: string) => (lc[l] = (lc[l] || 0) + 1));
      uc[s.user] = (uc[s.user] || 0) + 1;
    });
    return { labelCount: lc, userCount: uc };
  }, [sessions]);

  const labelData = useMemo(() => Object.entries(labelCount).map(([name, value]) => ({ name, value })), [labelCount]);
  const userData = useMemo(() => Object.entries(userCount).map(([name, value]) => ({ name, value })), [userCount]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      <div className="bg-white border rounded-lg p-4 shadow-sm">
        <h3 className="font-semibold mb-3">📈 Distribution by Label</h3>
        {Recharts ? (
          <Recharts.ResponsiveContainer width="100%" height={250}>
            <Recharts.PieChart>
              <Recharts.Pie data={labelData} dataKey="value" nameKey="name" label>
                {labelData.map((_, i) => (
                  <Recharts.Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Recharts.Pie>
              <Recharts.Tooltip />
            </Recharts.PieChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div className="p-8 text-center">Loading chart…</div>
        )}
      </div>

      <div className="bg-white border rounded-lg p-4 shadow-sm">
        <h3 className="font-semibold mb-3">👥 Active Users</h3>
        {Recharts ? (
          <Recharts.ResponsiveContainer width="100%" height={250}>
            <Recharts.BarChart data={userData}>
              <Recharts.XAxis dataKey="name" />
              <Recharts.YAxis />
              <Recharts.Tooltip />
              <Recharts.Bar dataKey="value" fill="#60a5fa" />
            </Recharts.BarChart>
          </Recharts.ResponsiveContainer>
        ) : (
          <div className="p-8 text-center">Loading chart…</div>
        )}
      </div>
    </div>
  );
}
