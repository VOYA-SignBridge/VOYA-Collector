import { type FormEvent, useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, UserIcon } from "../components/auth/AuthInput";
import OtpCodeInput from "../components/auth/OtpCodeInput";
import {
  resetPasswordWithTicket,
  startRecovery,
  verifyRecoveryCode,
  type OtpChannel,
} from "../api/verification";
import { friendlyError } from "../lib/errors";
import { secondsFromRetryError, useResendCountdown } from "../hooks/useResendCountdown";
import { InfoCircleIcon, MailIcon, SmartphoneIcon } from "../components/ui/Icons";
import { Trans, useI18n } from "../i18n";

/**
 * Quên mật khẩu — MỘT cửa duy nhất, ba bước.
 *
 * Vì sao chỉ còn một cửa
 * -----------------------
 * Trước đây màn hình đăng nhập có hai đường: "Quên mật khẩu?" gửi một đường
 * liên kết, "Khôi phục bằng mã" gửi một mã. Đứng ở góc người vừa quên mật khẩu,
 * hai đường ấy trả lời **cùng một câu hỏi** bằng hai cách, và họ không có cơ sở
 * nào để chọn — sự khác biệt (liên kết chết khi mở thư trên máy khác) là chi
 * tiết của bên triển khai, không phải một lựa chọn để hỏi người dùng.
 *
 * Nên: một đường vào, và nó là đường mã — mã đi được qua cả thư lẫn tin nhắn,
 * và không phụ thuộc vào việc mở thư trên đúng thiết bị đang đăng nhập.
 *
 * Ba bước, không phải một biểu mẫu
 * ---------------------------------
 * Bản trước hỏi tên đăng nhập, mã, mật khẩu mới và xác nhận mật khẩu **cùng một
 * lúc**, rồi gửi tất cả trong một request. Hệ quả: gõ nhầm một chữ số của mã
 * thì cái mất là cả một mật khẩu vừa nghĩ ra. Giờ mã được trả lời ngay ở bước
 * hai, và bước ba chỉ hỏi mật khẩu.
 *
 * Nó cũng đóng lại nút "Tôi đã có mã rồi" của bản trước — một lối tắt cho một
 * tình huống không tồn tại: mã chỉ ra đời khi ai đó bấm xin. Người chưa thấy mã
 * cần nút **Gửi lại**, chứ không cần một cửa riêng để tự khai là mình có mã.
 *
 * Điều dễ làm sai nhất ở màn hình này
 * ------------------------------------
 * Máy chủ trả **cùng một câu** cho mọi kết cục của bước một: gửi được, tài
 * khoản không tồn tại, gửi thất bại, hay đang trong thời gian chờ. Đó là chủ ý
 * — khác nhau thì đây thành công cụ dò xem ai có tài khoản, và danh sách tài
 * khoản của một chương trình giáo dục đặc biệt đúng là thứ không được rò.
 *
 * Nên màn hình này **không được** vẽ dấu tích xanh, không được nói "đã gửi mã
 * tới bạn". Nó nói "nếu tài khoản tồn tại" — vì người vừa gõ nhầm địa chỉ sẽ
 * không nhận được gì, và họ cần biết điều đó là có thể.
 *
 * @i18n-key-table — `STEP_TITLE` và nhãn kênh nhận mã là KHOÁ từ điển.
 */

type Step = "identify" | "code" | "password";

const STEP_TITLE: Record<Step, string> = {
  identify: "Quên mật khẩu",
  code: "Nhập mã xác minh",
  password: "Đặt mật khẩu mới",
};

