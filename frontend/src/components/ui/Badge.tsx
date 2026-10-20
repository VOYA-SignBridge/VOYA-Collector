import type { ReactNode } from "react";
import { toneClasses, type StatusTone } from "../../theme/status";
import { AlertTriangleIcon, CheckCircleIcon, InfoCircleIcon, XCircleIcon } from "./Icons";

/**
 * Nhãn trạng thái.
 *
 * Hai thay đổi so với bản đầu, cả hai đều có lý do ngoài thẩm mỹ:
 *
 * 1. **Màu lấy từ `theme/status`, không viết tay.** Bản đầu ghi cứng
 *    `bg-green-100`; đổi quy ước "thành công là xanh dương" khi đó là đi sửa
 *    31 tệp và bỏ sót vài chỗ.
 * 2. **Có biểu tượng mặc định.** Thương hiệu của hệ thống vốn đã là xanh
 *    dương, nên một chip xanh dương tự nó không nói "thành công" — nó chỉ nói
 *    "thuộc ứng dụng này". Biểu tượng mới là thứ mang nghĩa; màu chỉ nhấn thêm.
 *    Đây cũng là WCAG 1.4.1: không truyền đạt thông tin bằng riêng màu sắc.
 *
 * Tắt biểu tượng bằng `icon={false}` khi nhãn nằm trong một hàng đã có biểu
 * tượng khác — hai biểu tượng cạnh nhau thì không cái nào được đọc.
 */

/**
 * `info` và `default` là tên cũ, giữ lại làm bí danh.
 *
 * Đổi thẳng sang `tone` sẽ làm vỡ tám tệp trong một lần sửa vốn chỉ nói về
 * MÀU. Hai bí danh này quy về `neutral` — trước đây `info` là xanh CTU, và
 * giờ xanh đã mang nghĩa "thành công" thì để `info` cũng xanh là xoá mất đúng
 * sự phân biệt vừa dựng.
 */
type BadgeVariant = StatusTone | "info" | "default";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  icon?: boolean;
  className?: string;
}

const normalise = (v: BadgeVariant): StatusTone =>
  v === "info" || v === "default" ? "neutral" : v;

const ICONS: Record<StatusTone, (p: { className?: string }) => ReactNode> = {
  success: CheckCircleIcon,
  warning: AlertTriangleIcon,
  danger: XCircleIcon,
  neutral: InfoCircleIcon,
};

const SIZES = {
  sm: { box: "px-2 py-0.5 text-xs gap-1", icon: "w-3 h-3" },
  md: { box: "px-2.5 py-1 text-sm gap-1.5", icon: "w-3.5 h-3.5" },
};

export default function Badge({
  children,
  variant = "neutral",
  size = "md",
  icon = true,
  className = "",
}: BadgeProps) {
  const tone = normalise(variant);
  const Glyph = ICONS[tone];
  const s = SIZES[size];
  return (
    <span
      className={`inline-flex items-center border rounded-full font-medium ${toneClasses(tone, "soft")} ${s.box} ${className}`}
    >
      {icon && <Glyph className={`${s.icon} shrink-0`} aria-hidden="true" />}
      {children}
    </span>
  );
}
