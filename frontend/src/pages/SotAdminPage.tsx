/**
 * Dữ liệu chuẩn & đồng bộ — trang vận hành SOT.
 *
 * Bố cục (Đợt 2 kế hoạch UX 13/09/2026)
 * ---------------------------------------
 * Ba mục, theo thứ tự câu hỏi người vận hành thật sự đặt ra:
 *
 *   1. TÌNH TRẠNG  — dữ liệu chuẩn đang thế nào? Một câu kết luận (bảy trạng
 *      thái riêng biệt, xem `utils/sotStatus`), thời điểm kiểm tra, việc cần
 *      làm, rồi ba con số nói bằng chữ thường.
 *   2. MÁY ĐƯỢC CẤP QUYỀN — ai được công bố? Danh sách + đăng ký máy mới gấp
 *      lại, có giải thích ai cần làm việc này và khoá riêng phải để đâu.
 *   3. NÂNG CAO — fingerprint, sha256, schema, số dòng thô. Gấp lại mặc định:
 *      vẫn có, không xoá, nhưng không đứng chắn trước câu trả lời.
 *
 * Thuật ngữ đổi theo bảng §5 của kế hoạch: "Verify SOT" → "Kiểm tra bản dữ
 * liệu chuẩn", "Máy ghi/Read-only" → "Có quyền công bố/Chỉ đọc",
 * "raw_uploads/samples/classes" → "Tệp ghi hình gốc/Mẫu dữ liệu/Nhãn".
 * Cơ chế ký số, API và phạm vi dữ liệu KHÔNG đổi — chỉ chữ trên màn hình đổi.
 */

import { useEffect, useState, type ReactNode } from "react";

import PrivateKeyModal from "../components/sot/PrivateKeyModal";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import {
  getSotOverview,
  getSotRemote,
  getSotSchema,
  runSotVerify,
  registerSotMachine,
  revokeSotMachine,
  type SotMachine,
  type SotOverview,
  type SotRemote,
  type SotVerifyResult,
} from "../api/sot";
import { useToast } from "../hooks/useToast";
import { useI18n } from "../i18n";
import { friendlyError } from "../lib/errors";
import { toneClasses, type StatusTone } from "../theme/status";
import { sotConclusion, type SotConclusion } from "../utils/sotStatus";

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d.getTime()) ? String(v) : d.toLocaleString("vi-VN");
}

function fmtNumber(n: number | undefined): string {
  return typeof n === "number" && n >= 0 ? n.toLocaleString("vi-VN") : "—";
}

/** Sắc thái của kết luận → sắc thái của hệ thống (có biểu tượng đi kèm). */
const CONCLUSION_TONE: Record<SotConclusion["tone"], StatusTone> = {
  neutral: "neutral",
  ok: "success",
  warn: "warning",
  bad: "danger",
};

