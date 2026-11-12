import { useCallback } from "react";
import axiosClient from "../api/axiosClient";
import { friendlyError } from "../lib/errors";
import { tr } from "../i18n";
import { askPassword } from "../lib/askPassword";

/**
 * Nâng quyền tạm thời cho những thao tác máy chủ đánh dấu `require_sudo`.
 *
 * Mật khẩu được hỏi bằng `lib/askPassword` — ô che ký tự, dựng bằng DOM thuần
 * nên mật khẩu không bao giờ vào state của React. (Bản trước dùng
 * `window.prompt`: ô chữ thường, mật khẩu hiện rõ trên màn hình.)
 *
 * Cách dùng — hỏi khi bị TỪ CHỐI, không hỏi trước:
 *
 * ```ts
 * try {
 *   await doTheThing();
 * } catch (err) {
 *   if (!isSudoRequired(err)) throw err;
 *   if (await ensureSudo("Đổi gói của một tổ chức")) await doTheThing();
 * }
 * ```
 *
 * Hỏi trước là bắt người vận hành gõ mật khẩu cho cả những lượt bấm mà phiên
 * sudo hiện tại vẫn còn hiệu lực.
 */

/** Máy chủ có đang đòi nâng quyền không. */
export function isSudoRequired(err: unknown): boolean {
  const data = (err as { response?: { data?: unknown } })?.response?.data as
    | { code?: string; detail?: { code?: string } }
    | undefined;
  return data?.code === "sudo_required" || data?.detail?.code === "sudo_required";
}

export function useSudo(): {
  ensureSudo: (why: string) => Promise<boolean>;
  sudoError: (err: unknown) => string;
} {
  const ensureSudo = useCallback(
    (why: string) =>
      askPassword({
        title: tr("Xác nhận lại mật khẩu"),
        message: tr("{viec} cần xác thực lại. Nhập mật khẩu của bạn:", { viec: why }),
        verify: async (password) => {
          try {
            await axiosClient.post("/api/v1/admin/sudo", { password });
            return null;
          } catch (err) {
            return friendlyError(err, tr("Mật khẩu không đúng hoặc phiên đã hết hạn."));
          }
        },
      }),
    [],
  );

  const sudoError = useCallback(
    (err: unknown) => friendlyError(err, tr("Mật khẩu không đúng hoặc phiên đã hết hạn.")),
    [],
  );

  return { ensureSudo, sudoError };
}
