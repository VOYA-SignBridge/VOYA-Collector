/**
 * Hộp thoại hiện KHOÁ RIÊNG của một máy ghi SOT — đúng một lần.
 *
 * Máy chủ không lưu khoá riêng (chỉ lưu khoá công khai), nên chuỗi trong hộp
 * này biến mất vĩnh viễn khi hộp đóng. Bản trước (SOT-01, 13/09/2026) đóng khi
 * bấm ra nền và nút Copy báo "Đã copy" vô điều kiện — kể cả khi
 * `navigator.clipboard` không tồn tại (trang mở qua HTTP thường) hay bị trình
 * duyệt từ chối. Hai lối mất khoá, cả hai đều im lặng.
 *
 * Mẫu tham chiếu: trang tạo *personal access token* của GitHub và màn hình
 * lộ khoá API của Stripe/AWS — "Make sure to copy it now. You won't be able to
 * see it again", không có nút đóng nào nằm cạnh đường thoát vô ý, và trạng
 * thái "đã sao chép" chỉ hiện sau khi trình duyệt xác nhận.
 *
 * Ba quy tắc của hộp này:
 *   1. KHÔNG đóng khi bấm nền hay nhấn Escape. Đóng chỉ bằng nút, và nút chỉ
 *      mở sau khi người dùng đã sao chép thành công HOẶC tự xác nhận đã lưu.
 *   2. "Đã sao chép" chỉ hiện sau `await clipboard.writeText` thành công; thất
 *      bại thì nói thẳng và chọn sẵn nội dung để Ctrl+C.
 *   3. Luôn có đường thủ công: tải về tệp `.key`.
 */

import { useEffect, useId, useRef, useState } from "react";

import { useI18n } from "../../i18n";

export interface PrivateKeyModalProps {
  name: string;
  privateKey: string;
  hint?: string;
  onClose: () => void;
}

type CopyState = "idle" | "copied" | "failed";

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard?.writeText) return false;
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export default function PrivateKeyModal({ name, privateKey, hint, onClose }: PrivateKeyModalProps) {
  const { t } = useI18n();
  const titleId = useId();
  const box = useRef<HTMLTextAreaElement>(null);
  const [copy, setCopy] = useState<CopyState>("idle");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    box.current?.focus();
    box.current?.select();
  }, []);

  const doCopy = async () => {
    const ok = await copyToClipboard(privateKey);
    setCopy(ok ? "copied" : "failed");
    if (!ok) {
      box.current?.focus();
      box.current?.select();
    }
  };

  const canClose = copy === "copied" || saved;
  const downloadHref = `data:application/octet-stream;charset=utf-8,${encodeURIComponent(privateKey)}`;
  const fileName = `${name.replace(/[^\w.-]+/g, "_") || "may-ghi"}.key`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      data-testid="private-key-backdrop"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
      >
        <h3 id={titleId} className="text-lg font-bold text-slate-900">
          {t("Khoá riêng của máy “{name}”", { name })}
        </h3>
        <p className="mt-1 text-sm font-medium text-amber-700">
          {hint || t("Lưu ngay — chỉ hiển thị một lần. Máy chủ không giữ khoá riêng, đóng hộp này là mất.")}
        </p>

        <textarea
          ref={box}
          readOnly
          value={privateKey}
          rows={4}
          aria-label={t("Khoá riêng")}
          className="mt-3 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800"
          onFocus={(e) => e.target.select()}
        />

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void doCopy()}
            className="rounded-lg bg-ctu-blue px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-ctu-blue/90"
          >
            {copy === "copied" ? t("Đã sao chép") : t("Sao chép")}
          </button>
          <a
            href={downloadHref}
            download={fileName}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {t("Tải về tệp .key")}
          </a>
        </div>

        {/* Trạng thái nói bằng CHỮ, có role=status để trình đọc màn hình đọc được. */}
        <p role="status" aria-live="polite" className="mt-2 min-h-[1.25rem] text-xs">
          {copy === "copied" && (
            <span className="text-ctu-blue">{t("Đã sao chép vào bộ nhớ tạm. Dán vào nơi lưu an toàn trước khi đóng.")}</span>
          )}
          {copy === "failed" && (
            <span className="text-red-700">
              {t("Trình duyệt không cho sao chép tự động. Nội dung đã được chọn sẵn — nhấn Ctrl+C (⌘C), hoặc tải về tệp.")}
            </span>
          )}
        </p>

        <label className="mt-3 flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={saved}
            onChange={(e) => setSaved(e.target.checked)}
            className="mt-0.5"
          />
          <span>{t("Tôi đã lưu khoá riêng vào nơi an toàn và hiểu rằng không xem lại được.")}</span>
        </label>

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={!canClose}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Đã lưu, đóng")}
          </button>
        </div>
      </div>
    </div>
  );
}
