"use client";

import * as React from "react";
import { Wifi, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

export function NetworkStatus() {
  const [isOnline, setIsOnline] = React.useState(true);
  const [showBanner, setShowBanner] = React.useState(false);

  React.useEffect(() => {
    // Set initial state
    setIsOnline(navigator.onLine);

    const handleOnline = () => {
      setIsOnline(true);
      // Show "back online" briefly
      setShowBanner(true);
      setTimeout(() => setShowBanner(false), 3000);
    };

    const handleOffline = () => {
      setIsOnline(false);
      setShowBanner(true);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  if (!showBanner) return null;

  return (
    <div
      className={cn(
        "fixed top-0 left-0 right-0 z-50 flex items-center justify-center gap-2 py-2 text-sm font-medium transition-all duration-300",
        isOnline
          ? "bg-emerald-500 text-white"
          : "bg-amber-500 text-amber-950"
      )}
    >
      {isOnline ? (
        <>
          <Wifi className="h-4 w-4" />
          Back online
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4" />
          You&apos;re offline - some features may be unavailable
        </>
      )}
    </div>
  );
}

// Inline status indicator (for headers/footers)
export function NetworkStatusIndicator({ className }: { className?: string }) {
  const [isOnline, setIsOnline] = React.useState(true);

  React.useEffect(() => {
    setIsOnline(navigator.onLine);

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return (
    <div
      className={cn(
        "flex items-center gap-1.5 text-xs",
        isOnline ? "text-emerald-500" : "text-amber-500",
        className
      )}
    >
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          isOnline ? "bg-emerald-500" : "bg-amber-500 animate-pulse"
        )}
      />
      {isOnline ? "Online" : "Offline"}
    </div>
  );
}
