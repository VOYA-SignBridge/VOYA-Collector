import axiosClient from "./axiosClient";
import { validateLabels, validateSessions, validateLabel } from "./validators";
import type { Result } from "./validators";
import type { Label, Session, ClassRow, ClassesListResponse, ClassStatsRow, ClassStatsResponse } from "../types";

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

export const getSamples = async (): Promise<Result<Session[]>> => {
  const res = await axiosClient.get("/dataset/sessions");
  return validateSessions(res.data);
};

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
    items = items.map(item => ({
      ...item,
      class_idx: item.class_idx === '' || item.class_idx === null || item.class_idx === undefined 
        ? -1 
        : (typeof item.class_idx === 'string' ? parseInt(item.class_idx, 10) : Number(item.class_idx))
    }));

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

export const registerClass = async (payload: { label: string; language?: string; dialect?: string; is_common_global?: boolean; is_common_language?: boolean; }): Promise<Result<ClassRow>> => {
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
    const raw = res.data as any;
    // Expect shape: { total_classes, max_count, distribution: [...] }
    const out: ClassStatsResponse = { total_classes: 0, max_count: 0, distribution: [] };
    if (raw && typeof raw === 'object') {
      out.total_classes = Number(raw.total_classes || 0);
      out.max_count = Number(raw.max_count || 0);
      if (Array.isArray(raw.distribution)) {
        out.distribution = raw.distribution.map((d: any) => ({
          class_uid: String(d.class_uid),
          class_idx: d.class_idx !== undefined ? Number(d.class_idx) : undefined,
          slug: d.slug,
          label_original: d.label_original,
          count: Number(d.count || 0),
          samples_count: Number(d.count || 0),
          language: d.language,
          dialect: d.dialect,
          // preserve other fields if present
        } as ClassStatsRow));
      }
    }
    return { ok: true, data: out };
  } catch (e) {
    return { ok: false, error: 'Invalid classes stats response' } as Result<ClassStatsResponse>;
  }
};

// Keep legacy endpoints as fallback (getLabels/createLabel/updateLabel/deleteLabel remain)
