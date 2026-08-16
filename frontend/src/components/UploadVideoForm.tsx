import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import { uploadVideo } from "../api/upload";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import SpeechInputButton from "./SpeechInputButton";
import AddDialectModal from "./AddDialectModal";
import { AlertTriangleIcon } from "./ui/Icons";
import { useToast } from "../hooks/useToast";

// ============================================================================
// TYPES
// ============================================================================

type FileItem = {
  id: string;
  file: File;
  label: string;
  user: string;
  dialect: string;
  class_uid?: string;
  status: 'pending' | 'validating' | 'uploading' | 'done' | 'error';
  progress?: number;
  message?: string;
  uploadedId?: string | number;
};

type ValidationError = {
  fileId: string;
  field: 'label' | 'user' | 'file';
  message: string;
};

type Props = {
  onError?: (msg: string) => void;
  onSuccess?: (results: Array<{ fileId: string; uploadedId: string | number }>) => void;
};

// ============================================================================
// COMPONENT
// ============================================================================

export default function UploadVideoFormV2({ onError, onSuccess }: Props) {
  const { toast } = useToast();
  // ========== STATE ==========
  const [files, setFiles] = useState<FileItem[]>([]);
  const [defaultLabel, setDefaultLabel] = useState("");
  const [defaultClassUid, setDefaultClassUid] = useState<string | undefined>(undefined);
  const [defaultUser, setDefaultUser] = useState(() => localStorage.getItem('lastUser') || '');
  const [defaultDialect, setDefaultDialect] = useState<string>(() =>
    localStorage.getItem('dialectSelected') || 'Miền Bắc'
  );
  const [dialectList, setDialectList] = useState<string[]>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('dialectList') || 'null');
      if (Array.isArray(stored) && stored.length > 0) {
        // Auto-merge new dialects into existing list
        const merged = Array.from(new Set([...stored, 'Cần Thơ']));
        // Save merged list back to localStorage
        localStorage.setItem('dialectList', JSON.stringify(merged));
        return merged;
      }
    } catch (err) {
      void err;
    }
    const defaultList = ['Bảng chữ cái', 'Miền Bắc', 'Miền Trung', 'Miền Nam', 'Hòa Đê'];
    localStorage.setItem('dialectList', JSON.stringify(defaultList));
    return defaultList;
  });
  
  const [uploadingAll, setUploadingAll] = useState(false);
  const [concurrency, setConcurrency] = useState(3);
  const [dragActive, setDragActive] = useState(false);
   const [showBulkEdit, setShowBulkEdit] = useState(false);
   const [showAdvanced, setShowAdvanced] = useState(false);
   const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
   const [recentUsers, setRecentUsers] = useState<string[]>(() => {
     try {
       const raw = localStorage.getItem('recentSigners');
       const parsed = raw ? JSON.parse(raw) : [];
       if (Array.isArray(parsed)) {
         return parsed.filter((x) => typeof x === 'string').slice(0, 5);
       }
     } catch {
       // ignore
     }
     return [];
   });
   
   const [showAddDialectModal, setShowAddDialectModal] = useState(false);
   const fileInputRef = useRef<HTMLInputElement>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);
  
  // ========== VALIDATION ==========
  const validateFile = useCallback((item: FileItem): ValidationError[] => {
    const errors: ValidationError[] = [];
    if (!item.label || item.label.trim() === '') {
      errors.push({ fileId: item.id, field: 'label', message: 'Nhãn không được để trống' });
    }
    if (!item.user || item.user.trim() === '') {
      errors.push({ fileId: item.id, field: 'user', message: 'Người ký hiệu không được để trống' });
    }
    if (item.file.size > 100 * 1024 * 1024) {
      errors.push({ fileId: item.id, field: 'file', message: 'File vượt quá 100MB' });
    }
    return errors;
  }, []);
  
  const validateAllFiles = useCallback((): ValidationError[] => {
    return files.flatMap(f => validateFile(f));
  }, [files, validateFile]);
  
  // ========== COMPUTED ==========
  const stats = useMemo(() => {
    const total = files.length;
    const pending = files.filter(f => f.status === 'pending').length;
    const uploading = files.filter(f => f.status === 'uploading').length;
    const done = files.filter(f => f.status === 'done').length;
    const error = files.filter(f => f.status === 'error').length;
    const validationErrors = validateAllFiles();
    const canUpload = validationErrors.length === 0 && pending > 0;
    
    return { total, pending, uploading, done, error, validationErrors, canUpload };
  }, [files, validateAllFiles]);
  
  // ========== FILE MANAGEMENT ==========
  const generateFileId = () => `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  const addFiles = useCallback((incomingFiles: File[]) => {
    if (!incomingFiles || incomingFiles.length === 0) return;
    
    const videoFiles = incomingFiles.filter(
      f => f.type.startsWith('video/') || /\.(mp4|mov|avi|wmv|mkv|webm)$/i.test(f.name)
    );
    
    if (videoFiles.length === 0) {
      onError?.("Không tìm thấy file video hợp lệ");
      return;
    }
    
    // Kiểm tra xem có CSV mapping đã lưu không
    let csvMapping: Record<string, { label?: string; user?: string; dialect?: string; class_uid?: string }> = {};
    try {
      const stored = localStorage.getItem('csvMapping');
      if (stored) {
        csvMapping = JSON.parse(stored);
      }
    } catch (e) {
      // ignore
    }
    
    setFiles(prev => {
      const existingKeys = new Set(prev.map(p => `${p.file.name}::${p.file.size}`));
      const newFiles: FileItem[] = videoFiles
        .filter(f => !existingKeys.has(`${f.name}::${f.size}`))
        .map(file => {
          // Áp dụng CSV mapping nếu có
          const mapping = csvMapping[file.name] || {};
          return {
            id: generateFileId(),
            file,
            label: mapping.label || defaultLabel,
            user: mapping.user || defaultUser,
            dialect: mapping.dialect || defaultDialect,
            class_uid: mapping.class_uid || defaultClassUid,
            status: 'pending' as const,
          };
        });
      
      if (newFiles.length === 0) {
        toast.warning(`Bỏ qua ${videoFiles.length} file trùng lặp`);
      } else {
        // Xóa CSV mapping sau khi đã áp dụng
        const appliedCount = newFiles.filter(f => csvMapping[f.file.name]).length;
        if (appliedCount > 0) {
          toast.success(`Thêm ${newFiles.length} file, trong đó ${appliedCount} file đã áp dụng CSV mapping`);
          localStorage.removeItem('csvMapping');
        }
      }
      
      return [...prev, ...newFiles];
    });
  }, [defaultLabel, defaultUser, defaultDialect, defaultClassUid, onError, toast]);

  // Listen for global selectClass events dispatched by LabelsPage
  useEffect(() => {
    const handler = (e: Event) => {
      try {
        // CustomEvent detail contains class_uid, class_idx, label, slug
        const ce = e as CustomEvent<Record<string, unknown>>;
        const d = ce.detail as { class_uid?: string; class_idx?: number; label?: string; slug?: string };
        if (d) {
          if (d.label) setDefaultLabel(String(d.label));
          if (d.class_uid) setDefaultClassUid(String(d.class_uid));
          // provide quick feedback
          toast.success(`Chọn nhãn: ${d.label} (${d.class_uid ?? d.class_idx ?? ''})`);
        }
      } catch (err) {
        // ignore
      }
    };
    window.addEventListener('selectClass', handler);
    return () => window.removeEventListener('selectClass', handler);
  }, [onError, toast]);
  
  const removeFile = useCallback((id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);
  
  const updateFile = useCallback((id: string, updates: Partial<FileItem>) => {
    setFiles(prev => prev.map(f => f.id === id ? { ...f, ...updates } : f));
  }, []);
  
  // ========== BULK ACTIONS ==========
  const applyBulkEdit = useCallback((field: 'label' | 'user' | 'dialect', value: string) => {
    if (selectedIds.size === 0) return;
    setFiles(prev => prev.map(f => 
      selectedIds.has(f.id) ? { ...f, [field]: value } : f
    ));
  }, [selectedIds]);
  
  const removeSelected = useCallback(() => {
    setFiles(prev => prev.filter(f => !selectedIds.has(f.id)));
    setSelectedIds(new Set());
  }, [selectedIds]);
  
  const selectAll = useCallback(() => {
    setSelectedIds(new Set(files.map(f => f.id)));
  }, [files]);
  
  const deselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);
  
  // ========== CSV IMPORT ==========
  const handleCSVImport = useCallback(async (csvFile: File) => {
    try {
      const text = await csvFile.text();
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      if (lines.length === 0) {
        onError?.('File CSV trống');
        return;
      }
      
      const header = lines[0].split(',').map(h => h.trim().toLowerCase());
      const rows = lines.slice(1).map(line => {
        const parts = line.split(',').map(p => p.trim());
        const obj: Record<string, string> = {};
        header.forEach((h, i) => { obj[h] = parts[i] || ''; });
        return obj;
      });
      
      console.log('📊 CSV Debug Info:');
      console.log('Headers:', header);
      console.log('Rows parsed:', rows);
      
      if (files.length === 0) {
        // Nếu chưa có file nào, lưu CSV mapping vào localStorage để áp dụng sau
        const mapping: Record<string, { label?: string; user?: string; dialect?: string }> = {};
        rows.forEach(row => {
          const filename = row.filename || row.file || row.name;
          if (filename) {
            mapping[filename] = {
              label: row.label,
              user: row.user,
              dialect: row.dialect,
            };
          }
        });
        localStorage.setItem('csvMapping', JSON.stringify(mapping));
        toast.success(`Đã lưu ${Object.keys(mapping).length} mapping từ CSV. Thêm video vào là tự động áp dụng.`);
        console.log('💾 Saved CSV mapping:', mapping);
        return;
      }
      
      // Nếu đã có file, áp dụng mapping ngay
      console.log('📁 Current files:', files.map(f => f.file.name));
      
      let matchedCount = 0;
      const matchDetails: string[] = [];
      
      setFiles(prev => prev.map(item => {
        const match = rows.find(r => {
          const csvFilename = r.filename || r.file || r.name;
          const matched = csvFilename === item.file.name;
          if (matched) {
            matchDetails.push(`${item.file.name} -> ${r.label || 'N/A'}`);
          }
          return matched;
        });
        
        if (match) {
          matchedCount++;
          return {
            ...item,
            label: match.label || item.label,
            user: match.user || item.user,
            dialect: match.dialect || item.dialect,
          };
        }
        return item;
      }));
      
      console.log('🎯 Match results:', matchDetails);
      
      if (matchedCount > 0) {
        const unmatchedCount = files.length - matchedCount;
        if (unmatchedCount > 0) {
          toast.success(`Đã ánh xạ ${matchedCount}/${files.length} file từ CSV. ${unmatchedCount} file không có trong CSV sẽ dùng giá trị mặc định.`);
        } else {
          toast.success(`Đã ánh xạ ${matchedCount}/${files.length} file từ CSV`);
        }
      } else {
        // Không có file nào match
        const csvFilenames = rows.map(r => r.filename || r.file || r.name).filter(Boolean);
        const currentFilenames = files.map(f => f.file.name);
        
        console.warn('❌ No matches found!');
        console.log('CSV filenames:', csvFilenames);
        console.log('Current filenames:', currentFilenames);
        
        onError?.(`Không tìm thấy file nào khớp với CSV. Kiểm tra tên file trong CSV có trùng với tên file đã chọn không.`);
      }
    } catch (err) {
      console.error('CSV parsing error:', err);
      onError?.('Không đọc được file CSV. Định dạng cần có: filename,label,user,dialect');
    }
  }, [files, onError, toast]);
  
  // ========== UPLOAD ==========
  const uploadSingle = useCallback(async (item: FileItem): Promise<boolean> => {
    const errors = validateFile(item);
    if (errors.length > 0) {
      updateFile(item.id, { 
        status: 'error', 
        message: errors.map(e => e.message).join(', ')
      });
      return false;
    }
    
    updateFile(item.id, { status: 'uploading', progress: 0 });
    
    try {
      const res = await uploadVideo(item.file, item.user, item.label, item.dialect, (pct) => {
        updateFile(item.id, { progress: pct });
      });
      const result = res as { ok?: boolean; data?: { id?: string | number }; error?: string };
      if (result.ok) {
        updateFile(item.id, { 
          status: 'done', 
          progress: 100,
          message: 'Thành công',
          uploadedId: result.data?.id
        });
        return true;
      } else {
        updateFile(item.id, { 
          status: 'error', 
          message: result.error || 'Upload thất bại'
        });
        return false;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      updateFile(item.id, { status: 'error', message: msg });
      return false;
    }
  }, [validateFile, updateFile]);
  
  const uploadAll = useCallback(async () => {
    const pendingFiles = files.filter(f => f.status === 'pending');
    if (pendingFiles.length === 0) {
      onError?.('Không có file nào cần upload');
      return;
    }
    
    const validationErrors = validateAllFiles();
    if (validationErrors.length > 0) {
      onError?.(`Có ${validationErrors.length} lỗi cần sửa trước khi upload`);
      return;
    }
    
    setUploadingAll(true);
    const results: Array<{ fileId: string; uploadedId: string | number }> = [];
    
    // Concurrent upload pool
    let idx = 0;
    const runWorker = async () => {
      while (idx < pendingFiles.length) {
        const item = pendingFiles[idx++];
        const success = await uploadSingle(item);
        if (success && item.uploadedId) {
          results.push({ fileId: item.id, uploadedId: item.uploadedId });
        }
      }
    };
    
    const workers = Array.from(
      { length: Math.min(concurrency, pendingFiles.length) },
      () => runWorker()
    );
    
    await Promise.all(workers);
    setUploadingAll(false);
    
    if (results.length > 0) {
      onSuccess?.(results);
    }
  }, [files, concurrency, validateAllFiles, uploadSingle, onError, onSuccess]);
  
  // ========== DRAG & DROP ==========
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);
  
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  }, [addFiles]);
  
  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files ? Array.from(e.target.files) : [];
    addFiles(selectedFiles);
    if (e.target) e.target.value = '';
  }, [addFiles]);
  
  const handleCSVInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const csvFile = e.target.files?.[0];
    if (csvFile) handleCSVImport(csvFile);
    if (e.target) e.target.value = '';
  }, [handleCSVImport]);
  
  // ========== PERSISTENCE ==========
  useEffect(() => {
    if (defaultUser) {
      localStorage.setItem('lastUser', defaultUser);
    }
  }, [defaultUser]);
  
  useEffect(() => {
    localStorage.setItem('dialectSelected', defaultDialect);
  }, [defaultDialect]);
  
  // ========== HELPERS ==========
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };
  
  const getStatusBadge = (status: FileItem['status']) => {
    const variants = {
      pending: { variant: 'default' as const, text: 'Chờ upload' },
      validating: { variant: 'warning' as const, text: 'Kiểm tra' },
      uploading: { variant: 'warning' as const, text: 'Đang tải' },
      done: { variant: 'success' as const, text: 'Hoàn thành' },
      error: { variant: 'danger' as const, text: 'Lỗi' },
    };
    return variants[status];
  };
  
  const triggerFilePicker = (folder = false) => {
    if (fileInputRef.current) {
      try {
        if (folder) {
          fileInputRef.current.setAttribute('webkitdirectory', 'true');
        } else {
          fileInputRef.current.removeAttribute('webkitdirectory');
        }
      } catch (e) {
        // ignore
      }
      fileInputRef.current.click();
    }
  };

  const rememberUser = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setRecentUsers((prev) => {
      const next = [trimmed, ...prev.filter((x) => x !== trimmed)].slice(0, 5);
      try {
        localStorage.setItem('recentSigners', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);
  
  // ============================================================================
  // RENDER
  // ============================================================================
  
  return (
    <div className="w-full mx-auto space-y-5 sm:space-y-6">
      {/* Header with Stats */}
      <div className="card card-compact">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
          <div className="flex items-center">
            <div className="w-11 h-11 sm:w-12 sm:h-12 bg-gradient-to-br from-ctu-blue to-ctu-navy rounded-xl flex items-center justify-center mr-3 sm:mr-4 shadow-md">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Tải video</h2>
              <p className="text-sm text-gray-600">Quản lý và tải nhiều video cùng lúc</p>
            </div>
          </div>
          
          {stats.total > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              {stats.pending > 0 && <Badge variant="default">{stats.pending} chờ</Badge>}
              {stats.uploading > 0 && <Badge variant="warning">{stats.uploading} đang tải</Badge>}
              {stats.done > 0 && <Badge variant="success">{stats.done} xong</Badge>}
              {stats.error > 0 && <Badge variant="danger">{stats.error} lỗi</Badge>}
            </div>
          )}
        </div>
        
        {/* Default Values Form */}
        <div className="bg-gradient-to-r from-ctu-blue/10 to-ctu-navy/5 rounded-xl p-4 sm:p-5 border border-ctu-blue/30 mb-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center">
            <svg className="w-4 h-4 mr-2 text-ctu-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Giá trị mặc định (áp dụng cho file mới)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Nhãn mặc định</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={defaultLabel}
                  onChange={(e) => setDefaultLabel(e.target.value)}
                  placeholder="ví dụ: đi bộ"
                  className="input text-sm flex-1"
                />
                <SpeechInputButton
                  onText={(text) => setDefaultLabel(text)}
                  title="Dùng giọng nói để điền nhãn mặc định"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Người ký hiệu</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={defaultUser}
                  onChange={(e) => setDefaultUser(e.target.value)}
                  placeholder="ví dụ: Trân"
                  className="input text-sm flex-1"
                  onBlur={() => rememberUser(defaultUser)}
                />
                <SpeechInputButton
                  onText={(text) => setDefaultUser(text)}
                  title="Dùng giọng nói để điền tên người ký hiệu"
                />
              </div>
              {recentUsers.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-blue-700">
                  <span className="text-blue-500">Gợi ý:</span>
                  {recentUsers.map((name) => (
                    <button
                      type="button"
                      key={name}
                      onClick={() => setDefaultUser(name)}
                      className="px-2 py-0.5 rounded-full bg-ctu-blue/10 hover:bg-ctu-blue/20 text-ctu-blue border border-ctu-blue/30"
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Bộ ngôn ngữ</label>
              <select
                value={defaultDialect}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === '__add_new__') {
                    setShowAddDialectModal(true);
                  } else {
                    setDefaultDialect(v);
                  }
                }}
                className="input text-sm"
              >
                {dialectList.map(d => <option key={d} value={d}>{d}</option>)}
                <option value="__add_new__">+ Thêm mới...</option>
              </select>
            </div>
          </div>
        </div>

        <AddDialectModal
          isOpen={showAddDialectModal}
          onClose={() => setShowAddDialectModal(false)}
          onAdd={(name) => {
            const updated = Array.from(new Set([...dialectList, name]));
            setDialectList(updated);
            setDefaultDialect(name);
            localStorage.setItem('dialectList', JSON.stringify(updated));
          }}
        />
        
        {/* Upload Area */}
        <div
          className={`
            relative border-2 border-dashed rounded-xl p-5 sm:p-8 transition-all duration-200
            ${dragActive ? 'border-ctu-blue bg-ctu-blue/5 scale-[1.02]' : 'border-gray-300 hover:border-gray-400 bg-gray-50'}
          `}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            multiple
            onChange={handleFileInput}
            className="hidden"
          />
          
          <div className="text-center">
            <div className="w-14 h-14 sm:w-16 sm:h-16 bg-gradient-to-br from-gray-200 to-gray-300 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm">
              <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Kéo thả video vào đây
            </h3>
            <p className="text-sm text-gray-600 mb-6">hoặc chọn từ máy tính</p>
            
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 mb-4">
              <Button onClick={() => triggerFilePicker(false)} variant="primary" className="shadow-md w-full sm:w-auto">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
                Chọn file
              </Button>
              <Button onClick={() => triggerFilePicker(true)} variant="secondary" className="shadow-md w-full sm:w-auto">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                Chọn thư mục
              </Button>
              <Button
                onClick={() => csvInputRef.current?.click()}
                variant="secondary"
                className="shadow-md w-full sm:w-auto"
                title="Import CSV để ánh xạ label hàng loạt. Format: filename,label,user,dialect"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Import CSV
              </Button>
              <input
                ref={csvInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={handleCSVInput}
                className="hidden"
              />
            </div>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-2 text-xs text-gray-500 text-center sm:text-left">
              <p>
                Hỗ trợ: MP4, MOV, AVI, WMV, MKV, WebM • Tối đa 100MB/file
              </p>
              <span className="text-gray-400 hidden sm:inline">•</span>
              <p className="text-ctu-blue font-medium">
                Có thể import CSV trước hoặc sau đều được
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* File List */}
      {files.length > 0 && (
        <div className="card card-compact">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              Danh sách file ({files.length})
            </h3>
            <div className="flex flex-wrap items-center gap-2">
              {selectedIds.size > 0 ? (
                <>
                  <span className="text-sm text-gray-600">{selectedIds.size} đã chọn</span>
                  <Button onClick={() => setShowBulkEdit(!showBulkEdit)} variant="secondary" className="text-xs">
                    Sửa hàng loạt
                  </Button>
                  <Button onClick={removeSelected} variant="danger" className="text-xs">
                    Xóa đã chọn
                  </Button>
                  <Button onClick={deselectAll} variant="secondary" className="text-xs">
                    Bỏ chọn
                  </Button>
                </>
              ) : (
                <Button onClick={selectAll} variant="secondary" className="text-xs">
                  Chọn tất cả
                </Button>
              )}
            </div>
          </div>
          
          {/* Bulk Edit Panel */}
          {showBulkEdit && selectedIds.size > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
              <h4 className="text-sm font-semibold text-gray-900 mb-3">
                Áp dụng cho {selectedIds.size} file đã chọn:
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Nhãn</label>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input
                      type="text"
                      placeholder="Nhập nhãn mới"
                      className="input text-sm flex-1"
                      id="bulk-label-input"
                    />
                    <Button
                      onClick={() => {
                        const val = (document.getElementById('bulk-label-input') as HTMLInputElement)?.value;
                        if (val) applyBulkEdit('label', val);
                      }}
                      variant="primary"
                      className="text-xs"
                    >
                      Áp dụng
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Người ký hiệu</label>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input
                      type="text"
                      placeholder="Nhập tên người ký hiệu"
                      className="input text-sm flex-1"
                      id="bulk-user-input"
                    />
                    <Button
                      onClick={() => {
                        const val = (document.getElementById('bulk-user-input') as HTMLInputElement)?.value;
                        if (val) applyBulkEdit('user', val);
                      }}
                      variant="primary"
                      className="text-xs"
                    >
                      Áp dụng
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Bộ ngôn ngữ</label>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <select className="input text-sm flex-1" id="bulk-dialect-select">
                      {dialectList.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                    <Button
                      onClick={() => {
                        const val = (document.getElementById('bulk-dialect-select') as HTMLSelectElement)?.value;
                        if (val) applyBulkEdit('dialect', val);
                      }}
                      variant="primary"
                      className="text-xs"
                    >
                      Áp dụng
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Validation Errors Summary */}
          {stats.validationErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <h4 className="text-sm font-semibold text-red-900 mb-2">
                <AlertTriangleIcon className="mr-1 inline-block h-4 w-4 align-text-bottom" />
            Có {stats.validationErrors.length} lỗi cần sửa trước khi upload:
              </h4>
              <ul className="text-xs text-red-800 space-y-1">
                {stats.validationErrors.slice(0, 5).map((err, idx) => (
                  <li key={idx}>
                    • File "{files.find(f => f.id === err.fileId)?.file.name}": {err.message}
                  </li>
                ))}
                {stats.validationErrors.length > 5 && (
                  <li className="text-red-600 font-medium">
                    ... và {stats.validationErrors.length - 5} lỗi khác
                  </li>
                )}
              </ul>
            </div>
          )}
          
          {/* Files Table */}
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="w-full min-w-[920px] text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === files.length && files.length > 0}
                      onChange={(e) => e.target.checked ? selectAll() : deselectAll()}
                      className="rounded"
                    />
                  </th>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">File</th>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">Nhãn</th>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">Người ký hiệu</th>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">Bộ ngôn ngữ</th>
                  <th className="px-2 sm:px-3 py-2 text-left text-xs font-medium text-gray-700 whitespace-nowrap">Trạng thái</th>
                  <th className="px-2 sm:px-3 py-2 text-right text-xs font-medium text-gray-700 whitespace-nowrap">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {files.map((item) => {
                  const badge = getStatusBadge(item.status);
                  const errors = validateFile(item);
                  const hasError = errors.length > 0;
                  
                  return (
                    <tr
                      key={item.id}
                      className={`hover:bg-gray-50 transition-colors ${
                        selectedIds.has(item.id) ? 'bg-ctu-blue/5' : ''
                      }`}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={(e) => {
                            const next = new Set(selectedIds);
                            if (e.target.checked) {
                              next.add(item.id);
                            } else {
                              next.delete(item.id);
                            }
                            setSelectedIds(next);
                          }}
                          className="rounded"
                        />
                      </td>
                      <td className="px-2 sm:px-3 py-2">
                        <div className="flex items-center space-x-2 min-w-0">
                          <div className="w-8 h-8 bg-ctu-blue/10 rounded flex items-center justify-center flex-shrink-0">
                            <svg className="w-4 h-4 text-ctu-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-gray-900 truncate" title={item.file.name}>
                              {item.file.name}
                            </div>
                            <div className="text-xs text-gray-500">{formatFileSize(item.file.size)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-2 sm:px-3 py-2">
                        <input
                          type="text"
                          value={item.label}
                          onChange={(e) => updateFile(item.id, { label: e.target.value })}
                          placeholder="Nhãn..."
                          className={`input text-sm w-full ${hasError && !item.label ? 'border-red-300 bg-red-50' : ''}`}
                          disabled={item.status === 'uploading' || item.status === 'done'}
                        />
                      </td>
                      <td className="px-2 sm:px-3 py-2">
                        <input
                          type="text"
                          value={item.user}
                          onChange={(e) => updateFile(item.id, { user: e.target.value })}
                          placeholder="Tên người ký hiệu..."
                          className={`input text-sm w-full ${hasError && !item.user ? 'border-red-300 bg-red-50' : ''}`}
                          disabled={item.status === 'uploading' || item.status === 'done'}
                        />
                      </td>
                      <td className="px-2 sm:px-3 py-2">
                        <select
                          value={item.dialect}
                          onChange={(e) => updateFile(item.id, { dialect: e.target.value })}
                          className="input text-sm w-full"
                          disabled={item.status === 'uploading' || item.status === 'done'}
                        >
                          {dialectList.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                      </td>
                      <td className="px-2 sm:px-3 py-2">
                        <div className="flex flex-col space-y-1">
                          <Badge variant={badge.variant} size="sm">
                            {badge.text}
                          </Badge>
                          {item.message && (
                            <span className="text-xs text-gray-600 truncate" title={item.message}>
                              {item.message}
                            </span>
                          )}
                          {item.status === 'uploading' && item.progress !== undefined && (
                            <div className="w-full bg-gray-200 rounded-full h-1">
                              <div
                                className="bg-ctu-blue h-1 rounded-full transition-all"
                                style={{ width: `${item.progress}%` }}
                              />
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-2 sm:px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {item.status === 'error' && (
                            <button
                              onClick={() => uploadSingle(item)}
                              className="text-xs text-ctu-blue hover:text-ctu-navy font-medium"
                            >
                              Thử lại
                            </button>
                          )}
                          {item.status !== 'uploading' && (
                            <button
                              onClick={() => removeFile(item.id)}
                              className="text-xs text-red-600 hover:text-red-700 font-medium"
                            >
                              Xóa
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          {/* Upload Actions */}
          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pt-4 border-t border-gray-200">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <div className="text-sm text-gray-600">
                <span className="font-medium">{stats.pending}</span> file chờ upload
              </div>
              {stats.validationErrors.length > 0 && (
                <div className="text-sm text-red-600 font-medium">
                  <AlertTriangleIcon className="mr-1 inline-block h-3.5 w-3.5 align-text-bottom" />
                {stats.validationErrors.length} lỗi
                </div>
              )}
            </div>
            
            <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
              {stats.total > 0 && (
                <Button
                  onClick={() => {
                    if (window.confirm(`Xóa tất cả ${files.length} file?`)) {
                      setFiles([]);
                      setSelectedIds(new Set());
                    }
                  }}
                  variant="secondary"
                  disabled={uploadingAll}
                  className="w-full sm:w-auto"
                >
                  Xóa tất cả
                </Button>
              )}
              <Button
                onClick={uploadAll}
                variant="primary"
                loading={uploadingAll}
                disabled={!stats.canUpload || uploadingAll}
                className="shadow-md w-full sm:w-auto"
              >
                {uploadingAll ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Đang upload ({stats.uploading}/{stats.total})
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    Upload {stats.pending} file
                  </>
                )}
              </Button>
            </div>
          </div>
          
          {/* Advanced Settings */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-gray-600 hover:text-gray-900 font-medium flex items-center"
            >
              <svg
                className={`w-4 h-4 mr-1 transform transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              Cài đặt nâng cao
            </button>
            
            {showAdvanced && (
              <div className="mt-3 bg-gray-50 rounded-lg p-3 sm:p-4">
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <label className="text-sm font-medium text-gray-700">
                    Số luồng upload đồng thời:
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={concurrency}
                    onChange={(e) => setConcurrency(parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-sm font-semibold text-gray-900 min-w-[3ch]">
                    {concurrency}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Tăng số luồng để upload nhanh hơn (khuyến nghị: 3-5). Quá cao có thể gây lỗi server.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
