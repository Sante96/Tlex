import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { AuthProvider } from "@/contexts/auth-context";
import { ProfileProvider } from "@/contexts/profile-context";
import { ToastProvider } from "@/components/ui/toast";
import "./globals.css";

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
    <html lang={locale} className="dark">
      <body
        className="font-sans bg-zinc-950 text-white min-h-screen"
      >
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
