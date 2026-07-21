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

/** Self-service account management (acts on the current user via /auth/me). */
export const accountApi = {
  updateProfile: (full_name: string) =>
    api.patch<AuthUser>("/auth/me", { full_name }).then((r) => r.data),

  changePassword: (current_password: string, new_password: string, confirm_password: string) =>
    api.post("/auth/me/password", { current_password, new_password, confirm_password }).then((r) => r.data),

  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post<AuthUser>("/auth/me/avatar", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },

  removeAvatar: () => api.delete<AuthUser>("/auth/me/avatar").then((r) => r.data),

  deleteAccount: (password: string) =>
    api.delete("/auth/me", { data: { password } }).then((r) => r.data),
};
