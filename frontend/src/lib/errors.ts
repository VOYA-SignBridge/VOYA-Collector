/**
 * Đổi lỗi từ máy chủ thành câu người dùng đọc được — và chỉ câu đó.
 *
 * Vì sao không hiện thẳng `detail`
 * ---------------------------------
 * Khắp giao diện đang viết `e?.response?.data?.detail || "…"`. Cách đó hỏng ở
 * hai đầu, và đầu thứ hai là đầu nghiêm trọng:
 *
 * 1. **Vô nghĩa với người dùng.** FastAPI trả 422 dưới dạng MẢNG
 *    `[{loc: ["query","_args"], msg: "field required", …}]`. Nối chuỗi một mảng
 *    ra `[object Object]`. Người dùng thấy đúng chữ đó trên màn hình.
 * 2. **Rò thông tin.** Một `detail` chưa lọc mang được tên bảng, tên cột, ràng
 *    buộc khoá ngoại, đường dẫn tệp trong container, tên máy chủ nội bộ, và
 *    tên lớp ngoại lệ. Với người đang dò hệ thống thì đó là bản đồ miễn phí —
 *    và nó vi phạm đúng nguyên tắc chủ dự án đã đặt: không để lộ chi tiết nội
 *    bộ ra ngoài.
 *
 * Cách làm ở đây, theo thứ tự
 * ----------------------------
 *   1. Có `error_code` mà ta biết → dùng câu ta tự soạn. Đây là đường TỐT
 *      nhất: máy chủ nói *chuyện gì*, giao diện quyết định *nói thế nào*.
 *   2. Không có mã, nhưng `detail` trông như một câu do người viết cho người
 *      đọc → cho qua. Backend này soạn nhiều thông báo tiếng Việt tử tế
 *      ("Không thể tự khóa tài khoản của chính mình") và chôn chúng đi thì tệ
 *      hơn.
 *   3. Còn lại → câu chung theo mã HTTP.
 *
 * Bước 2 là bước phải cẩn thận, nên `looksHumanWritten` **mặc định từ chối**:
 * chỉ chuỗi vượt qua mọi phép kiểm mới được hiện.
 *
 * @i18n-key-table — chuỗi tiếng Việt trong tệp này là KHOÁ từ điển, đi qua
 * `tr()` ở chỗ trả về. Xem `scripts/i18n-coverage.mjs`.
 */

import { tr } from "../i18n";

/**
 * Mã lỗi nghiệp vụ backend trả về → câu hiển thị.
 *
 * Bảng này giữ nguyên tiếng Việt vì **tiếng Việt là khoá** của từ điển dịch:
 * câu ở đây đi thẳng vào `tr()` ở dưới. Dịch sẵn sang tiếng Anh tại chỗ này sẽ
 * làm hỏng đúng cơ chế đó.
 */
const BY_CODE: Record<string, string> = {
  stale_version: "Nội dung đã được người khác cập nhật. Hãy tải lại rồi thử lại.",
  draft_already_open: "Đã có một bản nháp đang mở cho loại văn bản này.",
  invalid_transition: "Không chuyển được sang trạng thái đó từ trạng thái hiện tại.",
  status_not_settable: "Trạng thái này không đặt trực tiếp được.",
  sudo_required: "Thao tác này cần xác thực lại mật khẩu.",
  quota_exceeded: "Đã dùng hết hạn mức của gói hiện tại.",
  trial_exhausted: "Đã hết thời gian dùng thử hôm nay. Vui lòng quay lại vào ngày mai.",
  consent_required: "Bạn cần đồng ý với các điều khoản trước khi tiếp tục.",
  not_owner: "Bạn chỉ thao tác được trên dữ liệu do mình đóng góp.",
};

/** Mã HTTP → câu chung. Cố ý mơ hồ ở nhóm 5xx. */
const BY_STATUS: Record<number, string> = {
  400: "Yêu cầu không hợp lệ. Hãy kiểm tra lại thông tin đã nhập.",
  401: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
  403: "Bạn không có quyền thực hiện thao tác này.",
  404: "Không tìm thấy dữ liệu yêu cầu. Có thể nó đã bị xoá.",
  409: "Dữ liệu vừa thay đổi ở nơi khác. Hãy tải lại rồi thử lại.",
  413: "Tệp quá lớn so với giới hạn cho phép.",
  422: "Dữ liệu gửi lên không hợp lệ. Hãy kiểm tra lại các ô đã nhập.",
  429: "Bạn thao tác hơi nhanh. Vui lòng chờ một lát rồi thử lại.",
  500: "Máy chủ gặp sự cố. Sự việc đã được ghi nhận, vui lòng thử lại sau.",
  502: "Máy chủ đang không phản hồi. Vui lòng thử lại sau ít phút.",
  503: "Dịch vụ đang bảo trì hoặc quá tải. Vui lòng thử lại sau ít phút.",
  504: "Máy chủ xử lý quá lâu. Vui lòng thử lại.",
};

/**
 * Dấu hiệu một chuỗi là thông báo HỆ THỐNG chứ không phải câu cho người dùng.
 * Dính bất kỳ dấu hiệu nào thì không hiện.
 */
