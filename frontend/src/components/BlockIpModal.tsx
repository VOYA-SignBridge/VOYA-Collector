/**
 * @i18n-key-table — `PRESET_REASONS` và `DURATIONS` là bảng KHOÁ, dịch tại chỗ dựng.
 */
import { useState } from "react";
import { BanIcon } from "./ui/Icons";
import { Trans, useI18n } from "../i18n";

const PRESET_REASONS = [
  "Gửi quá nhiều request (nghi bot/quét)",
  "Hoạt động đáng ngờ",
  "Spam / lạm dụng dịch vụ",
  "Vi phạm điều khoản sử dụng",
  "Dò mật khẩu / tấn công đăng nhập",
];

const DURATIONS: { label: string; value: number }[] = [
  { label: "15 phút", value: 15 * 60 },
  { label: "1 giờ", value: 60 * 60 },
  { label: "6 giờ", value: 6 * 60 * 60 },
  { label: "24 giờ", value: 24 * 60 * 60 },
  { label: "7 ngày", value: 7 * 24 * 60 * 60 },
  { label: "Vĩnh viễn", value: 0 },
];

export interface BlockPayload { reason: string; duration_seconds: number }

export default function BlockIpModal({
  ip, open, onClose, onConfirm,
}: {
  ip: string | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (ip: string, payload: BlockPayload) => Promise<void> | void;
}) {
  const { t } = useI18n();
  const [preset, setPreset] = useState(PRESET_REASONS[0]);
  const [custom, setCustom] = useState("");
  const [duration, setDuration] = useState<number>(60 * 60);
  const [busy, setBusy] = useState(false);

  if (!open || !ip) return null;
  const reason = custom.trim() || preset;

  const submit = async () => {
    setBusy(true);
    try {
      await onConfirm(ip, { reason, duration_seconds: duration });
      onClose();
      setCustom("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="max-w-lg w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-1">
          <BanIcon className="h-5 w-5"  aria-hidden="true" />
          <h3 className="text-lg font-bold text-slate-900">{t("Chặn IP")}</h3>
        </div>
        <p className="text-sm text-slate-500 mb-4">
          <Trans
            k="Chặn {ip}. Người dùng sẽ thấy thông báo kèm lý do bên dưới."
            vars={{
              ip: <span className="font-mono font-medium text-slate-700">{ip}</span>,
            }}
          />
        </p>

        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{t("Lý do")}</label>
        <div className="space-y-1.5 mb-3">
          {PRESET_REASONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input type="radio" name="reason" checked={!custom && preset === r} onChange={() => { setPreset(r); setCustom(""); }} className="accent-ctu-blue" />
              {t(r)}
            </label>
          ))}
        </div>
        <input
          type="text"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          placeholder={t("…hoặc nhập lý do khác")}
          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-ctu-blue/40"
        />

        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{t("Thời hạn chặn")}</label>
        <div className="flex flex-wrap gap-2 mb-6">
          {DURATIONS.map((d) => (
            <button
              key={d.label}
              onClick={() => setDuration(d.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                duration === d.value
                  ? "bg-ctu-blue text-white border-ctu-blue"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {t(d.label)}
            </button>
          ))}
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors">
            {t("Hủy")}
          </button>
          <button onClick={submit} disabled={busy}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50">
            {busy ? t("Đang chặn…") : t("Chặn IP")}
          </button>
        </div>
      </div>
    </div>
  );
}
