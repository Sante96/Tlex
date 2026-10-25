"use client";

import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import {
  LOCALE_COOKIE,
  type Locale,
  locales,
  defaultLocale,
} from "@/i18n/config";

/** The page's locale, as the server chose it (cookie, else the browser's language) and
 * wrote it into <html lang>. Reading the cookie alone missed the browser fallback: the
 * UI, the settings page and the TMDB language sent to the backend could disagree. */
export function getClientLocale(): Locale {
  const lang = typeof document === "undefined" ? "" : document.documentElement.lang;
  return locales.includes(lang as Locale) ? (lang as Locale) : defaultLocale;
}

export function useSetLocale() {
  const router = useRouter();
  return (locale: Locale) => {
    Cookies.set(LOCALE_COOKIE, locale, { expires: 365, sameSite: "lax" });
    router.refresh();
  };
}

export { type Locale, locales, defaultLocale };
