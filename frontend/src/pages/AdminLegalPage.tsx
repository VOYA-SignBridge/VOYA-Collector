/**
 * Quản trị văn bản pháp lý: soạn thảo, công bố, tra sổ đăng bạ, đo độ phủ.
 *
 * Bốn điều màn hình này cố ý làm khác thói quen thường gặp
 * ---------------------------------------------------------
 * **Không có nút Sửa trên bản đã công bố.** Sửa một bản đã công bố là viết lại
 * bản văn nằm dưới những chữ ký đã thu; cơ sở dữ liệu chặn việc đó bằng
 * trigger. Không dựng một nút đi tới bức tường ấy chỉ để hiện lỗi. Muốn đổi thì
 * mở bản nháp mới — đó là cả luồng bên dưới.
 *
 * **Không có đường công bố thẳng.** Trước đây trang này có một biểu mẫu dán nội
 * dung rồi bấm Công bố. Nó đã bị thay bằng luồng nháp → rà soát → phê duyệt,
 * vì một bản văn pháp lý ra khỏi tay một người mà không ai đọc lại là đúng thứ
 * quy trình tồn tại để chặn. Đường thẳng vẫn còn ở CLI cho kịch bản triển khai.
 *
 * **Hai con số cho "đã đồng ý".** `accepted` gộp tất cả; `accepted_by_user` chỉ
 * đếm những lượt người dùng tự bấm. Gộp lại là để bảng điều khiển báo "100% đã
 * đồng ý" trong khi không ai bấm nút nào.
 *
 * **Công bố đòi nhập lại mật khẩu.** Cùng luật với thay đổi thiết lập nền tảng.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import DocumentViewer from "../components/legal/DocumentViewer";
import Badge from "../components/ui/Badge";
import Tabs, { useUrlTab } from "../components/ui/Tabs";
import DraftEditor from "../components/legal/DraftEditor";
import {
  DRAFT_STATUS_LABEL,
  LEGAL_KIND_LABEL,
  adminDocumentFileUrl,
  createDraft,
  fetchAdminOverview,
  fetchAnyVersion,
  fetchDraft,
  fetchDrafts,
  fetchEvents,
  type LegalAdminOverview,
  type LegalDocumentContent,
  type LegalDocumentRow,
  type LegalDraft,
  type LegalEvent,
  type LegalKind,
} from "../api/legal";
import { useSudo } from "../hooks/useSudo";
import UploadDocumentForm from "../components/legal/UploadDocumentForm";
import { Trans, useI18n } from "../i18n";

const KINDS = Object.keys(LEGAL_KIND_LABEL) as LegalKind[];

function errorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: unknown } } };
  const detail = e.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const obj = detail as { message?: string };
    if (obj.message) return obj.message;
  }
  return fallback;
}

export default function AdminLegalPage() {
  const { t } = useI18n();
  const [overview, setOverview] = useState<LegalAdminOverview | null>(null);
  const [drafts, setDrafts] = useState<LegalDraft[]>([]);
  const [openDraft, setOpenDraft] = useState<LegalDraft | null>(null);
  const [events, setEvents] = useState<LegalEvent[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<{ title: string; doc: LegalDocumentContent } | null>(null);
  const [newDraftKind, setNewDraftKind] = useState<LegalKind>("terms");

  const tabs = useMemo(() => [
    { id: "overview", label: t("Tổng quan") },
    { id: "compose", label: t("Soạn & duyệt"), count: drafts.filter((d) => d.status !== "published").length },
    { id: "versions", label: t("Phiên bản"), count: overview?.documents.length ?? 0 },
    { id: "consents", label: t("Chấp thuận") },
    { id: "events", label: t("Lịch sử") },
  ] as const, [t, drafts, overview]);
  const [tab, setTab] = useUrlTab("tab", tabs, "overview");

  const load = useCallback(async () => {
    try {
      const [o, d, e] = await Promise.all([
        fetchAdminOverview(),
        fetchDrafts(),
        fetchEvents(undefined, 60),
      ]);
      setOverview(o);
      setDrafts(d);
      setEvents(e);
    } catch (err) {
      setError(errorMessage(err, t("Không tải được danh sách văn bản.")));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /**
   * Nâng quyền khi máy chủ đòi. Cùng một hàm với trang Gói dịch vụ — xem
   * `hooks/useSudo` về lý do dùng `window.prompt` cho mật khẩu.
   */
  const { ensureSudo: askForSudo } = useSudo();
  const ensureSudo = useCallback(async () => {
    const ok = await askForSudo(t("Công bố văn bản pháp lý"));
    if (!ok) setError(t("Mật khẩu không đúng, hoặc bạn đã huỷ."));
    return ok;
  }, [askForSudo]);

  const onDraftChanged = useCallback(
    async (updated: LegalDraft) => {
      // Đọc lại đầy đủ (kèm thân bài) rồi mới đặt vào state: phản hồi của các
      // endpoint đổi trạng thái cố ý KHÔNG mang `body`, và đặt thẳng nó vào sẽ
      // làm ô soạn thảo trống trơn sau mỗi lần bấm nút trạng thái.
      const full = updated.body === undefined
        ? await fetchDraft(updated.draft_id).catch(() => updated)
        : updated;
      setOpenDraft(full);
      setDrafts((list) =>
        list.map((d) => (d.draft_id === full.draft_id ? full : d)),
      );
      void load();
    },
    [load],
  );

  const startDraft = async () => {
    setError("");
    try {
      const created = await createDraft(newDraftKind, true);
      setDrafts((list) => [created, ...list]);
      setOpenDraft(created);
    } catch (err) {
      setError(errorMessage(err, t("Không mở được bản nháp.")));
    }
  };

  const byKind = useMemo(() => {
    const groups = new Map<LegalKind, LegalDocumentRow[]>();
    for (const row of overview?.documents ?? []) {
      const list = groups.get(row.kind) ?? [];
      list.push(row);
      groups.set(row.kind, list);
    }
    return groups;
  }, [overview]);

  const openPreview = async (row: LegalDocumentRow) => {
    try {
      const doc = await fetchAnyVersion(row.kind, row.version);
      // Giữ NGUYÊN document, không rút riêng `body`: với tệp tải lên `body`
      // rỗng và bản trước hiện một khung trắng (LEG-01). Viewer chọn cách dựng
      // theo `body_format`, và dùng đường quản trị để thấy cả bản đã lên lịch.
      setPreview({ title: t("{p1} — bản {version}", { p1: t(LEGAL_KIND_LABEL[row.kind]), version: row.version }), doc });
    } catch (err) {
      setError(errorMessage(err, t("Không đọc được bản văn.")));
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-900">{t("Văn bản pháp lý")}</h1>
      <p className="mt-1 text-sm text-slate-500">
        {t("Nội dung một bản đã công bố không sửa được. Muốn đổi thì công bố phiên bản mới.")}
      </p>

      {overview && overview.missing_required.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">
            {t("Chưa công bố: {ds}", { ds: overview.missing_required.map((k) => t(LEGAL_KIND_LABEL[k])).join(", ") })}
          </p>
          <p className="mt-1">
            {t("Khi chưa công bố, đăng ký vẫn chạy nhưng")} <strong>{t("không thu chấp thuận nào")}</strong>.
          </p>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-6">
        <Tabs tabs={tabs} value={tab} onChange={setTab} label={t("Mục của trang văn bản pháp lý")}>
      {tab === "overview" && (
        <section className="space-y-6">
          {/* Mỗi loại một thẻ: bản đang áp dụng, bản chờ, nháp đang mở. Người
              quản trị nhìn một lượt biết "còn thiếu gì" mà không cần đọc bảng. */}
          <div className="grid gap-3 sm:grid-cols-2">
            {KINDS.map((k) => {
              const rows = byKind.get(k) ?? [];
              const current = rows.find((r) => r.status === "current");
              const scheduled = rows.filter((r) => r.status === "scheduled");
              const openDrafts = drafts.filter((d) => d.kind === k && d.status !== "published");
              const required = overview?.required_at_registration.includes(k);
              return (
                <div key={k} className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-slate-900">{t(LEGAL_KIND_LABEL[k])}</h3>
                    {current ? (
                      <Badge variant="success" size="sm">{t("đang áp dụng")}</Badge>
                    ) : (
                      <Badge variant={required ? "danger" : "neutral"} size="sm">{t("chưa công bố")}</Badge>
                    )}
                  </div>
                  <dl className="mt-2 space-y-1 text-sm text-slate-600">
                    <div className="flex justify-between gap-3">
                      <dt>{t("Bản đang áp dụng")}</dt>
                      <dd className="font-mono text-xs text-slate-800">{current?.version ?? "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt>{t("Đã lên lịch")}</dt>
                      <dd className="text-slate-800">{scheduled.length ? scheduled.map((r) => r.version).join(", ") : "—"}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt>{t("Nháp đang mở")}</dt>
                      <dd className="text-slate-800 tabular-nums">{openDrafts.length || "—"}</dd>
                    </div>
                  </dl>
                  {required && !current && (
                    <p className="mt-2 text-xs text-red-700">
                      {t("Bắt buộc lúc đăng ký. Chưa công bố thì không thu được chấp thuận nào.")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <p className="font-medium text-slate-900">{t("Bắt đầu từ đâu?")}</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              <li>{t("Có văn bản mới hoặc bản sửa: mở mục “Soạn & duyệt”, tải tệp hoặc viết trong hệ thống.")}</li>
              <li>{t("Muốn biết ai đã đồng ý bản nào: mở mục “Chấp thuận”.")}</li>
              <li>{t("Cần đối chiếu ai đã làm gì: mở mục “Lịch sử”.")}</li>
            </ul>
          </div>
        </section>
      )}
      {tab === "compose" && (
        <section>
          <h2 className="text-lg font-semibold text-slate-900">{t("Tạo phiên bản mới")}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {t("Một trong hai cách: tải tệp đã ký (PDF/DOCX) — đường thường dùng, hoặc viết nội dung trong hệ thống rồi duyệt qua bản nháp. Cả hai đều ra một phiên bản có số hiệu, không sửa được sau khi công bố.")}
          </p>
      {/* Tải tệp lên đứng TRƯỚC trình soạn markdown, vì với văn bản pháp lý
          thật thì đây là đường thường dùng: phòng pháp chế gửi .docx, bản đã
          ký và đóng dấu về dưới dạng .pdf. Trình soạn markdown ở dưới vẫn còn
          cho những bản viết ngay trong hệ thống. */}
      <div className="mt-4">
        <UploadDocumentForm onDone={() => void load()} ensureSudo={ensureSudo} />
      </div>
      {notice && (
        <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          {notice}
        </div>
      )}


          <div className="mt-8 border-t border-slate-200 pt-6">
      {/* ------------------------------------------------------ bản nháp */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900">{t("Bản nháp")}</h2>
          <div className="flex items-center gap-2">
            <select
              aria-label={t("Loại văn bản cần soạn")}
              value={newDraftKind}
              onChange={(e) => setNewDraftKind(e.target.value as LegalKind)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(LEGAL_KIND_LABEL[k])}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={startDraft}
              className="rounded-lg bg-ctu-blue px-4 py-1.5 text-sm font-semibold text-white"
            >
              {t("Soạn bản mới")}
            </button>
          </div>
        </div>

        {drafts.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            {t("Không có bản nháp nào đang mở. Bản mới sẽ chép sẵn nội dung bản đang hiệu lực làm điểm xuất phát.")}
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {drafts.map((d) => (
              <li key={d.draft_id}>
                <button
                  type="button"
                  onClick={async () =>
                    setOpenDraft(
                      openDraft?.draft_id === d.draft_id
                        ? null
                        : await fetchDraft(d.draft_id),
                    )
                  }
                  className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-4 py-2 text-left text-sm hover:bg-slate-50"
                >
                  <span className="font-medium text-slate-800">
                    {t(LEGAL_KIND_LABEL[d.kind])}
                    {d.target_version && (
                      <span className="ml-2 font-mono text-xs text-slate-500">
                        {d.target_version}
                      </span>
                    )}
                  </span>
                  <span className="flex items-center gap-3 text-xs text-slate-500">
                    <span>{t(DRAFT_STATUS_LABEL[d.status])}</span>
                    <span>#{d.revision}</span>
                    <span>{new Date(d.updated_at).toLocaleString("vi-VN")}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {openDraft && (
          <div className="mt-4">
            <DraftEditor
              draft={openDraft}
              onChanged={onDraftChanged}
              onPublished={(message) => {
                setNotice(message);
                void load();
              }}
              ensureSudo={ensureSudo}
            />
          </div>
        )}
      </section>

          </div>
        </section>
      )}
      {tab === "versions" && (<>
      {/* ---------------------------------------------------- lịch sử bản */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">{t("Các bản đã công bố")}</h2>
        {KINDS.map((kind) => {
          const rows = byKind.get(kind) ?? [];
          return (
            <div key={kind} className="mt-4">
              <h3 className="text-sm font-semibold text-slate-700">
                {t(LEGAL_KIND_LABEL[kind])}
              </h3>
              {rows.length === 0 ? (
                <p className="mt-1 text-sm text-slate-400">{t("Chưa công bố bản nào.")}</p>
              ) : (
                <div className="mt-1 overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                        <th className="px-3 py-1.5">{t("Bản")}</th>
                        <th className="px-3 py-1.5">{t("Trạng thái")}</th>
                        <th className="px-3 py-1.5">{t("Hiệu lực từ")}</th>
                        <th className="px-3 py-1.5 text-right">{t("Chữ ký")}</th>
                        <th className="px-3 py-1.5 text-right">{t("Độ dài")}</th>
                        <th className="px-3 py-1.5" />
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.doc_id} className="border-b border-slate-100">
                          <td className="px-3 py-1.5 font-mono text-xs">{row.version}</td>
                          <td className="px-3 py-1.5">
                            {/* Ba trạng thái từ máy chủ, không suy ở đây. Màu KHÔNG
                                là kênh duy nhất: chữ khác nhau ở cả ba. */}
                            {row.status === "current" && (
                              <span className="rounded bg-ctu-blue/10 px-2 py-0.5 text-xs font-medium text-ctu-blue">
                                {t("đang áp dụng")}
                              </span>
                            )}
                            {row.status === "superseded" && (
                              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                                {t("đã thay thế")}
                              </span>
                            )}
                            {row.status === "scheduled" && (
                              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                                {t("đã lên lịch")}
                              </span>
                            )}
                            {row.requires_reconsent && (
                              <span className="ml-1 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                                {t("đồng ý lại")}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-1.5 text-xs">
                            {new Date(row.effective_from).toLocaleString("vi-VN")}
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums">
                            {row.consent_count}
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums text-xs text-slate-500">
                            {row.body_length.toLocaleString("vi-VN")}
                          </td>
                          <td className="px-3 py-1.5 text-right">
                            <button
                              type="button"
                              onClick={() => void openPreview(row)}
                              className="text-xs font-semibold text-ctu-blue hover:underline"
                            >
                              Xem
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </section>

      </>)}
      {tab === "consents" && (<>
      {/* ------------------------------------------------------- độ phủ */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">{t("Độ phủ chấp thuận")}</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b-2 border-slate-300 text-left">
                <th className="px-3 py-2">{t("Loại")}</th>
                <th className="px-3 py-2">{t("Bản hiện hành")}</th>
                <th className="px-3 py-2 text-right">{t("Tài khoản")}</th>
                <th className="px-3 py-2 text-right">{t("Đã đồng ý")}</th>
                <th className="px-3 py-2 text-right">{t("Người dùng tự bấm")}</th>
                <th className="px-3 py-2 text-right">{t("Còn thiếu")}</th>
              </tr>
            </thead>
            <tbody>
              {(overview?.coverage ?? []).map((row) => (
                <tr key={row.kind} className="border-b border-slate-200">
                  <td className="px-3 py-2">{t(LEGAL_KIND_LABEL[row.kind])}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.version ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.accounts}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.accepted}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.accepted_by_user}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.missing}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {t("Chênh lệch giữa")} <em>{t("Đã đồng ý")}</em> {t("và")} <em>{t("Người dùng tự bấm")}</em> {t("là số dòng do người vận hành ghi hộ. Chúng không phải chữ ký.")}
        </p>
      </section>

      </>)}
      {tab === "events" && (<>
      {/* ------------------------------------------------- sổ đăng bạ */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">{t("Sổ đăng bạ")}</h2>
        <p className="mt-1 text-sm text-slate-500">
          <Trans
            k="Ai làm gì, lên đối tượng nào, lúc nào. Sổ này {khong_chua} — nó được đọc và chuyển tiếp thường xuyên hơn bảng văn bản."
            vars={{
              khong_chua: (
                <strong>{t("không bao giờ chứa nội dung văn bản")}</strong>
              ),
            }}
          />
        </p>
        {events.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">{t("Chưa có sự kiện nào.")}</p>
        ) : (
          <ol className="mt-3 space-y-1">
            {events.map((e) => (
              <li
                key={e.event_id}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-b border-slate-100 py-1.5 text-sm"
              >
                <time className="w-40 shrink-0 tabular-nums text-xs text-slate-500">
                  {new Date(e.occurred_at).toLocaleString("vi-VN")}
                </time>
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                  {e.action}
                </code>
                <span className="text-slate-700">
                  {e.kind ? t(LEGAL_KIND_LABEL[e.kind]) : "—"}
                  {e.version && (
                    <span className="ml-1 font-mono text-xs text-slate-500">
                      {e.version}
                    </span>
                  )}
                  {e.revision != null && (
                    <span className="ml-1 text-xs text-slate-400">#{e.revision}</span>
                  )}
                </span>
                <span className="text-xs text-slate-500">{e.actor || "—"}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
      </>)}
        </Tabs>
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
          <div className="my-8 w-full max-w-3xl rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">{preview.title}</h3>
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="rounded-lg px-3 py-1 text-sm text-slate-500 hover:bg-slate-100"
              >
                {t("Đóng")}
              </button>
            </div>
            <DocumentViewer
              doc={preview.doc}
              fileUrl={(d, o) => adminDocumentFileUrl(d.kind, d.version, o)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
