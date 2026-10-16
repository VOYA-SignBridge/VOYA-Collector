import { useState } from "react";
import { createTicket } from "../../api/account";
import Button from "../ui/Button";
import { BuildingIcon, CheckCircleIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

/**
 * "Tài khoản của bạn chưa thuộc tổ chức nào" — nhưng có thứ để bấm.
 *
 * Bản trước dừng ở một câu: *"Hãy liên hệ quản trị viên hệ thống để được xếp
 * vào một tổ chức."* Đó là một ngõ cụt có thiện chí — nó nói ra việc cần làm mà
 * không đưa cách làm, nên người dùng phải tự đi tìm địa chỉ thư của một người
 * họ không biết tên.
 *
 * Vì sao KHÔNG phải là nút "Tạo tổ chức"
 * ---------------------------------------
 * `POST /tenants` đòi `require_admin` — quản trị viên NỀN TẢNG. Mở nó cho mọi
 * người là một quyết định sản phẩm chứ không phải một dòng mã: phải trả lời
 * được ai được tạo, mỗi người bao nhiêu, hạn mức mặc định là gì, và chặn lạm
 * dụng ra sao. Dựng một nút gọi thẳng endpoint đó chỉ tạo ra một nút luôn 403.
 *
 * Nên trang này gửi một YÊU CẦU, đi qua đúng đường dây hỗ trợ vừa được nối
 * thông: phiếu vào hàng đợi `/admin/support`, quản trị viên nhận thông báo. Vòng
 * khép kín, không có bước nào dựa vào việc ai đó tình cờ nhìn thấy.
 */
export default function RequestOrganizationCard() {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const canSend = name.trim().length >= 2 && purpose.trim().length >= 10 && !busy;

  const submit = async () => {
    if (!canSend) return;
    setBusy(true);
    setError("");
    try {
      await createTicket({
        subject: t("Yêu cầu tạo tổ chức: {p1}", { p1: name.trim() }).slice(0, 200),
        // Gộp cả hai ô vào thân phiếu: người trực cần đọc được toàn bộ ngữ cảnh
        // trong một lần, không phải ghép từ tiêu đề với phần còn lại.
        body: `Tên tổ chức đề nghị: ${name.trim()}\n\nMục đích sử dụng:\n${purpose.trim()}`,
        category: "account",
      });
      setSent(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail || t("Không gửi được yêu cầu. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 p-5">
        <p className="flex items-center gap-2 font-semibold text-sky-900">
          <CheckCircleIcon className="h-5 w-5" aria-hidden="true" />
          {t("Đã gửi yêu cầu")}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-sky-800">
          {t("Yêu cầu đã vào hàng đợi hỗ trợ. Bạn theo dõi và trả lời thêm được ở mục Hỗ trợ trong Cài đặt.")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="flex items-center gap-2 font-semibold text-slate-900">
        <BuildingIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
        {t("Yêu cầu tạo tổ chức")}
      </h3>
      <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
        {t("Tổ chức do quản trị viên hệ thống tạo. Gửi yêu cầu ở đây và bạn sẽ nhận được phản hồi ngay trong ứng dụng.")}
      </p>

      <div className="mt-4 space-y-3">
        <div>
          <label htmlFor="org-req-name" className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Tên tổ chức đề nghị")}
          </label>
          <input
            id="org-req-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("vd: Trường Chuyên biệt Cần Thơ")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
        </div>

        <div>
          <label htmlFor="org-req-purpose" className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("Mục đích sử dụng")}
          </label>
          <textarea
            id="org-req-purpose"
            rows={3}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder={t("Bạn định thu thập dữ liệu gì, cho ai, và khoảng bao nhiêu người tham gia?")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
          />
          <p className="mt-1 text-xs text-slate-500">
            {t("Tối thiểu 10 ký tự. Càng rõ thì càng ít phải hỏi lại.")}
          </p>
        </div>

        {error ? (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <Button onClick={submit} disabled={!canSend}>
          {busy ? t("Đang gửi…") : t("Gửi yêu cầu")}
        </Button>
      </div>
    </div>
  );
}
