"use client";

import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import {
  LOCALE_COOKIE,
  type Locale,
  locales,
  defaultLocale,
} from "@/i18n/config";

export function getClientLocale(): Locale {
  const raw = Cookies.get(LOCALE_COOKIE);
  return raw && locales.includes(raw as Locale)
    ? (raw as Locale)
    : defaultLocale;
}

export function useSetLocale() {
  const router = useRouter();
  return (locale: Locale) => {
    Cookies.set(LOCALE_COOKIE, locale, { expires: 365, sameSite: "lax" });
    router.refresh();
  };
}

export { type Locale, locales, defaultLocale };
