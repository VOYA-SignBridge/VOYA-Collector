/**
 * Văn bản pháp lý: đọc công khai, công bố qua đường quản trị.
 *
 * Hai kiểu dữ liệu tách riêng và đó là chủ ý: `LegalDocument` KHÔNG có `body`.
 * Đường `/legal/{kind}` được gọi mỗi lần dựng biểu mẫu đăng ký và chỉ cần số
 * hiệu phiên bản; kiểu dữ liệu nói ra điều đó thì không ai vô tình viết một
 * màn hình đọc điều khoản dựa trên nó rồi thắc mắc vì sao trang trắng.
 *
 * @i18n-key-table — chữ tiếng Việt trong tệp này là KHOÁ từ điển; bảng nhãn
 * xuất khẩu ở đây được dịch tại chỗ dùng bằng `t(BANG[x])`.
 */

import axiosClient, { getApiBaseURL } from "./axiosClient";
import { tr } from "../i18n";

const PUBLIC_PREFIX = "/api/v1/legal";
const ADMIN_PREFIX = "/api/v1/admin/legal";

export type LegalKind = "terms" | "privacy" | "data_contribution" | "guardian";

export const LEGAL_KIND_LABEL: Record<LegalKind, string> = {
  terms: "Điều khoản sử dụng",
  privacy: "Chính sách quyền riêng tư",
  data_contribution: "Đồng ý đóng góp dữ liệu",
  guardian: "Đồng ý của người giám hộ",
};

/** Siêu dữ liệu. Không kèm thân văn bản — xem chú thích đầu tệp. */
export interface LegalDocument {
  kind: LegalKind;
  version: string;
  url: string;
  title: string;
  language: string;
  effective_from: string;
  change_summary: string;
  content_hash: string;
  requires_reconsent: boolean;
  /**
   * Bản văn này là một TỆP tải lên (pdf/docx/odt) hay là markdown gõ trong
   * ứng dụng. Giao diện chọn trình đọc theo cờ này.
   *
   * `file_key` — đường trong kho blob của máy chủ — CỐ Ý không có ở đây. Một
   * đường lưu trữ nội bộ nằm trong phản hồi công khai là một lời mời dò kho.
   */
  has_file: boolean;
  file_name: string | null;
  file_mime: string | null;
  file_size: number | null;
}

export interface LegalDocumentContent extends LegalDocument {
  /** Rỗng khi `body_format === "file"` — nội dung nằm ở tệp, không ở đây. */
  body: string;
  body_format: "markdown" | "text" | "file";
}

/**
 * Đường tải tệp gốc của một bản văn.
 *
 * CÔNG KHAI, cùng lý do như `/content`: phải đọc được trước khi có tài khoản.
 * Trả về đường dẫn chứ không phải blob — trình duyệt tự tải, nên PDF nhúng
 * được thẳng vào `<object>` mà không cần đi qua JavaScript và một `blob:` URL
 * phải nhớ thu hồi.
 *
 * `download=true` buộc tải về; bỏ trống để trình duyệt tự mở.
 */
export function documentFileUrl(
  kind: LegalKind,
  opts: { version?: string; download?: boolean } = {},
): string {
  const params = new URLSearchParams();
  if (opts.version) params.set("version", opts.version);
  if (opts.download) params.set("download", "true");
  const qs = params.toString();
  // Gắn base path bằng tay. Đường này đi vào `<object data=...>` và
  // `<a href=...>`, tức KHÔNG qua axios — nên bộ chặn request vốn thêm tiền tố
  // cho mọi lời gọi không chạm tới nó. Thiếu bước này thì tệp 404 trên mọi bản
  // triển khai đặt ứng dụng dưới một thư mục con (máy CTU chạy dưới `/voya`).
  const base = getApiBaseURL().replace(/\/+$/, "").replace(/\/api$/, "");
  return `${base}${PUBLIC_PREFIX}/${kind}/file${qs ? `?${qs}` : ""}`;
}

/** Một dòng ở màn hình quản trị: mọi bản, kể cả bản chưa tới ngày hiệu lực. */
export interface LegalDocumentRow extends LegalDocument {
  doc_id: string;
  body_length: number;
  is_effective: boolean;
  consent_count: number;
  published_at: string;
  published_by: string | null;
}

