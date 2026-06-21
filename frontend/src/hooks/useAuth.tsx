import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { api } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────────────

interface User {
  id: string;
  email: string;
  role: string;
  team_id: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, teamName?: string) => Promise<void>;
  logout: () => void;
}

// ── Storage keys ───────────────────────────────────────────────────────

const ACCESS_TOKEN_KEY = 'agent_factory_access_token';
const REFRESH_TOKEN_KEY = 'agent_factory_refresh_token';
const USER_KEY = 'agent_factory_user';

// ── Helpers ────────────────────────────────────────────────────────────

function loadStoredAuth(): Pick<AuthState, 'user' | 'accessToken' | 'refreshToken'> {
  try {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    const userRaw = localStorage.getItem(USER_KEY);
    const user = userRaw ? (JSON.parse(userRaw) as User) : null;
    return { user, accessToken, refreshToken };
  } catch {
    return { user: null, accessToken: null, refreshToken: null };
  }
}

function saveAuth(user: User, accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── Context ────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const stored = loadStoredAuth();
    return {
      user: stored.user,
      accessToken: stored.accessToken,
      refreshToken: stored.refreshToken,
      isLoading: !!stored.accessToken, // Only loading if we have a token to validate
      isAuthenticated: false,
    };
  });

  // Validate stored token on mount
  useEffect(() => {
    if (!state.accessToken) {
      setState((s) => ({ ...s, isLoading: false }));
      return;
    }

    let cancelled = false;

    api
      .get<{ user: User }>('/api/auth/me')
      .then((data) => {
        if (!cancelled) {
          setState((s) => ({
            ...s,
            user: data.user,
            isAuthenticated: true,
            isLoading: false,
          }));
        }
      })
      .catch(() => {
        if (!cancelled) {
          // Token invalid — try refresh
          refreshAccessToken()
            .then(() => {
              if (!cancelled) {
                setState((s) => ({ ...s, isAuthenticated: true, isLoading: false }));
              }
            })
            .catch(() => {
              if (!cancelled) {
                clearAuth();
                setState({
                  user: null,
                  accessToken: null,
                  refreshToken: null,
                  isLoading: false,
                  isAuthenticated: false,
                });
              }
            });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Token refresh ──────────────────────────────────────────────────

  async function refreshAccessToken(): Promise<void> {
    const stored = loadStoredAuth();
    if (!stored.refreshToken) throw new Error('No refresh token');

    const data = await api.post<{ access_token: string; refresh_token: string }>(
      '/api/auth/refresh',
      { refresh_token: stored.refreshToken },
      { skipAuth: true },
    );

    const user = loadStoredAuth().user;
    if (user) {
      saveAuth(user, data.access_token, data.refresh_token);
      setState((s) => ({
        ...s,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user,
        isAuthenticated: true,
      }));
    }
  }

  // ── Login ──────────────────────────────────────────────────────────

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<{
      access_token: string;
      refresh_token: string;
    }>('/api/auth/login', { email, password }, { skipAuth: true });

    // Fetch user profile
    const me = await api.get<{ user: User }>('/api/auth/me', {
      headers: { Authorization: `Bearer ${data.access_token}` },
    } as RequestInit);

    const user = me.user;
    saveAuth(user, data.access_token, data.refresh_token);

    setState({
      user,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  // ── Register ───────────────────────────────────────────────────────

  const register = useCallback(
    async (email: string, password: string, teamName?: string) => {
      const data = await api.post<{
        access_token: string;
        refresh_token: string;
      }>(
        '/api/auth/register',
        { email, password, team_name: teamName || 'default' },
        { skipAuth: true },
      );

      // Fetch user profile
      const me = await api.get<{ user: User }>('/api/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      } as RequestInit);

      const user = me.user;
      saveAuth(user, data.access_token, data.refresh_token);

      setState({
        user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        isLoading: false,
        isAuthenticated: true,
      });
    },
    [],
  );

  // ── Logout ─────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    clearAuth();
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,
      isAuthenticated: false,
    });
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ───────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
