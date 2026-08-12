import { useCallback, useEffect, useRef, useState } from "react";

import apiClient from "../api/axiosClient";
import { useVisiblePoll } from "./useVisiblePoll";
import { tr } from "../i18n";
import { useToast } from "./useToast";

/**
 * Việc đang chờ quản trị viên, theo từng mục console — kèm pop-up khi TĂNG.
 *
 * Huy hiệu và pop-up trả lời hai câu hỏi khác nhau
 * ------------------------------------------------
 * Huy hiệu trả lời "chỗ nào đang có việc" — nó là TRẠNG THÁI, luôn đúng, nhìn
 * lúc nào cũng được. Pop-up trả lời "vừa có việc mới" — nó là SỰ KIỆN, chỉ
 * đúng một lần, và nó cắt ngang.
 *
 * Trộn hai thứ này là cách hỏng quen thuộc: hiện pop-up theo trạng thái thì cứ
 * mỗi chu kỳ lại nổ một cái y hệt cái trước, và người ta tắt hết thông báo
 * trong hai ngày. Nên pop-up ở đây chỉ nổ khi con số **tăng so với lần đo
 * trước**, và tuyệt đối không nổ ở lần đo đầu tiên.
 *
 * Vì sao lần đầu phải im
 * -----------------------
 * Mở console lên mà nhận năm cái pop-up cho năm việc đã tồn tại từ hôm qua là
 * báo sai: không có gì "vừa xảy ra" cả. `seen` khởi tạo bằng `null` chứ không
 * phải `{}` chính là để phân biệt "chưa đo lần nào" với "đo rồi, tất cả bằng
 * 0" — hai thứ mà một object rỗng gộp làm một.
 *
 * @i18n-key-table — chữ trong `LABELS` là KHOÁ từ điển, dịch bằng `tr(...)`
 * lúc dựng câu pop-up.
 */

/** Nhãn hiển thị của từng mục. Khoá là `href`, khớp với `ADMIN_NAV`. */
const LABELS: Record<string, string> = {
  "/admin/support": "Hỗ trợ",
  "/admin/vocabulary": "Từ vựng & phương ngữ",
  "/admin/legal": "Văn bản pháp lý",
  "/admin/tenants": "Tổ chức",
  "/admin/resources": "Giám sát tài nguyên",
};

export type AttentionCounts = Record<string, number>;

const POLL_MS = 30_000;

export function useAdminAttention(active = true) {
  const [counts, setCounts] = useState<AttentionCounts>({});
  const seen = useRef<AttentionCounts | null>(null);

  // `useToast()` dựng một object MỚI mỗi lần dựng lại. Để `toast` trong mảng
  // phụ thuộc của `refresh` thì `refresh` cũng mới mỗi lần, và cái `useEffect`
  // ở dưới chạy lại sau MỌI lần dựng — tức mỗi lần đặt state lại kéo thêm một
  // lượt gọi máy chủ, kéo thêm một lần đặt state. Bộ test bắt được ngay: hai
  // câu trả lời giả bị dùng hết trong một lần dựng đầu tiên.
  //
  // `useToast()` NÉM khi không có `<ToastProvider>` bao ngoài. Đúng với phần
  // lớn chỗ gọi, nhưng sai với chỗ này: hook đang nằm trong VỎ của console
  // quản trị, nên một provider thiếu sẽ không tắt mất pop-up — nó làm trắng cả
  // console. Huy hiệu là tín hiệu chính và nó không cần toast; chạy thiếu
  // pop-up là suy giảm chấp nhận được, còn màn hình trắng thì không.
  //
  // `useContext` bên trong vẫn được gọi VÔ ĐIỀU KIỆN, nên thứ tự hook không
  // đổi — cái `try` này chỉ chặn phép kiểm ném lỗi ở cuối.
  let toast: ReturnType<typeof useToast>["toast"] | null = null;
  try {
    toast = useToast().toast;
  } catch {
    toast = null;
  }
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refresh = useCallback(async () => {
    try {
      const res = await apiClient.get<{ counts: AttentionCounts }>(
        "/api/v1/admin/attention",
      );
      const next = res.data?.counts ?? {};
      setCounts(next);

      const before = seen.current;
      seen.current = next;
      if (before === null) return; // lần đo đầu: không có gì "vừa" xảy ra

      for (const [href, n] of Object.entries(next)) {
        const was = before[href] ?? 0;
        if (n <= was) continue;
        // `tr` chứ không phải `t`: hook này chạy ngoài cây component của trang
        // (nó sống trong vỏ console), và câu sinh ra ở đây là một pop-up sống
        // vài giây rồi biến mất — không cần dựng lại khi đổi ngôn ngữ.
        toastRef.current?.info(
          tr("{muc}: có {n} việc mới đang chờ", {
            muc: tr(LABELS[href] ?? href),
            n: n - was,
          }),
        );
      }
    } catch {
      // Im lặng có chủ ý. Đây là số phụ trợ trên thanh bên; một lượt hỏi hụt
      // (mất mạng chốc lát, token vừa xoay) không đáng để ném một dải đỏ lên
      // màn hình đè lên việc quản trị viên đang làm. Huy hiệu giữ nguyên số cũ.
    }
  }, []);

  useEffect(() => {
    if (active) void refresh();
  }, [active, refresh]);

  // Dừng khi tab bị ẩn: mỗi lượt là năm truy vấn đếm, và một console để quên
  // qua đêm sẽ chạy chúng hơn một nghìn lần mà không ai nhìn.
  useVisiblePoll(refresh, POLL_MS, active);

  return { counts, refresh };
}

export default useAdminAttention;
