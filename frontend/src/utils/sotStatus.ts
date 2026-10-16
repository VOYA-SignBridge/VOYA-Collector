/**
 * Kết luận MỘT CÂU về bản dữ liệu chuẩn (SOT) cho người vận hành.
 *
 * Trang SOT trước 13/09/2026 (SOT-02) trải ra `Verify`, `publish`, `signed_by`,
 * fingerprint… và để người đọc tự ghép thành câu trả lời. Sáu trạng thái dưới
 * đây là sáu câu trả lời khác nhau cho "dữ liệu chuẩn đang thế nào?", và chúng
 * KHÔNG được gộp: "chưa kiểm tra" không phải "kiểm tra thất bại", "không kết
 * nối được kho" không phải "kho chưa có bản nào".
 *
 * Hàm thuần, không phụ thuộc React — để kiểm từng nhánh bằng bảng.
 *
 * @i18n-key-table — `headline`/`nextStep` là KHOÁ từ điển, dịch ở nơi dùng
 * bằng `t(...)`; bản EN nằm trong vùng `@i18n-dynamic` của `i18n/en.ts`.
 */

import type { SotRemote, SotVerifyResult } from "../api/sot";

export type SotConclusionKind =
  | "checking"
  | "unreachable"
  | "nothing_published"
  | "untrusted_source"
  | "unchecked"
  | "verified"
  | "verify_failed";

export interface SotConclusion {
  kind: SotConclusionKind;
  /** Kết luận, tiếng Việt, một câu. Đây là KHOÁ từ điển (dịch bằng `t()`). */
  headline: string;
  /** Việc cần làm tiếp — hoặc `null` khi không cần làm gì. */
  nextStep: string | null;
  /** Sắc thái để chọn biểu tượng/màu; màu không phải kênh duy nhất. */
  tone: "neutral" | "ok" | "warn" | "bad";
}

export function sotConclusion(input: {
  remote: SotRemote | null;
  remoteLoading: boolean;
  verify: SotVerifyResult | null;
  verifying: boolean;
}): SotConclusion {
  const { remote, remoteLoading, verify, verifying } = input;

  if (remoteLoading || verifying) {
    return {
      kind: "checking",
      headline: "Đang kiểm tra kho bản dữ liệu chuẩn…",
      nextStep: null,
      tone: "neutral",
    };
  }
  if (!remote || remote.available === false) {
    return {
      kind: "unreachable",
      headline: "Không kết nối được với kho bản dữ liệu chuẩn.",
      nextStep: "Kiểm tra quyền truy cập Google Drive của máy chủ rồi bấm Làm mới.",
      tone: "bad",
    };
  }
  if (!remote.published) {
    return {
      kind: "nothing_published",
      headline: "Kho truy cập được nhưng chưa có bản dữ liệu chuẩn nào được công bố.",
      nextStep: "Công bố từ máy được cấp quyền (SignBridge_SE).",
      tone: "warn",
    };
  }
  if (remote.trusted === false) {
    return {
      kind: "untrusted_source",
      headline: "Có bản đã công bố nhưng KHÔNG xác minh được nguồn: chữ ký không thuộc máy nào được cấp quyền.",
      nextStep: "Đừng đồng bộ. Đối chiếu danh sách máy được cấp quyền và người đã công bố bản này.",
      tone: "bad",
    };
  }
  if (verify && !verify.ok) {
    return {
      kind: "verify_failed",
      headline: "Bản đã công bố KHÔNG qua được kiểm tra toàn vẹn.",
      nextStep: "Xem lỗi bên dưới; không dùng bản này cho tới khi kiểm tra lại đạt.",
      tone: "bad",
    };
  }
  if (verify && verify.ok) {
    return {
      kind: "verified",
      headline: "Bản dữ liệu chuẩn đã công bố và đã kiểm tra toàn vẹn thành công.",
      nextStep: null,
      tone: "ok",
    };
  }
  return {
    kind: "unchecked",
    headline: "Có bản đã công bố từ máy được cấp quyền, nhưng phiên này CHƯA kiểm tra toàn vẹn.",
    nextStep: "Bấm “Kiểm tra bản dữ liệu chuẩn” để xác nhận trước khi dựa vào nó.",
    tone: "warn",
  };
}
