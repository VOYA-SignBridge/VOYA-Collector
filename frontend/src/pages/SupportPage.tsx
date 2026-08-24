/**
 * Kênh hỗ trợ của người dùng — `/settings/support`.
 *
 * Từ "biểu mẫu gửi phiếu" sang "phòng chat"
 * ------------------------------------------
 * Bản trước là ba màn hình rời: danh sách → biểu mẫu → chi tiết. Nó đúng về
 * chức năng và sai về nhịp. Người đang gặp sự cố không muốn điền biểu mẫu; họ
 * muốn kể chuyện. Ba màn hình biến một câu hỏi mười giây thành một thủ tục, và
 * mỗi lần chuyển màn hình là một lần người ta cân nhắc bỏ cuộc.
 *
 * Nên: một khung nhắn tin. Danh sách hội thoại bên trái, cuộc trao đổi bên
 * phải, bóng chat, và chip câu hỏi nhanh. Cùng dữ liệu, cùng API — chỉ khác
 * cách bày.
 *
 * Trợ lý tự động trả lời NGAY, người trực vào sau
 * ------------------------------------------------
 * Máy chủ trả lời được một số câu thường gặp ngay lúc phiếu mở
 * (`app/support_bot.py`). Nó KHÔNG hoãn việc báo cho người trực — người trực
 * vẫn nhận thông báo cùng lúc. "Để bot xử lý trước rồi mới gọi người" là cách
 * biến một sự cố gấp thành một sự cố gấp bị bỏ quên.
 *
 * Bóng của trợ lý trông khác hẳn bóng của người trực. Xem `ChatBubble` về vì
 * sao ba tín hiệu độc lập chứ không phải một.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  CATEGORY_LABEL,
  createTicket,
  fetchSupportStarters,
  fetchTicket,
  fetchTickets,
  replyToTicket,
  setTicketStatus,
  STATUS_LABEL,
  authorKindOf,
  type Ticket,
  type TicketCategory,
  type TicketStatus,
  type TicketSummary,
} from "../api/account";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { AlertTriangleIcon, InboxIcon, PencilIcon, RobotIcon } from "../components/ui/Icons";
import ChatThread from "../components/support/ChatThread";
import Composer from "../components/support/Composer";
import QuickReplies from "../components/support/QuickReplies";
import { useVisiblePoll } from "../hooks/useVisiblePoll";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";

const STATUS_TONE: Record<TicketStatus, "success" | "warning" | "neutral"> = {
  open: "warning",
  pending: "warning",
  resolved: "success",
  closed: "neutral",
};

/** Chu kỳ hỏi lại khi có hội thoại đang mở. Xem `useVisiblePoll`. */
const POLL_MS = 8000;

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("vi-VN", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      });
}

