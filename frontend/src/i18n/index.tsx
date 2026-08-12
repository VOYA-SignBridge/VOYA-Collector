/**
 * Khung đa ngôn ngữ, viết tay, không phụ thuộc thư viện ngoài.
 *
 * Vì sao không dùng `react-i18next`: nó kéo theo ~40 KB và một hệ thống
 * namespace/backend/interpolation mà dự án này không dùng tới. Cái cần ở đây là
 * một từ điển phẳng, một hook, và một chỗ chọn ngôn ngữ. Ba thứ đó gọn hơn phần
 * cấu hình của thư viện.
 *
 * BA NGUYÊN TẮC, và cái thứ ba là cái hay bị bỏ:
 *
 * 1. **Tiếng Việt là bản GỐC, không phải bản dịch.** Sản phẩm phục vụ người
 *    Việt học ngôn ngữ ký hiệu Việt Nam. Tiếng Anh là bản dịch cho người đọc
 *    nước ngoài — trong đó có hội đồng chấm và người đọc bài báo quốc tế.
 *
 * 2. **Khoá là câu tiếng Việt, không phải mã.** `t("Đăng nhập")` chứ không phải
 *    `t("auth.login.button")`. Nhờ vậy một chuỗi chưa dịch vẫn hiển thị ĐÚNG
 *    tiếng Việt thay vì hiện ra một mã lỗi giữa giao diện — kiểu hỏng mà người
 *    dùng nhìn thấy còn lập trình viên thì không.
 *
 * 3. **`lang` trên thẻ `<html>` phải đổi theo.** Đây là chỗ hầu hết bản cài đặt
 *    quên. Trình đọc màn hình chọn giọng đọc theo thuộc tính đó; để nguyên
 *    `lang="vi"` rồi hiện chữ tiếng Anh nghĩa là người khiếm thị nghe tiếng Anh
 *    đọc bằng bộ phát âm tiếng Việt. WCAG 3.1.1 — xem docs/ACCESSIBILITY.md.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { EN } from "./en";

export const LANGUAGES = {
  vi: "Tiếng Việt",
  en: "English",
} as const;

export type Language = keyof typeof LANGUAGES;

const STORAGE_KEY = "voya.lang";
export const DEFAULT_LANGUAGE: Language = "vi";

function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && value in LANGUAGES;
}

/** Ngôn ngữ đã lưu, hoặc suy từ trình duyệt, hoặc tiếng Việt. */
export function detectLanguage(): Language {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (isLanguage(saved)) return saved;
  } catch {
    // localStorage bị chặn (chế độ riêng tư, cookie bị khoá). Không phải lỗi —
    // chỉ có nghĩa là lựa chọn không nhớ được giữa các phiên.
  }
  const nav = typeof navigator !== "undefined" ? navigator.language : "";
  return nav.toLowerCase().startsWith("en") ? "en" : DEFAULT_LANGUAGE;
}

interface I18nValue {
  lang: Language;
  setLang: (next: Language) => void;
  /** Dịch. Trả về chính khoá khi chưa có bản dịch — xem nguyên tắc 2. */
  t: (key: string, vars?: TransVars) => string;
}

/**
 * Giá trị mặc định là một BẢN CHẠY ĐƯỢC, không phải `null`.
 *
 * Bản đầu để `null` và cho `useI18n` ném lỗi khi nằm ngoài provider. Lập luận
 * khi đó: một cây component ngoài provider sẽ hiện tiếng Việt kể cả khi người
 * dùng đã chọn tiếng Anh, và không có gì cho thấy điều đó sai.
 *
 * Lập luận ấy đúng khi `t()` được gọi ở vài chỗ. Nó **đổ** khi `t()` có mặt
 * khắp ứng dụng: lúc đó mọi bài test dựng một component đơn lẻ đều phải bọc
 * provider, nếu không thì vỡ — và cái vỡ đó không nói gì về component đang
 * kiểm. Một cơ chế bắt buộc phải có mặt ở mọi chỗ thì không được phép là cơ
 * chế có thể ném.
 *
 * Nên: mặc định trả về tiếng Việt (bản GỐC, xem nguyên tắc 1) và kêu một tiếng
 * ở chế độ phát triển. Tín hiệu vẫn còn, nhưng nó không đánh sập gì.
 */
const FALLBACK: I18nValue = {
  lang: DEFAULT_LANGUAGE,
  setLang: () => {
    if (import.meta.env.DEV) {
      console.warn("[i18n] setLang gọi ngoài <I18nProvider> — không có tác dụng");
    }
  },
  t: (key, vars) => interpolate(key, vars),
};

/**
 * Giá trị điền vào chỗ trống của một khoá.
 *
 * `null`/`undefined` được nhận CÓ CHỦ Ý. Phần lớn chỗ trống lấy từ dữ liệu máy
 * chủ (`m.username`, `res.machine.name`), và những trường đó vốn có thể rỗng.
 * Bắt từng chỗ gọi tự viết `?? ""` là hàng chục lần lặp cùng một câu, và chỉ
 * cần quên một lần là màn hình hiện ra chữ "null" giữa câu. Ở đây quy về chuỗi
 * rỗng một lần cho tất cả.
 */
