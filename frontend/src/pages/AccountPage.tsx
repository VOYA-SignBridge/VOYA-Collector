/**
 * Tài khoản của tôi: chấp thuận và tên đăng nhập.
 *
 * Vì sao trang này tồn tại
 * -------------------------
 * Cả hai đường phía máy chủ đã sống từ trước — `POST /legal/{kind}/accept`,
 * `POST /legal/{kind}/withdraw`, `PATCH /auth/me` — và **không có màn hình nào
 * gọi tới chúng**. Hệ quả đo được ngày 2026-08-09: 10 tài khoản đã ký `terms`
 * và `privacy` lúc đăng ký, `signer_consents` có 0 dòng, và vì cổng đồng thuận
 * chỉ đọc bảng thứ hai nên **mọi bản phát hành nghiên cứu đều rỗng**. Không
 * phải vì cơ chế sai, mà vì không ai ký được `data_contribution`.
 *
 * `data_contribution` cố ý KHÔNG nằm trong `REQUIRED_AT_REGISTRATION`: chính
 * bản văn hứa rằng từ chối không ảnh hưởng tới quyền dùng phần còn lại của hệ
 * thống. Nên nó phải hỏi được ở một chỗ khác, và đây là chỗ đó.
 *
 * Ba điều trang này từ chối làm
 * ------------------------------
 * 1. **Không tự suy ra rút được hay không.** `withdrawable` đến từ máy chủ.
 *    Giao diện tự suy sẽ có ngày hiện một cái nút chắc chắn trả 409.
 * 2. **Không gộp "chưa ký bao giờ" với "đã ký bản cũ".** Nói với người từng
 *    đồng ý rằng họ chưa từng đồng ý là một câu sai, không phải một cách rút
 *    gọn.
 * 3. **Không hứa quá mức đã cấp.** Ký `data_contribution` cấp
 *    `internal_training`, KHÔNG cấp quyền công bố. Ranh giới ấy nằm trong chính
 *    bản văn (mục 4), nên màn hình phải nói ra thay vì để người ta suy đoán.
 *
 * @i18n-key-table — nhãn trả về từ `statusOf` là KHOÁ từ điển, dịch lúc dựng.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import PageHeader from "../components/ui/PageHeader";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { AlertTriangleIcon, InfoCircleIcon } from "../components/ui/Icons";
import { useAuth } from "../contexts/AuthContext";
import { notifyAuthChange } from "../api/axiosClient";
import { useToast } from "../hooks/useToast";
import { friendlyError } from "../lib/errors";
import { updateUsername } from "../api/auth";
import TwoFactorSection from "../components/account/TwoFactorSection";
import { Trans, useI18n } from "../i18n";
import {
  CONSENT_SCOPE_LABEL,
  LEGAL_KIND_LABEL,
  acceptDocument,
  fetchMyConsents,
  withdrawDocument,
  type LegalKind,
  type MyConsent,
} from "../api/legal";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("vi-VN");
}

/** Bốn trạng thái, bốn câu khác nhau. Xem chú thích đầu tệp, điểm 2. */
function statusOf(c: MyConsent): { tone: "success" | "warning" | "neutral"; label: string } {
  if (c.accepted) return { tone: "success", label: "Đã đồng ý" };
  if (c.needs_reconsent) return { tone: "warning", label: "Cần đồng ý lại" };
  // "Chưa đồng ý" trên một văn bản hỏi theo từng buổi đọc như một việc còn nợ,
  // trong khi thực ra không có gì để làm ở trang này.
  if (!c.self_signable) return { tone: "neutral", label: "Hỏi theo từng buổi" };
  return { tone: "neutral", label: "Chưa đồng ý" };
}

export default function AccountPage() {
  const { t } = useI18n();
  return (
    <div className="space-y-8">
      <PageHeader
        title={t("Tài khoản của tôi")}
        subtitle={t("Xem lại những gì bạn đã đồng ý, thay đổi quyết định, và đổi tên đăng nhập.")}
        breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Tài khoản") }]}
      />
      <ConsentSection />
      <TwoFactorSection />
      <UsernameSection />
    </div>
  );
}

// ---------------------------------------------------------------- chấp thuận

