import { defaultAvatarColor, findAvatarPreset } from "../lib/avatars";

const SIZES = {
  sm: { box: "h-8 w-8 text-sm", icon: "h-4 w-4" },
  md: { box: "h-10 w-10 text-lg", icon: "h-5 w-5" },
  lg: { box: "h-20 w-20 text-3xl", icon: "h-10 w-10" },
} as const;

/**
 * Ảnh đại diện: mẫu người dùng đã chọn, hoặc chữ cái đầu của tên khi chưa chọn
 * (hoặc khoá lạ, ví dụ một mẫu đã bị gỡ khỏi bộ).
 *
 * Trang trí thuần tuý (`aria-hidden`): tên người luôn nằm cạnh bên, nên đọc
 * thêm "ảnh đại diện" chỉ làm trình đọc màn hình nói thừa.
 */
export default function Avatar({
  user,
  size = "md",
  className = "",
}: {
  user: { username?: string; avatar_key?: string | null } | null | undefined;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const s = SIZES[size];
  const preset = findAvatarPreset(user?.avatar_key);
  const name = user?.username ?? "";
  const bg = preset?.bg ?? (name ? defaultAvatarColor(name) : "bg-ctu-blue");
  const base = `flex shrink-0 items-center justify-center rounded-full font-bold text-white ring-1 ring-white/25 ${s.box} ${bg} ${className}`;

  return (
    <span aria-hidden="true" className={base}>
      {preset ? <preset.Icon className={s.icon} /> : name ? name.charAt(0).toUpperCase() : "C"}
    </span>
  );
}