const STEP_INDEX: Record<Step, number> = { identify: 1, code: 2, password: 3 };

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("identify");
  const [identifier, setIdentifier] = useState("");
  const [channel, setChannel] = useState<OtpChannel>("email");
  const [code, setCode] = useState("");
  const [ticket, setTicket] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const { secondsLeft, startFrom, clear: clearCountdown } = useResendCountdown();

  const passwordError =
    password.length > 0 && password.length < 8 ? t("Mật khẩu phải có ít nhất 8 ký tự.") : "";
  const confirmError =
    confirmPassword.length > 0 && confirmPassword !== password
      ? t("Mật khẩu xác nhận không khớp.")
      : "";
  const canSavePassword =
    password.length >= 8 && password === confirmPassword && !busy;

  /** Bước 1 → 2, và cũng là nút "Gửi lại mã" ở bước 2. */
  const requestCode = useCallback(async () => {
    if (!identifier.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await startRecovery(identifier, channel);
      setNotice(res.message);
      setCode("");
      setStep("code");
      // Thời gian chờ do máy chủ đặt (mặc định 60 giây). Bắt đầu đếm ngay cả
      // khi ta không biết chắc thư có đi hay không — vì ta KHÔNG được biết.
      startFrom(60);
    } catch (err) {
      // Chỉ tới đây khi mạng hỏng hoặc bị chặn tần suất. Đường "tài khoản
      // không tồn tại" trả 200 kèm câu chung, không ném ra ngoài.
      setError(friendlyError(err, t("Không gửi được yêu cầu. Vui lòng thử lại.")));
      const wait = secondsFromRetryError(err);
      if (wait) {
        // 429 kèm số giây nghĩa là một mã VẪN CÒN SỐNG — người này đã xin cách
        // đây chưa lâu, có thể ở một tab khác. Đưa họ sang ô nhập mã thay vì
        // giữ ở bước một, nơi việc duy nhất làm được là bấm lại đúng cái nút
        // vừa bị từ chối.
        setStep("code");
        startFrom(wait);
      }
    } finally {
      setBusy(false);
    }
  }, [identifier, channel, busy, startFrom]);

  /** Bước 2 → 3. Mã bị tiêu ở đây; đổi lại ta cầm một vé sống 5 phút. */
  const submitCode = async (e: FormEvent) => {
    e.preventDefault();
    if (code.length !== 6 || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await verifyRecoveryCode(identifier, code);
      setTicket(res.reset_ticket);
      setError("");
      setStep("password");
    } catch (err) {
      // Một mã sai và một tài khoản không tồn tại cho ra cùng lời từ chối.
      // Đừng đoán nửa nào hỏng — máy chủ cố tình không nói.
      setError(friendlyError(err, t("Mã xác minh không đúng hoặc đã hết hạn.")));
      // Giữ lại mã sai trên màn hình là mời người dùng bấm gửi lần nữa với đúng
      // chuỗi vừa hỏng — mà mỗi lần như vậy tiêu một trong năm lượt thử.
      setCode("");
      const status = (err as { response?: { status?: number } })?.response?.status;
      // 429 ở đây nghĩa là thử thách đã chết vì nhập sai quá số lần. Đợi hết
      // đồng hồ rồi mới cho xin mã mới là bắt họ chờ một thứ không còn tồn tại.
      if (status === 429) clearCountdown();
    } finally {
      setBusy(false);
    }
  };

  /** Bước 3. Vé đổi lấy mật khẩu mới. */
  const submitPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSavePassword) return;
    setBusy(true);
    setError("");
    try {
      await resetPasswordWithTicket(ticket, password);
      setDone(true);
    } catch (err) {
      setError(friendlyError(err, t("Không đặt lại được mật khẩu. Vui lòng thử lại.")));
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 400) {
        // Vé hết hạn. Mã đã tiêu rồi nên quay về bước 2 là ngõ cụt — phải xin
        // mã mới. Giữ nguyên tên đăng nhập để họ chỉ cần bấm một lần.
        setTicket("");
        setStep("identify");
        setPassword("");
        setConfirmPassword("");
        clearCountdown();
      }
    } finally {
      setBusy(false);
    }
  };

  const footer = (
    <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{t("Nhớ ra mật khẩu rồi?")}</span>
      <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
        {t("Quay lại đăng nhập →")}
      </Link>
    </div>
  );

  if (done) {
    return (
      <AuthShell title={t("Đã đặt lại mật khẩu")} footer={footer}>
        <div className="space-y-4">
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-relaxed text-sky-800">
            {t("Mật khẩu đã được đặt lại. Mọi phiên đăng nhập cũ trên các thiết bị khác đã bị thu hồi, kể cả phiên của người có thể đã chiếm được tài khoản.")}
          </div>
          <button
            type="button"
            onClick={() => navigate("/login", { replace: true })}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy"
          >
            {t("Đăng nhập lại")}
          </button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={t(STEP_TITLE[step])} footer={footer}>
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
        {t("Bước {n} / 3", { n: STEP_INDEX[step] })}
      </p>

      {step === "identify" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void requestCode();
          }}
          className="space-y-4"
        >
          <p className="text-sm leading-relaxed text-slate-600">
            {t("Nhập tên đăng nhập hoặc email của tài khoản. Chúng tôi sẽ gửi một mã gồm sáu chữ số để bạn tự đặt lại mật khẩu.")}
          </p>

          <AuthInput
            label={t("Tên đăng nhập hoặc email")}
            icon={<UserIcon />}
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            type="text"
            autoComplete="username"
            placeholder={t("vd: minh123 hoặc minh@example.com")}
          />

          <ChannelPicker value={channel} onChange={setChannel} />

          {error ? <ErrorBox message={error} /> : null}

          <button
            type="submit"
            disabled={!identifier.trim() || busy}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? t("Đang gửi mã…") : t("Tiếp tục")}
          </button>
        </form>
      ) : step === "code" ? (
        <form onSubmit={submitCode} className="space-y-4">
          {notice ? (
            <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-slate-700">
              <InfoCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
              <span>{notice}</span>
            </div>
          ) : null}

          {/* Tên đăng nhập ở đây là NGỮ CẢNH, không phải một ô để điền lại. Bản
              trước dựng lại nguyên ô nhập ở bước hai, nên người dùng thấy mình
              vừa gõ xong đã bị hỏi lại đúng câu đó. Sửa được thì phải quay lại
              bước một, vì đổi tên đăng nhập giữa chừng làm mã vừa gửi vô nghĩa. */}
          <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-2.5 text-sm">
            <span className="truncate font-medium text-slate-700">{identifier}</span>
            <button
              type="button"
              onClick={() => {
                setStep("identify");
                setCode("");
                setError("");
                setNotice("");
                clearCountdown();
              }}
              className="shrink-0 font-semibold text-ctu-blue hover:text-ctu-navy"
            >
              {t("Đổi")}
            </button>
          </div>

          <OtpCodeInput
            value={code}
            // Xoá lời từ chối ngay khi họ bắt đầu gõ lại. Để nguyên thì màn
            // hình vừa hiện "mã không đúng" vừa hiện chuỗi mới đang gõ, và
            // người dùng không biết câu đó nói về chuỗi nào.
            onChange={(next) => {
              setCode(next);
              if (error) setError("");
            }}
            autoFocus
            disabled={busy}
            error={error}
            hint={t("Mã có hiệu lực trong ít phút. Nhập sai quá năm lần thì phải xin mã mới.")}
          />

          <button
            type="submit"
            disabled={code.length !== 6 || busy}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? t("Đang kiểm tra…") : t("Xác nhận")}
          </button>

          <button
            type="button"
            disabled={secondsLeft > 0 || busy}
            onClick={() => void requestCode()}
            className="w-full rounded-xl px-5 py-2.5 text-sm font-semibold text-ctu-blue transition hover:bg-ctu-blue/10 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
          >
            {secondsLeft > 0
              ? t("Chưa nhận được mã? Gửi lại sau {giay} giây", { giay: secondsLeft })
              : t("Gửi lại mã")}
          </button>
        </form>
      ) : (
        <form onSubmit={submitPassword} className="space-y-4">
          <p className="text-sm leading-relaxed text-slate-600">
            <Trans
              k="Mã đã được xác nhận. Đặt mật khẩu mới cho tài khoản {taikhoan}."
              vars={{ taikhoan: <span className="font-semibold text-slate-800">{identifier}</span> }}
            />
          </p>

          <AuthInput
            label={t("Mật khẩu mới")}
            icon={<LockIcon />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder={t("Tối thiểu 8 ký tự")}
            error={passwordError}
          />

          <AuthInput
            label={t("Xác nhận mật khẩu mới")}
            icon={<LockIcon />}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder={t("Nhập lại mật khẩu mới")}
            error={confirmError}
            trailing={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="rounded-lg px-3 py-1.5 text-xs font-semibold text-ctu-blue hover:bg-ctu-blue/10"
              >
                {showPassword ? t("Ẩn") : t("Hiện")}
              </button>
            }
          />

          {error ? <ErrorBox message={error} /> : null}

          <button
            type="submit"
            disabled={!canSavePassword}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? t("Đang lưu…") : t("Lưu mật khẩu mới")}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {message}
    </div>
  );
}

