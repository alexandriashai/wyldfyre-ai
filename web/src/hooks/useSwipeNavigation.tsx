"use client";

import React, { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

interface SwipeConfig {
  threshold?: number; // Minimum distance for a swipe (default: 100px)
  allowedTime?: number; // Maximum time for a swipe gesture (default: 300ms)
  disableOnInputs?: boolean; // Disable when touching inputs (default: true)
}

/**
 * Hook to enable swipe gestures for browser navigation on mobile.
 * - Swipe right (from left edge): Go back in history
 * - Swipe left (from right edge): Go forward in history
 */
export function useSwipeNavigation(config: SwipeConfig = {}) {
  const {
    threshold = 80,
    allowedTime = 400,
    disableOnInputs = true,
  } = config;

  const router = useRouter();
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const touchStartTime = useRef(0);
  const isTracking = useRef(false);

  useEffect(() => {
    // Only enable on touch devices
    if (typeof window === "undefined" || !("ontouchstart" in window)) {
      return;
    }

    const handleTouchStart = (e: TouchEvent) => {
      // Check if we should disable on inputs
      if (disableOnInputs) {
        const target = e.target as HTMLElement;
        const tagName = target.tagName.toLowerCase();
        if (
          tagName === "input" ||
          tagName === "textarea" ||
          tagName === "select" ||
          target.isContentEditable ||
          target.closest("[data-no-swipe]")
        ) {
          isTracking.current = false;
          return;
        }
      }

      const touch = e.touches[0];
      const screenWidth = window.innerWidth;

      // Only track swipes that start from edges (within 30px of edge)
      const edgeThreshold = 30;
      const isFromLeftEdge = touch.clientX < edgeThreshold;
      const isFromRightEdge = touch.clientX > screenWidth - edgeThreshold;

      if (!isFromLeftEdge && !isFromRightEdge) {
        isTracking.current = false;
        return;
      }

      isTracking.current = true;
      touchStartX.current = touch.clientX;
      touchStartY.current = touch.clientY;
      touchStartTime.current = Date.now();
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (!isTracking.current) return;
      isTracking.current = false;

      const touch = e.changedTouches[0];
      const deltaX = touch.clientX - touchStartX.current;
      const deltaY = touch.clientY - touchStartY.current;
      const elapsedTime = Date.now() - touchStartTime.current;

      // Check if it's a valid horizontal swipe
      if (elapsedTime > allowedTime) return;
      if (Math.abs(deltaX) < threshold) return;
      if (Math.abs(deltaY) > Math.abs(deltaX) * 0.5) return; // Too vertical

      if (deltaX > 0 && touchStartX.current < 30) {
        // Swiped right from left edge - go back
        e.preventDefault();
        router.back();
      } else if (deltaX < 0 && touchStartX.current > window.innerWidth - 30) {
        // Swiped left from right edge - go forward
        e.preventDefault();
        router.forward();
      }
    };

    // Use passive: false to allow preventDefault
    document.addEventListener("touchstart", handleTouchStart, { passive: true });
    document.addEventListener("touchend", handleTouchEnd, { passive: false });

    return () => {
      document.removeEventListener("touchstart", handleTouchStart);
      document.removeEventListener("touchend", handleTouchEnd);
    };
  }, [threshold, allowedTime, disableOnInputs, router]);
}

/**
 * Provider component to enable swipe navigation globally.
 * Add this to your root layout.
 */
export function SwipeNavigationProvider({ children }: { children: React.ReactNode }) {
  useSwipeNavigation();
  return <>{children}</>;
}
