"use client";

import { useState } from "react";
import {
  Sidebar,
  TopBar,
  SIDEBAR_WIDTH_EXPANDED,
  SIDEBAR_WIDTH_COLLAPSED,
} from "@/components/layout";
import { AuthGuard } from "@/components/auth-guard";
import { SidebarProvider, useSidebar } from "@/contexts/sidebar-context";
import { SplashScreen } from "@/components/splash-screen";

function MainLayoutContent({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const sidebarWidth = isCollapsed
    ? SIDEBAR_WIDTH_COLLAPSED
    : SIDEBAR_WIDTH_EXPANDED;
  const [showSplash, setShowSplash] = useState(() => {
    // Check if splash was already shown this session (runs only on client)
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
    <>
      {showSplash && <SplashScreen onComplete={handleSplashComplete} />}
      <div className="min-h-screen bg-zinc-950">
        <Sidebar />
        <div
          className="transition-all duration-300"
          style={{ marginLeft: sidebarWidth }}
        >
          <TopBar />
          <main className="p-6">{children}</main>
        </div>
      </div>
    </>
  );
}

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard requireAuth={true} redirectTo="/login">
      <SidebarProvider>
        <MainLayoutContent>{children}</MainLayoutContent>
      </SidebarProvider>
    </AuthGuard>
  );
}
