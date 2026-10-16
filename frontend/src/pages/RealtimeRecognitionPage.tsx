import RealtimeRuntime from "../components/realtime/RealtimeRuntime";
import TrialGate from "../components/TrialGate";

/**
 * Tuyến `/realtime` mở cho cả khách chưa đăng nhập — đó là chủ ý, vì đây là
 * thứ duy nhất người lạ có thể thử trước khi quyết định dùng.
 *
 * Nhưng cổng gác ở máy chủ đòi **một trong hai**: phiên đăng nhập hoặc phiếu
 * dùng thử. `TrialGate` là chỗ xin phiếu; nếu bỏ nó đi thì trang vẫn mở, camera
 * vẫn bật, và mọi lời gọi API trả 401.
 */
export default function RealtimeRecognitionPage() {
  return (
    <TrialGate>
      <RealtimeRuntime />
    </TrialGate>
  );
}
