"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { CommandPalette } from "@/components/command-palette";
import { PWAInstallPrompt } from "@/components/pwa/install-prompt";
import { PWAUpdatePrompt } from "@/components/pwa/update-prompt";
import { NetworkStatus } from "@/components/pwa/network-status";
import { FlameLoader } from "@/components/brand/logo";
import { ErrorBoundary } from "@/components/error-boundary";
import { SwipeNavigationProvider } from "@/hooks/useSwipeNavigation";

// Service Worker Registration
function useServiceWorker() {
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      "serviceWorker" in navigator &&
      process.env.NODE_ENV === "production"
    ) {
      navigator.serviceWorker
        .register("/sw.js")
        .then((registration) => {
          console.log("SW registered:", registration.scope);

          // Check for updates
          registration.addEventListener("updatefound", () => {
            const newWorker = registration.installing;
            if (newWorker) {
              newWorker.addEventListener("statechange", () => {
                if (
                  newWorker.state === "installed" &&
                  navigator.serviceWorker.controller
                ) {
                  // New content available
                  console.log("New content available, refresh to update");
                }
              });
            }
          });
        })
        .catch((error) => {
          console.error("SW registration failed:", error);
        });
    }
  }, []);
}

// Theme initialization
function useTheme() {
  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const root = document.documentElement;

    if (stored === "dark" || stored === "light") {
      root.classList.add(stored);
    } else {
      // System preference
      const systemDark = window.matchMedia(
        "(prefers-color-scheme: dark)"
      ).matches;
      root.classList.add(systemDark ? "dark" : "light");
    }
  }, []);
}

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const { initialize } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);

  // Register service worker
  useServiceWorker();

  // Initialize theme
  useTheme();

  useEffect(() => {
    initialize().finally(() => setIsInitialized(true));
  }, [initialize]);

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <FlameLoader className="h-16 w-16" />
          <p className="text-sm text-muted-foreground animate-pulse">
            Loading Wyld Fyre...
          </p>
        </div>
      </div>
    );
  }

  return (
    <SwipeNavigationProvider>
      {children}
    </SwipeNavigationProvider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  );

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <AuthInitializer>
            {children}
            <CommandPalette />
            <PWAInstallPrompt />
            <PWAUpdatePrompt />
            <NetworkStatus />
            <Toaster />
          </AuthInitializer>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
