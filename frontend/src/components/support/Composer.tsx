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
 *
 * `disabled` và `canSend` là HAI thứ khác nhau — sửa 16/08/2026
 * -------------------------------------------------------------
 * Trước lần sửa này chỉ có `disabled`, và `SupportPage` truyền vào
 * `disabled={busy || !ready}` với `ready` đòi mô tả dài từ 10 ký tự. Kết quả là
 * một vòng luẩn quẩn có thật, không phải chuyện lý thuyết:
 *
 *     mô tả rỗng  ->  !ready  ->  textarea bị disabled  ->  không gõ được mô tả
 *
 * Người dùng mở "Hội thoại mới", gõ được tiêu đề (một `<input>` riêng, không bị
 * khoá), rồi phát hiện ô nhắn tin **không nhận phím**. Báo cáo của họ đúng
 * nguyên văn: "tôi còn gửi tin nhắn không được nữa".
 *
 * Nên tách:
 *   `disabled` — không GÕ được (đang gửi, hội thoại đã đóng)
 *   `canSend`  — gõ được nhưng chưa đủ điều kiện GỬI
 *
 * Và khi chưa gửi được thì phải NÓI RA, ngay cạnh nút. Một cái nút mờ đi không
 * kèm lý do là chỗ người ta bấm ba lần rồi bỏ cuộc.
 */
export default function Composer({
  value,
  onChange,
  onSend,
  disabled = false,
  canSend = true,
  blockedReason = "",
  placeholder,
  minLength = 2,
  autoFocus = false,
}: {
  value: string;
  onChange: (next: string) => void;
  onSend: () => void;
  /** Khoá cả việc GÕ. Chỉ dùng khi thật sự không được nhập: đang gửi, đã đóng. */
  disabled?: boolean;
  /** Gõ được, nhưng chưa gửi được. Kèm `blockedReason` để nói vì sao. */
  canSend?: boolean;
  blockedReason?: string;
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

  const longEnough = value.trim().length >= minLength;
  const ready = longEnough && canSend && !disabled;

  return (
    <div className="border-t border-slate-200 bg-white">
      <form
        className="flex items-end gap-2 px-3 py-3 sm:px-4"
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

      {/* Lý do nằm NGAY DƯỚI nút, và chỉ hiện khi người dùng đã bắt đầu gõ —
          hiện ngay từ ô trống là mắng người ta trước khi họ làm gì. */}
      {!ready && !disabled && blockedReason && value.length > 0 ? (
        <p aria-live="polite" className="px-4 pb-2 text-xs text-amber-700">
          {blockedReason}
        </p>
      ) : null}
    </div>
  );
}
