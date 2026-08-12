import { useEffect, useState, type ReactNode } from "react";
import { useToast } from "../hooks/useToast";
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
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Badge({ tone, children }: { tone: "green" | "gray" | "red" | "blue"; children: ReactNode }) {
  const tones: Record<string, string> = {
    green: "bg-sky-100 text-sky-800 border-sky-200",
    gray: "bg-slate-100 text-slate-700 border-slate-200",
    red: "bg-red-100 text-red-800 border-red-200",
    blue: "bg-ctu-blue/10 text-ctu-blue border-ctu-blue/30",
  };
  return (
    <span className={`inline-flex items-center border px-2 py-0.5 rounded-full text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export default function SotAdminPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [overview, setOverview] = useState<SotOverview | null>(null);
  const [remote, setRemote] = useState<SotRemote | null>(null);
  const [schemaCols, setSchemaCols] = useState<Record<string, string[]>>({});
  const [showSchema, setShowSchema] = useState(false);
  const [loading, setLoading] = useState(true);
  const [remoteLoading, setRemoteLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<SotVerifyResult | null>(null);

  // register form
  const [mode, setMode] = useState<"public_key" | "generate">("public_key");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [publicKey, setPublicKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<{ name: string; private_key: string; hint?: string } | null>(null);

  const loadOverview = async () => {
    try {
      setLoading(true);
      setOverview(await getSotOverview());
    } catch (e: any) {
      toast.error(friendlyError(e, "Không tải được thông tin SOT"));
    } finally {
      setLoading(false);
    }
  };

  const loadRemote = async () => {
    try {
      setRemoteLoading(true);
      setRemote(await getSotRemote());
    } catch (e: any) {
      setRemote({ available: false, error: friendlyError(e, "Lỗi đọc Drive") });
    } finally {
      setRemoteLoading(false);
    }
  };

  useEffect(() => {
    loadOverview();
    loadRemote();
    getSotSchema().then((s) => setSchemaCols(s.required_columns || {})).catch(() => {});
  }, []);

  const doVerify = async () => {
    try {
      setVerifying(true);
      const res = await runSotVerify();
      setVerifyResult(res);
      if (res.ok) toast.success(`Verify OK — ${res.version ?? res.status}`);
      else toast.error("Verify thất bại");
    } catch (e: any) {
      toast.error(friendlyError(e, "Verify lỗi"));
    } finally {
      setVerifying(false);
    }
  };

  const doRegister = async () => {
    if (!name.trim()) {
      toast.error("Nhập tên máy");
      return;
    }
    if (mode === "public_key" && !publicKey.trim()) {
      toast.error("Dán public key của máy");
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
      loadOverview();
    } catch (e: any) {
      toast.error(friendlyError(e, "Đăng ký thất bại"));
    } finally {
      setSubmitting(false);
    }
  };

  const doRevoke = async (m: SotMachine) => {
    if (!m.fingerprint) return;
    if (!window.confirm(t("Thu hồi quyền SOT của máy \"{name}\"?", { name: m.name }))) return;
    try {
      await revokeSotMachine(m.fingerprint);
      toast.success(t("Đã thu hồi \"{name}\"", { name: m.name }));
      loadOverview();
    } catch (e: any) {
      toast.error(friendlyError(e, "Thu hồi thất bại"));
    }
  };

  if (loading && !overview) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  const dbc = overview?.db_counts ?? {};

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-6 animate-fade-in">
      <PageHeader
        title={t("Quản lý SOT & thiết bị")}
        subtitle={t("Source of Truth: máy được cấp quyền, dữ liệu đã publish, schema.")}
        actions={
          <>
            <button
              onClick={() => { loadOverview(); loadRemote(); }}
              className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-700 font-medium hover:bg-slate-50 transition-colors"
            >
              {t("Làm mới")}
            </button>
            <button
              onClick={doVerify}
              disabled={verifying}
              className="px-3 py-2 rounded-lg bg-ctu-blue text-white text-sm font-medium hover:bg-ctu-blue/90 disabled:opacity-50 transition-colors"
            >
              {verifying ? t("Đang verify…") : "Verify SOT"}
            </button>
          </>
        }
      />

      {verifyResult && (
        <div className={`rounded-lg border p-3 text-sm ${verifyResult.ok ? "bg-sky-50 border-sky-200 text-sky-800" : "bg-red-50 border-red-200 text-red-700"}`}>
          {verifyResult.ok
            ? `Verify OK — version=${verifyResult.version ?? verifyResult.status}, signed_by=${verifyResult.signed_by ?? "?"}`
            : t("Không xác minh được: {error}", { error: verifyResult.error })}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title={t("Version đã publish")}>
          {remoteLoading ? (
            <span className="text-slate-400">…</span>
          ) : remote?.available === false ? (
            <Badge tone="red">{t("Drive lỗi")}</Badge>
          ) : remote?.published ? (
            <div>
              <div className="text-lg font-bold text-slate-900">{remote.version}</div>
              <div className="mt-1 text-xs text-slate-500">
                {remote.trusted ? <Badge tone="green">signed: {remote.signed_by}</Badge> : <Badge tone="red">{t("chữ ký lạ")}</Badge>}
              </div>
            </div>
          ) : (
            <Badge tone="gray">{t("Chưa publish")}</Badge>
          )}
        </Card>
        <Card title={t("Máy này")}>
          {overview?.this_machine.is_writer ? (
            <div>
              <Badge tone="green">{t("Máy ghi")}</Badge>
              <div className="text-xs text-slate-500 mt-1.5 font-mono break-all">{overview.this_machine.fingerprint}</div>
            </div>
          ) : (
            <Badge tone="gray">{t("Read-only (không có khóa)")}</Badge>
          )}
        </Card>
        <Card title={t("Phiên bản lược đồ")}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{overview?.schema_version ?? "—"}</div>
        </Card>
        <Card title={t("Máy được cấp quyền")}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{overview?.machines.length ?? 0}</div>
        </Card>
      </div>

      {/* DB counts */}
      <Card title={t("Dữ liệu trong database (live)")}>
        <div className="grid grid-cols-3 gap-4">
          {/* Tham số tên `t` sẽ CHE hàm dịch `t` của cả component — lỗi hiện ra
              ở dòng khác chỗ gây ra nó. Đặt tên `kind`. */}
          {(["classes", "samples", "raw_uploads"] as const).map((kind) => (
            <div key={kind} className="text-center">
              <div className="text-2xl font-bold text-slate-900 tabular-nums">{dbc[kind] >= 0 ? dbc[kind] : "?"}</div>
              <div className="text-xs text-slate-500 mt-0.5">{kind === "classes" ? t("nhãn (classes)") : kind}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Remote CSV files */}
      {remote?.published && remote.files && (
        <Card title={t("File CSV trong {version} (từ manifest)", { version: remote.version })}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-4 font-semibold">{t("Tệp")}</th>
                  <th className="py-2 pr-4 font-semibold">{t("Số dòng")}</th>
                  <th className="py-2 font-semibold">sha256</th>
                </tr>
              </thead>
              <tbody>
                {remote.files.map((f) => (
                  <tr key={f.name} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-4 font-mono text-slate-800">{f.name}</td>
                    <td className="py-2 pr-4 text-slate-700 tabular-nums">{f.rows ?? "—"}</td>
                    <td className="py-2 font-mono text-xs text-slate-500 truncate max-w-[220px]" title={f.sha256}>{f.sha256.slice(0, 16)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Machines */}
      <Card title={t("Máy được cấp quyền SOT")}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200">
                <th className="py-2 pr-4 font-semibold">{t("Tên")}</th>
                <th className="py-2 pr-4 font-semibold">{t("Dấu vân khoá")}</th>
                <th className="py-2 pr-4 font-semibold">{t("Nguồn")}</th>
                <th className="py-2 pr-4 font-semibold">{t("Thêm bởi / lúc")}</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {(overview?.machines ?? []).map((m) => (
                <tr key={m.fingerprint ?? m.name} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-4 font-medium text-slate-900">
                    {m.name}
                    {m.note && <div className="text-xs text-slate-400 font-normal">{m.note}</div>}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-600 break-all">{m.fingerprint}</td>
                  <td className="py-2 pr-4">
                    {m.source === "committed" ? <Badge tone="blue">{t("đã ghi trong mã nguồn")}</Badge> : <Badge tone="gray">db</Badge>}
                  </td>
                  <td className="py-2 pr-4 text-xs text-slate-500">
                    {m.added_by ?? "—"}<br />{fmtDate(m.added_at)}
                  </td>
                  <td className="py-2 text-right">
                    {m.revocable ? (
                      <button onClick={() => doRevoke(m)} className="text-red-600 hover:text-red-800 text-xs font-medium">
                        {t("Thu hồi")}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400" title={t("Nằm trong authorized_keys.json (git)")}>{t("khóa")}</span>
                    )}
                  </td>
                </tr>
              ))}
              {(overview?.machines ?? []).length === 0 && (
                <tr><td colSpan={5} className="py-4 text-center text-slate-400">{t("Chưa có máy nào")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Register */}
      <Card title={t("Đăng ký máy mới")}>
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setMode("public_key")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === "public_key" ? "bg-ctu-blue text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
          >
            {t("Dán public key")}
          </button>
          <button
            onClick={() => setMode("generate")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === "generate" ? "bg-ctu-blue text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
          >
            {t("Server tạo khóa")}
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Tên máy (vd: desktop-lab)")}
            className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-ctu-blue/30 focus:border-ctu-blue"
          />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("Ghi chú (tuỳ chọn)")}
            className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-ctu-blue/30 focus:border-ctu-blue"
          />
        </div>
        {mode === "public_key" && (
          <textarea
            value={publicKey}
            onChange={(e) => setPublicKey(e.target.value)}
            placeholder={t("Public key base64 (máy chạy `python -m app.sot.cli keygen` để lấy)")}
            rows={2}
            className="mt-3 w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 font-mono placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-ctu-blue/30 focus:border-ctu-blue"
          />
        )}
        {mode === "generate" && (
          <p className="mt-3 text-xs text-amber-600">
            {t("Server sẽ sinh cặp khóa và hiển thị khóa riêng")} <b>{t("một lần duy nhất")}</b> {t("để bạn tải về máy writer.")}
          </p>
        )}
        <button
          onClick={doRegister}
          disabled={submitting}
          className="mt-3 px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-medium hover:bg-sky-700 disabled:opacity-50 transition-colors"
        >
          {submitting ? t("Đang đăng ký…") : t("Đăng ký")}
        </button>
      </Card>

      {/* Schema viewer — table/column inventory only. The raw CREATE TABLE
          listing used to be rendered here; the API no longer returns it, so the
          DDL cannot leak through a screenshot or a shared screen. */}
      <Card title={t("Lược đồ cơ sở dữ liệu (SOT)")}>
        <button onClick={() => setShowSchema((s) => !s)} className="text-sm text-ctu-blue font-medium hover:underline">
          {showSchema ? t("Ẩn") : t("Hiện")} danh sách bảng &amp; cột
        </button>
        {showSchema && (
          <div className="mt-3 max-h-96 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
            {Object.keys(schemaCols).length === 0 ? (
              <p className="text-xs text-slate-500">…</p>
            ) : (
              Object.entries(schemaCols).map(([table, cols]) => (
                <div key={table} className="mb-3 last:mb-0">
                  <p className="text-xs font-semibold text-slate-700">
                    {table}
                    <span className="ml-2 font-normal text-slate-400">
                      {t("{n} cột", { n: cols.length })}
                    </span>
                  </p>
                  <p className="mt-1 break-words text-xs leading-relaxed text-slate-600">
                    {cols.join(", ")}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      {/* Generated private key modal */}
      {generatedKey && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setGeneratedKey(null)}>
          <div className="bg-white rounded-xl p-6 max-w-lg w-full shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-slate-900">Khóa riêng của "{generatedKey.name}"</h3>
            <p className="text-sm text-amber-600 mt-1">
              {generatedKey.hint || t("Lưu ngay — chỉ hiển thị một lần. Server không lưu khóa riêng.")}
            </p>
            <textarea
              readOnly
              value={generatedKey.private_key}
              rows={3}
              className="mt-3 w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs text-slate-800 font-mono"
              onFocus={(e) => e.target.select()}
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => { navigator.clipboard?.writeText(generatedKey.private_key); toast.success("Đã copy"); }}
                className="px-3 py-2 rounded-lg bg-ctu-blue text-white text-sm font-medium hover:bg-ctu-blue/90 transition-colors"
              >
                Copy
              </button>
              <button onClick={() => setGeneratedKey(null)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 font-medium hover:bg-slate-50 transition-colors">
                {t("Đã lưu, đóng")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
