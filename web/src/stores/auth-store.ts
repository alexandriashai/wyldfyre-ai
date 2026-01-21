import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi } from "@/lib/api";
import { setToken, removeToken, getToken } from "@/lib/auth";

interface User {
  id: string;
  email: string;
  username?: string;
  display_name: string | null;
  role: string;
  is_admin?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  setError: (error: string | null) => void;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login(email, password);
          const token = response.access_token;
          setToken(token);
          set({ token, isAuthenticated: true });
          await get().fetchUser();
        } catch (err) {
          const message = err instanceof Error ? err.message : "Login failed";
          set({ error: message, isAuthenticated: false });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (email: string, password: string, displayName?: string) => {
        set({ isLoading: true, error: null });
        try {
          await authApi.register(email, password, displayName);
          // After registration, log the user in
          await get().login(email, password);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Registration failed";
          set({ error: message });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        const { token } = get();
        if (token) {
          try {
            await authApi.logout(token);
          } catch {
            // Ignore logout errors
          }
        }
        removeToken();
        set({ user: null, token: null, isAuthenticated: false });
      },

      fetchUser: async () => {
        const { token } = get();
        if (!token) return;

        set({ isLoading: true });
        try {
          const user = await authApi.me(token);
          set({ user, isAuthenticated: true });
        } catch {
          // Token is invalid, clear auth state
          removeToken();
          set({ user: null, token: null, isAuthenticated: false });
        } finally {
          set({ isLoading: false });
        }
      },

      setError: (error: string | null) => set({ error }),

      initialize: async () => {
        const token = getToken();
        if (token) {
          set({ token });
          await get().fetchUser();
        }
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ token: state.token }),
    }
  )
);
