import { api } from "./api";
import type { AuthUser } from "@/features/auth/authStore";

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

export const authApi = {
  register: (body: {
    full_name: string;
    email: string;
    password: string;
    confirm_password: string;
    terms_accepted: boolean;
  }) =>
    api.post<AuthUser>("/auth/register", body).then((r) => r.data),

  verifyEmail: (token: string) =>
    api.post<AuthUser>("/auth/verify-email", { token }).then((r) => r.data),

  login: (email: string, password: string) =>
    api
      .post<AuthResponse>("/auth/login", { email, password })
      .then((r) => r.data),

  refresh: (refresh_token: string) =>
    api.post<AuthResponse>("/auth/refresh", { refresh_token }).then((r) => r.data),

  logout: (refresh_token?: string) =>
    api.post("/auth/logout", { refresh_token }).catch(() => {}),

  me: () => api.get<AuthUser>("/auth/me").then((r) => r.data),

  forgotPassword: (email: string) =>
    api.post<{ message: string }>("/auth/forgot-password", { email }).then((r) => r.data),

  resetPassword: (token: string, password: string, confirm_password: string) =>
    api.post<AuthUser>("/auth/reset-password", { token, password, confirm_password }).then((r) => r.data),
};
