"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import {
  Sidebar,
  TopBar,
  BottomNav,
  SIDEBAR_EXPANDED,
  SIDEBAR_COLLAPSED,
  TV_WIDTHS,
} from "@/components/layout";
import { TVBackground } from "@/components/ds";
import { AuthGuard } from "@/components/auth-guard";
import { SplashScreen } from "@/components/splash-screen";
import { SidebarProvider, useSidebar } from "@/contexts/sidebar-context";
import { useProfile } from "@/contexts/profile-context";
import { useIsMobile } from "@/lib/breakpoints";
import { useIsTV, useTVTier } from "@/hooks/use-platform";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => ({ default: m.MeshGradient })),
  { ssr: false },
);

/** Progress and the watchlist belong to a profile: a device that hasn't picked one goes
 * to the picker, or takes the only one there is. It used to browse without a profile. */
function ProfileGate({ children }: { children: React.ReactNode }) {
  const { needsProfileSelection, isLoading, profiles, selectProfile } = useProfile();
  const router = useRouter();

  useEffect(() => {
    if (!needsProfileSelection) return;
    if (profiles.length === 1) selectProfile(profiles[0]);
    else router.replace("/profiles");
  }, [needsProfileSelection, profiles, selectProfile, router]);

  if (isLoading || needsProfileSelection) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <Loader2 className="h-8 w-8 text-[#e5a00d] animate-spin" />
      </div>
    );
  }
  return <>{children}</>;
}

function MainContent({ children }: { children: React.ReactNode }) {
  const { isCollapsed, tvExpanded } = useSidebar();
  const isMobile = useIsMobile();
  const isTV = useIsTV();
  const tvTier = useTVTier();
  const tvWidths = TV_WIDTHS[tvTier ?? "1080"];
  const marginLeft = isMobile
    ? 0
    : isTV
      ? tvExpanded ? tvWidths.expanded : tvWidths.collapsed
      : isCollapsed
        ? SIDEBAR_COLLAPSED
        : SIDEBAR_EXPANDED;

  return (
    <motion.div
      initial={false}
      animate={{ marginLeft }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      <TopBar />
      <main className="pb-16 md:pb-0 landscape:pb-0">
        {children}
      </main>
    </motion.div>
  );
}

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isTV = useIsTV();

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
          <div className="min-h-screen">
            {/* Background — TVBackground (CSS) on TV, animated shader on web */}
            {isTV ? (
              <div className="fixed inset-0 z-[-1]">
                <TVBackground />
              </div>
            ) : (
              <div className="fixed inset-0 z-[-1]">
                <MeshGradient
                  style={{ width: "100%", height: "100%" }}
                  colors={["#09090b", "#1c1500", "#09090b"]}
                  distortion={1}
                  swirl={0.1}
                  grainMixer={0}
                  grainOverlay={0}
                  speed={0.25}
                />
                <div
                  className="absolute inset-0"
                  style={{ backgroundColor: "rgba(9,9,11,0.45)" }}
                />
              </div>
            )}
            <Sidebar />
            <MainContent>{children}</MainContent>
            <BottomNav />
          </div>
        </SidebarProvider>
      </ProfileGate>
    </AuthGuard>
  );
}
