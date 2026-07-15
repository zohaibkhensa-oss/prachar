const TOKEN_KEY = "prachar_token";
const REFRESH_KEY = "prachar_refresh_token";
const EMAIL_KEY = "prachar_email";
const PASSWORD_KEY = "prachar_password";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
  window.localStorage.removeItem(PASSWORD_KEY);
}

export function requireAuth(): string {
  const token = getToken();
  if (!token) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  return token;
}

/**
 * Attempts to re-login using saved credentials, or refresh token.
 * Returns a fresh access token, or null if refresh fails.
 */
export async function refreshToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

  // Try refresh token first
  const refresh = getRefreshToken();
  if (refresh) {
    try {
      const res = await fetch(`${apiBase}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (res.ok) {
        const data = await res.json() as { access_token: string };
        setToken(data.access_token);
        return data.access_token;
      }
    } catch {}
  }

  // Fallback: re-login with saved credentials
  const email = window.localStorage.getItem(EMAIL_KEY);
  const password = window.localStorage.getItem(PASSWORD_KEY);
  if (email && password) {
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json() as { access_token: string; refresh_token?: string };
        setToken(data.access_token);
        if (data.refresh_token) {
          window.localStorage.setItem(REFRESH_KEY, data.refresh_token);
        }
        return data.access_token;
      }
    } catch {}
  }

  // All refresh attempts failed — redirect to login
  clearToken();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
  return null;
}

/**
 * Fetch wrapper that automatically refreshes the token on 401.
 * Use this instead of raw fetch for authenticated API calls.
 */
export async function authedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  let res = await fetch(url, { ...options, headers });

  // If token expired, try to refresh and retry once
  if (res.status === 401) {
    const newToken = await refreshToken();
    if (newToken) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${newToken}`,
      };
      res = await fetch(url, { ...options, headers: retryHeaders });
    }
  }

  return res;
}