function ConsentSection() {
  const { t } = useI18n();
  const [consents, setConsents] = useState<MyConsent[] | null>(null); const [loadError, setLoadError] = useState(""); /** Ô "tôi đã đọc", theo từng loại văn bản. Nút ký mở khoá theo nó. */ const [read, setRead] = useState<Record<string, boolean>>({});
  /** Loại đang chờ xác nhận rút. Rút là thao tác một chiều, không bấm nhầm được. */
  const [confirming, setConfirming] = useState<LegalKind | null>(null);
  const [busy, setBusy] = useState<LegalKind | null>(null);
  const { toast } = useToast();

  // Bộ đếm lượt tải: một lượt nạp chậm không được ghi đè lên kết quả mới hơn.
  const run = useRef(0);

  const load = useCallback(async () => {
    const mine = ++run.current;
    try {
      const data = await fetchMyConsents();
      if (mine !== run.current) return;
      setConsents(data);
      setLoadError("");
    } catch (err) {
      if (mine !== run.current) return;
      setLoadError(friendlyError(err, "Không đọc được danh sách chấp thuận của bạn."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const accept = useCallback(
    async (c: MyConsent) => {
      setBusy(c.kind);
      try {
        // Gửi `current_version`, KHÔNG BAO GIỜ `accepted_version`: máy chủ đối
        // chiếu với bản đang hiệu lực và trả 409 nếu lệch. Gửi bản cũ nghĩa là
        // xin ghi chữ ký cho một bản văn đã bị thay thế.
        await acceptDocument(c.kind, c.current_version);
        toast.success(t("Đã ghi nhận đồng ý với {p1}.", { p1: t(LEGAL_KIND_LABEL[c.kind]) }));
        setRead((prev) => ({ ...prev, [c.kind]: false }));
        await load();
      } catch (err) {
        toast.error(friendlyError(err, "Không ghi nhận được đồng ý của bạn."));
        // Văn bản đã đổi trong lúc trang đang mở. Bỏ tích và nạp lại: giữ ô
        // tích là ghi nhận sự đồng ý với thứ người dùng chưa đọc.
        setRead((prev) => ({ ...prev, [c.kind]: false }));
        await load();
      } finally {
        setBusy(null);
      }
    },
    [load, toast],
  );

  const withdraw = useCallback(
    async (c: MyConsent) => {
      setBusy(c.kind);
      try {
        await withdrawDocument(c.kind);
        toast.success(t("Đã rút đồng ý với {p1}.", { p1: t(LEGAL_KIND_LABEL[c.kind]) }));
        setConfirming(null);
        await load();
      } catch (err) {
        toast.error(friendlyError(err, "Không rút được đồng ý."));
      } finally {
        setBusy(null);
      }
    },
    [load, toast],
  );

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold text-slate-900">{t("Chấp thuận của tôi")}</h2>
      <p className="mt-1 text-sm text-slate-600">
        <Trans
          k="Mỗi dòng ghi lại bạn đã đồng ý với {ban}, không phải một ô đánh dấu. Bấm vào số hiệu bản để đọc lại đúng bản mình đã ký."
          vars={{ ban: <strong>{t("bản nào")}</strong> }}
        />
      </p>

      {loadError && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{loadError}</span>
        </div>
      )}

      {!consents && !loadError && (
        <p className="mt-4 text-sm text-slate-500">{t("Đang tải…")}</p>
      )}

      {/* Không có văn bản nào ĐANG hiệu lực là trạng thái bình thường của một
          bản triển khai mới — công bố chính là hành động bật cưỡng chế. */}
      {consents?.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">
          {t("Hệ thống chưa công bố văn bản nào, nên chưa có gì để bạn đồng ý.")}
        </p>
      )}

      <div className="mt-4 space-y-4">
        {consents?.map((c) => {
          const status = statusOf(c);
          const isBusy = busy === c.kind;
          return (
            <article
              key={c.kind}
              className="rounded-xl border border-slate-200 bg-slate-50/60 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold text-slate-900">
                    {t(LEGAL_KIND_LABEL[c.kind])}
                  </h3>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Bản đang hiệu lực:{" "}
                    <Link
                      to={`/legal/${c.kind}`}
                      className="font-medium text-ctu-blue underline underline-offset-2"
                    >
                      {c.current_version}
                    </Link>
                    {c.required_at_registration && " · bắt buộc để dùng hệ thống"}
                  </p>
                </div>
                <Badge variant={status.tone} size="sm">
                  {t(status.label)}
                </Badge>
              </div>

              {c.accepted_version && (
                <p className="mt-2 text-sm text-slate-700">
                  Bạn đã ký bản{" "}
                  {/* Đường DUY NHẤT từ giao diện tới đúng bản mình đã ký. Không
                      có nó, "bạn đã đồng ý" là câu không kiểm chứng được. */}
                  <Link
                    to={`/legal/${c.kind}?version=${encodeURIComponent(c.accepted_version)}`}
                    className="font-semibold text-ctu-blue underline underline-offset-2"
                  >
                    {c.accepted_version}
                  </Link>
                  {c.accepted_at && t(" lúc {p1}", { p1: formatDate(c.accepted_at) })}.
                </p>
              )}

              {c.needs_reconsent && (
                <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    {t("Bản mới đã thay đổi phạm vi so với bản bạn ký, nên nó cần bạn đồng ý lại. Chấp thuận cũ vẫn được giữ nguyên trong hồ sơ.")}
                  </span>
                </div>
              )}

              {c.grants_scope && (
                <div className="mt-2 flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                  <InfoCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
                  <span>
                    Ký văn bản này cho phép dùng dữ liệu bạn đóng góp ở mức:{" "}
                    <strong>{t(CONSENT_SCOPE_LABEL[c.grants_scope])}</strong>. Các mức
                    cao hơn — công bố cùng bài báo, chia sẻ ra ngoài tổ chức — cần
                    một thoả thuận riêng bằng văn bản, và việc ký ở đây{" "}
                    <strong>{t("không")}</strong> {t("thay cho thoả thuận đó.")}
                  </span>
                </div>
              )}

              {/* --- hành động --- */}
              {/* Văn bản hỏi theo từng buổi ghi hình thì không có nút ký ở đây.
                  Một chữ ký vĩnh viễn cho một bản văn vừa nói "mỗi buổi thu là
                  một lần bạn biết cụ thể hôm nay con em mình làm gì" sẽ thu
                  được đúng thứ mà bản văn ấy từ chối. */}
              {!c.self_signable && (
                <p className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
                  <Trans
                    k="Văn bản này được hỏi trong {khi}, không ký một lần ở đây. Bạn đọc trước được bằng liên kết bên trên."
                    vars={{ khi: <strong>{t("từng buổi ghi hình")}</strong> }}
                  />
                </p>
              )}

              {!c.accepted && c.self_signable && (
                <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-3">
                  <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={!!read[c.kind]}
                      onChange={(e) =>
                        setRead((prev) => ({ ...prev, [c.kind]: e.target.checked }))
                      }
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-ctu-blue focus:ring-ctu-blue"
                    />
                    <span>
                      Tôi đã đọc và đồng ý với{" "}
                      <Link
                        to={`/legal/${c.kind}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-ctu-blue underline underline-offset-2"
                      >
                        {t(LEGAL_KIND_LABEL[c.kind])}
                      </Link>{" "}
                      <span className="text-slate-400">
                        {t("(bản {v})", { v: c.current_version })}
                      </span>
                      .
                    </span>
                  </label>
                  <Button
                    size="sm"
                    className="mt-3"
                    disabled={!read[c.kind]}
                    loading={isBusy}
                    onClick={() => void accept(c)}
                  >
                    {t("Ghi nhận đồng ý")}
                  </Button>
                </div>
              )}

              {c.accepted && c.withdrawable && confirming !== c.kind && (
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-3"
                  onClick={() => setConfirming(c.kind)}
                >
                  {t("Rút đồng ý")}
                </Button>
              )}

              {c.accepted && !c.withdrawable && (
                <p className="mt-3 text-xs text-slate-500">
                  {t("Văn bản này bắt buộc để dùng hệ thống nên không rút riêng được. Nếu bạn muốn dừng hẳn, hãy yêu cầu xoá tài khoản.")}
                </p>
              )}

              {confirming === c.kind && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800">
                  <p className="font-semibold">
                    {t("Rút đồng ý với {loai}?", {
                      loai: t(LEGAL_KIND_LABEL[c.kind]),
                    })}
                  </p>
                  {/* Nói đúng những gì cơ chế thật sự làm. Xem
                      docs/04-legal/CONSENT_ENFORCEMENT.md §5 — rút chặn ở MỌI mức, kể cả
                      nội bộ, nhưng KHÔNG xoá tệp đã có. Hứa xoá ở đây là hứa
                      một việc hệ thống không làm. */}
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    <li>
                      <Trans
                        k="Từ lượt chọn dữ liệu tiếp theo, mẫu của bạn bị loại ở {muc}, kể cả huấn luyện nội bộ."
                        vars={{ muc: <strong>{t("mọi mức")}</strong> }}
                      />
                    </li>
                    <li>
                      <Trans
                        k="Những tệp bạn đã đóng góp {trangthai}. Muốn xoá, hãy dùng Thùng rác hoặc yêu cầu xoá tài khoản."
                        vars={{ trangthai: <strong>{t("không bị xoá")}</strong> }}
                      />
                    </li>
                    <li>{t("Bạn có thể đồng ý lại bất cứ lúc nào ở chính trang này.")}</li>
                  </ul>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {/* "Xác nhận rút", không lặp lại "Rút đồng ý": hai nút cùng
                        chữ ở hai bước khác nhau làm người dùng không chắc mình
                        đang ở bước nào, và bước thứ hai là bước không lùi được. */}
                    <Button
                      size="sm"
                      variant="danger"
                      loading={isBusy}
                      onClick={() => void withdraw(c)}
                    >
                      {t("Xác nhận rút")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={isBusy}
                      onClick={() => setConfirming(null)}
                    >
                      {t("Giữ nguyên")}
                    </Button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
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
        toast.success("Tên không thay đổi.");
        return;
      }
      setRows(result.rows);
      toast.success(t("Đã đổi tên thành {new_username}.", { new_username: result.new_username }));
      // Thanh bên và chữ ký đầu trang đang giữ tên cũ. `AuthProvider` chỉ nạp
      // lại /auth/me khi có sự kiện này — không phát thì người dùng thấy tên cũ
      // cho tới lần tải trang sau, và tưởng việc đổi tên thất bại.
      notifyAuthChange();
    } catch (err) {
      setError(friendlyError(err, "Không đổi được tên tài khoản."));
    } finally {
      setBusy(false);
    }
  }, [canSave, trimmed, toast]);

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
