import { tr } from "../i18n";
// Map machine-readable QC codes from the backend to Vietnamese UI messages.
// The server also sends fallback message strings, but the UI never trusts
// them — codes are the contract, text lives here.

const HAND_WORD: Record<number, string> = { 1: "1 tay", 2: "2 tay" };

export function qcMessage(code: string, detail?: Record<string, unknown>): string {
  const hands = typeof detail?.hands_required === "number" ? detail.hands_required : undefined;
  const handsText = hands !== undefined ? HAND_WORD[hands] ?? `${hands} tay` : tr("đủ tay");
  const completeness = typeof detail?.completeness === "number" ? detail.completeness : undefined;
  const pct = completeness !== undefined ? Math.round(completeness * 100) : undefined;

  switch (code) {
    case "MISSING_REQUIRED_HAND":
      return pct !== undefined
        ? tr("Chỉ phát hiện {handsText} ở {pct}% khung hình — ký hiệu này cần {handsText2}. Mẫu vẫn được lưu nhưng sẽ bị đánh dấu để kiểm tra.", { handsText, pct, handsText2: handsText })
        : tr("Không phát hiện đủ {handsText} trong phần lớn khung hình. Mẫu vẫn được lưu nhưng sẽ bị đánh dấu để kiểm tra.", { handsText });
    case "HIGH_JITTER":
      return "Chuyển động tay bị rung/nhiễu nhiều. Hãy giữ tay ổn định trong khung hình. Mẫu vẫn được lưu nhưng sẽ bị đánh dấu.";
    case "LOW_HAND_PRESENCE":
      return "Nhiều khung hình không phát hiện được tay. Hãy giữ tay trong khung hình. Mẫu vẫn được lưu nhưng sẽ bị đánh dấu.";
    case "QC_HANDS_MISSING":
      return tr("Mẫu bị từ chối: ký hiệu này cần {handsText} nhưng hầu như không phát hiện đủ. Vui lòng thu lại.", { handsText });
    case "QC_EXTREME_JITTER":
      return "Mẫu bị từ chối do dữ liệu tay bị nhiễu quá mạnh. Vui lòng thu lại ở nơi đủ sáng và giữ tay trong khung hình.";
    case "QC_TOO_FEW_VALID_FRAMES":
      return "Mẫu bị từ chối: quá nhiều khung hình trống (không thấy tay). Vui lòng thu lại.";
    default:
      return "Chất lượng mẫu thấp — mẫu đã được đánh dấu để kiểm tra.";
  }
}

/** True when the code is a hard reject (sample was NOT saved). */
export function isRejectCode(code: string): boolean {
  return code.startsWith("QC_");
}
