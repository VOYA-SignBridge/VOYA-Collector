import { useRef, useState, type ReactNode } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import { MailIcon, ShieldIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";
import { copyToClipboard } from "../sot/PrivateKeyModal";

export type RecoveryAction = "reset_link" | "clear_2fa";

export interface RecoveryPayload {
  action: RecoveryAction;
  reason: string;
}

/** Máy chủ trả về khi tạo liên kết: để quản trị viên chuyển tay nếu thư không tới. */
export interface RecoveryResult {
  reset_link?: string;
  email_sent?: boolean;
  expires_minutes?: number;
}

const MIN_REASON = 5;

/**
 * Giúp một người lấy lại tài khoản.
 *
 * Hộp thoại này không bao giờ cho quản trị viên đặt mật khẩu hộ: cả hai hành
 * động chỉ "mở lại cánh cửa", bước cuối vẫn do chính chủ đi. Mật khẩu CỦA quản
 * trị viên (nâng quyền) được hỏi ở bước sau qua `useSudo`, không nằm trong
 * state của hộp thoại này.
 *
 * Gửi liên kết xong thì hộp KHÔNG đóng mà hiện liên kết kèm nút sao chép: email
 * đăng ký có thể đã sai hoặc bỏ, và người cần hỗ trợ thường nhờ qua tin nhắn.
 */
export default function RecoveryModal({
  user,
  onClose,
  onConfirm,
}: {
  user: { username: string; email: string } | null;
  onClose: () => void;
  onConfirm: (payload: RecoveryPayload) => Promise<RecoveryResult | null | void> | void;
}) {
  const { t } = useI18n();
  const [action, setAction] = useState<RecoveryAction>("reset_link");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<RecoveryResult | null>(null);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const linkBox = useRef<HTMLInputElement>(null);

  if (!user) return null;
  // Lý do nhập nhanh: bấm một cái thay vì gõ. Người dùng sửa lại được.
  const quickReasons = [
    t("Chủ tài khoản nhờ qua tin nhắn"),
    t("Chủ tài khoản quên mật khẩu"),
    t("Chủ tài khoản mất điện thoại"),
  ];
  const valid = reason.trim().length >= MIN_REASON;

  const reset = () => {
    setReason("");
    setAction("reset_link");
    setDone(null);
    setCopy("idle");
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    try {
      const result = await onConfirm({ action, reason: reason.trim() });
      if (result && result.reset_link) {
        setDone(result);
        return;
      }
      if (result === null) return; // thất bại: giữ hộp mở, trang đã báo lỗi
      reset();
      onClose();
    } finally {
      setBusy(false);
    }
  };


  if (done?.reset_link) {
    const link = done.reset_link;
    const doCopy = async () => {
      const ok = await copyToClipboard(link);
      setCopy(ok ? "copied" : "failed");
      if (!ok) linkBox.current?.select();
    };
    return (
      <Modal isOpen onClose={close} title={t("Liên kết đặt lại mật khẩu cho {name}", { name: user.username })} size="md">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            {done.email_sent
              ? t("Đã gửi thư tới {email}. Nếu chủ tài khoản không nhận được, sao chép liên kết dưới đây và gửi trực tiếp cho họ.", { email: user.email })
              : t("Tài khoản này không có email nên không gửi thư được. Sao chép liên kết dưới đây và gửi trực tiếp cho chủ tài khoản.")}
          </p>
          <div className="flex gap-2">
            <input
              ref={linkBox}
              readOnly
              value={link}
              aria-label={t("Liên kết đặt lại mật khẩu")}
              onFocus={(e) => e.target.select()}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800"
            />
            <Button variant="primary" onClick={() => void doCopy()}>
              {copy === "copied" ? t("Đã sao chép") : t("Sao chép")}
            </Button>
          </div>
          <p role="status" aria-live="polite" className="min-h-[1.25rem] text-xs">
            {copy === "failed" && (
              <span className="text-red-700">
                {t("Trình duyệt không cho sao chép tự động. Liên kết đã được chọn sẵn, nhấn Ctrl+C.")}
              </span>
            )}
          </p>
          <ul className="list-disc space-y-1 rounded-lg bg-amber-50 p-3 pl-7 text-xs text-amber-900">
            <li>{t("Liên kết hết hạn sau {n} phút và chỉ dùng được một lần.", { n: done.expires_minutes ?? 30 })}</li>
            <li>{t("Chỉ gửi cho chính chủ tài khoản. Ai có liên kết này đều đặt được mật khẩu mới.")}</li>
            <li>{t("Việc hiện liên kết đã được ghi vào nhật ký kiểm toán.")}</li>
          </ul>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={close}>
              {t("Xong")}
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  const options: { value: RecoveryAction; title: string; hint: string; icon: ReactNode }[] = [
    {
      value: "reset_link",
      title: t("Gửi liên kết đặt lại mật khẩu"),
      hint: t("Gửi thư tới {email} và hiện liên kết để bạn sao chép, gửi qua kênh khác nếu thư không tới.", { email: user.email || "—" }),
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
