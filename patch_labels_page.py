import re
from pathlib import Path

target = Path("frontend/src/pages/LabelsPage.tsx")
content = target.read_text("utf-8")

# Add import taxonomiesApi
if "taxonomiesApi" not in content:
    content = content.replace(
        'import { getLabels, getClassesList, getClassesStats, updateClass, deleteClass, listSamples, updateSample, deleteSample } from "../api/dataset";',
        'import { getLabels, getClassesList, getClassesStats, updateClass, deleteClass, listSamples, updateSample, deleteSample } from "../api/dataset";\nimport { taxonomiesApi, Language, Dialect } from "../api/taxonomies";'
    )

# Add states
states_str = """
  const [labels, setLabels] = useState<Label[]>([]);
"""
new_states = """
  const [labels, setLabels] = useState<Label[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [dialectsList, setDialectsList] = useState<Dialect[]>([]);
"""
if "const [languages," not in content:
    content = content.replace(states_str, new_states)

# Add useEffect for taxonomies
effect_str = """
  // Reset page when search or filters change
  useEffect(() => {
"""
new_effect = """
  useEffect(() => {
    taxonomiesApi.getLanguages().then(setLanguages).catch(console.error);
    taxonomiesApi.getDialects().then(setDialectsList).catch(console.error);
  }, []);

  // Reset page when search or filters change
  useEffect(() => {
"""
if "taxonomiesApi.getLanguages" not in content:
    content = content.replace(effect_str, new_effect)

# Replace getLanguageName and getDialectName
old_getLang = """
  const getLanguageName = (lang?: string): string => {
    const l = (lang || language);
    return l === 'vn' ? 'Tiếng Việt' : l === 'en' ? 'English' : l;
  };
"""
old_getDialect = """
  const getDialectName = (dialect?: string): string => {
    const d = (dialect || 'common');
    const map: Record<string, string> = {
      'common': 'Chung',
      'bac': 'Miền Bắc',
      'nam': 'Miền Nam',
      'trung': 'Miền Trung',
      'hoa-de': 'Hòa Đê',
      'can-tho': 'Cần Thơ',
      'bang-chu-cai': 'Bảng chữ cái',
      'spa': 'Spa',
    };
    return map[d] || d;
  };
"""

new_getLang = """
  const getLanguageName = (lang?: string): string => {
    const l = (lang || language);
    const found = languages.find(x => x.code === l);
    return found ? found.name : (l === 'vn' ? 'Tiếng Việt' : l === 'en' ? 'English' : l);
  };
"""
new_getDialect = """
  const getDialectName = (dialect?: string): string => {
    const d = (dialect || 'common');
    const found = dialectsList.find(x => x.code === d);
    if (found) return found.name;
    const map: Record<string, string> = {
      'common': 'Chung', 'bac': 'Miền Bắc', 'nam': 'Miền Nam', 'trung': 'Miền Trung',
      'hoa-de': 'Hòa Đê', 'can-tho': 'Cần Thơ', 'bang-chu-cai': 'Bảng chữ cái', 'spa': 'Spa',
    };
    return map[d] || d;
  };
"""

content = content.replace(old_getLang.strip(), new_getLang.strip())
content = content.replace(old_getDialect.strip(), new_getDialect.strip())

# Soft delete modal for classes
old_delete_save = """
  const handleDeleteSave = async () => {
    if (!deleteTarget?.class_uid) return;
    setDeleteSaving(true);
    try {
      const res = await deleteClass(deleteTarget.class_uid);
"""
new_delete_save = """
  const handleDeleteSave = async () => {
    if (!deleteTarget?.class_uid) return;
    if (!window.confirm("Bạn có chắc chắn muốn đưa nhãn này và toàn bộ dữ liệu bên trong vào thùng rác không?")) return;
    setDeleteSaving(true);
    try {
      const res = await deleteClass(deleteTarget.class_uid);
"""
if "đưa nhãn này và toàn bộ dữ liệu bên trong vào thùng rác không" not in content:
    content = content.replace(old_delete_save.strip(), new_delete_save.strip())

# Same for sample deletion
old_delete_sessions = """
  const handleDeleteSessions = async (groupIds: string[]) => {
    if (groupIds.length === 0) return;
"""
new_delete_sessions = """
  const handleDeleteSessions = async (groupIds: string[]) => {
    if (groupIds.length === 0) return;
    if (!window.confirm("Bạn có chắc chắn muốn đưa các mẫu này vào thùng rác không?")) return;
"""
if "đưa các mẫu này vào thùng rác" not in content:
    content = content.replace(old_delete_sessions.strip(), new_delete_sessions.strip())


# Add Thùng Rác button next to "+ Tải lên"
# Wait, let's just add it near the header.
old_header = """
          <Button 
            variant="primary" 
            onClick={() => window.location.href = '/upload'}
            className="flex items-center gap-2 px-5 py-2.5 shadow-md hover:shadow-lg transition-all rounded-xl"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Tải lên
          </Button>
"""
new_header = """
          <Button 
            variant="primary" 
            onClick={() => window.location.href = '/upload'}
            className="flex items-center gap-2 px-5 py-2.5 shadow-md hover:shadow-lg transition-all rounded-xl"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Tải lên
          </Button>
          <Button 
            variant="outline" 
            onClick={() => window.location.href = '/trash'}
            className="flex items-center gap-2 px-5 py-2.5 text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300 transition-all rounded-xl bg-white"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            Thùng rác
          </Button>
"""
if "/trash" not in content:
    content = content.replace(old_header.strip(), new_header.strip())


# Fix the dialect array in filtering
old_filter_array = "['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho'].includes(item.dialect)"
new_filter_array = "(dialectsList.length > 0 ? dialectsList.map(d=>d.code) : ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho']).includes(item.dialect)"
content = content.replace(old_filter_array, new_filter_array)

old_available = "const availableDialects = language === 'vn' ? ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho', 'bang-chu-cai', 'spa'] : ['common'];"
new_available = "const availableDialects = dialectsList.length > 0 ? dialectsList.filter(d => d.language_code === (language || 'vn')).map(d => d.code) : (language === 'vn' ? ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho', 'bang-chu-cai', 'spa'] : ['common']);"
content = content.replace(old_available, new_available)

old_edit_available = "const availableDialects = editLanguage === 'vn' ? ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho', 'bang-chu-cai', 'spa'] : ['common'];"
new_edit_available = "const availableDialects = dialectsList.length > 0 ? dialectsList.filter(d => d.language_code === (editLanguage || 'vn')).map(d => d.code) : (editLanguage === 'vn' ? ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho', 'bang-chu-cai', 'spa'] : ['common']);"
content = content.replace(old_edit_available, new_edit_available)

target.write_text(content, "utf-8")
print("LabelsPage.tsx patched successfully.")
