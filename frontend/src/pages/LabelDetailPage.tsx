/**
 * Chi tiết nhãn.
 *
 * @i18n-key-table — `TIER_LABELS` là bảng KHOÁ, dịch tại chỗ dựng.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import PageHeader from "../components/ui/PageHeader";
import Badge from "../components/ui/Badge";
import Modal from "../components/ui/Modal";
import ErrorBanner from "../components/ErrorBanner";
import LoadingScreen from "../components/LoadingScreen";
import EmptyState from "../components/ui/EmptyState";
import { getClassesList } from "../api/dataset";
import type { ClassRow } from "../types";
import {
  getLabelSessions,
  getSessionFrames,
  getPreviewStatus,
  previewVideoUrl,
  sampleDownloadUrl,
  deleteLabelSession,
  reassignLabelSession,
  type LabelSession,
  type LabelSessionsResponse,
} from "../api/labelDetail";
import { stabilizeSequence, type FramesData } from "../components/viewer/handData";
import { dialectLabel } from "../config/dialectLabels";
import { usePlayback } from "../components/viewer/usePlayback";
import { useRenderTier, type TierChoice } from "../components/viewer/useRenderTier";
import Skeleton2DPlayer from "../components/viewer/Skeleton2DPlayer";
import PlayerControls from "../components/viewer/PlayerControls";
import { Trans, useI18n } from "../i18n";

// three.js (~150KB gz) stays out of the page chunk until a Tier-1 device
// actually renders the 3D view.
const Hand3DPlayer = lazy(() => import("../components/viewer/Hand3DPlayer"));

// The third hand-maintained dialect map found in this codebase, and the same
// story as the other two: it listed `mienTay`, which is not a dialect id in the
// registry and never had a class behind it, while any dialect approved through
// the registry could not appear. The slug is the label now — see
// config/dialectLabels.ts.

const TIER_LABELS: Record<Exclude<TierChoice, "auto">, string> = {
  "3d": "3D da thịt",
  "2d": "Khung xương 2D",
  video: "Video nhẹ (server)",
};

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

type PreviewState = "checking" | "rendering" | "ready" | "error";

export default function LabelDetailPage() {
  const { t } = useI18n();
  const { id: classUid = "" } = useParams();

  const [info, setInfo] = useState<LabelSessionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string>("");
  const [frames, setFrames] = useState<FramesData | null>(null);
  const [framesError, setFramesError] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<PreviewState>("checking");
  const [deletingId, setDeletingId] = useState<string>("");
  // Reassign ("đổi nhãn"): move a recording to a different existing label.
  const [reassignTarget, setReassignTarget] = useState<LabelSession | null>(null);
  const [labels, setLabels] = useState<ClassRow[]>([]);
  const [labelsLoading, setLabelsLoading] = useState(false);
  const [labelFilter, setLabelFilter] = useState("");
  const [reassignSaving, setReassignSaving] = useState(false);

  const tierState = useRenderTier();
  const { tier } = tierState;

  const playback = usePlayback(frames?.frames ?? 0, frames?.fps ?? 15);

  // Display-only de-jitter, shared by the 2D and 3D tiers so both show the same
  // motion. Off-switch kept because judging whether a sample is faulty means
  // looking at exactly what was stored, unsmoothed.
  const [stabilize, setStabilize] = useState(true);
  const viewFrames = useMemo(
    () =>
      frames && stabilize
        ? { ...frames, sequence: stabilizeSequence(frames.sequence) }
        : frames,
    [frames, stabilize]
  );

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLabelSessions(classUid);
      setInfo(data);
      setSelectedId((prev) => prev || data.sessions[0]?.session_id || "");
    } catch (err) {
      const e = err as { userMessage?: string; message?: string };
      setError(e.userMessage || e.message || t("Không tải được danh sách lần quay"));
    } finally {
      setLoading(false);
    }
  }, [classUid]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Delete a recording. The backend enforces ownership by auth_user_id (owner or
  // admin) and logs it; the button is only shown when session.can_manage is true.
  const handleDeleteSession = useCallback(
    async (session: LabelSession) => {
      const ok = window.confirm(
        `Xóa lần quay này của "${info?.label_original ?? t("nhãn")}"?\n` +
          t("{sample_count} mẫu sẽ được chuyển vào thùng rác.", { sample_count: session.sample_count }),
      );
      if (!ok) return;
      setDeletingId(session.session_id);
      setError(null);
      try {
        await deleteLabelSession(classUid, session.session_id);
        // Drop the selection if it pointed at the just-removed session, then
        // reload so the list + counts reflect the deletion.
        setSelectedId((prev) => (prev === session.session_id ? "" : prev));
        await loadSessions();
      } catch (err) {
        const e = err as { userMessage?: string; message?: string };
        setError(e.userMessage || e.message || t("Không xóa được lần quay"));
      } finally {
        setDeletingId("");
      }
    },
    [classUid, info, loadSessions],
  );

  // Open the "đổi nhãn" picker; lazy-load the label list on first open.
  const openReassign = useCallback(
    async (session: LabelSession) => {
      setReassignTarget(session);
      setLabelFilter("");
      if (labels.length === 0) {
        setLabelsLoading(true);
        const res = await getClassesList();
        if (res.ok) setLabels(res.data.items);
        setLabelsLoading(false);
      }
    },
    [labels.length],
  );

  const handleReassign = useCallback(
    async (targetClassUid: string) => {
      if (!reassignTarget) return;
      setReassignSaving(true);
      setError(null);
      try {
        await reassignLabelSession(classUid, reassignTarget.session_id, targetClassUid);
        setSelectedId((prev) => (prev === reassignTarget.session_id ? "" : prev));
        setReassignTarget(null);
        await loadSessions();
      } catch (err) {
        const e = err as { userMessage?: string; message?: string };
        setError(e.userMessage || e.message || t("Không đổi được nhãn cho lần quay"));
      } finally {
        setReassignSaving(false);
      }
    },
    [classUid, reassignTarget, loadSessions],
  );

  // Load the keypoint frames whenever the 2D/3D viewers need them.
  useEffect(() => {
    if (!selectedId || tier === "video") return;
    let cancelled = false;
    setFrames(null);
    setFramesError(null);
    getSessionFrames(classUid, selectedId)
      .then((data) => {
        if (!cancelled) setFrames(data);
      })
      .catch((err) => {
        const e = err as { userMessage?: string; message?: string };
        if (!cancelled) setFramesError(e.userMessage || e.message || t("Không tải được dữ liệu khung hình"));
      });
    return () => {
      cancelled = true;
    };
  }, [classUid, selectedId, tier]);

  // Tier 3: probe the server preview; a 202 means "render enqueued" → poll.
  useEffect(() => {
    if (!selectedId || tier !== "video") return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;

    const probe = async () => {
      try {
        const status = await getPreviewStatus(classUid, selectedId);
        if (cancelled) return;
        if (status === "ready") {
          setPreviewState("ready");
          return;
        }
        setPreviewState("rendering");
        if (attempts++ < 40) timer = setTimeout(probe, 3000);
        else setPreviewState("error");
      } catch {
        if (!cancelled) setPreviewState("error");
      }
    };

    setPreviewState("checking");
    probe();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [classUid, selectedId, tier]);

  if (loading) return <LoadingScreen />;

  if (error || !info) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-4">
        <ErrorBanner message={error || t("Không tải được dữ liệu nhãn")} />
        <button type="button" onClick={loadSessions} className="btn-secondary text-sm px-4 py-2 rounded-lg">
          {t("Thử lại")}
        </button>
      </div>
    );
  }

  const selected = info.sessions.find((s) => s.session_id === selectedId) || null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <PageHeader
        breadcrumb={[{ label: t("Thư viện nhãn"), href: "/labels" }, info.label_original]}
        title={info.label_original}
        subtitle={t("{p1} · {count} lần quay đã thu thập", { p1: dialectLabel(info.dialect), count: info.count })}
      />

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* ------- Left: sessions & timeline ------- */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
            {t("Các lần quay (Sessions)")}
          </h2>

          {info.sessions.length === 0 && (
            <EmptyState
              title={t("Chưa có lần quay nào")}
              description={t("Nhãn này chưa có dữ liệu được thu thập.")}
            />
          )}

          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1" data-testid="session-list">
            {info.sessions.map((session, index) => (
              <SessionCard
                key={session.session_id}
                session={session}
                index={info.sessions.length - index}
                active={session.session_id === selectedId}
                deleting={deletingId === session.session_id}
                onSelect={() => setSelectedId(session.session_id)}
                onDelete={() => handleDeleteSession(session)}
                onReassign={() => openReassign(session)}
              />
            ))}
          </div>
        </div>

        {/* ------- Right: motion player ------- */}
        <div>
          <div className="bg-slate-900 rounded-2xl shadow-lg overflow-hidden">
            <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-slate-700/60">
              <span className="text-slate-200 text-sm font-medium flex-1 min-w-[10rem] truncate">
                {selected
                  ? t("Người đóng góp: {ai}", { ai: selected.username || selected.user_id || t("Ẩn danh") })
                  : t("Chọn một lần quay")}
              </span>

              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={tierState.eco}
                  onChange={(e) => tierState.setEco(e.target.checked)}
                  className="accent-ctu-blue"
                />
                {t("Eco (tiết kiệm máy)")}
              </label>

              <select
                value={tierState.choice}
                onChange={(e) => tierState.setChoice(e.target.value as TierChoice)}
                aria-label={t("Chất lượng hiển thị")}
                className="bg-slate-700 text-slate-100 text-xs rounded-lg px-2 py-1.5 border border-slate-600 cursor-pointer"
              >
                <option value="auto">{t("Tự động ({che_do})", { che_do: t(TIER_LABELS[tier]) })}</option>
                <option value="3d">{t(TIER_LABELS["3d"])}</option>
                <option value="2d">{t(TIER_LABELS["2d"])}</option>
                <option value="video">{t(TIER_LABELS.video)}</option>
              </select>

              {tier !== "video" && (
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={stabilize}
                    onChange={(e) => setStabilize(e.target.checked)}
                    className="cursor-pointer accent-sky-500"
                  />
                  {t("Giảm rung")}
                </label>
              )}
            </div>

            {tierState.downgraded && tierState.choice === "auto" && (
              <div className="px-4 py-2 text-xs text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
                {t("Máy đang chậm/nóng — đã tự chuyển về chế độ nhẹ hơn. Bạn có thể chọn lại ở menu Chất lượng.")}
              </div>
            )}

            {/* Older samples stored only the model's input. Say so, instead of
                letting a flattened, artificially separated pair of hands look
                like a faithful replay of what was recorded. */}
            {frames?.landmark_source === "normalized" && tier !== "video" && (
              <div className="px-4 py-2 text-xs text-slate-300 bg-slate-700/40 border-b border-slate-600/50">
                <Trans
                  k="Mẫu này chỉ lưu dữ liệu đã chuẩn hoá cho mô hình: mỗi bàn tay đã bị dời về gốc cổ tay và co giãn riêng. Vì vậy {matgi} — hai tay được xếp cạnh nhau để xem cho rõ, không phải vị trí lúc quay."
                  vars={{
                    matgi: (
                      <strong>
                        {t("khoảng cách thật giữa hai tay và độ sâu không còn")}
                      </strong>
                    ),
                  }}
                />
              </div>
            )}

            {/* Depth is the one thing the 3D view cannot fake. Samples recorded
                before the capture side read MediaPipe's world landmarks carry
                only its image-space z, which is a relative regression spanning
                ~20% of a hand's own width — so those hands really are flatter
                than the signer's were, and that is a property of the recording
                rather than of this view. */}
            {tier === "3d" && frames && !frames.sequence_world && (
              <div className="px-4 py-2 text-xs text-slate-300 bg-slate-700/40 border-b border-slate-600/50">
                <Trans
                  k="Mẫu này không có toạ độ 3D thật (chỉ thu trước khi hệ thống lưu {toado}), nên {chieusau} so với lúc ký. Hình dạng và chuyển động vẫn đúng."
                  vars={{
                    toado: <em>{t("toạ độ trong không gian thật")}</em>,
                    chieusau: <strong>{t("chiều sâu bị dẹp")}</strong>,
                  }}
                />
              </div>
            )}

            {!selected ? (
              <div className="aspect-square flex items-center justify-center text-slate-400 text-sm">
                {t("Chọn một lần quay ở danh sách bên trái để xem lại chuyển động.")}
              </div>
            ) : tier === "video" ? (
              <VideoTier
                classUid={classUid}
                sessionId={selected.session_id}
                state={previewState}
              />
            ) : framesError ? (
              <div className="aspect-square flex items-center justify-center px-6">
                <p className="text-red-300 text-sm text-center">{framesError}</p>
              </div>
            ) : !frames ? (
              <div
                className="aspect-square flex items-center justify-center text-slate-400 text-sm animate-pulse"
                data-testid="frames-loading"
              >
                {t("Đang tải dữ liệu chuyển động…")}
              </div>
            ) : (
              <>
                {tier === "3d" ? (
                  <Suspense
                    fallback={
                      <div className="aspect-square flex items-center justify-center text-slate-400 text-sm animate-pulse">
                        {t("Đang khởi tạo khung cảnh 3D…")}
                      </div>
                    }
                  >
                    <Hand3DPlayer
                      data={viewFrames ?? frames}
                      frameRef={playback.frameRef}
                      onFps={tierState.reportFps}
                    />
                  </Suspense>
                ) : (
                  <Skeleton2DPlayer data={viewFrames ?? frames} frame={playback.frame} />
                )}
                <PlayerControls
                  frame={playback.frame}
                  frameCount={frames.frames}
                  playing={playback.playing}
                  speed={playback.speed}
                  onToggle={playback.toggle}
                  onSeek={playback.seek}
                  onSpeed={playback.setSpeed}
                />
              </>
            )}
          </div>

          <p className="mt-3 text-xs text-slate-500">
            {t("Trình xem chỉ hiển thị đúng dữ liệu tọa độ đã thu (.npz) — không dùng video quay gốc, nên danh tính người đóng góp luôn được bảo vệ.")}
          </p>
        </div>
      </div>

      <Modal
        isOpen={!!reassignTarget}
        onClose={() => {
          if (!reassignSaving) setReassignTarget(null);
        }}
        title={t("Đổi nhãn cho lần quay")}
        size="md"
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            {t("Chọn nhãn đúng để chuyển lần quay này sang. Dữ liệu (.npz) sẽ được di chuyển sang nhãn mới.")}
          </p>
          <input
            type="text"
            value={labelFilter}
            onChange={(e) => setLabelFilter(e.target.value)}
            placeholder={t("Tìm nhãn…")}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ctu-blue"
            autoFocus
          />
          {labelsLoading ? (
            <div className="py-6 text-center text-sm text-slate-400 animate-pulse">
              {t("Đang tải danh sách nhãn…")}
            </div>
          ) : (
            <div className="max-h-[45vh] overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg">
              {labels
                .filter((c) => c.class_uid !== info.class_uid)
                .filter((c) => {
                  const q = labelFilter.trim().toLowerCase();
                  if (!q) return true;
                  return (
                    (c.label_original || "").toLowerCase().includes(q) ||
                    (c.slug || "").toLowerCase().includes(q)
                  );
                })
                .slice(0, 100)
                .map((c) => (
                  <button
                    key={c.class_uid}
                    type="button"
                    disabled={reassignSaving}
                    onClick={() => handleReassign(c.class_uid)}
                    className="w-full text-left px-3 py-2 hover:bg-ctu-blue/5 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-between gap-2"
                  >
                    <span className="text-sm font-medium text-slate-800 truncate">
                      {c.label_original}
                    </span>
                    <span className="text-[11px] text-slate-400 whitespace-nowrap">
                      {c.language || ""} · {dialectLabel(c.dialect)}
                    </span>
                  </button>
                ))}
              {labels.filter((c) => c.class_uid !== info.class_uid).length === 0 && (
                <div className="py-6 text-center text-sm text-slate-400">
                  {t("Không có nhãn nào khác.")}
                </div>
              )}
            </div>
          )}
          {reassignSaving && (
            <div className="text-sm text-ctu-blue animate-pulse">{t("Đang chuyển lần quay…")}</div>
          )}
        </div>
      </Modal>
    </div>
  );
}

