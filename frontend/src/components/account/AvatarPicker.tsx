import { useRef, useState } from "react";
import { AVATAR_MAX_BYTES, setAvatar, uploadAvatar } from "../../api/auth";
import { notifyAuthChange } from "../../api/axiosClient";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../hooks/useToast";
import { useI18n } from "../../i18n";
import { friendlyError } from "../../lib/errors";
import { AVATAR_PRESETS } from "../../lib/avatars";
import Button from "../ui/Button";
import Avatar from "../Avatar";

/**
 * Chọn ảnh đại diện từ bộ mẫu hoặc tải ảnh của mình lên. Bấm là lưu ngay (không có nút "Lưu"), giống cách
 * các mạng xã hội làm: chọn xong thấy đổi ở đầu trang ngay.
 */
export default function AvatarPicker() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const current = user?.avatar_key ?? null;
  const fileInput = useRef<HTMLInputElement>(null);

  const upload = async (file: File | undefined) => {
    if (!file || busy) return;
    // Kiểm sớm ở trình duyệt cho khỏi gửi cả tệp lớn rồi mới bị từ chối; máy chủ
    // vẫn là nơi quyết định (loại tệp thật được kiểm ở đó, không tin phần mở rộng).
    if (file.size > AVATAR_MAX_BYTES) {
      toast.error(t("Ảnh lớn quá 2 MB. Hãy chọn ảnh nhỏ hơn."));
      return;
    }
    setBusy(true);
    try {
      await uploadAvatar(file);
      notifyAuthChange();
      toast.success(t("Đã đổi ảnh đại diện."));
    } catch (err) {
      toast.error(friendlyError(err, t("Không tải được ảnh lên.")));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = ""; // cho phép chọn lại đúng tệp đó
    }
  };

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
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          tabIndex={-1}
          aria-label={t("Chọn ảnh từ máy")}
          onChange={(e) => void upload(e.target.files?.[0])}
        />
        <Button variant="secondary" size="sm" loading={busy} onClick={() => fileInput.current?.click()}>
          {t("Tải ảnh của bạn lên")}
        </Button>
        <span className="text-xs text-slate-500">{t("JPEG, PNG hoặc WebP, tối đa 2 MB. Ảnh được cắt vuông.")}</span>
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
