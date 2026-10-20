/**
 * Xuất xứ của một lần thu (UC18 — Inspect Data Provenance).
 *
 * Luật hiển thị của màn hình này chỉ có một, và nó quan trọng hơn bố cục:
 * **ô chưa từng được ghi nhận phải trông khác ô có giá trị**. Backend trả `null`
 * cho những ô đó thay vì chuỗi rỗng, và ở đây chúng hiện thành "chưa ghi nhận"
 * màu nhạt — chứ không phải một dấu gạch ngang trông y hệt số 0.
 *
 * Lý do: khi một xuất xứ suy đoán đã hiện lên màn hình thì nó không còn phân
 * biệt được với một xuất xứ có thật. Người đọc bảng này sẽ dùng nó để trả lời
 * "mẫu này lấy ở đâu ra", và câu trả lời sai ở đó đắt hơn hẳn một ô trống.
 */
import { useEffect, useState } from "react";
import { getSessionProvenance, type SessionProvenance } from "../api/labelDetail";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import LoadingSpinner from "./ui/LoadingSpinner";
import { XIcon } from "./ui/Icons";

/** Ô chưa ghi nhận. Cố ý KHÔNG phải "—": dấu gạch đọc như một giá trị. */
function Unrecorded() {
  const { t } = useI18n();
  return <span className="italic text-slate-400">{t("chưa ghi nhận")}</span>;
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  const empty = value === null || value === undefined || value === "";
  return (
    <div className="flex flex-wrap items-baseline gap-2 py-1.5 border-b border-slate-100 last:border-0">
      <dt className="w-56 shrink-0 text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className="min-w-0 flex-1 break-all text-sm text-slate-800">
        {empty ? <Unrecorded /> : String(value)}
      </dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-800">{title}</h3>
      <dl>{children}</dl>
    </section>
  );
}

function pct(v: number | null): string | null {
  return v === null || v === undefined ? null : `${(v * 100).toFixed(1)}%`;
}

export default function ProvenanceModal({
  classUid,
  sessionId,
  onClose,
}: {
  classUid: string;
  sessionId: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [data, setData] = useState<SessionProvenance | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    getSessionProvenance(classUid, sessionId)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(friendlyError(e, t("Không đọc được xuất xứ"))));
    return () => {
      alive = false;
    };
  }, [classUid, sessionId, t]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl bg-slate-50 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3 rounded-t-2xl">
          <div className="min-w-0">
            <h2 className="font-semibold text-slate-900">{t("Xuất xứ dữ liệu")}</h2>
            <p className="truncate font-mono text-xs text-slate-400">{sessionId}</p>
          </div>
          <button
            onClick={onClose}
            aria-label={t("Đóng")}
            className="text-slate-400 transition-colors hover:text-slate-600"
          >
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!data && !error && (
            <div className="flex justify-center py-10">
              <LoadingSpinner />
            </div>
          )}

          {data && (
            <>
              <Section title={t("Nguồn gốc")}>
                <Row label={t("Kiểu nguồn")} value={data.origin.source_type} />
                <Row label={t("Đợt thu thập")} value={data.origin.collection_campaign} />
                <Row label={t("Thu lúc")} value={data.origin.created_at} />
                <Row label={t("Đã đồng bộ kho ngoài")} value={data.origin.gdrive_synced} />
                <Row label={t("Số mẫu trong lần thu")} value={data.sample_count} />
              </Section>

              <Section title={t("Ngữ cảnh thu")}>
                <Row label={t("Lớp ký hiệu")} value={data.context.label_original} />
                <Row label={t("Mã lớp")} value={data.class_uid} />
                <Row label={t("Ngôn ngữ")} value={data.context.language} />
                <Row label={t("Phương ngữ")} value={data.context.dialect} />
                <Row
                  label={t("Người ký")}
                  value={
                    data.context.signer_id
                      ? `${data.context.signer_id}${data.context.signer_name ? ` — ${data.context.signer_name}` : ""}`
                      : null
                  }
                />
                <Row label={t("Nhãn người đóng góp")} value={data.context.contributor_label} />
                <Row label={t("Tổ chức")} value={data.context.tenant_id} />
              </Section>

              <Section title={t("Chuỗi dẫn xuất")}>
                <Row
                  label={t("Còn vật liệu gốc")}
                  value={data.derivation.raw_landmarks_available}
                />
                <Row
                  label={t("Phiên bản chuẩn hoá")}
                  value={data.derivation.normalization_version}
                />
                <Row
                  label={t("Hợp đồng tiền xử lý")}
                  value={data.derivation.preprocess_contract_version}
                />
                <Row label={t("FPS gốc")} value={data.derivation.fps_original} />
                <Row label={t("FPS sau xử lý")} value={data.derivation.fps_processed} />
                <Row
                  label={t("Độ dài chuỗi gốc")}
                  value={data.derivation.sequence_length_original}
                />
                <Row label={t("Độ dài chuỗi đang dùng")} value={data.derivation.seq_len} />
                <Row label={t("Đường dẫn tệp")} value={data.derivation.file_path} />
                <Row label={t("Địa chỉ lưu trữ")} value={data.derivation.storage_url} />
                <Row label={t("Mã kiểm tra")} value={data.derivation.checksum} />
              </Section>

              <Section title={t("Chất lượng")}>
                <Row label={t("Độ đầy đủ")} value={pct(data.quality.completeness)} />
                <Row label={t("Độ rung")} value={data.quality.jitter} />
                <Row label={t("Tỉ lệ tay trái")} value={pct(data.quality.left_hand_ratio)} />
                <Row label={t("Tỉ lệ tay phải")} value={pct(data.quality.right_hand_ratio)} />
                <Row label={t("Tỉ lệ hai tay")} value={pct(data.quality.both_hands_ratio)} />
                <Row label={t("Cờ chất lượng")} value={data.quality.quality_flags} />
                <Row label={t("Trạng thái chất lượng")} value={data.quality.quality_status} />
              </Section>

              <Section title={t("Các mẫu sinh ra từ lần thu này")}>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-slate-400">
                      <tr>
                        <th className="py-1.5 pr-3 text-left font-medium">{t("Mã mẫu")}</th>
                        <th className="py-1.5 pr-3 text-left font-medium">{t("Biến thể")}</th>
                        <th className="py-1.5 pr-3 text-right font-medium">{t("Độ dài")}</th>
                        <th className="py-1.5 pr-3 text-right font-medium">{t("Độ đầy đủ")}</th>
                        <th className="py-1.5 text-left font-medium">{t("Mã kiểm tra")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.samples.map((sp, i) => (
                        <tr key={sp.sample_uid ?? i} className="border-t border-slate-100">
                          <td className="py-1.5 pr-3 font-mono text-slate-700">
                            {sp.sample_uid ?? <Unrecorded />}
                          </td>
                          <td className="py-1.5 pr-3 text-slate-600">
                            {sp.augment_id ?? t("gốc")}
                          </td>
                          <td className="py-1.5 pr-3 text-right tabular-nums text-slate-600">
                            {sp.seq_len ?? <Unrecorded />}
                          </td>
                          <td className="py-1.5 pr-3 text-right tabular-nums text-slate-600">
                            {pct(sp.completeness) ?? <Unrecorded />}
                          </td>
                          <td className="py-1.5 font-mono text-[11px] text-slate-400">
                            {sp.checksum ? sp.checksum.slice(0, 16) : <Unrecorded />}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            </>
          )}
        </div>

        <div className="flex justify-end border-t border-slate-200 bg-white px-5 py-3 rounded-b-2xl">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            {t("Đóng")}
          </button>
        </div>
      </div>
    </div>
  );
}
