/**
 * Chọn ngôn ngữ.
 *
 * Là `<select>` thật chứ không phải menu tự vẽ: nó đã có sẵn điều hướng bàn
 * phím, đọc được bằng trình đọc màn hình, và trên điện thoại mở ra bộ chọn của
 * hệ điều hành. Một menu tự vẽ phải làm lại cả ba thứ đó và thường làm thiếu.
 *
 * Nhãn của mỗi ngôn ngữ viết BẰNG CHÍNH ngôn ngữ đó ("Tiếng Việt", "English"):
 * người đang lạc trong một giao diện họ không đọc được vẫn nhận ra tên tiếng mẹ
 * đẻ của mình. Dịch nhãn theo ngôn ngữ hiện tại là làm hỏng đúng công dụng đó.
 *
 * `tone="dark"` cho console quản trị. Console dùng nền tối và KHÔNG dùng lại
 * header của ứng dụng, nên nếu ô này chỉ có một bộ màu sáng thì nó hoặc trông
 * lạc lõng, hoặc — như đã xảy ra — bị bỏ hẳn khỏi console. Một người đọc tiếng
 * Anh bước vào `/admin` sẽ mắc kẹt trong mười hai mục tiếng Việt mà không có
 * lối đổi, vì lối đổi duy nhất nằm ở cái header mà console vừa thay mất.
 */

import { LANGUAGES, useI18n, type Language } from "../i18n";
import { GlobeIcon } from "./ui/Icons";

export default function LanguageSwitcher({
  className = "",
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  const { lang, setLang, t } = useI18n();
  const dark = tone === "dark";

  return (
    <label className={`inline-flex items-center gap-1.5 ${className}`}>
      <GlobeIcon
        className={`h-4 w-4 ${dark ? "text-slate-400" : "text-slate-500"}`}
        aria-hidden="true"
      />
      <span className="sr-only">{t("Ngôn ngữ")}</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Language)}
        className={`rounded-lg border px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 ${
          dark
            ? "border-slate-700 bg-slate-800 text-slate-100 focus-visible:ring-sky-400"
            : "border-slate-300 bg-white text-slate-700 focus-visible:ring-ctu-blue"
        }`}
      >
        {(Object.keys(LANGUAGES) as Language[]).map((code) => (
          <option key={code} value={code}>
            {LANGUAGES[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
