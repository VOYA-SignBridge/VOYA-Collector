import { useCallback } from "react";
import axiosClient from "../api/axiosClient";
import { friendlyError } from "../lib/errors";
import { tr } from "../i18n";

/**
 * Nâng quyền tạm thời cho những thao tác máy chủ đánh dấu `require_sudo`.
 *
 * Vì sao dùng `window.prompt` chứ không phải một hộp thoại tự vẽ
 * ---------------------------------------------------------------
 * Mật khẩu đi thẳng từ prompt tới `/admin/sudo` và **không bao giờ nằm trong
 * state của React**. Một ô `<input>` tự dựng sẽ giữ nó trong state, nghĩa là
 * nó xuất hiện trong bản chụp devtools, trong mọi lượt render lại, và trong
 * bất cứ công cụ ghi lại phiên nào đang cắm vào trang. Với một chuỗi mà chủ dự
 * án đã yêu cầu không được lưu ở đâu cả, prompt là lựa chọn đúng dù xấu hơn.
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
  const ensureSudo = useCallback(async (why: string) => {
    const password = window.prompt(tr("{viec} cần xác thực lại. Nhập mật khẩu của bạn:", { viec: why }));
    if (!password) return false;
    try {
      await axiosClient.post("/api/v1/admin/sudo", { password });
      return true;
    } catch {
      return false;
    }
  }, []);

  const sudoError = useCallback(
    (err: unknown) => friendlyError(err, tr("Mật khẩu không đúng hoặc phiên đã hết hạn.")),
    [],
  );

  return { ensureSudo, sudoError };
}
