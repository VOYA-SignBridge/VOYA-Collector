import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
// import DebugPanel from "./components/DebugPanel";
import { Suspense, lazy, useEffect, useState } from "react";
import { loadAuthToken } from "./api/axiosClient";
import { me } from "./api/auth";

// Minimal type for the debug interface exposed on window
// interface DebuggerInterface {
//   getState?: () => { enabled?: boolean };
//   setState?: (s: { enabled?: boolean }) => void;
// }

const LabelsPage = lazy(() => import("./pages/LabelsPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
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
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Kiểm tra token khi app startup
    const token = loadAuthToken();
    setAuthToken(token);
    setLoading(false);

    // keep in sync with other tabs / auth changes
    const handleAuthChange = () => {
      setAuthToken(loadAuthToken());
    };

    window.addEventListener("voya:auth-change", handleAuthChange);
    window.addEventListener("storage", handleAuthChange);

    return () => {
      window.removeEventListener("voya:auth-change", handleAuthChange);
      window.removeEventListener("storage", handleAuthChange);
    };
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
    <Router>
      <Layout>
        <Suspense fallback={<div className="p-6">Loading...</div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route
              path="/upload"
              element={
                <ProtectedRoute>
                  <UploadPage />
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

            <Route
              path="/"
              element={<Navigate to={authToken ? "/upload" : "/login"} replace />}
            />
            <Route
              path="*"
              element={<Navigate to={authToken ? "/upload" : "/login"} replace />}
            />
          </Routes>
        </Suspense>
      </Layout>
      {/* <DebugPanel /> */}
    </Router>
  );
}

export default App;
