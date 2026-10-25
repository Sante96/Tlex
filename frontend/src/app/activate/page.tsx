"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, CheckCircle, Tv } from "lucide-react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { DSButton, DSInput } from "@/components/ds";
import { confirmDeviceCode } from "@/lib/api";
import { AppBackground } from "@/components/layout/app-background";

export default function ActivatePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("auth.activate");

  const [code, setCode] = useState(searchParams.get("code") ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await confirmDeviceCode(code.trim().toUpperCase(), email, password);
      setDone(true);
      setTimeout(() => router.push("/"), 3000);
    } catch {
      setError(t("error"));
    } finally {
      setIsLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
        <AppBackground />
        <div
          className="relative z-10 flex flex-col items-center gap-5 text-center rounded-2xl px-10 py-12 shadow-[0_24px_48px_rgba(0,0,0,0.6)] glass"
        >
          <div className="w-16 h-16 rounded-full bg-plex-orange/15 border border-plex-orange/30 flex items-center justify-center">
            <CheckCircle className="h-8 w-8 text-plex-orange" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-white">{t("success")}</h1>
            <p className="text-sm text-[#71717a] mt-2 max-w-xs">{t("successSubtitle")}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      <AppBackground />

      {/* Glass card */}
      <div
        className="relative z-10 w-full max-w-sm rounded-2xl p-8 shadow-[0_24px_48px_rgba(0,0,0,0.6)] glass"
      >
        {/* Header */}
        <div className="text-center mb-7">
          <Image src="/tlex-logo.svg" alt="TLEX" width={200} height={58} className="h-13 w-auto mx-auto" unoptimized />
          <div className="flex items-center justify-center gap-2 mt-3">
            <Tv className="h-4 w-4 text-[#71717a]" />
            <h1 className="text-lg font-semibold text-white">{t("title")}</h1>
          </div>
          <p className="text-sm text-[#71717a] mt-1">{t("subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
              {error}
            </div>
          )}

          {/* Code input styled prominently */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-[#a1a1aa]">{t("code")}</label>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="ABCD12"
              maxLength={6}
              required
              className="w-full h-12 rounded-lg bg-[#18181b] px-3 text-center text-xl font-mono font-bold tracking-[0.4em] text-plex-orange border border-[#3f3f46] outline-none transition-colors focus:border-plex-orange focus:border-2 placeholder:text-[#3f3f46] placeholder:tracking-normal"
            />
          </div>

          <div
            className="w-full h-px my-1"
            style={{ background: "linear-gradient(to right, transparent, rgba(63,63,70,0.6), transparent)" }}
          />

          <DSInput
            label={t("email")}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPlaceholder")}
            required
            autoComplete="email"
          />

          <DSInput
            label={t("password")}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            autoComplete="current-password"
          />

          <DSButton
            type="submit"
            disabled={isLoading}
            className="mt-1 w-full"
            icon={isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}
          >
            {isLoading ? t("loading") : t("submit")}
          </DSButton>
        </form>
      </div>
    </div>
  );
}
