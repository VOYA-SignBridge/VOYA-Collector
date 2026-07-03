import re
from pathlib import Path

p = Path("frontend/src/api/validators.ts")
if p.exists():
    c = p.read_text("utf-8")
    c = re.sub(r'session_id\s*:', 'session_uid:', c)
    p.write_text(c, "utf-8")

p = Path("frontend/src/App.tsx")
if p.exists():
    c = p.read_text("utf-8")
    if "<TrashPage" not in c:
        # Add the route
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
        c = c.replace(route_str.strip(), new_route_str.strip())
        p.write_text(c, "utf-8")

p = Path("frontend/src/pages/TrashPage.tsx")
if p.exists():
    c = p.read_text("utf-8")
    # Replace the EmptyState with icon to EmptyState without icon
    c = re.sub(r'<EmptyState title="Thùng rác trống" description="Không có video nào trong thùng rác." icon=\{<svg[^>]+\>.*?</svg>\}\s*/>', '<EmptyState title="Thùng rác trống" description="Không có video nào trong thùng rác." />', c, flags=re.DOTALL)
    c = re.sub(r'<EmptyState title="Thùng rác trống" description="Không có nhãn nào trong thùng rác." icon=\{<svg[^>]+\>.*?</svg>\}\s*/>', '<EmptyState title="Thùng rác trống" description="Không có nhãn nào trong thùng rác." />', c, flags=re.DOTALL)
    p.write_text(c, "utf-8")

print("Fixed TS errors part 2")
