import { useState, type ComponentProps } from "react";
import { useI18n } from "../../i18n";
import { EyeIcon, EyeOffIcon } from "../ui/Icons";
import AuthInput, { LockIcon } from "./AuthInput";

type Props = Omit<ComponentProps<typeof AuthInput>, "icon" | "type" | "trailing">;

/**
 * Ô mật khẩu có nút con mắt RIÊNG.
 *
 * Mỗi ô tự giữ trạng thái hiện/ẩn của mình. Bản trước dùng MỘT trạng thái cho cả
 * "Mật khẩu" lẫn "Xác nhận mật khẩu": bấm ở ô này làm lộ luôn ô kia, và người
 * dùng không còn cách nào kiểm riêng một ô mà không phơi cả hai ra màn hình.
 */
export default function PasswordInput(props: Props) {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  const Eye = visible ? EyeOffIcon : EyeIcon;

  return (
    <AuthInput
      {...props}
      icon={<LockIcon />}
      type={visible ? "text" : "password"}
      trailing={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? t("Ẩn mật khẩu") : t("Hiện mật khẩu")}
          aria-pressed={visible}
          className="rounded-lg p-2 text-slate-500 transition hover:bg-ctu-blue/10 hover:text-ctu-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
        >
          <Eye className="h-5 w-5" aria-hidden="true" />
        </button>
      }
    />
  );
}
