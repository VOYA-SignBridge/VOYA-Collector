import { tr } from "../i18n";
import axiosClient from "./axiosClient";
import { validateLabels, validateSessions, validateLabel } from "./validators";
import type { Result } from "./validators";
import type { Label, Session, ClassRow, ClassesListResponse, ClassStatsRow, ClassStatsResponse } from "../types";
import { validateClass } from "./validators";

export const getLabels = async (): Promise<Result<Label[]>> => {
  const res = await axiosClient.get("/dataset/labels");
  return validateLabels(res.data);
};

export const createLabel = async (label: string): Promise<Result<Label>> => {
  const formData = new FormData();
  formData.append("label", label);
  const res = await axiosClient.post("/dataset/labels", formData);
  return validateLabel(res.data);
};

export const updateLabel = async (class_idx: number, label: string): Promise<Result<Label>> => {
  const formData = new FormData();
  formData.append("label", label);
  const res = await axiosClient.put(`/dataset/labels/${class_idx}`, formData);
  return validateLabel(res.data);
};

export const deleteLabel = async (class_idx: number): Promise<Result<null>> => {
  const res = await axiosClient.delete(`/dataset/labels/${class_idx}`);
  // Backend may return simple status object; we'll coerce to Result<null>
  return { ok: res.status >= 200 && res.status < 300, data: null, error: res.statusText } as Result<null>;
};

// Tiny in-flight + TTL cache so widgets that mount together (e.g. two
// dashboard sections both needing sessions) share ONE network request instead
// of each firing its own. A rejected request is evicted so the next call retries.
const _reqCache: Record<string, { t: number; p: Promise<unknown> }> = {};
function cachedRequest<T>(key: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = _reqCache[key];
  if (hit && now - hit.t < ttlMs) return hit.p as Promise<T>;
  const p = fn();
  _reqCache[key] = { t: now, p };
  p.catch(() => { if (_reqCache[key]?.p === p) delete _reqCache[key]; });
  return p;
}

export const getSamples = async (): Promise<Result<Session[]>> =>
  cachedRequest("dataset/sessions", 5000, async () => {
    const res = await axiosClient.get("/dataset/sessions");
    return validateSessions(res.data);
  });

export type CommunityStats = {
  labels_count: number;
  total_samples: number;
  contributors_count: number;
  regions_count: number;
};

// Server-side aggregate for the dashboard "Cộng đồng" block. Replaces the old
// pattern of downloading the whole class list + every session and reducing them
// in the browser — one small request (~120B), cached 30s.
export const getCommunityStats = async (): Promise<CommunityStats> =>
  cachedRequest("classes/community-stats", 30000, async () => {
    const res = await axiosClient.get("/classes/community-stats");
    return res.data as CommunityStats;
  });

export const getSampleData = async (sampleId: string) => {
  const res = await axiosClient.get(`/dataset/samples/${sampleId}/data`, {
    responseType: "arraybuffer", // để xử lý npz
  });
  return res.data;
};

export const deleteSample = async (sampleId: string) => {
  const res = await axiosClient.delete(`/dataset/samples/${sampleId}`);
  return { ok: res.status >= 200 && res.status < 300, status: res.status, statusText: res.statusText };
};

// --- New classes API wrappers (preferred modern endpoints) ---
export const getClassesList = async (language?: string, dialect?: string): Promise<Result<ClassesListResponse>> => {
  const params: Record<string, string> = {};
  if (language) params.language = language;
  if (dialect) params.dialect = dialect;
  const res = await axiosClient.get('/classes/list', { params });
  
  // Debug: print raw response for investigation
  // eslint-disable-next-line no-console
  console.debug('[api] getClassesList RAW response:', JSON.stringify(res.data, null, 2));
  
  try {
    const raw = res.data;
    let items: ClassRow[] = [];
    let count = 0;

    // Primary: expect {count, items: [...]}
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      if (Array.isArray(raw.items)) {
        items = raw.items;
        count = raw.count ?? items.length;
      } else if (Array.isArray(raw.data)) {
        // Fallback: {data: [...]}
        items = raw.data;
        count = items.length;
      } else {
        // Try to extract class-like objects from keys
        const possibleItems: ClassRow[] = [];
        for (const k of Object.keys(raw)) {
          const v = raw[k];
          if (v && typeof v === 'object' && ('class_uid' in v || 'class_idx' in v)) {
            possibleItems.push(v as ClassRow);
          }
        }
        if (possibleItems.length > 0) {
          items = possibleItems;
          count = items.length;
        }
      }
    } else if (Array.isArray(raw)) {
      // Fallback: top-level array
      items = raw as ClassRow[];
      count = items.length;
    }

    // Normalize class_idx to number (BE returns string, sometimes empty)
    // and hands_required to 1 | 2 | null (BE returns ""/"1"/"2" strings)
    items = items.map(item => {
      const rawHands = item.hands_required;
      const handsNum = rawHands === '' || rawHands === null || rawHands === undefined
        ? null
        : Number(rawHands);
      return {
        ...item,
        class_idx: item.class_idx === '' || item.class_idx === null || item.class_idx === undefined
          ? -1
          : (typeof item.class_idx === 'string' ? parseInt(item.class_idx, 10) : Number(item.class_idx)),
        hands_required: handsNum === 1 || handsNum === 2 ? handsNum : null,
      };
    });

    const data: ClassesListResponse = { count, items };
    
    // eslint-disable-next-line no-console
    console.debug('[api] getClassesList PARSED:', { count, itemsLength: items.length, firstItem: items[0] });
    
    return { ok: true, data };
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[api] getClassesList PARSE ERROR:', e);
    return { ok: false, error: 'Invalid classes list response' } as Result<ClassesListResponse>;
  }
};

