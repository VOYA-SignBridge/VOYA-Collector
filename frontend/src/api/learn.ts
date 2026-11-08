/**
 * Học ký hiệu — API công khai (không cần đăng nhập).
 *
 * Danh mục từ vựng lấy từ Danh mục NNKH tiếng Việt (QIPEDC, Bộ GD&ĐT); video
 * mẫu chỉ LIÊN KẾT sang trang chính thức. `own` là phần dữ liệu của chính hệ
 * thống này cho cùng ký hiệu — để người học biết có thể "thử ký" hay cần
 * "đóng góp mẫu".
 */

import axiosClient from "./axiosClient";

const PREFIX = "/api/v1/learn";

export type LearnRegion = "bac" | "trung" | "nam" | "khong_ghi";

export interface SignVariant {
  code: string;
  region: LearnRegion | string;
  region_name: string;
  video_url: string;
}

export interface OwnClass {
  class_uid: string;
  label: string;
  region: string;
  dialect: string;
  sample_count: number;
}

export interface Sign {
  slug: string;
  word: string;
  pos: string;
  kind: string;
  definition: string;
  variants: SignVariant[];
  own: OwnClass[];
  own_sample_count: number;
}

export type LearnKind = "tu_thuong" | "bang_chu_cai" | "chu_so";

export interface LearnFacets {
  kinds: { key: LearnKind | string; name: string; count: number }[];
  regions: { key: LearnRegion | string; name: string; count: number }[];
  /** Từ loại đủ lớn để lọc (Danh từ, Động từ, …) — tên là DỮ LIỆU, không dịch. */
  pos: { name: string; count: number }[];
  /** Chữ cái đầu (không dấu) CÓ từ — để thanh A–Z không có nút chết. */
  letters: string[];
}

export interface SignList {
  items: Sign[];
  /** Số mục khớp bộ lọc (mọi trang). */
  total: number;
  page: number;
  pages: number;
  limit: number;
  /** Cả danh mục, không tính bộ lọc. */
  total_words: number;
  facets: LearnFacets;
  attribution: string;
  dictionary_url: string;
}

export interface SignQuery {
  q?: string;
  region?: string;
  kind?: string;
  pos?: string;
  letter?: string;
  /** Chỉ ký hiệu hệ thống đã có mẫu — "thử được với camera". */
  hasOwn?: boolean;
  page?: number;
  limit?: number;
}

export interface SignDetail extends Sign {
  attribution: string;
  dictionary_url: string;
}

export async function searchSigns(query: SignQuery = {}): Promise<SignList> {
  const { q = "", region = "", kind = "", pos = "", letter = "", hasOwn = false, page = 1, limit = 24 } = query;
  const res = await axiosClient.get<SignList>(`${PREFIX}/signs`, {
    params: { q, region, kind, pos, letter, has_own: hasOwn, page, limit },
  });
  return res.data;
}

export async function fetchSign(slug: string): Promise<SignDetail> {
  const res = await axiosClient.get<SignDetail>(`${PREFIX}/sign`, { params: { slug } });
  return res.data;
}

/** @i18n-key-table — tên vùng là KHOÁ từ điển, dịch bằng `t(REGION_LABEL[r])`. */
export const REGION_LABEL: Record<string, string> = {
  bac: "Miền Bắc",
  trung: "Miền Trung",
  nam: "Miền Nam",
  khong_ghi: "Chung (không ghi vùng)",
};

/** @i18n-key-table — loại mục là KHOÁ từ điển, dịch bằng `t(KIND_LABEL[k])`. */
export const KIND_LABEL: Record<string, string> = {
  tu_thuong: "Từ thường",
  bang_chu_cai: "Bảng chữ cái",
  chu_so: "Chữ số",
};
