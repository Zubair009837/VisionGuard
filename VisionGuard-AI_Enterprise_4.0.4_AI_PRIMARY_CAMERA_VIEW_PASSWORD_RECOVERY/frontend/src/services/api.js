import axios from "axios";
import { clearSession, getToken } from "./auth";

// VisionGuard AI backend.
// The Vite proxy sends /api/* to FastAPI on port 8010.
const API_BASE = import.meta.env.DEV
  ? "/api"
  : `${window.location.protocol}//${window.location.hostname}:8010`;

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = String(error.config?.url || "");

    const isAuthRequest =
      url.includes("/auth/login") ||
      url.includes("/auth/password/forgot") ||
      url.includes("/auth/password/reset");

    if (status === 401 && !isAuthRequest) {
      clearSession();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export default api;
