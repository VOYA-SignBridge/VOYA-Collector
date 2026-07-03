import re
from pathlib import Path

target = Path("frontend/src/App.tsx")
content = target.read_text("utf-8")

if "TrashPage" not in content:
    content = content.replace(
        'const LabelsPage = lazy(() => import("./pages/LabelsPage"));',
        'const LabelsPage = lazy(() => import("./pages/LabelsPage"));\nconst TrashPage = lazy(() => import("./pages/TrashPage"));'
    )
    
    route_str = """
            <Route 
              path="/upload" 
              element={
                <ProtectedRoute>
                  <UploadPage />
                </ProtectedRoute>
              } 
            />
"""
    new_route_str = """
            <Route 
              path="/upload" 
              element={
                <ProtectedRoute>
                  <UploadPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/trash" 
              element={
                <ProtectedRoute>
                  <TrashPage />
                </ProtectedRoute>
              } 
            />
"""
    content = content.replace(route_str.strip(), new_route_str.strip())
    
    target.write_text(content, "utf-8")
    print("App.tsx patched.")
