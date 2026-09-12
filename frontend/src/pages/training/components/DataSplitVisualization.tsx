/**
 * Bước 3: tập dữ liệu ĐANG được chia thế nào.
 *
 * Bước này từng hiện ba thanh trượt tỉ lệ train/val/test. Chúng là state cục
 * bộ: không có gì gửi chúng lên máy chủ, và máy chủ không có tham số nào để
 * nhận — huấn luyện luôn chạy trên split đã sinh sẵn trên đĩa. Người dùng kéo,
 * và không có gì xảy ra.
 *
 * Cái giá không chỉ là một điều khiển vô dụng. Nó chiếm chỗ của đúng một sự
 * thật quyết định cách đọc con số cuối cùng: cùng một người có xuất hiện ở cả
 * tập học lẫn tập đánh giá hay không. Trên tập này khác biệt ấy đáng 0.129 độ
 * chính xác — nên một màn hình im lặng về nó là im lặng theo chiều làm kết quả
 * đẹp lên.
 *
 * MIỄN TRỪ khỏi bảng màu trạng thái (`theme/status.ts`). Ba dải màu ở đây là ba
 * CHUỖI DỮ LIỆU (train / validation / test) trên cùng một thanh, không phải ba
 * mức trạng thái. Quy dải "validation" về xanh dương "thành công" sẽ làm nó
 * trùng màu với dải bên cạnh, và người xem mất khả năng đọc tỉ lệ — đúng thứ
 * duy nhất biểu đồ này tồn tại để hiển thị.
 */

import React from 'react';
import type { DatasetInfo, SplitProvenance } from '../../../hooks/useTrainingAPI';
import { dialectLabel } from '../../../config/dialectLabels';
import { useI18n } from "../../../i18n";
import {
  CheckCircleIcon,
  GraduationCapIcon,
  InfoCircleIcon,
  SearchIcon,
  AlertTriangleIcon,
} from '../../../components/ui/Icons';

interface Props {
  datasetInfo: DatasetInfo | null;
  // Phương ngữ đã chọn ở bước trước — split chỉ áp dụng cho các phương ngữ này.
  selectedDialects?: string[];
}

