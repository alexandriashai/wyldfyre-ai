"use client";

import { useEffect, useState, useCallback } from "react";
import { isClient } from "@/lib/utils";

export type PushPermission = "granted" | "denied" | "default" | "unsupported";

export interface PushSubscriptionData {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface UsePushNotificationsResult {
  permission: PushPermission;
  isSupported: boolean;
  isSubscribed: boolean;
  isLoading: boolean;
  error: Error | null;
  subscribe: () => Promise<PushSubscriptionData | null>;
  unsubscribe: () => Promise<boolean>;
  requestPermission: () => Promise<PushPermission>;
}

/**
 * VAPID public key - should be set via environment variable
 * Generate with: npx web-push generate-vapid-keys
 */
const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

/**
 * Convert URL-safe base64 to Uint8Array for VAPID key
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Hook for managing Web Push Notifications
 */
export function usePushNotifications(): UsePushNotificationsResult {
  const [permission, setPermission] = useState<PushPermission>("default");
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const isSupported =
    isClient() &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window;

  // Check current permission and subscription status
  useEffect(() => {
    if (!isSupported) {
      setPermission("unsupported");
      setIsLoading(false);
      return;
    }

    // Get current permission
    setPermission(Notification.permission as PushPermission);

    // Check if already subscribed
    navigator.serviceWorker.ready.then(async (registration) => {
      try {
        const subscription = await registration.pushManager.getSubscription();
        setIsSubscribed(!!subscription);
      } catch (e) {
        console.error("Error checking push subscription:", e);
      } finally {
        setIsLoading(false);
      }
    });
  }, [isSupported]);

  const requestPermission = useCallback(async (): Promise<PushPermission> => {
    if (!isSupported) {
      return "unsupported";
    }

    try {
      const result = await Notification.requestPermission();
      setPermission(result as PushPermission);
      return result as PushPermission;
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Permission request failed"));
      return "denied";
    }
  }, [isSupported]);

  const subscribe = useCallback(async (): Promise<PushSubscriptionData | null> => {
    if (!isSupported) {
      setError(new Error("Push notifications not supported"));
      return null;
    }

    if (!VAPID_PUBLIC_KEY) {
      setError(new Error("VAPID public key not configured"));
      return null;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Request permission if not granted
      if (Notification.permission !== "granted") {
        const permission = await requestPermission();
        if (permission !== "granted") {
          throw new Error("Notification permission denied");
        }
      }

      // Get service worker registration
      const registration = await navigator.serviceWorker.ready;

      // Check for existing subscription
      let subscription = await registration.pushManager.getSubscription();

      // Create new subscription if none exists
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }

      // Extract subscription data
      const subscriptionJson = subscription.toJSON();
      const subscriptionData: PushSubscriptionData = {
        endpoint: subscriptionJson.endpoint!,
        keys: {
          p256dh: subscriptionJson.keys!.p256dh,
          auth: subscriptionJson.keys!.auth,
        },
      };

      setIsSubscribed(true);
      return subscriptionData;
    } catch (e) {
      const error = e instanceof Error ? e : new Error("Subscription failed");
      setError(error);
      console.error("Push subscription error:", e);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported, requestPermission]);

  const unsubscribe = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await subscription.unsubscribe();
      }

      setIsSubscribed(false);
      return true;
    } catch (e) {
      const error = e instanceof Error ? e : new Error("Unsubscribe failed");
      setError(error);
      console.error("Push unsubscribe error:", e);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported]);

  return {
    permission,
    isSupported,
    isSubscribed,
    isLoading,
    error,
    subscribe,
    unsubscribe,
    requestPermission,
  };
}

/**
 * Send a local notification (for testing or fallback)
 */
export async function sendLocalNotification(
  title: string,
  options?: NotificationOptions
): Promise<boolean> {
  if (!isClient() || !("Notification" in window)) {
    return false;
  }

  if (Notification.permission !== "granted") {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      return false;
    }
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    await registration.showNotification(title, {
      icon: "/icons/icon-192x192.png",
      badge: "/icons/icon-72x72.png",
      vibrate: [100, 50, 100],
      ...options,
    });
    return true;
  } catch (e) {
    console.error("Local notification error:", e);
    return false;
  }
}

/**
 * Check if device is iOS (for special handling)
 */
export function isIOSDevice(): boolean {
  if (!isClient()) return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

/**
 * Check if running as iOS PWA (limited push support)
 */
export function isIOSPWA(): boolean {
  if (!isClient()) return false;
  return (
    isIOSDevice() &&
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}
