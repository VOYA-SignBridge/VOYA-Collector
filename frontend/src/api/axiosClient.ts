import axios from "axios";

const axiosClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000", // Vite env var
  // Do not set a global Content-Type here. Let axios/browser set it per-request.
});

// Request logger (development only)
axiosClient.interceptors.request.use((cfg) => {
  if (import.meta.env.DEV) {
    console.debug('[api] Request:', cfg.method, cfg.url, cfg.params ?? '', cfg.data ?? '');
  }
  return cfg;
});

// Response logger
axiosClient.interceptors.response.use(
  (res) => {
    if (import.meta.env.DEV) {
      console.debug('[api] Response:', res.config.url, res.status);
    }
    return res;
  },
  (err) => {
    // Normalize error message for network errors and log details to console
  console.error('[api] Request failed:', err?.config?.url, err?.message, err?.response?.status);

    // If this is a network error (no response) give a more actionable message
    if (err && err.message && err.message === 'Network Error' && !err.response) {
      err.userMessage = 'Network Error: unable to reach API. Check backend URL, CORS and that the server is running.';
    }
    return Promise.reject(err);
  }
);

export default axiosClient;
