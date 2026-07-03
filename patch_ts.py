import re
from pathlib import Path

# Fix taxonomies.ts
p = Path("frontend/src/api/taxonomies.ts")
c = p.read_text("utf-8").replace("import apiClient from './apiClient';", "import axiosClient from './axiosClient';")
c = c.replace("apiClient", "axiosClient")
p.write_text(c, "utf-8")

# Fix trash.ts
p = Path("frontend/src/api/trash.ts")
c = p.read_text("utf-8").replace("import apiClient from './apiClient';", "import axiosClient from './axiosClient';")
c = c.replace("apiClient", "axiosClient")
p.write_text(c, "utf-8")

# Fix LabelsPage.tsx imports
p = Path("frontend/src/pages/LabelsPage.tsx")
c = p.read_text("utf-8").replace('import { taxonomiesApi, Language, Dialect } from "../api/taxonomies";', 'import { taxonomiesApi } from "../api/taxonomies";\nimport type { Language, Dialect } from "../api/taxonomies";')
p.write_text(c, "utf-8")

# Fix TrashPage.tsx imports and TS props errors
p = Path("frontend/src/pages/TrashPage.tsx")
c = p.read_text("utf-8")
c = c.replace('import { trashApi, TrashClass, TrashSample } from "../api/trash";', 'import { trashApi } from "../api/trash";\nimport type { TrashClass, TrashSample } from "../api/trash";')
c = c.replace('import { useAuth } from "../contexts/AuthContext";', '')
c = c.replace('const { user } = useAuth();', 'const user = JSON.parse(localStorage.getItem("user") || "null");')

c = re.sub(r'<PageHeader[^>]+icon=\{[^}]+\}\s*/>', '<PageHeader title="Thùng rác" subtitle="Quản lý các mục đã xóa tạm thời. Các mục ở đây có thể được khôi phục hoặc xóa vĩnh viễn." />', c, flags=re.DOTALL)
c = c.replace('onDismiss={() => setError(null)}', '')
c = c.replace('text="Đang tải dữ liệu..."', '')
c = re.sub(r'icon=\{<svg[^>]+>[^<]+</svg>\s*(<path[^>]+></path>\s*)*\s*(<polyline[^>]+></polyline>\s*)*\s*(<line[^>]+></line>\s*)*\s*</svg>\}', '', c)
c = c.replace('variant="outline"', 'variant="secondary"')
p.write_text(c, "utf-8")

print("Fixed TS errors")
