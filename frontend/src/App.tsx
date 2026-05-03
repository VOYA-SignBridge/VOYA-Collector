import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import DebugPanel from "./components/DebugPanel";
import { Suspense, lazy, useEffect } from "react";

const LabelsPage = lazy(() => import("./pages/LabelsPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));

function App() {
  useEffect(() => {
    // Keyboard shortcut: Shift+D to toggle debug mode
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.shiftKey && e.key === 'D') {
        e.preventDefault();
        const debugger_interface = (window as any).__voyadebug;
        if (debugger_interface?.getState) {
          const state = debugger_interface.getState();
          debugger_interface.setState({ enabled: !state.enabled });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <Router>
        <Layout>
          <Suspense fallback={<div className="p-6">Loading...</div>}>
            <Routes>
              <Route path="/labels" element={<LabelsPage />} />
              <Route path="/upload" element={<UploadPage />} />

              <Route path="/" element={<Navigate to="/upload" />} />
              <Route path="*" element={<Navigate to="/upload" replace />} />
            </Routes>
          </Suspense>
        </Layout>
        <DebugPanel />
    </Router>
  );
}

export default App;
