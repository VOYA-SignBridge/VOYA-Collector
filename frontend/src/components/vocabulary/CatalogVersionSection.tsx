/**
 * Phiên bản danh mục (UC10 — Manage Vocabulary Version).
 *
 * Cơ chế đã có sẵn từ lâu ở `vocabulary_registry.publish_catalog_version`:
 * đóng băng danh mục đang sống thành một bản BẤT BIẾN kèm băm nội dung, và
 * idempotent theo nội dung — công bố lại một danh mục không đổi thì trả về
 * đúng bản đã có chứ không đúc thêm bản trùng. Thiếu duy nhất một màn hình.
 *
 * Câu hỏi mà màn hình này phải trả lời được trong một cái liếc: **danh mục
 * hiện tại đã khớp bản công bố gần nhất chưa?** Đối chiếu hai chuỗi băm là cách
 * duy nhất trả lời đúng — "có sửa gì từ lần công bố" không suy được từ ngày
 * tháng, vì sửa rồi sửa lại về như cũ vẫn cho ra cùng một băm và ĐÚNG là không
 * có gì thay đổi.
 */
import { useCallback, useEffect, useState } from "react";
import {
  getCatalogState,
  getCatalogVersions,
  publishCatalog,
  type CatalogState,
  type CatalogVersion,
} from "../../api/vocabulary";
import Button from "../ui/Button";
import Badge from "../ui/Badge";
import { friendlyError } from "../../lib/errors";
import { useToast } from "../../hooks/useToast";
import { useI18n } from "../../i18n";

function short(h: string | null | undefined): string {
  return h ? `${h.slice(0, 12)}…` : "—";
}

export default function CatalogVersionSection() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [state, setState] = useState<CatalogState | null>(null);
  const [versions, setVersions] = useState<CatalogVersion[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [st, vs] = await Promise.all([getCatalogState(), getCatalogVersions(20)]);
      setState(st);
      setVersions(vs);
      setError("");
    } catch (e) {
      setError(friendlyError(e, t("Không đọc được phiên bản danh mục")));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  // "Đã sửa từ lần công bố" là một phép SO SÁNH BĂM, không phải so ngày.
  const inSync = !!state && state.latest_content_hash === state.content_hash;
  const neverPublished = !!state && state.latest_version === null;

  const publish = async () => {
    setBusy(true);
    try {
      const res = await publishCatalog(note.trim());
      toast.success(
        res.created
          ? t("Đã công bố phiên bản {n}", { n: String(res.version) })
          : t("Danh mục không đổi — vẫn là phiên bản {n}", { n: String(res.version) }),
      );
      setNote("");
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Công bố thất bại")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Phiên bản danh mục")}</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            {t("Đóng băng danh mục hiện tại thành một bản bất biến để thu thập, xuất dữ liệu và huấn luyện tham chiếu tới.")}
          </p>
        </div>
        {state && (
          <Badge variant={neverPublished ? "default" : inSync ? "success" : "warning"}>
            {neverPublished
              ? t("Chưa công bố lần nào")
              : inSync
                ? t("Khớp bản đã công bố")
                : t("Đã sửa từ lần công bố")}
          </Badge>
        )}
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <dl className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t("Bản mới nhất")}
          </dt>
          <dd className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
            {state?.latest_version ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t("Băm bản đã công bố")}
          </dt>
          <dd className="mt-1 font-mono text-sm text-slate-700">
            {short(state?.latest_content_hash)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t("Băm danh mục hiện tại")}
          </dt>
          <dd className="mt-1 font-mono text-sm text-slate-700">{short(state?.content_hash)}</dd>
        </div>
      </dl>

      <div className="mb-5 flex flex-wrap items-end gap-2">
        <label className="min-w-[220px] flex-1">
          <span className="mb-1 block text-xs font-medium text-slate-500">
            {t("Ghi chú cho bản này")}
          </span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("vd: bổ sung phương ngữ miền Trung")}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
          />
        </label>
        <Button onClick={publish} disabled={busy}>
          {busy ? t("Đang công bố…") : t("Công bố phiên bản")}
        </Button>
      </div>

      {versions.length === 0 ? (
        <p className="text-sm text-slate-400">{t("Chưa có phiên bản nào được công bố.")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">{t("Bản")}</th>
                <th className="px-3 py-2 font-medium">{t("Băm nội dung")}</th>
                <th className="px-3 py-2 font-medium">{t("Ghi chú")}</th>
                <th className="px-3 py-2 font-medium">{t("Người công bố")}</th>
                <th className="px-3 py-2 font-medium">{t("Lúc")}</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.version} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-semibold tabular-nums text-slate-900">
                    {v.version}
                    {v.version === state?.latest_version && (
                      <span className="ml-2 text-xs font-normal text-ctu-blue">
                        {t("mới nhất")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">
                    {short(v.content_hash)}
                  </td>
                  <td className="px-3 py-2 text-slate-600">{v.note || "—"}</td>
                  <td className="px-3 py-2 text-slate-600">{v.created_by_username || "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-500">
                    {new Date(v.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
