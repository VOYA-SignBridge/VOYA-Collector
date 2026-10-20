/**
 * Học ký hiệu — `/learn`. CÔNG KHAI: học sinh, phụ huynh, giáo viên không cần
 * tài khoản.
 *
 * Bản 17/09/2026: từ "một ô tìm + ba nút miền + một danh sách dài" thành một
 * trang tra cứu đúng nghĩa — ô tìm lớn ở đầu, bộ lọc (miền, loại mục, từ
 * loại, chữ cái đầu, "thử được"), lưới thẻ, và phân trang. Vẫn giữ nguyên tắc
 * 13/09 §6: không thống kê, không biểu đồ, không thuật ngữ; mọi bộ lọc là một
 * câu người mới đọc hiểu ngay.
 *
 * Mọi trạng thái (từ khoá, bộ lọc, trang) nằm trong URL — chia sẻ được, quay
 * lại được, và trang chi tiết bấm "Tất cả ký hiệu" về đúng chỗ đang xem.
 *
 * Khác "Thư viện nhãn" (`/labels`) ở đối tượng và câu hỏi: đây trả lời "ký hiệu
 * này làm thế nào?", bên kia trả lời "nhãn này đã có bao nhiêu mẫu?". Hai cửa,
 * một kho: thẻ ký hiệu có nút nhỏ "Đóng góp mẫu", chi tiết nhãn có "Học cách
 * ký".
 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import {
  ArrowRightIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  GraduationCapIcon,
  HandIcon,
  SearchIcon,
  XIcon,
} from "../../components/ui/Icons";
import { useI18n } from "../../i18n";
import { KIND_LABEL, REGION_LABEL, searchSigns, type LearnFacets, type Sign } from "../../api/learn";

const REGIONS = ["", "bac", "trung", "nam"] as const;
const KINDS = ["", "tu_thuong", "bang_chu_cai", "chu_so"] as const;
const PAGE_SIZES = [12, 24, 48] as const;
const DEFAULT_PAGE_SIZE = 24;

/** Gợi ý gõ thử — từ hay gặp ở lớp học, đủ đa dạng để thấy cả ba miền. */
// i18n-ignore-next-line — từ khoá tra cứu, là DỮ LIỆU tiếng Việt: danh mục chỉ có tiếng Việt nên ở giao diện tiếng Anh vẫn gõ đúng những từ này.
const EXAMPLES = ["xin chào", "cảm ơn", "gia đình", "trường học", "bạn bè", "ăn cơm"];

/**
 * Tham số URL bằng tiếng Việt không dấu (`?vung=bac&trang=2`), theo `?vung=`
 * đã có từ bản đầu — người dùng chia sẻ liên kết đọc được nó nghĩa là gì.
 */
interface Query {
  q: string;
  vung: string;
  loai: string;
  tu_loai: string;
  chu: string;
  thu_duoc: string;
  trang: string;
  moi_trang: string;
}

/** Trang 1 ≤ … ≤ n, thu về ≤ 7 ô kèm dấu "…" khi nhiều trang. */
function pageWindow(page: number, pages: number): (number | "…")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const set = new Set<number>([1, pages, page - 1, page, page + 1]);
  if (page <= 3) [2, 3, 4].forEach((n) => set.add(n));
  if (page >= pages - 2) [pages - 3, pages - 2, pages - 1].forEach((n) => set.add(n));
  const sorted = [...set].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("…");
    out.push(sorted[i]);
  }
  return out;
}

