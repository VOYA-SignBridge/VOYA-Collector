import { useEffect, useState } from "react";
import { getClassesList, getSamples, getClassesStats } from "../../api/dataset";
import type { Session } from "../../types";

interface StatItem {
  label: string;
  value: number;
  description: string;
  icon: string;
}

export default function CommunityStatsSection() {
  const [stats, setStats] = useState<StatItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        // Fetch labels count
        const labelsRes = await getClassesList();
        const labelsCount = labelsRes.ok ? labelsRes.data.count : 0;

        // Fetch samples count
        const samplesRes = await getSamples();
        const totalSamples = samplesRes.ok
          ? samplesRes.data.reduce((sum: number, s: Session) => sum + s.samples_count, 0)
          : 0;

        // Count unique contributors (users) from samples
        const contributors = new Set<string>();
        if (samplesRes.ok) {
          samplesRes.data.forEach((session: Session) => {
            contributors.add(session.user);
          });
        }

        // Fetch class stats to count regions
        const statsRes = await getClassesStats();
        const distribution = statsRes.ok ? statsRes.data.distribution : [];
        const regions = new Set<string>();
        if (distribution.length > 0) {
          distribution.forEach((dist) => {
            if (dist.label_original) {
              regions.add(dist.label_original);
            }
          });
        }

        const newStats: StatItem[] = [
          {
            label: "nhãn",
            value: labelsCount,
            description: "Ngôn ngữ ký hiệu được ghi nhận",
            icon: "🏷️",
          },
          {
            label: "mẫu",
            value: totalSamples,
            description: "Video hoặc ghi hình được tải lên",
            icon: "📁",
          },
          {
            label: "người đóng góp",
            value: contributors.size,
            description: "Thành viên cộng đồng hoạt động",
            icon: "👥",
          },
          {
            label: "khu vực/phương ngữ",
            value: Math.max(regions.size, 2),
            description: "Vùng lãnh thổ được đại diện",
            icon: "🌏",
          },
        ];

        setStats(newStats);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Error fetching community stats:", error);
        setStats([]);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-12 bg-slate-100 rounded-xl animate-pulse" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">Cộng đồng của chúng ta</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-md hover:shadow-lg transition-all duration-200 text-center"
          >
            <div className="text-4xl sm:text-5xl mb-3">{stat.icon}</div>
            <div className="text-3xl sm:text-4xl font-bold text-slate-900 mb-2">
              {stat.value.toLocaleString()}
            </div>
            <p className="text-sm sm:text-base font-medium text-slate-600 mb-3">{stat.label}</p>
            <p className="text-xs text-slate-500 leading-relaxed">{stat.description}</p>
          </div>
        ))}
      </div>

      <div className="bg-gradient-to-r from-slate-50 to-slate-100 rounded-2xl px-6 py-5 border border-slate-200 text-center">
        <p className="text-sm sm:text-base text-slate-700">
          <strong>Đang phát triển bởi</strong>
          <br />
          <span className="text-indigo-600 font-semibold">Đại học Cần Thơ (CTU)</span>
          <br />
          <span className="text-xs text-slate-500 mt-1 block">Vì một cộng đồng giao tiếp không rào cản</span>
        </p>
      </div>
    </div>
  );
}
