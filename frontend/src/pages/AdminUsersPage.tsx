import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useToast } from "../hooks/useToast";
import { useSudo, isSudoRequired } from "../hooks/useSudo";
import apiClient from "../api/axiosClient";
import { me } from "../api/auth";
import type { AuthUser } from "../api/auth";
import {
  AlertTriangleIcon,
  DotsIcon,
  LifeBuoyIcon,
  LockIcon,
  SearchIcon,
  UnlockIcon,
} from "../components/ui/Icons";
import LockUserModal, { type LockPayload } from "../components/LockUserModal";
import RecoveryModal, { type RecoveryPayload, type RecoveryResult } from "../components/admin/RecoveryModal";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import PageHeader from "../components/ui/PageHeader";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { friendlyError } from "../lib/errors";
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

type Filter = "all" | "admin" | "locked" | "warned";

/** Menu "⋯": đóng khi bấm ra ngoài hoặc nhấn Esc, mở được bằng bàn phím. */
function RowMenu({ label, children }: { label: string; children: (close: () => void) => React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50 hover:text-slate-800"
      >
        <DotsIcon className="h-5 w-5" aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

function MenuItem({
  onClick,
  icon,
  danger,
  children,
}: {
  onClick: () => void;
  icon: React.ReactNode;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
        danger ? "text-red-600" : "text-slate-700"
      }`}
    >
      <span aria-hidden="true">{icon}</span>
      {children}
    </button>
  );
}

export default function AdminUsersPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const { ensureSudo } = useSudo();
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [lockTarget, setLockTarget] = useState<UserData | null>(null);
  const [recoveryTarget, setRecoveryTarget] = useState<UserData | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<UserData[]>("/api/v1/admin/users");
      setUsers(res.data);
    } catch (error: unknown) {
      toast.error(friendlyError(error, t("Không thể tải danh sách người dùng")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    me()
      .then((user) => setCurrentUser(user))
      .catch(() => setCurrentUser(null));
    fetchUsers();
  }, [fetchUsers]);

  const doLock = async (userId: string, payload: LockPayload) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/lock`, payload);
      toast.success(t("Đã khóa tài khoản"));
      fetchUsers();
    } catch (error: unknown) {
      toast.error(friendlyError(error, t("Khóa tài khoản thất bại")));
    }
  };

  const unlockUser = async (userId: string) => {
    try {
      await apiClient.post(`/api/v1/admin/users/${userId}/unlock`);
      toast.success(t("Đã mở khóa tài khoản"));
      fetchUsers();
    } catch (error: unknown) {
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
    } catch (error: unknown) {
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
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_admin: !currentIsAdmin } : u)));
    } catch (error: unknown) {
      toast.error(friendlyError(error, t("Lỗi cập nhật quyền")));
    }
  };

  /**
   * Hỏi mật khẩu quản trị khi bị TỪ CHỐI, không hỏi trước (xem `useSudo`):
   * phiên sudo còn hạn thì không bắt gõ lại.
   */
  const doRecovery = async (user: UserData, payload: RecoveryPayload): Promise<RecoveryResult | null> => {
    const call = () => apiClient.post<RecoveryResult>(`/api/v1/admin/users/${user.id}/recovery`, payload);
    try {
      let res;
      try {
        res = await call();
      } catch (err) {
        if (!isSudoRequired(err)) throw err;
        if (!(await ensureSudo(t("Hỗ trợ tài khoản")))) {
          toast.error(t("Đã huỷ: thao tác này cần xác thực lại mật khẩu."));
          return null;
        }
        res = await call();
      }
      if (payload.action === "reset_link") {
        // Hộp thoại sẽ hiện liên kết; toast chỉ nói thư có đi hay không.
        if (res?.data?.email_sent) toast.success(t("Đã gửi liên kết đặt lại mật khẩu tới {email}", { email: user.email }));
        return res?.data ?? {};
      }
      toast.success(t("Đã gỡ xác thực hai bước của {name}", { name: user.username }));
      return {};
    } catch (error: unknown) {
      toast.error(friendlyError(error, t("Hỗ trợ tài khoản thất bại")));
      return null;
    }
  };

  const counts = useMemo(
    () => ({
      all: users.length,
      admin: users.filter((u) => u.is_admin).length,
      locked: users.filter((u) => u.locked).length,
      warned: users.filter((u) => u.has_warning).length,
    }),
    [users],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return users.filter((u) => {
      if (filter === "admin" && !u.is_admin) return false;
      if (filter === "locked" && !u.locked) return false;
      if (filter === "warned" && !u.has_warning) return false;
      return !q || u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
    });
  }, [users, query, filter]);

  const filters: { key: Filter; label: string }[] = [
    { key: "all", label: t("Tất cả") },
    { key: "admin", label: t("Quản trị") },
    { key: "locked", label: t("Bị khoá") },
    { key: "warned", label: t("Đã cảnh báo") },
  ];

  return (
    <div className="space-y-5 animate-fade-in">
      <PageHeader
        title={t("Người dùng")}
        subtitle={t("{n} tài khoản. Tìm một người, rồi hỗ trợ, cảnh báo hoặc khoá ở cột bên phải.", { n: counts.all })}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative sm:w-80">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Tìm theo email hoặc tên đăng nhập")}
            aria-label={t("Tìm tài khoản theo email hoặc tên đăng nhập")}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/20"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("Lọc người dùng")}>
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                filter === f.key
                  ? "border-ctu-blue bg-ctu-blue text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {f.label} <span className="opacity-70">{counts[f.key]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-sm text-slate-600">
                <th scope="col" className="px-4 py-3 font-semibold">{t("Tên người dùng")}</th>
                <th scope="col" className="px-4 py-3 font-semibold">{t("Trạng thái")}</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={3} className="py-12">
                    <LoadingSpinner size="lg" label={t("Đang tải danh sách người dùng...")} />
                  </td>
                </tr>
              ) : shown.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-10 text-center text-sm text-slate-500">
                    {users.length === 0 ? t("Không có người dùng nào.") : t("Không có tài khoản nào khớp.")}
                  </td>
                </tr>
              ) : (
                shown.map((user) => {
                  const self = currentUser?.id === user.id;
                  return (
                    <tr key={user.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">
                          {user.username}
                          {self && <span className="ml-2 text-xs font-normal text-slate-400">{t("(bạn)")}</span>}
                        </div>
                        <div className="text-sm text-slate-500">{user.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {user.locked ? (
                            <span title={user.lock_reason || ""}>
                              <Badge variant="danger" size="sm">{user.lock_until ? t("Khóa tạm") : t("Bị khóa")}</Badge>
                            </span>
                          ) : user.is_active ? (
                            <Badge variant="success" size="sm">{t("Hoạt động")}</Badge>
                          ) : (
                            <Badge variant="neutral" size="sm">{t("Vô hiệu")}</Badge>
                          )}
                          {user.has_warning && <Badge variant="warning" size="sm">{t("Đã cảnh báo")}</Badge>}
                          {user.is_admin && <Badge variant="neutral" size="sm" icon={false}>Admin</Badge>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          {!self && (
                            <Button variant="secondary" size="sm" onClick={() => setRecoveryTarget(user)}>
                              <LifeBuoyIcon className="mr-1 inline h-4 w-4 -mt-0.5" aria-hidden="true" />
                              {t("Hỗ trợ")}
                            </Button>
                          )}
                          <RowMenu label={t("Thêm thao tác cho {name}", { name: user.username })}>
                            {(close) => (
                              <>
                                {!self && (
                                  <MenuItem
                                    icon={<AlertTriangleIcon className="h-4 w-4" />}
                                    onClick={() => { close(); warnUser(user.id, user.username); }}
                                  >
                                    {t("Cảnh báo")}
                                  </MenuItem>
                                )}
                                {!self && (user.locked ? (
                                  <MenuItem
                                    icon={<UnlockIcon className="h-4 w-4" />}
                                    onClick={() => { close(); unlockUser(user.id); }}
                                  >
                                    {t("Mở khoá")}
                                  </MenuItem>
                                ) : (
                                  <MenuItem
                                    danger
                                    icon={<LockIcon className="h-4 w-4" />}
                                    onClick={() => { close(); setLockTarget(user); }}
                                  >
                                    {t("Khoá")}
                                  </MenuItem>
                                ))}
                                {!self && <div className="my-1 border-t border-slate-100" />}
                                <MenuItem
                                  icon={<span className="inline-block w-4" />}
                                  onClick={() => { close(); handleToggleAdmin(user.id, user.is_admin); }}
                                >
                                  {user.is_admin ? t("Gỡ Admin") : t("Cấp Admin")}
                                </MenuItem>
                              </>
                            )}
                          </RowMenu>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <LockUserModal
        username={lockTarget?.username || null}
        open={!!lockTarget}
        onClose={() => setLockTarget(null)}
        onConfirm={(payload) => (lockTarget ? doLock(lockTarget.id, payload) : undefined)}
      />
      <RecoveryModal
        user={recoveryTarget}
        onClose={() => setRecoveryTarget(null)}
        onConfirm={(payload) => (recoveryTarget ? doRecovery(recoveryTarget, payload) : undefined)}
      />
    </div>
  );
}
