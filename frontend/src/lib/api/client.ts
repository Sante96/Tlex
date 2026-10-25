import axios, { isAxiosError, type InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

import { getClientLocale } from "@/lib/locale";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // the session cookies, also when the API is on another origin (dev)
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  // TMDB metadata in the UI's language
  config.headers["Accept-Language"] = getClientLocale() === "en" ? "en-US" : "it-IT";
  return config;
});

// --- Session ----------------------------------------------------------------
// The backend keeps the tokens in httpOnly cookies, out of this code's reach (and an
// XSS's), plus a readable `token_exp`: the access token's expiry in unix seconds. The
// `token` cookie also authenticates <video>, subtitle and font requests, which axios
// never sees, so it is renewed shortly before it expires instead of only after a 401.

let refreshTimer: ReturnType<typeof setTimeout> | undefined;
let refreshing: Promise<boolean> | null = null;

/** Logged in, as far as the page can tell. `token` is the JS cookie of sessions from
 * before the httpOnly cookies, until their first refresh replaces it. */
export const hasSession = () => !!(Cookies.get("token_exp") || Cookies.get("token"));

/** After a login, a device login or a password change: the backend set new cookies. */
export function sessionStarted() {
  scheduleRefresh();
}

/** Forget the session on this page; the backend clears the httpOnly cookies at logout. */
export function endSession() {
  clearTimeout(refreshTimer);
  // token and refresh_token: only the JS cookies of a session from before, or hasSession()
  // would keep bouncing between /login and a failing refresh
  for (const name of ["token_exp", "token", "refresh_token"]) Cookies.remove(name);
}

/** Rotate the refresh token cookie into a new session. True when the session is good
 * now, false when the backend refused it; rejects when the backend can't be reached or
 * fails (restarting, 502): that says nothing about the session. Concurrent callers in
 * this tab share one request, since the backend rotates refresh tokens. */
export function refreshTokens(): Promise<boolean> {
  refreshing ??= (async () => {
    const before = Cookies.get("token_exp");
    try {
      await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, undefined, {
        withCredentials: true,
      });
    } catch (e) {
      // Another tab renewed the shared cookies a moment earlier: its session is ours too
      if (Cookies.get("token_exp") === before) {
        if (isAxiosError(e) && e.response && e.response.status < 500) return false;
        throw e;
      }
    }
    scheduleRefresh();
    return true;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** The backend refused the session: back to the login page. */
function sessionExpired() {
  if (!hasSession()) return;
  endSession();
  window.location.assign("/login");
}

/** Timer path: refused means login again; unreachable means try again in 30 s. */
function renew() {
  refreshTokens().then(
    (ok) => ok || sessionExpired(),
    () => (refreshTimer = setTimeout(renew, 30_000)),
  );
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  const exp = Number(Cookies.get("token_exp"));
  if (!exp) {
    // A session from before: refresh now to get the httpOnly cookies and token_exp
    if (Cookies.get("token")) renew();
    return;
  }
  // One minute early, plus up to 30 s of jitter so tabs don't all renew at the same
  // instant; clamp because setTimeout fires at once past ~24.8 days
  const delay = exp * 1000 - Date.now() - 60_000 - Math.random() * 30_000;
  refreshTimer = setTimeout(renew, Math.min(Math.max(0, delay), 2 ** 31 - 1));
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
  // A failed refresh (backend down) rejects: this request fails, the session stays
  if (await refreshTokens().catch(() => Promise.reject(error))) return api(config);
  sessionExpired();
  throw error;
});
