import { LANGUAGES, useI18n, type Language } from "../../i18n";
import { CheckIcon, GlobeIcon } from "../../components/ui/Icons";

/**
 * Chọn ngôn ngữ giao diện.
 *
 * Trang này nói thẳng mức độ hoàn thiện của bản dịch thay vì để người dùng tự
 * phát hiện. Một nút đổi ngôn ngữ hứa nhiều hơn thứ nó làm được là cách chắc
 * chắn nhất để người ta kết luận sản phẩm hỏng — họ bấm, thấy phân nửa màn hình
 * vẫn tiếng Việt, và không có gì cho biết đó là chưa dịch xong hay là lỗi.
 */
export default function LanguageSettingsPage() {
  const { lang, setLang, t } = useI18n();

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-900">{t("Ngôn ngữ & hiển thị")}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {t("Lựa chọn được lưu trên trình duyệt này và áp dụng ngay.")}
        </p>
      </header>

      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium text-slate-700">
          {t("Ngôn ngữ giao diện")}
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {(Object.keys(LANGUAGES) as Language[]).map((code) => {
            const active = lang === code;
            return (
              <button
                key={code}
                type="button"
                onClick={() => setLang(code)}
                aria-pressed={active}
                className={`flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2 ${
                  active
                    ? "border-ctu-blue bg-ctu-blue/5"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <span className="flex items-center gap-3">
                  <GlobeIcon
                    className={`h-5 w-5 ${active ? "text-ctu-blue" : "text-slate-400"}`}
                    aria-hidden="true"
                  />
                  <span className="font-medium text-slate-900">{LANGUAGES[code]}</span>
                </span>
                {active ? (
                  <CheckIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
                ) : null}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
        <p className="font-medium text-slate-900">{t("Về bản dịch tiếng Anh")}</p>
        <p className="mt-1">
          {t(
            "Tiếng Việt là bản gốc. Bản tiếng Anh phủ giao diện chung, cài đặt, hỗ trợ, đăng nhập và văn bản pháp lý. Một số màn hình chuyên môn sâu vẫn hiển thị tiếng Việt.",
          )}
        </p>
        <p className="mt-2">
          {t(
            "Nội dung do người dùng nhập — tên nhãn, mô tả, nội dung phiếu hỗ trợ — luôn giữ nguyên như lúc nhập, không dịch máy.",
          )}
        </p>
      </div>
    </section>
  );
}
