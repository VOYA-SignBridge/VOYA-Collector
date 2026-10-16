/**
 * Chính sách áp dụng cho tổ chức — `/console/policies`.
 *
 * Vì sao một tổ chức cần trang này
 * ----------------------------------
 * Người điều hành một tổ chức chịu trách nhiệm về dữ liệu mà nhóm họ thu, nhưng
 * luật chi phối dữ liệu đó **do nền tảng đặt**: văn bản pháp lý nào đang hiệu
 * lực, bản nào buộc chấp thuận lại, hạn mức nào của gói, cơ chế cách ly nào
 * đang cưỡng chế. Trước trang này, những thứ đó nằm rải ở console nền tảng —
 * nơi quản trị viên tổ chức **không vào được**.
 *
 * Trang chỉ ĐỌC, và đó là chủ ý: chính sách nền tảng không phải thứ một tổ chức
 * sửa được. Cho họ **thấy** mà không cho **sửa** là đúng ranh giới A7 ≠ A8.
 *
 * @i18n-key-table — nhãn loại văn bản dùng bảng khoá của `api/legal`.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Badge from "../../components/ui/Badge";
import PageHeader from "../../components/ui/PageHeader";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import EmptyState from "../../components/ui/EmptyState";
import { useI18n } from "../../i18n";
import { LEGAL_KIND_LABEL, listPublishedDocuments, type LegalDocument } from "../../api/legal";
import { fetchBillingSummary, type BillingSummary } from "../../api/billing";
import { getScopeSummary, type ScopeSummary } from "../../api/workspaces";

export default function ConsolePoliciesPage() {
  const { t } = useI18n();
  const [docs, setDocs] = useState<LegalDocument[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [scope, setScope] = useState<ScopeSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const [d, b, s] = await Promise.allSettled([
        listPublishedDocuments(), fetchBillingSummary(), getScopeSummary(),
      ]);
      if (d.status === "fulfilled") setDocs(d.value);
      if (b.status === "fulfilled") setBilling(b.value);
      if (s.status === "fulfilled") setScope(s.value);
      setLoading(false);
    })();
  }, []);

  if (loading) return <LoadingSpinner size="lg" label={t("Đang tải chính sách…")} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Chính sách áp dụng")}
        subtitle={t("Luật do nền tảng đặt, đang có hiệu lực với tổ chức này. Trang chỉ đọc.")}
      />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">{t("Văn bản pháp lý đang hiệu lực")}</h2>
        {docs.length === 0 ? (
          <EmptyState
            title={t("Chưa công bố văn bản nào")}
            description={t("Khi chưa có văn bản, đăng ký vẫn chạy nhưng hệ thống không thu được chấp thuận nào.")}
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-600">
                <tr>
                  <th className="px-3 py-2">{t("Loại")}</th>
                  <th className="px-3 py-2">{t("Bản")}</th>
                  <th className="px-3 py-2">{t("Hiệu lực từ")}</th>
                  <th className="px-3 py-2">{t("Buộc chấp thuận lại")}</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={`${d.kind}:${d.version}`} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <Link
                        to={`/legal/${d.kind}?version=${encodeURIComponent(d.version)}`}
                        className="font-medium text-ctu-blue hover:underline"
                      >
                        {t(LEGAL_KIND_LABEL[d.kind] ?? d.kind)}
                      </Link>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{d.version}</td>
                    <td className="px-3 py-2 text-slate-600">
                      {d.effective_from ? new Date(d.effective_from).toLocaleDateString("vi-VN") : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant={d.requires_reconsent ? "warning" : "default"} size="sm">
                        {d.requires_reconsent ? t("Có") : t("Không")}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">{t("Chính sách kỹ thuật đang cưỡng chế")}</h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Row
            term={t("Cách ly dữ liệu giữa các tổ chức")}
            value={t("Cưỡng chế ở tầng cơ sở dữ liệu (Row-Level Security), fail-closed khi thiếu ngữ cảnh")}
            tone="success"
          />
          <Row
            term={t("Chế độ phân quyền")}
            value={scope?.authz_mode ?? "—"}
            tone={scope?.authz_mode === "casbin" ? "success" : "warning"}
            note={scope?.authz_mode === "shadow"
              ? t("Casbin quan sát và so sánh; hệ cũ hai phạm vi là bên quyết định.")
              : undefined}
          />
          <Row
            term={t("Gói cước áp dụng")}
            value={billing?.plan?.display_name ?? "—"}
            tone="default"
            note={t("Hạn mức chi tiết ở mục Gói & hạn mức.")}
          />
          <Row
            term={t("Dữ liệu gắn vào cây phạm vi")}
            value={scope?.data_carries_project_id ? t("Đã gắn") : t("Chưa gắn")}
            tone={scope?.data_carries_project_id ? "success" : "warning"}
            note={t("Mẫu, lớp và tác vụ huấn luyện hiện chỉ mang định danh tổ chức.")}
          />
        </dl>
      </section>
    </div>
  );
}

function Row({
  term, value, tone, note,
}: {
  term: string;
  value: string;
  tone: "success" | "warning" | "default";
  note?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <dt className="text-xs font-medium text-slate-500">{term}</dt>
      <dd className="mt-1">
        <Badge variant={tone} size="sm">{value}</Badge>
        {note && <p className="mt-1.5 text-xs text-slate-500">{note}</p>}
      </dd>
    </div>
  );
}