export interface ConsentCoverage {
  kind: LegalKind;
  version: string | null;
  accounts: number;
  accepted: number;
  /** Tách riêng vì một dòng ghi hộ KHÔNG phải chữ ký. Xem docs/04-legal/LEGAL_DOCUMENTS.md. */
  accepted_by_user: number;
  missing: number;
}

export interface LegalAdminOverview {
  documents: LegalDocumentRow[];
  kinds: LegalKind[];
  required_at_registration: LegalKind[];
  missing_required: LegalKind[];
  coverage: ConsentCoverage[];
}

export interface PublishPayload {
  kind: LegalKind;
  version: string;
  title: string;
  body: string;
  change_summary?: string;
  language?: string;
  requires_reconsent?: boolean;
  /** ISO 8601. Bỏ trống = hiệu lực ngay; đặt tương lai = lên lịch. */
  effective_from?: string | null;
}

// ------------------------------------------------------------------ công khai

export async function listPublishedDocuments(): Promise<LegalDocument[]> {
  const res = await axiosClient.get(`${PUBLIC_PREFIX}/documents`);
  return (res.data?.documents ?? []) as LegalDocument[];
}

export async function fetchDocument(kind: LegalKind): Promise<LegalDocument> {
  const res = await axiosClient.get(`${PUBLIC_PREFIX}/${kind}`);
  return res.data as LegalDocument;
}

export async function fetchContent(
  kind: LegalKind,
  version?: string,
): Promise<LegalDocumentContent> {
  const res = await axiosClient.get(`${PUBLIC_PREFIX}/${kind}/content`, {
    params: version ? { version } : undefined,
  });
  return res.data as LegalDocumentContent;
}

/**
 * Bản đang hiệu lực của một loại, hoặc `null` khi hệ thống chưa công bố gì.
 *
 * "Chưa công bố" là trạng thái BÌNH THƯỜNG, không phải lỗi: công bố chính là
 * hành động bật cưỡng chế, nên một bản triển khai mới chưa có văn bản nào vẫn
 * cho đăng ký. Biểu mẫu đăng ký dùng hàm này để biết có phải hỏi đồng ý không,
 * và nó không được sập chỉ vì câu trả lời là "không".
 */
export async function fetchDocumentOrNull(
  kind: LegalKind,
): Promise<LegalDocument | null> {
  try {
    return await fetchDocument(kind);
  } catch {
    return null;
  }
}

// -------------------------------------------------- chấp thuận của chính mình

/** Mức dữ liệu mà việc ký một văn bản CẤP. Thang tăng dần, không phải ba ô rời. */
export type ConsentScope =
  | "internal_training"
  | "research_release"
  | "public_library";

export const CONSENT_SCOPE_LABEL: Record<ConsentScope, string> = {
  internal_training: "Huấn luyện nội bộ trong tổ chức của bạn",
  research_release: "Công bố cùng bài báo, chia sẻ ra ngoài tổ chức",
  public_library: "Thư viện công khai",
};

export interface MyConsent {
  kind: LegalKind;
  title: string;
  /** Bản đang hiệu lực. Có thể khác bản mình đã ký. */
  current_version: string;
  accepted: boolean;
  /** Bản MÌNH đã ký. `null` khi chưa từng ký. Dùng để mở lại đúng bản đó. */
  accepted_version: string | null;
  accepted_at: string | null;
  /** Đã ký một bản cũ, bản mới đòi ký lại. KHÁC "chưa ký bao giờ". */
  needs_reconsent: boolean;
  required_at_registration: boolean;
  /**
   * Ký được MỘT LẦN cho cả tài khoản hay không.
   *
   * `false` với `guardian`: bản văn ấy tự nói nó được hỏi trong từng buổi ghi
   * hình. Trang tài khoản vẫn liệt kê nó để đọc trước, nhưng không đưa nút ký.
   */
  self_signable: boolean;
  /** Máy chủ quyết định, không phải giao diện suy ra — xem chú thích ở router. */
  withdrawable: boolean;
  grants_scope: ConsentScope | null;
}

export async function fetchMyConsents(): Promise<MyConsent[]> {
  const res = await axiosClient.get(`${PUBLIC_PREFIX}/me/consents`);
  return (res.data?.consents ?? []) as MyConsent[];
}

/**
 * Ký một văn bản.
 *
 * `version` phải là bản ĐANG hiệu lực — máy chủ đối chiếu và trả 409
 * `stale_version` nếu lệch. Vì thế luôn gửi `current_version` vừa đọc được,
 * không bao giờ gửi `accepted_version` (bản cũ) hay một hằng số.
 */
