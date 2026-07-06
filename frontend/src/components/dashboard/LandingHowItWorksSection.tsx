export default function LandingHowItWorksSection() {
  const steps = [
    {
      step: "01",
      title: "Đăng ký tài khoản",
      description: "Tạo tài khoản miễn phí để bắt đầu đóng góp và theo dõi tiến trình của bạn.",
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
    },
    {
      step: "02",
      title: "Ghi lại ký hiệu",
      description: "Sử dụng webcam để ghi lại các mẫu ngôn ngữ ký hiệu. Hệ thống hỗ trợ nhiều nhãn và phương ngữ.",
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      ),
    },
    {
      step: "03",
      title: "AI xử lý tự động",
      description: "MediaPipe trích xuất skeleton và TCN phân loại ký hiệu. Dữ liệu được tự động xử lý và xác thực.",
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
    },
    {
      step: "04",
      title: "Nhận dạng realtime",
      description: "Thử nghiệm nhận dạng ngôn ngữ ký hiệu theo thời gian thực với mô hình AI đã huấn luyện.",
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
    },
  ];

  return (
    <section className="py-16 sm:py-24">
      <div className="text-center mb-12 sm:mb-16">
        <span className="inline-block px-4 py-1.5 rounded-full bg-ctu-navy/10 text-ctu-navy text-sm font-semibold mb-4 tracking-wide uppercase">
          Quy trình
        </span>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
          Cách hoạt động
        </h2>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto">
          Chỉ cần 4 bước đơn giản để bắt đầu đóng góp cho cộng đồng người khiếm thính Việt Nam.
        </p>
      </div>

      <div className="relative">
        {/* Connection line */}
        <div className="hidden lg:block absolute top-10 left-[12%] right-[12%] h-0.5 bg-gradient-to-r from-ctu-blue via-ctu-navy to-ctu-blue opacity-20" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((item) => (
            <div key={item.step} className="relative text-center group">
              {/* Step number circle */}
              <div className="relative mx-auto mb-6 w-max">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-ctu-blue to-ctu-navy flex items-center justify-center text-white shadow-xl shadow-ctu-navy/20 group-hover:scale-110 transition-transform duration-300">
                  {item.icon}
                </div>
                <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-ctu-yellow text-ctu-navy font-bold text-sm flex items-center justify-center shadow-md">
                  {item.step}
                </div>
              </div>

              <h3 className="text-lg font-bold text-slate-900 mb-3">{item.title}</h3>
              <p className="text-sm text-slate-600 leading-relaxed max-w-xs mx-auto">
                {item.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
