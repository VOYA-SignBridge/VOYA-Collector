import { useCallback, useEffect, useRef, useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import Badge from "../components/ui/Badge";
import OtpCodeInput from "../components/auth/OtpCodeInput";
import {
  confirmVerificationCode,
  fetchVerificationStatus,
  sendVerificationCode,
  type OtpChannel,
  type VerificationStatus,
} from "../api/verification";
import { friendlyError } from "../lib/errors";
import { secondsFromRetryError, useResendCountdown } from "../hooks/useResendCountdown";
import { toneClasses, FOCUS_RING } from "../theme/status";
import {
  AlertTriangleIcon,
  InfoCircleIcon,
  MailIcon,
  SmartphoneIcon,
} from "../components/ui/Icons";
import { useToast } from "../hooks/useToast";
import { useI18n } from "../i18n";

/**
 * Xác minh email và số điện thoại của chính mình.
 *
 * Hai lớp chặn cho cùng một bẫy, và chúng không thừa nhau
 * --------------------------------------------------------
 * Máy chủ cho phép một thử thách còn sống cho mỗi cặp (tài khoản, mục đích),
 * nên một mã email và một mã SMS sống song song được. Nếu lời gọi xác nhận
 * không nói nó trả lời cho cái nào, máy chủ phải dò — và mỗi lần dò trượt đều
 * trừ lượt của thử thách nó chạm vào. Năm lần như vậy là thử thách điện thoại
 * chết vì "nhập sai quá số lần" dù người dùng chưa gõ sai chữ nào.
 *
 * Lớp thứ nhất: trang này giữ đúng MỘT `pending`; mở luồng kia sẽ đóng luồng
 * này lại. Lớp thứ hai: mỗi lần xác nhận đều gửi kèm `purpose`.
 *
 * Lớp thứ hai không thay được lớp thứ nhất. Hai ô nhập mã cùng mở là một màn
 * hình khó dùng, chứ không chỉ là một vấn đề về hạn mức lượt thử. Nhưng lớp
 * thứ nhất cũng không thay được lớp thứ hai: nó chỉ bảo vệ được người dùng đi
 * qua **trang này**.
 */

type Pending = { channel: OtpChannel; destination: string } | null;

export default function VerifyContactPage() {
  const { t } = useI18n();
  const [status, setStatus] = useState<VerificationStatus | null>(null);
  const [loadError, setLoadError] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { secondsLeft, startFrom, clear } = useResendCountdown();
  const { toast } = useToast();

  // Bộ đếm lượt tải: một lần nạp lại chậm không được ghi đè lên kết quả mới
  // hơn. Xem AdminTenantsPage — cùng cái bẫy.
  const run = useRef(0);

  const load = useCallback(async () => {
    const mine = ++run.current;
    try {
      const data = await fetchVerificationStatus();
      if (mine !== run.current) return;
      setStatus(data);
      setPhone((prev) => prev || data.phone_number);
      setLoadError("");
    } catch (err) {
      if (mine !== run.current) return;
      setLoadError(friendlyError(err, "Không đọc được trạng thái xác minh của tài khoản."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const send = useCallback(
    async (channel: OtpChannel, destination?: string) => {
      if (busy) return;
      setBusy(true);
      setError("");
      setCode("");
      try {
        await sendVerificationCode(channel, destination);
        setPending({ channel, destination: destination || status?.email || "" });
        startFrom(status?.resend_cooldown_seconds ?? 60);
      } catch (err) {
        setError(friendlyError(err, "Không gửi được mã. Vui lòng thử lại."));
        const wait = secondsFromRetryError(err);
        if (wait) {
          // Máy chủ nói còn phải đợi, nghĩa là mã CŨ vẫn sống. Mở ô nhập ra
          // thay vì để người dùng đứng trước một nút không bấm được và một mã
          // đang nằm trong hộp thư.
          setPending({ channel, destination: destination || status?.email || "" });
          startFrom(wait);
        }
      } finally {
        setBusy(false);
      }
    },
    [status, startFrom, busy],
  );

  const confirm = useCallback(async () => {
    if (code.length !== 6 || busy || !pending) return;
    setBusy(true);
    setError("");
    try {
      // Nói thẳng mã này trả lời cho thử thách nào. Không có nó, máy chủ dò
      // `verify_phone` trước — và một mã email gõ nhầm sẽ trừ lượt của thử
      // thách điện thoại mà người dùng không hề đụng tới.
      const res = await confirmVerificationCode(
        code,
        pending.channel === "sms" ? "verify_phone" : "verify_email",
      );
      toast.success(
        res.channel === "sms" ? t("Đã xác minh số điện thoại.") : t("Đã xác minh email."),
      );
      setPending(null);
      setCode("");
      clear();
      await load();
    } catch (err) {
      setError(friendlyError(err, "Mã xác minh không đúng hoặc đã hết hạn."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }, [code, busy, pending, toast, clear, load]);

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        <PageHeader
          title={t("Xác minh liên hệ")}
          subtitle={t("Chứng minh bạn đang giữ email và số điện thoại gắn với tài khoản. Địa chỉ đã xác minh là đường khôi phục khi bạn quên mật khẩu.")}
          breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Xác minh liên hệ") }]}
        />

        {loadError ? (
          <div
            role="alert"
            className={`mb-5 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${toneClasses("danger", "soft")}`}
          >
            <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{loadError}</span>
          </div>
        ) : null}

        {!status ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            {t("Đang tải trạng thái tài khoản…")}
          </div>
        ) : (
          <div className="space-y-5">
            {/* Lỗi khi GỬI mã. Chỉ hiện lúc chưa có luồng nào mở — khi đã mở,
                `OtpCodeInput` nhận cùng chuỗi này và đặt nó ngay dưới ô nhập,
                nên vẽ ở cả hai chỗ là nói hai lần một chuyện.

                Không có khối này thì một lượt gửi hỏng KHÔNG hiện gì cả: nút
                bật lại như cũ và người dùng ngồi đợi một mã không tồn tại. */}
            {error && !pending ? (
              <div
                role="alert"
                className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${toneClasses("danger", "soft")}`}
              >
                <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{error}</span>
              </div>
            ) : null}

            {/* ------------------------------------------------------ email */}
            <ContactCard
              Icon={MailIcon}
              title={t("Địa chỉ email")}
              value={status.email || t("(chưa có)")}
              verified={status.email_verified}
              open={pending?.channel === "email"}
            >
              {pending?.channel === "email" ? (
                <CodeStep
                  code={code}
                  setCode={setCode}
                  busy={busy}
                  error={error}
                  ttlMinutes={status.code_ttl_minutes}
                  secondsLeft={secondsLeft}
                  destination={status.email}
                  onConfirm={confirm}
                  onResend={() => void send("email")}
                  onCancel={() => {
                    setPending(null);
                    setCode("");
                    setError("");
                  }}
                />
              ) : (
                <button
                  type="button"
                  disabled={busy || !status.email}
                  onClick={() => void send("email")}
                  className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${toneClasses("success", status.email_verified ? "outline" : "solid")} ${FOCUS_RING}`}
                >
                  {status.email_verified ? t("Xác minh lại") : t("Gửi mã tới email này")}
                </button>
              )}
            </ContactCard>

            {/* --------------------------------------------------- điện thoại */}
            <ContactCard
              Icon={SmartphoneIcon}
              title={t("Số điện thoại")}
              value={status.phone_number || t("(chưa có)")}
              verified={status.phone_verified}
              open={pending?.channel === "sms"}
            >
              {!status.sms_available ? (
                // Trạng thái BÌNH THƯỜNG của bản triển khai này, không phải sự
                // cố. Nói thẳng thay vì để người dùng bấm gửi rồi nhận lỗi 503
                // — lượt bấm hỏng đó còn đốt luôn thời gian chờ.
                <div
                  className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${toneClasses("neutral", "soft")}`}
                >
                  <InfoCircleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    {t("Hệ thống chưa bật kênh tin nhắn. Bạn vẫn khôi phục tài khoản được bằng email đã xác minh.")}
                  </span>
                </div>
              ) : pending?.channel === "sms" ? (
                <CodeStep
                  code={code}
                  setCode={setCode}
                  busy={busy}
                  error={error}
                  ttlMinutes={status.code_ttl_minutes}
                  secondsLeft={secondsLeft}
                  destination={pending.destination}
                  onConfirm={confirm}
                  onResend={() => void send("sms", phone)}
                  onCancel={() => {
                    setPending(null);
                    setCode("");
                    setError("");
                  }}
                />
              ) : (
                <div className="flex flex-col gap-2 sm:flex-row">
                  <label className="flex-1">
                    <span className="sr-only">{t("Số điện thoại nhận mã")}</span>
                    <input
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      type="tel"
                      inputMode="tel"
                      autoComplete="tel"
                      // Máy chủ đòi dạng E.164 (`+84…`). Nói trước ở đây thay vì
                      // để nó bị từ chối sau một lượt gửi.
                      placeholder="+84901234567"
                      className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition focus:border-ctu-blue focus:ring-4 focus:ring-ctu-blue/15"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy || !/^\+[1-9]\d{7,14}$/.test(phone.replace(/\s/g, ""))}
                    onClick={() => void send("sms", phone.replace(/\s/g, ""))}
                    className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${toneClasses("success", "solid")} ${FOCUS_RING}`}
                  >
                    {t("Gửi mã qua tin nhắn")}
                  </button>
                </div>
              )}
            </ContactCard>

            <p className="text-xs leading-relaxed text-slate-500">
              {t("Số bắt đầu bằng dấu cộng và mã quốc gia, ví dụ")} <code>+84901234567</code>. Mã có
              hiệu lực {status.code_ttl_minutes} phút và nhập sai quá năm lần thì phải xin mã
              mới.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ContactCard({
  Icon,
  title,
  value,
  verified,
  open,
  children,
}: {
  Icon: typeof MailIcon;
  title: string;
  value: string;
  verified: boolean;
  open: boolean;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <section
      className={`rounded-2xl border bg-white p-5 shadow-sm transition ${
        open ? "border-ctu-blue/40 ring-4 ring-ctu-blue/10" : "border-slate-200"
      }`}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 text-slate-500">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
            <p className="break-all text-sm text-slate-500">{value}</p>
          </div>
        </div>
        {/* `Badge` tự gắn biểu tượng theo sắc thái — đừng truyền thêm cái nữa,
            hai biểu tượng cạnh nhau thì không cái nào được đọc. */}
        <Badge variant={verified ? "success" : "warning"}>
          {verified ? t("Đã xác minh") : t("Chưa xác minh")}
        </Badge>
      </div>
      {children}
    </section>
  );
}

function CodeStep({
  code,
  setCode,
  busy,
  error,
  ttlMinutes,
  secondsLeft,
  destination,
  onConfirm,
  onResend,
  onCancel,
}: {
  code: string;
  setCode: (v: string) => void;
  busy: boolean;
  error: string;
  ttlMinutes: number;
  secondsLeft: number;
  destination: string;
  onConfirm: () => void;
  onResend: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onConfirm();
      }}
      className="space-y-3"
    >
      <p className="text-sm text-slate-600">
        {t("Đã gửi mã tới")} <span className="font-semibold text-slate-800">{destination}</span>. Mã có
        hiệu lực {ttlMinutes} phút.
      </p>

      <OtpCodeInput
        value={code}
        onChange={setCode}
        autoFocus
        disabled={busy}
        error={error}
        label={t("Nhập mã sáu chữ số")}
      />

      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={code.length !== 6 || busy}
          className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${toneClasses("success", "solid")} ${FOCUS_RING}`}
        >
          {busy ? t("Đang xác minh…") : t("Xác nhận")}
        </button>
        <button
          type="button"
          disabled={secondsLeft > 0 || busy}
          onClick={onResend}
          className={`rounded-xl border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${toneClasses("neutral", "outline")} ${FOCUS_RING}`}
        >
          {secondsLeft > 0 ? t("Gửi lại sau {secondsLeft} giây", { secondsLeft }) : t("Gửi lại mã")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-500 transition hover:bg-slate-100"
        >
          {t("Huỷ")}
        </button>
      </div>
    </form>
  );
}
