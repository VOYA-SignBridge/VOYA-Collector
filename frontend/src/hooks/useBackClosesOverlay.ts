import { useEffect, useRef } from "react";

/**
 * Cho nút QUAY LẠI đóng một lớp phủ, thay vì rời khỏi trang.
 *
 * Vấn đề
 * ------
 * `FullscreenCaptureModal` mở/đóng bằng một biến trạng thái React. Trình duyệt
 * không biết gì về biến đó, nên khi người dùng đang thu hình và bấm nút quay
 * lại — phản xạ tự nhiên để "thoát khỏi cái đang mở" — trình duyệt làm đúng
 * thứ nó biết: rời khỏi `/upload`. Cả phiên thu đang dở biến mất, kể cả những
 * lần thu đã xong nhưng chưa gửi.
 *
 * Trên điện thoại Android thì đây không phải trường hợp hiếm: nút quay lại là
 * nút hệ thống, và nó là cách mặc định để đóng bất cứ thứ gì chiếm toàn màn
 * hình.
 *
 * Cách làm
 * --------
 * Lúc mở, đẩy thêm một mục vào lịch sử. Mục đó không đổi URL, nó chỉ là chỗ để
 * nút quay lại "ăn" vào. Khi `popstate` bắn, ta biết người dùng vừa bấm quay
 * lại trong lúc lớp phủ đang mở, nên gọi đóng thay vì để trình duyệt điều
 * hướng.
 *
 * Lúc đóng bằng cách khác (nút X, phím Esc), phải tự gỡ mục vừa đẩy bằng
 * `history.back()`, nếu không lịch sử tích dần những mục ma và người dùng phải
 * bấm quay lại hai lần mới rời được trang.
 *
 * Cạnh khó: người dùng HUỶ hộp thoại xác nhận
 * --------------------------------------------
 * `handleClose` của modal hỏi lại khi đang thu dở. Nếu người dùng chọn "ở
 * lại", modal KHÔNG đóng — nhưng mục lịch sử thì đã bị nút quay lại tiêu mất
 * rồi. Lần bấm quay lại tiếp theo sẽ rời khỏi trang thật, tức là cái phanh chỉ
 * hoạt động đúng một lần.
 *
 * Nên sau khi gọi đóng, hook kiểm lại: nếu lớp phủ vẫn mở thì đẩy lại một mục
 * mới. Kiểm ở `setTimeout(0)` chứ không kiểm ngay, vì việc đóng đi qua
 * `setState` của React và giá trị chỉ phản ánh ở lượt render sau.
 */
export function useBackClosesOverlay(isOpen: boolean, onClose: () => void): void {
  // Giữ bản mới nhất trong ref để effect không phải chạy lại mỗi lần
  // `onClose` được tạo lại — chạy lại nghĩa là gỡ rồi đẩy lại mục lịch sử,
  // và làm thế ở mỗi lần render là tự đánh nát lịch sử duyệt.
  const onCloseRef = useRef(onClose);
  const isOpenRef = useRef(isOpen);
  const pushedRef = useRef(false);

  useEffect(() => {
    onCloseRef.current = onClose;
    isOpenRef.current = isOpen;
  });

  useEffect(() => {
    if (!isOpen) return;

    const push = () => {
      window.history.pushState({ voyaOverlay: true }, "");
      pushedRef.current = true;
    };

    const handlePop = () => {
      // Trình duyệt đã gỡ mục của ta rồi; đừng gỡ thêm lần nữa lúc dọn dẹp.
      pushedRef.current = false;
      onCloseRef.current();
      window.setTimeout(() => {
        if (isOpenRef.current && !pushedRef.current) push();
      }, 0);
    };

    push();
    window.addEventListener("popstate", handlePop);

    return () => {
      window.removeEventListener("popstate", handlePop);
      // Gỡ listener TRƯỚC khi gọi `back()`: `back()` cũng bắn `popstate`, và
      // nếu listener còn đó thì nó sẽ gọi đóng thêm một lần nữa cho một lớp
      // phủ vốn đã đóng.
      if (pushedRef.current) {
        pushedRef.current = false;
        window.history.back();
      }
    };
  }, [isOpen]);
}

export default useBackClosesOverlay;
