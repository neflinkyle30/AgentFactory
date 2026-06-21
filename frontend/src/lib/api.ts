/**
 * API client — fetch wrapper with auth, token refresh, and error handling.
 *
 * Features:
 * - Auto-attach Authorization header from localStorage
 * - 401 handling: attempt token refresh once, redirect to /login on failure
 * - Type-safe request/response generics
 * - Base URL from Vite env: VITE_API_URL (falls back to '' for proxy)
 */

// ── Constants ──────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

const ACCESS_TOKEN_KEY = 'agent_factory_access_token';
const REFRESH_TOKEN_KEY = 'agent_factory_refresh_token';

// ── Types ──────────────────────────────────────────────────────────────

interface ApiErrorBody {
  detail?: string;
  message?: string;
}

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    const detail = body?.detail || body?.message || `Request failed with status ${status}`;
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  skipAuth?: boolean;
  body?: unknown;
}

// ── Token helpers ──────────────────────────────────────────────────────

function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

// ── Token refresh ──────────────────────────────────────────────────────

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  // Dedupe concurrent refresh attempts
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) return false;

      const data = await res.json();
      localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
      if (data.refresh_token) {
        localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
      }
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

function clearAuthAndRedirect() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem('agent_factory_user');

  // Only redirect if not already on login/register
  if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
    window.location.href = '/login';
  }
}

// ── Core fetch wrapper ─────────────────────────────────────────────────

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth = false, body, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };

  // Attach auth token
  if (!skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const url = `${BASE_URL}${path}`;

  const res = await fetch(url, {
    ...fetchOptions,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Handle 401 — try refresh once
  if (res.status === 401 && !skipAuth) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      // Retry with new token
      const newToken = getAccessToken();
      const retryRes = await fetch(url, {
        ...fetchOptions,
        headers: {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });

      if (!retryRes.ok) {
        if (retryRes.status === 401) {
          clearAuthAndRedirect();
        }
        throw new ApiError(
          retryRes.status,
          await retryRes.json().catch(() => null),
        );
      }

      return retryRes.json() as Promise<T>;
    }

    // Refresh failed — clear and redirect
    clearAuthAndRedirect();
    throw new ApiError(401, { detail: 'Authentication expired. Please log in again.' });
  }

  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null));
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ── Public API ──────────────────────────────────────────────────────────

export const api = {
  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'GET' });
  },

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'POST', body });
  },

  put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'PUT', body });
  },

  patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'PATCH', body });
  },

  delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>(path, { ...options, method: 'DELETE' });
  },
};

// ── Re-exports ─────────────────────────────────────────────────────────

export { getAccessToken, clearAuthAndRedirect };
