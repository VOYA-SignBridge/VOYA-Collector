import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { getCommunityStats } from "../../api/dataset";
import { FolderIcon, GlobeIcon, TagIcon, UsersIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

interface StatItem {
  label: string;
  value: number;
  description: string;
  icon: ReactNode;
}

export default function CommunityStatsSection() {
  const { t } = useI18n();
  const [stats, setStats] = useState<StatItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        // One server-aggregated request instead of downloading the full class
        // list + every session and reducing them here on the main thread.
        const s = await getCommunityStats();

        const newStats: StatItem[] = [
          {
            label: t("nhãn"),
            value: s.labels_count,
            description: t("Ngôn ngữ ký hiệu được ghi nhận"),
            icon: <TagIcon className="h-8 w-8 sm:h-9 sm:w-9" />,
          },
          {
            label: t("mẫu"),
            value: s.total_samples,
            description: t("Video hoặc ghi hình được tải lên"),
            icon: <FolderIcon className="h-8 w-8 sm:h-9 sm:w-9" />,
          },
          {
            label: t("người đóng góp"),
            value: s.contributors_count,
            description: t("Thành viên cộng đồng hoạt động"),
            icon: <UsersIcon className="h-8 w-8 sm:h-9 sm:w-9" />,
          },
          {
            label: t("khu vực/phương ngữ"),
            value: s.regions_count,
            description: t("Vùng lãnh thổ được đại diện"),
            icon: <GlobeIcon className="h-8 w-8 sm:h-9 sm:w-9" />,
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
      <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">{t("Cộng đồng của chúng ta")}</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-md hover:shadow-lg transition-all duration-200 text-center"
          >
            <div className="mb-3 flex justify-center text-ctu-blue">{stat.icon}</div>
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
          <strong>{t("Đang phát triển bởi")}</strong>
          <br />
          <span className="text-ctu-blue font-semibold">{t("Đại học Cần Thơ (CTU)")}</span>
          <br />
          <span className="text-xs text-slate-500 mt-1 block">{t("Vì một cộng đồng giao tiếp không rào cản")}</span>
        </p>
      </div>
    </div>
  );
}
