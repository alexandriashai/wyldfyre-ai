/**
 * Notification Service - Centralized notification management
 */

import { isClient } from "./utils";

export type NotificationType =
  | "message"
  | "agent_status"
  | "task_complete"
  | "task_failed"
  | "system"
  | "error";

export interface NotificationPayload {
  type: NotificationType;
  title: string;
  body: string;
  icon?: string;
  badge?: string;
  tag?: string;
  data?: Record<string, unknown>;
  actions?: NotificationAction[];
  requireInteraction?: boolean;
  silent?: boolean;
}

export interface NotificationPreferences {
  enabled: boolean;
  messages: boolean;
  agentStatus: boolean;
  taskUpdates: boolean;
  errors: boolean;
  sound: boolean;
  vibrate: boolean;
}

const DEFAULT_PREFERENCES: NotificationPreferences = {
  enabled: true,
  messages: true,
  agentStatus: true,
  taskUpdates: true,
  errors: true,
  sound: true,
  vibrate: true,
};

const PREFERENCES_KEY = "wyld-fyre-notification-preferences";

/**
 * Get notification preferences from localStorage
 */
export function getNotificationPreferences(): NotificationPreferences {
  if (!isClient()) return DEFAULT_PREFERENCES;

  try {
    const stored = localStorage.getItem(PREFERENCES_KEY);
    if (stored) {
      return { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.error("Failed to load notification preferences:", e);
  }

  return DEFAULT_PREFERENCES;
}

/**
 * Save notification preferences to localStorage
 */
export function setNotificationPreferences(
  preferences: Partial<NotificationPreferences>
): void {
  if (!isClient()) return;

  try {
    const current = getNotificationPreferences();
    const updated = { ...current, ...preferences };
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(updated));
  } catch (e) {
    console.error("Failed to save notification preferences:", e);
  }
}

/**
 * Check if a notification type should be shown based on preferences
 */
export function shouldShowNotification(type: NotificationType): boolean {
  const prefs = getNotificationPreferences();

  if (!prefs.enabled) return false;

  switch (type) {
    case "message":
      return prefs.messages;
    case "agent_status":
      return prefs.agentStatus;
    case "task_complete":
    case "task_failed":
      return prefs.taskUpdates;
    case "error":
      return prefs.errors;
    case "system":
      return true;
    default:
      return true;
  }
}

/**
 * Get default icon for notification type
 */
function getNotificationIcon(type: NotificationType): string {
  const icons: Record<NotificationType, string> = {
    message: "/icons/notification-message.png",
    agent_status: "/icons/notification-agent.png",
    task_complete: "/icons/notification-success.png",
    task_failed: "/icons/notification-error.png",
    system: "/icons/icon-192x192.png",
    error: "/icons/notification-error.png",
  };
  return icons[type] || "/icons/icon-192x192.png";
}

/**
 * Show a notification using the service worker
 */
export async function showNotification(
  payload: NotificationPayload
): Promise<boolean> {
  if (!isClient()) return false;

  // Check preferences
  if (!shouldShowNotification(payload.type)) {
    return false;
  }

  // Check if notifications are supported and permission granted
  if (!("Notification" in window)) {
    console.warn("Notifications not supported");
    return false;
  }

  if (Notification.permission !== "granted") {
    console.warn("Notification permission not granted");
    return false;
  }

  const prefs = getNotificationPreferences();

  try {
    const registration = await navigator.serviceWorker.ready;

    const options: NotificationOptions = {
      body: payload.body,
      icon: payload.icon || getNotificationIcon(payload.type),
      badge: payload.badge || "/icons/icon-72x72.png",
      tag: payload.tag || `wyld-fyre-${payload.type}-${Date.now()}`,
      data: {
        type: payload.type,
        url: "/",
        timestamp: Date.now(),
        ...payload.data,
      },
      actions: payload.actions,
      requireInteraction: payload.requireInteraction,
      silent: payload.silent || !prefs.sound,
      vibrate: prefs.vibrate ? [100, 50, 100] : undefined,
    };

    await registration.showNotification(payload.title, options);
    return true;
  } catch (e) {
    console.error("Failed to show notification:", e);
    return false;
  }
}

/**
 * Notification helpers for specific events
 */
export const notifications = {
  /**
   * New chat message notification
   */
  newMessage: (from: string, preview: string, conversationId: string) => {
    return showNotification({
      type: "message",
      title: `Message from ${from}`,
      body: preview.length > 100 ? preview.slice(0, 100) + "..." : preview,
      tag: `message-${conversationId}`,
      data: {
        conversationId,
        url: `/chat?conversation=${conversationId}`,
      },
      actions: [
        { action: "reply", title: "Reply" },
        { action: "dismiss", title: "Dismiss" },
      ],
    });
  },

  /**
   * Agent status change notification
   */
  agentStatus: (
    agentName: string,
    status: "online" | "offline" | "busy" | "error",
    message?: string
  ) => {
    const statusMessages: Record<string, string> = {
      online: `${agentName} is now online and ready`,
      offline: `${agentName} has gone offline`,
      busy: `${agentName} is currently busy`,
      error: `${agentName} encountered an error`,
    };

    return showNotification({
      type: "agent_status",
      title: `Agent Status: ${agentName}`,
      body: message || statusMessages[status] || `Status: ${status}`,
      tag: `agent-status-${agentName.toLowerCase()}`,
      data: {
        agent: agentName,
        status,
        url: `/agents/${agentName.toLowerCase()}`,
      },
    });
  },

  /**
   * Task completed notification
   */
  taskComplete: (taskName: string, taskId: string, result?: string) => {
    return showNotification({
      type: "task_complete",
      title: "Task Completed",
      body: result || `"${taskName}" has been completed successfully`,
      tag: `task-${taskId}`,
      data: {
        taskId,
        url: `/tasks/${taskId}`,
      },
    });
  },

  /**
   * Task failed notification
   */
  taskFailed: (taskName: string, taskId: string, error?: string) => {
    return showNotification({
      type: "task_failed",
      title: "Task Failed",
      body: error || `"${taskName}" failed to complete`,
      tag: `task-${taskId}`,
      requireInteraction: true,
      data: {
        taskId,
        url: `/tasks/${taskId}`,
      },
    });
  },

  /**
   * System notification
   */
  system: (title: string, body: string, data?: Record<string, unknown>) => {
    return showNotification({
      type: "system",
      title,
      body,
      data,
    });
  },

  /**
   * Error notification
   */
  error: (title: string, error: string) => {
    return showNotification({
      type: "error",
      title,
      body: error,
      requireInteraction: true,
    });
  },
};

/**
 * Register push subscription with the server
 */
export async function registerPushSubscription(
  token: string,
  subscription: {
    endpoint: string;
    keys: { p256dh: string; auth: string };
  }
): Promise<boolean> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/api/notifications/subscribe`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(subscription),
    });

    return response.ok;
  } catch (e) {
    console.error("Failed to register push subscription:", e);
    return false;
  }
}

/**
 * Unregister push subscription from the server
 */
export async function unregisterPushSubscription(
  token: string,
  endpoint: string
): Promise<boolean> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/api/notifications/unsubscribe`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ endpoint }),
    });

    return response.ok;
  } catch (e) {
    console.error("Failed to unregister push subscription:", e);
    return false;
  }
}
