import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { HandIcon, TagIcon, UploadIcon, UsersIcon, DatabaseIcon } from "../ui/Icons";
import { useAuth } from "../../hooks/useAuth";
import SyncGDriveModal from "../SyncGDriveModal";

interface ActionCard {
  title: string;
  description: string;
  href?: string;
  onClick?: () => void;
  icon: ReactNode;
  color: "blue" | "navy" | "gold" | "red" | "green";
  highlight?: string;
}

export default function QuickActionsSection() {
  const navigate = useNavigate();
  // Lấy từ AuthProvider thay vì tự gọi /auth/me. Trước đây mỗi lần vào trang
  // chủ có tới ba lời gọi song song (provider + component này + CaptureCamera),
  // và thẻ dành cho admin ở đây xuất hiện trễ hơn phần còn lại một nhịp.
  const { user } = useAuth();
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);

  const handleSyncLocal = () => {
    setIsSyncModalOpen(true);
  };

  const baseActions: ActionCard[] = [
    {
      title: "Đóng góp dữ liệu",
      icon: <UploadIcon className="h-7 w-7" />,
      description: "Ghi lại các mẫu ngôn ngữ ký hiệu và tải lên hệ thống",
      highlight: "Tạo ra tác động",
      href: "/upload",
      color: "blue",
    },
    {
      title: "Thư viện nhãn",
      icon: <TagIcon className="h-7 w-7" />,
      description: "Quản lý và tổ chức các nhãn ký hiệu trong cộng đồng",
      highlight: "Khám phá & quản lý",
      href: "/labels",
      color: "navy",
    },
    {
      title: "Nhận dạng realtime",
      icon: <HandIcon className="h-7 w-7" />,
      description: "Kiểm tra các mô hình nhận dạng trực tiếp trong thời gian thực",
      highlight: "Thử nghiệm ngay",
      href: "/realtime",
      color: "gold",
    },
  ];

  const adminActions: ActionCard[] = user?.is_admin
    ? [
        {
          title: "Đồng bộ Server",
          icon: <DatabaseIcon className="h-7 w-7" />,
          description: "Tải file còn thiếu từ Google Drive về máy chủ",
          highlight: "Quản trị hệ thống",
          onClick: handleSyncLocal,
          color: "green",
        },
        {
          title: "Quản lý Người dùng",
          icon: <UsersIcon className="h-7 w-7" />,
          description: "Quản lý tài khoản, thay đổi quyền Admin",
          highlight: "Phân quyền",
          href: "/admin/users",
          color: "red",
        },
      ]
    : [];

  const actions = [...baseActions, ...adminActions];

  const colorClasses = {
    blue: "from-ctu-blue/10 via-white to-blue-50 border-ctu-blue/30 hover:shadow-ctu-blue/20",
    navy: "from-ctu-navy/10 via-white to-slate-50 border-ctu-navy/30 hover:shadow-ctu-navy/20",
    gold: "from-ctu-yellow/15 via-white to-amber-50 border-ctu-yellow/40 hover:shadow-ctu-yellow/30",
    green: "from-emerald-500/10 via-white to-emerald-50 border-emerald-500/30 hover:shadow-emerald-500/20",
    red: "from-rose-500/10 via-white to-rose-50 border-rose-500/30 hover:shadow-rose-500/20",
  };

  const iconBgClasses = {
    blue: "bg-ctu-blue/10 text-ctu-blue",
    navy: "bg-ctu-navy/10 text-ctu-navy",
    gold: "bg-ctu-yellow/20 text-ctu-navy",
    green: "bg-emerald-500/10 text-emerald-600",
    red: "bg-rose-500/10 text-rose-600",
  };

  const textColorClasses = {
    blue: "text-ctu-navy",
    navy: "text-ctu-navy",
    gold: "text-ctu-navy",
    green: "text-emerald-800",
    red: "text-rose-800",
  };

  const buttonColorClasses = {
    blue: "bg-ctu-blue hover:bg-ctu-navy-mid text-white",
    navy: "bg-ctu-navy hover:bg-ctu-navy-mid text-white",
    gold: "bg-ctu-yellow hover:bg-amber-400 text-ctu-navy",
    green: "bg-emerald-600 hover:bg-emerald-700 text-white",
    red: "bg-rose-600 hover:bg-rose-700 text-white",
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 flex items-center gap-2">
        Truy cập nhanh
        {user?.is_admin && (
          <span className="text-xs bg-rose-100 text-rose-700 px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider ml-2">
            Admin Mode
          </span>
        )}
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
        {actions.map((action, idx) => (
          <button
            key={action.href || idx}
            onClick={action.onClick ? action.onClick : () => action.href && navigate(action.href)}
            className={`group bg-gradient-to-br ${colorClasses[action.color]} border-2 rounded-2xl p-8 sm:p-10 text-left transition-all duration-300 hover:shadow-2xl hover:-translate-y-2 active:translate-y-0`}
          >
            <div
              className={`inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5 ${iconBgClasses[action.color]} transition-transform group-hover:scale-110 group-hover:rotate-6`}
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
      
      <SyncGDriveModal 
        isOpen={isSyncModalOpen} 
        onClose={() => setIsSyncModalOpen(false)} 
      />
    </div>
  );
}
