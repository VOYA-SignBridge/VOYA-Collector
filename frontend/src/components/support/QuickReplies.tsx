import { useI18n } from "../../i18n";

/**
 * Chip trả lời nhanh.
 *
 * Vì sao chip GỬI THẲNG chứ không điền vào ô soạn
 * ------------------------------------------------
 * Điền vào ô rồi bắt bấm Gửi là hai thao tác cho một ý định đã rõ. Nhưng có
 * một ngoại lệ thật: mở hội thoại MỚI thì chip chỉ chọn chủ đề — người dùng
 * vẫn phải mô tả sự cố của mình. Nên `mode` là tham số, không phải hằng số.
 *
 * Chip là chữ GIAO DIỆN nên chúng đi qua `t()`. Chúng đến từ máy chủ (để luôn
 * khớp bảng luật của trợ lý) và mang chính câu tiếng Việt làm khoá — đúng quy
 * ước từ điển của dự án, xem docs/I18N.md.
 */
export default function QuickReplies({
  items,
  onPick,
  disabled = false,
  label,
}: {
  items: string[];
  onPick: (text: string) => void;
  disabled?: boolean;
  label?: string;
}) {
  const { t } = useI18n();
  if (items.length === 0) return null;

  return (
    <div className="px-3 pb-2 sm:px-4">
      {label ? (
        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          {label}
        </p>
      ) : null}
      {/* `role="list"` tường minh: `flex` bỏ ngữ nghĩa danh sách ở một số trình
          đọc màn hình, và người dùng cần nghe "danh sách 5 mục" để biết mình
          đang ở đâu. */}
      <ul role="list" className="flex flex-wrap gap-1.5">
        {items.map((text) => (
          <li key={text}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(text)}
              className="rounded-full border border-ctu-blue/30 bg-ctu-blue/5 px-3 py-1.5 text-xs font-medium text-ctu-blue transition hover:border-ctu-blue hover:bg-ctu-blue/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-1 disabled:opacity-50"
            >
              {t(text)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
