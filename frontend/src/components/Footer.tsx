import { useNavigate } from "react-router-dom";

export default function Footer() {
  const navigate = useNavigate();

  const quickLinks = [
    { name: "Trang chủ", href: "/" },
    { name: "Nhận dạng realtime", href: "/realtime" },
    { name: "Đăng nhập", href: "/login" },
    { name: "Đăng ký", href: "/register" },
  ];

  const projectLinks = [
    { name: "Đóng góp dữ liệu", href: "/upload" },
    { name: "Thư viện nhãn", href: "/labels" },
    { name: "Huấn luyện model", href: "/training" },
  ];

  return (
    <footer className="bg-gradient-to-b from-slate-900 to-slate-950 text-white">
      {/* Main footer */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-12">
          {/* Brand Column */}
          <div className="lg:col-span-1">
            <div className="flex items-center gap-3 mb-5 cursor-pointer" onClick={() => navigate("/")}>
              <img src="logo.png" alt="CTU.SignBridge" className="h-12 w-12 object-contain" />
              <div>
                <div className="text-xl font-bold">
                  <span className="text-ctu-blue">CTU</span>
                  <span className="text-blue-300">.SignBridge</span>
                </div>
                <div className="text-xs text-slate-400">Đại học Cần Thơ</div>
              </div>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed mb-6">
              Nền tảng thu thập và nhận dạng Ngôn ngữ Ký hiệu Việt Nam (VSL)
              sử dụng công nghệ AI, phục vụ nghiên cứu và cộng đồng.
            </p>
            {/* Social / University links */}
            <div className="flex items-center gap-3">
              <a
                href="https://www.ctu.edu.vn"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs text-slate-300 hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
                ctu.edu.vn
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4">
              Truy cập nhanh
            </h3>
            <ul className="space-y-3">
              {quickLinks.map((link) => (
                <li key={link.href}>
                  <button
                    onClick={() => navigate(link.href)}
                    className="text-sm text-slate-400 hover:text-white transition-colors inline-flex items-center gap-2 group"
                  >
                    <span className="w-1 h-1 rounded-full bg-ctu-blue opacity-0 group-hover:opacity-100 transition-opacity" />
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Project Links */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4">
              Dự án
            </h3>
            <ul className="space-y-3">
              {projectLinks.map((link) => (
                <li key={link.href}>
                  <button
                    onClick={() => navigate(link.href)}
                    className="text-sm text-slate-400 hover:text-white transition-colors inline-flex items-center gap-2 group"
                  >
                    <span className="w-1 h-1 rounded-full bg-ctu-blue opacity-0 group-hover:opacity-100 transition-opacity" />
                    {link.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact / University Info */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4">
              Liên hệ
            </h3>
            <ul className="space-y-3 text-sm text-slate-400">
              <li className="flex items-start gap-3">
                <svg className="w-5 h-5 text-ctu-blue shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
                <span>Dự án nghiên cứu khoa học - Trường Công nghệ Thông tin và Truyền thông, Đại học Cần Thơ</span>
              </li>
              <li className="flex items-start gap-3">
                <svg className="w-5 h-5 text-ctu-blue shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span>Khu II, Đ. 3/2, Xuân Khánh, Ninh Kiều, Cần Thơ</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-center justify-center gap-4">
          <p className="text-sm text-slate-500 text-center">
            Dự án nghiên cứu khoa học - Trường Công nghệ Thông tin và Truyền thông
          </p>
        </div>
      </div>
    </footer>
  );
}
