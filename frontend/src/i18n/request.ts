import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";
import { locales, defaultLocale, LOCALE_COOKIE, type Locale } from "./config";

function detectSystemLocale(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) return defaultLocale;
  const preferred = acceptLanguage.split(",")[0].trim().toLowerCase();
  if (preferred.startsWith("it")) return "it";
  if (preferred.startsWith("en")) return "en";
  return defaultLocale;
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const raw = cookieStore.get(LOCALE_COOKIE)?.value;
  const headerStore = await headers();
  const locale: Locale =
    raw && locales.includes(raw as Locale)
      ? (raw as Locale)
      : detectSystemLocale(headerStore.get("accept-language"));

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
