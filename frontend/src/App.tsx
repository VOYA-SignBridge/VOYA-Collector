import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useParams } from "react-router-dom";
import Layout from "./components/Layout";
// import DebugPanel from "./components/DebugPanel";
import { Suspense, lazy, useEffect, useState } from "react";
import { ToastProvider } from "./hooks/useToast";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import ToastContainer from "./components/ui/ToastContainer";
import SecurityNotices from "./components/SecurityNotices";
import LoadingScreen from "./components/LoadingScreen";
import NotAuthorizedPage from "./pages/NotAuthorizedPage";
import RouteErrorBoundary from "./components/RouteErrorBoundary";

// Minimal type for the debug interface exposed on window
// interface DebuggerInterface {
//   getState?: () => { enabled?: boolean };
//   setState?: (s: { enabled?: boolean }) => void;
// }

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LabelsPage = lazy(() => import("./pages/LabelsPage"));
const LabelDetailPage = lazy(() => import("./pages/LabelDetailPage"));
const CollectionSessionsPage = lazy(() => import("./pages/CollectionSessionsPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const RealtimeRecognitionPage = lazy(() => import("./pages/RealtimeRecognitionPage"));
const TrainingPipeline = lazy(() => import("./pages/training/TrainingPipeline"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const InvitationPage = lazy(() => import("./pages/InvitationPage"));
const VerifyContactPage = lazy(() => import("./pages/VerifyContactPage"));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage"));
const AdminResourcesPage = lazy(() => import("./pages/AdminResourcesPage"));
const AdminActivityPage = lazy(() => import("./pages/AdminActivityPage"));
const AdminDataPage = lazy(() => import("./pages/AdminDataPage"));
const SotAdminPage = lazy(() => import("./pages/SotAdminPage"));
const AdminSignersPage = lazy(() => import("./pages/AdminSignersPage"));
const AdminProcessingPage = lazy(() => import("./pages/AdminProcessingPage"));
const AdminVocabularyPage = lazy(() => import("./pages/AdminVocabularyPage"));
const AdminLegalPage = lazy(() => import("./pages/AdminLegalPage"));
const AdminTenantsPage = lazy(() => import("./pages/AdminTenantsPage"));
const AdminBillingPage = lazy(() => import("./pages/AdminBillingPage"));
const LegalDocumentPage = lazy(() => import("./pages/LegalDocumentPage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));
const ConsentsPage = lazy(() => import("./pages/settings/ConsentsPage"));
const OrganizationPage = lazy(() => import("./pages/OrganizationPage"));
const WorkspacesPage = lazy(() => import("./pages/settings/WorkspacesPage"));
const ModerationPage = lazy(() => import("./pages/ModerationPage"));
const OrgPickerPage = lazy(() => import("./pages/org/OrgPickerPage"));
const OrgLayout = lazy(() => import("./pages/org/OrgLayout"));
const OrgUploadPage = lazy(() =>
  import("./pages/org/OrgWorkPages").then((m) => ({ default: m.OrgUploadPage })));
const OrgLabelsPage = lazy(() =>
  import("./pages/org/OrgWorkPages").then((m) => ({ default: m.OrgLabelsPage })));
const OrgSessionsPage = lazy(() =>
  import("./pages/org/OrgWorkPages").then((m) => ({ default: m.OrgSessionsPage })));
const OrgRealtimePage = lazy(() =>
  import("./pages/org/OrgWorkPages").then((m) => ({ default: m.OrgRealtimePage })));
const OrgTrainingPage = lazy(() =>
  import("./pages/org/OrgWorkPages").then((m) => ({ default: m.OrgTrainingPage })));
const OrgSettingsLayout = lazy(() => import("./pages/org/OrgSettingsLayout"));
const ConsoleHomePage = lazy(() => import("./pages/console/ConsoleHomePage"));
const ConsoleAllocationsPage = lazy(() => import("./pages/console/ConsoleAllocationsPage"));
const ConsolePoliciesPage = lazy(() => import("./pages/console/ConsolePoliciesPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const SupportPage = lazy(() => import("./pages/SupportPage"));
const TrashPage = lazy(() => import("./pages/TrashPage"));
const BillingPage = lazy(() => import("./pages/BillingPage"));
const IntegrationsPage = lazy(() => import("./pages/IntegrationsPage"));
// Vo cua console quan tri va trung tam Cai dat.
const AdminShell = lazy(() => import("./components/AdminShell"));
const AdminHomePage = lazy(() => import("./pages/admin/AdminHomePage"));
const AdminSupportPage = lazy(() => import("./pages/admin/AdminSupportPage"));
const SettingsLayout = lazy(() => import("./pages/settings/SettingsLayout"));
const SecuritySettingsPage = lazy(() => import("./pages/settings/SecuritySettingsPage"));
const LanguageSettingsPage = lazy(() => import("./pages/settings/LanguageSettingsPage"));


// Protected Route Wrapper — reads the shared AuthProvider instead of firing its
// own /auth/me. The provider already reloads on login/logout (AUTH_EVENT) and
// cross-tab storage changes, so no local listeners are needed here.
function ProtectedRoute({
  children,
  requireAdmin = false,
}: {
  children: React.ReactNode;
  requireAdmin?: boolean;
}) {
  const { loading, isAuthenticated, isAdmin } = useAuth();

  if (loading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  // Signed in but lacking admin rights → show a proper 403 page instead of
  // leaking the admin shell (which would render empty and look broken).
  if (requireAdmin && !isAdmin) return <NotAuthorizedPage />;
  return <>{children}</>;
}

// Back-compat: the label detail page moved from /admin/labels/:id to /labels/:id
// (it is no longer admin-only). Preserve old links by redirecting, keeping :id.
function RedirectToLabelDetail() {
  const { id = "" } = useParams();
  return <Navigate to={`/labels/${id}`} replace />;
}

// Cùng lý do và cùng hình dạng: hỗ trợ đã chuyển vào Cài đặt, và các thông báo
// đã gửi trước lượt chuyển ấy vẫn mang đường `/support/<id>`. Giữ ID lại.
function SupportTicketRedirect() {
  const { id = "" } = useParams();
  return <Navigate to={id ? `/settings/support/${id}` : "/settings/support"} replace />;
}

function App() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  // useEffect(() => {
  //   // Keyboard shortcut: Shift+D to toggle debug mode
  //   const handleKeyDown = (e: KeyboardEvent) => {
  //     if (e.shiftKey && e.key === "D") {
  //       e.preventDefault();
  //       const debuggerInterface = (window as unknown as Record<string, unknown>)
  //         .__voyadebug as DebuggerInterface | undefined;
  //       if (debuggerInterface?.getState && debuggerInterface?.setState) {
  //         const state = debuggerInterface.getState();
  //         debuggerInterface.setState({ enabled: !state.enabled });
  //       }
  //     }
  //   };
  //
  //   window.addEventListener("keydown", handleKeyDown);
  //   return () => window.removeEventListener("keydown", handleKeyDown);
  // }, []);

  if (loading) {
    return <LoadingScreen />;
  }

// Lấy thư mục gốc động từ cấu hình Runtime Nginx tiêm vào
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const basename = (window as any).__ENV__?.VITE_BASE_PATH || "/";

  return (
    <ToastProvider>
      <AuthProvider>
        <Router basename={basename}>
          <Layout>
          {/* Boundary nằm NGOÀI Suspense, không phải trong: một `import()` bị
              từ chối sẽ ném ra từ chính ranh giới Suspense, nên một boundary
              đặt bên trong sẽ không bao giờ thấy lỗi đó. Xem
              RouteErrorBoundary.tsx về việc vì sao nút quay lại là đường hay
              kích hoạt lỗi này nhất sau mỗi lần triển khai. */}
          <RouteErrorBoundary>
          <Suspense fallback={<LoadingScreen />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* /recover là cửa thứ hai cũ, đã gộp vào /forgot-password. Giữ
                  lại đường chuyển hướng chứ không xoá: địa chỉ này đã đi ra
                  ngoài trong thư và có thể nằm trong dấu trang của ai đó. */}
              <Route path="/recover" element={<Navigate to="/forgot-password" replace />} />

              {/* Nhận lời mời. CÔNG KHAI và phải như vậy — người nhận chưa có
                  tài khoản, đó chính là lý do có lời mời. Mã đi trong fragment
                  (`#token=…`), thứ trình duyệt không gửi lên máy chủ. */}
              <Route path="/invitation" element={<InvitationPage />} />

              <Route
                path="/verify"
                element={
                  <ProtectedRoute>
                    <VerifyContactPage />
                  </ProtectedRoute>
                }
              />

              {/* Văn bản pháp lý: CÔNG KHAI, và phải như vậy. Ô "Tôi đồng ý" ở
                  biểu mẫu đăng ký mở ra trang này, nên đặt nó sau cổng đăng
                  nhập sẽ bắt người ta đồng ý với thứ họ không đọc được. */}
              <Route path="/legal/:kind" element={<LegalDocumentPage />} />
              <Route path="/legal" element={<Navigate to="/legal/terms" replace />} />

              <Route path="/labels" element={<LabelsPage />} />

              {/* Label detail (session viewer) is open to any signed-in user:
                  the backend gates it with get_current_user (not admin), and a
                  contributor may view all recordings but act only on their own
                  (per-session is_owner flag). Keep the old /admin/labels/:id URL
                  working via a redirect so existing links/bookmarks don't break. */}
              <Route
                path="/labels/:id"
                element={
                  <ProtectedRoute>
                    <LabelDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/admin/labels/:id" element={<RedirectToLabelDetail />} />

              <Route
                path="/sessions"
                element={
                  <ProtectedRoute>
                    <CollectionSessionsPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/realtime" element={<RealtimeRecognitionPage />} />

              {/* Thông báo và hỗ trợ: mọi thành viên đã đăng nhập, KHÔNG phải
                  `requireAdmin`. Cờ đó là quản trị viên NỀN TẢNG — dùng nó ở
                  đây sẽ khoá đúng những người cần mở phiếu hỗ trợ nhất. */}
              <Route
                path="/notifications"
                element={
                  <ProtectedRoute>
                    <NotificationsPage />
                  </ProtectedRoute>
                }
              />
              {/* Hỗ trợ đã chuyển vào Cài đặt. Giữ chuyển hướng: thông báo
                  "phản hồi mới trên phiếu" gửi trước hôm nay trỏ vào đây. */}
              <Route path="/support" element={<Navigate to="/settings/support" replace />} />
              {/* Giữ ID khi chuyển hướng. Bản trước ném nó đi và đưa mọi thông
                  báo "phản hồi mới trên phiếu #X" về cùng một danh sách — người
                  dùng phải tự đi tìm lại đúng thứ vừa được báo. Những thông báo
                  ấy đã nằm sẵn trong cơ sở dữ liệu với đường dẫn cũ, nên đường
                  này phải chuyển tiếp ID chứ không chỉ tồn tại. */}
              <Route path="/support/:id" element={<SupportTicketRedirect />} />

              <Route
                path="/training"
                element={
                  <ProtectedRoute>
                    <TrainingPipeline />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/upload"
                element={
                  <ProtectedRoute>
                    <UploadPage />
                  </ProtectedRoute>
                }
              />

              {/* ================= CONSOLE QUẢN TRỊ =================
                  Một vỏ riêng (`AdminShell`), không phải một nhóm trong thanh
                  bên. Route lồng chứ không phải mười route phẳng: cổng quyền và
                  cái vỏ khai ĐÚNG MỘT LẦN, nên không thể thêm một trang quản
                  trị mà quên gác nó — kiểu sót mà mười route phẳng mời gọi. */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminShell>
                      <Outlet />
                    </AdminShell>
                  </ProtectedRoute>
                }
              >
                <Route index element={<AdminHomePage />} />
                <Route path="data" element={<AdminDataPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                <Route path="support" element={<AdminSupportPage />} />
                {/* Cùng trang, mở sẵn một phiếu. Thông báo "phiếu hỗ trợ
                    mới" trỏ vào đây kèm ID; trước đây không route nào khớp
                    nên cú nhấp rơi vào trang không tìm thấy. */}
                <Route path="support/:id" element={<AdminSupportPage />} />
                <Route path="resources" element={<AdminResourcesPage />} />
                <Route path="activity" element={<AdminActivityPage />} />
                <Route path="sot" element={<SotAdminPage />} />
                <Route path="signers" element={<AdminSignersPage />} />
                <Route path="processing" element={<AdminProcessingPage />} />
                {/* Duyệt phương ngữ do người đóng góp đề xuất. Thiếu route này
                    thì đề xuất từ AddDialectModal nằm chờ mãi mãi. */}
                <Route path="vocabulary" element={<AdminVocabularyPage />} />
                <Route path="legal" element={<AdminLegalPage />} />
                {/* Mặt giao diện cho 20 endpoint ở routers/tenants.py, vốn
                    không có chỗ nào gọi tới. Cô lập hai mặt phẳng là lõi kiến
                    trúc, mà trước trang này nó chỉ vận hành được bằng curl. */}
                <Route path="tenants" element={<AdminTenantsPage />} />
                {/* Bốn endpoint nền tảng của routers/billing.py cũng không có
                    mặt giao diện: đổi gói một tổ chức và treo tổ chức quá hạn
                    chỉ làm được bằng curl, còn sửa hạn mức của một gói thì chỉ
                    làm được bằng cách gõ SQL vào cơ sở dữ liệu sản xuất. */}
                <Route path="billing" element={<AdminBillingPage />} />
                <Route path="trash" element={<TrashPage />} />
              </Route>

              {/* ================= TRUNG TÂM CÀI ĐẶT =================
                  Sáu mục vốn nằm rải trong thanh bên chính. Mỗi mục vẫn là một
                  ROUTE chứ không phải một tab trong state: `/settings/security`
                  phải chia sẻ được, đánh dấu được và quay-lại được — và thông
                  báo bảo mật trỏ tới đây bằng đường dẫn. */}
              {/* TỔ CHỨC. Hai tầng, và tầng ngoài là thứ mới:

                  /org            chọn tổ chức — một người có thể thuộc nhiều
                  /org/<id>/...   vỏ của MỘT tổ chức

                  Đoạn `<id>` là BẢN SAO của `users.active_tenant_id` để liên
                  kết chia sẻ được. Máy chủ đọc cột chứ không đọc đường dẫn, nên
                  gõ tay mã của tổ chức khác vào đây không cho xem dữ liệu của
                  họ — xem `tenant_middleware`.

                  Tách khỏi `/admin` (nền tảng) và `/settings` (tài khoản của
                  tôi): ba thẩm quyền khác nhau. Vỏ KHÔNG phải hàng rào quyền;
                  máy chủ vẫn cưỡng chế. */}
              {/* Kiểm duyệt ở CẤP CAO NHẤT, không nằm trong `/admin`.

                  Người kiểm duyệt giữ `community_reviewer`, không giữ
                  `is_admin` — đặt trang này sau `requireAdmin` sẽ chặn đúng
                  những người nó sinh ra để phục vụ. Quyền do
                  `require_moderator` ở máy chủ cưỡng chế. */}
              <Route
                path="/moderation"
                element={
                  <ProtectedRoute>
                    <ModerationPage />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/org"
                element={
                  <ProtectedRoute>
                    <OrgPickerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/org/:tenantId"
                element={
                  <ProtectedRoute>
                    <OrgLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<ConsoleHomePage />} />
                <Route path="upload" element={<OrgUploadPage />} />
                <Route path="labels" element={<OrgLabelsPage />} />
                <Route path="sessions" element={<OrgSessionsPage />} />
                <Route path="realtime" element={<OrgRealtimePage />} />
                <Route path="training" element={<OrgTrainingPage />} />
                <Route path="members" element={<OrganizationPage />} />
                <Route path="settings" element={<OrgSettingsLayout />}>
                  <Route index element={<WorkspacesPage />} />
                  <Route path="allocations" element={<ConsoleAllocationsPage />} />
                  <Route path="billing" element={<BillingPage />} />
                  <Route path="integrations" element={<IntegrationsPage />} />
                  <Route path="policies" element={<ConsolePoliciesPage />} />
                </Route>
              </Route>

              {/* Địa chỉ cũ của console. Giữ chuyển hướng chứ không xoá: chúng
                  đã đi ra ngoài trong tài liệu và dấu trang. Tất cả về `/org`,
                  nơi người dùng chọn tổ chức rồi mới vào — mã tổ chức không suy
                  ra được từ đường cũ. */}
              <Route path="/console" element={<Navigate to="/org" replace />} />
              <Route path="/console/*" element={<Navigate to="/org" replace />} />

              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <SettingsLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/settings/account" replace />} />
                <Route path="account" element={<AccountPage />} />
                <Route path="security" element={<SecuritySettingsPage />} />
                <Route path="consents" element={<ConsentsPage />} />
                {/* `/settings/contact` giữ lại làm CHUYỂN HƯỚNG, không xoá.
                    Nó đã đi ra ngoài trong thư mời và trong thông báo bảo mật;
                    một đường dẫn cũ trả 404 là cách chắc chắn khiến người nhận
                    thư kết luận hệ thống hỏng. Nội dung giờ nằm trong Bảo mật. */}
                <Route path="contact" element={<Navigate to="/settings/security" replace />} />
                {/* KHÔNG dùng `requireAdmin` — cờ đó là quản trị viên NỀN TẢNG,
                    còn đây là quản trị viên TỔ CHỨC. Gác bằng cờ sai sẽ tái lập
                    đúng cái gộp khái niệm mà trang này sinh ra để gỡ. Quyền
                    thật do `require_tenant_admin` ở máy chủ cưỡng chế. */}
                <Route path="organization" element={<OrganizationPage />} />
                {/* Hai tầng phạm vi dưới tenant. Route riêng chứ không phải một
                    tab trong trang Tổ chức: nó phải chia sẻ được cho người chấm
                    và phải mở thẳng được từ tài liệu. */}
                <Route path="workspaces" element={<WorkspacesPage />} />
                <Route path="billing" element={<BillingPage />} />
                <Route path="integrations" element={<IntegrationsPage />} />
                <Route path="support" element={<SupportPage />} />
                <Route path="support/:id" element={<SupportPage />} />
                <Route path="language" element={<LanguageSettingsPage />} />
              </Route>

              {/* Địa chỉ cũ. Giữ chuyển hướng chứ không xoá: chúng đã đi ra
                  ngoài trong thư thông báo và có thể nằm trong dấu trang. */}
              <Route path="/account" element={<Navigate to="/settings/account" replace />} />
              <Route path="/organization" element={<Navigate to="/settings/organization" replace />} />
              <Route path="/verify" element={<Navigate to="/settings/contact" replace />} />
              <Route path="/billing" element={<Navigate to="/settings/billing" replace />} />
              <Route path="/integrations" element={<Navigate to="/settings/integrations" replace />} />

              {/* Thùng rác của NGƯỜI DÙNG: mẫu họ tự xoá mềm (backend giới hạn
                  theo auth_user_id). Bản toàn hệ thống nằm ở /admin/trash. */}
              <Route
                path="/trash"
                element={
                  <ProtectedRoute>
                    <TrashPage />
                  </ProtectedRoute>
                }
              />

              <Route path="/" element={<DashboardPage />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          </RouteErrorBoundary>
          </Layout>
          {/* <DebugPanel /> */}
          <ToastContainer />
          <SecurityNotices />
        </Router>
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;
