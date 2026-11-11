import { useState, type ReactNode } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import { MailIcon, ShieldIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

export type RecoveryAction = "reset_link" | "clear_2fa";

export interface RecoveryPayload {
  action: RecoveryAction;
  reason: string;
}

const MIN_REASON = 5;

/**
 * Giúp một người lấy lại tài khoản.
 *
 * Hộp thoại này không bao giờ cho quản trị viên đặt mật khẩu hộ: cả hai hành
 * động chỉ "mở lại cánh cửa", bước cuối vẫn do chính chủ đi. Mật khẩu CỦA quản
 * trị viên (nâng quyền) được hỏi ở bước sau qua `useSudo`, không nằm trong
 * state của hộp thoại này.
 */
export default function RecoveryModal({
  user,
  onClose,
  onConfirm,
}: {
  user: { username: string; email: string } | null;
  onClose: () => void;
  onConfirm: (payload: RecoveryPayload) => Promise<void> | void;
}) {
  const { t } = useI18n();
  const [action, setAction] = useState<RecoveryAction>("reset_link");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  // Lý do nhập nhanh: bấm một cái thay vì gõ. Người dùng sửa lại được.
  const quickReasons = [
    t("Chủ tài khoản nhờ qua tin nhắn"),
    t("Chủ tài khoản quên mật khẩu"),
    t("Chủ tài khoản mất điện thoại"),
  ];
  const valid = reason.trim().length >= MIN_REASON;

  const close = () => {
    if (busy) return;
    setReason("");
    setAction("reset_link");
    onClose();
  };

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    try {
      await onConfirm({ action, reason: reason.trim() });
      setReason("");
      setAction("reset_link");
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const options: { value: RecoveryAction; title: string; hint: string; icon: ReactNode }[] = [
    {
      value: "reset_link",
      title: t("Gửi liên kết đặt lại mật khẩu"),
      hint: t("Thư gửi tới {email}. Chủ tài khoản tự đặt mật khẩu mới.", { email: user.email }),
      icon: <MailIcon className="h-5 w-5" aria-hidden="true" />,
    },
    {
      value: "clear_2fa",
      title: t("Gỡ xác thực hai bước"),
      hint: t("Dùng khi chủ tài khoản mất điện thoại và hết mã khôi phục. Họ đăng nhập lại bằng mật khẩu."),
      icon: <ShieldIcon className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  return (
    <Modal isOpen onClose={close} title={t("Hỗ trợ tài khoản {name}", { name: user.username })} size="md">
      <div className="space-y-5">
        <fieldset className="space-y-2">
          <legend className="sr-only">{t("Chọn cách hỗ trợ")}</legend>
          {options.map((o) => (
            <label
              key={o.value}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                action === o.value ? "border-ctu-blue bg-ctu-blue/5" : "border-slate-200 hover:bg-slate-50"
              }`}
            >
              <input
                type="radio"
                name="recovery-action"
                value={o.value}
                checked={action === o.value}
                onChange={() => setAction(o.value)}
                className="mt-1 accent-ctu-blue"
              />
              <span className="text-slate-500">{o.icon}</span>
              <span>
                <span className="block text-sm font-semibold text-slate-900">{o.title}</span>
                <span className="block text-xs text-slate-500">{o.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div>
          <label htmlFor="recovery-reason" className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Lý do")}
          </label>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {quickReasons.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setReason(r)}
                className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                {r}
              </button>
            ))}
          </div>
          <textarea
            id="recovery-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/20"
            placeholder={t("Ít nhất 5 ký tự. Được ghi vào nhật ký kiểm toán.")}
          />
        </div>

        <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          {t("Chủ tài khoản sẽ nhận thông báo về việc này. Bạn sẽ được hỏi lại mật khẩu của chính mình để xác nhận.")}
        </p>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={busy}>
            {t("Huỷ")}
          </Button>
          <Button variant="primary" onClick={submit} disabled={!valid || busy}>
            {busy ? t("Đang xử lý…") : t("Xác nhận")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
