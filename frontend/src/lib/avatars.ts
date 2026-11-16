import type { ComponentType, SVGProps } from "react";
import {
  BoltIcon,
  CameraIcon,
  CloudIcon,
  CompassIcon,
  GlobeIcon,
  GraduationCapIcon,
  HandIcon,
  HeartIcon,
  MoonIcon,
  RocketIcon,
  SparkleIcon,
  StarIcon,
} from "../components/ui/Icons";

/**
 * Bộ ảnh đại diện MẪU: một lựa chọn cho người không muốn dùng ảnh của mình (và là
 * lựa chọn an toàn cho cộng đồng nhạy cảm về danh tính — không lộ khuôn mặt). Người
 * dùng cũng có thể tải ảnh riêng lên; xem `isUploadedAvatar`.
 *
 * Với mẫu, máy chủ chỉ lưu `key`; hình vẽ nằm ở đây, nên thêm hay đổi mẫu không cần
 * migration.
 *
 * Màu nền dùng các bậc 600–700 để biểu tượng trắng đạt tương phản 3:1 của WCAG
 * 1.4.11 (thành phần đồ hoạ). Lớp Tailwind phải viết nguyên chuỗi để bộ quét thấy.
 */
export type AvatarPreset = {
  key: string;
  bg: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
};

export const AVATAR_PRESETS: readonly AvatarPreset[] = [
  { key: "hand", bg: "bg-sky-600", Icon: HandIcon },
  { key: "heart", bg: "bg-rose-600", Icon: HeartIcon },
  { key: "star", bg: "bg-amber-600", Icon: StarIcon },
  { key: "sparkle", bg: "bg-violet-600", Icon: SparkleIcon },
  { key: "moon", bg: "bg-indigo-600", Icon: MoonIcon },
  { key: "rocket", bg: "bg-emerald-600", Icon: RocketIcon },
  { key: "bolt", bg: "bg-orange-700", Icon: BoltIcon },
  { key: "compass", bg: "bg-teal-600", Icon: CompassIcon },
  { key: "camera", bg: "bg-cyan-700", Icon: CameraIcon },
  { key: "globe", bg: "bg-fuchsia-600", Icon: GlobeIcon },
  { key: "cap", bg: "bg-lime-700", Icon: GraduationCapIcon },
  { key: "cloud", bg: "bg-slate-600", Icon: CloudIcon },
];

/** `avatar_key` trỏ tới ảnh người dùng TẢI LÊN (máy chủ cấp, dạng `u-<epoch>`). */
export function isUploadedAvatar(key: string | null | undefined): key is string {
  return !!key && key.startsWith("u-");
}

export function findAvatarPreset(key: string | null | undefined): AvatarPreset | null {
  return AVATAR_PRESETS.find((p) => p.key === key) ?? null;
}

/**
 * Màu nền của ảnh mặc định (chữ cái đầu), suy từ tên để cùng một người luôn cùng
 * một màu mà không phải lưu gì.
 */
export function defaultAvatarColor(username: string): string {
  let h = 0;
  for (const ch of username) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
  return AVATAR_PRESETS[h % AVATAR_PRESETS.length].bg;
}
