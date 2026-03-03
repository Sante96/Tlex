"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { MeshGradient } from "@paper-design/shaders-react";
import { useTranslations } from "next-intl";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations("auth.register");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(t("passwordMismatch"));
      return;
    }
    if (password.length < 8) {
      setError("Password min. 8 caratteri");
      return;
    }

    setIsLoading(true);
    try {
      await register(email, password);
      router.push("/login?registered=true");
    } catch (err) {
      if (err instanceof Error) {
        setError(
          err.message.includes("400") ? t("emailTaken") : err.message,
        );
      } else {
        setError(t("failed"));
      }
    } finally {
      setIsLoading(false);
    }
  };

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
          <span className="text-4xl font-bold tracking-tight text-[#e5a00d]">
            TLEX
          </span>
          <h1 className="text-xl font-semibold text-white mt-3">
            {t("title")}
          </h1>
          <p className="text-sm text-[#71717a] mt-1">
            {t("subtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
              {error}
            </div>
          )}

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-white/70">{t("email")}</label>
            <input
              type="email"
              placeholder="tu@esempio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-[#e5a00d] transition-colors"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-white/70">{t("password")}</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className="w-full h-10 px-3 pr-10 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-[#e5a00d] transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/70 transition-colors"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Confirm password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-white/70">{t("confirmPassword")}</label>
            <input
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-[#e5a00d] transition-colors"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="mt-1 h-10 w-full rounded-lg bg-[#e5a00d] hover:bg-[#f0b429] active:bg-[#c89200] text-black text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            {isLoading ? t("loading") : t("submit")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[#52525b]">
          {t("hasAccount")}{" "}
          <Link
            href="/login"
            className="text-[#e5a00d] hover:text-[#f0b429] transition-colors"
          >
            {t("login")}
          </Link>
        </p>
      </div>
    </div>
  );
}
