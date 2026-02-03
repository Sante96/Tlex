"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Le password non coincidono");
      return;
    }

    if (password.length < 8) {
      setError("La password deve essere di almeno 8 caratteri");
      return;
    }

    setIsLoading(true);

    try {
      await register(email, password);
      router.push("/login?registered=true");
    } catch (err) {
      if (err instanceof Error) {
        setError(
          err.message.includes("400")
            ? "Email already registered"
            : err.message,
        );
      } else {
        setError("Registration failed");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      <div className="absolute inset-0 bg-gradient-to-br from-plex-orange/10 via-zinc-950 to-zinc-950" />

      <Card className="w-full max-w-md relative z-10 bg-zinc-900/90 border-zinc-800 backdrop-blur">
        <CardHeader className="text-center pb-2">
          <Link href="/" className="inline-block mb-4">
            <span className="text-4xl font-bold text-plex-orange">TLEX</span>
          </Link>
          <CardTitle className="text-2xl text-white">Crea account</CardTitle>
          <CardDescription className="text-zinc-400">
            Registrati per iniziare lo streaming
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" className="text-zinc-300">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="tu@esempio.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-plex-orange focus:ring-plex-orange"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-zinc-300">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 pr-10 focus:border-plex-orange focus:ring-plex-orange"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 text-zinc-400 hover:text-white"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-zinc-300">
                Conferma Password
              </Label>
              <Input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-plex-orange focus:ring-plex-orange"
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-plex-orange hover:bg-plex-orange/90 text-black font-semibold"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creazione account...
                </>
              ) : (
                "Registrati"
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-zinc-500">
            Hai già un account?{" "}
            <Link
              href="/login"
              className="text-plex-orange hover:text-plex-orange/80"
            >
              Accedi
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
