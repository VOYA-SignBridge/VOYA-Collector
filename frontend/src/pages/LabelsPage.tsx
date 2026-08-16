import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getLabels, getClassesList, getClassesStats, updateClass, deleteClass, registerClass } from "../api/dataset";
import type { Label, ClassRow } from "../types";
import ErrorBanner from "../components/ErrorBanner";
import PageHeader from "../components/ui/PageHeader";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import LoadingScreen from "../components/LoadingScreen";
import Badge from "../components/ui/Badge";
import Modal from "../components/ui/Modal";
import { SearchIcon, TagIcon } from "../components/ui/Icons";
import { useAuth } from "../hooks/useAuth";
import { dialectLabel } from "../config/dialectLabels";
import DialectBadge from "../components/DialectBadge";
import { useVocabularyRegistry } from "../hooks/useVocabularyRegistry";
import { StarIcon, XIcon, GlobeIcon } from "../components/ui/Icons";
import { useI18n } from "../i18n";

export default function LabelsPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { loading: authLoading, isAdmin } = useAuth();
  // The four dialect pickers below used to be four hand-written <option> lists
  // that disagreed with each other and could never offer a newly approved
  // dialect. They all read this now.
  const { dialects: registryDialects, regions: registryRegions } = useVocabularyRegistry();
  // Vùng miền đọc từ chính bản đăng ký, KHÔNG cứng hoá. Bảng tra phương ngữ
  // viết tay trước đây đã bị gỡ vì đúng lý do này: nó không bao giờ học được
  // một giá trị được thêm sau khi mã đã viết.
  const regionOptions = useMemo(
    () => (registryRegions.length > 0
      ? registryRegions
      : [{ code: "unclassified", name_vi: t("Chưa phân loại") }]),
    [registryRegions, t],
  );
  const regionLabel = (code?: string): string =>
    registryRegions.find((r) => r.code === code)?.name_vi || code || "";

  const dialectOptions = useMemo(
    () => registryDialects.filter((d) => d.is_active !== false).map((d) => d.dialect_id),
    [registryDialects],
  );
  const [labels, setLabels] = useState<Label[]>([]);
  const [classes, setClasses] = useState<ClassRow[] | null>(null);
  const [sampleCounts, setSampleCounts] = useState<Record<string, number>>({});
  const [language, setLanguage] = useState<string>('vn');
  const [dialect, setDialect] = useState<string>(''); // Empty = all dialects
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [operationLogs, setOperationLogs] = useState<string[] | null>(null);
  const [showOperationLogs, setShowOperationLogs] = useState(false);

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
    return l === 'vn' ? t('Tiếng Việt') : l === 'en' ? 'English' : l;
  };
  
  // The slug is the label — see config/dialectLabels.ts. The hand-written map
  // that used to live here could not show a dialect approved through the
  // registry, because nobody would have added it.
  const getDialectName = (dialect?: string): string => dialectLabel(dialect || 'common');
  const [search, setSearch] = useState<string>("");
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [editTarget, setEditTarget] = useState<RenderItem | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [editLanguage, setEditLanguage] = useState<string>("vn");
  const [editDialect, setEditDialect] = useState<string>("common");
  // Vùng KHỞI ĐẦU là `unclassified`, và đó là một trạng thái có nghĩa chứ
  // không phải chỗ trống: "đã vào hệ thống, chưa qua khâu phân loại vùng".
  // Cố ý không đoán thành `common` — `common` nghĩa là "đã xác minh rằng
  // không cần phân biệt vùng", một khẳng định mạnh hơn hẳn.
  const [editRegion, setEditRegion] = useState<string>("unclassified");
  const [editSaving, setEditSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RenderItem | null>(null);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [createTarget, setCreateTarget] = useState(false);
  const [createValue, setCreateValue] = useState<string>("");
  const [createLanguage, setCreateLanguage] = useState<string>("vn");
  const [createDialect, setCreateDialect] = useState<string>("common");
  const [createRegion, setCreateRegion] = useState<string>("unclassified");
  const [createSaving, setCreateSaving] = useState(false);

  // Applied to dialect values coming FROM the backend, which already returns
  // canonical ids — so this is defensive tidying only.
  //
  // It used to carry a table of spelling variants ('bắc' -> 'bac', 'cần thơ' ->
  // 'can-tho', …). That table was written for an era when a dialect could be
  // typed by hand; every picker now offers ids from GET /vocabulary/registry,
  // and the table could never have learned a newly approved dialect anyway.
  // Verified before removing it: no non-slug dialect exists in classes,
  // samples, raw_uploads or dataset/samples.csv.
  const normalizeDialect = (d?: string) => (d ? String(d).toLowerCase().trim() : '');

  // Normalize either `classes` (new BE) or legacy `labels` into a common render shape
  type RenderItem = {
    class_uid?: string;
    class_idx: number;
    slug: string;
    label_original: string;
    language?: string;
    created_at?: string;
    dialect?: string;
    region?: string;
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
          region: c.region,
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
              if (s.class_uid) map[s.class_uid] = s.samples_count ?? s.count ?? 0;
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
    setEditDialect(item.dialect || dialect || "common");
    setEditRegion(item.region || "unclassified");
  };

  const navigateToDetails = (item: RenderItem) => {
    const id = item.class_uid || item.class_idx;
    navigate(`/labels/${id}`);
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

  const saveCreate = async () => {
    const nextLabel = createValue.trim();
    if (!nextLabel) {
      setError(t("Tên nhãn không được để trống."));
      return;
    }

    setCreateSaving(true);
    setError(null);
    setShowOperationLogs(false);
    try {
      const result = await registerClass({
        label: nextLabel,
        language: createLanguage,
        dialect: createDialect,
        region: createRegion,
        is_common_language: createDialect === "common",
        is_common_global: false,
      });
      if (!result.ok) {
        setError(result.error || t("Không thể tạo nhãn."));
        return;
      }

      const updated = result.data;
      setStatusMessage(
        t("Đã tạo nhãn \"{label_original}\" ({p1} / {p2})", { label_original: updated.label_original || nextLabel, p1: getLanguageName(updated.language || createLanguage), p2: getDialectName(updated.dialect || createDialect) })
      );
      
      setClasses((prev) => prev ? [updated, ...prev] : [updated]);
      if (updated.class_uid) {
        setSampleCounts((prev) => ({ ...prev, [updated.class_uid]: 0 }));
      }
      setCreateTarget(false);
      setCreateValue("");
      setCreateLanguage("vn");
      setCreateDialect("common");
      setCreateRegion("unclassified");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || t("Không thể tạo nhãn."));
    } finally {
      setCreateSaving(false);
    }
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    const nextLabel = editValue.trim();
    if (!nextLabel) {
      setError(t("Label không được để trống."));
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
        region: editRegion,
        is_common_language: editDialect === "common",
      });
      if (!result.ok) {
        setError(result.error || t("Không thể cập nhật nhãn."));
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
        t("Đã cập nhật nhãn \"{label_original}\" ({p1} / {p2})", { label_original: updated.label_original || nextLabel, p1: getLanguageName(updated.language || editLanguage), p2: getDialectName(updated.dialect || editDialect) })
      );
      setEditTarget(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || t("Không thể cập nhật nhãn."));
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
        setError(result.error || t("Không thể xóa nhãn."));
        setOperationLogs(extractOperationLogs(result));
        setShowOperationLogs(true);
        return;
      }

      applyLabelDelete(classRef);
      const logs = extractOperationLogs(result);
      setOperationLogs(logs);
      setStatusMessage(
        t("Đã xóa nhãn \"{label_original}\" ({p1} / {p2})", { label_original: deleteTarget.label_original, p1: getLanguageName(deleteTarget.language), p2: getDialectName(deleteTarget.dialect) })
      );
      setDeleteTarget(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || t("Không thể xóa nhãn."));
    } finally {
      setDeleteSaving(false);
    }
  };

  // Show loading state while auth loads
  if (authLoading) {
    return <LoadingScreen />;
  }



  return (
    <div className="space-y-6">
      <PageHeader 
        title={t("Thư viện nhãn")} 
        subtitle={t("Quản lý và tìm kiếm các nhãn ngôn ngữ ký hiệu.")}
        breadcrumb={[{ label: "Dashboard", href: "/" }, t("Dữ liệu"), t("Nhãn")]}
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
        <div className="fixed bottom-4 left-4 right-4 z-40 sm:left-auto sm:right-6 sm:max-w-md rounded-lg border border-sky-300 bg-sky-50 px-4 py-3 text-sm text-sky-800 shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">{statusMessage}</div>
            <button onClick={() => setStatusMessage(null)} className="mt-0.5 text-sky-700 hover:text-sky-800" aria-label={t("Đóng thông báo")}>
              <XIcon className="h-4 w-4"  aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
      {operationLogs && operationLogs.length > 0 && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium text-sm text-gray-800">{t("Hoạt động (logs)")}</div>
            <button
              onClick={() => setShowOperationLogs(!showOperationLogs)}
              className="px-2 py-1 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
            >
              {showOperationLogs ? t('▼ Ẩn') : t('▶ Hiển thị')}
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
          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-ctu-blue/10 to-blue-50 border-ctu-blue/30">
            <div className="text-sm font-medium text-ctu-blue">{t("Tổng nhãn")}</div>
            <div className="text-xl sm:text-3xl font-bold text-ctu-navy mt-1">{renderItems.length}</div>
            <div className="text-xs text-ctu-blue mt-2">trong {language === 'vn' ? t('Tiếng Việt') : 'English'}</div>
          </div>

          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-sky-50 to-sky-100 border-sky-200">
            <div className="text-sm font-medium text-sky-700">{t("Tổng mẫu")}</div>
            <div className="text-xl sm:text-3xl font-bold text-sky-900 mt-1">
              {renderItems.reduce((sum, item) => sum + (item.samples_count ?? 0), 0)}
            </div>
            <div className="text-xs text-sky-700 mt-2">{t("mẫu video")}</div>
          </div>

          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-ctu-yellow/15 to-amber-50 border-ctu-yellow/40">
            <div className="text-sm font-medium text-ctu-navy">{t("Phổ biến")}</div>
            <div className="text-xl sm:text-3xl font-bold text-ctu-navy mt-1">
              {renderItems.filter(item => item.is_common_language || item.is_common_global).length}
            </div>
            <div className="text-xs text-ctu-navy/80 mt-2">{t("nhãn phổ biến")}</div>
          </div>

          <div className="card card-compact p-3 sm:p-4 bg-gradient-to-br from-ctu-navy/10 to-slate-50 border-ctu-navy/30">
            <div className="text-sm font-medium text-ctu-navy">{t("Phương ngữ")}</div>
            <div className="text-xl sm:text-3xl font-bold text-ctu-navy mt-1">
              {new Set(renderItems.map(item => item.dialect)).size}
            </div>
            <div className="text-xs text-ctu-navy/80 mt-2">{t("vùng miền")}</div>
          </div>
        </div>
      )}

      {/* Labels list */}
      <div className="card card-compact p-3 sm:p-4 lg:p-5">
        <div className="space-y-3 sm:space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center">
              Danh sách nhãn
              {!loading && (
                <Badge variant="info" className="ml-3">
                  {renderItems.length}
                </Badge>
              )}
            </h2>

            <div className="flex items-center gap-2">
              {!loading && renderItems.length > 0 && (
                <>
                  {isAdmin && (
                    <Button variant="primary" size="sm" onClick={() => setCreateTarget(true)}>
                      <span className="text-xs">{t("Tạo nhãn mới")}</span>
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={exportJSON}>
                    <span className="text-xs">{t("Xuất JSON")}</span>
                  </Button>
                  <Button variant="secondary" size="sm" onClick={downloadCSV}>
                    <span className="text-xs">{t("Xuất CSV")}</span>
                  </Button>
                </>
              )}
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-row sm:items-center">
            <div className="min-w-0">
              <select className="input text-sm py-2.5" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="vn">{t("🇻🇳 Tiếng Việt")}</option>
                <option value="en">{t("🇬🇧 Tiếng Anh")}</option>
              </select>
            </div>
            <div className="min-w-0">
              <select className="input text-sm py-2.5" value={dialect} onChange={(e) => setDialect(e.target.value)}>
                <option value="">{t("Tất cả vùng")}</option>
                {dialectOptions.map((d) => (
                  <option key={d} value={d}>{dialectLabel(d)}</option>
                ))}
              </select>
            </div>
            
            <div className="col-span-2 sm:flex-1 w-full relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("Tìm kiếm nhãn, slug hoặc ID...")}
                className="input w-full pl-9 text-sm py-2.5"
                aria-label={t("Tìm kiếm nhãn")}
              />
            </div>
            
            <div className="col-span-2 sm:col-span-1 flex border border-gray-300 rounded-lg overflow-hidden w-full sm:w-auto">
              <button
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'grid' ? 'bg-ctu-blue text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
                onClick={() => setViewMode('grid')}
                title={t("Xem dạng lưới")}
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </button>
              <button
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'list' ? 'bg-ctu-blue text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
                onClick={() => setViewMode('list')}
                title={t("Xem dạng danh sách")}
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
            <LoadingSpinner size="lg" label={t("Đang tải danh sách nhãn...")} />
          </div>
        ) : renderItems.length === 0 ? (
          <EmptyState 
            title={t("Không tìm thấy nhãn")} 
            description={t("Thử điều chỉnh bộ lọc hoặc tìm kiếm với từ khóa khác.")}
          />
        ) : (
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-3 sm:gap-4' : 'space-y-3'}>
            {renderItems.map((item) => (
              <div 
                key={item.class_uid ?? item.class_idx}
                className={`${
                  viewMode === 'grid'
                    ? 'card card-compact group hover:shadow-xl hover:-translate-y-1 transition-all duration-300 p-3 sm:p-4 border-2 border-transparent hover:border-ctu-blue/30'
                    : 'card card-compact group hover:bg-gradient-to-r hover:from-ctu-blue/5 hover:to-ctu-navy/5 transition-all duration-200 p-3 sm:p-4'
                }`}
              >
                <div className={`flex ${
                  viewMode === 'grid' ? 'flex-col' : 'flex-col gap-4 sm:flex-row sm:items-start sm:justify-between'
                }`}>
                  <div className="flex-1 min-w-0 w-full">
                    {/* Header */}
                    <div className="flex items-start gap-2.5 mb-2.5">
                      <div className="flex-shrink-0 text-ctu-blue">
                        <TagIcon className="h-6 w-6" />
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
                        <DialectBadge dialect={item.dialect} size="sm" />
                        {/* Vùng miền: chỉ hiện khi ĐÃ phân loại.
                            `unclassified` là mặc định của gần như mọi nhãn cũ, nên
                            hiện nó ở mọi dòng là nhiễu mà không thêm thông tin.
                            Ngược lại, hai biến thể vùng của cùng một từ đều mang
                            vùng thật, nên cả hai đều hiện — và đó đúng là lúc cần
                            phân biệt, vì slug và phương ngữ của chúng giống hệt nhau. */}
                        {item.region && item.region !== "unclassified" && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-700">
                            <GlobeIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5" aria-hidden="true" />
                            {regionLabel(item.region)}
                          </span>
                        )}
                        {item.is_common_global && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sky-100 text-sky-800">
                            <StarIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
                    {t("Toàn cầu")}
                          </span>
                        )}
                      </div>
                    )}
                    
                    {/* Sample Progress (Grid View) */}
                    {viewMode === 'grid' && (() => {
                      const sessions = Math.floor((item.samples_count ?? 0) / 5);
                      const isCompleted = sessions >= 5;
                      return (
                      <div className="mt-2.5">
                        <div className="flex items-center justify-between text-[11px] font-medium text-gray-600 mb-1">
                          <span>{t("Tiến độ thu thập")}</span>
                          <span className={`${isCompleted ? 'text-ctu-blue font-bold' : 'text-gray-900'}`}>{sessions} / 5</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-1.5 mb-1.5 overflow-hidden">
                          <div 
                            className="h-1.5 rounded-full transition-all duration-500 bg-ctu-blue"
                            style={{ width: `${Math.min(100, (sessions / 5) * 100)}%` }}
                          ></div>
                        </div>
                        {!isCompleted ? (
                          <div className="text-[10px] text-amber-600 font-medium">
                            {t("Cần thêm {n} lần quay", { n: 5 - sessions })}
                          </div>
                        ) : (
                          <div className="text-[10px] text-ctu-blue font-medium flex items-center gap-1">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                            {t("Đã đủ điều kiện huấn luyện")}
                          </div>
                        )}
                      </div>
                      );
                    })()}
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
                        <DialectBadge dialect={item.dialect} size="md" />
                        {/* Vùng miền: chỉ hiện khi ĐÃ phân loại.
                            `unclassified` là mặc định của gần như mọi nhãn cũ, nên
                            hiện nó ở mọi dòng là nhiễu mà không thêm thông tin.
                            Ngược lại, hai biến thể vùng của cùng một từ đều mang
                            vùng thật, nên cả hai đều hiện — và đó đúng là lúc cần
                            phân biệt, vì slug và phương ngữ của chúng giống hệt nhau. */}
                        {item.region && item.region !== "unclassified" && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-700">
                            <GlobeIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5" aria-hidden="true" />
                            {regionLabel(item.region)}
                          </span>
                        )}
                        {item.is_common_global && (
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                    <StarIcon className="mr-1 h-3.5 w-3.5"  aria-hidden="true" />
                    {t("Toàn cầu")}</span>
                        )}
                      </div>
                      
                      {/* Sample Progress (List View) */}
                      {(() => {
                        const sessions = Math.floor((item.samples_count ?? 0) / 5);
                        const isCompleted = sessions >= 5;
                        return (
                          <div className="flex flex-col min-w-[140px]">
                            <div className="flex items-center justify-between text-[11px] mb-1">
                              <span className="text-gray-500 font-medium">{t("Tiến độ")}</span>
                              <span className={`font-bold ${isCompleted ? 'text-ctu-blue' : 'text-gray-900'}`}>{sessions}/5</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5 mb-1 overflow-hidden">
                              <div 
                                className="h-1.5 rounded-full transition-all duration-500 bg-ctu-blue"
                                style={{ width: `${Math.min(100, (sessions / 5) * 100)}%` }}
                              ></div>
                            </div>
                            {!isCompleted ? (
                              <div className="text-[10px] text-amber-600 font-medium text-right">
                                {t("Thiếu {n} lần quay", { n: 5 - sessions })}
                              </div>
                            ) : (
                              <div className="text-[10px] text-ctu-blue font-medium text-right flex items-center justify-end gap-1">
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                                {t("Đã đủ")}
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {isAdmin ? (
                    <div className={`mt-3 grid grid-cols-3 gap-2 ${viewMode === 'list' ? 'sm:justify-end' : ''}`}>
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full justify-center px-2 py-2 text-xs"
                        onClick={() => navigateToDetails(item)}
                      >
                        {t("Chi tiết")}
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full justify-center px-2 py-2 text-xs"
                        onClick={() => openEdit(item)}
                      >
                        {t("Sửa")}
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        className="w-full justify-center px-2 py-2 text-xs"
                        onClick={() => openDelete(item)}
                      >
                        {t("Xóa")}
                      </Button>
                    </div>
                  ) : (
                    <div className={`mt-3 grid grid-cols-1 gap-2 ${viewMode === 'list' ? 'sm:justify-end' : ''}`}>
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full justify-center px-3 py-2 text-xs"
                        onClick={() => navigateToDetails(item)}
                      >
                        {t("Chi tiết")}
                      </Button>
                      <div className="mt-1 text-xs text-gray-500 italic text-center">
                        {t("Chỉ quản trị viên có thể chỉnh sửa")}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        isOpen={createTarget}
        onClose={() => !createSaving && setCreateTarget(false)}
        title={t("Tạo nhãn mới")}
      >
        <div className="space-y-4">
          <div className="rounded-lg border border-ctu-blue/30 bg-ctu-blue/10 p-4 text-sm text-ctu-navy">
            {t("Nhãn mới sẽ được lưu vào cơ sở dữ liệu và đồng bộ vào file CSV gốc. Bạn cần thu thập ít nhất 5 mẫu cho nhãn này để có thể huấn luyện (Train) mô hình AI.")}
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">{t("Tên nhãn (Tiếng Việt/English)")}</label>
            <input
              className="input w-full"
              value={createValue}
              onChange={(e) => setCreateValue(e.target.value)}
              placeholder={t("Ví dụ: Xin chào, Cảm ơn...")}
              disabled={createSaving}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">{t("Ngôn ngữ")}</label>
              <select
                className="input w-full"
                value={createLanguage}
                onChange={(e) => setCreateLanguage(e.target.value)}
                disabled={createSaving}
              >
                <option value="vn">{t("🇻🇳 Tiếng Việt")}</option>
                <option value="en">{t("🇬🇧 Tiếng Anh")}</option>
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">{t("Phương ngữ (Dialect)")}</label>
              <select
                className="input w-full"
                value={createDialect}
                onChange={(e) => setCreateDialect(e.target.value)}
                disabled={createSaving}
              >
                {dialectOptions.map((d) => (
                  <option key={d} value={d}>{dialectLabel(d)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">{t("Vùng miền")}</label>
              <select
                className="input w-full"
                value={createRegion}
                onChange={(e) => setCreateRegion(e.target.value)}
                disabled={createSaving}
              >
                {regionOptions.map((r) => (
                  <option key={r.code} value={r.code}>{r.name_vi || r.code}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-500">
                {t("Cùng một từ có thể có nhiều biến thể vùng; mỗi biến thể là một nhãn riêng.")}
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-100 mt-6">
            <Button variant="ghost" onClick={() => setCreateTarget(false)} disabled={createSaving}>
              {t("Hủy")}
            </Button>
            <Button variant="primary" onClick={saveCreate} loading={createSaving}>
              {t("Tạo nhãn")}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={Boolean(editTarget)}
        onClose={() => !editSaving && setEditTarget(null)}
        title={editTarget ? t("Chỉnh sửa nhãn #{class_idx}", { class_idx: editTarget.class_idx }) : t("Chỉnh sửa nhãn")}
      >
        {editTarget && (
          <div className="space-y-4">
            <div className="rounded-lg border border-ctu-blue/30 bg-ctu-blue/10 p-4 text-sm text-ctu-navy">
              {t("Thay đổi này sẽ được đồng bộ xuống CSV, Postgres và các mirror storage liên quan.")}
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">{t("Tên nhãn")}</label>
              <input
                className="input w-full"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                placeholder={t("Nhập tên nhãn mới")}
                disabled={editSaving}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">{t("Ngôn ngữ")}</label>
                <select
                  className="input w-full"
                  value={editLanguage}
                  onChange={(e) => setEditLanguage(e.target.value)}
                  disabled={editSaving}
                >
                  <option value="vn">{t("🇻🇳 Tiếng Việt")}</option>
                  <option value="en">{t("🇬🇧 Tiếng Anh")}</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">{t("Phương ngữ")}</label>
                <select
                  className="input w-full"
                  value={editDialect}
                  onChange={(e) => setEditDialect(e.target.value)}
                  disabled={editSaving}
                >
                  {dialectOptions.map((d) => (
                    <option key={d} value={d}>{dialectLabel(d)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">{t("Vùng miền")}</label>
                <select
                  className="input w-full"
                  value={editRegion}
                  onChange={(e) => setEditRegion(e.target.value)}
                  disabled={editSaving}
                >
                  {regionOptions.map((r) => (
                    <option key={r.code} value={r.code}>{r.name_vi || r.code}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 text-sm text-gray-600 sm:grid-cols-2">
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-xs uppercase tracking-wide text-gray-400">{t("Slug hiện tại")}</div>
                <div className="mt-1 font-mono text-gray-800">{editTarget.slug}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="text-xs uppercase tracking-wide text-gray-400">{t("Số mẫu")}</div>
                <div className="mt-1 font-mono text-gray-800">{editTarget.samples_count ?? 0}</div>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={() => setEditTarget(null)} disabled={editSaving}>
                {t("Hủy")}
              </Button>
              <Button variant="primary" onClick={saveEdit} loading={editSaving}>
                {t("Lưu thay đổi")}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={Boolean(deleteTarget)}
        onClose={() => !deleteSaving && setDeleteTarget(null)}
        title={deleteTarget ? t("Xóa nhãn #{class_idx}", { class_idx: deleteTarget.class_idx }) : t("Xóa nhãn")}
        size="sm"
      >
        {deleteTarget && (
          <div className="space-y-4">
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              {t("Xóa nhãn này sẽ xóa luôn các mẫu liên quan và cập nhật lại các mirror storage đã đồng bộ.")}
            </div>
            <div className="space-y-2 text-sm text-gray-700">
              <div><span className="font-medium">{t("Nhãn:")}</span> {deleteTarget.label_original}</div>
              <div><span className="font-medium">{t("Định danh:")}</span> {deleteTarget.slug}</div>
              <div><span className="font-medium">{t("Số mẫu:")}</span> {deleteTarget.samples_count ?? 0}</div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={() => setDeleteTarget(null)} disabled={deleteSaving}>
                {t("Hủy")}
              </Button>
              <Button variant="danger" onClick={confirmDelete} loading={deleteSaving}>
                {t("Xác nhận xóa")}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
