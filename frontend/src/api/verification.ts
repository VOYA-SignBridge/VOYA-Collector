/**
 * Mã dùng một lần (OTP): xác minh địa chỉ, và khôi phục tài khoản.
 *
 * Hai luồng, và chúng KHÁC nhau ở chỗ được phép tiết lộ bao nhiêu
 * ----------------------------------------------------------------
 * `/verify/*` chạy sau đăng nhập. Người gọi đã chứng minh mình là ai, nên máy
 * chủ nói thẳng: mã sai, còn phải đợi 40 giây, đã nhập sai quá số lần.
 *
 * `/recover/*` chạy trước đăng nhập. Ở đó **mọi câu trả lời đều giống nhau**,
 * bất kể tài khoản có tồn tại hay không — nếu khác nhau thì endpoint này thành
 * một cách để dò xem ai có tài khoản trên hệ thống. Hệ quả cho giao diện là
 * điều dễ làm sai nhất ở đây:
 *
 *   **Đừng bao giờ suy ra trạng thái tài khoản từ phản hồi của `/recover/*`.**
 *   Gõ nhầm địa chỉ vẫn nhận "đã gửi mã". Màn hình phải nói "nếu tài khoản tồn
 *   tại" chứ không được nói "đã gửi mã tới bạn" — câu sau là một lời nói dối
 *   với người vừa gõ nhầm, và họ sẽ ngồi đợi một mã không bao giờ tới.
 *
 * Vì sao không có hàm nào nhận `challenge_id`
 * --------------------------------------------
 * Máy chủ ràng buộc mã vào cặp (tài khoản, mục đích) và cho phép đúng MỘT thử
 * thách còn sống mỗi cặp. Giao diện không cần mang `challenge_id` đi đâu cả;
 * mang theo chỉ tạo thêm một thứ có thể lệch với thực tế ở máy chủ.
 */

import axiosClient from "./axiosClient";

const API_PREFIX = "/api/v1/auth";

export type OtpChannel = "email" | "sms";

export interface VerificationStatus {
  email: string;
  email_verified: boolean;
  /** Rỗng khi tài khoản chưa từng xác minh số nào. */
  phone_number: string;
  phone_verified: boolean;
  /** Giây phải đợi giữa hai lần xin mã. Lấy từ máy chủ, đừng viết cứng. */
  resend_cooldown_seconds: number;
  code_ttl_minutes: number;
  /**
   * Bản triển khai này có gửi được SMS không.
   *
   * `false` là trạng thái BÌNH THƯỜNG ở đây — chưa có nhà cung cấp SMS nào
   * được cấu hình. Giao diện phải khoá kênh SMS thay vì để người dùng bấm gửi
   * rồi nhận 503: một thử thách được cấp mà không giao được sẽ đốt luôn thời
   * gian chờ, khiến họ không xin lại mã qua email được trong một phút.
   */
  sms_available: boolean;
}

export interface CodeSent {
  challenge_id: string;
  purpose: string;
  channel: OtpChannel;
  expires_in_minutes: number;
}

export interface CodeConfirmed {
  verified: boolean;
  purpose: string;
  channel: OtpChannel;
}

// ------------------------------------------------------- sau đăng nhập

export async function fetchVerificationStatus(): Promise<VerificationStatus> {
  const res = await axiosClient.get<VerificationStatus>(`${API_PREFIX}/verification-status`);
  return res.data;
}

/**
 * Xin một mã để chứng minh mình sở hữu địa chỉ.
 *
 * `destination` bỏ trống với kênh email nghĩa là "địa chỉ đang gắn với tài
 * khoản". Với SMS thì **bắt buộc**, vì tài khoản có thể chưa có số nào — đó
 * đúng là lý do người ta xác minh một số.
 */
export async function sendVerificationCode(
  channel: OtpChannel,
  destination?: string,
): Promise<CodeSent> {
  const res = await axiosClient.post<CodeSent>(`${API_PREFIX}/verify/send`, {
    channel,
    ...(destination ? { destination } : {}),
  });
  return res.data;
}

/** Mục đích của một thử thách xác minh. Không gồm `reset_password` — mã đó nộp
 *  qua `/recover/confirm`, cùng lúc với mật khẩu mới. */
