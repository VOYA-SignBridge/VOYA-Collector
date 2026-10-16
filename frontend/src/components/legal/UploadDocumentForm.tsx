import { useRef, useState } from "react";
import {
  LEGAL_KIND_LABEL, uploadDocument, type LegalKind,
} from "../../api/legal";
import Button from "../ui/Button";
import { AlertTriangleIcon, CheckCircleIcon, UploadIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";
import { describeEffectiveFrom, localInputToOffsetIso } from "../../utils/effectiveFrom";
import { isSudoRequired } from "../../hooks/useSudo";

/**
 * Tải một bản văn pháp lý lên và công bố nó.
 *
 * Đây là đường thay cho ô soạn markdown với những văn bản đến từ bên ngoài:
 * phòng pháp chế gửi `.docx`, bản đã ký và đóng dấu về dưới dạng `.pdf`.
 *
 * Bốn điều biểu mẫu này phải nói ra, vì cả bốn đều KHÔNG hoàn tác được
 * ---------------------------------------------------------------------
 * 1. **Số hiệu là vĩnh viễn.** Công bố xong thì không sửa nội dung dưới cùng
 *    một số hiệu được nữa — trigger `trg_legal_documents_freeze` chặn ở tầng
 *    cơ sở dữ liệu. Muốn đổi thì tăng số hiệu.
 * 2. **"Yêu cầu đồng ý lại" đá mọi người đang dùng** ra màn hình chấp thuận ở
 *    lượt gọi API tiếp theo của họ. Đó là một thao tác ảnh hưởng toàn hệ thống
 *    nấp sau một ô tích.
 * 3. **Ngày hiệu lực ở tương lai là lên lịch**, không phải nháp: bản nằm sẵn
 *    trong bảng và tự thay bản cũ đúng giờ, không ai phải chạy lệnh gì.
 * 4. **Cần nâng quyền.** Máy chủ trả 403 `sudo_required` nếu chưa nhập lại mật
 *    khẩu trong 5 phút gần đây. Bản trước chỉ hiện câu đó rồi dừng: người vận
 *    hành mắc kẹt ở một thông báo bảo nhập lại mật khẩu mà không có chỗ nào để
 *    nhập (LEG-05). Nay biểu mẫu nhận `ensureSudo` từ trang cha — hỏi mật khẩu
 *    ngay tại chỗ, rồi tự gửi lại với ĐÚNG tệp và siêu dữ liệu đang có, như
 *    "sudo mode" của GitHub. Không có `ensureSudo` (trang cha không nối) thì
 *    vẫn hiện nguyên văn như cũ.
 */

const ACCEPT = ".pdf,.docx,.doc,.odt,.md,.txt";
const KINDS: LegalKind[] = ["terms", "privacy", "data_contribution", "guardian"];

export default function UploadDocumentForm({
  onDone,
  ensureSudo,
}: {
  onDone?: () => void;
  /** Hỏi nâng quyền khi máy chủ đòi; trả `true` nếu đã nâng xong. */
  ensureSudo?: () => Promise<boolean>;
}) {
  const { t } = useI18n();
  const fileInput = useRef<HTMLInputElement>(null);

  const [kind, setKind] = useState<LegalKind>("terms");
  const [version, setVersion] = useState("");
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("vi");
  const [summary, setSummary] = useState("");
  const [reconsent, setReconsent] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const canSubmit = !!file && version.trim().length > 0 && !busy;

  const reset = () => {
    setVersion("");
    setTitle("");
    setSummary("");
    setReconsent(false);
    setEffectiveFrom("");
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  const submit = async () => {
    if (!canSubmit || !file) return;
    setBusy(true);
    setError("");
    setDone("");
    const payload = {
      kind,
      version: version.trim(),
      file,
      title: title.trim(),
      language,
      change_summary: summary.trim(),
      requires_reconsent: reconsent,
      // `datetime-local` cho ra "2026-08-20T09:00" — không có múi giờ. Bản
      // trước gửi nguyên chuỗi ấy và máy chủ (chạy UTC) hiểu là 09:00 UTC:
      // văn bản có hiệu lực lúc 16:00 giờ Việt Nam, lệch 7 giờ trên một mốc
      // pháp lý (LEG-04). Nay gắn offset của trình duyệt vào trước khi gửi.
      effective_from: localInputToOffsetIso(effectiveFrom),
    };
    try {
      let res;
      try {
        res = await uploadDocument(payload);
      } catch (err) {
        // Hỏi KHI bị từ chối, không hỏi trước — xem `hooks/useSudo`. Gửi lại
        // đúng `payload` đang có; người dùng không phải chọn lại tệp.
        if (!ensureSudo || !isSudoRequired(err)) throw err;
        if (!(await ensureSudo())) {
          setError(t("Chưa xác thực lại được, văn bản chưa công bố. Tệp và thông tin đã nhập vẫn còn."));
          return;
        }
        res = await uploadDocument(payload);
      }
      const v = res.published?.version || version.trim();
      setDone(
        res.current?.version === v
          ? t("Đã công bố bản {v} và nó đang có hiệu lực.", { v })
          : t("Đã lên lịch bản {v}. Bản đang hiệu lực chưa đổi.", { v }),
      );
      reset();
      onDone?.();
    } catch (err) {
      const data = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      const msg =
        typeof data === "string"
          ? data
          : (data as { message?: string })?.message ||
            t("Không tải lên được. Vui lòng thử lại.");
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <header>
        <h3 className="flex items-center gap-2 font-semibold text-slate-900">
          <UploadIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
          {t("Tải văn bản lên")}
        </h3>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">
          {t("Nhận PDF, DOCX, ODT, hoặc văn bản thuần. Tệp gốc được giữ nguyên từng byte và là thứ người dùng đọc khi ký.")}
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Loại văn bản")}
          </span>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as LegalKind)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>{t(LEGAL_KIND_LABEL[k])}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Số hiệu phiên bản")}
          </span>
          <input
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="2026-08-10"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
          <span className="mt-1 block text-xs text-slate-500">
            {t("Không sửa được sau khi công bố. Muốn đổi nội dung thì tăng số hiệu.")}
          </span>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Tiêu đề")}
          </span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Ngôn ngữ")}
          </span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          >
            <option value="vi">{t("Tiếng Việt")}</option>
            <option value="en">English</option>
          </select>
        </label>

        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Tóm tắt thay đổi so với bản trước")}
          </span>
          <textarea
            rows={2}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
          <span className="mt-1 block text-xs text-slate-500">
            {t("Hiện ngay trên trang văn bản. Đây là thứ người đã ký bản cũ đọc đầu tiên.")}
          </span>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Ngày giờ hiệu lực")}
          </span>
          <input
            type="datetime-local"
            value={effectiveFrom}
            onChange={(e) => setEffectiveFrom(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
          {/* Xem trước có múi giờ: người công bố đọc lại ĐÚNG thời điểm sẽ được
              lưu, như Google Calendar hay Stripe luôn ghi múi giờ cạnh giờ hẹn. */}
          {describeEffectiveFrom(effectiveFrom) ? (
            <span
              className="mt-1 block text-xs font-medium text-slate-700"
              data-testid="effective-from-preview"
            >
              {t("Có hiệu lực lúc {when}", { when: describeEffectiveFrom(effectiveFrom) ?? "" })}
            </span>
          ) : (
            <span className="mt-1 block text-xs text-slate-500">
              {t("Bỏ trống = hiệu lực ngay. Đặt tương lai = lên lịch.")}
            </span>
          )}
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Tệp văn bản")}
          </span>
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
        </label>
      </div>

      <label className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <input
          type="checkbox"
          checked={reconsent}
          onChange={(e) => setReconsent(e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0"
        />
        <span className="text-sm leading-relaxed text-amber-900">
          <span className="font-semibold">{t("Yêu cầu mọi người đồng ý lại")}</span>
          <span className="mt-0.5 block">
            {t("Bật ô này sẽ đưa MỌI người dùng đang hoạt động ra màn hình chấp thuận ở lượt gọi tiếp theo của họ. Chỉ dùng khi nội dung đổi tới mức chữ ký cũ không còn nói đúng điều họ đã đồng ý.")}
          </span>
        </span>
      </label>

      {error ? (
        <p role="alert" className="flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : null}

      {done ? (
        <p className="flex items-start gap-2 rounded-lg bg-sky-50 px-4 py-3 text-sm text-sky-800">
          <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{done}</span>
        </p>
      ) : null}

      <Button onClick={submit} disabled={!canSubmit}>
        {busy ? t("Đang tải lên…") : t("Tải lên và công bố")}
      </Button>
    </section>
  );
}
