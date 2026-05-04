import axios from "axios";

/**
 * Determine API base URL based on environment
 * - In browser: Use configured VITE_API_URL or fall back to location
 * - Behind proxy: Use relative paths or configured URL
 */
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

const axiosClient = axios.create({
  baseURL: getApiBaseURL(),
  timeout: 30000,
});

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
      err.userMessage =
        "Network Error: Cannot reach backend. Check that:\n" +
        "- Backend service is running\n" +
        "- Frontend API URL is correct (VITE_API_URL)\n" +
        "- CORS is properly configured\n" +
        "- Firewall is not blocking connections";
    } else if (err?.response?.status === 0) {
      err.userMessage = "Connection refused. Backend may be offline.";
    } else if (err?.code === "ECONNABORTED") {
      err.userMessage = "Request timeout. Backend may be slow or offline.";
    }

    return Promise.reject(err);
  }
);

export default axiosClient;
