import { useEffect, useRef, useState } from "react";

import { SendIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

/**
 * Ô soạn lời nhắn.
 *
 * **Enter gửi, Shift+Enter xuống dòng.** Đây là quy ước của mọi ứng dụng nhắn
 * tin, và đi ngược nó là bắt người dùng học lại một thói quen đã có sẵn. Nhưng
 * nó cũng là một cái bẫy: người ta lỡ tay gửi một câu chưa xong. Nên nút Gửi
 * vẫn luôn có mặt và ô vẫn tự cao lên theo nội dung — người muốn viết dài nhìn
 * thấy mình đang viết dài.
 *
 * Ô tự cao **có trần**: một lời nhắn 60 dòng không được phép đẩy hết cuộc trao
 * đổi ra khỏi màn hình.
 */
export default function Composer({
  value,
  onChange,
  onSend,
  disabled = false,
  placeholder,
  minLength = 2,
  autoFocus = false,
}: {
  value: string;
  onChange: (next: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
  minLength?: number;
  autoFocus?: boolean;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [rows, setRows] = useState(1);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    setRows(value.split("\n").length);
  }, [value]);

  const ready = value.trim().length >= minLength && !disabled;

  return (
    <form
      className="flex items-end gap-2 border-t border-slate-200 bg-white px-3 py-3 sm:px-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onSend();
      }}
    >
      <label htmlFor="chat-composer" className="sr-only">
        {t("Nội dung lời nhắn")}
      </label>
      <textarea
        id="chat-composer"
        ref={ref}
        rows={1}
        value={value}
        autoFocus={autoFocus}
        disabled={disabled}
        placeholder={placeholder ?? t("Nhập lời nhắn…")}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (ready) onSend();
          }
        }}
        className="max-h-40 min-h-[2.5rem] flex-1 resize-none rounded-2xl border border-slate-300 px-3.5 py-2 text-sm leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue disabled:bg-slate-50"
      />
      <button
        type="submit"
        disabled={!ready}
        aria-label={t("Gửi")}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ctu-blue text-white transition hover:bg-ctu-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <SendIcon className="h-5 w-5" aria-hidden="true" />
      </button>
      {rows > 1 ? (
        <span className="sr-only" aria-live="polite">
          {t("Shift+Enter để xuống dòng")}
        </span>
      ) : null}
    </form>
  );
}
