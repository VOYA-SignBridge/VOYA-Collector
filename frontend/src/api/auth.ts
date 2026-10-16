import axiosClient, { clearAuthToken, setAuthToken } from "./axiosClient";

export type AuthUser = {
  id: string;
  username: string;
  email: string;
  is_active?: boolean;
  is_admin?: boolean;
  created_at?: string | null;
  /**
   * Tổ chức nhà của tài khoản.
   *
   * `UserOut` phía máy chủ đã trả trường này từ đợt v4, nhưng kiểu ở đây chưa
   * khai nên không màn hình nào dùng được. Trang "Tổ chức của tôi" cần nó: đó là
   * thứ duy nhất cho biết phải hỏi API về tenant NÀO — giao diện không được đoán,
   * và cũng không được để người dùng gõ vào.
   */
  tenant_id?: string | null;
  /**
   * Vai của tài khoản TRONG tổ chức của nó — `admin` · `editor` · `viewer`, hoặc
   * `null` khi không có vai nào ở tầng tenant.
   *
   * Khác hẳn `is_admin`, vốn là quản trị **nền tảng**. Trước khi có trường này,
   * thanh điều hướng chỉ đọc được `is_admin`, nên quản trị viên của một tổ chức
   * không thấy console của chính mình dù máy chủ cho họ vào.
   *
   * Dùng để VẼ giao diện, không phải để quyết định quyền — quyền do
   * `require_tenant_admin` cưỡng chế ở từng điểm cuối.
   */
  tenant_role?: string | null;
};

/**
 * Vai ở tầng tenant được vào console tổ chức.
 *
 * Phải khớp `tenant_admin.TENANT_ADMIN_ROLES` phía máy chủ, hiện là `("admin",)`
 * — vai ở tầng tenant là `admin` · `editor` · `viewer`, KHÔNG có tiền tố
 * `tenant_`. Danh sách này chỉ quyết định link có hiện hay không; lệch nhau thì
 * hậu quả là một link thừa dẫn tới 403, không phải một lỗ quyền.
 */
export const TENANT_ADMIN_ROLES = ["admin"] as const;

export function isTenantAdmin(user: AuthUser | null | undefined): boolean {
  if (!user) return false;
  if (user.is_admin) return true; // cửa thoát hiểm của người vận hành nền tảng
  return TENANT_ADMIN_ROLES.includes(
    (user.tenant_role ?? "") as (typeof TENANT_ADMIN_ROLES)[number],
  );
}

export type RegisterPayload = {
  username: string;
  email: string;
  password: string;
  /** Tên tổ chức, dùng để đặt tên cho tenant mà lượt đăng ký này tạo ra. */
  organization_name?: string;
  /**
   * Gói cho tổ chức vừa tạo. Chỉ gói tự phục vụ được nhận; máy chủ từ chối
   * phần còn lại, nên biểu mẫu không được cho chọn chúng.
   */
  plan_code?: string;
  /**
   * Số hiệu bản văn bản mà người dùng vừa đọc và đồng ý.
   *
   * Máy chủ đối chiếu lại số hiệu này với bản đang hiệu lực; gửi số cũ sẽ bị
   * từ chối với mã `stale_version` chứ không được ghi nhận. Bỏ trống là hợp lệ
   * khi hệ thống chưa công bố văn bản nào — công bố chính là hành động bật
   * cưỡng chế.
   */
  accepted_terms_version?: string;
  accepted_privacy_version?: string;
  /**
   * Mã lời mời, khi người này gia nhập một tổ chức có sẵn thay vì tự lập.
   *
   * Máy chủ kiểm mã **trước khi** tạo tài khoản, và đòi địa chỉ email khớp với
   * địa chỉ lời mời được phát cho. Lời mời nêu đích danh một người; ai cầm
   * được đường liên kết cũng không vì thế mà thành người đó.
   */
  invitation_token?: string;
};

export type LoginPayload = {
  identifier: string;
  password: string;
};

export async function register(payload: RegisterPayload): Promise<AuthUser> {
  const res = await axiosClient.post("/api/v1/auth/register", payload);
  return res.data as AuthUser;
}

/** Login sets httpOnly auth cookies server-side and returns the user profile
 *  (no token in the body — the browser can't read the httpOnly cookies). */
/**
 * Kết quả bước một. Hai hình dạng, và phải phân biệt được ở kiểu dữ liệu.
 *
 * Nếu gộp làm một kiểu với vài trường tuỳ chọn, chỗ gọi sẽ đọc `user.username`
 * của một phản hồi chỉ có vé — TypeScript im lặng, giao diện hiện `undefined`.
 */
export type LoginResult =
  | { kind: "session"; user: AuthUser }
  | { kind: "two_factor"; challenge: string };

export async function login(payload: LoginPayload): Promise<LoginResult> {
  const res = await axiosClient.post("/api/v1/auth/login", payload);
  // Purge any legacy localStorage Bearer token from the pre-cookie era: if it
  // lingered, every request would carry a stale Authorization header alongside
  // the fresh cookie and could shadow the new session.
  clearAuthToken();
  setAuthToken(null);

  const data = res.data as Record<string, unknown>;
  if (data?.two_factor_required) {
    return { kind: "two_factor", challenge: String(data.challenge ?? "") };
  }
  return { kind: "session", user: res.data as AuthUser };
}