const DataSplitVisualization: React.FC<Props> = ({ datasetInfo, selectedDialects = [] }) => {
  const { t } = useI18n();

  if (!datasetInfo) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-slate-600">{t("Đang tải thông tin dataset...")}</p>
      </div>
    );
  }

  const prov: SplitProvenance | null = datasetInfo.split_provenance ?? null;
  const counts = prov?.counts ?? {};
  const trainCount = counts.train ?? 0;
  const valCount = counts.val ?? 0;
  const testCount = counts.test ?? 0;
  const total = trainCount + valCount + testCount;
  const pct = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);
  const trainPct = pct(trainCount);
  const valPct = pct(valCount);
  const testPct = Math.max(0, 100 - trainPct - valPct);

  // Chưa phân giải được hiện vật: nói ra, đừng vẽ một biểu đồ rỗng trông như
  // thể tập dữ liệu trống.
  if (!prov || total === 0) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="flex items-center gap-1.5 font-semibold">
            <AlertTriangleIcon className="h-4 w-4" aria-hidden="true" />
            {t("Chưa xác định được tập dữ liệu sẽ dùng")}
          </p>
          <p className="mt-2 text-xs">
            {prov?.warning ??
              t("Chưa có hiện vật chia tập nào được ghim cho lượt huấn luyện này.")}
          </p>
        </div>
      </div>
    );
  }

  const tachNguoi = prov.signer_disjoint;
  const khongKiemDuoc = !prov.identity_column;

  return (
    <div className="space-y-6">
      {/* Ngữ cảnh: split áp dụng cho các phương ngữ đã chọn ở bước trước */}
      {selectedDialects.length > 0 && (
        <div className="rounded-lg bg-ctu-blue/5 border border-ctu-blue/20 px-4 py-3 text-sm">
          <span className="text-slate-600">{t("Chia tập cho phương ngữ đã chọn:")} </span>
          <span className="font-semibold text-ctu-blue">
            {selectedDialects.map((d) => dialectLabel(d)).join(', ')}
          </span>
        </div>
      )}

      {/* Hiện vật nào, mục đích gì — thay cho ba thanh trượt không gửi đi đâu */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4">
          {t("Tập Dữ Liệu Sẽ Dùng")}
        </h3>
        <dl className="grid gap-3 sm:grid-cols-2 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">{t("Hiện vật")}</dt>
            <dd className="mt-0.5 font-mono text-slate-900 break-all">
              {prov.split_id || t("mặc định của trainer")}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">{t("Mục đích")}</dt>
            <dd className="mt-0.5 font-semibold text-slate-900">
              {prov.purpose === 'operational'
                ? t("Vận hành — mô hình đem dùng thật")
                : prov.purpose === 'research'
                  ? t("Nghiên cứu — số liệu để báo cáo")
                  : t("chưa khai")}
            </dd>
          </div>
        </dl>

        <p className="mt-4 text-xs text-slate-500">
          {t("Tỉ lệ chia là thuộc tính của hiện vật đã sinh sẵn, không chỉnh được từ màn hình này. Muốn tỉ lệ khác thì phải sinh một hiện vật mới.")}
        </p>
      </div>

      {/* Người ký — điều quyết định cách đọc con số cuối cùng */}
      <div
        className={`rounded-lg border p-4 text-sm ${
          khongKiemDuoc
            ? 'border-amber-300 bg-amber-50 text-amber-900'
            : tachNguoi
              ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
              : 'border-amber-300 bg-amber-50 text-amber-900'
        }`}
      >
        <p className="flex items-center gap-1.5 font-semibold">
          {tachNguoi && !khongKiemDuoc ? (
            <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
          ) : (
            <AlertTriangleIcon className="h-4 w-4" aria-hidden="true" />
          )}
          {tachNguoi && !khongKiemDuoc
            ? t("Người ký được tách giữa học và đánh giá")
            : t("Người ký CHƯA được bảo đảm tách")}
        </p>

        {prov.warning ? (
          <p className="mt-2 text-xs">{prov.warning}</p>
        ) : (
          <p className="mt-2 text-xs">
            {t("Không người ký nào xuất hiện ở cả tập học lẫn tập đánh giá, nên con số đo được phản ánh độ chính xác trên người ký mới.")}
          </p>
        )}

        {prov.identity_column && (
          <p className="mt-2 text-xs opacity-80">
            {t("Đếm theo cột {c}; số người ký: học {a}, kiểm {b}, đánh giá {d}.", {
              c: prov.identity_column,
              a: String((prov.signers.train ?? []).length),
              b: String((prov.signers.val ?? []).length),
              d: String((prov.signers.test ?? []).length),
            })}
          </p>
        )}
      </div>

      {/* Hình ảnh phân chia — tỉ lệ ĐO ĐƯỢC, không phải tỉ lệ mong muốn */}
      <div>
        <p className="mb-3 text-sm font-semibold text-slate-900 uppercase tracking-wider">
          {t("Hình Ảnh Phân Chia")}
        </p>
        <div className="flex h-20 w-full overflow-hidden rounded-xl shadow-sm">
          <div
            className="flex items-center justify-center bg-gradient-to-r from-ctu-blue to-ctu-navy text-white font-semibold text-sm text-center"
            style={{ width: `${trainPct}%` }}
            title={t("Train: {p1} mẫu", { p1: trainCount.toLocaleString() })}
          >
            {trainPct > 10 && `${trainPct}% Train`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-semibold text-sm text-center"
            style={{ width: `${valPct}%` }}
            title={t("Validation: {p1} mẫu", { p1: valCount.toLocaleString() })}
          >
            {valPct > 10 && `${valPct}% Val`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-600 text-white font-semibold text-sm text-center"
            style={{ width: `${testPct}%` }}
            title={t("Test: {p1} mẫu", { p1: testCount.toLocaleString() })}
          >
            {testPct > 10 && `${testPct}% Test`}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <SplitCard
          label={t("Huấn Luyện")}
          icon={<GraduationCapIcon className="h-7 w-7" />}
          count={trainCount}
          percentage={trainPct}
          color="from-ctu-blue to-ctu-navy"
          description={t("Dạy mô hình")}
        />
        <SplitCard
          label={t("Kiểm Tra")}
          icon={<CheckCircleIcon className="h-7 w-7" />}
          count={valCount}
          percentage={valPct}
          color="from-emerald-500 to-emerald-600"
          description={t("Điều chỉnh")}
        />
        <SplitCard
          label={t("Đánh Giá")}
          icon={<SearchIcon className="h-7 w-7" />}
          count={testCount}
          percentage={testPct}
          color="from-amber-500 to-orange-600"
          description={t("Kiểm định cuối")}
        />
      </div>

      {/* Info */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
        <p className="flex items-center gap-1.5 font-medium">
          <InfoCircleIcon className="h-4 w-4" aria-hidden="true" />
          {t("Vì sao không chỉnh được tỉ lệ ở đây")}
        </p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs">
          <li>{t("Tập học dạy mô hình; tập kiểm chọn thời điểm dừng; tập đánh giá đo kết quả cuối.")}</li>
          <li>{t("Ba tập được sinh cùng lúc thành một hiện vật bất biến, kèm mã băm — đổi tỉ lệ nghĩa là sinh hiện vật mới, không phải kéo một thanh trượt.")}</li>
          <li>{t("Nhờ vậy một kết quả đã công bố luôn truy được về đúng tập dữ liệu đã tạo ra nó.")}</li>
        </ul>
      </div>
    </div>
  );
};

function SplitCard({
  label,
  icon,
  count,
  percentage,
  color,
  description,
}: {
  label: string;
  icon: React.ReactNode;
  count: number;
  percentage: number;
  color: string;
  description: string;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-slate-400">{icon}</div>
          <h4 className="mt-2 font-semibold text-slate-900">{label}</h4>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full bg-gradient-to-r ${color} px-2.5 py-1 text-xs font-semibold text-white`}>
          {percentage}%
        </div>
      </div>
      <p className="mt-3 text-lg font-bold text-slate-900">{count.toLocaleString()}</p>
      <p className="text-xs text-slate-500">{t("mẫu")}</p>
    </div>
  );
}

export default DataSplitVisualization;
