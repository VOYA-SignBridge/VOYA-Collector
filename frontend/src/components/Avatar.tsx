import { useEffect, useState } from "react";
import { uploadedAvatarUrl } from "../api/auth";
import { defaultAvatarColor, findAvatarPreset, isUploadedAvatar } from "../lib/avatars";

const SIZES = {
  sm: { box: "h-8 w-8 text-sm", icon: "h-4 w-4" },
  md: { box: "h-10 w-10 text-lg", icon: "h-5 w-5" },
  lg: { box: "h-20 w-20 text-3xl", icon: "h-10 w-10" },
} as const;

/**
 * Ảnh đại diện: ảnh người dùng tải lên, hoặc mẫu đã chọn, hoặc chữ cái đầu của
 * tên khi chưa chọn (hay khoá lạ, hay ảnh tải lên không tải được).
 *
 * Trang trí thuần tuý (`aria-hidden`): tên người luôn nằm cạnh bên, nên đọc
 * thêm "ảnh đại diện" chỉ làm trình đọc màn hình nói thừa.
 */
export default function Avatar({
  user,
  size = "md",
  className = "",
}: {
  user: { id?: string; username?: string; avatar_key?: string | null } | null | undefined;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const s = SIZES[size];
  const key = user?.avatar_key;
  const name = user?.username ?? "";
  const uploaded = isUploadedAvatar(key) && !!user?.id;
  // Ảnh tải lên hỏng (mạng, bị xoá) thì rơi về chữ cái đầu thay vì hiện ô vỡ.
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [key]);

  const preset = findAvatarPreset(key);
  const bg = preset?.bg ?? (name ? defaultAvatarColor(name) : "bg-ctu-blue");
  const base = `flex shrink-0 items-center justify-center overflow-hidden rounded-full font-bold text-white ring-1 ring-white/25 ${s.box} ${className}`;

  if (uploaded && !broken) {
    return (
      <span aria-hidden="true" className={`${base} bg-slate-200`}>
        <img
          src={uploadedAvatarUrl(user!.id!, key!)}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setBroken(true)}
          className="h-full w-full object-cover"
        />
      </span>
    );
  }

  return (
    <span aria-hidden="true" className={`${base} ${bg}`}>
      {preset ? <preset.Icon className={s.icon} /> : name ? name.charAt(0).toUpperCase() : "C"}
    </span>
  );
}
