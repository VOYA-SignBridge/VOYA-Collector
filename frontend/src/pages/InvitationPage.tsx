import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import {
  acceptInvitation,
  inspectInvitation,
  roleLabel,
  type InvitationPreview,
} from "../api/tenants";
import { friendlyError } from "../lib/errors";
import { BuildingIcon, MailIcon, ShieldIcon } from "../components/ui/Icons";
import { useAuth } from "../contexts/AuthContext";
import { useI18n } from "../i18n";

/**
 * Trang nhận lời mời gia nhập một tổ chức.
 *
 * Mã lời mời nằm ở FRAGMENT, không phải query string
 * ---------------------------------------------------
 * Đường liên kết đúng là `…/invitation#token=abc`, không phải `?token=abc`.
 * Khác biệt không phải chuyện thẩm mỹ: trình duyệt **không bao giờ gửi phần
 * sau dấu thăng lên máy chủ**, nên mã không đọng lại ở nhật ký truy cập của
 * nginx, không đi qua proxy nào, và không dính vào header `Referer` khi người
 * dùng bấm sang một trang khác.
 *
 * Query string vẫn được chấp nhận, vì thư mời cũ có thể đã phát ra ở dạng đó
 * và một liên kết chết thì tệ hơn một liên kết kém kín. Nhưng khi nhận được mã
 * ở query, trang **xoá nó khỏi thanh địa chỉ ngay** bằng `replaceState` — muộn
 * còn hơn không: nó chặn được phần lịch sử trình duyệt và phần `Referer`.
 *
 * Hai đường nhận lời mời, tuỳ người đã có tài khoản hay chưa
 * -----------------------------------------------------------
 * **Chưa có tài khoản** — mã được tiêu thụ trong lượt đăng ký
 * (`POST /auth/register` kèm `invitation_token`); máy chủ kiểm mã TRƯỚC khi tạo
 * tài khoản, nên một mã hỏng không để lại tài khoản mồ côi.
 *
 * **Đã có tài khoản** — `POST /tenants/invitations/accept`. Đường này thêm vào
 * 21/08/2026 để bịt một ngõ cụt im lặng: trước đó lời mời CHỈ tiêu thụ được
 * trong lượt đăng ký, nên một lời mời gửi tới địa chỉ đã có tài khoản không bao
 * giờ nhận được — người nhận bị đẩy sang trang đăng ký rồi bị từ chối vì email
 * đã dùng, còn lời mời nằm lại `pending` cho tới lúc hết hạn, không kèm lời
 * giải thích nào.
 *
 * Dù đi đường nào, mã cũng không quay lại URL: nó đi qua state của router.
 */

