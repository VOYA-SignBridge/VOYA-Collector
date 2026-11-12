import { tr } from "../i18n";

/**
 * Hộp hỏi lại mật khẩu của CHÍNH người đang thao tác (nâng quyền / sudo).
 *
 * Vì sao không dùng `window.prompt`
 * ---------------------------------
 * Bản trước dùng prompt để mật khẩu không bao giờ vào state của React. Nhưng
 * prompt của trình duyệt là ô chữ THƯỜNG: mật khẩu hiện rõ trên màn hình, ai
 * đứng sau lưng hay chụp màn hình là thấy (sự cố thật 12/11/2026). Đổi một rủi
 * ro lý thuyết (devtools) lấy một rủi ro nhìn thấy được là đổi sai chiều.
 *
 * Vì sao dựng bằng DOM thuần chứ không phải component React
 * ---------------------------------------------------------
 * Giữ nguyên lý do ban đầu: mật khẩu chỉ nằm trong `input.value` của một phần
 * tử tự huỷ, không đi qua state/props, không bị re-render sao chép, không hiện
 * trong React DevTools. Phần tử bị gỡ khỏi DOM ngay khi đóng.
 *
 * `verify` nhận mật khẩu, trả `null` nếu đạt hoặc một câu báo lỗi — sai mật
 * khẩu thì báo ngay trong hộp cho gõ lại, không bắt bấm lại từ đầu.
 */
export function askPassword(opts: {
  title: string;
  message: string;
  verify: (password: string) => Promise<string | null>;
}): Promise<boolean> {
  return new Promise((resolve) => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const root = document.createElement("div");
    root.className = "fixed inset-0 z-[60] flex items-center justify-center p-4";
    root.innerHTML = `
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" data-role="backdrop"></div>
      <form role="dialog" aria-modal="true" aria-labelledby="ask-pw-title" aria-describedby="ask-pw-msg"
            class="relative w-full max-w-sm rounded-xl bg-white p-5 shadow-xl">
        <h2 id="ask-pw-title" class="text-lg font-semibold text-slate-900"></h2>
        <p id="ask-pw-msg" class="mt-1 text-sm text-slate-600"></p>
        <label for="ask-pw-input" class="mt-4 block text-sm font-medium text-slate-700"></label>
        <input id="ask-pw-input" type="password" autocomplete="current-password" required
               class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/20" />
        <p role="alert" aria-live="assertive" class="mt-2 min-h-[1.25rem] text-sm text-red-600" data-role="error"></p>
        <div class="mt-3 flex justify-end gap-2">
          <button type="button" data-role="cancel"
                  class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"></button>
          <button type="submit" data-role="ok"
                  class="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white hover:bg-ctu-blue/90 disabled:opacity-60"></button>
        </div>
      </form>`;

    // Chữ gán bằng textContent — không bao giờ ghép chuỗi người dùng vào innerHTML.
    const $ = <T extends HTMLElement>(sel: string) => root.querySelector(sel) as T;
    const form = $<HTMLFormElement>("form");
    const input = $<HTMLInputElement>("input");
    const error = $<HTMLElement>('[data-role="error"]');
    const ok = $<HTMLButtonElement>('[data-role="ok"]');
    const cancel = $<HTMLButtonElement>('[data-role="cancel"]');
    $<HTMLElement>("h2").textContent = opts.title;
    $<HTMLElement>("#ask-pw-msg").textContent = opts.message;
    $<HTMLElement>("label").textContent = tr("Mật khẩu của bạn");
    ok.textContent = tr("Xác nhận");
    cancel.textContent = tr("Huỷ");

    let busy = false;
    const finish = (result: boolean) => {
      input.value = "";
      document.removeEventListener("keydown", onKey, true);
      root.remove();
      previousFocus?.focus?.();
      resolve(result);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        e.stopPropagation();
        finish(false);
      }
    };

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const password = input.value;
      if (!password || busy) return;
      busy = true;
      ok.disabled = true;
      ok.textContent = tr("Đang xử lý…");
      error.textContent = "";
      let problem: string | null;
      try {
        problem = await opts.verify(password);
      } catch {
        problem = tr("Mật khẩu không đúng hoặc phiên đã hết hạn.");
      }
      busy = false;
      if (problem === null) return finish(true);
      ok.disabled = false;
      ok.textContent = tr("Xác nhận");
      error.textContent = problem;
      input.value = "";
      input.focus();
    });
    cancel.addEventListener("click", () => !busy && finish(false));
    $<HTMLElement>('[data-role="backdrop"]').addEventListener("click", () => !busy && finish(false));
    // Bắt Esc ở pha capture để Modal React bên dưới không đóng theo.
    document.addEventListener("keydown", onKey, true);

    document.body.appendChild(root);
    input.focus();
  });
}
