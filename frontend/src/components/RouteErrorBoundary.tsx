import { tr } from "../i18n";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangleIcon, RepeatIcon } from "./ui/Icons";

/**
 * Bắt lỗi khi một chunk lazy không tải được, và nạp lại trang MỘT lần.
 *
 * Vì sao cần
 * ----------
 * Mọi trang trong App.tsx đều là `lazy(() => import(...))`, tức là mã của một
 * trang chỉ được tải khi người dùng đi tới nó lần đầu. Tên tệp chunk mang mã
 * hash nội dung, nên mỗi lần triển khai lại sinh ra tên mới và tên cũ biến mất
 * khỏi máy chủ.
 *
 * Hệ quả: một tab đang mở TRƯỚC lúc triển khai vẫn giữ bản đồ chunk cũ. Người
 * dùng bấm NÚT QUAY LẠI về một trang họ chưa mở trong phiên này, trình duyệt
 * xin đúng tệp cũ đó, nginx trả 404, `import()` bị từ chối — và vì không có
 * error boundary nào, React gỡ toàn bộ cây. Màn hình trắng, không thông báo,
 * không nút nào bấm được.
 *
 * Nút quay lại là đường hay gặp nhất vì nó chuyển trang mà KHÔNG tải lại tài
 * liệu, nên bản đồ chunk cũ vẫn còn nguyên trong bộ nhớ.
 *
 * Vì sao nạp lại chứ không hiện nút "thử lại"
 * --------------------------------------------
 * Thử lại `import()` sẽ xin đúng URL đã 404 và hỏng y hệt. Thứ duy nhất sửa
 * được là lấy lại `index.html` mới, và điều đó cần một lượt tải tài liệu thật.
 *
 * Vì sao chỉ nạp lại MỘT lần
 * ---------------------------
 * Nếu nguyên nhân không phải chunk cũ mà là một lỗi thật trong mã trang, tự
 * nạp lại sẽ thành vòng lặp vô tận: hỏng, nạp lại, hỏng, nạp lại. Cờ trong
 * `sessionStorage` cắt vòng đó — lần thứ hai thì hiện thông báo cho người dùng
 * thay vì tiếp tục quay. Dùng `sessionStorage` chứ không phải biến trong bộ
 * nhớ vì việc nạp lại xoá sạch bộ nhớ, nên một biến sẽ luôn thấy "lần đầu".
 */

const RELOAD_FLAG = "voya:chunk-reload";

/**
 * Lỗi này có phải do chunk không tải được không.
 *
 * Không có mã lỗi chuẩn nào cho tình huống này; mỗi trình duyệt đặt một câu
 * khác nhau. So khớp theo chuỗi là cách duy nhất, và nó cố ý RỘNG: bỏ sót một
 * biến thể nghĩa là màn hình trắng quay lại, còn nhận nhầm một lỗi khác chỉ
 * tốn đúng một lần nạp lại rồi thông báo hiện ra bình thường.
 */
function looksLikeStaleChunk(error: Error): boolean {
  const text = `${error?.name ?? ""} ${error?.message ?? ""}`.toLowerCase();
  return (
    text.includes("dynamically imported module") ||
    text.includes("failed to fetch dynamically") ||
    text.includes("importing a module script failed") ||
    text.includes("chunkloaderror") ||
    text.includes("loading chunk") ||
    text.includes("loading css chunk")
  );
}

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default // `tr()` chứ KHÔNG phải `t()`: đây là một class component, và bắt lỗi khi dựng
// là việc duy nhất `componentDidCatch` làm được — không có bản hook nào thay
// thế. Hook không gọi được trong class, nên phải dùng bản dịch mức module.
// Chấp nhận được ở đây vì màn hình này được dựng lại từ đầu mỗi lần bung lỗi.
class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Ghi ra console trước khi xử lý: nếu bước dưới nạp lại trang, đây là dấu
    // vết duy nhất còn lại để biết vì sao.
    console.error("[RouteErrorBoundary]", error, info.componentStack);

    if (looksLikeStaleChunk(error) && !sessionStorage.getItem(RELOAD_FLAG)) {
      sessionStorage.setItem(RELOAD_FLAG, "1");
      window.location.reload();
    }
  }

  componentDidMount() {
    // Chỉ xoá cờ khi dựng được KHÔNG kèm lỗi.
    //
    // Điều kiện này không thừa — thiếu nó thì cái phanh tự vô hiệu hoá chính
    // mình. Khi con ném lỗi ngay ở lượt render đầu, React gỡ cây, dựng lại
    // boundary ở trạng thái lỗi, rồi commit: `componentDidMount` chạy TRƯỚC
    // `componentDidCatch`. Xoá cờ ở đây nghĩa là lượt `componentDidCatch` ngay
    // sau đó luôn thấy "chưa từng nạp lại" và nạp lại — hỏng, nạp lại, hỏng,
    // nạp lại, vô tận, đúng thứ cờ này sinh ra để chặn.
    if (!this.state.error) sessionStorage.removeItem(RELOAD_FLAG);
  }

  private handleReload = () => {
    sessionStorage.removeItem(RELOAD_FLAG);
    window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const stale = looksLikeStaleChunk(error);
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-xl">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-3xl">
            {stale
              ? <RepeatIcon className="h-8 w-8"  aria-hidden="true" />
              : <AlertTriangleIcon className="h-8 w-8"  aria-hidden="true" />}
          </div>
          <h2 className="mb-2 text-xl font-bold text-slate-900">
            {stale ? tr("Ứng dụng vừa được cập nhật") : tr("Trang này gặp sự cố")}
          </h2>
          <p className="mb-6 text-slate-600">
            {stale
              ? tr("Phiên bản bạn đang mở đã cũ hơn phiên bản trên máy chủ. Hãy tải lại để tiếp tục — dữ liệu của bạn không bị ảnh hưởng.")
              : tr("Đã có lỗi khi hiển thị trang. Bạn có thể tải lại để thử tiếp; nếu vẫn lỗi, vui lòng báo cho quản trị viên.")}
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-lg bg-ctu-blue px-5 py-2.5 font-medium text-white transition-colors hover:bg-ctu-navy focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2"
          >
            {tr("Tải lại trang")}
          </button>
        </div>
      </div>
    );
  }
}
