import axios from "axios";

/**
 * Determine API base URL based on environment
 * - In browser: Use configured VITE_API_URL or fall back to location
 * - Behind proxy: Use relative paths or configured URL
 */

const AUTH_EVENT = "voya:auth-change";

const emitAuthChange = () => {
  window.dispatchEvent(new Event(AUTH_EVENT));
};

const getApiBaseURL = (): string => {
  // First, try environment variable (set at build time)
  const envUrl = import.meta.env.VITE_API_URL;
  
  if (envUrl) {
    return envUrl;
  }

  // Fallback: this deployment serves the frontend on :8080 and the backend on :8000.
  // Use the backend port explicitly so browser requests do not fall back to the frontend nginx.
  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8000`;
  }

  // Final fallback
  return "http://localhost:8000";
};

const TOKEN_KEY = "VOYA_AUTHENTICATION_TOKEN";

const axiosClient = axios.create({
  baseURL: getApiBaseURL(),
  timeout: 30000,
});

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

loadAuthToken();

// Request logger (development only)
axiosClient.interceptors.request.use((cfg) => {
  if (import.meta.env.DEV) {
    console.debug("[api] Request:", cfg.method?.toUpperCase(), cfg.url, {
      params: cfg.params,
      hasData: !!cfg.data,
    });
  }
  return cfg;
});

// Response logger and error handler
axiosClient.interceptors.response.use(
  (res) => {
    if (import.meta.env.DEV) {
      console.debug("[api] Response OK:", res.config.url, res.status);
    }
    return res;
  },
  (err) => {
    const url = err?.config?.url || "unknown";
    const status = err?.response?.status || "no-response";
    const message = err?.message || "unknown error";
    
    console.error("[api] Request failed:", { url, status, message });

    // Normalize error message for better UX
    if (err?.message === "Network Error" && !err?.response) {
      // err.userMessage =
      //   "Network Error: Cannot reach backend. Check that:\n" +
      //   "- Backend service is running\n" +
      //   "- Frontend API URL is correct (VITE_API_URL)\n" +
      //   "- CORS is properly configured\n" +
      //   "- Firewall is not blocking connections";
      err.userMessage = "Server đang offline hoặc không thể kết nối. Vui lòng thử lại sau.";
    } else if (err?.response?.status === 0) {
      err.userMessage = "Connection refused. Backend may be offline.";
    } else if (err?.code === "ECONNABORTED") {
      err.userMessage = "Request timeout. Backend may be slow or offline.";
    } else if (err?.response?.status === 401) {
      // Phân biệt 401 từ auth endpoints (sai mật khẩu) vs protected routes (hết token)
      const url = err?.config?.url || "";
      const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/register") || url.includes("/auth/me");
      
      if (!isAuthEndpoint) {
        // 401 từ protected routes = hết token, redirect login
        clearAuthToken();
        err.userMessage = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
        setTimeout(() => {
          window.location.href = "/login";
        }, 500);
      } else {
        // 401 từ auth endpoints = sai mật khẩu, chỉ set message, không redirect
        err.userMessage = "Username, email hoặc mật khẩu không đúng.";
      }
    } else if (err?.response?.status === 403) {
      err.userMessage = "Bạn không có quyền truy cập tài nguyên này.";
    } else if (err?.response?.status === 404) {
      err.userMessage = "Không tìm thấy tài nguyên yêu cầu.";
    } else if (err?.response?.status === 413) {
      err.userMessage = "Dữ liệu quá lớn, không thể tải lên.";
    } else if (err?.response?.status === 429) {
      err.userMessage = "Bạn gửi quá nhiều yêu cầu, vui lòng thử lại sau.";
    } else if (err?.response?.status >= 500) {
      err.userMessage = "Hệ thống không thể kết nối, vui lòng thử lại sau.";
    }

    return Promise.reject(err);
  }
);

export default axiosClient;
