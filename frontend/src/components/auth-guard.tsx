"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useDelayed } from "@/hooks/use-delayed";

interface AuthGuardProps {
  children: React.ReactNode;
  /** false: a guest-only page (login, register), left once signed in */
  requireAuth?: boolean;
  /** Where to go when the page isn't for this visitor */
  redirectTo?: string;
}

export function AuthGuard({
  children,
  requireAuth = true,
  redirectTo = requireAuth ? "/login" : "/",
}: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const showLoader = useDelayed(isLoading);
  const router = useRouter();

  // replace, not push: a redirect must not leave a history entry, or Back from
  // /login lands on the guarded page, which redirects to /login again (and on
  // the TV app Back could never leave the app)
  useEffect(() => {
    if (!isLoading) {
      if (requireAuth && !isAuthenticated) {
        router.replace(redirectTo);
      } else if (!requireAuth && isAuthenticated) {
        router.replace(redirectTo);
      }
    }
  }, [isAuthenticated, isLoading, requireAuth, redirectTo, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        {showLoader && <Loader2 className="h-8 w-8 text-plex-orange animate-spin" />}
      </div>
    );
  }

  if (requireAuth && !isAuthenticated) {
    return null;
  }

  if (!requireAuth && isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