export type TransVars = Record<string, string | number | null | undefined>;

const I18nContext = createContext<I18nValue>(FALLBACK);

/** `{ten}` trong chuỗi được thay bằng `vars.ten`. */
function interpolate(text: string, vars?: TransVars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name) =>
    name in vars ? String(vars[name] ?? "") : whole,
  );
}

/**
 * Ngôn ngữ hiện tại, giữ ở mức module để mã KHÔNG PHẢI component đọc được.
 *
 * `lib/errors.ts` đổi lỗi máy chủ thành câu người đọc, và nó là một hàm thuần —
 * không phải component, nên không gọi hook được. Cùng cảnh với các bảng nhãn ở
 * `api/*.ts`. Không có lối này thì chỉ còn hai lựa chọn: sửa 46 chỗ gọi để
 * chuyền `t` xuống, hoặc bỏ luôn không dịch thông báo lỗi.
 *
 * **Giới hạn phải nói ra: chuỗi do `tr()` sinh ra KHÔNG tự đổi khi người dùng
 * đổi ngôn ngữ.** Nó là một chuỗi, không phải một liên kết sống. Một thông báo
 * lỗi đã nằm trong state sẽ giữ nguyên ngôn ngữ lúc nó sinh ra cho tới lần dựng
 * lại kế tiếp. Với thông báo lỗi thoáng qua thì chấp nhận được; với chữ cố định
 * trên màn hình thì KHÔNG — chỗ đó phải dùng `t()` trong component.
 */
let currentLang: Language = DEFAULT_LANGUAGE;

/** Bản `t()` cho mã ngoài React. Đọc kỹ giới hạn ở `currentLang` trước khi dùng. */
export function tr(key: string, vars?: TransVars): string {
  if (currentLang === "vi") return interpolate(key, vars);
  return interpolate(EN[key] ?? key, vars);
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Language>(detectLanguage);
  // Đặt trong thân hàm chứ không trong `useEffect`: effect chạy SAU lần dựng
  // đầu, nên một `tr()` gọi trong lúc dựng sẽ đọc nhầm ngôn ngữ mặc định.
  currentLang = lang;

  useEffect(() => {
    // Nguyên tắc 3. `document.documentElement` chứ không phải một thẻ nào khác:
    // trình đọc màn hình đọc thuộc tính này ở gốc tài liệu.
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Language) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Xem chú thích ở detectLanguage.
    }
  }, []);

  const t = useCallback(
    (key: string, vars?: TransVars) => {
      if (lang === "vi") return interpolate(key, vars);
      return interpolate(EN[key] ?? key, vars);
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  // Không ném. Xem chú thích ở `FALLBACK` về vì sao bản đầu ném và vì sao lập
  // luận đó không còn đứng vững khi `t()` có mặt khắp ứng dụng.
  return useContext(I18nContext);
}

/** Chỉ hàm dịch, cho những chỗ không cần đổi ngôn ngữ. */
export function useT() {
  return useI18n().t;
}

/**
 * Một câu có chữ được **in đậm** hoặc *nghiêng* ở giữa — dịch NGUYÊN CÂU.
 *
 * Vì sao cần đến nó. `<p>Mẫu này thu trước khi hệ thống lưu <em>toạ độ thật</em>,
 * nên <strong>chiều sâu bị dẹp</strong>.</p>` là MỘT câu, nhưng JSX cắt nó thành
 * năm nút. Bọc `t()` quanh từng nút cho ra năm khoá, mỗi khoá là một mảnh câu —
 * và tiếng Anh KHÔNG giữ nguyên trật tự từ của tiếng Việt, nên ghép năm mảnh đã
 * dịch rời lại sẽ ra một câu sai ngữ pháp. Tệ hơn: nó chỉ sai ở bản tiếng Anh,
 * nên người phát triển nói tiếng Việt không bao giờ nhìn thấy.
 *
 * Ở đây câu là một khoá trọn vẹn, chỗ nhấn mạnh là `{tên}`, và người dịch tự do
 * đặt chỗ nhấn ở vị trí nào tiếng Anh cần:
 *
 * ```tsx
 * <Trans
 *   k="thu trước khi hệ thống lưu {toado}, nên {chieusau} so với lúc ký."
 *   vars={{ toado: <em>toạ độ thật</em>, chieusau: <strong>chiều sâu bị dẹp</strong> }}
 * />
 * ```
 *
 * Biến không có trong `vars` được để nguyên `{tên}` thay vì biến mất — một chỗ
 * trống nhìn thấy được thì sửa được, còn một chỗ trống im lặng thì không.
 */
export function Trans({
  k,
  vars,
}: {
  k: string;
  vars?: Record<string, React.ReactNode>;
}) {
  const { t } = useI18n();
  // `t(k)` không kèm `vars`: giữ nguyên `{tên}` để tự tách ở dưới. Bản dịch
  // tiếng Anh phải mang đúng bộ tên đó, chỉ khác vị trí.
  const parts = t(k).split(/(\{\w+\})/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\{(\w+)\}$/.exec(part);
        if (m && vars && m[1] in vars) {
          return <React.Fragment key={i}>{vars[m[1]]}</React.Fragment>;
        }
        return part;
      })}
    </>
  );
}
