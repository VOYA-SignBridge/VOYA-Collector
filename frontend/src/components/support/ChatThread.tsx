import { useEffect, useRef } from "react";

import { authorKindOf, type TicketMessage } from "../../api/account";
import ChatBubble from "./ChatBubble";
import { useI18n } from "../../i18n";

/**
 * Vùng cuộn chứa cả cuộc trao đổi.
 *
 * Ba chi tiết nhỏ quyết định nó có dùng được hay không
 * ----------------------------------------------------
 * 1. **Tự cuộn xuống khi có lời mới — nhưng CHỈ khi người đọc đang ở đáy.**
 *    Kéo lên đọc lại rồi bị giật xuống là cách nhanh nhất khiến người ta bỏ
 *    cuộc. Ngưỡng 80px cho phép hụt vài dòng vẫn tính là "đang ở đáy".
 * 2. **Gộp lời nhắn liên tiếp cùng người.** Lặp tên và avatar ở mỗi dòng làm
 *    một cuộc trao đổi 20 câu trông như 20 thông báo rời rạc.
 * 3. **Vạch ngày.** Không có nó thì một câu hôm qua và một câu hôm nay dính
 *    liền nhau, và "10:32" ở dưới không nói được đó là 10:32 của ngày nào.
 */

function dayKey(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toDateString();
}

function dayLabel(iso: string, t: (k: string, v?: Record<string, string | number>) => string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return t("Hôm nay");
  if (d.toDateString() === yesterday.toDateString()) return t("Hôm qua");
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

export default function ChatThread({
  messages,
  isMine,
  emptyHint,
}: {
  messages: TicketMessage[];
  /** Bóng nào là của người đang xem. Hai bên trả lời khác nhau nên không đoán được ở đây. */
  isMine: (m: TicketMessage) => boolean;
  emptyHint?: string;
}) {
  const { t } = useI18n();
  const boxRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);

  // Ghi lại vị trí cuộn TRƯỚC khi danh sách thay đổi. Đọc sau khi nó đã dài
  // thêm thì `scrollHeight` đã đổi và phép so luôn cho ra "không ở đáy".
  const onScroll = () => {
    const el = boxRef.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    const el = boxRef.current;
    if (!el || !atBottom.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-slate-500">
        {emptyHint ?? t("Chưa có lời nhắn nào.")}
      </div>
    );
  }

  return (
    <div
      ref={boxRef}
      onScroll={onScroll}
      className="flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-4"
    >
      <ol className="flex flex-col gap-2">
        {messages.map((m, i) => {
          const prev = i > 0 ? messages[i - 1] : null;
          const newDay = !prev || dayKey(prev.created_at) !== dayKey(m.created_at);
          const sameAuthor =
            !!prev &&
            !newDay &&
            authorKindOf(prev) === authorKindOf(m) &&
            prev.author_label === m.author_label;
          return (
            <li key={m.message_id} className="contents">
              {newDay ? (
                <li className="my-2 flex items-center gap-3" aria-hidden="true">
                  <span className="h-px flex-1 bg-slate-200" />
                  <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    {dayLabel(m.created_at, t)}
                  </span>
                  <span className="h-px flex-1 bg-slate-200" />
                </li>
              ) : null}
              <ChatBubble message={m} mine={isMine(m)} showAuthor={!sameAuthor} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