export type VerifyPurpose = "verify_email" | "verify_phone";

/**
 * Nộp mã, kèm theo việc nói rõ nó trả lời cho thử thách nào.
 *
 * Bỏ trống `purpose` vẫn chạy — máy chủ sẽ thử `verify_phone` rồi
 * `verify_email` — nhưng phép thử đó **không miễn phí**: mỗi lần đoán sai đều
 * trừ lượt của thử thách nó chạm vào. Ai đang mở cả hai thử thách mà gõ nhầm mã
 * email hai lần thì mất bốn trong mười lượt, một nửa số đó của thử thách họ
 * không hề trả lời.
 *
 * Trang xác minh chỉ mở một luồng tại một thời điểm nên không dính bẫy này,
 * nhưng vẫn gửi `purpose`: khi đó điều bảo đảm nằm trong chính yêu cầu, chứ
 * không nằm trong máy trạng thái của một màn hình.
 */
export async function confirmVerificationCode(
  code: string,
  purpose?: VerifyPurpose,
): Promise<CodeConfirmed> {
  const res = await axiosClient.post<CodeConfirmed>(`${API_PREFIX}/verify/confirm`, {
    code: code.trim(),
    ...(purpose ? { purpose } : {}),
  });
  return res.data;
}

// -------------------------------------------------- trước đăng nhập

/**
 * Bắt đầu khôi phục tài khoản.
 *
 * Trả về câu chung do máy chủ soạn. Câu đó là câu duy nhất — thành công, tài
 * khoản không tồn tại, gửi thất bại, hay đang trong thời gian chờ đều ra đúng
 * chuỗi này. **Đừng thêm dấu tích xanh cạnh nó.**
 */
export async function startRecovery(
  identifier: string,
  channel: OtpChannel = "email",
): Promise<{ message: string }> {
  const res = await axiosClient.post<{ message: string }>(`${API_PREFIX}/recover/start`, {
    identifier: identifier.trim(),
    channel,
  });
  return res.data;
}

/**
 * Nộp mã. Trả về một vé sống 5 phút để đổi lấy mật khẩu mới.
 *
 * Hai bước chứ không một, vì màn hình phải trả lời được "mã của tôi có đúng
 * không?" TRƯỚC khi bắt người ta nghĩ ra một mật khẩu. Gộp lại thì mọi lần gõ
 * nhầm một chữ số đều phải trả giá bằng cả một mật khẩu vừa nhập.
 *
 * Cái giá đã trả cho việc tách: máy chủ dùng CHUNG bộ đếm tần suất cho
 * `/recover/verify` và `/recover/confirm`, nếu không thì tách biểu mẫu làm đôi
 * là tự nhân đôi số lần đoán mã cho phép.
 *
 * Mã bị **tiêu** ngay tại đây. Bỏ dở giữa chừng thì phải xin mã mới — đúng như
 * Google/Facebook, và là điều duy nhất đúng: một mã còn sống sau khi đã dùng là
 * một mã nằm trong hộp thư chờ người khác đọc.
 */
export async function verifyRecoveryCode(
  identifier: string,
  code: string,
): Promise<{ reset_ticket: string; expires_in_minutes: number }> {
  const res = await axiosClient.post(`${API_PREFIX}/recover/verify`, {
    identifier: identifier.trim(),
    code: code.trim(),
  });
  return res.data;
}

/**
 * Đổi vé lấy mật khẩu mới. Mọi phiên cũ trên mọi thiết bị bị thu hồi.
 *
 * Vé hết hạn cho ra lời từ chối KHÁC với mã sai, và điều đó an toàn: cầm được
 * vé đã chứng minh mã từng đúng, nên câu này không tiết lộ gì thêm. Nói "mã
 * sai" ở đây sẽ đẩy người ta quay lại đọc một mã đã tiêu — việc duy nhất chắc
 * chắn không cứu được họ.
 */
export async function resetPasswordWithTicket(
  resetTicket: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await axiosClient.post<{ message: string }>(`${API_PREFIX}/recover/confirm`, {
    reset_ticket: resetTicket,
    new_password: newPassword,
  });
  return res.data;
}
