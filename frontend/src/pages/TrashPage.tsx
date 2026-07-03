import { useState, useEffect } from "react";
import { trashApi } from "../api/trash";
import type { TrashClass, TrashSample } from "../api/trash";
import PageHeader from "../components/ui/PageHeader";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import LoadingSpinner from "../components/ui/LoadingSpinner";

import ErrorBanner from "../components/ErrorBanner";

export default function TrashPage() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  const isAdmin = user?.is_admin || false;
  
  const [activeTab, setActiveTab] = useState<"samples" | "classes">("samples");
  const [samples, setSamples] = useState<TrashSample[]>([]);
  const [classes, setClasses] = useState<TrashClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchTrash = async () => {
    setLoading(true);
    setError(null);
    try {
      if (isAdmin && activeTab === "classes") {
        const cls = await trashApi.getTrashedClasses();
        setClasses(cls);
      } else {
        const smps = await trashApi.getTrashedSamples();
        setSamples(smps);
      }
    } catch (err: any) {
      setError(err.message || "Lỗi khi tải dữ liệu thùng rác");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrash();
  }, [activeTab]);

  useEffect(() => {
    if (!statusMessage) return;
    const timer = setTimeout(() => setStatusMessage(null), 3000);
    return () => clearTimeout(timer);
  }, [statusMessage]);

  const handleRestoreSample = async (uid: string) => {
    try {
      await trashApi.restoreSample(uid);
      setStatusMessage("Khôi phục video thành công");
      fetchTrash();
    } catch (err: any) {
      setError(err.message || "Khôi phục thất bại");
    }
  };

  const handleHardDeleteSample = async (uid: string) => {
    if (!window.confirm("CẢNH BÁO: Xóa vĩnh viễn không thể khôi phục. Bạn chắc chắn chứ?")) return;
    if (!window.confirm("Bạn thực sự chắc chắn muốn xóa vĩnh viễn mục này? (Xác nhận lớp 2)")) return;
    
    try {
      await trashApi.hardDeleteSample(uid);
      setStatusMessage("Đã xóa vĩnh viễn video");
      fetchTrash();
    } catch (err: any) {
      setError(err.message || "Xóa vĩnh viễn thất bại");
    }
  };

  const handleRestoreClass = async (uid: string) => {
    try {
      await trashApi.restoreClass(uid);
      setStatusMessage("Khôi phục nhãn thành công");
      fetchTrash();
    } catch (err: any) {
      setError(err.message || "Khôi phục thất bại");
    }
  };

  const handleHardDeleteClass = async (uid: string) => {
    if (!window.confirm("CẢNH BÁO: Xóa vĩnh viễn nhãn sẽ xóa luôn mọi dữ liệu bên trong. Bạn chắc chắn chứ?")) return;
    if (!window.confirm("Bạn thực sự chắc chắn muốn xóa vĩnh viễn nhãn này? (Xác nhận lớp 2)")) return;
    
    try {
      await trashApi.hardDeleteClass(uid);
      setStatusMessage("Đã xóa vĩnh viễn nhãn");
      fetchTrash();
    } catch (err: any) {
      setError(err.message || "Xóa vĩnh viễn thất bại");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <PageHeader title="Thùng rác" subtitle="Quản lý các mục đã xóa tạm thời. Các mục ở đây có thể được khôi phục hoặc xóa vĩnh viễn." />

      {error && <ErrorBanner message={error}  />}
      {statusMessage && (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-md flex items-start gap-3 shadow-sm animate-fade-in">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-green-500 mt-0.5 shrink-0"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          <div className="text-green-800 font-medium">{statusMessage}</div>
        </div>
      )}

      {isAdmin && (
        <div className="flex space-x-1 border-b border-gray-200">
          <button
            onClick={() => setActiveTab("samples")}
            className={`py-2 px-4 text-sm font-medium border-b-2 focus:outline-none ${activeTab === "samples" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"}`}
          >
            Video
          </button>
          <button
            onClick={() => setActiveTab("classes")}
            className={`py-2 px-4 text-sm font-medium border-b-2 focus:outline-none ${activeTab === "classes" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"}`}
          >
            Nhãn
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden min-h-[400px] relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-white/50 backdrop-blur-sm z-10">
            <LoadingSpinner size="lg"  />
          </div>
        ) : activeTab === "samples" ? (
          samples.length === 0 ? (
            <EmptyState title="Thùng rác trống" description="Không có video nào trong thùng rác." />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Video ID</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nhãn</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Người tạo</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ngày xóa</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Hành động</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {samples.map((s) => (
                    <tr key={s.sample_uid} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{s.sample_uid}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{s.label_original}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{s.user_id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(s.deleted_at).toLocaleString('vi-VN')}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium flex justify-end gap-2">
                        <Button variant="secondary" size="sm" onClick={() => handleRestoreSample(s.sample_uid)}>
                          Khôi phục
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => handleHardDeleteSample(s.sample_uid)}>
                          Xóa vĩnh viễn
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          classes.length === 0 ? (
            <EmptyState title="Thùng rác trống" description="Không có nhãn nào trong thùng rác." />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tên Nhãn</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Thư mục</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ngôn ngữ</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ngày xóa</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Hành động</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {classes.map((c) => (
                    <tr key={c.class_uid} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{c.label_original}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{c.folder_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{c.language} / {c.dialect}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(c.deleted_at).toLocaleString('vi-VN')}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium flex justify-end gap-2">
                        <Button variant="secondary" size="sm" onClick={() => handleRestoreClass(c.class_uid)}>
                          Khôi phục
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => handleHardDeleteClass(c.class_uid)}>
                          Xóa vĩnh viễn
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
}
