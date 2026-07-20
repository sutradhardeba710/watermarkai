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

/** True when the refresh endpoint itself rejected the token (definitively
 * dead session). Network blips / 5xx / timeouts are NOT session-ending. */
function isAuthRejection(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  return status === 401 || status === 403;
}

async function refreshAccessToken(): Promise<string> {
  if (typeof window === "undefined") throw new Error("Session refresh is browser-only.");

  const refreshToken = window.localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) {
    const err = new Error("No refresh token is available.");
    (err as { response?: { status: number } }).response = { status: 401 };
    throw err;
  }

  const response = await axios.post<RefreshResponse>(
    baseURL + "/auth/refresh",
    { refresh_token: refreshToken },
    { headers: { "Content-Type": "application/json" }, timeout: 15_000 },
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
      } catch (refreshErr) {
        // Only end the session when the server actually rejected the refresh
        // token. A network drop / server restart mid-refresh must not log the
        // user out — the next 401 will simply retry the refresh.
        if (isAuthRejection(refreshErr)) {
          clearStoredSession();
          if (window.location.pathname !== "/login") {
            window.location.assign("/login?session=expired");
          }
        }
      }
    }

    const body = err?.response?.data;
    if (body?.error) {
      err.message = body.error.message || err.message;
      err.code = body.error.code;
    }

    // Maintenance mode: backend answers 503 MAINTENANCE for gated routes.
    // Send the user to the maintenance page (admins keep working — /admin
    // routes are exempted server-side).
    if (
      typeof window !== "undefined" &&
      status === 503 &&
      body?.error?.code === "MAINTENANCE" &&
      !window.location.pathname.startsWith("/maintenance") &&
      !window.location.pathname.startsWith("/admin")
    ) {
      window.location.assign("/maintenance");
    }
    return Promise.reject(err);
  },
);

export type ApiError = { message?: string; code?: string };