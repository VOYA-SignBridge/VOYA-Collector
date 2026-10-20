/**
 * Dải thông báo lỗi.
 *
 * @i18n-key-table — `label` trong `CONFIG` là KHOÁ từ điển; bảng nằm ngoài
 * component nên `t()` gọi ở chỗ dựng.
 */
import { useState, useEffect } from "react";
import { toneClasses, type StatusTone } from "../theme/status";
import { AlertTriangleIcon, CheckCircleIcon, InfoCircleIcon, XCircleIcon, XIcon } from "./ui/Icons";
import { useI18n } from "../i18n";

/**
 * Dải thông báo trong luồng nội dung.
 *
 * Ba sửa đổi so với bản đầu:
 *
 * 1. **Màu theo `theme/status`** — "thành công" là xanh dương CTU.
 * 2. **Biểu tượng là SVG.** Bản đầu dùng `❌ ⚠️ ℹ️ ✅`. Emoji được HỆ ĐIỀU HÀNH
 *    dựng, nên cùng một dải thông báo ra bốn kiểu khác nhau trên bốn máy, và
 *    trên máy thiếu phông emoji thì ra ô vuông rỗng. Chúng cũng không đổi màu
 *    theo `currentColor`, nên một cảnh báo vàng vẫn kèm dấu đỏ.
 * 3. **Tiêu đề bằng tiếng Việt.** Bản đầu in
 *    `type.charAt(0).toUpperCase() + type.slice(1)`, tức người dùng thấy chữ
 *    "Error" / "Warning" tiếng Anh giữa một giao diện tiếng Việt — và với
 *    `type="info"` thì thành "Info", một từ không nói gì cả.
 */

type BannerType = "error" | "warning" | "info" | "success";

type Props = {
  message: string;
  onClose?: () => void;
  type?: BannerType;
  autoClose?: boolean;
  duration?: number;
};

const CONFIG: Record<BannerType, { tone: StatusTone; label: string; Glyph: typeof XCircleIcon }> = {
  error:   { tone: "danger",  label: "Có lỗi",   Glyph: XCircleIcon },
  warning: { tone: "warning", label: "Lưu ý",    Glyph: AlertTriangleIcon },
  info:    { tone: "neutral", label: "Thông tin", Glyph: InfoCircleIcon },
  success: { tone: "success", label: "Đã xong",  Glyph: CheckCircleIcon },
};

export default function ErrorBanner({
  message,
  onClose,
  type = "error",
  autoClose = false,
  duration = 5000,
}: Props) {
  const { t } = useI18n();
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    setIsVisible(true);
  }, [message, type]);

  useEffect(() => {
    if (autoClose) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(() => onClose?.(), 300);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [autoClose, duration, onClose]);

  const { tone, label, Glyph } = CONFIG[type];

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(() => onClose?.(), 300);
  };

  if (!isVisible) return null;

  return (
    <div
      role={type === "error" ? "alert" : "status"}
      aria-live={type === "error" ? "assertive" : "polite"}
      className={`card mb-6 border transition-all duration-300 ease-out animate-fade-in motion-reduce:transition-none ${toneClasses(tone, "soft")}`}
    >
      <div className="flex items-start gap-4">
        <Glyph className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm mb-1">{t(label)}</div>
          <div className="text-sm leading-relaxed">{message}</div>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={handleClose}
            className="text-current opacity-60 hover:opacity-100 transition-colors p-1 rounded-md hover:bg-white/60"
            aria-label={t("Đóng thông báo")}
          >
            <XIcon className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}