function Section({ title, hint, children, actions }: {
  title: string;
  hint?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          {hint && <p className="mt-0.5 text-sm text-slate-500">{hint}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-1 text-sm text-slate-900">{children}</div>
    </div>
  );
}

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30";

export default function SotAdminPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [overview, setOverview] = useState<SotOverview | null>(null);
  const [remote, setRemote] = useState<SotRemote | null>(null);
  const [schemaCols, setSchemaCols] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [remoteLoading, setRemoteLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<SotVerifyResult | null>(null);
  /** Thời điểm lượt kiểm tra gần nhất KẾT THÚC — người đọc cần biết kết luận cũ bao nhiêu. */
  const [verifiedAt, setVerifiedAt] = useState<Date | null>(null);
  /** Lỗi tải tổng quan GIỮ TRÊN TRANG. Toast trôi đi rồi, trang vẫn phải nói được vì sao trống (SOT-02). */
  const [overviewError, setOverviewError] = useState<string | null>(null);

  // đăng ký máy
  const [mode, setMode] = useState<"public_key" | "generate">("public_key");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [publicKey, setPublicKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<{ name: string; private_key: string; hint?: string } | null>(null);

  const loadOverview = async () => {
    try {
      setLoading(true);
      setOverviewError(null);
      setOverview(await getSotOverview());
    } catch (e: unknown) {
      setOverviewError(friendlyError(e, t("Không tải được thông tin SOT")));
    } finally {
      setLoading(false);
    }
  };

  const loadRemote = async () => {
    try {
      setRemoteLoading(true);
      setRemote(await getSotRemote());
    } catch (e: unknown) {
      setRemote({ available: false, error: friendlyError(e, t("Lỗi đọc Drive")) });
    } finally {
      setRemoteLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
    void loadRemote();
    getSotSchema().then((s) => setSchemaCols(s.required_columns || {})).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy khi mở trang
  }, []);

  const doVerify = async () => {
    try {
      setVerifying(true);
      const res = await runSotVerify();
      setVerifyResult(res);
      setVerifiedAt(new Date());
      if (res.ok) toast.success(t("Kiểm tra đạt — bản {v}", { v: res.version ?? res.status ?? "" }));
      else toast.error(t("Kiểm tra không đạt"));
    } catch (e: unknown) {
      setVerifyResult({ ok: false, error: friendlyError(e, t("Không chạy được kiểm tra")) });
      setVerifiedAt(new Date());
    } finally {
      setVerifying(false);
    }
  };

  const doRegister = async () => {
    if (!name.trim()) {
      toast.error(t("Nhập tên máy"));
      return;
    }
    if (mode === "public_key" && !publicKey.trim()) {
      toast.error(t("Dán khoá công khai của máy"));
      return;
    }
    try {
      setSubmitting(true);
      const res = await registerSotMachine({
        name: name.trim(),
        note: note.trim() || undefined,
        mode,
        public_key: mode === "public_key" ? publicKey.trim() : undefined,
      });
      toast.success(t("Đã đăng ký máy \"{name}\"", { name: res.machine.name }));
      if (res.private_key) {
        setGeneratedKey({ name: res.machine.name ?? name, private_key: res.private_key, hint: res.private_key_hint });
      }
      setName("");
      setNote("");
      setPublicKey("");
      void loadOverview();
    } catch (e: unknown) {
      toast.error(friendlyError(e, t("Đăng ký thất bại")));
    } finally {
      setSubmitting(false);
    }
  };

  const doRevoke = async (m: SotMachine) => {
    if (!m.fingerprint) return;
    // Nói rõ TÁC ĐỘNG, không chỉ hỏi "có chắc không".
    if (!window.confirm(t("Thu hồi quyền công bố của máy \"{name}\"? Máy này sẽ không công bố được bản dữ liệu chuẩn mới; các bản đã công bố không bị ảnh hưởng.", { name: m.name ?? "" }))) return;
    try {
      await revokeSotMachine(m.fingerprint);
      toast.success(t("Đã thu hồi \"{name}\"", { name: m.name ?? "" }));
      void loadOverview();
    } catch (e: unknown) {
      toast.error(friendlyError(e, t("Thu hồi thất bại")));
    }
  };

  if (loading && !overview && !overviewError) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  const dbc = overview?.db_counts ?? {};
  const machines = overview?.machines ?? [];
  const conclusion = sotConclusion({ remote, remoteLoading, verify: verifyResult, verifying });
  const tone = CONCLUSION_TONE[conclusion.tone];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 animate-fade-in sm:p-6">
      <PageHeader
        title={t("Dữ liệu chuẩn & đồng bộ")}
        subtitle={t("Quản lý bản dữ liệu chuẩn và các máy được phép công bố bản đó.")}
        actions={
          <>
            <Button variant="secondary" onClick={() => { void loadOverview(); void loadRemote(); }}>
              {t("Làm mới")}
            </Button>
            <Button onClick={() => void doVerify()} disabled={verifying}>
              {verifying ? t("Đang kiểm tra…") : t("Kiểm tra bản dữ liệu chuẩn")}
            </Button>
          </>
        }
      />

      {overviewError && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span>{t("Không tải được thông tin máy và dữ liệu: {error}", { error: overviewError })}</span>
          <Button size="sm" variant="secondary" onClick={() => void loadOverview()}>{t("Thử lại")}</Button>
        </div>
      )}

      {/* ---------------- 1. Tình trạng ---------------- */}
      <Section title={t("Tình trạng dữ liệu chuẩn")}>
        {/* Kết luận một câu — trả lời "dữ liệu chuẩn đang thế nào?" trước mọi con số.
            Chữ + biểu tượng + thời điểm; màu chỉ là kênh phụ. */}
        <div
          role="status"
          aria-live="polite"
          data-testid="sot-conclusion"
          data-kind={conclusion.kind}
          className={`rounded-xl border p-4 ${toneClasses(tone, "soft")}`}
        >
          <div className="flex items-start gap-3">
            <Badge variant={tone} size="md" className="shrink-0">
              {t(
                conclusion.tone === "ok" ? "Ổn" :
                conclusion.tone === "warn" ? "Cần chú ý" :
                conclusion.tone === "bad" ? "Có vấn đề" : "Đang kiểm tra",
              )}
            </Badge>
            <div className="min-w-0">
              <p className="text-base font-semibold">{t(conclusion.headline)}</p>
              <p className="mt-1 text-xs opacity-80">
                {verifiedAt
                  ? t("Kiểm tra lúc {when}", { when: verifiedAt.toLocaleString("vi-VN") })
                  : t("Chưa chạy kiểm tra toàn vẹn trong phiên này")}
              </p>
              {conclusion.nextStep && (
                <p className="mt-2 text-sm">
                  <span className="font-medium">{t("Việc cần làm:")}</span> {t(conclusion.nextStep)}
                </p>
              )}
              {verifyResult && !verifyResult.ok && verifyResult.error && (
                <p className="mt-2 font-mono text-xs opacity-80">{verifyResult.error}</p>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Fact label={t("Bản dữ liệu đã công bố")}>
            {remoteLoading ? (
              <span className="text-slate-400">…</span>
            ) : remote?.available === false ? (
              <Badge variant="danger" size="sm">{t("Không kết nối được kho")}</Badge>
            ) : remote?.published ? (
              <>
                <span className="font-semibold">{remote.version}</span>
                <span className="block text-xs text-slate-500">
                  {remote.trusted
                    ? t("Nguồn: {m}", { m: remote.signed_by ?? "" })
                    : t("Không xác minh được nguồn")}
                  {remote.created_at ? ` · ${fmtDate(remote.created_at)}` : ""}
                </span>
              </>
            ) : (
              <Badge variant="neutral" size="sm">{t("Chưa công bố")}</Badge>
            )}
          </Fact>
          <Fact label={t("Máy hiện tại")}>
            {overview?.this_machine.is_writer
              ? <Badge variant="success" size="sm">{t("Có quyền công bố")}</Badge>
              : <Badge variant="neutral" size="sm">{t("Chỉ đọc")}</Badge>}
          </Fact>
          <Fact label={t("Dữ liệu đang có trong hệ thống")}>
            <span className="font-semibold tabular-nums">{fmtNumber(dbc.samples)}</span> {t("mẫu")}
            {" · "}
            <span className="font-semibold tabular-nums">{fmtNumber(dbc.classes)}</span> {t("nhãn")}
            {" · "}
            <span className="font-semibold tabular-nums">{fmtNumber(dbc.raw_uploads)}</span> {t("tệp ghi hình gốc")}
          </Fact>
        </div>
      </Section>

      {/* ---------------- 2. Máy được cấp quyền ---------------- */}
      <Section
        title={t("Máy được cấp quyền công bố")}
        hint={t("Chỉ những máy trong danh sách này mới ký và công bố được bản dữ liệu chuẩn. Máy khác chỉ đọc.")}
      >
        {machines.length === 0 ? (
          <p className="text-sm text-slate-500">{t("Chưa có máy nào được cấp quyền.")}</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {machines.map((m) => (
              <li key={m.fingerprint ?? m.name ?? ""} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-medium text-slate-900">{m.name}</p>
                  <p className="text-xs text-slate-500">
                    {m.source === "committed" ? t("Khai báo trong mã nguồn") : t("Đăng ký qua giao diện")}
                    {m.added_by ? ` · ${t("bởi {who}", { who: m.added_by })}` : ""}
                    {m.added_at ? ` · ${fmtDate(m.added_at)}` : ""}
                  </p>
                  {m.note && <p className="mt-0.5 text-xs text-slate-500">{m.note}</p>}
                </div>
                {m.revocable ? (
                  <Button size="sm" variant="ghost" className="text-red-700" onClick={() => void doRevoke(m)}>
                    {t("Thu hồi quyền")}
                  </Button>
                ) : (
                  <span className="text-xs text-slate-400">{t("Không thu hồi được từ giao diện")}</span>
                )}
              </li>
            ))}
          </ul>
        )}

        <details className="mt-4 rounded-lg border border-slate-200 bg-slate-50">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-800">
            {t("Đăng ký máy mới")}
          </summary>
          <div className="space-y-3 px-4 pb-4">
            <p className="text-sm text-slate-600">
              {t("Dành cho người vận hành khi có một máy mới cần được phép công bố. Khoá công khai được lưu ở đây; khoá riêng chỉ nằm trên máy đó và không bao giờ được gửi lên máy chủ.")}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-slate-700">{t("Tên máy")}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("ví dụ: may-phong-lab")} className={INPUT} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-slate-700">{t("Ghi chú (tuỳ chọn)")}</span>
                <input value={note} onChange={(e) => setNote(e.target.value)} className={INPUT} />
              </label>
            </div>
            <fieldset>
              <legend className="mb-1 text-sm font-medium text-slate-700">{t("Máy đó đã có khoá chưa?")}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm ${mode === "public_key" ? "border-ctu-blue bg-white" : "border-slate-200"}`}>
                  <input type="radio" name="sot-mode" checked={mode === "public_key"} onChange={() => setMode("public_key")} className="mt-0.5" />
                  <span>
                    <span className="block font-medium text-slate-900">{t("Đã có — dán khoá công khai")}</span>
                    <span className="block text-xs text-slate-500">{t("Trên máy đó chạy `python -m app.sot.cli keygen` rồi dán khoá công khai vào đây.")}</span>
                  </span>
                </label>
                <label className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm ${mode === "generate" ? "border-ctu-blue bg-white" : "border-slate-200"}`}>
                  <input type="radio" name="sot-mode" checked={mode === "generate"} onChange={() => setMode("generate")} className="mt-0.5" />
                  <span>
                    <span className="block font-medium text-slate-900">{t("Chưa có — tạo khoá trên máy chủ")}</span>
                    <span className="block text-xs text-slate-500">{t("Khoá riêng hiện đúng một lần để bạn chép sang máy đó. Đóng hộp là mất.")}</span>
                  </span>
                </label>
              </div>
            </fieldset>
            {mode === "public_key" && (
              <textarea
                value={publicKey}
                onChange={(e) => setPublicKey(e.target.value)}
                placeholder={t("Khoá công khai (base64)")}
                aria-label={t("Khoá công khai")}
                rows={2}
                className={`${INPUT} font-mono`}
              />
            )}
            <Button onClick={() => void doRegister()} disabled={submitting}>
              {submitting ? t("Đang đăng ký…") : t("Đăng ký máy")}
            </Button>
          </div>
        </details>
      </Section>

      {/* ---------------- 3. Nâng cao ---------------- */}
      <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <summary className="cursor-pointer px-5 py-4 text-base font-semibold text-slate-900">
          {t("Chi tiết kỹ thuật")}
        </summary>
        <div className="space-y-5 px-5 pb-5 text-sm">
          <div className="grid gap-3 sm:grid-cols-2">
            <Fact label={t("Phiên bản cấu trúc dữ liệu")}>
              <span className="tabular-nums">{overview?.schema_version ?? "—"}</span>
              {remote?.schema_version != null && remote.schema_version !== overview?.schema_version && (
                <span className="ml-2 text-xs text-amber-700">{t("bản đã công bố dùng v{v}", { v: String(remote.schema_version) })}</span>
              )}
            </Fact>
            <Fact label={t("Mã khoá của máy hiện tại")}>
              <span className="break-all font-mono text-xs">{overview?.this_machine.fingerprint ?? t("(máy này không có khoá)")}</span>
            </Fact>
          </div>

          {machines.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-slate-700">{t("Mã khoá của các máy được cấp quyền")}</p>
              <ul className="space-y-1">
                {machines.map((m) => (
                  <li key={`fp-${m.fingerprint ?? m.name ?? ""}`} className="flex flex-wrap gap-x-3 text-xs">
                    <span className="font-medium text-slate-800">{m.name}</span>
                    <span className="break-all font-mono text-slate-500">{m.fingerprint}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {remote?.published && remote.files && (
            <div>
              <p className="mb-1 font-medium text-slate-700">{t("Danh sách tệp của bản {v}", { v: remote.version ?? "" })}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                      <th className="py-2 pr-4 font-semibold">{t("Tệp")}</th>
                      <th className="py-2 pr-4 font-semibold">{t("Số dòng")}</th>
                      <th className="py-2 font-semibold">{t("Mã kiểm tra (sha256)")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {remote.files.map((f) => (
                      <tr key={f.name} className="border-b border-slate-100 last:border-0">
                        <td className="py-2 pr-4 font-mono text-slate-800">{f.name}</td>
                        <td className="py-2 pr-4 tabular-nums text-slate-700">{f.rows ?? "—"}</td>
                        <td className="max-w-[220px] truncate py-2 font-mono text-xs text-slate-500" title={f.sha256}>{f.sha256.slice(0, 16)}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div>
            <p className="mb-1 font-medium text-slate-700">{t("Bảng và cột mà bản dữ liệu chuẩn yêu cầu")}</p>
            {Object.keys(schemaCols).length === 0 ? (
              <p className="text-xs text-slate-500">…</p>
            ) : (
              <div className="max-h-80 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
                {Object.entries(schemaCols).map(([table, cols]) => (
                  <div key={table} className="mb-3 last:mb-0">
                    <p className="text-xs font-semibold text-slate-700">
                      {table}
                      <span className="ml-2 font-normal text-slate-400">{t("{n} cột", { n: cols.length })}</span>
                    </p>
                    <p className="mt-1 break-words text-xs leading-relaxed text-slate-600">{cols.join(", ")}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </details>

      {/* Khoá riêng hiện một lần — xem components/sot/PrivateKeyModal (SOT-01). */}
      {generatedKey && (
        <PrivateKeyModal
          name={generatedKey.name}
          privateKey={generatedKey.private_key}
          hint={generatedKey.hint}
          onClose={() => setGeneratedKey(null)}
        />
      )}
    </div>
  );
}
