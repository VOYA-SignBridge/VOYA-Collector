import { useEffect, useState } from "react";
import { useToast } from "../hooks/useToast";
import apiClient from "../api/axiosClient";
import { me } from "../api/auth";
import type { AuthUser } from "../api/auth";
import { CheckIcon, XIcon, UsersIcon } from "../components/ui/Icons";
import LockUserModal, { type LockPayload } from "../components/LockUserModal";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { friendlyError } from "../lib/errors";
import { AlertTriangleIcon, LockIcon, UnlockIcon } from "../components/ui/Icons";
import { useI18n } from "../i18n";

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
  const { t } = useI18n();
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
      toast.error(friendlyError(error, t("Không thể tải danh sách người dùng")));
    } finally {
      setLoading(false);
    }
  };

  const doLock = async (userId: string, payload: LockPayload) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/lock`, payload);
      toast.success(t("Đã khóa tài khoản"));
      fetchUsers();
    } catch (error: any) {
      toast.error(friendlyError(error, t("Khóa tài khoản thất bại")));
    }
  };

  const unlockUser = async (userId: string) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/unlock`);
      toast.success(t("Đã mở khóa tài khoản"));
      fetchUsers();
    } catch (error: any) {
      toast.error(friendlyError(error, t("Mở khóa thất bại")));
    }
  };

  const warnUser = async (userId: string, name: string) => {
    const message = window.prompt(t("Nội dung cảnh báo gửi tới \"{name}\" (người dùng sẽ thấy khi đăng nhập):", { name }), "");
    if (message === null || !message.trim()) return;
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/warn`, { message: message.trim() });
      toast.success(t("Đã gửi cảnh báo tới {name}", { name }));
      fetchUsers();
    } catch (error: any) {
      toast.error(friendlyError(error, t("Gửi cảnh báo thất bại")));
    }
  };

  const handleToggleAdmin = async (userId: string, currentIsAdmin: boolean) => {
    if (currentUser?.id === userId && currentIsAdmin) {
      toast.error(t("Không thể tự gỡ quyền admin của chính mình!"));
      return;
    }

    try {
      await apiClient.put(`/api/v1/admin/users/${userId}/role`, { is_admin: !currentIsAdmin });
      toast.success(t("Đã cập nhật quyền cho người dùng"));
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_admin: !currentIsAdmin } : u))
      );
    } catch (error: any) {
      toast.error(friendlyError(error, t("Lỗi cập nhật quyền")));
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
            {t("Quản lý hệ thống")}
          </h2>
          <p className="text-slate-600">{t("Quản trị danh sách người dùng và phân quyền")}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="py-4 px-6 font-semibold text-slate-700">{t("Tên người dùng")}</th>
                <th className="py-4 px-6 font-semibold text-slate-700">Email</th>
                <th className="py-4 px-6 font-semibold text-slate-700">{t("Trạng thái")}</th>
                <th className="py-4 px-6 font-semibold text-slate-700">{t("Quyền quản trị")}</th>
                <th className="py-4 px-6 font-semibold text-slate-700 text-right">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12">
                    <LoadingSpinner size="lg" label={t("Đang tải danh sách người dùng...")} />
                  </td>
                </tr>
              ) : !Array.isArray(users) || users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    {t("Không có người dùng nào.")}
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
                            {user.lock_until ? t("Khóa tạm") : t("Bị khóa")}
                          </span>
                        ) : user.is_active ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-800">
                            <span className="w-1.5 h-1.5 rounded-full bg-sky-600"></span>
                            {t("Hoạt động")}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                            {t("Vô hiệu")}
                          </span>
                        )}
                        {user.has_warning && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700">
                            <AlertTriangleIcon className="h-3 w-3"  aria-hidden="true" />
                            {t("Đã cảnh báo")}
                          </span>
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
                              <AlertTriangleIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
                  {t("Cảnh báo")}
                            </button>
                            {user.locked ? (
                              <button
                                onClick={() => unlockUser(user.id)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-sky-50 text-sky-800 border border-sky-200 hover:bg-sky-100 transition-colors"
                              >
                                <UnlockIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
                  {t("Mở khoá")}
                              </button>
                            ) : (
                              <button
                                onClick={() => setLockTarget(user)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors"
                              >
                                <LockIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
                  {t("Khoá")}
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
                            <><XIcon className="w-4 h-4" /> {t("Gỡ Admin")}</>
                          ) : (
                            <><CheckIcon className="w-4 h-4" /> {t("Cấp Admin")}</>
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
