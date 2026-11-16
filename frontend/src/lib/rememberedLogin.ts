/**
 * Tên đăng nhập của lần đăng nhập có tick "Ghi nhớ", để điền sẵn vào ô lần sau.
 *
 * Chỉ giữ TÊN, không bao giờ giữ mật khẩu hay token. Lưu ở trình duyệt chứ
 * không ở máy chủ: đây là tiện ích của thiết bị này, và `localStorage` có thể
 * bị chặn (chế độ riêng tư) nên mọi lối vào đều chịu được việc nó ném lỗi.
 */
const KEY = "voya:remembered-login";

export function readRememberedLogin(): string {
  try {
    return localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

/** Nhớ `identifier` nếu `remember`, ngược lại quên: bỏ tick là rút lại lựa chọn. */
export function saveRememberedLogin(identifier: string, remember: boolean): void {
  try {
    if (remember) localStorage.setItem(KEY, identifier);
    else localStorage.removeItem(KEY);
  } catch {
    /* chế độ riêng tư / hết dung lượng: chỉ mất phần điền sẵn */
  }
}
