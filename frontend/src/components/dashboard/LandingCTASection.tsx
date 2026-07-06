import { useNavigate } from "react-router-dom";
import Button from "../ui/Button";

export default function LandingCTASection() {
  const navigate = useNavigate();

  return (
    <section className="py-16 sm:py-24">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-ctu-navy via-ctu-navy-mid to-ctu-blue p-10 sm:p-16 lg:p-20 text-center shadow-2xl shadow-ctu-navy/30">
        {/* Background decorations */}
        <div className="absolute top-0 left-0 w-72 h-72 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-ctu-yellow/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border border-white/5 rounded-full" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] border border-white/5 rounded-full" />

        <div className="relative z-10">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-6 leading-tight">
            Sẵn sàng đóng góp cho
            <br />
            <span className="text-ctu-yellow">cộng đồng người khiếm thính?</span>
          </h2>
          <p className="text-lg sm:text-xl text-white/80 mb-10 max-w-2xl mx-auto leading-relaxed">
            Hàng triệu người khiếm thính tại Việt Nam cần sự hỗ trợ của bạn.
            Mỗi mẫu dữ liệu bạn đóng góp giúp AI hiểu tốt hơn Ngôn ngữ Ký hiệu Việt Nam.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              onClick={() => navigate("/register")}
              className="justify-center px-8 py-4 text-lg font-bold bg-ctu-yellow hover:bg-amber-400 text-ctu-navy shadow-xl hover:shadow-2xl transition-all hover:-translate-y-0.5"
            >
              Bắt đầu ngay — Miễn phí →
            </Button>
            <Button
              onClick={() => navigate("/realtime")}
              variant="ghost"
              className="justify-center px-8 py-4 text-lg font-bold text-white border-2 border-white/30 hover:bg-white/10 hover:border-white/50"
            >
              Thử nhận dạng trước
            </Button>
          </div>

          <p className="mt-6 text-sm text-white/50">
            Không cần cài đặt • Hoàn toàn miễn phí • Dữ liệu được bảo mật
          </p>
        </div>
      </div>
    </section>
  );
}
