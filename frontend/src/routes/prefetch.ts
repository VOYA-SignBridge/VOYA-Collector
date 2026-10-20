/**
 * Nạp trước chunk của một tuyến khi người dùng tỏ ý sẽ đi tới đó.
 *
 * Vấn đề nó giải
 * ---------------
 * Mọi trang đều `lazy()`, nên mỗi lần chuyển tuyến là một vòng đi–về mạng để
 * lấy chunk, và trong lúc chờ người dùng nhìn màn hình trống của `<Suspense>`.
 * Trên mạng của trường vào giờ cao điểm, khoảng trống đó dài tới mức người ta
 * bấm lại lần nữa.
 *
 * Khoảng thời gian giữa lúc con trỏ chạm vào một mục và lúc ngón tay bấm
 * xuống là 100–300 ms — đủ để tải xong một chunk 10–40 kB. Nạp trước ở
 * `mouseenter`/`focus` biến quãng chờ đó thành số không mà không tốn thêm một
 * byte nào cho người KHÔNG bấm vào.
 *
 * Vì sao chuỗi đường dẫn lặp lại ở đây thay vì dùng chung với `App.tsx`
 * ---------------------------------------------------------------------
 * `import()` được bộ nạp mô-đun ghi nhớ theo **mô-đun đã phân giải**, không
 * theo vị trí gọi. `../pages/UploadPage` ở tệp này và `./pages/UploadPage` ở
 * `App.tsx` phân giải về cùng một mô-đun, nên cùng dùng một chunk và một bộ
 * nhớ đệm. Gom chung vào một bảng rồi cho `App.tsx` dùng lại sẽ gọn hơn về
 * hình thức, nhưng phải viết lại toàn bộ khối `lazy()` của `App.tsx` — một
 * thay đổi rộng hơn nhiều so với thứ đang cần.
 *
 * Bảng này KHÔNG cần đầy đủ. Thiếu một tuyến chỉ có nghĩa tuyến đó không được
 * nạp trước; không có gì hỏng.
 */

type Loader = () => Promise<unknown>;

const ROUTES: Record<string, Loader> = {
  "/": () => import("../pages/DashboardPage"),
  "/upload": () => import("../pages/UploadPage"),
  "/labels": () => import("../pages/LabelsPage"),
  "/realtime": () => import("../pages/RealtimeRecognitionPage"),
  "/training": () => import("../pages/training/TrainingPipeline"),
  "/trash": () => import("../pages/TrashPage"),
  "/account": () => import("../pages/AccountPage"),
  "/organization": () => import("../pages/OrganizationPage"),
  "/verify": () => import("../pages/VerifyContactPage"),
  "/billing": () => import("../pages/BillingPage"),
  "/integrations": () => import("../pages/IntegrationsPage"),
  "/admin/data": () => import("../pages/AdminDataPage"),
  "/admin/users": () => import("../pages/AdminUsersPage"),
  "/admin/resources": () => import("../pages/AdminResourcesPage"),
  "/admin/activity": () => import("../pages/AdminActivityPage"),
  "/admin/sot": () => import("../pages/SotAdminPage"),
  "/admin/vocabulary": () => import("../pages/AdminVocabularyPage"),
  "/admin/legal": () => import("../pages/AdminLegalPage"),
  "/admin/tenants": () => import("../pages/AdminTenantsPage"),
  "/admin/billing": () => import("../pages/AdminBillingPage"),
};

/** Đã gọi rồi thì thôi — `import()` tự nhớ, nhưng tránh luôn cả lời gọi thừa. */
const done = new Set<string>();

export function prefetchRoute(href: string): void {
  if (done.has(href)) return;
  const load = ROUTES[href];
  if (!load) return;
  done.add(href);
  // Nuốt lỗi có chủ ý: đây là việc mang tính đầu cơ. Mạng hỏng lúc nạp trước
  // KHÔNG được nổi lên thành thông báo lỗi — người dùng chưa yêu cầu gì cả, và
  // khi họ bấm thật thì `<Suspense>` sẽ thử lại và báo lỗi đúng lúc.
  load().catch(() => undefined);
}

/**
 * Props gắn vào một liên kết điều hướng.
 *
 * Có cả `onFocus` chứ không riêng `onMouseEnter`: người dùng bàn phím không
 * bao giờ phát ra `mouseenter`, và họ là nhóm ít nhất được hưởng lợi từ những
 * tối ưu kiểu này nhất.
 */
export function prefetchProps(href: string) {
  const fire = () => prefetchRoute(href);
  return { onMouseEnter: fire, onFocus: fire, onTouchStart: fire };
}
