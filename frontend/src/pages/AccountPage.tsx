/**
 * Tài khoản của tôi — `/settings/account`.
 *
 * Trang này để SỬA THÔNG TIN, không phải để đọc lại điều khoản
 * ------------------------------------------------------------
 * Bản trước gộp ba thứ: danh sách đồng thuận pháp lý, xác thực hai bước, và ô
 * đổi tên đăng nhập — dưới một tiêu đề nói rằng đây là nơi "xem lại những gì
 * bạn đã đồng ý ... và đổi tên đăng nhập". Ba việc, ba nhịp, ba lý do tìm đến
 * hoàn toàn khác nhau.
 *
 * Hậu quả cụ thể chứ không chỉ là lộn xộn: người vào để sửa một chữ trong tên
 * mình phải cuộn qua bốn thẻ văn bản pháp lý; người đi tìm "tôi đã ký cái gì"
 * không đoán được rằng nó nằm dưới chữ "Tài khoản"; và người nghi tài khoản có
 * vấn đề đi tìm chữ "Bảo mật" chứ không phải "Tài khoản".
 *
 * Nên từ 16/08/2026:
 *
 *     /settings/account    hồ sơ — tên đăng nhập, email
 *     /settings/consents   đồng thuận pháp lý
 *     /settings/security   2FA, đổi mật khẩu, xác minh liên hệ
 *
 * Vì sao lời nhắc "chưa xác minh" nằm ở ĐÂY mà việc xác minh thì ở kia
 * --------------------------------------------------------------------
 * Trang hồ sơ là nơi người dùng nhìn thấy địa chỉ email của mình. Đó cũng là
 * nơi họ nhận ra nó sai — một địa chỉ sai chỉ lộ ra khi có ai đó đọc nó. Nhưng
 * việc xác minh là thao tác bảo mật, nên nó sống ở trang Bảo mật. Lời nhắc ở
 * đây là cây cầu: nói ra vấn đề tại nơi nó được phát hiện, và chỉ đường tới nơi
 * giải quyết được.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import PageHeader from "../components/ui/PageHeader";
import Button from "../components/ui/Button";
import { AlertTriangleIcon, ShieldCheckIcon } from "../components/ui/Icons";
import { useAuth } from "../contexts/AuthContext";
import { notifyAuthChange } from "../api/axiosClient";
import { useToast } from "../hooks/useToast";
import { friendlyError } from "../lib/errors";
import { confirmEmailChange, startEmailChange, updateUsername } from "../api/auth";
import { fetchVerificationStatus, type VerificationStatus } from "../api/verification";
import { useI18n } from "../i18n";

export default function AccountPage() {
  const { t } = useI18n();
  return (
    <div className="space-y-8">
      <PageHeader
        title={t("Tài khoản của tôi")}
        subtitle={t("Sửa tên đăng nhập và địa chỉ liên hệ của bạn.")}
        breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Tài khoản") }]}
      />
      <VerificationHint />
      <UsernameSection />
      <EmailSection />
    </div>
  );
}

// ---------------------------------------------------------- nhắc xác minh

/**
 * Lời nhắc "còn thứ chưa xác minh", và KHÔNG hiện gì khi mọi thứ đã xong.
 *
 * Một tấm thẻ xanh ghi "tất cả đã xác minh" nghe thì tử tế, nhưng nó chiếm chỗ
 * vĩnh viễn ở đầu trang để nói một điều không đòi hỏi hành động nào. Thứ đáng
 * chiếm chỗ là việc còn phải làm.
 */
function VerificationHint() {
  const { t } = useI18n();
  const [status, setStatus] = useState<VerificationStatus | null>(null);

  useEffect(() => {
    // Hỏng thì im lặng: đây là lời nhắc phụ, và một biểu ngữ lỗi đỏ vì không
    // đọc được trạng thái xác minh sẽ che mất việc người dùng đang làm.
    fetchVerificationStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return null;
  const missing: string[] = [];
  if (!status.email_verified) missing.push(t("địa chỉ email"));
  if (status.phone_number && !status.phone_verified) missing.push(t("số điện thoại"));
  if (missing.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <ShieldCheckIcon className="h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        {t(
          "Bạn còn {what} chưa xác minh. Chưa xác minh thì không lấy lại được tài khoản khi quên mật khẩu.",
          { what: missing.join(t(" và ")) },
        )}
      </span>
      <Link
        to="/settings/security"
        className="shrink-0 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-amber-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
      >
        {t("Xác minh ngay")}
      </Link>
    </div>
  );
}

// ------------------------------------------------------------ tên đăng nhập

