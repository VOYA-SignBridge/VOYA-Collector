import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSamples } from "../../api/dataset";
import type { Session } from "../../types";
import { useI18n } from "../../i18n";

interface HeroSectionProps {
  username: string | null;
}

// Khung chào nằm trên nền NAVY CTU, cùng tông với thanh bên (18/10/2026). Hai nút
// không dùng `Button`: `.btn-primary`/`.btn-ghost` viết ngoài layer của Tailwind
// v4 nên luôn thắng class ghi đè, và nút "ghost" chữ xanh CTU trên nền navy thì
// không đủ tương phản.
const CTA_PRIMARY =
  "inline-flex items-center justify-center rounded-lg bg-white px-6 py-3 sm:px-8 text-base font-semibold text-ctu-navy shadow-md transition-colors hover:bg-blue-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-ctu-navy";
const CTA_SECONDARY =
  "inline-flex items-center justify-center rounded-lg border border-white/40 px-6 py-3 sm:px-8 text-base font-semibold text-white transition-colors hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-ctu-navy";

export default function HeroSection({ username }: HeroSectionProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [userSamples, setUserSamples] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!username) {
      setLoading(false);
      return;
    }

    const fetchUserSamples = async () => {
      try {
        const samplesRes = await getSamples();
        if (samplesRes.ok) {
          const userTotal = samplesRes.data
            .filter((session: Session) => session.user === username)
            .reduce((sum: number, session: Session) => sum + session.samples_count, 0);
          setUserSamples(userTotal);
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Error fetching user samples:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchUserSamples();
  }, [username]);

  return (
    <div className="relative isolate bg-gradient-to-br from-ctu-navy via-ctu-navy-mid to-ctu-blue rounded-3xl px-6 py-12 sm:px-8 sm:py-16 lg:px-12 lg:py-20 shadow-lg overflow-hidden text-white">
      {/* Background decoration */}
      <div className="absolute -top-24 -right-24 w-96 h-96 bg-ctu-blue-light/25 rounded-full blur-3xl -z-10" aria-hidden="true" />
      <div className="absolute -bottom-32 left-1/3 w-96 h-96 bg-white/10 rounded-full blur-3xl -z-10" aria-hidden="true" />

      <div className="relative z-10 max-w-3xl">
        {username ? (
          <>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4">
              {t("Xin chào, {ten}!", { ten: username })}
            </h1>

            <div className="mb-8 space-y-3">
              <p className="text-lg sm:text-xl font-semibold text-white">
                {loading ? (
                  <span className="text-blue-100/80">{t("Đang tính toán đóng góp của bạn...")}</span>
                ) : (
                  <>
                    {t("Bạn đã đóng góp")} <span className="text-ctu-blue-light">{userSamples.toLocaleString()}</span> {t("mẫu cho cộng đồng.")}
                  </>
                )}
              </p>
              <p className="text-base sm:text-lg text-blue-100/90 leading-relaxed">
                {t("Mỗi mẫu dữ liệu giúp cải thiện hệ thống nhận dạng Ngôn ngữ Ký hiệu Việt Nam.")}
                <br />
                <strong>{t("Tác động của bạn là có thật.")}</strong>
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 sm:gap-3">
              <button type="button" onClick={() => navigate("/upload")} className={CTA_PRIMARY}>
                {t("Đóng góp thêm dữ liệu →")}
              </button>
              <button type="button" onClick={() => navigate("/realtime")} className={CTA_SECONDARY}>
                {t("Thử nhận dạng")}
              </button>
            </div>
          </>
        ) : (
          <>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4">
              {t("Xin chào")}
            </h1>

            <div className="mb-8 space-y-3">
              <p className="text-lg sm:text-xl font-semibold text-white">
                {t("Khám phá CTU.SignBridge")}
              </p>
              <p className="text-base sm:text-lg text-blue-100/90 leading-relaxed">
                {t("Cùng xây dựng cộng đồng Ngôn ngữ Ký hiệu Việt Nam thông qua công nghệ nhận dạng AI.")}
                <br />
                <strong>{t("Mỗi đóng góp đều quan trọng.")}</strong>
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 sm:gap-3">
              <button type="button" onClick={() => navigate("/realtime")} className={CTA_PRIMARY}>
                {t("Thử nhận dạng ngay →")}
              </button>
              <button type="button" onClick={() => navigate("/register")} className={CTA_SECONDARY}>
                {t("Đăng ký đóng góp")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