const SYSTEM_MARKERS = [
  /traceback/i,
  /\bexception\b/i,
  /[A-Za-z]+Error\b/,          // ValueError, IntegrityError, TypeError…
  /psycopg2|sqlalchemy|asyncpg/i,
  /\bselect\b.+\bfrom\b/i,     // câu SQL lọt ra
  /\b(insert|update|delete)\s+(into|from|set)\b/i,
  /relation\s+"|column\s+"|constraint\s+"/i,
  /\/(usr|app|src|home|var|tmp)\//,   // đường dẫn trong container
  /[A-Za-z]:\\/,                      // đường dẫn Windows
  /\b\d{1,3}(\.\d{1,3}){3}\b/,        // địa chỉ IP
  /localhost|127\.0\.0\.1|postgres:|redis:/i,
  /\bat line \d+|line \d+, in\b/i,
  /<[a-z]+[\s>]/i,                    // mảnh HTML/XML
];

function looksHumanWritten(text: string): boolean {
  const s = text.trim();
  if (s.length < 3 || s.length > 200) return false;   // dài quá gần như chắc chắn là bãi nôn của hệ thống
  if (s.includes("\n")) return false;                  // nhiều dòng = vết ngăn xếp
  if (/^[{[]/.test(s)) return false;                   // JSON thô
  return !SYSTEM_MARKERS.some((re) => re.test(s));
}

/** Rút `detail` ra dạng chuỗi, chịu được cả ba hình dạng FastAPI hay trả. */
function extractDetail(data: unknown): string | null {
  if (typeof data === "string") return data;
  if (!data || typeof data !== "object") return null;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  // 422: mảng lỗi xác thực. Không bao giờ hiện nguyên trạng — `loc` mang tên
  // tham số nội bộ, và người dùng không sửa được gì từ đó.
  if (Array.isArray(detail)) return null;
  if (detail && typeof detail === "object") {
    const nested = (detail as { error?: unknown }).error;
    if (typeof nested === "string") return nested;
  }
  return null;
}

function extractCode(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  const code = d.error_code ?? d.code
    ?? (d.detail && typeof d.detail === "object"
      ? (d.detail as Record<string, unknown>).code
      : undefined);
  return typeof code === "string" ? code : null;
}

/**
 * Câu cuối cùng khi không suy ra được gì.
 *
 * Là hằng có tên chứ không nằm trong danh sách tham số: một chuỗi trốn trong
 * chữ ký hàm thì công cụ đo độ phủ không thấy, và thứ nó không thấy thì nó báo
 * là "bản dịch không ai dùng".
 */
const LAST_RESORT = "Thao tác không thành công. Vui lòng thử lại.";

/**
 * Câu an toàn để hiện cho người dùng.
 *
 * `fallback` là câu cho trường hợp không suy ra được gì — hãy viết nó theo
 * NGỮ CẢNH ("Không tải được danh sách tổ chức") chứ đừng viết "Đã có lỗi xảy
 * ra". Người dùng cần biết việc gì hỏng để quyết định làm gì tiếp.
 */
export function friendlyError(err: unknown, fallback = LAST_RESORT): string {
  const e = err as {
    response?: { status?: number; data?: unknown };
    code?: string;
    message?: string;
  };

  // Không có phản hồi = chưa tới được máy chủ.
  if (!e?.response) {
    if (e?.code === "ECONNABORTED") return tr("Máy chủ phản hồi quá lâu. Vui lòng thử lại.");
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      return tr("Thiết bị đang ngoại tuyến. Hãy kiểm tra kết nối mạng.");
    }
    return tr("Không kết nối được máy chủ. Hãy kiểm tra kết nối mạng rồi thử lại.");
  }

  const status = e.response.status ?? 0;
  const data = e.response.data;

  const code = extractCode(data);
  if (code && BY_CODE[code]) return tr(BY_CODE[code]);

  // Nhóm 5xx KHÔNG bao giờ cho `detail` đi qua: đó là lỗi chưa lường trước, và
  // đúng những lỗi đó mới hay mang theo nội dung của tầng dưới.
  if (status < 500) {
    const detail = extractDetail(data);
    // Cố ý KHÔNG dịch: đây là câu do máy chủ soạn, và từ điển ở đây chỉ biết
    // những câu của giao diện. Cho nó qua `tr()` cũng chỉ trả lại chính nó,
    // nhưng lại tạo ấn tượng sai rằng thông báo từ máy chủ đã được dịch.
    if (detail && looksHumanWritten(detail)) return detail;
  }

  return tr(BY_STATUS[status] ?? fallback);
}

/**
 * Có nên mời người dùng thử lại không.
 *
 * Nút "Thử lại" cạnh một lỗi 403 là lời mời làm một việc chắc chắn hỏng lần
 * nữa; cạnh một lỗi 503 thì đúng là việc nên làm.
 */
export function isRetryable(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  if (status === undefined) return true;          // lỗi mạng — thử lại hợp lý
  return status === 429 || status >= 500;
}