export default function LearnPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const query: Query = {
    q: params.get("q") ?? "",
    vung: params.get("vung") ?? "",
    loai: params.get("loai") ?? "",
    tu_loai: params.get("tu_loai") ?? "",
    chu: params.get("chu") ?? "",
    thu_duoc: params.get("thu_duoc") ?? "",
    trang: params.get("trang") ?? "",
    moi_trang: params.get("moi_trang") ?? "",
  };
  const page = Math.max(1, parseInt(query.trang, 10) || 1);
  const pageSize = (PAGE_SIZES as readonly number[]).includes(parseInt(query.moi_trang, 10))
    ? parseInt(query.moi_trang, 10)
    : DEFAULT_PAGE_SIZE;
  const hasFilter = Boolean(query.vung || query.loai || query.tu_loai || query.chu || query.thu_duoc);

  const [items, setItems] = useState<Sign[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [totalWords, setTotalWords] = useState<number | null>(null);
  // Facets là tĩnh (danh mục là tệp); giữ bản đã nhận để bộ lọc không nhấp
  // nháy mỗi lần tải lại kết quả.
  const [facets, setFacets] = useState<LearnFacets | null>(null);
  const [attribution, setAttribution] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const resultsRef = useRef<HTMLDivElement>(null);

  /** Đổi bất kỳ điều kiện nào là về trang 1 — trừ khi chính `trang` đang đổi. */
  const setQuery = (next: Partial<Query>) => {
    const p = new URLSearchParams(params);
    if (!("trang" in next)) p.delete("trang");
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  };

  const clearFilters = () => setQuery({ vung: "", loai: "", tu_loai: "", chu: "", thu_duoc: "" });

  const goToPage = (n: number) => {
    setQuery({ trang: n > 1 ? String(n) : "" });
    // Đưa mắt về đầu danh sách, chứ không để người xem ở cuối trang cũ.
    // (jsdom không có `scrollIntoView`; kiểm trước để test không đổ.)
    resultsRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    // Gõ tới đâu tìm tới đó, nhưng chờ 250 ms để không bắn một request mỗi phím.
    const timer = window.setTimeout(() => {
      searchSigns({
        q: query.q,
        region: query.vung,
        kind: query.loai,
        pos: query.tu_loai,
        letter: query.chu,
        hasOwn: query.thu_duoc === "1",
        page,
        limit: pageSize,
      })
        .then((res) => {
          if (cancelled) return;
          setItems(res.items);
          setTotal(res.total);
          setPages(res.pages);
          setTotalWords(res.total_words);
          setFacets(res.facets);
          setAttribution(res.attribution);
          // Máy chủ kéo trang quá xa về trang cuối; đồng bộ URL cho khớp.
          if (res.page !== page) {
            const p = new URLSearchParams(params);
            if (res.page > 1) p.set("trang", String(res.page));
            else p.delete("trang");
            setParams(p, { replace: true });
          }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.q, query.vung, query.loai, query.tu_loai, query.chu, query.thu_duoc, page, pageSize, reloadKey, t]);

  const fmt = (n: number) => n.toLocaleString("vi-VN");
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const summary = useMemo(() => {
    if (loading) return t("Đang tìm…");
    if (error) return "";
    if (total === 0) return t("Không thấy ký hiệu nào phù hợp.");
    return t("Hiện {a}–{b} trong {n} ký hiệu", { a: fmt(rangeStart), b: fmt(rangeEnd), n: fmt(total) });
  }, [loading, error, total, rangeStart, rangeEnd, t]);

  const posOptions = facets?.pos ?? [];
  const letters = facets?.letters ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      {/* ---- Đầu trang: một câu nói trang này để làm gì + ô tìm lớn ---- */}
      <header className="overflow-hidden rounded-2xl bg-gradient-to-br from-ctu-navy via-ctu-navy-mid to-ctu-blue px-5 py-7 text-white shadow-lg sm:px-8 sm:py-9">
        <div className="flex items-center gap-2 text-sm font-medium text-white/80">
          <GraduationCapIcon className="h-5 w-5" aria-hidden="true" />
          {t("Từ điển ngôn ngữ ký hiệu tiếng Việt")}
        </div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{t("Học ký hiệu")}</h1>
        <p className="mt-2 max-w-2xl text-base text-white/85">
          {t("Tra một từ, xem cách ký của từng miền, rồi tự thử với camera.")}
          {totalWords !== null && (
            <span className="ml-1 text-white/70">
              {t("Hiện có {n} ký hiệu.", { n: fmt(totalWords) })}
            </span>
          )}
        </p>

        <label className="relative mt-5 block">
          <span className="sr-only">{t("Tìm ký hiệu")}</span>
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={query.q}
            onChange={(e) => setQuery({ q: e.target.value })}
            placeholder={t("Gõ một từ, ví dụ: xin chào, cảm ơn, địa chỉ")}
            autoFocus
            className="w-full rounded-xl border-0 bg-white py-3.5 pl-12 pr-12 text-base text-slate-900 shadow-md placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-ctu-yellow/60"
          />
          {query.q && (
            <button
              type="button"
              onClick={() => setQuery({ q: "" })}
              aria-label={t("Xoá từ khoá")}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <XIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </label>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-white/70">{t("Thử gõ:")}</span>
          {EXAMPLES.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setQuery({ q: w })}
              className="rounded-full border border-white/30 bg-white/10 px-3 py-1 text-white hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-yellow"
            >
              {w}
            </button>
          ))}
        </div>
      </header>

      {/* ---- Bộ lọc: mỗi hàng một câu hỏi, mỗi nút một câu trả lời ---- */}
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-label={t("Bộ lọc")}>
        <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
          <FilterGroup label={t("Miền")}>
            {REGIONS.map((r) => {
              const count = r ? facets?.regions.find((x) => x.key === r)?.count : undefined;
              return (
                <Chip key={r || "all"} active={query.vung === r} onClick={() => setQuery({ vung: r })} count={count}>
                  {r ? t(REGION_LABEL[r]) : t("Tất cả")}
                </Chip>
              );
            })}
          </FilterGroup>

          <FilterGroup label={t("Loại")}>
            {KINDS.map((k) => {
              const count = k ? facets?.kinds.find((x) => x.key === k)?.count : undefined;
              return (
                <Chip key={k || "all"} active={query.loai === k} onClick={() => setQuery({ loai: k })} count={count}>
                  {k ? t(KIND_LABEL[k]) : t("Tất cả")}
                </Chip>
              );
            })}
          </FilterGroup>

          <div className="flex flex-wrap items-end gap-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">{t("Từ loại")}</span>
              <select
                value={query.tu_loai}
                onChange={(e) => setQuery({ tu_loai: e.target.value })}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
              >
                <option value="">{t("Tất cả")}</option>
                {posOptions.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name} ({fmt(p.count)})
                  </option>
                ))}
              </select>
            </label>

            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-800 has-[:checked]:border-ctu-blue has-[:checked]:bg-ctu-blue/5">
              <input
                type="checkbox"
                checked={query.thu_duoc === "1"}
                onChange={(e) => setQuery({ thu_duoc: e.target.checked ? "1" : "" })}
                className="h-4 w-4 rounded border-slate-300 text-ctu-blue focus:ring-ctu-blue"
              />
              <HandIcon className="h-4 w-4 text-ctu-blue" aria-hidden="true" />
              {t("Chỉ ký hiệu thử được với camera")}
            </label>
          </div>
        </div>

        {letters.length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label={t("Chữ cái đầu")}>
              <span className="mr-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t("Chữ cái")}</span>
              <button
                type="button"
                onClick={() => setQuery({ chu: "" })}
                aria-pressed={!query.chu}
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  !query.chu ? "bg-ctu-blue text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t("Tất cả")}
              </button>
              {letters.map((ch) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => setQuery({ chu: ch })}
                  aria-pressed={query.chu === ch}
                  className={`min-w-[1.75rem] rounded-md px-1.5 py-1 text-xs font-semibold uppercase ${
                    query.chu === ch ? "bg-ctu-blue text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>
        )}

        {hasFilter && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-sm">
            <span className="text-slate-500">{t("Đang lọc:")}</span>
            {query.vung && <ActiveTag onClear={() => setQuery({ vung: "" })}>{t(REGION_LABEL[query.vung])}</ActiveTag>}
            {query.loai && <ActiveTag onClear={() => setQuery({ loai: "" })}>{KIND_LABEL[query.loai] ? t(KIND_LABEL[query.loai]) : query.loai}</ActiveTag>}
            {query.tu_loai && <ActiveTag onClear={() => setQuery({ tu_loai: "" })}>{query.tu_loai}</ActiveTag>}
            {query.chu && <ActiveTag onClear={() => setQuery({ chu: "" })}>{t("Chữ {c}", { c: query.chu.toUpperCase() })}</ActiveTag>}
            {query.thu_duoc && <ActiveTag onClear={() => setQuery({ thu_duoc: "" })}>{t("Thử được với camera")}</ActiveTag>}
            <button type="button" onClick={clearFilters} className="ml-auto font-medium text-ctu-blue hover:underline">
              {t("Xoá bộ lọc")}
            </button>
          </div>
        )}
      </section>

      {/* ---- Kết quả ---- */}
      <div ref={resultsRef} className="scroll-mt-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-slate-600" role="status" aria-live="polite">{summary}</p>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            {t("Mỗi trang")}
            <select
              value={String(pageSize)}
              onChange={(e) => setQuery({ moi_trang: e.target.value === String(DEFAULT_PAGE_SIZE) ? "" : e.target.value })}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
              aria-label={t("Số ký hiệu mỗi trang")}
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>

        {error && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setReloadKey((k) => k + 1)}
              className="rounded-lg border border-red-300 bg-white px-3 py-1 font-medium text-red-800 hover:bg-red-100"
            >
              {t("Thử lại")}
            </button>
          </div>
        )}

        {loading && items.length === 0 ? (
          <ul className="grid gap-3 sm:grid-cols-2" aria-hidden="true">
            {Array.from({ length: 6 }, (_, i) => (
              <li key={i} className="animate-pulse rounded-xl border border-slate-200 bg-white p-4">
                <div className="h-5 w-1/2 rounded bg-slate-200" />
                <div className="mt-3 h-3 w-full rounded bg-slate-100" />
                <div className="mt-2 h-3 w-3/4 rounded bg-slate-100" />
                <div className="mt-4 flex gap-2">
                  <div className="h-5 w-12 rounded-full bg-slate-100" />
                  <div className="h-5 w-12 rounded-full bg-slate-100" />
                </div>
              </li>
            ))}
          </ul>
        ) : !error && items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
            <SearchIcon className="mx-auto h-10 w-10 text-slate-300" aria-hidden="true" />
            <h2 className="mt-3 text-lg font-semibold text-slate-800">{t("Không thấy ký hiệu nào phù hợp.")}</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
              {t("Thử gõ ngắn hơn hoặc không dấu — gõ cam on cũng ra cảm ơn — hoặc bỏ bớt bộ lọc.")}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {hasFilter && (
                <button type="button" onClick={clearFilters} className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-semibold text-white hover:bg-ctu-navy-mid">
                  {t("Xoá bộ lọc")}
                </button>
              )}
              {query.q && (
                <button type="button" onClick={() => setQuery({ q: "" })} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                  {t("Xoá từ khoá")}
                </button>
              )}
            </div>
          </div>
        ) : (
          <ul className={`grid gap-3 sm:grid-cols-2 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
            {items.map((s) => (
              <li key={s.slug}>
                <SignCard sign={s} />
              </li>
            ))}
          </ul>
        )}

        {pages > 1 && !error && (
          <nav className="flex flex-wrap items-center justify-center gap-1 pt-2" aria-label={t("Phân trang")}>
            <button
              type="button"
              onClick={() => goToPage(page - 1)}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
              {t("Trước")}
            </button>
            {pageWindow(page, pages).map((n, i) =>
              n === "…" ? (
                <span key={`gap-${i}`} className="px-1 text-slate-400" aria-hidden="true">…</span>
              ) : (
                <button
                  key={n}
                  type="button"
                  onClick={() => goToPage(n)}
                  aria-current={n === page ? "page" : undefined}
                  aria-label={t("Trang {n}", { n })}
                  className={`min-w-[2.25rem] rounded-lg px-2 py-1.5 text-sm font-medium ${
                    n === page ? "bg-ctu-blue text-white" : "text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {n}
                </button>
              ),
            )}
            <button
              type="button"
              onClick={() => goToPage(page + 1)}
              disabled={page >= pages}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t("Sau")}
              <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          </nav>
        )}
      </div>

      {attribution && (
        <p className="text-xs leading-relaxed text-slate-500">{attribution}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label}>
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  count?: number;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors ${
        active
          ? "border-ctu-blue bg-ctu-blue text-white"
          : "border-slate-200 bg-white text-slate-700 hover:border-ctu-blue/50 hover:bg-ctu-blue/5"
      }`}
    >
      {children}
      {count !== undefined && (
        <span className={`text-xs ${active ? "text-white/80" : "text-slate-400"}`}>{count.toLocaleString("vi-VN")}</span>
      )}
    </button>
  );
}

function ActiveTag({ onClear, children }: { onClear: () => void; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-ctu-blue/10 py-0.5 pl-2.5 pr-1 text-ctu-navy">
      {children}
      <button type="button" onClick={onClear} aria-label={t("Bỏ điều kiện này")} className="rounded-full p-0.5 hover:bg-ctu-blue/20">
        <XIcon className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </span>
  );
}

function SignCard({ sign }: { sign: Sign }) {
  const { t } = useI18n();
  const regions = sign.variants.filter((v) => v.region !== "khong_ghi");
  return (
    <Link
      to={`/learn/${sign.slug}`}
      className="group flex h-full flex-col rounded-xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-ctu-blue/60 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-semibold text-slate-900 group-hover:text-ctu-blue">{sign.word}</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            {sign.pos || (KIND_LABEL[sign.kind] ? t(KIND_LABEL[sign.kind]) : t("ký hiệu"))}
            {sign.kind !== "tu_thuong" && sign.pos && KIND_LABEL[sign.kind] ? ` · ${t(KIND_LABEL[sign.kind])}` : ""}
          </p>
        </div>
        <ChevronRightIcon className="h-5 w-5 shrink-0 text-slate-300 transition-colors group-hover:text-ctu-blue" aria-hidden="true" />
      </div>
      {/* Không có nghĩa thì để trống — 24 thẻ cùng lặp "chưa có giải nghĩa" là
          nhiễu; thẻ chi tiết mới là chỗ nói rõ điều đó. */}
      {sign.definition && (
        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-slate-600">{sign.definition}</p>
      )}
      <div className="flex-1" />
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {regions.length > 0 ? (
          regions.map((v) => (
            <span key={v.code} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{v.region_name}</span>
          ))
        ) : (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">{t("Chung")}</span>
        )}
        {sign.own_sample_count > 0 && (
          <Badge variant="success" size="sm" className="ml-auto">{t("thử được")}</Badge>
        )}
      </div>
    </Link>
  );
}
