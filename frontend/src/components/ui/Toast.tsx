import { useEffect, useState } from "react";
import { toneClasses, type StatusTone } from "../../theme/status";
import { AlertTriangleIcon, CheckCircleIcon, InfoCircleIcon, XCircleIcon, XIcon } from "./Icons";
import { useI18n } from "../../i18n";

/**
 * Thông báo nổi.
 *
 * Ba sửa đổi, và chỉ cái đầu là về màu:
 *
 * 1. Màu lấy từ `theme/status` — "thành công" giờ là xanh dương CTU.
 * 2. **Biểu tượng là SVG, không phải ký tự.** Bản đầu vẽ `✓ ✕ ⚠ ⓘ` bằng chữ,
 *    nên hình dạng và cỡ phụ thuộc phông của HỆ ĐIỀU HÀNH: Windows dựng chúng
 *    bằng Segoe UI Symbol, macOS bằng Apple Symbols, Android thì đôi khi đổi
 *    hẳn sang emoji màu. Cùng một thông báo trông khác nhau ở ba máy, và trên
 *    máy thiếu phông thì ra ô vuông rỗng.
 * 3. **`role="status"` + `aria-live`.** Không có nó, trình đọc màn hình không
 *    đọc thông báo — với người dùng khiếm thị thì lượt lưu vừa rồi im lặng
 *    hoàn toàn. Lỗi dùng `assertive` (cắt lời đang đọc), phần còn lại dùng
 *    `polite`.
 */

export interface ToastProps {
  id?: string;
  message: string;
  type?: "success" | "error" | "warning" | "info";
  duration?: number;
  onClose?: () => void;
}

const TONE: Record<NonNullable<ToastProps["type"]>, StatusTone> = {
  success: "success",
  error: "danger",
  warning: "warning",
  info: "neutral",
};

const GLYPH = {
  success: CheckCircleIcon,
  error: XCircleIcon,
  warning: AlertTriangleIcon,
  info: InfoCircleIcon,
};

export default function Toast({ message, type = "info", duration = 4000, onClose }: ToastProps) {
  const { t } = useI18n();
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onClose?.(), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const Glyph = GLYPH[type];

  return (
    <div
      role="status"
      aria-live={type === "error" ? "assertive" : "polite"}
      className={`
      ${isVisible ? "animate-fade-in" : "opacity-0 translate-x-full"}
      transition-all duration-300 ease-out motion-reduce:transition-none
      flex items-start gap-3 p-4 rounded-lg border backdrop-blur-sm
      ${toneClasses(TONE[type], "soft")}
      max-w-sm shadow-lg
    `}
    >
      <Glyph className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 text-sm font-medium">{message}</div>
      <button
        type="button"
        aria-label={t("Đóng thông báo")}
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onClose?.(), 300);
        }}
        className="text-current opacity-60 hover:opacity-100 transition-opacity shrink-0"
      >
        <XIcon className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );
}
