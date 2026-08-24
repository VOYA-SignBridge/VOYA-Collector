import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { register, login } from "../api/auth";
import { BuildingIcon } from "../components/ui/Icons";
import { notifyAuthChange } from "../api/axiosClient";
import AuthShell from "../components/auth/AuthShell";
import AuthInput, { LockIcon, MailIcon, UserIcon } from "../components/auth/AuthInput";
import { Trans, useI18n, tr } from "../i18n";
import {
  LEGAL_KIND_LABEL,
  fetchDocumentOrNull,
  type LegalDocument,
  type LegalKind,
} from "../api/legal";

type FormState = {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Đúng hai loại được hỏi lúc đăng ký. Phải khớp `legal.REQUIRED_AT_REGISTRATION`. */
const REQUIRED_KINDS: LegalKind[] = ["terms", "privacy"];

/**
 * Thông điệp lỗi từ máy chủ, ở dạng đọc được.
 *
 * `detail` của FastAPI là chuỗi ở phần lớn endpoint nhưng là ĐỐI TƯỢNG ở nhánh
 * chấp thuận — `{code, kind, version, url, message}` — vì giao diện cần số hiệu
 * phiên bản để dựng lại màn hình đồng ý. Trả thẳng đối tượng đó vào state kiểu
 * chuỗi làm React ném "Objects are not valid as a React child" và cả trang
 * trắng, che mất chính thông báo đang cần hiển thị.
 */
function readableDetail(err: unknown): { message: string; code?: string } {
  const e = err as {
    response?: { data?: { detail?: unknown } };
    userMessage?: string;
    message?: string;
  };
  const detail = e.response?.data?.detail;
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object") {
    const obj = detail as { message?: string; code?: string };
    if (obj.message) return { message: obj.message, code: obj.code };
  }
  // Hàm mức module → `tr` (xem docs/05-frontend/I18N.md §3), `t` không tồn tại ở đây.
  return { message: e.userMessage || e.message || tr("Không thể đăng ký") };
}

/**
 * Những gì `InvitationPage` chuyển sang qua state của router.
 *
 * Qua state chứ không qua URL: mã đã lộ một lần trên thanh địa chỉ khi người
 * dùng mở thư mời, và không có lý do gì để nó lộ thêm lần nữa ở đây. Đổi lại,
 * state không sống qua một lần tải lại trang — đó là hành vi ĐÚNG: tải lại thì
 * phần mời biến mất và biểu mẫu quay về đăng ký thường, thay vì mang theo một
 * mã mà người dùng không còn thấy.
 */
type InvitationHandoff = {
  invitationToken?: string;
  invitationEmail?: string;
  invitationTenant?: string;
};

