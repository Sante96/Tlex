import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { AuthProvider } from "@/contexts/auth-context";
import { ProfileProvider } from "@/contexts/profile-context";
import { ToastProvider } from "@/components/ui/toast";
import { TVViewportEffect } from "@/components/tv-viewport-effect";
import "./globals.css";

// The same typeface on every device: the system font made the app look different on
// Windows, Android, iOS and the TV. next/font serves it from this server, not Google.
const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans", display: "swap" });

export const metadata: Metadata = {
  title: "TLEX",
  description: "Self-hosted streaming platform powered by Telegram",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "TLEX",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={`dark ${geist.variable}`}>
      <body
        className="font-sans bg-zinc-950 text-white min-h-screen"
      >
        <TVViewportEffect />
        <NextIntlClientProvider locale={locale} messages={messages}>
          <AuthProvider>
            <ProfileProvider>
              <ToastProvider>{children}</ToastProvider>
            </ProfileProvider>
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
