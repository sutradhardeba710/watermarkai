import axios, { type InternalAxiosRequestConfig } from "axios";
import { useAuthStore, type AuthUser } from "@/features/auth/authStore";

// Next rewrites proxy /api/* to the backend (see next.config.js), so the
// browser uses same-origin. Server components can override with NEXT_PUBLIC_API_URL.
const baseURL =
  (typeof window !== "undefined" ? "" : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") +
  "/api/v1";

const ACCESS_KEY = "vwa_access_token";
const REFRESH_KEY = "vwa_refresh_token";
const USER_KEY = "vwa_user";

type RetryableConfig = InternalAxiosRequestConfig & { _retry?: boolean };
type RefreshResponse = {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
};

export const api = axios.create({
  baseURL,
  withCredentials: false,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem(ACCESS_KEY);
    if (token) config.headers.Authorization = "Bearer " + token;
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

function clearStoredSession() {
  if (typeof window === "undefined") return;
  useAuthStore.getState().clear();
}

async function refreshAccessToken(): Promise<string> {
  if (typeof window === "undefined") throw new Error("Session refresh is browser-only.");

  const refreshToken = window.localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) throw new Error("No refresh token is available.");

  const response = await axios.post<RefreshResponse>(
    baseURL + "/auth/refresh",
    { refresh_token: refreshToken },
    { headers: { "Content-Type": "application/json" } },
  );
  const session = response.data;
  useAuthStore.getState().setAuth(session.access_token, session.refresh_token, session.user);
  return session.access_token;
}

// Unwrap the SRS BE-004 envelope and recover once from an expired access token.
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err?.config as RetryableConfig | undefined;
    const status = err?.response?.status;
    const isAuthRoute =
      typeof original?.url === "string" &&
      (original.url.includes("/auth/login") || original.url.includes("/auth/refresh"));

    if (
      typeof window !== "undefined" &&
      status === 401 &&
      original &&
      !original._retry &&
      !isAuthRoute
    ) {
      original._retry = true;
      try {
        refreshPromise ??= refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
        const accessToken = await refreshPromise;
        original.headers.Authorization = "Bearer " + accessToken;
        return api(original);
      } catch {
        clearStoredSession();
        if (window.location.pathname !== "/login") {
          window.location.assign("/login?session=expired");
        }
      }
    }

    const body = err?.response?.data;
    if (body?.error) {
      err.message = body.error.message || err.message;
      err.code = body.error.code;
    }
    return Promise.reject(err);
  },
);

export type ApiError = { message?: string; code?: string };