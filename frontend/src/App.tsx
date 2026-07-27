import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from "react-router-dom";
import Layout from "./components/Layout";
// import DebugPanel from "./components/DebugPanel";
import { Suspense, lazy, useEffect, useState } from "react";
import { ToastProvider } from "./hooks/useToast";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import ToastContainer from "./components/ui/ToastContainer";
import SecurityNotices from "./components/SecurityNotices";
import LoadingScreen from "./components/LoadingScreen";
import NotAuthorizedPage from "./pages/NotAuthorizedPage";

// Minimal type for the debug interface exposed on window
// interface DebuggerInterface {
//   getState?: () => { enabled?: boolean };
//   setState?: (s: { enabled?: boolean }) => void;
// }

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LabelsPage = lazy(() => import("./pages/LabelsPage"));
const LabelDetailPage = lazy(() => import("./pages/LabelDetailPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const RealtimeRecognitionPage = lazy(() => import("./pages/RealtimeRecognitionPage"));
const TrainingPipeline = lazy(() => import("./pages/training/TrainingPipeline"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage"));
const AdminResourcesPage = lazy(() => import("./pages/AdminResourcesPage"));
const AdminActivityPage = lazy(() => import("./pages/AdminActivityPage"));
const AdminDataPage = lazy(() => import("./pages/AdminDataPage"));
const SotAdminPage = lazy(() => import("./pages/SotAdminPage"));
const TrashPage = lazy(() => import("./pages/TrashPage"));


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
          <Suspense fallback={<LoadingScreen />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

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

              <Route path="/realtime" element={<RealtimeRecognitionPage />} />

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

              <Route
                path="/admin/users"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminUsersPage />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/admin/resources"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminResourcesPage />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/admin/activity"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminActivityPage />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/admin/data"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminDataPage />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/admin/sot"
                element={
                  <ProtectedRoute requireAdmin>
                    <SotAdminPage />
                  </ProtectedRoute>
                }
              />

              {/* Trash is open to any signed-in user: a contributor manages
                  their OWN soft-deleted samples (backend scopes by auth_user_id);
                  an admin sees the whole trash incl. deleted labels. */}
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