function UsernameSection() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<Record<string, number> | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    setValue(user?.username ?? "");
  }, [user?.username]);

  const trimmed = value.trim();
  const canSave =
    !busy && trimmed.length >= 3 && trimmed !== (user?.username ?? "");

  const save = useCallback(async () => {
    if (!canSave) return;
    setBusy(true);
    setError("");
    setRows(null);
    try {
      const result = await updateUsername(trimmed);
      // `changed: false` nghĩa là tên mới trùng tên cũ — không phải lỗi, nhưng
      // cũng không có gì để khoe. Nói đúng chuyện đã xảy ra.
      if (!result.changed) {
        toast.success(t("Tên không thay đổi."));
        return;
      }
      setRows(result.rows);
      toast.success(t("Đã đổi tên thành {new_username}.", { new_username: result.new_username }));
      // Thanh bên và chữ ký đầu trang đang giữ tên cũ. `AuthProvider` chỉ nạp
      // lại /auth/me khi có sự kiện này — không phát thì người dùng thấy tên cũ
      // cho tới lần tải trang sau, và tưởng việc đổi tên thất bại.
      notifyAuthChange();
    } catch (err) {
      setError(friendlyError(err, t("Không đổi được tên tài khoản.")));
    } finally {
      setBusy(false);
    }
  }, [canSave, trimmed, toast, t]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold text-slate-900">{t("Tên đăng nhập")}</h2>
      <p className="mt-1 text-sm text-slate-600">
        {t("Tên này được chép vào từng mẫu bạn đã đóng góp ngay lúc ghi. Đổi tên ở đây sẽ cập nhật cả những bản sao đó, nên các mẫu cũ của bạn không mang tên cũ nữa.")}
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            {t("Tên đăng nhập")}
          </span>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            minLength={3}
            maxLength={100}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
          />
        </label>
        <Button loading={busy} disabled={!canSave} onClick={() => void save()}>
          {t("Lưu tên mới")}
        </Button>
      </div>

      {trimmed.length > 0 && trimmed.length < 3 && (
        <p className="mt-2 text-xs text-amber-700">{t("Tên phải dài ít nhất 3 ký tự.")}</p>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* Số hàng đã đổi, hiện ra chứ không giấu: đổi tên chạm vào dữ liệu đã
          đóng góp, và người bấm nút xứng đáng thấy việc gì đã thật sự xảy ra
          thay vì tin lời. */}
      {rows && Object.keys(rows).length > 0 && (
        <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
          <p className="font-semibold">{t("Đã cập nhật tên ở những chỗ sau")}</p>
          <ul className="mt-1 space-y-0.5">
            {Object.entries(rows).map(([place, count]) => (
              <li key={place} className="font-mono text-xs">
                {place}: {count}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-sky-800">
            {t("Nhật ký kiểm toán giữ nguyên tên cũ — đó là bằng chứng lịch sử về việc ai đã làm gì, và sửa nó theo tên mới là viết lại lịch sử.")}
          </p>
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------- email

/**
 * Đổi email — hai bước, và mã đi tới ĐỊA CHỈ MỚI.
 *
 * Không phải một ô `<input>` bấm Lưu là xong. Email là khoá khôi phục tài
 * khoản: nếu đổi được nó chỉ bằng một phiên đang mở, thì một máy bỏ quên ở quán
 * cà phê đủ để mất tài khoản vĩnh viễn — kẻ chiếm được chỉ cần trỏ địa chỉ sang
 * hộp thư của mình rồi bấm "quên mật khẩu".
 *
 * Nên mật khẩu hỏi ở cả hai bước, và mã sáu chữ số phải tới được hộp thư MỚI.
 * Một địa chỉ gõ nhầm sẽ đơn giản là không nhận được mã, và việc đổi không xảy
 * ra — hướng hỏng đúng chiều.
 */
function EmailSection() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();

  const [step, setStep] = useState<"idle" | "code">("idle");
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setStep("idle");
    setNewEmail("");
    setPassword("");
    setCode("");
    setError("");
  };

  const start = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const out = await startEmailChange({
        currentPassword: password,
        newEmail: newEmail.trim(),
      });
      setStep("code");
      toast.success(t("Đã gửi mã tới {email}.", { email: out.sent_to }));
    } catch (err) {
      setError(friendlyError(err, t("Không gửi được mã tới địa chỉ mới.")));
    } finally {
      setBusy(false);
    }
  }, [password, newEmail, toast, t]);

  const confirm = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const out = await confirmEmailChange({ currentPassword: password, code: code.trim() });
      toast.success(t("Đã đổi email thành {email}.", { email: out.email }));
      reset();
      // Header và trang hồ sơ đang giữ địa chỉ cũ. Không phát sự kiện thì người
      // dùng thấy địa chỉ cũ cho tới lần tải trang sau và tưởng việc đổi hỏng.
      notifyAuthChange();
    } catch (err) {
      setError(friendlyError(err, t("Mã không đúng hoặc đã hết hạn.")));
    } finally {
      setBusy(false);
    }
  }, [password, code, toast, t]);

  const emailLooksValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(newEmail.trim());

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold text-slate-900">{t("Địa chỉ email")}</h2>
      <p className="mt-1 text-sm text-slate-600">
        {t("Đây là địa chỉ nhận mã khôi phục khi bạn quên mật khẩu. Mã xác nhận sẽ được gửi tới địa chỉ MỚI, nên hãy chắc bạn đọc được hộp thư đó.")}
      </p>

      <p className="mt-3 text-sm">
        <span className="text-slate-500">{t("Đang dùng")}: </span>
        <span className="font-medium text-slate-900">{user?.email ?? ""}</span>
      </p>

      {step === "idle" ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="min-w-0">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              {t("Địa chỉ email mới")}
            </span>
            <input
              type="email"
              value={newEmail}
              autoComplete="email"
              onChange={(e) => setNewEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
            />
          </label>
          <label className="min-w-0">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              {t("Mật khẩu hiện tại")}
            </span>
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
            />
          </label>
          <div className="sm:col-span-2">
            <Button
              loading={busy}
              disabled={busy || !emailLooksValid || password.length < 1}
              onClick={() => void start()}
            >
              {t("Gửi mã tới địa chỉ mới")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="min-w-0">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              {t("Mã 6 chữ số vừa gửi")}
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={10}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 font-mono text-sm tracking-widest focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
            />
          </label>
          <div className="flex items-end gap-2 sm:col-span-2">
            <Button
              loading={busy}
              disabled={busy || code.trim().length < 4}
              onClick={() => void confirm()}
            >
              {t("Xác nhận đổi email")}
            </Button>
            <button
              type="button"
              onClick={reset}
              className="text-sm font-medium text-slate-500 hover:text-slate-700"
            >
              {t("Huỷ")}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}
