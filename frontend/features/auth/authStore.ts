"use client";

import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: "user" | "admin";
  admin_role?: string | null;
  email_verified: boolean;
  account_status: string;
  created_at: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  hydrated: boolean;
  setAuth: (access: string, refresh: string, user: AuthUser) => void;
  setUser: (user: AuthUser) => void;
  clear: () => void;
  hydrate: () => void;
}

const ACCESS_KEY = "vwa_access_token";
const REFRESH_KEY = "vwa_refresh_token";
const USER_KEY = "vwa_user";

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,
  setAuth: (access, refresh, user) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACCESS_KEY, access);
      window.localStorage.setItem(REFRESH_KEY, refresh);
      window.localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
    set({ accessToken: access, refreshToken: refresh, user });
  },
  setUser: (user) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
    set({ user });
  },
  clear: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(ACCESS_KEY);
      window.localStorage.removeItem(REFRESH_KEY);
      window.localStorage.removeItem(USER_KEY);
    }
    set({ accessToken: null, refreshToken: null, user: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    const access = window.localStorage.getItem(ACCESS_KEY);
    const refresh = window.localStorage.getItem(REFRESH_KEY);
    const userRaw = window.localStorage.getItem(USER_KEY);
    if (access && userRaw) {
      try {
        const user = JSON.parse(userRaw) as AuthUser;
        set({ accessToken: access, refreshToken: refresh, user, hydrated: true });
      } catch {
        get().clear();
        set({ hydrated: true });
      }
    } else {
      set({ hydrated: true });
    }
  },
}));
