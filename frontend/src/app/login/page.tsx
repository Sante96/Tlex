"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2, RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import QRCode from "react-qr-code";
import Cookies from "js-cookie";
import Image from "next/image";
import { DSButton, DSInput, TVButton, TVBackground } from "@/components/ds";
import { useAuth } from "@/contexts/auth-context";
import { useIsTV } from "@/hooks/use-platform";
import { requestDeviceCode, pollDeviceCode } from "@/lib/api";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => ({ default: m.MeshGradient })),
  { ssr: false },
);

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const isTV = useIsTV();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations("auth.login");

  const [deviceCode, setDeviceCode] = useState<string | null>(null);
  const [userCode, setUserCode] = useState<string | null>(null);
  const [expiresIn, setExpiresIn] = useState(0);
  const [tvLoading, setTvLoading] = useState(false);
  const [origin, setOrigin] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activateUrl = origin ? `${origin}/activate?code=${userCode}` : "";

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  const startDeviceFlow = async () => {
    setTvLoading(true);
    try {
      const data = await requestDeviceCode();
      setDeviceCode(data.device_code);
      setUserCode(data.user_code);
      setExpiresIn(data.expires_in);
    } catch {
      setError("Errore nella richiesta del codice");
    } finally {
      setTvLoading(false);
    }
  };

  useEffect(() => {
    if (!isTV) return;
    startDeviceFlow();
  }, [isTV]);

  useEffect(() => {
    if (!deviceCode) return;

    const countdown = setInterval(() => {
      setExpiresIn((s) => {
        if (s <= 1) {
          clearInterval(countdown);
          setDeviceCode(null);
          setUserCode(null);
          startDeviceFlow();
          return 0;
        }
        return s - 1;
      });
    }, 1000);

    pollRef.current = setInterval(async () => {
      try {
        const res = await pollDeviceCode(deviceCode);
        if (res.status === "confirmed" && res.access_token) {
          clearInterval(pollRef.current!);
          clearInterval(countdown);
          Cookies.set("token", res.access_token, { expires: 7 });
          if (res.refresh_token) Cookies.set("refresh_token", res.refresh_token, { expires: 30 });
          router.push("/profiles");
        } else if (res.status === "expired") {
          clearInterval(pollRef.current!);
          clearInterval(countdown);
          setDeviceCode(null);
          setUserCode(null);
        }
      } catch { /* ignore */ }
    }, 5000);

    return () => {
      clearInterval(pollRef.current!);
      clearInterval(countdown);
    };
  }, [deviceCode, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await login({ email, password });
      router.push("/profiles");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("submit"));
    } finally {
      setIsLoading(false);
    }
  };

  if (isTV) {
    return (
      <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
        <TVBackground />

        <div className="relative z-10 flex flex-row items-center gap-16 px-24">
          {/* Left: instructions */}
          <div className="flex flex-col gap-8 w-[380px]">
            {/* Brand */}
            <div>
              <Image src="/tlex-logo.svg" alt="TLEX" width={200} height={58} className="h-16 w-auto" unoptimized />
              <p className="text-3xl font-semibold text-white mt-2">Accedi alla TV</p>
            </div>

            {/* Steps */}
            <div className="flex flex-col gap-5">
              <div className="flex items-start gap-4">
                <span className="flex-shrink-0 w-8 h-8 rounded-full bg-[#e5a00d]/20 border border-[#e5a00d]/40 text-[#e5a00d] text-sm font-bold flex items-center justify-center">1</span>
                <div>
                  <p className="text-base font-medium text-white">Vai su</p>
                  <p className="text-base font-mono text-[#e5a00d]">
                    {origin}/activate
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <span className="flex-shrink-0 w-8 h-8 rounded-full bg-[#e5a00d]/20 border border-[#e5a00d]/40 text-[#e5a00d] text-sm font-bold flex items-center justify-center">2</span>
                <p className="text-base font-medium text-white pt-1">Inserisci il codice qui sotto</p>
              </div>
              <div className="flex items-start gap-4">
                <span className="flex-shrink-0 w-8 h-8 rounded-full bg-[#e5a00d]/20 border border-[#e5a00d]/40 text-[#e5a00d] text-sm font-bold flex items-center justify-center">3</span>
                <p className="text-base font-medium text-white pt-1">Accedi con le tue credenziali</p>
              </div>
            </div>

            {/* Code tiles */}
            {userCode && (
              <div className="flex flex-col gap-3">
                <div className="flex gap-2">
                  {userCode.split("").map((char, i) => (
                    <span
                      key={i}
                      className="w-14 h-16 flex items-center justify-center rounded-xl bg-[#18181b] border border-[#e5a00d]/30 text-3xl font-mono font-bold text-[#e5a00d] shadow-[0_0_12px_rgba(229,160,13,0.15)]"
                    >
                      {char}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-[#52525b]">
                  Scade in {Math.floor(expiresIn / 60)}:{String(expiresIn % 60).padStart(2, "0")}
                </p>
              </div>
            )}

            {!userCode && !tvLoading && (
              <TVButton
                variant="secondary"
                icon={<RefreshCw className="h-5 w-5" />}
                onClick={startDeviceFlow}
              >
                Riprova
              </TVButton>
            )}

            {tvLoading && (
              <div className="flex items-center gap-3 text-[#71717a] text-base">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Generazione codice...</span>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="h-64 w-px bg-gradient-to-b from-transparent via-[#3f3f46] to-transparent" />

          {/* Right: QR */}
          <div className="flex flex-col items-center gap-5">
            <div
              className="rounded-2xl p-1.5"
              style={{
                background: "linear-gradient(135deg, rgba(229,160,13,0.5), rgba(229,160,13,0.1))",
              }}
            >
              <div className="rounded-xl p-4 bg-white">
                {activateUrl && userCode ? (
                  <QRCode value={activateUrl} size={196} />
                ) : (
                  <div className="w-[196px] h-[196px] bg-[#f4f4f5] rounded-lg flex items-center justify-center">
                    <Loader2 className="h-8 w-8 text-[#a1a1aa] animate-spin" />
                  </div>
                )}
              </div>
            </div>
            <p className="text-base text-[#71717a]">Oppure scansiona con il telefono</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 z-0">
        <MeshGradient
          style={{ width: "100%", height: "100%" }}
          colors={["#09090b", "#1c1500", "#09090b"]}
          distortion={1}
          swirl={0.1}
          grainMixer={0}
          grainOverlay={0}
          speed={0.3}
        />
        <div
          className="absolute inset-0"
          style={{ backgroundColor: "rgba(9,9,11,0.45)" }}
        />
      </div>

      {/* Glass card */}
      <div
        className="relative z-10 w-full max-w-sm rounded-2xl p-8 shadow-[0_24px_48px_rgba(0,0,0,0.6)]"
        style={{
          backgroundColor: "rgba(10,10,10,0.7)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        {/* Logo + heading */}
        <div className="text-center mb-8">
          <Image src="/tlex-logo.svg" alt="TLEX" width={200} height={58} className="h-13 w-auto mx-auto" unoptimized />
          <h1 className="text-xl font-semibold text-white mt-3">
            {t("title")}
          </h1>
          <p className="text-sm text-[#71717a] mt-1">{t("subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
              {error}
            </div>
          )}

          <DSInput
            label={t("email")}
            type="email"
            placeholder="tu@esempio.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />

          <DSInput
            label={t("password")}
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            suffix={
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-[#71717a] hover:text-[#fafafa] transition-colors"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            }
          />

          <DSButton
            type="submit"
            disabled={isLoading}
            className="mt-1 w-full"
            icon={
              isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : undefined
            }
          >
            {isLoading ? t("loading") : t("submit")}
          </DSButton>
        </form>

        <p className="mt-6 text-center text-sm text-[#52525b]">
          {t("noAccount")}{" "}
          <Link
            href="/register"
            className="text-[#e5a00d] hover:text-[#f0b429] transition-colors"
          >
            {t("register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
