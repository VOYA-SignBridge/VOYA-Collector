import { tr } from "../i18n";
import axios from "axios";

/**
 * Auth transport
 * --------------
 * Tokens live in httpOnly cookies set by the backend (JS/XSS can't read them).
 * This client therefore sends credentials on every request, echoes the
 * non-httpOnly CSRF cookie in an X-CSRF-Token header on state-changing calls,
 * and transparently refreshes an expired access token once before failing.
 *
 * The old localStorage Bearer helpers are kept as no-op-ish shims for backward
 * compatibility (and to feed the WebSocket token fallback), but nothing is
 * stored there in the cookie flow.
 */

const AUTH_EVENT = "voya:auth-change";

const emitAuthChange = () => {
  window.dispatchEvent(new Event(AUTH_EVENT));
};

export const getApiBaseURL = (): string => {
  // 1. Lấy từ cấu hình Runtime Nginx tiêm vào
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const runtimeUrl = (window as any).__ENV__?.VITE_API_URL;
  if (runtimeUrl && runtimeUrl !== "api" && runtimeUrl !== "api/") {
    return runtimeUrl;
  }

  // 2. Dự phòng (Fallback): Lấy từ biến môi trường lúc Build (phục vụ cho dev mode)
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl !== "api" && envUrl !== "api/") {
    return envUrl;
  }

  return "";
};

const TOKEN_KEY = "VOYA_AUTHENTICATION_TOKEN";

const axiosClient = axios.create({
  timeout: 30000,
  // Send + receive the auth cookies (same-origin through the nginx gateway).
  withCredentials: true,
});

// --- Legacy Bearer helpers (kept for backward-compat / WS token fallback) ----
export function setAuthToken(token: string | null) {
  if (token) {
    axiosClient.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete axiosClient.defaults.headers.common.Authorization;
  }
}

export function loadAuthToken() {
  const token = localStorage.getItem(TOKEN_KEY);
  setAuthToken(token);
  return token;
}

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveAuthToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  setAuthToken(token);
  emitAuthChange();
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
  setAuthToken(null);
  emitAuthChange();
}

/** Signal a login/logout so the AuthProvider re-fetches /auth/me. Used by the
 *  cookie flow where there is no token to save to localStorage. */
export function notifyAuthChange() {
  emitAuthChange();
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const hit = document.cookie.split("; ").find((c) => c.startsWith(prefix));
  return hit ? decodeURIComponent(hit.slice(prefix.length)) : null;
}

/** CSRF double-submit token, for code paths that bypass this axios client
 *  (e.g. raw fetch() in useTrainingAPI) and must set the header themselves. */
export function getCsrfToken(): string | null {
  return readCookie("voya_csrf");
}

/** Cheap "might I have a session?" — a legacy token or the hint cookie. */
function hasSessionCookie(): boolean {
  return !!getAuthToken() || readCookie("voya_auth") !== null;
}

loadAuthToken();

// Pre-calculate apiBase to prepend to relative URLs
let apiBase = getApiBaseURL().replace(/\/+$/, "");
if (apiBase.endsWith("/api")) {
  apiBase = apiBase.slice(0, -4);
}

// Request: attach the CSRF token on unsafe methods + dev logging + prepend baseUrl.
axiosClient.interceptors.request.use((cfg) => {
  if (cfg.url && cfg.url.startsWith("/") && apiBase) {
    cfg.url = apiBase + cfg.url;
  }

  const method = (cfg.method || "get").toLowerCase();
  if (method !== "get" && method !== "head" && method !== "options") {
    const csrf = readCookie("voya_csrf");
    if (csrf && cfg.headers) {
      if (typeof (cfg.headers as { set?: unknown }).set === "function") {
        (cfg.headers as { set: (k: string, v: string) => void }).set("X-CSRF-Token", csrf);
      } else {
        (cfg.headers as Record<string, string>)["X-CSRF-Token"] = csrf;
      }
    }
  }
  if (import.meta.env.DEV) {
    console.debug("[api] Request:", cfg.method?.toUpperCase(), cfg.url, {
      params: cfg.params,
      hasData: !!cfg.data,
    });
  }
  return cfg;
});

