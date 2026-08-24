/**
 * Vocabulary registry client.
 *
 * The registry is the SINGLE source of truth for which dialects and recognition
 * profiles exist. Before this module the frontend shipped two hand-maintained
 * maps (config/dialectLabels.ts and a copy inside FullscreenCaptureModal), which
 * had already drifted from the database: they listed `ha-noi` and `saigon`,
 * neither of which has ever had a class or a sample behind it, while a dialect
 * approved through POST /vocabulary/dialects could never appear at all.
 *
 * Ordering note: the server returns dialects and profiles already ordered
 * (profiles by display_order, which is geographic — alphabet, north, central,
 * south, hoa_de — not alphabetical). Render them in the order received and do
 * NOT re-sort, or the picker stops matching the rest of the system.
 */

import axiosClient from "./axiosClient";
import { tr } from "../i18n";

const API_PREFIX = "/api/v1/vocabulary";

export interface RegistryDialect {
  dialect_id: string;
  display_name: string;
  status?: string;
  is_active?: boolean;
  created_by?: string | null;
  created_at?: string | null;
  merged_into?: string | null;
}

export interface RegistryProfile {
  profile_id: string;
  display_name: string;
  is_trainable?: boolean | number;
  display_order?: number;
  is_active?: boolean;
}

/** Một vùng miền dùng được, đọc từ bảng `regions` chứ không cứng hoá. */
export interface RegistryRegion {
  code: string;
  name_vi: string;
  name_en?: string;
  sort_order?: number;
}

export interface VocabularyRegistry {
  registry_version: number;
  dialects: RegistryDialect[];
  profiles: RegistryProfile[];
  /** Tuỳ chọn: một backend cũ hơn không trả trường này. */
  regions?: RegistryRegion[];
}

export interface PendingDialect extends RegistryDialect {
  created_by_username?: string | null;
}

/** Raised shape of the 409 the API returns when a slug is already taken. */
export interface SlugTakenError {
  error: "slug_taken";
  dialect_id: string;
  existing_display_name: string;
  message: string;
}

export type VocabResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number; slugTaken?: SlugTakenError };

function toError(e: unknown): VocabResult<never> {
  const err = e as { response?: { status?: number; data?: { detail?: unknown } }; message?: string };
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;

  // 409 from POST /dialects carries a structured body so the UI can offer
  // "use the existing one" instead of just saying the name is taken.
  if (status === 409 && detail && typeof detail === "object" && "error" in (detail as object)) {
    const st = detail as SlugTakenError;
    return { ok: false, error: st.message || tr("Slug đã tồn tại"), status, slugTaken: st };
  }
  const msg =
    typeof detail === "string" ? detail : err?.message || tr("Không gọi được registry");
  return { ok: false, error: msg, status };
}

/** GET /vocabulary/registry — dialects + profiles + registry_version. Auth optional. */
export async function getVocabularyRegistry(): Promise<VocabResult<VocabularyRegistry>> {
  try {
    const res = await axiosClient.get(`${API_PREFIX}/registry`);
    const d = res.data ?? {};
    return {
      ok: true,
      data: {
        registry_version: Number(d.registry_version ?? 0),
        dialects: Array.isArray(d.dialects) ? d.dialects : [],
        profiles: Array.isArray(d.profiles) ? d.profiles : [],
      },
    };
  } catch (e) {
    return toError(e);
  }
}

/** POST /vocabulary/dialects — any signed-in user may propose one. 201 on create. */
export async function proposeDialect(payload: {
  dialect_id: string;
  display_name: string;
}): Promise<VocabResult<{ dialect: RegistryDialect; created: boolean }>> {
  try {
    const res = await axiosClient.post(`${API_PREFIX}/dialects`, payload);
    return { ok: true, data: res.data };
  } catch (e) {
    return toError(e);
  }
}

/** GET /vocabulary/dialects/pending — admin only. */
export async function getPendingDialects(): Promise<VocabResult<PendingDialect[]>> {
  try {
    const res = await axiosClient.get(`${API_PREFIX}/dialects/pending`);
    const items = res.data?.items;
    return { ok: true, data: Array.isArray(items) ? items : [] };
  } catch (e) {
    return toError(e);
  }
}

/** POST /vocabulary/dialects/{id}/approve — admin only. */
export async function approveDialect(dialectId: string): Promise<VocabResult<unknown>> {
  try {
    const res = await axiosClient.post(
      `${API_PREFIX}/dialects/${encodeURIComponent(dialectId)}/approve`
    );
    return { ok: true, data: res.data };
  } catch (e) {
    return toError(e);
  }
}

/**
 * POST /vocabulary/dialects/{id}/reject — admin only.
 *
 * `mergeInto` is REQUIRED by the API (400 without it): rejecting is really
 * "this is a duplicate of that one", so anything already filed under the
 * rejected slug has somewhere to go instead of being orphaned.
 */
export async function rejectDialect(
  dialectId: string,
  mergeInto: string
): Promise<VocabResult<unknown>> {
  try {
    const res = await axiosClient.post(
      `${API_PREFIX}/dialects/${encodeURIComponent(dialectId)}/reject`,
      { merge_into: mergeInto }
    );
    return { ok: true, data: res.data };
  } catch (e) {
    return toError(e);
  }
}

/**
 * PATCH /vocabulary/dialects/{id} — rename or (de)activate.
 * `dialect_id` itself is never editable: it is the key used by samples.csv,
 * folder names and realtime model ids.
 */
export async function updateDialect(
  dialectId: string,
  patch: { display_name?: string; is_active?: boolean }
): Promise<VocabResult<unknown>> {
  try {
    const res = await axiosClient.patch(
      `${API_PREFIX}/dialects/${encodeURIComponent(dialectId)}`,
      patch
    );
    return { ok: true, data: res.data };
  } catch (e) {
    return toError(e);
  }
}


// --------------------------------------------------------------------------- phiên bản danh mục (UC10)

/**
 * Một bản danh mục ĐÃ ĐÓNG BĂNG. Nội dung của nó không sửa được; muốn đổi thì
 * công bố bản mới. `content_hash` là thứ cho phép đối chiếu rằng bản đang đọc
 * đúng là bản đã công bố.
 */
export interface CatalogVersion {
  version: number;
  content_hash: string;
  note: string | null;
  created_at: string;
  created_by_username: string | null;
}

export interface CatalogState {
  dialects: unknown[];
  profiles: unknown[];
  /** Băm của danh mục ĐANG SỐNG (chưa công bố). */
  content_hash: string;
  latest_version: number | null;
  /** Băm của bản công bố gần nhất. Khác `content_hash` = đã sửa từ lần công bố. */
  latest_content_hash: string | null;
}

const CATALOG = "/api/v1/vocabulary/catalog";

export async function getCatalogState(): Promise<CatalogState> {
  const res = await axiosClient.get<CatalogState>(CATALOG);
  return res.data;
}

export async function getCatalogVersions(limit = 50): Promise<CatalogVersion[]> {
  const res = await axiosClient.get<{ items: CatalogVersion[] }>(`${CATALOG}/versions`, {
    params: { limit },
  });
  return res.data.items;
}

/** Công bố. Bất biến theo NỘI DUNG: danh mục không đổi thì trả về bản đã có. */
export async function publishCatalog(note: string): Promise<{ version: number; created: boolean }> {
  const res = await axiosClient.post(`${CATALOG}/publish`, { note });
  return res.data;
}
