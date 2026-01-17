"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { FlameLoader } from "@/components/brand";

/**
 * Share Target Page
 * Handles content shared to the PWA from other apps (Android Web Share Target API)
 * The actual content is handled by the service worker, this page just redirects
 */
export default function ShareTargetPage() {
  const router = useRouter();

  useEffect(() => {
    // The service worker handles the POST and stores the shared content
    // This page is just a fallback in case the redirect doesn't work
    // Wait a moment then redirect to chat
    const timeout = setTimeout(() => {
      router.replace("/chat?shared=true");
    }, 500);

    return () => clearTimeout(timeout);
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-950 via-purple-950/20 to-slate-950">
      <FlameLoader size="lg" />
      <p className="mt-6 text-gold-400/80 animate-pulse">
        Receiving shared content...
      </p>
    </div>
  );
}