export default function SupportPage() {
  const { t } = useI18n();
  // Phiếu cần mở, lấy từ ĐƯỜNG DẪN. Thông báo "phản hồi mới trên phiếu"
  // trỏ thẳng vào một phiếu cụ thể; không đọc tham số này thì cú nhấp chỉ
  // mở danh sách và người dùng phải tự đi tìm lại thứ vừa được báo.
  const { id: ticketFromUrl } = useParams<{ id?: string }>();

  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [open, setOpen] = useState<Ticket | null>(null);
  const [composing, setComposing] = useState(false);
  const [starters, setStarters] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Soạn hội thoại mới
  const [subject, setSubject] = useState("");
  const [category, setCategory] = useState<TicketCategory>("other");
  const [draft, setDraft] = useState("");
  // Trả lời trong hội thoại đang mở
  const [reply, setReply] = useState("");

  // Số thứ tự lượt tải chi tiết: một lượt hỏi lại chậm KHÔNG được ghi đè lên
  // kết quả mới hơn, nếu không thì lời vừa gửi biến mất khỏi màn hình rồi hiện
  // lại ở lượt sau.
  const run = useRef(0);

  const loadList = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      setTickets(await fetchTickets());
      setError("");
    } catch (err) {
      setError(friendlyError(err, t("Không tải được danh sách hội thoại.")));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [t]);

  const loadTicket = useCallback(async (id: string, quiet = false) => {
    const mine = ++run.current;
    try {
      const data = await fetchTicket(id);
      if (mine !== run.current) return;
      setOpen(data);
      setError("");
    } catch (err) {
      if (mine !== run.current) return;
      if (!quiet) setError(friendlyError(err, t("Không mở được hội thoại.")));
    }
  }, [t]);

  // Mở thẳng phiếu mà đường dẫn chỉ tới.
  //
  // Chạy TÁCH khỏi lượt nạp danh sách bên dưới, và không phụ thuộc vào nó: một
  // phiếu đã giải quyết có thể không còn trong danh sách mặc định, nhưng cú
  // nhấp từ thông báo vẫn phải mở được nó. Nối hai việc lại sẽ tạo ra đúng một
  // ca hỏng — thông báo về phiếu cũ dẫn tới một màn hình trống.
  useEffect(() => {
    if (ticketFromUrl) void loadTicket(ticketFromUrl);
  }, [ticketFromUrl, loadTicket]);

  useEffect(() => {
    void loadList();
    void fetchSupportStarters()
      .then((s) => setStarters(s.starters))
      // Chip là tiện ích, không phải điều kiện để dùng trang. Mất chúng thì ô
      // soạn vẫn hoạt động, nên hỏng ở đây không được hiện lỗi đỏ.
      .catch(() => setStarters([]));
  }, [loadList]);

  // Hỏi lại cả danh sách lẫn hội thoại đang mở. Danh sách cũng phải làm mới:
  // người trực trả lời làm trạng thái đổi, và một hàng ghi "đang mở" trong khi
  // nó đã được giải quyết là một hàng nói dối.
  useVisiblePoll(() => {
    if (open) void loadTicket(open.ticket_id, true);
    void loadList(true);
  }, POLL_MS, !composing);

  const selectTicket = async (id: string) => {
    setComposing(false);
    setReply("");
    await loadTicket(id);
  };

  const startNew = () => {
    setOpen(null);
    setComposing(true);
    setSubject("");
    setDraft("");
    setCategory("other");
    setError("");
  };

  const submitNew = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await createTicket({
        subject: subject.trim(),
        body: draft.trim(),
        category,
      });
      setComposing(false);
      setOpen(created);
      setDraft("");
      setSubject("");
      await loadList(true);
    } catch (err) {
      setError(friendlyError(err, t("Không mở được hội thoại.")));
    } finally {
      setBusy(false);
    }
  };

  const submitReply = async (text?: string) => {
    const body = (text ?? reply).trim();
    if (!open || body.length < 2 || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await replyToTicket(open.ticket_id, body);
      run.current += 1;             // vô hiệu mọi lượt hỏi lại đang bay
      setOpen(updated);
      setReply("");
      await loadList(true);
    } catch (err) {
      setError(friendlyError(err, t("Không gửi được lời nhắn.")));
    } finally {
      setBusy(false);
    }
  };

  const closeTicket = async () => {
    if (!open || busy) return;
    setBusy(true);
    try {
      setOpen(await setTicketStatus(open.ticket_id, "closed"));
      await loadList(true);
    } catch (err) {
      setError(friendlyError(err, t("Không đóng được hội thoại.")));
    } finally {
      setBusy(false);
    }
  };

  const suggestions = useMemo(() => open?.bot_suggestions ?? [], [open]);
  const closed = open?.status === "closed";

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {t("Hỗ trợ")}
          </h1>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-600">
            <RobotIcon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            {t("Trợ lý tự động trả lời ngay. Người trực cũng nhận được thông báo và sẽ vào khi sẵn sàng.")}
          </p>
        </div>
        <Button onClick={startNew}>
          <PencilIcon className="mr-1.5 h-4 w-4" aria-hidden="true" />
          {t("Hội thoại mới")}
        </Button>
      </div>

      {error ? (
        <div
          role="alert"
          className="mb-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="grid min-h-[32rem] gap-4 lg:h-[calc(100vh-16rem)] lg:grid-cols-[20rem_1fr]">
        {/* ---------------------------------------------- danh sách hội thoại */}
        <aside
          className={`flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white ${
            open || composing ? "hidden lg:flex" : "flex"
          }`}
        >
          <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
            {t("Hội thoại của tôi")}
          </h2>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <p className="p-4 text-sm text-slate-500">{t("Đang tải…")}</p>
            ) : tickets.length === 0 ? (
              <div className="p-6 text-center">
                <InboxIcon className="mx-auto h-8 w-8 text-slate-300" aria-hidden="true" />
                <p className="mt-2 text-sm text-slate-500">
                  {t("Chưa có hội thoại nào. Bấm \"Hội thoại mới\" để bắt đầu.")}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {tickets.map((row) => {
                  const active = open?.ticket_id === row.ticket_id;
                  return (
                    <li key={row.ticket_id}>
                      <button
                        type="button"
                        onClick={() => void selectTicket(row.ticket_id)}
                        aria-current={active ? "true" : undefined}
                        className={`w-full px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ctu-blue ${
                          active ? "bg-ctu-blue/5" : "hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">
                            {row.subject}
                          </span>
                          <Badge variant={STATUS_TONE[row.status]} size="sm">
                            {t(STATUS_LABEL[row.status])}
                          </Badge>
                        </div>
                        {row.last_snippet ? (
                          <p className="mt-0.5 truncate text-xs text-slate-500">
                            {row.last_snippet}
                          </p>
                        ) : null}
                        <p className="mt-0.5 text-[11px] text-slate-400">
                          {formatWhen(row.updated_at)}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>

        {/* ------------------------------------------------------ khung chat */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
          {composing ? (
            <NewConversation
              subject={subject}
              onSubject={setSubject}
              category={category}
              onCategory={setCategory}
              draft={draft}
              onDraft={setDraft}
              starters={starters}
              busy={busy}
              onSend={submitNew}
              onCancel={() => setComposing(false)}
            />
          ) : open ? (
            <>
              <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-3">
                <button
                  type="button"
                  onClick={() => setOpen(null)}
                  className="text-sm font-medium text-ctu-blue lg:hidden"
                >
                  {t("← Danh sách")}
                </button>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-slate-900">
                    {open.subject}
                  </h2>
                  <p className="text-xs text-slate-500">
                    {t(CATEGORY_LABEL[open.category])} · {formatWhen(open.created_at)}
                  </p>
                </div>
                <Badge variant={STATUS_TONE[open.status]} size="sm">
                  {t(STATUS_LABEL[open.status])}
                </Badge>
              </header>

              <ChatThread
                messages={open.messages}
                isMine={(m) => authorKindOf(m) === "user"}
              />

              {closed ? (
                <p className="border-t border-slate-200 bg-white px-4 py-4 text-center text-sm text-slate-600">
                  {t("Hội thoại này đã đóng. Nếu vấn đề còn, hãy mở hội thoại mới.")}
                </p>
              ) : (
                <>
                  <QuickReplies
                    items={suggestions}
                    disabled={busy}
                    onPick={(text) => void submitReply(text)}
                    label={t("Trả lời nhanh")}
                  />
                  <Composer
                    value={reply}
                    onChange={setReply}
                    onSend={() => void submitReply()}
                    disabled={busy}
                  />
                  <div className="border-t border-slate-100 bg-white px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => void closeTicket()}
                      disabled={busy}
                      className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-700 disabled:opacity-50"
                    >
                      {t("Đóng hội thoại này")}
                    </button>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
              <InboxIcon className="h-10 w-10 text-slate-300" aria-hidden="true" />
              <p className="mt-3 max-w-sm text-sm text-slate-500">
                {t("Chọn một hội thoại bên trái, hoặc mở hội thoại mới để hỏi bất cứ điều gì.")}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/**
 * Ô soạn hội thoại mới.
 *
 * Vẫn có Tiêu đề và Phân loại vì máy chủ cần chúng — tiêu đề là thứ người trực
 * đọc trong hàng đợi, phân loại là thứ định tuyến. Nhưng chúng nằm gọn trên MỘT
 * hàng ở đầu khung chứ không thành một biểu mẫu riêng: người dùng vẫn thấy mình
 * đang ở trong một cuộc trò chuyện.
 *
 * Chip ở đây **điền tiêu đề** chứ không gửi thẳng — khác với chip trả lời nhanh.
 * Mở một hội thoại mới cần lời mô tả của chính người gặp sự cố; gửi ngay một
 * câu mẫu là mở một phiếu rỗng nghĩa.
 */
function NewConversation({
  subject, onSubject, category, onCategory, draft, onDraft,
  starters, busy, onSend, onCancel,
}: {
  subject: string;
  onSubject: (v: string) => void;
  category: TicketCategory;
  onCategory: (v: TicketCategory) => void;
  draft: string;
  onDraft: (v: string) => void;
  starters: string[];
  busy: boolean;
  onSend: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const subjectOk = subject.trim().length >= 5;
  const draftOk = draft.trim().length >= 10;
  const ready = subjectOk && draftOk;

  /**
   * Câu nói ra ĐÚNG thứ còn thiếu, không phải cả hai điều kiện một lượt.
   *
   * "Cần tiêu đề từ 5 ký tự và mô tả từ 10 ký tự" bắt người dùng tự đối chiếu
   * hai vế với hai ô để đoán mình sai ở đâu. Người đang bực vì một sự cố không
   * làm việc đó — họ bấm lại lần nữa rồi bỏ.
   */
  const blocked = !subjectOk
    ? t("Còn thiếu tiêu đề ở ô trên (từ 5 ký tự).")
    : !draftOk
      ? t("Mô tả cần ít nhất 10 ký tự để người trực hiểu chuyện gì đang xảy ra.")
      : "";

  return (
    <>
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="flex-1 text-sm font-semibold text-slate-900">
            {t("Hội thoại mới")}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            {t("Huỷ")}
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <label className="min-w-[12rem] flex-1">
            <span className="sr-only">{t("Tiêu đề")}</span>
            <input
              value={subject}
              onChange={(e) => onSubject(e.target.value)}
              maxLength={200}
              placeholder={t("Bạn cần giúp việc gì?")}
              className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            />
          </label>
          <label>
            <span className="sr-only">{t("Phân loại")}</span>
            <select
              value={category}
              onChange={(e) => onCategory(e.target.value as TicketCategory)}
              className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            >
              {(Object.keys(CATEGORY_LABEL) as TicketCategory[]).map((c) => (
                <option key={c} value={c}>{t(CATEGORY_LABEL[c])}</option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto max-w-lg rounded-2xl border border-dashed border-slate-300 bg-white p-4">
          <RobotIcon className="mx-auto h-8 w-8 text-slate-300" aria-hidden="true" />
          <p className="mt-2 text-center text-sm text-slate-600">
            {t("Chọn một chủ đề bên dưới, rồi mô tả cụ thể chuyện đang xảy ra. Trợ lý sẽ trả lời ngay, và người trực nhận được phiếu cùng lúc.")}
          </p>

          {/* Danh sách SỐNG, không phải một câu điều kiện tĩnh. Người dùng thấy
              từng vạch xanh lên ngay khi mình gõ, nên họ không phải đoán xem
              cái nút mờ kia đang chờ gì. */}
          <ul className="mx-auto mt-4 max-w-xs space-y-1.5 text-sm">
            <Requirement done={subjectOk} label={t("Tiêu đề, từ 5 ký tự")} />
            <Requirement done={draftOk} label={t("Mô tả, từ 10 ký tự")} />
          </ul>
        </div>
      </div>

      <QuickReplies
        items={starters}
        disabled={busy}
        onPick={(text) => onSubject(text)}
        label={t("Chủ đề thường gặp")}
      />
      {/* `disabled` CHỈ mang `busy`. Truyền `!ready` vào đây là khoá luôn ô gõ,
          và vì `ready` đòi chính nội dung ô đó nên người dùng không bao giờ gõ
          được — xem chú thích của `Composer`. */}
      <Composer
        value={draft}
        onChange={onDraft}
        onSend={onSend}
        disabled={busy}
        canSend={ready}
        blockedReason={blocked}
        minLength={10}
        autoFocus
        placeholder={t("Mô tả cụ thể: bạn đang ở màn hình nào, hệ thống hiện ra chữ gì?")}
      />
    </>
  );
}

/** Một dòng điều kiện, có dấu tick khi đã đạt. */
function Requirement({ done, label }: { done: boolean; label: string }) {
  return (
    <li
      className={`flex items-center gap-2 ${done ? "text-emerald-700" : "text-slate-500"}`}
    >
      {/* Không chỉ dựa vào MÀU: ký hiệu đổi theo trạng thái, nên người mù màu
          vẫn đọc được hàng nào đã xong. */}
      <span aria-hidden="true" className="font-semibold">
        {done ? "✓" : "○"}
      </span>
      <span>{label}</span>
    </li>
  );
}
