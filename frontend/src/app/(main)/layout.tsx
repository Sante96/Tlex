"use client";

import { useEffect, useState, ViewTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import {
  Sidebar,
  TopBar,
  BottomNav,
  SIDEBAR_EXPANDED,
  SIDEBAR_COLLAPSED,
  TV_WIDTHS,
} from "@/components/layout";
import { AuthGuard } from "@/components/auth-guard";
import { SplashScreen } from "@/components/splash-screen";
import { NAV_MOTION } from "@/components/ds/nav-item";
import { SidebarProvider, useSidebar } from "@/contexts/sidebar-context";
import { useProfile } from "@/contexts/profile-context";
import { useIsMobile, useIsTablet } from "@/lib/breakpoints";
import { useIsTV, useTVTier } from "@/hooks/use-platform";
import { AppBackground } from "@/components/layout/app-background";
import { useDelayed } from "@/hooks/use-delayed";


/** Progress and the watchlist belong to a profile: a device that hasn't picked one goes
 * to the picker, or takes the only one there is. It used to browse without a profile. */
function ProfileGate({ children }: { children: React.ReactNode }) {
  const { needsProfileSelection, isLoading, profiles, selectProfile } = useProfile();
  const router = useRouter();
  const showLoader = useDelayed(isLoading || needsProfileSelection);

  useEffect(() => {
    if (!needsProfileSelection) return;
    if (profiles.length === 1) selectProfile(profiles[0]);
    else router.replace("/profiles");
  }, [needsProfileSelection, profiles, selectProfile, router]);

  if (isLoading || needsProfileSelection) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        {showLoader && <Loader2 className="h-8 w-8 text-plex-orange animate-spin" />}
      </div>
    );
  }
  return <>{children}</>;
}

function MainContent({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const isTV = useIsTV();
  const tvTier = useTVTier();
  const tvWidths = TV_WIDTHS[tvTier ?? "1080"];
  const marginLeft = isMobile
    ? 0
    : isTV
      ? // The TV sidebar opens over the page: pushing it re-laid the poster grid on every
        // frame of the animation, on the TV's weak hardware
        tvWidths.collapsed
      : // On a tablet too: open, it took a third of an upright iPad
        isCollapsed || isTablet
        ? SIDEBAR_COLLAPSED
        : SIDEBAR_EXPANDED;

  return (
    <motion.div
      initial={false}
      animate={{ marginLeft }}
      transition={NAV_MOTION}
    >
      <TopBar />
      <main className="pb-(--bottom-nav-space) md:pb-0 landscape:pb-0">
        {/* Navigations run in a transition: the old page fades out and the new one in
            (globals.css). The browser animates snapshots, so the glass keeps its blur. */}
        <ViewTransition name="page">
          <div>{children}</div>
        </ViewTransition>
      </main>
    </motion.div>
  );
}

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [showSplash, setShowSplash] = useState(() => {
    if (typeof window !== "undefined") {
      return !sessionStorage.getItem("splashShown");
    }
    return true;
  });

  const handleSplashComplete = () => {
    sessionStorage.setItem("splashShown", "true");
    setShowSplash(false);
  };

  return (
    <AuthGuard requireAuth={true} redirectTo="/login">
      <ProfileGate>
        {showSplash && <SplashScreen onComplete={handleSplashComplete} />}
        <SidebarProvider>
          {/* Sideways, clear of the notch (the sidebar is fixed: it moves by itself) */}
          <div className="min-h-screen pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]">
            <AppBackground />
            <Sidebar />
            <MainContent>{children}</MainContent>
            <BottomNav />
          </div>
        </SidebarProvider>
      </ProfileGate>
    </AuthGuard>
  );
}
