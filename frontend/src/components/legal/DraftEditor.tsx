/**
 * Trình soạn thảo văn bản pháp lý.
 *
 * Điều quan trọng nhất trong tệp này không phải trình soạn thảo mà là **cách nó
 * xử lý xung đột ghi**.
 *
 * Máy chủ chỉ nhận lượt ghi kèm đúng số hiệu bản mà nó đang giữ. Khi có người
 * lưu trước, phản hồi là 409 kèm số hiệu mới. Cách xử lý sai — và là cách mặc
 * định nếu không nghĩ tới — là hiện "Lưu thất bại, hãy tải lại trang", tức là
 * **vứt đi đoạn người dùng vừa gõ**. Với một văn bản pháp lý dài vài nghìn chữ
 * thì đó là mất bài thật.
 *
 * Ở đây, xung đột giữ nguyên nội dung trong ô soạn thảo và đưa ra hai lựa chọn
 * tường minh: xem bản của người kia, hoặc ghi đè bằng bản của mình. Không tự
 * động làm cái nào — hợp nhất hai bản văn pháp lý là việc của con người.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import Markdown from "../Markdown";
import { useI18n } from "../../i18n";
import {
  DRAFT_STATUS_LABEL,
  LEGAL_KIND_LABEL,
  RevisionConflict,
  fetchDraft,
  publishDraft,
  saveDraft,
  setDraftStatus,
  type DraftStatus,
  type LegalDraft,
} from "../../api/legal";

/** Chuyển trạng thái nào hiện thành nút. Phải khớp `legal.DRAFT_TRANSITIONS`. */
const NEXT_STATUS: Record<DraftStatus, DraftStatus[]> = {
  draft: ["in_review", "discarded"],
  in_review: ["approved", "draft", "discarded"],
  approved: ["draft", "discarded"],
  published: [],
  discarded: [],
};

const STATUS_CHIP: Record<DraftStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  in_review: "bg-amber-100 text-amber-800",
  approved: "bg-sky-100 text-sky-800",
  published: "bg-sky-100 text-sky-800",
  discarded: "bg-slate-100 text-slate-400",
};

/** `datetime-local` cần `YYYY-MM-DDTHH:mm`, không nhận hậu tố múi giờ. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function messageOf(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: unknown } } };
  const detail = e.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const obj = detail as { message?: string };
    if (obj.message) return obj.message;
  }
  return err instanceof Error ? err.message : fallback;
}

export interface DraftEditorProps {
  draft: LegalDraft;
  onChanged: (draft: LegalDraft) => void;
  onPublished: (message: string) => void;
  /** Trả về true khi đã nâng quyền xong; false khi người dùng bỏ dở. */
  ensureSudo: () => Promise<boolean>;
}

