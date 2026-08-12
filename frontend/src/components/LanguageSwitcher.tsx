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
 */

import { LANGUAGES, useI18n, type Language } from "../i18n";
import { GlobeIcon } from "./ui/Icons";

export default function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useI18n();

  return (
    <label className={`inline-flex items-center gap-1.5 ${className}`}>
      <GlobeIcon className="h-4 w-4 text-slate-500" aria-hidden="true" />
      <span className="sr-only">{t("Ngôn ngữ")}</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Language)}
        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
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
