import { useState } from "react";

const PRESET_REASONS = [
  "Vi phạm điều khoản sử dụng",
  "Đăng tải nội dung không phù hợp",
  "Hành vi spam / lạm dụng dịch vụ",
  "Chia sẻ tài khoản trái phép",
  "Tạm khóa để xác minh / điều tra",
];

const DURATIONS: { label: string; value: number }[] = [
  { label: "1 giờ", value: 60 * 60 },
  { label: "24 giờ", value: 24 * 60 * 60 },
  { label: "7 ngày", value: 7 * 24 * 60 * 60 },
  { label: "30 ngày", value: 30 * 24 * 60 * 60 },
  { label: "Vĩnh viễn", value: 0 },
];

export interface LockPayload { reason: string; duration_seconds: number }

export default function LockUserModal({
  username, open, onClose, onConfirm,
}: {
  username: string | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (payload: LockPayload) => Promise<void> | void;
}) {
  const [preset, setPreset] = useState(PRESET_REASONS[0]);
  const [custom, setCustom] = useState("");
  const [duration, setDuration] = useState<number>(24 * 60 * 60);
  const [busy, setBusy] = useState(false);

  if (!open || !username) return null;
  const reason = custom.trim() || preset;

  const submit = async () => {
    setBusy(true);
    try {
      await onConfirm({ reason, duration_seconds: duration });
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
          <span className="text-lg">🔒</span>
          <h3 className="text-lg font-bold text-slate-900">Khóa tài khoản</h3>
        </div>
        <p className="text-sm text-slate-500 mb-4">
          Khóa tài khoản <span className="font-semibold text-slate-700">{username}</span>. Người dùng sẽ bị đăng xuất và thấy thông báo kèm lý do bên dưới.
        </p>

        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Lý do</label>
        <div className="space-y-1.5 mb-3">
          {PRESET_REASONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input type="radio" name="lockreason" checked={!custom && preset === r} onChange={() => { setPreset(r); setCustom(""); }} className="accent-ctu-blue" />
              {r}
            </label>
          ))}
        </div>
        <input
          type="text"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          placeholder="…hoặc nhập lý do khác"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-ctu-blue/40"
        />

        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Thời hạn khóa</label>
        <div className="flex flex-wrap gap-2 mb-6">
          {DURATIONS.map((d) => (
            <button
              key={d.label}
              onClick={() => setDuration(d.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                duration === d.value ? "bg-ctu-blue text-white border-ctu-blue" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors">Hủy</button>
          <button onClick={submit} disabled={busy}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50">
            {busy ? "Đang khóa…" : "Khóa tài khoản"}
          </button>
        </div>
      </div>
    </div>
  );
}
