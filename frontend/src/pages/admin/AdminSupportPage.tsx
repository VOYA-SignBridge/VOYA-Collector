/**
 * Bàn trực hỗ trợ — `/admin/support`.
 *
 * Vì sao NHIỀU hội thoại mở cùng lúc
 * -----------------------------------
 * Bản trước là một danh sách: bấm vào một phiếu thì cả hàng đợi biến mất, trả
 * lời xong bấm "về hàng đợi" rồi tìm lại phiếu tiếp theo. Với một người trực
 * đang cầm bốn cuộc trao đổi, cách đó bắt họ giữ ngữ cảnh trong đầu — và người
 * ta không giữ được, nên họ trả lời nhầm cuộc hoặc bắt người dùng chờ.
 *
 * Nên: hàng đợi ở lại bên trái, và các cuộc đang xử lý nằm trên một hàng TAB.
 * Chuyển giữa chúng không mất gì, kể cả nội dung đang gõ dở — xem `drafts`.
 *
 * Ba quyết định nhỏ, mỗi cái vá một cách hỏng cụ thể
 * ---------------------------------------------------
 * 1. **Nội dung gõ dở lưu THEO từng hội thoại.** Một ô soạn dùng chung nghĩa là
 *    chuyển tab làm mất câu đang viết, hoặc tệ hơn, gửi nó sang nhầm người.
 * 2. **Trả lời xong KHÔNG đóng tab.** Người dùng thường nhắn lại ngay; đóng tab
 *    rồi mở lại là đúng thao tác thừa mà cả bản này sinh ra để bỏ.
 * 3. **Hàng đợi tự làm mới, tab đang mở cũng vậy.** Nhưng dừng khi tab trình
 *    duyệt bị ẩn — xem `useVisiblePoll`.
 *
 * @i18n-key-table — `key` của bộ lọc, `STATUS_LABEL`/`CATEGORY_LABEL` và bảng
 * câu trả lời mẫu là KHOÁ từ điển, dịch tại chỗ dựng.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  CATEGORY_LABEL, authorKindOf, fetchSupportQueue, fetchTicket, replyToTicket,
  setTicketStatus, STATUS_LABEL, type Ticket, type TicketStatus,
  type TicketSummary,
} from "../../api/account";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import ChatThread from "../../components/support/ChatThread";
import Composer from "../../components/support/Composer";
import QuickReplies from "../../components/support/QuickReplies";
import { InboxIcon, RobotIcon, XIcon } from "../../components/ui/Icons";
import { useVisiblePoll } from "../../hooks/useVisiblePoll";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";

const STATUS_TONE: Record<TicketStatus, "success" | "warning" | "neutral"> = {
  open: "warning",
  pending: "warning",
  resolved: "success",
  closed: "neutral",
};

/** Bộ lọc. `null` = mọi trạng thái; xem `fetchSupportQueue` về vì sao không dùng undefined. */
const FILTERS: { key: string; value: TicketStatus | null }[] = [
  { key: "Đang mở", value: "open" },
  { key: "Chờ người dùng", value: "pending" },
  { key: "Đã giải quyết", value: "resolved" },
  { key: "Tất cả", value: null },
];

/**
 * Câu trả lời mẫu của người trực.
 *
 * Ở phía trình duyệt chứ không phải máy chủ — khác với luật của trợ lý. Luật
 * của trợ lý phải nằm ở máy chủ vì chúng KHỚP từ khoá và sinh ra lời nhắn thật
 * trong bản ghi trao đổi. Những câu dưới đây chỉ điền vào ô soạn cho người trực
 * sửa lại trước khi gửi, nên chúng là tiện ích giao diện thuần tuý.
 */
const CANNED: string[] = [
  "Chào bạn, mình đã nhận được phiếu và đang kiểm tra.",
  "Bạn gửi giúp mình ảnh chụp màn hình lúc lỗi xảy ra nhé.",
  "Mình cần thêm mã phiên thu để dò đúng dữ liệu của bạn.",
  "Mình đã xử lý xong, bạn thử lại giúp mình nhé.",
];

/** Trần số tab. Người trực giữ nhiều hơn chừng này là đã mất ngữ cảnh rồi. */
const MAX_TABS = 5;
const POLL_MS = 8000;

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("vi-VN", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      });
}