export async function acceptDocument(kind: LegalKind, version: string) {
  const res = await axiosClient.post(`${PUBLIC_PREFIX}/${kind}/accept`, { version });
  return res.data as { kind: LegalKind; accepted: true; version: string };
}

/** Rút chấp thuận. 409 với văn bản bắt buộc để dùng hệ thống. */
export async function withdrawDocument(kind: LegalKind) {
  const res = await axiosClient.post(`${PUBLIC_PREFIX}/${kind}/withdraw`);
  return res.data as { kind: LegalKind; accepted: false; withdrawn: boolean };
}

// ------------------------------------------------------------------ quản trị

export async function fetchAdminOverview(): Promise<LegalAdminOverview> {
  const res = await axiosClient.get(`${ADMIN_PREFIX}/documents`);
  return res.data as LegalAdminOverview;
}

export async function fetchAnyVersion(
  kind: LegalKind,
  version: string,
): Promise<LegalDocumentContent> {
  const res = await axiosClient.get(
    `${ADMIN_PREFIX}/documents/${kind}/${encodeURIComponent(version)}`,
  );
  return res.data as LegalDocumentContent;
}

export async function publishDocument(payload: PublishPayload) {
  const res = await axiosClient.post(`${ADMIN_PREFIX}/documents`, payload);
  return res.data as { published: LegalDocumentRow; current: LegalDocument | null };
}

/**
 * Công bố một bản văn bằng cách TẢI TỆP LÊN.
 *
 * `FormData`, không phải JSON: một tệp `.pdf` mã hoá base64 để nhét vào JSON
 * phình thêm 33% và bắt cả hai đầu giữ nguyên tệp trong bộ nhớ hai lần.
 *
 * KHÔNG đặt `Content-Type` bằng tay. Trình duyệt phải tự sinh nó, vì nó còn
 * phải kèm `boundary=...` — một chuỗi ngẫu nhiên chỉ trình duyệt biết. Ghi đè
 * header này là lỗi hay gặp nhất với multipart, và triệu chứng là 422 kèm
 * thông báo nói rằng thiếu trường `file`, thứ rõ ràng đang có mặt.
 */
export async function uploadDocument(input: {
  kind: LegalKind;
  version: string;
  file: File;
  title?: string;
  language?: string;
  change_summary?: string;
  requires_reconsent?: boolean;
  effective_from?: string | null;
}) {
  const form = new FormData();
  form.append("kind", input.kind);
  form.append("version", input.version);
  form.append("file", input.file);
  form.append("title", input.title ?? "");
  form.append("language", input.language ?? "vi");
  form.append("change_summary", input.change_summary ?? "");
  form.append("requires_reconsent", String(!!input.requires_reconsent));
  if (input.effective_from) form.append("effective_from", input.effective_from);

  const res = await axiosClient.post(`${ADMIN_PREFIX}/documents/upload`, form);
  return res.data as { published: LegalDocumentRow; current: LegalDocument | null };
}

// ------------------------------------------------------- bản nháp (soạn thảo)

export type DraftStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "published"
  | "discarded";

export const DRAFT_STATUS_LABEL: Record<DraftStatus, string> = {
  draft: "Đang soạn",
  in_review: "Đang rà soát",
  approved: "Đã phê duyệt",
  published: "Đã công bố",
  discarded: "Đã huỷ",
};

export interface LegalDraft {
  draft_id: string;
  kind: LegalKind;
  title: string;
  language: string;
  body_format: "markdown" | "text";
  change_summary: string;
  target_version: string;
  requires_reconsent: boolean;
  effective_from: string | null;
  status: DraftStatus;
  /**
   * Số hiệu bản mà máy chủ đang giữ.
   *
   * Mọi lượt ghi phải gửi lại đúng con số này. Máy chủ chỉ ghi khi hai bên
   * khớp; lệch thì trả 409 kèm số hiệu hiện tại. Đây là toàn bộ cơ chế chống
   * hai người soạn đè mất bài của nhau, nên đừng bao giờ gửi một giá trị đoán
   * hay một giá trị tăng ở phía trình duyệt.
   */
  revision: number;
  based_on_version: string | null;
  published_version: string | null;
  storage_key: string | null;
  content_hash: string | null;
  byte_size: number;
  created_at: string;
  updated_at: string;
  /** Chỉ có khi đọc một bản nháp cụ thể; danh sách trả `body_length` thay thế. */
  body?: string;
  body_length?: number;
}

