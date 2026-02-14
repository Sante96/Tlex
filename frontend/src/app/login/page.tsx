"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { DSButton, DSCard, DSInput } from "@/components/ds";
import { useAuth } from "@/contexts/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({ email, password });
      router.push("/profiles");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-plex-orange/10 via-zinc-950 to-zinc-950" />

      <DSCard className="w-full max-w-md relative z-10 !bg-zinc-900/90 backdrop-blur">
        <div className="text-center pb-2 mb-4">
          <Link href="/" className="inline-block mb-4">
            <span className="text-4xl font-bold text-plex-orange">TLEX</span>
          </Link>
          <h1 className="text-2xl font-semibold text-white">Bentornato</h1>
          <p className="text-sm text-[#a1a1aa] mt-1">
            Accedi al tuo account per continuare
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <DSInput
            id="email"
            label="Email"
            type="email"
            placeholder="tu@esempio.com"
            value={email}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setEmail(e.target.value)
            }
            required
          />

          <DSInput
            id="password"
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={password}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setPassword(e.target.value)
            }
            required
            suffix={
              <button
                type="button"
                className="text-[#71717a] hover:text-white transition-colors"
                onClick={() => setShowPassword(!showPassword)}
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
            className="w-full"
            disabled={isLoading}
            icon={
              isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : undefined
            }
          >
            {isLoading ? "Accesso in corso..." : "Accedi"}
          </DSButton>
        </form>

        <div className="mt-6 text-center text-sm text-[#52525b]">
          Non hai un account?{" "}
          <Link
            href="/register"
            className="text-plex-orange hover:text-plex-orange/80"
          >
            Registrati
          </Link>
        </div>
      </DSCard>
    </div>
  );
}