/**
 * Chọn kênh nhận mã.
 *
 * SMS luôn hiện, kể cả khi bản triển khai chưa cấu hình nhà cung cấp nào. Ở
 * luồng khôi phục ta KHÔNG hỏi máy chủ xem SMS có sẵn không — câu hỏi đó trả
 * lời được mà không cần đăng nhập, và nó lộ cấu hình hệ thống. Máy chủ tự âm
 * thầm chuyển về email khi không gửi SMS được, và vì mọi phản hồi đều giống
 * nhau nên người dùng không nhận ra sự khác biệt.
 */
function ChannelPicker({
  value,
  onChange,
}: {
  value: OtpChannel;
  onChange: (next: OtpChannel) => void;
}) {
  const { t } = useI18n();
  const options: { key: OtpChannel; label: string; Icon: typeof MailIcon }[] = [
    { key: "email", label: "Qua email", Icon: MailIcon },
    { key: "sms", label: "Qua tin nhắn", Icon: SmartphoneIcon },
  ];
  return (
    <fieldset>
      <legend className="mb-1.5 block text-sm font-medium text-slate-700">{t("Nhận mã bằng")}</legend>
      <div className="grid grid-cols-2 gap-2">
        {options.map(({ key, label, Icon }) => {
          const active = value === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onChange(key)}
              aria-pressed={active}
              className={`flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${
                active
                  ? "border-ctu-blue bg-ctu-blue/10 text-ctu-blue"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {t(label)}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