/** Bước hai: đổi vé + mã (TOTP hoặc mã khôi phục) lấy một phiên thật. */
export async function loginTwoFactor(
  challenge: string, code: string,
): Promise<AuthUser> {
  const res = await axiosClient.post("/api/v1/auth/login/2fa", { challenge, code });
  return res.data as AuthUser;
}

/** Revoke the refresh token server-side and clear all auth cookies. */
export async function logout(): Promise<void> {
  try {
    await axiosClient.post("/api/v1/auth/logout");
  } catch {
    // Best-effort: even if the call fails, the client clears local state.
  }
}

export async function me(): Promise<AuthUser> {
  const res = await axiosClient.get("/api/v1/auth/me");
  return res.data as AuthUser;
}

/**
 * Kết quả một lượt đổi tên tài khoản.
 *
 * `rows` là số hàng đã đổi ở từng chỗ cái tên bị chép tới — `samples.username`,
 * `raw_uploads.*`, `signers.display_name`, cột `user_id` trong `samples.csv`.
 * Nó có mặt trong phản hồi vì đổi tên KHÔNG phải một câu `UPDATE users`: nó
 * chạm vào dữ liệu đã đóng góp, và người bấm nút xứng đáng được thấy điều đó
 * thay vì tin lời.
 *
 * `changed: false` nghĩa là tên mới trùng tên cũ — không phải lỗi, và không có
 * hàng nào bị chạm.
 */
export type RenameResult = {
  changed: boolean;
  old_username: string;
  new_username: string;
  rows: Record<string, number>;
};

export async function updateUsername(username: string): Promise<RenameResult> {
  const res = await axiosClient.patch("/api/v1/auth/me", { username });
  return res.data as RenameResult;
}

export type MessageResponse = {
  message: string;
};

/**
 * Đặt lại mật khẩu bằng ĐƯỜNG LIÊN KẾT gửi vào hộp thư.
 *
 * **Không màn hình nào còn gọi hàm này.** Từ 10/08/2026 luồng quên mật khẩu
 * chạy bằng mã sáu chữ số (`api/verification.ts`) — một cửa duy nhất, vì hai
 * cửa trả lời cùng một câu hỏi chỉ bắt người dùng chọn giữa hai chi tiết triển
 * khai. Hàm và endpoint được giữ lại để những liên kết đã gửi đi còn dùng được
 * (xem `/reset-password`), không phải để nối lại vào giao diện.
 */
export async function forgotPassword(identifier: string): Promise<MessageResponse> {
  const res = await axiosClient.post("/api/v1/auth/forgot-password", { identifier });
  return res.data as MessageResponse;
}

export async function resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
  const res = await axiosClient.post("/api/v1/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return res.data as MessageResponse;
}

/**
 * Đổi mật khẩu khi ĐANG đăng nhập.
 *
 * `code` chỉ cần khi tài khoản đã bật xác thực hai bước, và nhận CẢ mã TOTP sáu
 * chữ số lẫn mã khôi phục `xxxxx-xxxxx`. Máy chủ trả 400 kèm
 * `detail.code === "2fa_required"` khi thiếu — giao diện dùng đúng mã đó để mở
 * ô nhập, thay vì đoán trước bằng cách hỏi `/2fa/status`. Đoán trước là hai
 * nguồn sự thật cho cùng một câu hỏi, và chúng lệch nhau ngay khi người dùng
 * bật 2FA ở một tab khác.
 *
 * Thành công nghĩa là **mọi thiết bị đã bị đăng xuất**, kể cả tab đang gọi. Chỗ
 * gọi phải nói trước điều đó rồi mới đưa người dùng về màn hình đăng nhập.
 */
export async function changePassword(payload: {
  currentPassword: string;
  newPassword: string;
  code?: string;
}): Promise<MessageResponse> {
  const res = await axiosClient.post("/api/v1/auth/change-password", {
    current_password: payload.currentPassword,
    new_password: payload.newPassword,
    code: payload.code || undefined,
  });
  return res.data as MessageResponse;
}

/**
 * Đổi email: hai bước, mã gửi tới ĐỊA CHỈ MỚI.
 *
 * Thứ cần chứng minh là "bạn đọc được hộp thư mới" — "bạn đọc được hộp thư cũ"
 * đã được chứng minh bằng việc đang đăng nhập. Mật khẩu hỏi ở cả hai bước: bước
 * đầu chỉ gửi một lá thư, bước sau mới đổi địa chỉ nhận thư khôi phục tài
 * khoản, tức bước có thể biến một phiên bị chiếm thành mất tài khoản vĩnh viễn.
 */
export async function startEmailChange(payload: {
  currentPassword: string;
  newEmail: string;
}): Promise<{ challenge_id: string; sent_to: string; expires_in_minutes: number }> {
  const res = await axiosClient.post("/api/v1/auth/change-email/start", {
    current_password: payload.currentPassword,
    new_email: payload.newEmail,
  });
  return res.data;
}

export async function confirmEmailChange(payload: {
  currentPassword: string;
  code: string;
}): Promise<{ email: string; email_verified: boolean }> {
  const res = await axiosClient.post("/api/v1/auth/change-email/confirm", {
    current_password: payload.currentPassword,
    code: payload.code,
  });
  return res.data;
}