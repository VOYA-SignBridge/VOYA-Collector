import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { fetchTrialStatus, startTrial, TRIAL_EVENT, type TrialState } from "../api/trial";
import { friendlyError } from "../lib/errors";
import { toneClasses, FOCUS_RING } from "../theme/status";
import { AlertTriangleIcon, ClockIcon, HandIcon, SparkleIcon } from "./ui/Icons";
import { Trans, useI18n } from "../i18n";

/**
 * Cổng dùng thử cho khách chưa đăng nhập.
 *
 * Vì sao cần một lớp bọc thay vì để trang tự xoay xở
 * ---------------------------------------------------
 * Cổng gác ở máy chủ cho `/realtime/*` chạy với **một trong hai**: phiên đăng
 * nhập, hoặc một phiếu dùng thử. Không có phiếu thì mọi lời gọi trả 401.
 *
 * Nếu để `RealtimeRuntime` tự dựng rồi tự hỏng, khách sẽ thấy đúng thứ tệ nhất:
 * trang mở ra, camera xin quyền, rồi "Không thể tải danh sách bộ nhận diện" —
 * một thông báo nói rằng hệ thống hỏng, trong khi thứ họ cần chỉ là bấm một
 * nút. Nên phiếu phải có TRƯỚC khi runtime được dựng, và đó là lý do lớp này
 * bọc `children` thay vì nằm cạnh nó.
 *
 * Người đã đăng nhập đi thẳng qua, không gọi thêm request nào.
 *
 * Vì sao đồng hồ nghe SỰ KIỆN chứ không tự hỏi lại
 * -------------------------------------------------
 * Cổng gác gắn số phút còn lại vào header của mọi phản hồi đi qua phiếu, và
 * `axiosClient` phát nó ra dưới dạng một sự kiện. Trang nhận dạng bắn request
 * liên tục; hỏi lại `/trial/status` cho mỗi khung hình là gấp đôi lưu lượng chỉ
 * để hiển thị một con số.
 */

type TrialMinutesEvent = CustomEvent<{
  remaining: number;
  limit: number;
  exhausted?: boolean;
}>;

export default function TrialGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { loading: authLoading, isAuthenticated } = useAuth();

  const [state, setState] = useState<TrialState | null>(null);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Người đã đăng nhập không bao giờ cần phiếu. Giữ trong ref để hiệu ứng bên
  // dưới không phải chạy lại chỉ vì `isAuthenticated` đổi từ undefined sang
  // false trong lượt dựng đầu.
  const skip = isAuthenticated;

  const load = useCallback(async () => {
    try {
      setState(await fetchTrialStatus());
      setError("");
    } catch (err) {
      setError(friendlyError(err, t("Không đọc được hạn mức dùng thử.")));
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (skip) {
      setChecking(false);
      return;
    }
    void load();
  }, [authLoading, skip, load]);

  // Đồng hồ chạy theo phản hồi thật, không theo bộ đếm ở trình duyệt.
  const stateRef = useRef<TrialState | null>(null);
  stateRef.current = state;
  useEffect(() => {
    if (skip) return;
    const onMinutes = (e: Event) => {
      const { remaining, limit, exhausted } = (e as TrialMinutesEvent).detail;
      const prev = stateRef.current;
      setState({
        has_grant: true,
        minutes_limit: limit || prev?.minutes_limit || 0,
        minutes_used: Math.max(0, (limit || prev?.minutes_limit || 0) - remaining),
        minutes_remaining: remaining,
        resets_at: prev?.resets_at ?? null,
        exhausted: exhausted ?? remaining <= 0,
      });
    };
    window.addEventListener(TRIAL_EVENT, onMinutes);
    return () => window.removeEventListener(TRIAL_EVENT, onMinutes);
  }, [skip]);

  const begin = async () => {
    setBusy(true);
    setError("");
    try {
      setState(await startTrial());
    } catch (err) {
      setError(friendlyError(err, t("Không xin được lượt dùng thử. Vui lòng thử lại.")));
    } finally {
      setBusy(false);
    }
  };

  if (skip) return <>{children}</>;
  if (authLoading || checking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center text-sm text-slate-500">
        {t("Đang kiểm tra hạn mức dùng thử…")}
      </div>
    );
  }

  // Chưa có phiếu, hoặc đã tiêu hết phút hôm nay: không dựng runtime. Dựng nó
  // chỉ để mọi request trả 401 là bật camera của người ta lên mà không dùng
  // vào việc gì.
  if (!state?.has_grant || state.exhausted) {
    return (
      <Invitation
        exhausted={!!state?.exhausted}
        limit={state?.minutes_limit ?? 0}
        resetsAt={state?.resets_at ?? null}
        busy={busy}
        error={error}
        onStart={begin}
      />
    );
  }

  return (
    <>
      <TrialMeter state={state} />
      {children}
    </>
  );
}

