import { useId, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDownIcon } from "./Icons";

interface CollapsibleProps {
  /** Tiêu đề luôn hiển thị, kể cả khi đang đóng. */
  title: string;
  /** Một dòng nói rõ bên trong có gì, để người dùng biết có cần mở hay không. */
  description?: string;
  /** Nhãn phụ bên phải tiêu đề (ví dụ số dòng, trạng thái). */
  badge?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Khối nội dung đóng/mở được.
 *
 * Dùng cho phần chi tiết kỹ thuật mà đa số người xem không cần: mặc định đóng
 * để màn hình chỉ còn thông tin ai cũng đọc được, ai cần sâu hơn thì mở ra.
 * Nội dung bên trong chỉ render khi mở — bảng lớn và ma trận nhầm lẫn không tốn
 * công dựng nếu không ai xem.
 */
export default function Collapsible({
  title,
  description,
  badge,
  defaultOpen = false,
  children,
  className = "",
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={contentId}
        className="flex w-full items-center gap-3 rounded-2xl px-5 py-4 text-left transition-colors hover:bg-slate-50"
      >
        <ChevronDownIcon
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-slate-900">{title}</span>
          {description && (
            <span className="mt-0.5 block text-xs text-slate-500">{description}</span>
          )}
        </span>
        {badge && <span className="shrink-0">{badge}</span>}
      </button>

      {open && (
        <div id={contentId} className="border-t border-slate-100 px-5 py-5">
          {children}
        </div>
      )}
    </div>
  );
}