function SessionCard({
  session,
  index,
  active,
  deleting,
  onSelect,
  onDelete,
  onReassign,
}: {
  session: LabelSession;
  index: number;
  active: boolean;
  deleting: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onReassign: () => void;
}) {
  const { t } = useI18n();
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer ${
        active
          ? "border-ctu-blue bg-ctu-blue/5 ring-1 ring-ctu-blue shadow-sm"
          : "border-slate-200 bg-white hover:border-ctu-blue/50 hover:shadow-sm"
      }`}
      data-testid={`session-card-${session.session_id}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-800 text-sm flex items-center gap-1.5">
          Lần quay {index}
          {session.is_owner && (
            <span className="text-[10px] font-medium text-ctu-blue bg-ctu-blue/10 px-1.5 py-0.5 rounded">
              {t("của bạn")}
            </span>
          )}
        </span>
        <div className="flex items-center gap-1">
          <Badge size="sm" variant="info">
            {session.sample_count} mẫu
          </Badge>
          {session.has_preview && (
            <Badge size="sm" variant="success">
              {t("video nhẹ")}
            </Badge>
          )}
        </div>
      </div>
      <p className="mt-1 text-xs text-slate-600 truncate">
        {session.username || session.user_id || t("Ẩn danh")} · {formatDate(session.created_at)}
      </p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-slate-400">
          {session.seq_len} khung hình · {session.source_type || "camera"}
        </span>
        {session.can_manage && (
          <div className="flex items-center gap-2 whitespace-nowrap">
            {session.original_sample_uid && (
              <a
                href={sampleDownloadUrl(session.original_sample_uid)}
                download={`${session.original_sample_uid}.npz`}
                onClick={(e) => e.stopPropagation()}
                className="text-[11px] text-ctu-blue hover:text-ctu-navy hover:underline"
              >
                {t("Tải .npz")}
              </a>
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onReassign();
              }}
              disabled={deleting}
              className="text-[11px] text-amber-600 hover:text-amber-700 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("Đổi nhãn")}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              disabled={deleting}
              className="text-[11px] text-red-600 hover:text-red-700 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleting ? t("Đang xóa…") : "Xóa"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function VideoTier({
  classUid,
  sessionId,
  state,
}: {
  classUid: string;
  sessionId: string;
  state: PreviewState;
}) {
  const { t } = useI18n();
  if (state === "ready") {
    return (
      <video
        controls
        loop
        autoPlay
        muted
        playsInline
        src={previewVideoUrl(classUid, sessionId)}
        className="w-full aspect-square bg-[#0c161e] object-contain"
        data-testid="preview-video"
      />
    );
  }
  if (state === "error") {
    return (
      <div className="aspect-square flex items-center justify-center px-6">
        <p className="text-red-300 text-sm text-center">
          {t("Chưa tạo được video xem nhẹ cho lần quay này. Hãy thử chế độ Khung xương 2D.")}
        </p>
      </div>
    );
  }
  return (
    <div
      className="aspect-square flex flex-col items-center justify-center gap-2 text-slate-400 text-sm"
      data-testid="preview-rendering"
    >
      <span className="animate-pulse">
        {state === "checking"
          ? t("Đang kiểm tra bản xem nhẹ…")
          : t("Server đang chuẩn bị video (một lần duy nhất)…")}
      </span>
      <span className="text-[11px] text-slate-500">{t("Các lần xem sau sẽ mở ngay lập tức.")}</span>
    </div>
  );
}
