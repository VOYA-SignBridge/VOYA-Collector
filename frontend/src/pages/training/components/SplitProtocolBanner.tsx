import type { SplitProvenance } from '../../../hooks/useTrainingAPI';
import { AlertTriangleIcon, CheckCircleIcon } from '../../../components/ui/Icons';

/**
 * Shows which partition produced a metric, right next to the metric itself.
 *
 * Why this exists: a single number is meaningless without the protocol behind
 * it. The same model on the same 453 test samples scored 0.596 when trained on
 * four signers (root_strict_v13, which puts a signer in validation) and 0.956
 * when trained on five (the LOSO fold that keeps that signer in training). Both
 * are correct; only one is comparable to the thesis tables, which report a mean
 * over leave-one-signer-out folds.
 *
 * Bản trước hiển thị ba đoạn cảnh báo chồng nghĩa nhau, và in lại nguyên danh
 * sách người ký ba lần giống hệt — nhìn như lỗi render chứ không ra thông tin.
 * Giờ mỗi ý chỉ nói một lần: số người ký ở mỗi tập, rồi đúng một câu giải thích
 * con số bên trên đọc thế nào.
 */

const PART_LABELS: Record<string, string> = {
  train: 'Huấn luyện',
  val: 'Kiểm định',
  test: 'Kiểm tra',
};

export default function SplitProtocolBanner({
  provenance,
  splitVersion,
}: {
  provenance?: SplitProvenance | null;
  splitVersion?: string | null;
}) {
  if (!provenance) {
    return (
      <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          Lần chạy này không ghi lại cách chia dữ liệu, nên không biết người ở tập kiểm tra có
          từng xuất hiện lúc huấn luyện hay không. Chưa nên đem con số bên trên so với các bảng
          trong báo cáo.
        </p>
      </div>
    );
  }

  const { split_mode, signer_disjoint, signers, counts, warning } = provenance;
  const parts: Array<'train' | 'val' | 'test'> = ['train', 'val', 'test'];

  // Người vừa học vừa bị đem ra chấm — đây mới là thông tin cần đọc, thay vì in
  // lại cùng một danh sách ở cả ba ô.
  const trainSigners = new Set(signers?.train ?? []);
  const overlap = (signers?.test ?? []).filter((s) => trainSigners.has(s));

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        {parts.map((p) => {
          const list = signers?.[p] ?? [];
          return (
            <div key={p} className="rounded-lg bg-white p-3 ring-1 ring-slate-200">
              <div className="text-xs font-medium text-slate-500">{PART_LABELS[p]}</div>
              <div className="mt-0.5 text-sm font-semibold text-slate-900">
                {(counts?.[p] ?? 0).toLocaleString()} mẫu
              </div>
              <div
                className="mt-1 text-xs text-slate-600"
                title={list.length ? list.join(', ') : undefined}
              >
                {list.length ? `${list.length} người ký` : '— chưa ghi người ký'}
              </div>
            </div>
          );
        })}
      </div>

      {/* Đúng một câu nói rõ con số bên trên đọc thế nào. Ưu tiên cảnh báo do
          máy chủ sinh ra vì nó nêu đích danh người ký bị trùng. */}
      {signer_disjoint ? (
        <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-900">
          <CheckCircleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            Không ai vừa có mặt lúc huấn luyện vừa bị đem ra chấm, nên con số bên trên phản ánh
            khả năng nhận dạng một người hoàn toàn mới.
          </p>
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-900">
          <AlertTriangleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            {warning ??
              `${overlap.length || 'Một số'} người ký vừa có mặt lúc huấn luyện vừa bị đem ra chấm${
                overlap.length ? ` (${overlap.slice(0, 5).join(', ')}${overlap.length > 5 ? '…' : ''})` : ''
              }.`}{' '}
            Mô hình đã nhìn thấy chính những người này lúc học, nên đây là khả năng{' '}
            <strong>nhận lại người quen</strong>. Với người lạ, kết quả thực tế sẽ thấp hơn.
          </p>
        </div>
      )}

      <p className="text-xs text-slate-500">
        Đây là kết quả của <strong>một lần chia</strong> ({split_mode || 'không rõ cách chia'}
        {splitVersion ? `, ${splitVersion}` : ''}). Bảng trong báo cáo lấy trung bình nhiều lần
        chia luân phiên từng người ký, nên hai con số không so thẳng với nhau được.
      </p>
    </div>
  );
}
