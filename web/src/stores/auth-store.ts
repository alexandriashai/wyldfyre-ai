import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi, authenticatedFetch } from "@/lib/api";
import { setToken, removeToken, getToken, getRefreshToken, setRefreshToken, isTokenExpired, getTokenExpiresIn } from "@/lib/auth";

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

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleTokenRefresh(
  token: string,
  set: (state: Partial<AuthState>) => void,
  get: () => AuthState
) {
  // Clear any existing timer
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }

  const expiresIn = getTokenExpiresIn(token);
  // Refresh 2 minutes before expiry (or immediately if less than 2 min left)
  const refreshIn = Math.max(0, (expiresIn - 120)) * 1000;

  refreshTimer = setTimeout(async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return;

    try {
      const response = await authApi.refreshToken(refreshToken);
      const newToken = response.access_token;
      setToken(newToken);
      if (response.refresh_token) {
        setRefreshToken(response.refresh_token);
      }
      set({ token: newToken });
      // Schedule next refresh
      scheduleTokenRefresh(newToken, set, get);
    } catch {
      // Refresh failed, user will need to re-login
      removeToken();
      set({ user: null, token: null, isAuthenticated: false });
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  }, refreshIn);
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
          if (response.refresh_token) {
            setRefreshToken(response.refresh_token);
          }
          set({ token, isAuthenticated: true });
          await get().fetchUser();
          scheduleTokenRefresh(token, set, get);
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
        let token = getToken();
        if (token) {
          // If token is expired, try refreshing before fetching user
          if (isTokenExpired(token)) {
            const refreshToken = getRefreshToken();
            if (refreshToken) {
              try {
                const response = await authApi.refreshToken(refreshToken);
                token = response.access_token;
                setToken(token);
                if (response.refresh_token) {
                  setRefreshToken(response.refresh_token);
                }
              } catch {
                // Refresh failed, clear auth
                removeToken();
                set({ user: null, token: null, isAuthenticated: false });
                return;
              }
            } else {
              // No refresh token, clear auth
              removeToken();
              set({ user: null, token: null, isAuthenticated: false });
              return;
            }
          }
          set({ token });
          await get().fetchUser();

          // Schedule proactive token refresh before expiry
          scheduleTokenRefresh(token, set, get);
        }
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ token: state.token }),
    }
  )
);