function readToken(hash: string, search: string): { token: string; fromQuery: boolean } {
  const fromHash = new URLSearchParams(hash.replace(/^#/, "")).get("token");
  if (fromHash) return { token: fromHash, fromQuery: false };
  const fromSearch = new URLSearchParams(search).get("token");
  return { token: fromSearch || "", fromQuery: !!fromSearch };
}

export default function InvitationPage() {
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const [token, setToken] = useState("");
  const [manual, setManual] = useState("");
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const run = useRef(0);
  const [accepting, setAccepting] = useState(false);

  // So sánh không phân biệt hoa thường và bỏ khoảng trắng hai đầu — máy chủ
  // chuẩn hoá y hệt trước khi đối chiếu, nên giao diện phải hỏi CÙNG một câu.
  // Lệch một chút ở đây sẽ hiện nút cho người mà máy chủ sẽ từ chối.
  const norm = (v: string | undefined | null) => (v || "").trim().toLowerCase();
  const sameEmail = !!preview && norm(user?.email) === norm(preview.email);

  const onAccept = useCallback(async () => {
    if (!token) return;
    setAccepting(true);
    setError("");
    try {
      await acceptInvitation(token);
      navigate("/organization", { replace: true });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setAccepting(false);
    }
  }, [token, navigate]);

  const inspect = useCallback(async (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    const mine = ++run.current;
    setLoading(true);
    setError("");
    try {
      const data = await inspectInvitation(value);
      if (mine !== run.current) return;
      setPreview(data);
      setToken(value);
    } catch (err) {
      if (mine !== run.current) return;
      setPreview(null);
      // Mã lạ và mã hết hạn cùng trả 404 — máy chủ cố ý không phân biệt, nên
      // câu này cũng không được đoán.
      setError(
        friendlyError(
          err,
          t("Lời mời không còn hiệu lực. Hãy đề nghị người mời gửi lại một liên kết mới."),
        ),
      );
    } finally {
      if (mine === run.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const { token: found, fromQuery } = readToken(location.hash, location.search);
    if (!found) return;
    if (fromQuery) {
      // Gỡ mã khỏi thanh địa chỉ trước khi làm bất cứ việc gì khác.
      window.history.replaceState(null, "", `${location.pathname}#token=${found}`);
    }
    void inspect(found);
  }, [location.hash, location.search, location.pathname, inspect]);

  const footer = (
    <div className="flex flex-col gap-2 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
      <span>{t("Đã có tài khoản?")}</span>
      <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
        {t("Đăng nhập →")}
      </Link>
    </div>
  );

  return (
    <AuthShell title={t("Lời mời gia nhập")} footer={footer}>
      {preview ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-900">
            <div className="flex items-start gap-3">
              <BuildingIcon className="mt-0.5 h-5 w-5 shrink-0 text-sky-700" aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                  {t("Bạn được mời vào")}
                </p>
                <p className="mt-0.5 break-words text-base font-bold text-sky-900">
                  {preview.tenant_display_name}
                </p>
              </div>
            </div>
          </div>

          <dl className="space-y-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-sm">
            <Row Icon={MailIcon} label={t("Lời mời phát cho")}>
              <span className="break-all font-medium text-slate-800">{preview.email}</span>
            </Row>
            <Row Icon={ShieldIcon} label={t("Vai trong tổ chức")}>
              <span className="font-medium text-slate-800">{t(roleLabel(preview.role))}</span>
            </Row>
            {preview.expires_at ? (
              <Row Icon={BuildingIcon} label={t("Hết hạn")}>
                <span className="font-medium text-slate-800">
                  {new Date(preview.expires_at).toLocaleString("vi-VN")}
                </span>
              </Row>
            ) : null}
          </dl>

          {isAuthenticated ? null : (
            <p className="text-sm leading-relaxed text-slate-600">
              {t("Lời mời này nêu đích danh địa chỉ ở trên. Bạn phải đăng ký bằng chính địa chỉ đó — đăng ký bằng email khác sẽ bị từ chối và lời mời vẫn còn nguyên.")}
            </p>
          )}

          {isAuthenticated ? (
            sameEmail ? (
              // Địa chỉ khớp — nhận thẳng bằng tài khoản đang đăng nhập. Trước
              // 21/08/2026 nhánh này là một lời xin lỗi: lời mời chỉ tiêu thụ
              // được trong lượt đăng ký, nên người đã có tài khoản không có
              // đường nào vào tổ chức đã mời họ.
              <button
                type="button"
                onClick={() => void onAccept()}
                disabled={accepting}
                className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
              >
                {accepting ? t("Đang nhận lời mời…") : t("Nhận lời mời")}
              </button>
            ) : (
              // Khác địa chỉ: máy chủ CHẮC CHẮN từ chối (lời mời nêu đích danh
              // một người). Hiện nút ở đây chỉ để dẫn người ta tới một câu 403.
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800">
                {t("Lời mời này phát cho một địa chỉ khác với tài khoản bạn đang đăng nhập. Hãy đăng xuất rồi mở lại liên kết này.")}
              </div>
            )
          ) : (
            <button
              type="button"
              onClick={() =>
                // Mã đi qua state của router, KHÔNG qua URL. Một lần lộ trên
                // thanh địa chỉ là đủ; không cần thêm lần thứ hai.
                navigate("/register", {
                  state: {
                    invitationToken: token,
                    invitationEmail: preview.email,
                    invitationTenant: preview.tenant_display_name,
                  },
                })
              }
              className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy"
            >
              {t("Tạo tài khoản để gia nhập")}
            </button>
          )}
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void inspect(manual);
          }}
          className="space-y-4"
        >
          <p className="text-sm leading-relaxed text-slate-600">
            {t("Dán mã lời mời bạn nhận được, hoặc mở lại liên kết trong thư mời. Nếu liên kết đã hết hạn, hãy đề nghị người mời gửi lại.")}
          </p>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">{t("Mã lời mời")}</span>
            <input
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              type="text"
              autoComplete="off"
              spellCheck={false}
              placeholder={t("Dán mã tại đây")}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 font-mono text-sm text-slate-900 shadow-sm outline-none transition focus:border-ctu-blue focus:ring-4 focus:ring-ctu-blue/15"
            />
          </label>

          {error ? (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={!manual.trim() || loading}
            className="w-full rounded-xl bg-ctu-blue px-5 py-3.5 font-semibold text-white shadow-lg shadow-ctu-blue/25 transition hover:bg-ctu-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? t("Đang kiểm tra…") : t("Kiểm tra lời mời")}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

function Row({
  Icon,
  label,
  children,
}: {
  Icon: typeof MailIcon;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <dt className="text-xs text-slate-500">{label}</dt>
        <dd className="mt-0.5">{children}</dd>
      </div>
    </div>
  );
}
