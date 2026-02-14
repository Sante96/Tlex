"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Sidebar,
  TopBar,
  SIDEBAR_EXPANDED,
  SIDEBAR_COLLAPSED,
} from "@/components/layout";
import { AuthGuard } from "@/components/auth-guard";
import { SplashScreen } from "@/components/splash-screen";
import { RouteTransitionProvider } from "@/contexts/route-transition-context";
import { SidebarProvider, useSidebar } from "@/contexts/sidebar-context";

function MainContent({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const marginLeft = isCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

  return (
    <motion.div
      animate={{ marginLeft }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      <TopBar />
      <main>
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
        <div className="min-h-screen" style={{ backgroundColor: "#09090b" }}>
          <Sidebar />
          <MainContent>{children}</MainContent>
        </div>
      </SidebarProvider>
    </AuthGuard>
  );
}
