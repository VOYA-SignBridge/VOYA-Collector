import { useState } from "react";
import { setAvatar } from "../../api/auth";
import { notifyAuthChange } from "../../api/axiosClient";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../hooks/useToast";
import { useI18n } from "../../i18n";
import { friendlyError } from "../../lib/errors";
import { AVATAR_PRESETS } from "../../lib/avatars";
import Avatar from "../Avatar";

/**
 * Chọn ảnh đại diện từ bộ mẫu. Bấm là lưu ngay (không có nút "Lưu"), giống cách
 * các mạng xã hội làm: chọn xong thấy đổi ở đầu trang ngay.
 */
export default function AvatarPicker() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const current = user?.avatar_key ?? null;

  const choose = async (key: string | null) => {
    if (busy || key === current) return;
    setBusy(true);
    try {
      await setAvatar(key);
      // `AuthProvider` chỉ nạp lại hồ sơ khi có sự kiện này; không phát thì đầu
      // trang giữ ảnh cũ và người dùng tưởng lượt chọn thất bại.
      notifyAuthChange();
      toast.success(t("Đã đổi ảnh đại diện."));
    } catch (err) {
      toast.error(friendlyError(err, t("Không đổi được ảnh đại diện.")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div role="radiogroup" aria-label={t("Chọn ảnh đại diện")} className="grid grid-cols-6 gap-3 sm:grid-cols-12">
        {AVATAR_PRESETS.map(({ key, Icon, bg }) => {
          const selected = current === key;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={t("Ảnh đại diện {n}", { n: AVATAR_PRESETS.findIndex((p) => p.key === key) + 1 })}
              disabled={busy}
              onClick={() => void choose(key)}
              className={`flex h-10 w-10 items-center justify-center rounded-full text-white transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2 disabled:opacity-60 ${bg} ${
                selected ? "ring-2 ring-ctu-blue ring-offset-2" : "hover:scale-110 motion-reduce:hover:scale-100"
              }`}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
            </button>
          );
        })}
      </div>
      <button
        type="button"
        disabled={busy || current === null}
        onClick={() => void choose(null)}
        className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-ctu-blue hover:text-ctu-navy disabled:cursor-default disabled:text-slate-400"
      >
        <Avatar user={{ username: user?.username }} size="sm" />
        {t("Dùng chữ cái đầu của tên")}
      </button>
    </div>
  );
}