export default function AdminSupportPage() {
  const { t } = useI18n();

  const [filter, setFilter] = useState<TicketStatus | null>("open");
  const [items, setItems] = useState<TicketSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  /** Các hội thoại đang mở, theo thứ tự tab. */
  const [tabs, setTabs] = useState<Ticket[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  /** Nội dung gõ dở, TÁCH theo từng hội thoại. Xem điểm 1 ở đầu tệp. */
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const run = useRef(0);
  const active = tabs.find((x) => x.ticket_id === activeId) ?? null;

  const loadQueue = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      setItems(await fetchSupportQueue(filter));
      setError("");
    } catch (err) {
      setError(friendlyError(err, t("Không tải được hàng đợi hỗ trợ.")));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [filter, t]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const refreshActive = useCallback(async () => {
    if (!activeId) return;
    const mine = ++run.current;
    try {
      const data = await fetchTicket(activeId);
      if (mine !== run.current) return;
      setTabs((list) => list.map((x) => (x.ticket_id === data.ticket_id ? data : x)));
    } catch {
      // Lượt làm mới nền hỏng thì im lặng: người trực đang đọc một cuộc trao
      // đổi, và một dải đỏ nhảy ra vì một lượt hỏi lại trượt mạng chỉ làm họ
      // mất tập trung. Lỗi ở thao tác THẬT (gửi, đổi trạng thái) vẫn hiện.
    }
  }, [activeId]);

  useVisiblePoll(() => {
    void loadQueue(true);
    void refreshActive();
  }, POLL_MS);

  const openTab = async (id: string) => {
    setActiveId(id);
    if (tabs.some((x) => x.ticket_id === id)) return;
    try {
      const data = await fetchTicket(id);
      setTabs((list) => {
        const next = [...list.filter((x) => x.ticket_id !== id), data];
        // Đầy tab thì bỏ cái CŨ NHẤT, không phải cái đang mở.
        return next.length > MAX_TABS ? next.slice(next.length - MAX_TABS) : next;
      });
    } catch (err) {
      setError(friendlyError(err, t("Không mở được hội thoại.")));
    }
  };

  const closeTab = (id: string) => {
    setTabs((list) => {
      const next = list.filter((x) => x.ticket_id !== id);
      if (id === activeId) setActiveId(next.length ? next[next.length - 1].ticket_id : "");
      return next;
    });
    setDrafts((d) => {
      const { [id]: _gone, ...rest } = d;
      return rest;
    });
  };

  const submitReply = async () => {
    const body = (drafts[activeId] ?? "").trim();
    if (!active || body.length < 2 || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await replyToTicket(active.ticket_id, body);
      run.current += 1;
      setTabs((list) => list.map((x) => (x.ticket_id === updated.ticket_id ? updated : x)));
      setDrafts((d) => ({ ...d, [active.ticket_id]: "" }));
      // Trả lời làm phiếu chuyển sang "chờ người dùng" nên nó rơi khỏi bộ lọc
      // "Đang mở". Nạp lại để hàng đợi nói đúng sự thật ngay — nhưng TAB thì
      // giữ nguyên, xem điểm 2 ở đầu tệp.
      void loadQueue(true);
    } catch (err) {
      setError(friendlyError(err, t("Không gửi được trả lời.")));
    } finally {
      setBusy(false);
    }
  };

  const resolve = async () => {
    if (!active || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await setTicketStatus(active.ticket_id, "resolved");
      setTabs((list) => list.map((x) => (x.ticket_id === updated.ticket_id ? updated : x)));
      void loadQueue(true);
    } catch (err) {
      setError(friendlyError(err, t("Không đổi được trạng thái.")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-11rem)] min-h-[34rem] flex-col">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            {t("Bàn trực hỗ trợ")}
          </h1>
          <p className="text-sm text-slate-600">
            {t("Phiếu do người dùng trong tổ chức gửi lên. Mở tối đa {n} hội thoại cùng lúc.", { n: MAX_TABS })}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => {
            const on = filter === f.value;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.value)}
                aria-pressed={on}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2 ${
                  on
                    ? "border-ctu-blue bg-ctu-blue/10 text-ctu-blue"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                {t(f.key)}
              </button>
            );
          })}
        </div>
      </div>

      {error ? (
        <p role="alert" className="mb-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[19rem_1fr]">
        {/* ------------------------------------------------------- hàng đợi */}
        <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
          <h2 className="border-b border-slate-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {t("Hàng đợi")} · {items.length}
          </h2>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <p className="p-4 text-sm text-slate-500">{t("Đang tải…")}</p>
            ) : items.length === 0 ? (
              <div className="p-6 text-center">
                <InboxIcon className="mx-auto h-8 w-8 text-slate-300" aria-hidden="true" />
                <p className="mt-2 text-sm text-slate-500">
                  {t("Chưa có phiếu hỗ trợ nào khớp bộ lọc này.")}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {items.map((row) => {
                  const on = row.ticket_id === activeId;
                  const opened = tabs.some((x) => x.ticket_id === row.ticket_id);
                  return (
                    <li key={row.ticket_id}>
                      <button
                        type="button"
                        onClick={() => void openTab(row.ticket_id)}
                        aria-current={on ? "true" : undefined}
                        className={`w-full px-3 py-2.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ctu-blue ${
                          on ? "bg-ctu-blue/5" : opened ? "bg-slate-50" : "hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">
                            {row.requester || t("không rõ")}
                          </span>
                          <Badge variant={STATUS_TONE[row.status]} size="sm">
                            {t(STATUS_LABEL[row.status])}
                          </Badge>
                        </div>
                        <p className="truncate text-xs text-slate-600">{row.subject}</p>
                        {row.last_snippet ? (
                          <p className="mt-0.5 truncate text-[11px] text-slate-400">
                            {row.last_kind === "staff" ? `${t("Bạn")}: ` : ""}
                            {row.last_snippet}
                          </p>
                        ) : null}
                        <p className="mt-0.5 text-[11px] text-slate-400">
                          {t(CATEGORY_LABEL[row.category])} · {formatWhen(row.updated_at)}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>

        {/* --------------------------------------------- khung nhiều hội thoại */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
          {tabs.length > 0 ? (
            <div role="tablist" aria-label={t("Hội thoại đang mở")}
                 className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-2 pt-2">
              {tabs.map((x) => {
                const on = x.ticket_id === activeId;
                return (
                  <div
                    key={x.ticket_id}
                    className={`flex shrink-0 items-center gap-1 rounded-t-lg border border-b-0 px-2.5 py-1.5 text-xs ${
                      on
                        ? "border-slate-200 bg-slate-50 font-semibold text-slate-900"
                        : "border-transparent text-slate-500 hover:bg-slate-50"
                    }`}
                  >
                    <button
                      type="button"
                      role="tab"
                      aria-selected={on}
                      onClick={() => setActiveId(x.ticket_id)}
                      className="max-w-[10rem] truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
                    >
                      {x.requester || x.subject}
                    </button>
                    <button
                      type="button"
                      aria-label={t("Đóng tab {ten}", { ten: x.requester || x.subject })}
                      onClick={() => closeTab(x.ticket_id)}
                      className="rounded p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
                    >
                      <XIcon className="h-3 w-3" aria-hidden="true" />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}

          {active ? (
            <>
              <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-slate-900">
                    {active.subject}
                  </h2>
                  <p className="text-xs text-slate-500">
                    {active.requester || t("không rõ")} · {t(CATEGORY_LABEL[active.category])}
                    {" · "}
                    {formatWhen(active.created_at)}
                  </p>
                </div>
                <Badge variant={STATUS_TONE[active.status]} size="sm">
                  {t(STATUS_LABEL[active.status])}
                </Badge>
                <Button size="sm" variant="secondary" onClick={() => void resolve()} disabled={busy}>
                  {t("Đã giải quyết")}
                </Button>
              </header>

              {active.messages.some((m) => authorKindOf(m) === "bot") ? (
                <p className="flex items-start gap-1.5 border-b border-slate-200 bg-amber-50/60 px-4 py-1.5 text-[11px] text-amber-800">
                  <RobotIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {t("Trợ lý tự động đã trả lời trong hội thoại này — đọc lướt qua để không nói lại cùng một điều.")}
                </p>
              ) : null}

              <ChatThread
                messages={active.messages}
                isMine={(m) => authorKindOf(m) === "staff"}
              />

              <QuickReplies
                items={CANNED}
                disabled={busy}
                label={t("Câu trả lời mẫu")}
                onPick={(text) =>
                  setDrafts((d) => ({
                    ...d,
                    // Nối vào phần đang gõ chứ không đè lên: người trực hay gõ
                    // dở rồi mới chọn mẫu, và đè lên là xoá công của họ.
                    [active.ticket_id]: d[active.ticket_id]
                      ? `${d[active.ticket_id].trimEnd()} ${text}`
                      : text,
                  }))
                }
              />
              <Composer
                value={drafts[active.ticket_id] ?? ""}
                onChange={(v) => setDrafts((d) => ({ ...d, [active.ticket_id]: v }))}
                onSend={() => void submitReply()}
                disabled={busy}
                placeholder={t("Trả lời người dùng…")}
              />
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
              <InboxIcon className="h-10 w-10 text-slate-300" aria-hidden="true" />
              <p className="mt-3 max-w-sm text-sm text-slate-500">
                {t("Chọn một phiếu trong hàng đợi để mở hội thoại. Bạn mở được nhiều cuộc cùng lúc và chuyển qua lại bằng tab.")}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
