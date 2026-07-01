import { useNavigate } from "react-router-dom";

interface ActionCard {
  title: string;
  description: string;
  href: string;
  icon: string;
  color: "indigo" | "violet" | "cyan";
  highlight?: string;
}

export default function QuickActionsSection() {
  const navigate = useNavigate();

  const actions: ActionCard[] = [
    {
      title: "Đóng góp dữ liệu",
      icon: "📤",
      description: "Ghi lại các mẫu ngôn ngữ ký hiệu và tải lên hệ thống",
      highlight: "Tạo ra tác động",
      href: "/upload",
      color: "indigo",
    },
    {
      title: "Thư viện nhãn",
      icon: "🏷️",
      description: "Quản lý và tổ chức các nhãn ký hiệu trong cộng đồng",
      highlight: "Khám phá & quản lý",
      href: "/labels",
      color: "violet",
    },
    {
      title: "Nhận dạng realtime",
      icon: "🖐️",
      description: "Kiểm tra các mô hình nhận dạng trực tiếp trong thời gian thực",
      highlight: "Thử nghiệm ngay",
      href: "/realtime",
      color: "cyan",
    },
  ];

  const colorClasses = {
    indigo: "from-indigo-50 via-white to-blue-50 border-indigo-200 hover:shadow-indigo-200/60",
    violet: "from-violet-50 via-white to-purple-50 border-violet-200 hover:shadow-violet-200/60",
    cyan: "from-cyan-50 via-white to-sky-50 border-cyan-200 hover:shadow-cyan-200/60",
  };

  const iconBgClasses = {
    indigo: "bg-indigo-100 text-indigo-700",
    violet: "bg-violet-100 text-violet-700",
    cyan: "bg-cyan-100 text-cyan-700",
  };

  const textColorClasses = {
    indigo: "text-indigo-900",
    violet: "text-violet-900",
    cyan: "text-cyan-900",
  };

  const buttonColorClasses = {
    indigo: "bg-indigo-600 hover:bg-indigo-700 text-white",
    violet: "bg-violet-600 hover:bg-violet-700 text-white",
    cyan: "bg-cyan-600 hover:bg-cyan-700 text-white",
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">Truy cập nhanh</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
        {actions.map((action) => (
          <button
            key={action.href}
            onClick={() => navigate(action.href)}
            className={`group bg-gradient-to-br ${colorClasses[action.color]} border-2 rounded-2xl p-8 sm:p-10 text-left transition-all duration-300 hover:shadow-2xl hover:-translate-y-2 active:translate-y-0`}
          >
            <div
              className={`inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5 ${iconBgClasses[action.color]} text-2xl transition-transform group-hover:scale-110 group-hover:rotate-6`}
            >
              {action.icon}
            </div>

            <h3 className={`text-2xl sm:text-3xl font-bold mb-3 ${textColorClasses[action.color]}`}>
              {action.title}
            </h3>

            <p className="text-sm sm:text-base text-slate-600 mb-6 leading-relaxed">{action.description}</p>

            <div className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg ${buttonColorClasses[action.color]} font-semibold text-sm sm:text-base transition-all group-hover:gap-3`}>
              {action.highlight}
              <svg className="w-5 h-5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
