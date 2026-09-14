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

export interface SignList {
  items: Sign[];
  total_words: number;
  attribution: string;
  dictionary_url: string;
}

export interface SignDetail extends Sign {
  attribution: string;
  dictionary_url: string;
}

export async function searchSigns(q: string, region: string = "", limit = 50): Promise<SignList> {
  const res = await axiosClient.get<SignList>(`${PREFIX}/signs`, { params: { q, region, limit } });
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
