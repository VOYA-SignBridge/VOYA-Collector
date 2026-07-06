import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSamples } from "../../api/dataset";
import type { Session } from "../../types";
import Button from "../ui/Button";

interface HeroSectionProps {
  username: string | null;
}

export default function HeroSection({ username }: HeroSectionProps) {
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
    <div className="relative bg-gradient-to-br from-ctu-blue/5 via-white to-ctu-navy/5 rounded-3xl px-6 py-12 sm:px-8 sm:py-16 lg:px-12 lg:py-20 border border-slate-100/50 shadow-lg overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-ctu-blue/10 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-ctu-navy/10 rounded-full blur-3xl -z-10" />

      <div className="relative z-10 max-w-3xl">
        {username ? (
          <>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4">
              <span className="bg-gradient-to-r from-ctu-navy via-ctu-navy-mid to-ctu-blue bg-clip-text text-transparent">Xin chào, {username}!</span> 👋
            </h1>

            <div className="mb-8 space-y-3">
              <p className="text-lg sm:text-xl font-semibold text-slate-900">
                {loading ? (
                  <span className="text-slate-400">Đang tính toán đóng góp của bạn...</span>
                ) : (
                  <>
                    Bạn đã đóng góp <span className="text-ctu-blue">{userSamples.toLocaleString()}</span> mẫu cho cộng đồng.
                  </>
                )}
              </p>
              <p className="text-base sm:text-lg text-slate-600 leading-relaxed">
                Mỗi mẫu dữ liệu giúp cải thiện hệ thống nhận dạng Ngôn ngữ Ký hiệu Việt Nam.
                <br />
                <strong>Tác động của bạn là có thật.</strong>
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 sm:gap-3">
              <Button
                onClick={() => navigate("/upload")}
                className="justify-center px-6 py-3 sm:px-8 text-base font-semibold"
                variant="primary"
              >
                Đóng góp thêm dữ liệu →
              </Button>
              <Button
                onClick={() => navigate("/realtime")}
                className="justify-center px-6 py-3 sm:px-8 text-base font-semibold"
                variant="ghost"
              >
                Thử nhận dạng
              </Button>
            </div>
          </>
        ) : (
          <>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4">
              <span className="bg-gradient-to-r from-ctu-navy via-ctu-navy-mid to-ctu-blue bg-clip-text text-transparent">Xin chào</span> 👋
            </h1>

            <div className="mb-8 space-y-3">
              <p className="text-lg sm:text-xl font-semibold text-slate-900">
                Khám phá CTU.SignBridge
              </p>
              <p className="text-base sm:text-lg text-slate-600 leading-relaxed">
                Cùng xây dựng cộng đồng Ngôn ngữ Ký hiệu Việt Nam thông qua công nghệ nhận dạng AI.
                <br />
                <strong>Mỗi đóng góp đều quan trọng.</strong>
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 sm:gap-3">
              <Button
                onClick={() => navigate("/realtime")}
                className="justify-center px-6 py-3 sm:px-8 text-base font-semibold"
                variant="primary"
              >
                Thử nhận dạng ngay →
              </Button>
              <Button
                onClick={() => navigate("/register")}
                className="justify-center px-6 py-3 sm:px-8 text-base font-semibold"
                variant="ghost"
              >
                Đăng ký đóng góp
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