function Invitation({
  exhausted,
  limit,
  resetsAt,
  busy,
  error,
  onStart,
}: {
  exhausted: boolean;
  limit: number;
  resetsAt: string | null;
  busy: boolean;
  error: string;
  onStart: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:py-14">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm sm:p-8">
        <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-50 text-sky-700">
          {exhausted ? (
            <ClockIcon className="h-7 w-7" aria-hidden="true" />
          ) : (
            <HandIcon className="h-7 w-7" aria-hidden="true" />
          )}
        </span>

        {exhausted ? (
          <>
            <h1 className="text-xl font-bold text-slate-900">{t("Đã hết lượt dùng thử hôm nay")}</h1>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-600">
              {t("Bạn đã dùng hết {n} phút miễn phí của hôm nay.", { n: limit })}
              {resetsAt ? (
                <>
                  {" "}
                  Hạn mức làm mới lúc{" "}
                  <span className="font-semibold text-slate-800">
                    {new Date(resetsAt).toLocaleString("vi-VN")}
                  </span>
                  .
                </>
              ) : (
                " Hạn mức làm mới vào ngày mai."
              )}
            </p>
          </>
        ) : (
          <>
            <h1 className="text-xl font-bold text-slate-900">
              {t("Dùng thử nhận diện, không cần tài khoản")}
            </h1>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-600">
              <Trans
                k="Mỗi ngày bạn có {so_phut} nhận diện miễn phí. Chỉ tính thời gian máy thật sự xử lý — mở trang mà không ký hiệu gì thì không tiêu phút nào."
                vars={{
                  so_phut: (
                    <span className="font-semibold text-slate-800">
                      {t("{n} phút", { n: limit })}
                    </span>
                  ),
                }}
              />
            </p>
          </>
        )}

        {error ? (
          <div
            role="alert"
            className={`mt-4 rounded-xl border px-4 py-3 text-sm ${toneClasses("danger", "soft")}`}
          >
            <AlertTriangleIcon className="mr-2 inline h-4 w-4" aria-hidden="true" />
            {error}
          </div>
        ) : null}

        <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          {!exhausted && (
            <button
              type="button"
              onClick={onStart}
              disabled={busy}
              className={`inline-flex w-full items-center justify-center gap-2 rounded-xl border px-5 py-3 font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto ${toneClasses("success", "solid")} ${FOCUS_RING}`}
            >
              <SparkleIcon className="h-4 w-4" aria-hidden="true" />
              {busy ? t("Đang chuẩn bị…") : t("Bắt đầu dùng thử")}
            </button>
          )}
          <Link
            to="/register"
            className={`inline-flex w-full items-center justify-center rounded-xl border px-5 py-3 font-semibold transition sm:w-auto ${toneClasses("neutral", "outline")} ${FOCUS_RING}`}
          >
            {t("Tạo tài khoản miễn phí")}
          </Link>
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Có tài khoản rồi?{" "}
          <Link to="/login" className="font-semibold text-ctu-blue hover:text-ctu-navy">
            {t("Đăng nhập")}
          </Link>{" "}
          để dùng không giới hạn thời gian.
        </p>
      </div>
    </div>
  );
}

function TrialMeter({ state }: { state: TrialState }) {
  const { t } = useI18n();
  const limit = Math.max(1, state.minutes_limit);
  const used = Math.min(limit, Math.max(0, state.minutes_used));
  const pct = Math.round((used / limit) * 100);
  // Cảnh báo khi còn ít, không phải khi đã hết — lúc hết thì đã muộn để họ
  // sắp xếp lại việc đang làm.
  const low = state.minutes_remaining <= Math.max(2, Math.round(limit * 0.15));

  return (
    <div className="mx-auto mb-3 w-full max-w-6xl px-2.5 sm:px-4 lg:px-5">
      <div
        className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-2.5 text-sm ${toneClasses(low ? "warning" : "success", "soft")}`}
      >
        <span className="flex items-center gap-2 font-semibold">
          <ClockIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {t("Đang dùng thử")}
        </span>

        <span className="tabular-nums">
          {t("Còn")} <span className="font-bold">{state.minutes_remaining}</span> / {state.minutes_limit}{" "}
          phút hôm nay
        </span>

        <div
          className="h-1.5 min-w-[100px] flex-1 overflow-hidden rounded-full bg-white/70"
          role="progressbar"
          aria-valuenow={used}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-label={t("Số phút dùng thử đã dùng hôm nay")}
        >
          <div
            className={`h-full rounded-full transition-all ${low ? "bg-amber-500" : "bg-sky-600"}`}
            style={{ width: `${pct}%` }}
          />
        </div>

        <Link
          to="/register"
          className="font-semibold text-current underline underline-offset-2 hover:opacity-80"
        >
          {t("Tạo tài khoản để bỏ giới hạn")}
        </Link>
      </div>
    </div>
  );
}
