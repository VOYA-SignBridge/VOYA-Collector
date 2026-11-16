import { useCallback, useEffect, useState } from "react";
import {
  fetchSessions,
  revokeOtherSessions,
  revokeSession,
  type DeviceSession,
} from "../../api/auth";
import { useToast } from "../../hooks/useToast";
import { useI18n } from "../../i18n";
import { friendlyError } from "../../lib/errors";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import { SmartphoneIcon } from "../ui/Icons";
import LoadingSpinner from "../ui/LoadingSpinner";
import Modal from "../ui/Modal";

/** Ngày giờ theo ngôn ngữ đang dùng; chuỗi rỗng khi không đọc được. */
export function formatWhen(value: string | null | undefined, locale: string): string {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Thiết bị đang đăng nhập: xem từng thiết bị và đăng xuất từng cái.
 *
 * Trả lời câu "có ai khác đang dùng tài khoản của tôi không". Thiết bị ĐANG DÙNG
 * không có nút đăng xuất ở đây (đã có nút Đăng xuất chính thức) — đá chính mình ra
 * khỏi trang đang mở là thao tác dễ nhầm.
 */
export default function DevicesSection() {
  const { t, lang } = useI18n();
  const { toast } = useToast();
  const [sessions, setSessions] = useState<DeviceSession[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);

  const load = useCallback(async () => {
    try {
      setSessions(await fetchSessions());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const logoutOne = async (id: string) => {
    setBusy(id);
    try {
      await revokeSession(id);
      toast.success(t("Đã đăng xuất thiết bị đó."));
      await load();
    } catch (err) {
      toast.error(friendlyError(err, t("Không đăng xuất được thiết bị.")));
    } finally {
      setBusy(null);
    }
  };

  const logoutOthers = async () => {
    setBusy("all");
    try {
      const n = await revokeOtherSessions();
      toast.success(t("Đã đăng xuất {n} thiết bị khác.", { n }));
      setConfirmAll(false);
      await load();
    } catch (err) {
      toast.error(friendlyError(err, t("Không đăng xuất được các thiết bị khác.")));
    } finally {
      setBusy(null);
    }
  };

  const others = (sessions ?? []).filter((s) => !s.current);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{t("Thiết bị đang đăng nhập")}</h3>
          <p className="mt-1 text-sm text-slate-600">
            {t("Nếu thấy thiết bị lạ, hãy đăng xuất nó rồi đổi mật khẩu.")}
          </p>
        </div>
        {others.length > 0 && (
          <Button variant="secondary" size="sm" onClick={() => setConfirmAll(true)} disabled={busy !== null}>
            {t("Đăng xuất mọi thiết bị khác")}
          </Button>
        )}
      </div>

      {sessions === null && !failed && (
        <div className="mt-4"><LoadingSpinner size="sm" label={t("Đang tải…")} /></div>
      )}
      {failed && (
        <p role="alert" className="mt-4 text-sm text-red-700">
          {t("Không tải được danh sách thiết bị.")}{" "}
          <button type="button" onClick={() => void load()} className="font-semibold underline">
            {t("Thử lại")}
          </button>
        </p>
      )}

      {sessions && (
        <ul className="mt-4 divide-y divide-slate-100">
          {sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-3 py-3">
              <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                <SmartphoneIcon className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                  {s.device}
                  {s.current && <Badge variant="success" size="sm">{t("Thiết bị này")}</Badge>}
                  {s.remembered && <Badge variant="neutral" size="sm" icon={false}>{t("Đã ghi nhớ")}</Badge>}
                </p>
                <p className="text-xs text-slate-500">
                  {t("Dùng lần cuối {when}", { when: formatWhen(s.last_active, lang) })}
                  {" · "}
                  {t("Đăng nhập từ {when}", { when: formatWhen(s.started_at, lang) })}
                </p>
              </div>
              {!s.current && (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busy === s.id}
                  disabled={busy !== null}
                  onClick={() => void logoutOne(s.id)}
                >
                  {t("Đăng xuất")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <Modal isOpen={confirmAll} onClose={() => setConfirmAll(false)} title={t("Đăng xuất mọi thiết bị khác?")} size="sm">
        <p className="text-sm text-slate-600">
          {t("{n} thiết bị khác sẽ bị đăng xuất ngay. Thiết bị bạn đang dùng được giữ nguyên.", { n: others.length })}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmAll(false)} disabled={busy !== null}>
            {t("Huỷ")}
          </Button>
          <Button variant="primary" loading={busy === "all"} onClick={() => void logoutOthers()}>
            {t("Đăng xuất")}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
