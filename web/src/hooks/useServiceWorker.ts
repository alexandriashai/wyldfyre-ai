"use client";

import { useEffect, useCallback, useState, useRef } from "react";

interface ServiceWorkerState {
  isSupported: boolean;
  isRegistered: boolean;
  registration: ServiceWorkerRegistration | null;
  updateAvailable: boolean;
  error: Error | null;
}

interface UseServiceWorkerOptions {
  onUpdateAvailable?: () => void;
  onNotificationClick?: (data: NotificationClickData) => void;
  onSharedContent?: (content: string) => void;
}

interface NotificationClickData {
  action?: string;
  url?: string;
  type?: string;
  conversationId?: string;
  agentName?: string;
  navigate?: string;
}

/**
 * Hook for managing service worker interactions
 * Handles updates, notification clicks, shared content, and messaging
 */
export function useServiceWorker(options: UseServiceWorkerOptions = {}) {
  const { onUpdateAvailable, onNotificationClick, onSharedContent } = options;

  const [state, setState] = useState<ServiceWorkerState>({
    isSupported: false,
    isRegistered: false,
    registration: null,
    updateAvailable: false,
    error: null,
  });

  const registrationRef = useRef<ServiceWorkerRegistration | null>(null);

  // Check for shared content on mount
  const checkSharedContent = useCallback(async () => {
    if (!navigator.serviceWorker?.controller) return;

    // Check URL for shared parameter
    const params = new URLSearchParams(window.location.search);
    if (!params.has("shared")) return;

    // Request shared content from service worker
    const messageChannel = new MessageChannel();

    return new Promise<string | null>((resolve) => {
      messageChannel.port1.onmessage = (event) => {
        if (event.data?.content) {
          onSharedContent?.(event.data.content);
          resolve(event.data.content);
        } else {
          resolve(null);
        }
      };

      if (!navigator.serviceWorker.controller) {
        resolve(null);
        return;
      }

      navigator.serviceWorker.controller.postMessage(
        { type: "GET_SHARED_CONTENT" },
        [messageChannel.port2]
      );

      // Timeout after 2 seconds
      setTimeout(() => resolve(null), 2000);
    });
  }, [onSharedContent]);

  // Send platform info to service worker
  const sendPlatformInfo = useCallback(() => {
    if (!navigator.serviceWorker?.controller) return;

    const isIOS =
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

    const isAndroid = /Android/.test(navigator.userAgent);

    navigator.serviceWorker.controller.postMessage({
      type: "SET_PLATFORM",
      isIOS,
      isAndroid,
    });
  }, []);

  // Skip waiting and activate new service worker
  const skipWaiting = useCallback(() => {
    if (registrationRef.current?.waiting) {
      registrationRef.current.waiting.postMessage({ type: "SKIP_WAITING" });
    }
  }, []);

  // Request specific URLs to be cached
  const cacheUrls = useCallback((urls: string[]) => {
    if (!navigator.serviceWorker?.controller) return;

    navigator.serviceWorker.controller.postMessage({
      type: "CACHE_URLS",
      urls,
    });
  }, []);

  // Clear cache
  const clearCache = useCallback(() => {
    if (!navigator.serviceWorker?.controller) return;

    navigator.serviceWorker.controller.postMessage({
      type: "CLEAR_CACHE",
    });
  }, []);

  // Get service worker version
  const getVersion = useCallback(async (): Promise<string | null> => {
    if (!navigator.serviceWorker?.controller) return null;

    const messageChannel = new MessageChannel();

    return new Promise((resolve) => {
      messageChannel.port1.onmessage = (event) => {
        resolve(event.data?.version || null);
      };

      if (!navigator.serviceWorker.controller) {
        resolve(null);
        return;
      }

      navigator.serviceWorker.controller.postMessage(
        { type: "GET_VERSION" },
        [messageChannel.port2]
      );

      setTimeout(() => resolve(null), 2000);
    });
  }, []);

  // Update app badge
  const updateBadge = useCallback((count: number) => {
    if (!navigator.serviceWorker?.controller) return;

    navigator.serviceWorker.controller.postMessage({
      type: "UPDATE_BADGE",
      count,
    });
  }, []);

  // Show notification via service worker
  const showNotification = useCallback(
    (title: string, options?: NotificationOptions) => {
      if (!navigator.serviceWorker?.controller) return;

      navigator.serviceWorker.controller.postMessage({
        type: "SHOW_NOTIFICATION",
        notification: { title, options },
      });
    },
    []
  );

  // Handle messages from service worker
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleMessage = (event: MessageEvent) => {
      if (!event.data) return;

      switch (event.data.type) {
        case "NOTIFICATION_CLICK":
          onNotificationClick?.(event.data);

          // Handle navigation if specified
          if (event.data.navigate) {
            window.location.href = event.data.navigate;
          }
          break;
      }
    };

    navigator.serviceWorker?.addEventListener("message", handleMessage);

    return () => {
      navigator.serviceWorker?.removeEventListener("message", handleMessage);
    };
  }, [onNotificationClick]);

  // Register service worker and handle updates
  useEffect(() => {
    if (typeof window === "undefined") return;

    const isSupported = "serviceWorker" in navigator;
    setState((prev) => ({ ...prev, isSupported }));

    if (!isSupported) return;

    let registration: ServiceWorkerRegistration | null = null;

    const register = async () => {
      try {
        registration = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
        });

        registrationRef.current = registration;

        setState((prev) => ({
          ...prev,
          isRegistered: true,
          registration,
          error: null,
        }));

        // Send platform info once controller is ready
        if (navigator.serviceWorker.controller) {
          sendPlatformInfo();
          checkSharedContent();
        }

        // Listen for new service worker
        registration.addEventListener("updatefound", () => {
          const newWorker = registration?.installing;
          if (!newWorker) return;

          newWorker.addEventListener("statechange", () => {
            if (
              newWorker.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              setState((prev) => ({ ...prev, updateAvailable: true }));
              onUpdateAvailable?.();
            }
          });
        });

        // Check for updates periodically (every 60 seconds)
        const updateInterval = setInterval(() => {
          registration?.update();
        }, 60000);

        return () => clearInterval(updateInterval);
      } catch (error) {
        setState((prev) => ({
          ...prev,
          error: error instanceof Error ? error : new Error("Registration failed"),
        }));
      }
    };

    // Handle controller change (new service worker activated)
    const handleControllerChange = () => {
      sendPlatformInfo();
      // Optionally reload the page
      // window.location.reload();
    };

    navigator.serviceWorker.addEventListener(
      "controllerchange",
      handleControllerChange
    );

    register();

    return () => {
      navigator.serviceWorker.removeEventListener(
        "controllerchange",
        handleControllerChange
      );
    };
  }, [sendPlatformInfo, checkSharedContent, onUpdateAvailable]);

  return {
    ...state,
    skipWaiting,
    cacheUrls,
    clearCache,
    getVersion,
    updateBadge,
    showNotification,
    checkSharedContent,
  };
}

/**
 * Check if app is running as installed PWA
 */
export function isPWA(): boolean {
  if (typeof window === "undefined") return false;

  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true ||
    document.referrer.includes("android-app://")
  );
}

/**
 * Check if device is iOS
 */
export function isIOSDevice(): boolean {
  if (typeof window === "undefined") return false;

  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

/**
 * Check if device is Android
 */
export function isAndroidDevice(): boolean {
  if (typeof window === "undefined") return false;

  return /Android/.test(navigator.userAgent);
}