export const registerClass = async (payload: { label: string; language?: string; dialect?: string; is_common_global?: boolean; is_common_language?: boolean; region?: string; }): Promise<Result<ClassRow>> => {
  const res = await axiosClient.post('/classes/register', payload);
  const raw = res.data;
  // Try to normalize the returned registration into a ClassRow
  if (raw && typeof raw === 'object') {
    const row = raw as ClassRow;
    return { ok: true, data: row } as Result<ClassRow>;
  }
  return { ok: false, error: 'Invalid register class response' } as Result<ClassRow>;
};

export const getClassesStats = async (language?: string, dialect?: string): Promise<Result<ClassStatsResponse>> => {
  const params: Record<string, string> = {};
  if (language) params.language = language;
  if (dialect) params.dialect = dialect;
  const res = await axiosClient.get('/classes/stats', { params });
  try {
    const raw: unknown = res.data;
    // Expect shape: { total_classes, max_count, distribution: [...] }
    const out: ClassStatsResponse = { total_classes: 0, max_count: 0, distribution: [] };

    const isRecord = (v: unknown): v is Record<string, unknown> =>
      typeof v === 'object' && v !== null && !Array.isArray(v);

    if (isRecord(raw)) {
      out.total_classes = Number(raw.total_classes ?? 0);
      out.max_count = Number(raw.max_count ?? 0);

      const dist = raw.distribution;
      if (Array.isArray(dist)) {
        out.distribution = dist
          .filter(isRecord)
          .map((d): ClassStatsRow => {
            const count = Number(d.count ?? 0);
            return {
              class_uid: String(d.class_uid ?? ''),
              class_idx: d.class_idx !== undefined && d.class_idx !== null ? Number(d.class_idx) : undefined,
              slug: typeof d.slug === 'string' ? d.slug : undefined,
              label_original: typeof d.label_original === 'string' ? d.label_original : undefined,
              count,
              samples_count: count,
            };
          });
      }
    }
    return { ok: true, data: out };
  } catch (e) {
    return { ok: false, error: 'Invalid classes stats response' } as Result<ClassStatsResponse>;
  }
};

// Keep legacy endpoints as fallback (getLabels/createLabel/updateLabel/deleteLabel remain)
export const updateClass = async (
  classRef: string,
  payload: Record<string, unknown>,
): Promise<Result<ClassRow>> => {
  try {
    const res = await axiosClient.put(`/classes/${classRef}`, payload);
    if (res.status < 200 || res.status >= 300) {
      return { ok: false, error: res.statusText };
    }

    const raw = res.data || {};
    const validated = validateClass(raw);
    if (!validated.ok) return validated;

    // Return validated class row and pass through operation logs (if any)
    const out: Result<ClassRow> & { operation_logs?: string[]; op_id?: string } = {
      ok: true,
      data: { ...validated.data } as ClassRow,
    };
    if (raw.operation_logs) out.operation_logs = Array.isArray(raw.operation_logs) ? raw.operation_logs.map(String) : undefined;
    if (raw.op_id) out.op_id = String(raw.op_id);
    return out;
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : tr("Thao tác không thành công."),
    };
  }
};

