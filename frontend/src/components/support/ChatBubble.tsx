import { authorKindOf, type TicketMessage } from "../../api/account";
import { RobotIcon, ShieldCheckIcon, UserIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

/**
 * Một bóng chat.
 *
 * BA hình dạng, không phải hai
 * -----------------------------
 * Người dùng, người trực, và trợ lý tự động phải nhìn ra được khác nhau **mà
 * không cần đọc chữ**. Một giao diện chỉ có "của tôi" và "của họ" buộc trợ lý
 * phải trông giống người trực, và khi đó người dùng tin rằng đã có người thật
 * đọc phiếu của mình — một hiểu lầm mà giao diện tạo ra, không phải người dùng.
 *
 * Nên: trợ lý có nền khác, viền nét đứt, biểu tượng máy, và nhãn có chữ "tự
 * động" ngay trong tên. Ba tín hiệu độc lập cho cùng một sự thật, vì một tín
 * hiệu là thứ người ta lướt qua.
 *
 * Vì sao KHÔNG dùng màu để phân biệt người dùng với người trực
 * -------------------------------------------------------------
 * Có dùng — nhưng màu không bao giờ là tín hiệu DUY NHẤT. Bóng của người khác
 * luôn có biểu tượng và tên; bóng của mình luôn nằm bên phải. Người không phân
 * biệt được màu vẫn đọc được cuộc trao đổi (WCAG 1.4.1).
 */

function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const last = parts[parts.length - 1];
  return last.slice(0, 1).toLocaleUpperCase("vi-VN");
}

function timeOf(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export default function ChatBubble({
  message,
  mine,
  showAuthor = true,
}: {
  message: TicketMessage;
  /** Bóng này của người đang xem. Quyết định phía trái/phải, không quyết định vai. */
  mine: boolean;
  /** Ẩn tên khi lời nhắn nối tiếp cùng một người — bớt nhiễu, giữ nhịp đọc. */
  showAuthor?: boolean;
}) {
  const { t } = useI18n();
  const kind = authorKindOf(message);
  const isBot = kind === "bot";
  const isStaff = kind === "staff";

  const bubble = mine
    ? "bg-ctu-blue text-white rounded-br-md"
    : isBot
      ? "border border-dashed border-slate-300 bg-slate-50 text-slate-700 rounded-bl-md"
      : "border border-slate-200 bg-white text-slate-800 rounded-bl-md";

  const Glyph = isBot ? RobotIcon : isStaff ? ShieldCheckIcon : UserIcon;

  return (
    <li className={`flex gap-2 ${mine ? "flex-row-reverse" : "flex-row"}`}>
      {/* Ảnh đại diện chỉ hiện ở bóng của người khác: bên mình thì vị trí đã
          nói đủ, và một hàng avatar lặp lại ở cả hai phía làm hẹp vùng đọc. */}
      {!mine ? (
        <span
          aria-hidden="true"
          className={`mt-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
            isBot ? "bg-slate-200 text-slate-500" : "bg-ctu-blue/10 text-ctu-blue"
          } ${showAuthor ? "" : "invisible"}`}
        >
          <Glyph className="h-4 w-4" />
        </span>
      ) : null}

      <div className={`min-w-0 max-w-[min(42rem,80%)] ${mine ? "items-end" : "items-start"}`}>
        {showAuthor && !mine ? (
          <p className="mb-0.5 flex items-center gap-1.5 px-1 text-xs font-medium text-slate-500">
            <span className="truncate">{message.author_label}</span>
            {isBot ? (
              <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                {t("tự động")}
              </span>
            ) : null}
            {isStaff ? (
              <span className="rounded bg-ctu-blue/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ctu-blue">
                {t("người trực")}
              </span>
            ) : null}
          </p>
        ) : null}

        <div className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed shadow-sm ${bubble}`}>
          {/* Lời của trợ lý đi qua `t()`, lời của người thì KHÔNG.
              Câu của trợ lý do dự án viết ra nên nó là một khoá từ điển; câu
              của người là nội dung trao đổi, và "dịch" nó là sửa lời người
              khác. `t()` trên chuỗi lạ trả về chính nó, nhưng gọi nó ở đây
              vẫn sai về ý định. */}
          <p className="whitespace-pre-wrap break-words">
            {isBot ? t(message.body) : message.body}
          </p>
        </div>

        <p
          className={`mt-0.5 px-1 text-[11px] text-slate-400 ${
            mine ? "text-right" : "text-left"
          }`}
        >
          <time dateTime={message.created_at}>{timeOf(message.created_at)}</time>
        </p>
      </div>

      {mine ? (
        <span
          aria-hidden="true"
          className={`mt-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ctu-blue/10 text-ctu-blue ${
            showAuthor ? "" : "invisible"
          }`}
          title={message.author_label}
        >
          <span className="text-xs font-semibold">{initials(message.author_label)}</span>
        </span>
      ) : null}
    </li>
  );
}
