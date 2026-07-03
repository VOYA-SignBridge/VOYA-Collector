import { useState, useEffect, useMemo } from "react";
import { SmartLoader } from "../components/ui/SmartLoader";
import type { SmartLoaderState } from "../components/ui/SmartLoader";
import { getLabels, getClassesList, getClassesStats, updateClass, deleteClass, listSamples, updateSample, deleteSample } from "../api/dataset";
import { taxonomiesApi } from "../api/taxonomies";
import type { Language, Dialect } from "../api/taxonomies";
import type { Label, ClassRow } from "../types";
import ErrorBanner from "../components/ErrorBanner";
import PageHeader from "../components/ui/PageHeader";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Badge from "../components/ui/Badge";
import Modal from "../components/ui/Modal";
import { useAuth } from "../hooks/useAuth";
import { Pagination } from "../components/ui/Pagination";

export default function LabelsPage() {
  const { loading: authLoading, isAdmin } = useAuth();
  const [labels, setLabels] = useState<Label[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [dialectsList, setDialectsList] = useState<Dialect[]>([]);
  const [classes, setClasses] = useState<ClassRow[] | null>(null);
  const [sampleCounts, setSampleCounts] = useState<Record<string, number>>({});
  const [language, setLanguage] = useState<string>('vn');
  const [dialect, setDialect] = useState<string>(''); // Empty = all dialects
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [operationLogs, setOperationLogs] = useState<string[] | null>(null);
  const [showOperationLogs, setShowOperationLogs] = useState(false);

  const [search, setSearch] = useState<string>("");
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Responsive Labels Pagination
  const [labelsPage, setLabelsPage] = useState(1);
  const [labelsPerPage, setLabelsPerPage] = useState(12);

  // Update labelsPerPage based on window size
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1280) setLabelsPerPage(24); // xl
      else if (window.innerWidth >= 1024) setLabelsPerPage(18); // lg
      else if (window.innerWidth >= 768) setLabelsPerPage(12); // md
      else setLabelsPerPage(6); // sm and mobile
    };
    handleResize(); // Initial call
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    taxonomiesApi.getLanguages().then(setLanguages).catch(console.error);
    taxonomiesApi.getDialects().then(setDialectsList).catch(console.error);
  }, []);

  // Reset page when search or filters change
  useEffect(() => {
    setLabelsPage(1);
  }, [search, language, dialect, viewMode]);

  // Auto-dismiss status message after 2 seconds
  useEffect(() => {
    if (!statusMessage) return;
    const timer = setTimeout(() => setStatusMessage(null), 2000);
    return () => clearTimeout(timer);
  }, [statusMessage]);

  const extractOperationLogs = (res: unknown): string[] | null => {
    if (!res || typeof res !== "object") return null;
    const obj = res as Record<string, unknown>;
    const top = obj["operation_logs"];
    if (Array.isArray(top) && top.every((x) => typeof x === "string")) return top as string[];
    const data = obj["data"];
    if (data && typeof data === "object") {
      const d = data as Record<string, unknown>;
      const logs = d["operation_logs"];
      if (Array.isArray(logs) && logs.every((x) => typeof x === "string")) return logs as string[];
    }
    return null;
  };
  
  const getLanguageName = (lang?: string): string => {
    const l = (lang || language);
    const found = languages.find(x => x.code === l);
    return found ? found.name : (l === 'vn' ? 'Tiếng Việt' : l === 'en' ? 'English' : l);
  };
  
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
  const [editTarget, setEditTarget] = useState<RenderItem | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [editLanguage, setEditLanguage] = useState<string>("vn");
  const [editDialect, setEditDialect] = useState<string>("common");
  const [editSaving, setEditSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RenderItem | null>(null);
  const [deleteSaving, setDeleteSaving] = useState(false);

  // Samples Modal States
  const [samplesModalTarget, setSamplesModalTarget] = useState<RenderItem | null>(null);
  const [samplesList, setSamplesList] = useState<any[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(false);
  const [samplesError, setSamplesError] = useState<string | null>(null);
  const [samplesPage, setSamplesPage] = useState(1);
  const [samplesSearch, setSamplesSearch] = useState("");
  const SAMPLES_PER_PAGE = 10;
  
  const [editSampleTarget, setEditSampleTarget] = useState<any | null>(null);
  const [editSampleUserId, setEditSampleUserId] = useState("");
  const [editSampleSaving, setEditSampleSaving] = useState(false);
  

  
  // SmartLoader State
  const [loaderState, setLoaderState] = useState<SmartLoaderState>("hidden");
  const [loaderProgress, setLoaderProgress] = useState({ current: 0, total: 0 });


  // Load samples when modal opens
  useEffect(() => {
    if (samplesModalTarget) {
      const classUid = samplesModalTarget.class_uid;
      if (!classUid) return;
      
      setSamplesLoading(true);
      setSamplesError(null);
      setSamplesPage(1);
      
      listSamples(classUid)
        .then(res => {
          if (res.ok) {
            setSamplesList(res.data || []);
          } else {
            setSamplesError("Failed to load samples");
          }
        })
        .catch(err => {
          setSamplesError(err.message || "Failed to load samples");
        })
        .finally(() => {
          setSamplesLoading(false);
        });
      } else {
        setSamplesList([]);
        setEditSampleTarget(null);
      }
    }, [samplesModalTarget]);



  const handleSaveSample = async () => {
    if (!editSampleTarget || !editSampleUserId.trim()) return;
    
    setEditSampleSaving(true);
    try {
      const res = await updateSample(editSampleTarget.sample_id, {
        user_id: editSampleUserId.trim()
      });
      
      if (res.ok) {
        setSamplesList(prev => prev.map(s => 
          s.sample_id === editSampleTarget.sample_id
            ? { ...s, user: editSampleUserId.trim() } 
            : s
        ));
        setStatusMessage(`Đã cập nhật thông tin mẫu`);
        setEditSampleTarget(null);
      } else {
        setSamplesError("Failed to update sample");
      }
    } catch (err: any) {
      setSamplesError(err.message || "Failed to update sample");
    } finally {
      setEditSampleSaving(false);
    }
  };

  const handleDeleteBySessionUid = async (sessionUid: string) => {
    if (!sessionUid || sessionUid === '-') return;

    let samplesToDelete = samplesList.filter(s => s.session_uid === sessionUid);
    if (samplesToDelete.length === 0) return;

    if (!window.confirm(`Bạn có chắc chắn muốn đưa toàn bộ ${samplesToDelete.length} mẫu của cụm/session này vào thùng rác không?`)) return;

    setLoaderProgress({ current: 0, total: samplesToDelete.length });
    setLoaderState("processing");
    const successfulIds = new Set<string>();

    try {
      let i = 0;
      while (i < samplesToDelete.length) {
        const s = samplesToDelete[i];
        try {
          const res = await deleteSample(s.sample_id);
          if (res.ok) {
            successfulIds.add(s.sample_id);
          }
          i++; // Move to next sample
          setLoaderProgress({ current: i, total: samplesToDelete.length });
          await new Promise(r => setTimeout(r, 200)); // Small delay between requests
        } catch (err: any) {
          // If error is 429 or 5xx (failed to delete sample)
          setLoaderState("paused");
          await new Promise(r => setTimeout(r, 35000)); // Wait 35 seconds
          setLoaderState("processing");
          // Do NOT increment i, so it retries the same sample
        }
      }

      setLoaderState("success");
      await new Promise(r => setTimeout(r, 1500)); // Show success for 1.5s
      
      // Filter out deleted samples from list
      setSamplesList(prev => prev.filter(s => !successfulIds.has(s.sample_id)));

    } catch (err: any) {
      setSamplesError(err.message || "Lỗi trong quá trình xóa dữ liệu");
    } finally {
      setLoaderState("hidden");
    }
  };

  // Dialect normalization helper: map various forms to canonical slugs used by BE

  const normalizeDialect = (d?: string) => {
    if (!d) return '';
    const s = String(d).toLowerCase().trim();
    // common variants map
    const map: Record<string, string> = {
      'chung': 'common',
      'common': 'common',
      'bac': 'bac',
      'bắc': 'bac',
      'nam': 'nam',
      'trung': 'trung',
      'hoa-de': 'hoa-de',
      'hoa de': 'hoa-de',
      'hoade': 'hoa-de',
      'cần thơ': 'can-tho',
      'can tho': 'can-tho',
      'cantho': 'can-tho',
      'can-tho': 'can-tho',
    };
    return map[s] ?? s;
  };

  // Normalize either `classes` (new BE) or legacy `labels` into a common render shape
  type RenderItem = {
    class_uid?: string;
    class_idx: number;
    slug: string;
    label_original: string;
    language?: string;
    created_at?: string;
    dialect?: string;
    folder_name?: string;
    samples_count?: number;
    is_common_language?: boolean;
    is_common_global?: boolean;
  };

  const getClassRef = (item: { class_uid?: string; class_idx: string | number }) => item.class_uid || String(item.class_idx);

  const renderItems = useMemo<RenderItem[]>(() => {
    const q = search.trim().toLowerCase();
    const raw: RenderItem[] = [];
    if (classes && classes.length > 0) {
      for (const c of classes) {
        // Client-side dialect filter if dialect is selected (use normalized forms)
        const cDialect = normalizeDialect(c.dialect);
          if (dialect && cDialect !== dialect) {
            continue;
          }
        raw.push({
          class_uid: c.class_uid,
          class_idx: typeof c.class_idx === 'string' ? parseInt(c.class_idx, 10) : Number(c.class_idx),
          slug: c.slug,
          label_original: c.label_original,
          language: c.language,
          created_at: c.created_at,
          dialect: cDialect || c.dialect,
          folder_name: c.folder_name,
          samples_count: sampleCounts[c.class_uid] ?? 0,
          is_common_language: String(c.is_common_language) === '1' || c.is_common_language === true,
          is_common_global: String(c.is_common_global) === '1' || c.is_common_global === true,
        });
      }
    } else {
      for (const l of labels) {
        raw.push({
          class_idx: l.class_idx,
          slug: l.slug,
          label_original: l.label_original,
          language,
          created_at: undefined,
          samples_count: 0,
        });
      }
    }

    if (!q) return raw;
    return raw.filter((r) => {
      return (
        String(r.class_idx).includes(q) ||
        (r.label_original || '').toLowerCase().includes(q) ||
        (r.slug || '').toLowerCase().includes(q)
      );
    });
  }, [classes, labels, search, sampleCounts, dialect, language]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        setError(null); // Clear previous errors
        // Try modern classes endpoint first - KHÔNG gửi dialect để lấy TẤT CẢ
        console.log('[LabelsPage] Fetching classes list...');
        const classesRes = await getClassesList(language, '');
        console.log('[LabelsPage] getClassesList result:', classesRes);

        if (!mounted) return;
        if (classesRes.ok) {
          // Debug: log classes response received from backend
          // eslint-disable-next-line no-console
          console.debug('[LabelsPage] getClassesList:', classesRes.data);
          setClasses(classesRes.data.items || []);
          console.log('[LabelsPage] Classes set:', classesRes.data.items?.length || 0, 'items');

          // fetch stats and map counts by class_uid - cũng KHÔNG filter dialect
          console.log('[LabelsPage] Fetching classes stats...');
          const statsRes = await getClassesStats(language, '');
          console.log('[LabelsPage] getClassesStats result:', statsRes);
          
          if (statsRes.ok && statsRes.data) {
            const map: Record<string, number> = {};
            const distribution = statsRes.data.distribution || [];
            for (const s of distribution) {
              if (s.class_uid) map[s.class_uid] = s.count || s.samples_count || 0;
            }
            // Debug: log sample count mapping size
            // eslint-disable-next-line no-console
            console.debug('[LabelsPage] sampleCounts mapped for', Object.keys(map).length, 'classes');
            setSampleCounts(map);
          } else {
            console.warn('[LabelsPage] Stats fetch failed or empty:', statsRes);
          }
        } else {
            console.warn('[LabelsPage] getClassesList failed, trying legacy endpoint. Error:', classesRes.error);
            setClasses(null);
            setSampleCounts({});
            const legacy = await getLabels();
            if (!mounted) return;
            if (legacy.ok) {
              setLabels(legacy.data);
            } else {
              setError(legacy.error);
            }
          }
      } catch (err: unknown) {
        console.error('[LabelsPage] Exception during fetch:', err);
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg || "Failed to load labels");
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [language]); // Chỉ phụ thuộc language, KHÔNG phụ thuộc dialect

  const exportJSON = () => {
    const data = JSON.stringify(classes && classes.length > 0 ? classes : labels, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `labels-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCSV = useMemo(() => {
    const rows = ['class_idx,label_original,slug'];
    if (classes && classes.length > 0) {
      classes.forEach(c => rows.push(`${c.class_idx},"${String(c.label_original).replace(/"/g, '""')}",${c.slug}`));
    } else {
      labels.forEach(l => rows.push(`${l.class_idx},"${l.label_original.replace(/"/g, '""')}",${l.slug}`));
    }
    return rows.join('\n');
  }, [labels, classes]);

  const downloadCSV = () => {
    const blob = new Blob([exportCSV], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `labels-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openEdit = (item: RenderItem) => {
    setStatusMessage(null);
    setError(null);
    setEditTarget(item);
    setEditValue(item.label_original || "");
    setEditLanguage(item.language || language || "vn");
    setEditDialect(item.dialect || "common");
  };

  const openDelete = (item: RenderItem) => {
    setStatusMessage(null);
    setError(null);
    setDeleteTarget(item);
  };

  const applyLabelUpdate = (classRef: string, nextLabel: string, nextSlug?: string, nextLanguage?: string, nextDialect?: string) => {
    setClasses((prev) => prev ? prev.map((item) => {
      if (getClassRef(item) !== classRef) return item;
      return {
        ...item,
        label_original: nextLabel,
        slug: nextSlug ?? item.slug,
        language: nextLanguage ?? item.language,
        dialect: nextDialect ?? item.dialect,
      };
    }) : prev);
    const numericRef = Number(classRef);
    setLabels((prev) => prev.map((item) => item.class_idx === numericRef ? { ...item, label_original: nextLabel, slug: nextSlug ?? item.slug } : item));
  };

  const applyLabelDelete = (classRef: string) => {
    setClasses((prev) => prev ? prev.filter((item) => {
      return getClassRef(item) !== classRef;
    }) : prev);
    const numericRef = Number(classRef);
    setLabels((prev) => prev.filter((item) => item.class_idx !== numericRef));
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    const nextLabel = editValue.trim();
    if (!nextLabel) {
      setError("Label không được để trống.");
      return;
    }

    setEditSaving(true);
    setError(null);
    setShowOperationLogs(false);
    try {
      const classRef = getClassRef(editTarget);
      const result = await updateClass(classRef, {
        label_original: nextLabel,
        language: editLanguage,
        dialect: editDialect,
        is_common_language: editDialect === "common",
      });
      if (!result.ok) {
        setError(result.error || "Không thể cập nhật nhãn.");
        setOperationLogs(extractOperationLogs(result));
        setShowOperationLogs(true);
        return;
      }

      const updated = result.data;
      const logs = extractOperationLogs(result);
      setOperationLogs(logs);
      applyLabelUpdate(
        classRef,
        updated.label_original || nextLabel,
        updated.slug,
        updated.language || editLanguage,
        updated.dialect || editDialect,
      );
      setStatusMessage(
        `Đã cập nhật nhãn "${updated.label_original || nextLabel}" (${getLanguageName(updated.language || editLanguage)} / ${getDialectName(updated.dialect || editDialect)})`
      );
      setEditTarget(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || "Không thể cập nhật nhãn.");
    } finally {
      setEditSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteSaving(true);
    setError(null);
    setShowOperationLogs(false);
    try {
      const classRef = getClassRef(deleteTarget);
      const result = await deleteClass(classRef);
      if (!result.ok) {
        setError(result.error || "Không thể xóa nhãn.");
        setOperationLogs(extractOperationLogs(result));
        setShowOperationLogs(true);
        return;
      }

      applyLabelDelete(classRef);
      const logs = extractOperationLogs(result);
      setOperationLogs(logs);
      setStatusMessage(
        `Đã xóa nhãn "${deleteTarget.label_original}" (${getLanguageName(deleteTarget.language)} / ${getDialectName(deleteTarget.dialect)})`
      );
      setDeleteTarget(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || "Không thể xóa nhãn.");
    } finally {
      setDeleteSaving(false);
    }
  };

  const availableDialects = useMemo(() => {
    const set = new Set<string>(['common', 'bac', 'nam', 'trung', 'can-tho', 'hoa-de', 'bang-chu-cai', 'spa']);
    if (classes && classes.length > 0) {
      classes.forEach(c => { if (c.dialect) set.add(c.dialect); });
    } else {
      labels.forEach(l => { if (l.dialect) set.add(l.dialect); });
    }
    // "common" (Chung) luôn nằm đầu tiên nếu có
    const arr = Array.from(set);
    return arr.sort((a, b) => {
      if (a === 'common') return -1;
      if (b === 'common') return 1;
      return a.localeCompare(b);
    });
  }, [classes, labels]);

  // Show loading state while auth loads
  if (authLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6 relative">
      <SmartLoader state={loaderState} progress={loaderProgress} />
      
      <PageHeader 
        title="Thư viện nhãn" 
        subtitle="Quản lý và tìm kiếm các nhãn ngôn ngữ ký hiệu."
        breadcrumb={["Dữ liệu", "Nhãn"]}
      />

      {error && (
        <ErrorBanner 
          message={error} 
          onClose={() => setError(null)} 
          type="error"
          autoClose={false}
        />
      )}

      {statusMessage && !error && (
        <div className="fixed bottom-4 left-4 right-4 z-40 sm:left-auto sm:right-6 sm:max-w-md rounded-lg border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800 shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">{statusMessage}</div>
            <button onClick={() => setStatusMessage(null)} className="mt-0.5 text-green-600 hover:text-green-700">
              ✕
            </button>
          </div>
        </div>
      )}
      {operationLogs && operationLogs.length > 0 && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium text-sm text-gray-800">📋 Hoạt động (logs)</div>
            <button
              onClick={() => setShowOperationLogs(!showOperationLogs)}
              className="px-2 py-1 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
            >
              {showOperationLogs ? '▼ Ẩn' : '▶ Hiển thị'}
            </button>
          </div>
          {showOperationLogs && (
            <pre className="whitespace-pre-wrap break-words text-xs text-gray-700 bg-white rounded p-2 border border-gray-100 max-h-60 overflow-auto">{operationLogs.join('\n')}</pre>
          )}
        </div>
      )}

      {/* Stats Overview */}
      {!loading && renderItems.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-indigo-50 to-indigo-100 border-indigo-200">
            <div className="text-sm font-medium text-indigo-600">Tổng nhãn</div>
            <div className="text-xl sm:text-3xl font-bold text-indigo-900 mt-1">{renderItems.length}</div>
            <div className="text-xs text-indigo-600 mt-2">trong {language === 'vn' ? 'Tiếng Việt' : 'English'}</div>
          </div>
          
          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-green-50 to-green-100 border-green-200">
            <div className="text-sm font-medium text-green-600">Tổng mẫu</div>
            <div className="text-xl sm:text-3xl font-bold text-green-900 mt-1">
              {renderItems.reduce((sum, item) => sum + (item.samples_count ?? 0), 0)}
            </div>
            <div className="text-xs text-green-600 mt-2">video samples</div>
          </div>
          
          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
            <div className="text-sm font-medium text-purple-600">Phổ biến</div>
            <div className="text-xl sm:text-3xl font-bold text-purple-900 mt-1">
              {renderItems.filter(item => item.is_common_language || item.is_common_global).length}
            </div>
            <div className="text-xs text-purple-600 mt-2">nhãn phổ biến</div>
          </div>
          
          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
            <div className="text-sm font-medium text-orange-600">Phương ngữ</div>
            <div className="text-xl sm:text-3xl font-bold text-orange-900 mt-1">
              {new Set(renderItems.map(item => item.dialect)).size}
            </div>
            <div className="text-xs text-orange-600 mt-2">vùng miền</div>
          </div>
        </div>
      )}

      {/* Labels list */}
      <div className="card card-compact p-3 sm:p-4 lg:p-5">
        <div className="space-y-3 sm:space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center">
              📚 Danh sách nhãn
              {!loading && (
                <Badge variant="info" className="ml-3">
                  {renderItems.length}
                </Badge>
              )}
            </h2>
            
            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => window.location.href = '/trash'}
                className="text-red-500 hover:text-red-600 hover:bg-red-50"
              >
                <span className="flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  Thùng rác
                </span>
              </Button>
              {!loading && renderItems.length > 0 && (
                <>
                  <Button variant="secondary" size="sm" onClick={exportJSON}>
                    <span className="text-xs">📥 JSON</span>
                  </Button>
                  <Button variant="secondary" size="sm" onClick={downloadCSV}>
                    <span className="text-xs">📥 CSV</span>
                  </Button>
                </>
              )}
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-row sm:items-center">
            <div className="min-w-0">
              <select className="input text-sm py-2.5" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="vn">🇻🇳 Tiếng Việt</option>
                <option value="en">🇬🇧 English</option>
              </select>
            </div>
            <div className="min-w-0">
              <select className="input text-sm py-2.5" value={dialect} onChange={(e) => setDialect(e.target.value)}>
                <option value="">🗺️ Tất cả vùng</option>
                {availableDialects.map(d => (
                  <option key={d} value={d}>{getDialectName(d)}</option>
                ))}
              </select>
            </div>
            
            <div className="col-span-2 sm:flex-1 w-full">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="🔍 Tìm kiếm nhãn, slug hoặc ID..."
                className="input w-full text-sm py-2.5"
                aria-label="Tìm kiếm nhãn"
              />
            </div>
            
            <div className="col-span-2 sm:col-span-1 flex border border-gray-300 rounded-lg overflow-hidden w-full sm:w-auto">
              <button
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'grid' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
                onClick={() => setViewMode('grid')}
                title="Xem dạng lưới"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </button>
              <button
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'list' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
                onClick={() => setViewMode('list')}
                title="Xem dạng danh sách"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" className="text-indigo-400" />
            <span className="ml-3 text-gray-600">Loading labels...</span>
          </div>
        ) : renderItems.length === 0 ? (
          <EmptyState 
            title="Không tìm thấy nhãn" 
            description="Thử điều chỉnh bộ lọc hoặc tìm kiếm với từ khóa khác."
          />
        ) : (
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-3 sm:gap-4' : 'space-y-3'}>
            {renderItems.slice((labelsPage - 1) * labelsPerPage, labelsPage * labelsPerPage).map((item) => (
              <div 
                key={item.class_uid ?? item.class_idx}
                className={`${
                  viewMode === 'grid' 
                    ? 'card card-compact group hover:shadow-xl hover:-translate-y-1 transition-all duration-300 p-3 sm:p-4 border-2 border-transparent hover:border-indigo-200' 
                    : 'card card-compact group hover:bg-gradient-to-r hover:from-indigo-50 hover:to-purple-50 transition-all duration-200 p-3 sm:p-4'
                }`}
              >
                <div className={`flex ${
                  viewMode === 'grid' ? 'flex-col' : 'flex-col gap-4 sm:flex-row sm:items-start sm:justify-between'
                }`}>
                  <div className="flex-1 min-w-0 w-full">
                    {/* Header */}
                    <div className="flex items-start gap-2.5 mb-2.5">
                      <div className="flex-shrink-0">
                        <span className="text-2xl">🏷️</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-base sm:text-lg text-gray-900 leading-tight mb-0.5 truncate">
                          {item.label_original}
                        </h3>
                        <p className="text-[11px] sm:text-xs text-gray-500 font-mono truncate">
                          {item.slug}
                        </p>
                      </div>
                    </div>
                    
                    {/* Badges */}
                    {viewMode === 'grid' && (
                      <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
                        {item.class_idx !== -1 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-700">
                            #{item.class_idx}
                          </span>
                        )}
                        {item.dialect === 'common' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-800">
                            Chung
                          </span>
                        )}
                        {item.dialect === 'bac' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">
                            Miền Bắc
                          </span>
                        )}
                        {item.dialect === 'nam' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
                            Miền Nam
                          </span>
                        )}
                        {item.dialect === 'trung' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                            Miền Trung
                          </span>
                        )}
                        {item.dialect === 'hoa-de' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-100 text-purple-800">
                            Hòa Đê
                          </span>
                        )}
                        {item.dialect === 'can-tho' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-cyan-100 text-cyan-800">
                            Cần Thơ
                          </span>
                        )}
                        {item.dialect && !(dialectsList.length > 0 ? dialectsList.map(d=>d.code) : ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho']).includes(item.dialect) && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-200 text-gray-800">
                            {getDialectName(item.dialect)}
                          </span>
                        )}
                        {item.is_common_global && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-100 text-green-800">
                            ⭐ Toàn cầu
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* List view */}
                  {viewMode === 'list' && (
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 flex-wrap">
                        {item.class_idx !== -1 && (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-700">
                            #{item.class_idx}
                          </span>
                        )}
                        {item.dialect === 'common' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-800">Chung</span>
                        )}
                        {item.dialect === 'bac' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">Miền Bắc</span>
                        )}
                        {item.dialect === 'nam' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Miền Nam</span>
                        )}
                        {item.dialect === 'trung' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">Miền Trung</span>
                        )}
                        {item.dialect === 'hoa-de' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-800">Hòa Đê</span>
                        )}
                        {item.dialect === 'can-tho' && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-cyan-100 text-cyan-800">Cần Thơ</span>
                        )}
                        {item.dialect && !(dialectsList.length > 0 ? dialectsList.map(d=>d.code) : ['common', 'bac', 'nam', 'trung', 'hoa-de', 'can-tho']).includes(item.dialect) && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gray-200 text-gray-800">{getDialectName(item.dialect)}</span>
                        )}
                        {item.is_common_global && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">⭐ Toàn cầu</span>
                        )}
                      </div>
                    </div>
                  )}

                  <div className={`mt-3 grid ${isAdmin ? 'grid-cols-3' : 'grid-cols-1'} gap-2 ${viewMode === 'list' ? 'sm:justify-end' : ''}`}>
                    <Button
                      variant="primary"
                      size="sm"
                      className="w-full justify-center px-3 py-2 text-xs"
                      onClick={() => setSamplesModalTarget(item)}
                    >
                      <span className="mr-1">🎥</span> {item.samples_count || 0}
                    </Button>
                    {isAdmin && (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="w-full justify-center px-3 py-2 text-xs"
                          onClick={() => openEdit(item)}
                        >
                          Sửa
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          className="w-full justify-center px-3 py-2 text-xs"
                          onClick={() => openDelete(item)}
                        >
                          Xóa
                        </Button>
                      </>
                    )}
                  </div>
                  {!isAdmin && (
                    <div className="mt-2 text-xs text-gray-500 italic text-center">
                      Chỉ quản trị viên có thể chỉnh sửa
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        
        {/* Labels Pagination Controls */}
        {!loading && renderItems.length > labelsPerPage && (
          <div className="flex flex-col sm:flex-row items-center justify-between mt-6 pt-4 border-t border-gray-100 gap-4">
            <span className="text-sm text-gray-600">
              Hiển thị <span className="font-semibold text-gray-900">{(labelsPage - 1) * labelsPerPage + 1}</span> đến <span className="font-semibold text-gray-900">{Math.min(labelsPage * labelsPerPage, renderItems.length)}</span> trong số <span className="font-semibold text-gray-900">{renderItems.length}</span> nhãn
            </span>
            <Pagination 
              currentPage={labelsPage} 
              totalPages={Math.ceil(renderItems.length / labelsPerPage)} 
              onPageChange={setLabelsPage} 
            />
          </div>
        )}
      </div>

      <Modal
        isOpen={Boolean(editTarget)}
        onClose={() => !editSaving && setEditTarget(null)}
        title={editTarget ? `Chỉnh sửa nhãn #${editTarget.class_idx}` : "Chỉnh sửa nhãn"}
      >
        {editTarget && (
          <div className="space-y-4">
            <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-800">
              Thay đổi này sẽ được đồng bộ xuống CSV, Postgres và các mirror storage liên quan.
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Tên nhãn</label>
              <input
                className="input w-full"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                placeholder="Nhập tên nhãn mới"
                disabled={editSaving}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Ngôn ngữ</label>
                <select
                  className="input w-full"
                  value={editLanguage}
                  onChange={(e) => setEditLanguage(e.target.value)}
                  disabled={editSaving}
                >
                  <option value="vn">🇻🇳 Tiếng Việt</option>
                  <option value="en">🇬🇧 English</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Phương ngữ</label>
                <select
                  className="input w-full"
                  value={editDialect}
                  onChange={(e) => setEditDialect(e.target.value)}
                  disabled={editSaving}
                >
                  {availableDialects.map(d => (
                    <option key={d} value={d}>{getDialectName(d)}</option>
                  ))}
                  {editDialect && !availableDialects.includes(editDialect) && (
                    <option value={editDialect}>{getDialectName(editDialect)}</option>
                  )}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 text-sm text-gray-600 sm:grid-cols-2">
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-xs uppercase tracking-wide text-gray-400">Slug hiện tại</div>
                <div className="mt-1 font-mono text-gray-800">{editTarget.slug}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-xs uppercase tracking-wide text-gray-400">Số mẫu</div>
                <div className="mt-1 font-mono text-gray-800">{editTarget.samples_count ?? 0}</div>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={() => setEditTarget(null)} disabled={editSaving}>
                Hủy
              </Button>
              <Button variant="primary" onClick={saveEdit} loading={editSaving}>
                Lưu thay đổi
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={Boolean(deleteTarget)}
        onClose={() => !deleteSaving && setDeleteTarget(null)}
        title={deleteTarget ? `Xóa nhãn #${deleteTarget.class_idx}` : "Xóa nhãn"}
        size="sm"
      >
        {deleteTarget && (
          <div className="space-y-4">
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Bạn có chắc chắn muốn đưa mục này vào thùng rác không? Các dữ liệu liên quan cũng sẽ được chuyển vào thùng rác.
            </div>
            <div className="space-y-2 text-sm text-gray-700">
              <div><span className="font-medium">Nhãn:</span> {deleteTarget.label_original}</div>
              <div><span className="font-medium">Slug:</span> {deleteTarget.slug}</div>
              <div><span className="font-medium">Số mẫu:</span> {deleteTarget.samples_count ?? 0}</div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={() => setDeleteTarget(null)} disabled={deleteSaving}>
                Hủy
              </Button>
              <Button variant="danger" onClick={confirmDelete} loading={deleteSaving}>
                Xác nhận xóa
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Samples Modal */}
      <Modal
        isOpen={Boolean(samplesModalTarget)}
        onClose={() => setSamplesModalTarget(null)}
        title={samplesModalTarget ? `Samples: ${samplesModalTarget.label_original}` : "Samples"}
        size="lg"
      >
        {samplesLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" className="text-indigo-400" />
            <span className="ml-3 text-gray-600">Đang tải danh sách...</span>
          </div>
        ) : samplesError ? (
          <div className="text-center py-8 text-red-500">
            {samplesError}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <input
                type="text"
                placeholder="Tìm tên file, session, người thu thập..."
                className="input w-full sm:w-1/2"
                value={samplesSearch}
                onChange={(e) => {
                  setSamplesSearch(e.target.value);
                  setSamplesPage(1);
                }}
              />
              {/* Bulk delete removed for individual sample view */}
            </div>
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm text-left text-gray-500">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                  <tr>
                    <th scope="col" className="px-4 py-3">File / Sample ID</th>
                    <th scope="col" className="px-4 py-3">Người thu thập</th>
                    <th scope="col" className="px-4 py-3">Session</th>
                    <th scope="col" className="px-4 py-3">Ngày tạo</th>
                    <th scope="col" className="px-4 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const filteredSamples = samplesList.filter(s => {
                      if (!samplesSearch) return true;
                      const q = samplesSearch.toLowerCase();
                      return (s.user || '').toLowerCase().includes(q) ||
                             (s.file || '').toLowerCase().includes(q) ||
                             (s.session_uid || '').toLowerCase().includes(q);
                    });
                    
                    if (filteredSamples.length === 0) {
                      return (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                            Chưa có mẫu nào phù hợp.
                          </td>
                        </tr>
                      );
                    }
                    
                    return filteredSamples
                      .slice((samplesPage - 1) * SAMPLES_PER_PAGE, samplesPage * SAMPLES_PER_PAGE)
                      .map((sample) => (
                      <tr key={sample.sample_id || sample.file || Math.random()} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900 break-all max-w-[200px] truncate">
                          {sample.file || sample.sample_id || '-'}
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900 break-all">
                          {editSampleTarget?.sample_id === sample.sample_id ? (
                            <input 
                              type="text" 
                              className="input input-sm w-full"
                              value={editSampleUserId}
                              onChange={e => setEditSampleUserId(e.target.value)}
                              disabled={editSampleSaving}
                              placeholder="Tên người thu thập"
                              autoFocus
                            />
                          ) : (
                            sample.user || '-'
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs font-mono text-gray-600 truncate max-w-[150px]" title={sample.session_uid}>
                            {sample.session_uid || '-'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs whitespace-nowrap">
                          {sample.created_at ? new Date(sample.created_at).toLocaleString('vi-VN') : '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {editSampleTarget?.sample_id === sample.sample_id ? (
                            <div className="flex justify-end gap-2">
                              <Button variant="ghost" size="sm" onClick={() => setEditSampleTarget(null)} disabled={editSampleSaving}>Hủy</Button>
                              <Button variant="primary" size="sm" onClick={handleSaveSample} loading={editSampleSaving}>Lưu</Button>
                            </div>
                          ) : (
                            <div className="flex justify-end gap-2">
                              <Button 
                                variant="secondary" 
                                size="sm" 
                                onClick={() => {
                                  setEditSampleTarget(sample);
                                  setEditSampleUserId(sample.user || '');
                                }}
                              >
                                Sửa
                              </Button>
                              <Button 
                                variant="danger" 
                                size="sm" 
                                onClick={async () => {
                                  if (confirm(`Bạn có chắc chắn muốn đưa mẫu này vào thùng rác không?`)) {
                                    try {
                                      const res = await deleteSample(sample.sample_id);
                                      if (res.ok) {
                                        setSamplesList(prev => prev.filter(s => s.sample_id !== sample.sample_id));
                                        setStatusMessage(`Đã xóa mẫu vào thùng rác`);
                                      } else {
                                        setSamplesError(res.error || "Không thể xóa mẫu");
                                      }
                                    } catch (err: any) {
                                      setSamplesError(err.message || "Lỗi xóa mẫu");
                                    }
                                  }
                                }}
                              >
                                Xóa
                              </Button>
                              <Button 
                                variant="danger" 
                                size="sm" 
                                className="bg-red-700 hover:bg-red-800"
                                onClick={() => handleDeleteBySessionUid(sample.session_uid)}
                              >
                                Xóa Cụm
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
            
            {(() => {
              const filteredSamples = samplesList.filter(s => {
                if (!samplesSearch) return true;
                const q = samplesSearch.toLowerCase();
                return (s.user || '').toLowerCase().includes(q) ||
                       (s.file || '').toLowerCase().includes(q) ||
                       (s.session_uid || '').toLowerCase().includes(q);
              });
              const totalFiltered = filteredSamples.length;
              if (totalFiltered > SAMPLES_PER_PAGE) {
                return (
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between mt-4">
                    <span className="text-sm text-gray-700 mb-2 sm:mb-0">
                      Hiển thị <span className="font-semibold">{(samplesPage - 1) * SAMPLES_PER_PAGE + 1}</span> đến <span className="font-semibold">{Math.min(samplesPage * SAMPLES_PER_PAGE, totalFiltered)}</span> trong số <span className="font-semibold">{totalFiltered}</span> mẫu
                    </span>
                    <Pagination 
                      currentPage={samplesPage} 
                      totalPages={Math.ceil(totalFiltered / SAMPLES_PER_PAGE)} 
                      onPageChange={setSamplesPage} 
                    />
                  </div>
                );
              }
              return null;
            })()}
          </div>
        )}
      </Modal>
    </div>
  );
}
