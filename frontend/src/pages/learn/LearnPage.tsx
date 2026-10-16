/**
 * Học ký hiệu — `/learn`. CÔNG KHAI: học sinh, phụ huynh, giáo viên không cần
 * tài khoản.
 *
 * Một ô tìm, ba bộ lọc vùng, một danh sách. Không thống kê, không biểu đồ,
 * không thuật ngữ (kế hoạch UX 13/09/2026 §6, yêu cầu 14/09: "đơn giản, gọn,
 * dễ hiểu cho học sinh, người khiếm thính và thầy cô").
 *
 * Khác "Thư viện nhãn" (`/labels`) ở đối tượng và câu hỏi: đây trả lời "ký hiệu
 * này làm thế nào?", bên kia trả lời "nhãn này đã có bao nhiêu mẫu?". Hai cửa,
 * một kho: thẻ ký hiệu có nút nhỏ "Đóng góp mẫu", chi tiết nhãn có "Học cách
 * ký".
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import { GraduationCapIcon, SearchIcon } from "../../components/ui/Icons";
import { useI18n } from "../../i18n";
import { REGION_LABEL, searchSigns, type Sign } from "../../api/learn";

const REGIONS = ["", "bac", "trung", "nam"] as const;

export default function LearnPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const region = params.get("vung") ?? "";

  const [items, setItems] = useState<Sign[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [attribution, setAttribution] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const setQuery = (next: { q?: string; vung?: string }) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    // Gõ tới đâu tìm tới đó, nhưng chờ 250 ms để không bắn một request mỗi phím.
    const timer = window.setTimeout(() => {
      searchSigns(q, region, 60)
        .then((res) => {
          if (cancelled) return;
          setItems(res.items);
          setTotal(res.total_words);
          setAttribution(res.attribution);
        })
        .catch(() => {
          if (!cancelled) setError(t("Không tải được danh mục. Kiểm tra mạng rồi thử lại."));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [q, region, t]);

  const hint = useMemo(() => {
    if (loading) return t("Đang tìm…");
    if (error) return "";
    if (!q && !region) return total !== null ? t("{n} từ trong danh mục. Gõ để tìm.", { n: total.toLocaleString("vi-VN") }) : "";
    return items.length === 0
      ? t("Không thấy ký hiệu nào cho từ này.")
      : t("{n} kết quả", { n: items.length });
  }, [loading, error, q, region, total, items.length, t]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <GraduationCapIcon className="h-6 w-6 text-ctu-blue" aria-hidden="true" />
          {t("Học ký hiệu")}
        </h1>
        <p className="mt-1 text-base text-slate-600">
          {t("Tra một từ, xem cách ký của từng miền, rồi tự thử với camera.")}
        </p>
      </header>

      <div className="space-y-3">
        <label className="relative block">
          <span className="sr-only">{t("Tìm ký hiệu")}</span>
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQuery({ q: e.target.value })}
            placeholder={t("Gõ một từ, ví dụ: xin chào, cảm ơn, địa chỉ")}
            autoFocus
            className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-4 text-base placeholder:text-slate-400 focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
          />
        </label>

        <div className="flex flex-wrap gap-2" role="group" aria-label={t("Lọc theo miền")}>
          {REGIONS.map((r) => (
            <button
              key={r || "all"}
              type="button"
              onClick={() => setQuery({ vung: r })}
              aria-pressed={region === r}
              className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                region === r
                  ? "border-ctu-blue bg-ctu-blue text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              {r ? t(REGION_LABEL[r]) : t("Tất cả")}
            </button>
          ))}
        </div>

        <p className="text-sm text-slate-500" role="status">{hint}</p>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </div>

      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
        {items.map((s) => (
          <li key={s.slug}>
            <Link
              to={`/learn/${s.slug}`}
              className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
            >
              <span className="min-w-0">
                <span className="block text-base font-medium text-slate-900">{s.word}</span>
                <span className="block text-xs text-slate-500">
                  {s.pos || t("ký hiệu")}
                  {s.definition ? ` · ${s.definition.length > 90 ? s.definition.slice(0, 90) + "…" : s.definition}` : ""}
                </span>
              </span>
              <span className="flex shrink-0 flex-wrap gap-1">
                {s.variants.filter((v) => v.region !== "khong_ghi").map((v) => (
                  <span key={v.code} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{v.region_name}</span>
                ))}
                {s.own_sample_count > 0 && (
                  <Badge variant="success" size="sm">{t("thử được")}</Badge>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {attribution && (
        <p className="text-xs leading-relaxed text-slate-500">{attribution}</p>
      )}
    </div>
  );
}
