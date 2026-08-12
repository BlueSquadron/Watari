import axios from "axios";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LoginResponse, User } from "@/types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  loading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  tryRefresh: () => Promise<boolean>;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      loading: false,
      error: null,

      login: async (username, password) => {
        set({ loading: true, error: null });
        try {
          const { data } = await axios.post<{ data: LoginResponse }>(
            `${BASE_URL}/v1/auth/login`,
            { username, password },
          );
          set({
            accessToken: data.data.access_token,
            refreshToken: data.data.refresh_token,
            user: data.data.user,
            loading: false,
            error: null,
          });
        } catch (err) {
          const message =
            axios.isAxiosError(err) && err.response?.data?.message
              ? err.response.data.message
              : "Invalid username or password";
          set({ loading: false, error: message });
          throw err;
        }
      },

      logout: () => {
        set({ accessToken: null, refreshToken: null, user: null, error: null });
      },

      tryRefresh: async () => {
        const refreshToken = get().refreshToken;
        if (!refreshToken) return false;
        try {
          const { data } = await axios.post<{
            data: { access_token: string; expires_in: number };
          }>(`${BASE_URL}/v1/auth/refresh`, { refresh_token: refreshToken });
          set({ accessToken: data.data.access_token });
          return true;
        } catch {
          return false;
        }
      },

      setUser: (user) => set({ user }),
    }),
    {
      name: "watari-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    },
  ),
);