export default function DraftEditor({
  draft,
  onChanged,
  onPublished,
  ensureSudo,
}: DraftEditorProps) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    title: draft.title,
    body: draft.body ?? "",
    change_summary: draft.change_summary,
    target_version: draft.target_version,
    requires_reconsent: draft.requires_reconsent,
    effective_from: toLocalInput(draft.effective_from),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState<{ message: string; theirBody: string } | null>(
    null,
  );
  const [showPreview, setShowPreview] = useState(false);

  // Nạp lại biểu mẫu khi CHUYỂN sang một bản nháp khác, không phải mỗi lần
  // `draft` đổi tham chiếu: sau một lần lưu, `draft` là đối tượng mới với cùng
  // `draft_id`, và nạp lại khi đó sẽ giật con trỏ về đầu ô soạn thảo.
  const loadedId = useRef(draft.draft_id);
  useEffect(() => {
    if (loadedId.current === draft.draft_id) return;
    loadedId.current = draft.draft_id;
    setForm({
      title: draft.title,
      body: draft.body ?? "",
      change_summary: draft.change_summary,
      target_version: draft.target_version,
      requires_reconsent: draft.requires_reconsent,
      effective_from: toLocalInput(draft.effective_from),
    });
    setConflict(null);
    setError("");
  }, [draft]);

  const editable = draft.status === "draft" || draft.status === "in_review";

  const dirty = useMemo(
    () =>
      form.title !== draft.title ||
      form.body !== (draft.body ?? "") ||
      form.change_summary !== draft.change_summary ||
      form.target_version !== draft.target_version ||
      form.requires_reconsent !== draft.requires_reconsent ||
      form.effective_from !== toLocalInput(draft.effective_from),
    [form, draft],
  );

  const handleConflict = async (err: unknown) => {
    if (!(err instanceof RevisionConflict)) {
      setError(messageOf(err, t("Không lưu được.")));
      return;
    }
    // Kéo về bản của người kia để người soạn ĐỌC ĐƯỢC nó cạnh bản mình —
    // nhưng không ghi đè ô soạn thảo. Xem chú thích đầu tệp.
    let theirBody = "";
    try {
      theirBody = (await fetchDraft(draft.draft_id)).body ?? "";
    } catch {
      theirBody = t("(không đọc được bản trên máy chủ)");
    }
    setConflict({ message: err.message, theirBody });
  };

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const updated = await saveDraft(draft.draft_id, draft.revision, {
        title: form.title,
        body: form.body,
        change_summary: form.change_summary,
        target_version: form.target_version,
        requires_reconsent: form.requires_reconsent,
        effective_from: form.effective_from
          ? new Date(form.effective_from).toISOString()
          : null,
      });
      setConflict(null);
      onChanged(updated);
    } catch (err) {
      await handleConflict(err);
    } finally {
      setBusy(false);
    }
  };

  const advance = async (status: DraftStatus) => {
    setBusy(true);
    setError("");
    try {
      onChanged(await setDraftStatus(draft.draft_id, draft.revision, status));
    } catch (err) {
      await handleConflict(err);
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    setBusy(true);
    setError("");
    try {
      let result = await publishDraft(draft.draft_id, draft.revision).catch(
        async (err: unknown) => {
          const e = err as { response?: { data?: { detail?: { code?: string } } } };
          if (e.response?.data?.detail?.code !== "sudo_required") throw err;
          if (!(await ensureSudo())) return null;
          return publishDraft(draft.draft_id, draft.revision);
        },
      );
      if (!result) return;
      const scheduled = result.current?.version !== result.draft.published_version;
      onChanged(result.draft);
      onPublished(
        scheduled
          ? `Đã lên lịch bản ${result.draft.published_version}. Bản đang áp dụng vẫn là ${
              result.current?.version ?? t("(chưa có)")
            }.`
          : t("Đã công bố bản {published_version}. Bản này đang áp dụng.", { published_version: result.draft.published_version }),
      );
    } catch (err) {
      await handleConflict(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="font-semibold text-slate-900">
          {t(LEGAL_KIND_LABEL[draft.kind])}
        </h3>
        <span className={`rounded px-2 py-0.5 text-xs ${STATUS_CHIP[draft.status]}`}>
          {t(DRAFT_STATUS_LABEL[draft.status])}
        </span>
        <span className="text-xs text-slate-400" data-testid="revision">
          bản ghi #{draft.revision}
        </span>
        {draft.based_on_version && (
          <span className="text-xs text-slate-400">
            dựa trên {draft.based_on_version}
          </span>
        )}
      </div>

      {conflict && (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm">
          <p className="font-semibold text-amber-900">{conflict.message}</p>
          <p className="mt-1 text-amber-800">
            {t("Bài bạn vừa gõ vẫn còn nguyên trong ô bên dưới. Đọc bản của họ rồi tự hợp nhất — chúng tôi không tự trộn hai bản văn pháp lý.")}
          </p>
          <details className="mt-2">
            <summary className="cursor-pointer text-amber-900 underline">
              {t("Xem bản đang có trên máy chủ")}
            </summary>
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-white p-3 text-xs">
              {conflict.theirBody}
            </pre>
          </details>
          <button
            type="button"
            onClick={async () => {
              const fresh = await fetchDraft(draft.draft_id);
              setConflict(null);
              onChanged(fresh);
            }}
            className="mt-3 rounded-lg border border-amber-400 px-3 py-1.5 text-xs font-semibold text-amber-900"
          >
            {t("Nạp số hiệu mới (giữ nguyên bài của tôi)")}
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-600">{t("Tiêu đề")}</span>
          <input
            value={form.title}
            disabled={!editable}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">{t("Số hiệu phiên bản")}</span>
          <input
            value={form.target_version}
            disabled={!editable}
            placeholder="2026-09-01"
            onChange={(e) =>
              setForm((f) => ({ ...f, target_version: e.target.value }))
            }
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono disabled:bg-slate-50"
          />
        </label>
      </div>

      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm text-slate-600">{t("Nội dung (Markdown)")}</span>
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="text-xs font-semibold text-ctu-blue hover:underline"
          >
            {showPreview ? t("Ẩn xem trước") : t("Xem trước")}
          </button>
        </div>
        <div className={showPreview ? "grid gap-3 lg:grid-cols-2" : ""}>
          <textarea
            aria-label={t("Nội dung")}
            value={form.body}
            disabled={!editable}
            onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
            rows={18}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs disabled:bg-slate-50"
          />
          {showPreview && (
            <div className="max-h-[28rem] overflow-auto rounded-lg border border-slate-200 bg-white p-4">
              <Markdown text={form.body} />
            </div>
          )}
        </div>
      </div>

      <label className="mt-3 block text-sm">
        <span className="text-slate-600">{t("Bản này khác bản trước ở chỗ nào")}</span>
        <textarea
          value={form.change_summary}
          disabled={!editable}
          rows={2}
          onChange={(e) =>
            setForm((f) => ({ ...f, change_summary: e.target.value }))
          }
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
        />
      </label>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-600">{t("Hiệu lực từ (bỏ trống = ngay)")}</span>
          <input
            type="datetime-local"
            value={form.effective_from}
            disabled={!editable}
            onChange={(e) =>
              setForm((f) => ({ ...f, effective_from: e.target.value }))
            }
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50"
          />
        </label>
        <label className="flex items-start gap-2 pt-6 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={form.requires_reconsent}
            disabled={!editable}
            onChange={(e) =>
              setForm((f) => ({ ...f, requires_reconsent: e.target.checked }))
            }
            className="mt-0.5 h-4 w-4 rounded border-slate-300"
          />
          <span>
            {t("Buộc đồng ý lại")}
            <span className="block text-xs text-slate-500">
              {t("Chỉ bật khi thay đổi mở rộng phạm vi xử lý dữ liệu. Bật vì một lỗi chính tả sẽ dạy người dùng bấm đồng ý mà không đọc.")}
            </span>
          </span>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {editable && (
          <button
            type="button"
            onClick={save}
            disabled={busy || !dirty}
            className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? t("Đang lưu…") : t("Lưu")}
          </button>
        )}
        {NEXT_STATUS[draft.status].map((next) => (
          <button
            key={next}
            type="button"
            onClick={() => advance(next)}
            disabled={busy || dirty}
            title={dirty ? t("Lưu thay đổi trước đã") : undefined}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            {t(DRAFT_STATUS_LABEL[next])}
          </button>
        ))}
        {draft.status === "approved" && (
          <button
            type="button"
            onClick={publish}
            disabled={busy}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {t("Công bố")}
          </button>
        )}
      </div>
    </div>
  );
}