// Single-flight refresh: many requests can 401 at once when the access token
// expires; they all await the same POST /auth/refresh instead of stampeding.
let refreshPromise: Promise<unknown> | null = null;
function refreshSession(): Promise<unknown> {
  if (!refreshPromise) {
    refreshPromise = axiosClient
      .post("/api/v1/auth/refresh")
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

/**
 * Phát số phút dùng thử còn lại ra cho giao diện.
 *
 * Cổng gác gắn `X-Trial-Minutes-Remaining` vào MỌI phản hồi đi qua phiếu dùng
 * thử. Bắt ở đây — một chỗ duy nhất — thay vì bắt tại từng lời gọi: trang nhận
 * dạng bắn request liên tục, và bắt tại chỗ gọi thì đồng hồ hoặc phải nhận thêm
 * một vòng `/trial/status` cho mỗi khung hình (gấp đôi lưu lượng để hiện một
 * con số), hoặc phải luồn tham số qua bốn lớp không liên quan gì tới hạn ngạch.
 *
 * Không import từ `api/trial.ts` để tránh vòng phụ thuộc — tệp đó import
 * `axiosClient`. Tên sự kiện lặp lại ở hai nơi, và đó là cái giá rẻ hơn.
 */
function broadcastTrialMinutes(headers: unknown): void {
  const h = headers as Record<string, string> | undefined;
  if (!h) return;
  const remaining = Number(h["x-trial-minutes-remaining"]);
  const limit = Number(h["x-trial-minutes-limit"]);
  if (!Number.isFinite(remaining) || !Number.isFinite(limit)) return;
  window.dispatchEvent(
    new CustomEvent("voya:trial-minutes", { detail: { remaining, limit } }),
  );
}

// Response logger + transparent refresh-on-401 + error normalization.
axiosClient.interceptors.response.use(
  (res) => {
    if (import.meta.env.DEV) {
      console.debug("[api] Response OK:", res.config.url, res.status);
    }
    broadcastTrialMinutes(res.headers);
    return res;
  },
  async (err) => {
    const original = err?.config || {};
    const status = err?.response?.status;
    const url = original?.url || "unknown";
    const message = err?.message || "unknown error";
    const data = err?.response?.data;

    // Hết phút dùng thử. Cổng gác không gắn header ở nhánh từ chối — nó đặt
    // con số vào THÂN phản hồi — nên phải bắt riêng, nếu không đồng hồ trên
    // màn hình đứng ở số cuối cùng đọc được và người dùng không hiểu vì sao
    // trang ngừng chạy.
    if (status === 401 && data?.code === "trial_exhausted") {
      window.dispatchEvent(
        new CustomEvent("voya:trial-minutes", {
          detail: {
            remaining: 0,
            limit: Number(data.minutes_limit) || 0,
            exhausted: true,
          },
        }),
      );
    }
    // Admin blocked this client's IP → tell the user (reason + expiry). Handled
    // by a top-level <SecurityNotices> listener that shows a full-screen notice.
    if (status === 403 && data && data.blocked) {
      window.dispatchEvent(new CustomEvent("voya:blocked", { detail: data }));
    }
    // Admin force-logged-out this user → surface the reason before we redirect.
    if (status === 401 && typeof data?.detail === "string" && data.detail.includes(tr("quản trị viên"))) {
      window.dispatchEvent(new CustomEvent("voya:forcelogout", { detail: { message: data.detail } }));
    }

    // Access token likely expired → try ONE transparent refresh, then retry the
    // original request. Skipped for the auth bootstrap/teardown endpoints and
    // for guests (no session hint) to avoid pointless refresh attempts + loops.
    const isAuthCall = /\/auth\/(login|register|refresh|logout)/.test(url);
    if (status === 401 && !original.__retried && !isAuthCall && hasSessionCookie()) {
      original.__retried = true;
      try {
        await refreshSession();
        return axiosClient(original);
      } catch {
        // Refresh failed → the session is really gone. Clear local state and
        // let AuthProvider/ProtectedRoute react (redirect to login if needed).
        clearAuthToken();
      }
    }

    console.error("[api] Request failed:", { url, status, message });

    // Normalize error message for better UX
    if (err?.message === "Network Error" && !err?.response) {
      err.userMessage = tr("Không kết nối được máy chủ. Hãy kiểm tra kết nối mạng rồi thử lại.");
    } else if (err?.response?.status === 0) {
      err.userMessage = tr("Máy chủ từ chối kết nối. Có thể hệ thống đang tạm dừng.");
    } else if (err?.code === "ECONNABORTED") {
      err.userMessage = tr("Máy chủ phản hồi quá lâu. Vui lòng thử lại.");
    } else if (err?.response?.status === 401) {
      const reqUrl = err?.config?.url || "";
      const isAuthEndpoint = reqUrl.includes("/auth/login") || reqUrl.includes("/auth/register");
      if (isAuthEndpoint) {
        err.userMessage = tr("Tên đăng nhập, email hoặc mật khẩu không đúng.");
      } else {
        // Session gone (refresh already attempted above). Public pages stay
        // usable; ProtectedRoute sends logged-out users to /login.
        err.userMessage = tr("Bạn cần đăng nhập để thực hiện thao tác này.");
      }
    } else if (err?.response?.status === 403) {
      err.userMessage = tr("Bạn không có quyền truy cập tài nguyên này.");
    } else if (err?.response?.status === 404) {
      err.userMessage = tr("Không tìm thấy tài nguyên yêu cầu.");
    } else if (err?.response?.status === 413) {
      err.userMessage = tr("Dữ liệu quá lớn, không thể tải lên.");
    } else if (err?.response?.status === 429) {
      err.userMessage = tr("Bạn gửi quá nhiều yêu cầu, vui lòng thử lại sau.");
    } else if (err?.response?.status >= 500) {
      err.userMessage = tr("Hệ thống không thể kết nối, vui lòng thử lại sau.");
    }

    return Promise.reject(err);
  }
);

export default axiosClient;
