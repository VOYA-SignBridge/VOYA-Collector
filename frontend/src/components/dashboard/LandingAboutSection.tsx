import { useI18n } from "../../i18n";
export default function LandingAboutSection() {
  const { t } = useI18n();

  return (
    <section className="relative py-16 sm:py-24">
      {/* Section Header */}
      <div className="text-center mb-12 sm:mb-16">
        <span className="inline-block px-4 py-1.5 rounded-full bg-ctu-blue/10 text-ctu-blue text-sm font-semibold mb-4 tracking-wide uppercase">
          {t("Về dự án")}
        </span>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
          {t("CTU.SignBridge là gì?")}
        </h2>
        <p className="text-lg sm:text-xl text-slate-600 max-w-3xl mx-auto leading-relaxed">
          {t("Một hệ sinh thái mở, kết nối công nghệ AI và cộng đồng để xây dựng tài nguyên Ngôn ngữ Ký hiệu Việt Nam (VSL) đầu tiên tại Việt Nam.")}
        </p>
      </div>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
        {/* Feature 1: Thu thập dữ liệu */}
        <div className="group relative bg-white rounded-3xl p-8 sm:p-10 border border-slate-200/60 shadow-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-ctu-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-ctu-blue to-ctu-navy flex items-center justify-center text-white mb-6 shadow-lg shadow-ctu-blue/25">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">{t("Thu thập dữ liệu cộng đồng")}</h3>
            <p className="text-slate-600 leading-relaxed">
              {t("Nền tảng cho phép người dùng đóng góp video ký hiệu dễ dàng thông qua webcam hoặc tải lên video có sẵn. Mỗi mẫu dữ liệu đều được gắn nhãn và xác thực tự động.")}
            </p>
          </div>
        </div>

        {/* Feature 2: AI nhận dạng */}
        <div className="group relative bg-white rounded-3xl p-8 sm:p-10 border border-slate-200/60 shadow-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-ctu-navy/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-ctu-navy to-ctu-navy-mid flex items-center justify-center text-white mb-6 shadow-lg shadow-ctu-navy/25">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">{t("Nhận dạng bằng AI")}</h3>
            <p className="text-slate-600 leading-relaxed">
              {t("Sử dụng mô hình Deep Learning (TCN) kết hợp MediaPipe để nhận dạng ký hiệu theo thời gian thực, hỗ trợ nhiều phương ngữ ký hiệu khác nhau.")}
            </p>
          </div>
        </div>

        {/* Feature 3: Mã nguồn mở */}
        <div className="group relative bg-white rounded-3xl p-8 sm:p-10 border border-slate-200/60 shadow-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-ctu-yellow/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-400 to-ctu-yellow flex items-center justify-center text-ctu-navy mb-6 shadow-lg shadow-ctu-yellow/25">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-3">{t("Nghiên cứu & Mã nguồn mở")}</h3>
            <p className="text-slate-600 leading-relaxed">
              {t("Dự án nghiên cứu khoa học tại Đại học Cần Thơ, hướng đến xây dựng bộ dữ liệu VSL chuẩn đầu tiên phục vụ cộng đồng và nghiên cứu.")}
            </p>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="mt-12 sm:mt-16 bg-gradient-to-r from-ctu-navy via-ctu-navy-mid to-ctu-blue rounded-3xl p-8 sm:p-12 text-white shadow-2xl shadow-ctu-navy/30">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <div className="text-3xl sm:text-4xl font-bold mb-1">AI</div>
            <div className="text-sm sm:text-base text-white/70">{t("Nhận dạng realtime")}</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-bold mb-1">VSL</div>
            <div className="text-sm sm:text-base text-white/70">{t("Ngôn ngữ ký hiệu VN")}</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-bold mb-1">CTU</div>
            <div className="text-sm sm:text-base text-white/70">{t("Đại học Cần Thơ")}</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-bold mb-1">{t("Mở")}</div>
            <div className="text-sm sm:text-base text-white/70">{t("Mã nguồn mở")}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
