import { useEffect, useId, useRef } from "react";

/**
 * Ô nhập mã dùng một lần.
 *
 * Một ô, không phải sáu ô
 * ------------------------
 * Kiểu sáu ô vuông rời trông đẹp hơn và hỏng nhiều thứ hơn:
 *
 * * **Tự điền chết.** `autocomplete="one-time-code"` là thứ khiến iOS và
 *   Android nhặt mã từ tin nhắn/thư và điền hộ. Nó điền vào MỘT trường. Sáu
 *   trường thì hoặc không có gì xảy ra, hoặc cả sáu ký tự dồn vào ô đầu.
 * * **Dán chết.** Người dùng chép mã từ email rồi Ctrl+V; sáu ô rời phải tự
 *   viết lại logic tách ký tự, và bản viết tay nào cũng quên một trường hợp
 *   (dán khi con trỏ ở ô thứ ba, dán mã có khoảng trắng).
 * * **Trình đọc màn hình đọc sáu nhãn** cho một thông tin duy nhất.
 *
 * Nên: một `<input>` thật, giãn chữ cho dễ soát bằng mắt.
 *
 * `inputMode="numeric"` chứ không phải `type="number"` — `type="number"` cho
 * phép `e`, dấu trừ, và hiện nút tăng giảm trên một thứ không phải số lượng.
 */

import { useI18n } from "../../i18n";

interface Props {
  value: string;
  onChange: (next: string) => void;
  /** Số chữ số máy chủ phát ra. Xem `otp.CODE_DIGITS`. */
  length?: number;
  disabled?: boolean;
  /** Đặt con trỏ vào ô ngay khi hiện — dùng sau khi vừa gửi mã xong. */
  autoFocus?: boolean;
  label?: string;
  hint?: string;
  error?: string;
}

export default function OtpCodeInput({
  value,
  onChange,
  length = 6,
  disabled = false,
  autoFocus = false,
  label,
  hint,
  error,
}: Props) {
  const { t } = useI18n();
  const ref = useRef<HTMLInputElement>(null); // Nhãn nối với ô bằng `htmlFor`, KHÔNG bằng cách bọc `<input>` trong
  // `<label>`. Với kiểu bọc, mọi chữ nằm trong thẻ đó — kể cả dòng gợi ý và
  // dòng lỗi — đều bị tính vào TÊN của ô. Trình đọc màn hình khi đó đọc "Mã
  // xác minh Mã có hiệu lực trong ít phút Nhập sai quá năm lần…" như một cái
  // tên duy nhất. Gợi ý và lỗi thuộc về `aria-describedby`, là thứ được đọc
  // SAU tên chứ không thay thế nó.
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  return (
    <div className="block">
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label ?? t("Mã xác minh")}
      </label>
      <input
        id={id}
        ref={ref}
        // Lọc ngay lúc gõ chứ không đợi lúc gửi: chuỗi dán vào thường mang theo
        // khoảng trắng hoặc gạch nối, và để nguyên thì máy chủ từ chối một mã
        // vốn đúng.
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, length))}
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="\d*"
        maxLength={length}
        disabled={disabled}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        placeholder={"•".repeat(length)}
        className={`w-full rounded-xl border bg-white px-4 py-3 text-center font-mono text-2xl tracking-[0.5em] text-slate-900 shadow-sm outline-none transition placeholder:tracking-[0.4em] placeholder:text-slate-300 focus:border-ctu-blue focus:ring-4 focus:ring-ctu-blue/15 disabled:bg-slate-50 disabled:text-slate-400 ${
          error ? "border-red-300" : "border-slate-200"
        }`}
      />
      {error ? (
        <span id={errorId} role="alert" className="mt-1.5 block text-sm text-red-600">
          {error}
        </span>
      ) : hint ? (
        <span id={hintId} className="mt-1.5 block text-sm text-slate-500">
          {hint}
        </span>
      ) : null}
    </div>
  );
}