// --- Trash (soft delete) API ---
export interface TrashClass {
  class_uid: string;
  class_idx?: number | string;
  slug?: string;
  label_original?: string;
  language?: string;
  dialect?: string;
  sample_count?: number;
  deleted_at?: string;
}

export interface TrashSample {
  sample_uid: string;
  class_uid?: string;
  slug?: string;
  label_original?: string;
  language?: string;
  dialect?: string;
  user_id?: string;
  username?: string;
  seq_len?: number | string;
  deleted_at?: string;
}

export const getClassTrash = async (): Promise<Result<TrashClass[]>> => {
  try {
    const res = await axiosClient.get("/classes/trash");
    const items = Array.isArray(res.data?.items) ? (res.data.items as TrashClass[]) : [];
    return { ok: true, data: items };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Không đọc được thùng rác") };
  }
};

export const restoreClass = async (classUid: string): Promise<Result<null>> => {
  try {
    const res = await axiosClient.post(`/classes/${classUid}/restore`);
    if (res.data?.success === false) return { ok: false, error: res.data?.message || tr("Lỗi khôi phục") };
    return { ok: true, data: null };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Lỗi khôi phục") };
  }
};

export const purgeClass = async (classUid: string): Promise<Result<null>> => {
  try {
    const res = await axiosClient.delete(`/classes/${classUid}/purge`);
    if (res.data?.success === false) return { ok: false, error: res.data?.message || tr("Lỗi xóa vĩnh viễn") };
    return { ok: true, data: null };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Lỗi xóa vĩnh viễn") };
  }
};

export interface BulkResult { ok_count: number; failed_count: number }

const bulkCall = async (url: string, body: Record<string, unknown>): Promise<Result<BulkResult>> => {
  try {
    const res = await axiosClient.post(url, body);
    return { ok: true, data: { ok_count: res.data?.ok_count ?? 0, failed_count: res.data?.failed_count ?? 0 } };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Thao tác thất bại") };
  }
};

export const bulkRestoreClasses = (classUids: string[]) => bulkCall("/classes/trash/restore", { class_uids: classUids });
export const bulkPurgeClasses = (classUids: string[]) => bulkCall("/classes/trash/purge", { class_uids: classUids });
export const emptyClassTrash = () => bulkCall("/classes/trash/purge", { all: true });
export const bulkRestoreSamples = (sampleUids: string[]) => bulkCall("/dataset/samples/trash/restore", { sample_uids: sampleUids });
export const bulkPurgeSamples = (sampleUids: string[]) => bulkCall("/dataset/samples/trash/purge", { sample_uids: sampleUids });
export const emptySampleTrash = () => bulkCall("/dataset/samples/trash/purge", { all: true });

export const getSampleTrash = async (): Promise<Result<TrashSample[]>> => {
  try {
    const res = await axiosClient.get("/dataset/samples/trash");
    const items = Array.isArray(res.data?.items) ? (res.data.items as TrashSample[]) : [];
    return { ok: true, data: items };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Không đọc được thùng rác mẫu") };
  }
};

export const restoreSample = async (sampleId: string): Promise<Result<null>> => {
  try {
    await axiosClient.post(`/dataset/samples/${sampleId}/restore`);
    return { ok: true, data: null };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Lỗi khôi phục mẫu") };
  }
};

export const purgeSample = async (sampleId: string): Promise<Result<null>> => {
  try {
    await axiosClient.delete(`/dataset/samples/${sampleId}/purge`);
    return { ok: true, data: null };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : tr("Lỗi xóa vĩnh viễn mẫu") };
  }
};

export const deleteClass = async (classRef: string): Promise<Result<{ message: string; deleted: boolean; class_uid: string; class_idx: number; sample_count: number; raw_upload_count: number; op_id?: string; operation_logs?: string[] }>> => {
  try {
    const res = await axiosClient.delete(`/classes/${classRef}`);
    const data = res.data || {};

    if (data.success === true || data.deleted === true) {
      return {
        ok: true,
        data: {
          message: data.message || tr("Nhãn được xóa thành công"),
          deleted: true,
          class_uid: data.class_uid || "",
          class_idx: data.class_idx || 0,
          sample_count: data.sample_count || 0,
          raw_upload_count: data.raw_upload_count || 0,
          op_id: data.op_id,
          operation_logs: data.operation_logs,
        },
      };
    }

    return { ok: false, error: data.message || data.error || res.statusText };
  } catch (err) {
    const errMessage = err instanceof Error ? err.message : tr("Thao tác không thành công.");
    return {
      ok: false,
      error: errMessage,
    };
  }
};