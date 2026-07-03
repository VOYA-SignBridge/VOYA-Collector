import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
// import DebugPanel from "./components/DebugPanel";
import { Suspense, lazy, useEffect, useState } from "react";
import { loadAuthToken } from "./api/axiosClient";
import { me } from "./api/auth";
import { ToastProvider } from "./hooks/useToast";
import ToastContainer from "./components/ui/ToastContainer";

// Minimal type for the debug interface exposed on window
// interface DebuggerInterface {
//   getState?: () => { enabled?: boolean };
//   setState?: (s: { enabled?: boolean }) => void;
// }

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LabelsPage = lazy(() => import("./pages/LabelsPage"));
const TrashPage = lazy(() => import("./pages/TrashPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const RealtimeRecognitionPage = lazy(() => import("./pages/RealtimeRecognitionPage"));
const TrainingPipeline = lazy(() => import("./pages/training/TrainingPipeline"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));


// Protected Route Wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"loading" | "authed" | "unauth">("loading");
  const [tokenVersion, setTokenVersion] = useState(0);

  useEffect(() => {
    const onAuthChange = () => setTokenVersion((v) => v + 1);
    window.addEventListener("voya:auth-change", onAuthChange);
    window.addEventListener("storage", onAuthChange);
    return () => {
      window.removeEventListener("voya:auth-change", onAuthChange);
      window.removeEventListener("storage", onAuthChange);
    };
  }, []);

  useEffect(() => {
    const token = loadAuthToken();
    if (!token) {
      setStatus("unauth");
      return;
    }

    setStatus("loading");
    me()
      .then(() => setStatus("authed"))
      .catch(() => setStatus("unauth"));
  }, [tokenVersion]);

  if (status === "loading") return <div className="p-6">Loading...</div>;
  if (status === "unauth") return <Navigate to="/login" replace />;
  return <>{children}</>;
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
    return <div className="p-6">Loading...</div>;
  }

  return (
    <ToastProvider>
      <Router>
        <Layout>
          <Suspense fallback={<div className="p-6">Loading...</div>}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              <Route
                path="/trash"
                element={
                  <ProtectedRoute>
                    <TrashPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/labels"
                element={
                  <ProtectedRoute>
                    <LabelsPage />
                  </ProtectedRoute>
                }
              />

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

              {/* AI Studio removed */}

              <Route path="/" element={<DashboardPage />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
        {/* <DebugPanel /> */}
        <ToastContainer />
      </Router>
    </ToastProvider>
  );
}

export default App;
