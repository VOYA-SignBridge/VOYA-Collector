import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSamples } from "../../api/dataset";
import Button from "../ui/Button";
import {
  CameraIcon,
  ChipIcon,
  HeartIcon,
  MedalIcon,
  SparkleIcon,
  StarIcon,
  UploadIcon,
} from "../ui/Icons";
import type { Session } from "../../types";
import { useI18n } from "../../i18n";

interface MyContributionStats {
  totalSamples: number;
  sessionsCount: number;
  labels: string[];
  rank: number;
  totalContributors: number;
}

interface MyContributionSectionProps {
  username: string | null;
}

export default function MyContributionSection({ username }: MyContributionSectionProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [stats, setStats] = useState<MyContributionStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!username) {
      setLoading(false);
      return;
    }

    const fetchUserContribution = async () => {
      try {
        const samplesRes = await getSamples();
        if (samplesRes.ok) {
          const allSessions = samplesRes.data;

          // Calculate user's stats
          const userSessions = allSessions.filter((session: Session) => session.user === username);
          const userTotalSamples = userSessions.reduce(
            (sum: number, session: Session) => sum + session.samples_count,
            0
          );

          const labels: string[] = [];
          userSessions.forEach((session: Session) => {
            session.labels.forEach((label) => {
              if (!labels.includes(label)) {
                labels.push(label);
              }
            });
          });

          // Calculate user's rank (by contribution count)
          const contributionMap = new Map<string, number>();
          allSessions.forEach((session: Session) => {
            const current = contributionMap.get(session.user) || 0;
            contributionMap.set(session.user, current + session.samples_count);
          });

          const sortedContributors = Array.from(contributionMap.entries())
            .sort((a, b) => b[1] - a[1])
            .map(([user]) => user);

          const userRank = sortedContributors.indexOf(username) + 1;

          setStats({
            totalSamples: userTotalSamples,
            sessionsCount: userSessions.length,
            labels,
            rank: userRank,
            totalContributors: contributionMap.size,
          });
        } else {
          setStats({
            totalSamples: 0,
            sessionsCount: 0,
            labels: [],
            rank: 0,
            totalContributors: 0,
          });
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Error fetching user contribution:", error);
        setStats({
          totalSamples: 0,
          sessionsCount: 0,
          labels: [],
          rank: 0,
          totalContributors: 0,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchUserContribution();
  }, [username]);

  if (loading) {
    return <div className="h-48 bg-slate-100 rounded-2xl animate-pulse" />;
  }

  if (!username) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">{t("Tham gia cộng đồng")}</h2>
        <div className="bg-gradient-to-br from-ctu-blue/10 to-ctu-navy/5 rounded-2xl p-8 sm:p-10 border-2 border-ctu-blue/30 shadow-md">
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ctu-blue/10 text-ctu-blue">
                  <CameraIcon className="h-6 w-6" />
                </div>
                <p className="font-semibold text-slate-900">{t("Đóng góp dữ liệu VSL")}</p>
                <p className="text-sm text-slate-600 mt-2">{t("Ghi lại và tải lên mẫu Ngôn ngữ Ký hiệu Việt Nam")}</p>
              </div>
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ctu-navy/10 text-ctu-navy">
                  <ChipIcon className="h-6 w-6" />
                </div>
                <p className="font-semibold text-slate-900">{t("Hỗ trợ nghiên cứu AI")}</p>
                <p className="text-sm text-slate-600 mt-2">{t("Giúp cải thiện hệ thống nhận dạng tự động")}</p>
              </div>
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ctu-yellow/20 text-ctu-navy">
                  <HeartIcon className="h-6 w-6" />
                </div>
                <p className="font-semibold text-slate-900">{t("Hỗ trợ cộng đồng")}</p>
                <p className="text-sm text-slate-600 mt-2">{t("Cùng xây dựng tài nguyên cho người khiếm thính")}</p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
              <Button
                onClick={() => navigate("/login")}
                className="justify-center px-8 py-3 text-base font-semibold"
                variant="primary"
              >
                {t("Đăng nhập")}
              </Button>
              <Button
                onClick={() => navigate("/register")}
                className="justify-center px-8 py-3 text-base font-semibold"
                variant="ghost"
              >
                {t("Đăng ký tài khoản")}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  /** Hạng, vẽ bằng SVG.
   *
   * Ba hạng đầu dùng CHUNG một hình, khác nhau ở màu. Vàng/bạc/đồng vẽ bằng
   * ba emoji riêng thì trên máy thiếu phông màu chúng ra ba ô vuông giống
   * hệt nhau — mất sạch thứ tự hạng, đúng thứ duy nhất hình này để nói. */
  const rankMedal = (rank: number) => {
    if (rank === 1) return { Icon: MedalIcon, className: "text-amber-500" };
    if (rank === 2) return { Icon: MedalIcon, className: "text-slate-400" };
    if (rank === 3) return { Icon: MedalIcon, className: "text-orange-700" };
    if (rank <= 15) return { Icon: StarIcon, className: "text-sky-500" };
    return { Icon: SparkleIcon, className: "text-slate-400" };
  };

  const getRankText = (rank: number) => {
    if (rank === 1) return "Số 1 cộng tác viên";
    if (rank <= 15) return t("Top {rank} cộng tác viên", { rank });
    return "Cộng tác viên tích cực";
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">{t("Đóng góp của bạn")}</h2>

      {stats.totalSamples === 0 ? (
        <div className="bg-gradient-to-br from-ctu-blue/10 to-ctu-navy/5 rounded-2xl p-8 sm:p-12 border border-ctu-blue/30 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-ctu-blue/10 text-ctu-blue">
            <UploadIcon className="h-7 w-7" />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-2">{t("Hãy bắt đầu đóng góp!")}</p>
          <p className="text-slate-600 mb-6">
            {t("Bạn chưa có mẫu dữ liệu nào. Mỗi đóng góp giúp cải thiện hệ thống nhận dạng Ngôn ngữ Ký hiệu Việt Nam.")}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
            {/* Total Samples */}
            <div className="bg-gradient-to-br from-ctu-blue/10 to-blue-50 rounded-2xl p-6 sm:p-8 border border-ctu-blue/30 shadow-md">
              <div className="text-sm text-slate-600 mb-2 font-medium uppercase tracking-wider">{t("Mẫu Dữ Liệu")}</div>
              <div className="text-4xl sm:text-5xl font-bold text-ctu-blue mb-1">{stats.totalSamples}</div>
              <p className="text-sm text-slate-600">
                {t("Từ")} <strong>{stats.sessionsCount}</strong> {t("phiên ghi")}
              </p>
            </div>

            {/* Labels */}
            <div className="bg-gradient-to-br from-ctu-navy/10 to-slate-50 rounded-2xl p-6 sm:p-8 border border-ctu-navy/30 shadow-md">
              <div className="text-sm text-slate-600 mb-2 font-medium uppercase tracking-wider">{t("Nhãn Được Ghi")}</div>
              <div className="text-4xl sm:text-5xl font-bold text-ctu-navy mb-1">{stats.labels.length}</div>
              <p className="text-sm text-slate-600">{t("Loại ngôn ngữ ký hiệu")}</p>
            </div>

            {/* Rank */}
            <div className="bg-gradient-to-br from-ctu-yellow/20 to-amber-50 rounded-2xl p-6 sm:p-8 border border-ctu-yellow/40 shadow-md">
              <div className="text-sm text-slate-600 mb-2 font-medium uppercase tracking-wider">{t("Xếp Hạng")}</div>
              <div className="text-3xl sm:text-4xl font-bold mb-2 text-ctu-navy">
                {(() => {
                  const { Icon, className } = rankMedal(stats.rank);
                  return <Icon className={`inline h-4 w-4 -mt-0.5 ${className}`} aria-hidden="true" />;
                })()}{" "}
                {stats.rank}/{stats.totalContributors}
              </div>
              <p className="text-sm text-slate-600 font-semibold text-ctu-navy">{getRankText(stats.rank)}</p>
            </div>
          </div>

          {/* Labels Contributed */}
          {stats.labels.length > 0 && (
            <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-md">
              <p className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-4">
                {t("Các nhãn bạn đã đóng góp")}
              </p>
              <div className="flex flex-wrap gap-2 sm:gap-3">
                {stats.labels.slice(0, 12).map((label) => (
                  <span
                    key={label}
                    className="inline-flex items-center rounded-full bg-ctu-blue/10 px-4 py-2 text-sm font-medium text-ctu-blue border border-ctu-blue/30"
                  >
                    {label}
                  </span>
                ))}
                {stats.labels.length > 12 && (
                  <span className="inline-flex items-center rounded-full bg-slate-50 px-4 py-2 text-sm font-medium text-slate-600 border border-slate-200">
                    +{stats.labels.length - 12} nhãn khác
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
