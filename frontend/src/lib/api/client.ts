import axios, { type InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token and locale to requests
api.interceptors.request.use((config) => {
  const token = Cookies.get("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const locale = Cookies.get("TLEX_LOCALE") || "it";
  config.headers["Accept-Language"] = locale === "en" ? "en-US" : "it-IT";
  return config;
});

// --- Tokens ---------------------------------------------------------------
// The access token is short-lived. The `token` cookie is also what authenticates
// <video>, subtitle and font requests, which axios never sees, so it is renewed
// shortly before it expires instead of only after a 401.

const cookieOptions = () => ({
  expires: 30,
  sameSite: "lax" as const,
  secure: window.location.protocol === "https:",
});

let refreshTimer: ReturnType<typeof setTimeout> | undefined;
let refreshing: Promise<boolean> | null = null;

export function saveTokens(accessToken: string, refreshToken?: string) {
  Cookies.set("token", accessToken, cookieOptions());
  if (refreshToken) Cookies.set("refresh_token", refreshToken, cookieOptions());
  scheduleRefresh();
}

export function clearTokens() {
  clearTimeout(refreshTimer);
  Cookies.remove("token");
  Cookies.remove("refresh_token");
}

/** Exchange the refresh token for new tokens. Concurrent callers share one request:
 * the backend rotates refresh tokens, so a second parallel refresh would be rejected. */
export function refreshTokens(): Promise<boolean> {
  refreshing ??= (async () => {
    const refreshToken = Cookies.get("refresh_token");
    if (!refreshToken) return false;
    try {
      const { data } = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      });
      saveTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  const token = Cookies.get("token");
  if (!token || !Cookies.get("refresh_token")) return;
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload));
    // One minute early; clamp because setTimeout fires at once past ~24.8 days
    const delay = Math.min(Math.max(0, exp * 1000 - Date.now() - 60_000), 2 ** 31 - 1);
    refreshTimer = setTimeout(refreshTokens, delay);
  } catch {
    // Not a JWT we can read: the 401 handler below still covers axios calls
  }
}

if (typeof window !== "undefined") scheduleRefresh();

// On 401, refresh once and retry; if that fails the session is over
const AUTH_ENDPOINTS = /\/auth\/(login|register|refresh|device)/;

api.interceptors.response.use(undefined, async (error) => {
  const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
  if (
    error.response?.status !== 401 ||
    !config ||
    config._retried ||
    AUTH_ENDPOINTS.test(config.url ?? "")
  ) {
    throw error;
  }
  config._retried = true;
  if (await refreshTokens()) return api(config);
  if (Cookies.get("token")) {
    clearTokens();
    window.location.assign("/login");
  }
  throw error;
});