export interface LegalEvent {
  event_id: number;
  occurred_at: string;
  action: string;
  kind: LegalKind | null;
  version: string | null;
  draft_id: string | null;
  revision: number | null;
  storage_key: string | null;
  content_hash: string | null;
  /** Hành động và đối tượng — KHÔNG bao giờ chứa nội dung văn bản. */
  detail: Record<string, unknown> | null;
  actor: string;
}

export interface DraftUpdate {
  title?: string;
  language?: string;
  body?: string;
  change_summary?: string;
  target_version?: string;
  requires_reconsent?: boolean;
  effective_from?: string | null;
}

/** 409 khi có người ghi trước. `currentRevision` là thứ để nạp lại đúng chỗ. */
export class RevisionConflict extends Error {
  // Khai báo trường rồi gán trong thân hàm, KHÔNG dùng `readonly x` ngay trên
  // tham số. `tsconfig` bật `erasableSyntaxOnly`, cờ này cấm mọi cú pháp chỉ
  // TypeScript mới hiểu và không xoá đi được bằng cách bỏ chú thích kiểu —
  // "parameter property" là một trong số đó, vì nó SINH RA mã gán.
  //
  // Hệ quả nếu quên: `npx tsc --noEmit` vẫn xanh (nó chạy tsconfig khác),
  // nhưng `npm run build` — chạy `tsc -b` — thất bại, và **frontend không dựng
  // được**. Đó chính là trạng thái của kho tính tới 2026-08-09.
  readonly currentRevision: number | null;

  constructor(message: string, currentRevision: number | null) {
    super(message);
    this.name = "RevisionConflict";
    this.currentRevision = currentRevision;
  }
}

function rethrowConflict(err: unknown): never {
  const e = err as {
    response?: {
      status?: number;
      data?: { detail?: { code?: string; message?: string; current_revision?: number } };
    };
  };
  const detail = e.response?.data?.detail;
  if (e.response?.status === 409 && detail?.code === "revision_conflict") {
    throw new RevisionConflict(
      detail.message ?? tr("Bản nháp đã đổi."),
      detail.current_revision ?? null,
    );
  }
  throw err;
}

export async function fetchDrafts(includeClosed = false): Promise<LegalDraft[]> {
  const res = await axiosClient.get(`${ADMIN_PREFIX}/drafts`, {
    params: { include_closed: includeClosed },
  });
  return (res.data?.drafts ?? []) as LegalDraft[];
}

export async function fetchDraft(draftId: string): Promise<LegalDraft> {
  const res = await axiosClient.get(`${ADMIN_PREFIX}/drafts/${draftId}`);
  return res.data as LegalDraft;
}

export async function createDraft(
  kind: LegalKind,
  seedFromCurrent = true,
): Promise<LegalDraft> {
  const res = await axiosClient.post(`${ADMIN_PREFIX}/drafts`, {
    kind,
    seed_from_current: seedFromCurrent,
  });
  return res.data as LegalDraft;
}

export async function saveDraft(
  draftId: string,
  revision: number,
  changes: DraftUpdate,
): Promise<LegalDraft> {
  try {
    const res = await axiosClient.patch(`${ADMIN_PREFIX}/drafts/${draftId}`, {
      revision,
      ...changes,
    });
    return res.data as LegalDraft;
  } catch (err) {
    rethrowConflict(err);
  }
}

export async function setDraftStatus(
  draftId: string,
  revision: number,
  status: DraftStatus,
): Promise<LegalDraft> {
  try {
    const res = await axiosClient.post(
      `${ADMIN_PREFIX}/drafts/${draftId}/status`,
      { revision, status },
    );
    return res.data as LegalDraft;
  } catch (err) {
    rethrowConflict(err);
  }
}

export async function publishDraft(draftId: string, revision: number) {
  try {
    const res = await axiosClient.post(
      `${ADMIN_PREFIX}/drafts/${draftId}/publish`,
      { revision },
    );
    return res.data as { draft: LegalDraft; current: LegalDocument | null };
  } catch (err) {
    rethrowConflict(err);
  }
}

export async function fetchEvents(
  kind?: LegalKind,
  limit = 100,
): Promise<LegalEvent[]> {
  const res = await axiosClient.get(`${ADMIN_PREFIX}/events`, {
    params: { ...(kind ? { kind } : {}), limit },
  });
  return (res.data?.events ?? []) as LegalEvent[];
}
