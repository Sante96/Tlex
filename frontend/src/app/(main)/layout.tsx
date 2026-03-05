"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import {
  Sidebar,
  TopBar,
  BottomNav,
  SIDEBAR_EXPANDED,
  SIDEBAR_COLLAPSED,
} from "@/components/layout";
import { TVBackground } from "@/components/ds";
import { AuthGuard } from "@/components/auth-guard";
import { SplashScreen } from "@/components/splash-screen";
import { RouteTransitionProvider } from "@/contexts/route-transition-context";
import { SidebarProvider, useSidebar } from "@/contexts/sidebar-context";
import { useIsMobile } from "@/lib/breakpoints";
import { useIsTV } from "@/hooks/use-platform";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => ({ default: m.MeshGradient })),
  { ssr: false },
);

function MainContent({ children }: { children: React.ReactNode }) {
  const { isCollapsed, tvExpanded } = useSidebar();
  const isMobile = useIsMobile();
  const isTV = useIsTV();
  const marginLeft = isMobile
    ? 0
    : isTV
      ? tvExpanded ? SIDEBAR_EXPANDED : SIDEBAR_COLLAPSED
      : isCollapsed
        ? SIDEBAR_COLLAPSED
        : SIDEBAR_EXPANDED;

  return (
    <motion.div
      animate={{ marginLeft }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      <TopBar />
      <main className="pb-16 md:pb-0 landscape:pb-0">
        <RouteTransitionProvider>{children}</RouteTransitionProvider>
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
    </AuthGuard>
  );
}
