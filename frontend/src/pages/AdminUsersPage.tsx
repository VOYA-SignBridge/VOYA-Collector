import { useEffect, useState } from "react";
import { useToast } from "../hooks/useToast";
import apiClient from "../api/axiosClient";
import { me } from "../api/auth";
import type { AuthUser } from "../api/auth";
import { CheckIcon, XIcon, UsersIcon } from "../components/ui/Icons";
import LockUserModal, { type LockPayload } from "../components/LockUserModal";
import LoadingSpinner from "../components/ui/LoadingSpinner";

interface UserData {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  locked?: boolean;
  lock_reason?: string;
  lock_until?: number;
  has_warning?: boolean;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [lockTarget, setLockTarget] = useState<UserData | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    me()
      .then((user) => setCurrentUser(user))
      .catch(() => setCurrentUser(null));

    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<UserData[]>("/api/v1/admin/users");
      setUsers(res.data);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Không thể tải danh sách người dùng");
    } finally {
      setLoading(false);
    }
  };

  const doLock = async (userId: string, payload: LockPayload) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/lock`, payload);
      toast.success("Đã khóa tài khoản");
      fetchUsers();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Khóa tài khoản thất bại");
    }
  };

  const unlockUser = async (userId: string) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/unlock`);
      toast.success("Đã mở khóa tài khoản");
      fetchUsers();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Mở khóa thất bại");
    }
  };

  const warnUser = async (userId: string, name: string) => {
    const message = window.prompt(`Nội dung cảnh báo gửi tới "${name}" (người dùng sẽ thấy khi đăng nhập):`, "");
    if (message === null || !message.trim()) return;
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/warn`, { message: message.trim() });
      toast.success(`Đã gửi cảnh báo tới ${name}`);
      fetchUsers();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Gửi cảnh báo thất bại");
    }
  };

  const handleToggleAdmin = async (userId: string, currentIsAdmin: boolean) => {
    if (currentUser?.id === userId && currentIsAdmin) {
      toast.error("Không thể tự gỡ quyền admin của chính mình!");
      return;
    }

    try {
      await apiClient.put(`/api/v1/admin/users/${userId}/role`, { is_admin: !currentIsAdmin });
      toast.success(`Đã cập nhật quyền cho người dùng`);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_admin: !currentIsAdmin } : u))
      );
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Lỗi cập nhật quyền");
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-ctu-blue/10 flex items-center justify-center text-ctu-blue">
              <UsersIcon className="w-6 h-6" />
            </div>
            Quản lý hệ thống
          </h2>
          <p className="text-slate-600">Quản trị danh sách người dùng và phân quyền</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="py-4 px-6 font-semibold text-slate-700">Tên người dùng</th>
                <th className="py-4 px-6 font-semibold text-slate-700">Email</th>
                <th className="py-4 px-6 font-semibold text-slate-700">Trạng thái</th>
                <th className="py-4 px-6 font-semibold text-slate-700">Vai trò Admin</th>
                <th className="py-4 px-6 font-semibold text-slate-700 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12">
                    <LoadingSpinner size="lg" label="Đang tải danh sách người dùng..." />
                  </td>
                </tr>
              ) : !Array.isArray(users) || users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    Không có người dùng nào.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="py-4 px-6">
                      <div className="font-medium text-slate-900">{user.username}</div>
                    </td>
                    <td className="py-4 px-6 text-slate-600">{user.email}</td>
                    <td className="py-4 px-6">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {user.locked ? (
                          <span title={user.lock_reason || ""} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                            {user.lock_until ? "Khóa tạm" : "Bị khóa"}
                          </span>
                        ) : user.is_active ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                            Hoạt động
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                            Vô hiệu
                          </span>
                        )}
                        {user.has_warning && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700">⚠️ Đã cảnh báo</span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      {user.is_admin ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700">
                          <CheckIcon className="w-3.5 h-3.5" />
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-600">
                          User
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {currentUser?.id !== user.id && (
                          <>
                            <button
                              onClick={() => warnUser(user.id, user.username)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors"
                            >
                              ⚠️ Cảnh báo
                            </button>
                            {user.locked ? (
                              <button
                                onClick={() => unlockUser(user.id)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                              >
                                🔓 Mở khóa
                              </button>
                            ) : (
                              <button
                                onClick={() => setLockTarget(user)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors"
                              >
                                🔒 Khóa
                              </button>
                            )}
                          </>
                        )}
                        <button
                          onClick={() => handleToggleAdmin(user.id, user.is_admin)}
                          disabled={currentUser?.id === user.id}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            user.is_admin
                              ? "bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200"
                              : "bg-ctu-blue/10 text-ctu-blue hover:bg-ctu-blue/20 border border-ctu-blue/20"
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          {user.is_admin ? (
                            <><XIcon className="w-4 h-4" /> Gỡ Admin</>
                          ) : (
                            <><CheckIcon className="w-4 h-4" /> Cấp Admin</>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <LockUserModal
        username={lockTarget?.username || null}
        open={!!lockTarget}
        onClose={() => setLockTarget(null)}
        onConfirm={(payload) => lockTarget ? doLock(lockTarget.id, payload) : undefined}
      />
    </div>
  );
}