export default function RegisterPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const handoff = (useLocation().state ?? {}) as InvitationHandoff;
  const invitationToken = handoff.invitationToken ?? "";
  const invitationEmail = handoff.invitationEmail ?? "";

  const [form, setForm] = useState<FormState>({
    username: "",
    email: invitationEmail,
    password: "",
    confirmPassword: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  // Đăng ký tự phục vụ TẠO một tổ chức. Hai ô dưới đây là phần "đăng ký tổ
  // chức" của lượt đăng ký tài khoản — chúng không xuất hiện khi người dùng
  // tới từ lời mời, vì lúc đó tổ chức đã có sẵn và người mời đã chọn gói.
  const [accepted, setAccepted] = useState(false);

  /**
   * Nạp các văn bản bắt buộc.
   *
   * Danh sách RỖNG là trạng thái hợp lệ, không phải lỗi: công bố văn bản chính
   * là hành động bật cưỡng chế, nên một bản triển khai chưa công bố gì vẫn cho
   * đăng ký và biểu mẫu này không được hỏi một câu không có câu trả lời.
   */

  const loadDocuments = useCallback(async () => {
    const found = await Promise.all(REQUIRED_KINDS.map(fetchDocumentOrNull));
    setDocuments(found.filter((d): d is LegalDocument => d !== null));
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const consentRequired = documents.length > 0;

  const email = form.email.trim();
  const emailError =
    email.length > 0 && !EMAIL_PATTERN.test(email)
      ? t("Email không đúng định dạng.")
      : "";
  const passwordError =
    form.password.length > 0 && form.password.length < 8
      ? t("Mật khẩu phải có ít nhất 8 ký tự.")
      : "";
  const confirmPasswordError =
    form.confirmPassword && form.password !== form.confirmPassword
      ? t("Mật khẩu xác nhận không khớp.")
      : "";

  const canSubmit = useMemo(() => {
    return (
      form.username.trim().length >= 3 &&
      EMAIL_PATTERN.test(form.email.trim()) &&
      form.password.length >= 8 &&
      form.password === form.confirmPassword &&
      (!consentRequired || accepted) &&
      !loading
    );
  }, [form, loading, consentRequired, accepted]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitAttempted(true);
    if (!canSubmit) {
      setError("");
      return;
    }

    setLoading(true);
    setError("");

    try {
      // Số hiệu gửi lên là số hiệu vừa ĐỌC được, không phải một hằng số viết
      // cứng: máy chủ đối chiếu lại, nên một biểu mẫu mở lâu trong tab sẽ bị từ
      // chối với mã `stale_version` thay vì âm thầm ghi nhận chữ ký cho bản đã
      // bị thay thế.
      const consents: Record<string, string> = {};
      for (const doc of documents) {
        consents[`accepted_${doc.kind}_version`] = doc.version;
      }

      const minWait = new Promise((resolve) => setTimeout(resolve, 800));
      const registerTask = register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        ...(invitationToken
          ? { invitation_token: invitationToken }
          : {
            }),
        ...consents,
      }).then(() => login({
        identifier: form.email.trim(),
        password: form.password,
      }));

      await Promise.all([registerTask, minWait]);

      notifyAuthChange();
      navigate("/upload", { replace: true });
    } catch (err: unknown) {
      const { message, code } = readableDetail(err);
      setError(message);
      if (code === "stale_version") {
        // Văn bản đã đổi trong lúc biểu mẫu đang mở. Nạp lại số hiệu mới và bỏ
        // tích: chữ ký vừa rồi là chữ ký cho một bản văn khác, nên giữ ô tích
        // là ghi nhận sự đồng ý với thứ người dùng chưa đọc.
        setAccepted(false);
        void loadDocuments();
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title={t("Tạo tài khoản")}
      footer={
        <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("Đã có tài khoản?")}</span>
          <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            {t("Đăng nhập →")}
          </Link>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {handoff.invitationTenant ? (
          <div className="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            <BuildingIcon className="mt-0.5 h-4 w-4 shrink-0 text-sky-700" aria-hidden="true" />
            <span>
              <Trans
                k="Bạn đang gia nhập {tochuc} theo lời mời. Địa chỉ email đã được điền sẵn và không đổi được — lời mời nêu đích danh địa chỉ đó."
                vars={{ tochuc: <span className="font-semibold">{handoff.invitationTenant}</span> }}
              />
            </span>
          </div>
        ) : null}

        <AuthInput
          label={t("Tên đăng nhập")}
          icon={<UserIcon />}
          value={form.username}
          onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
          type="text"
          autoComplete="username"
          placeholder="vd: minh123"
        />

        <AuthInput
          label={t("Địa chỉ email")}
          icon={<MailIcon />}
          value={form.email}
          onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
          type="email"
          autoComplete="email"
          placeholder="vd: minh@example.com"
          // Khoá ô khi tới từ lời mời. Máy chủ vẫn kiểm lại — `readOnly` chỉ
          // ngăn một cú gõ nhầm dẫn tới lượt đăng ký bị từ chối sau khi đã điền
          // xong cả biểu mẫu, chứ không phải là phép cưỡng chế.
          readOnly={!!invitationToken}
          error={emailError || (submitAttempted && !email ? t("Vui lòng nhập email.") : "")}
        />

        <AuthInput
          label={t("Mật khẩu")}
          icon={<LockIcon />}
          value={form.password}
          onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          placeholder={t("Tối thiểu 8 ký tự")}
          error={passwordError || (submitAttempted && !form.password ? t("Vui lòng nhập mật khẩu.") : "")}
        />

        <AuthInput
          label={t("Xác nhận mật khẩu")}
          icon={<LockIcon />}
          value={form.confirmPassword}
          onChange={(e) => setForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          placeholder={t("Nhập lại mật khẩu")}
          error={confirmPasswordError}
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

        {/* Không còn khối "Tổ chức của bạn" ở đây.
            ---------------------------------------------------------------
            Đăng ký KHÔNG lập tổ chức nữa (22/08/2026). Tài khoản mới vào
            Cộng đồng với vai `community_member` và đóng góp được ngay.

            Lập tổ chức là việc CÓ CHỦ ĐÍCH, làm sau khi đăng nhập ở trang
            Tổ chức — nơi có chỗ chọn gói và nói rõ trần số tổ chức. Hỏi tên
            tổ chức và gói ngay ở bước đăng ký là bắt một người chỉ muốn đóng
            góp vài cử chỉ phải trả lời hai câu không liên quan, rồi sinh ra
            một tenant rỗng kèm một bản sao danh mục từ vựng cho mỗi người
            thử nền tảng. */}

        {/* Ô đồng ý chỉ xuất hiện khi hệ thống ĐÃ công bố văn bản. Hiện một ô
            trỏ tới trang trống sẽ thu được chữ ký cho một bản văn không tồn
            tại — tệ hơn là không thu gì. */}
        {consentRequired && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-ctu-blue focus:ring-ctu-blue"
              />
              <span>
                {t("Tôi đã đọc và đồng ý với")}{" "}
                {documents.map((doc, i) => (
                  <span key={doc.kind}>
                    {/* Từ nối của danh sách cũng phải dịch: tiếng Anh là " and ".
                        Dấu cách hai đầu nằm TRONG khoá — cắt ra ngoài thì bản
                        dịch không kiểm soát được khoảng trắng của chính nó. */}
                    {i > 0 && (i === documents.length - 1 ? t(" và ") : ", ")}
                    <Link
                      to={`/legal/${doc.kind}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-ctu-blue underline underline-offset-2 hover:text-ctu-navy"
                    >
                      {t(LEGAL_KIND_LABEL[doc.kind])}
                    </Link>{" "}
                    <span className="text-slate-400">{t("(bản {v})", { v: doc.version })}</span>
                  </span>
                ))}
                .
              </span>
            </label>
            {submitAttempted && !accepted && (
              <p className="mt-2 pl-7 text-xs text-red-600">
                {t("Bạn cần đọc và đồng ý trước khi tạo tài khoản.")}
              </p>
            )}
          </div>
        )}

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={!canSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && (
            <svg className="h-5 w-5 animate-spin text-white/80" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          {loading ? t("Đang tạo tài khoản...") : t("Tạo tài khoản")}
        </button>
      </form>
    </AuthShell>
  );
}
