"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export type SSEStatus = "connecting" | "connected" | "disconnected" | "error";

export interface SSEMessage<T = unknown> {
  id?: string;
  event?: string;
  data: T;
  retry?: number;
}

export interface UseSSEOptions<T> {
  url: string;
  enabled?: boolean;
  withCredentials?: boolean;
  headers?: Record<string, string>;
  onMessage?: (message: SSEMessage<T>) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  eventTypes?: string[];
}

/**
 * Hook for Server-Sent Events (SSE) connections
 * Provides automatic reconnection and event handling
 */
export function useSSE<T = unknown>({
  url,
  enabled = true,
  withCredentials = true,
  onMessage,
  onError,
  onOpen,
  onClose,
  reconnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
  eventTypes = [],
}: UseSSEOptions<T>) {
  const [status, setStatus] = useState<SSEStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<SSEMessage<T> | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!enabled || typeof window === "undefined") return;

    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setStatus("connecting");
    setError(null);

    try {
      const eventSource = new EventSource(url, { withCredentials });
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setStatus("connected");
        reconnectAttemptsRef.current = 0;
        onOpen?.();
      };

      eventSource.onerror = (event) => {
        setStatus("error");
        setError(new Error("SSE connection error"));
        onError?.(event);

        // Handle reconnection
        if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          const delay =
            reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1);

          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(
              `[SSE] Reconnecting... attempt ${reconnectAttemptsRef.current}`
            );
            connect();
          }, Math.min(delay, 30000)); // Max 30 seconds
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error("[SSE] Max reconnection attempts reached");
          setStatus("disconnected");
        }
      };

      // Default message handler
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as T;
          const message: SSEMessage<T> = {
            id: event.lastEventId,
            data,
          };
          setLastMessage(message);
          onMessage?.(message);
        } catch (e) {
          // Handle non-JSON messages
          const message: SSEMessage<T> = {
            id: event.lastEventId,
            data: event.data as T,
          };
          setLastMessage(message);
          onMessage?.(message);
        }
      };

      // Custom event type handlers
      eventTypes.forEach((eventType) => {
        eventSource.addEventListener(eventType, (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data) as T;
            const message: SSEMessage<T> = {
              id: event.lastEventId,
              event: eventType,
              data,
            };
            setLastMessage(message);
            onMessage?.(message);
          } catch (e) {
            const message: SSEMessage<T> = {
              id: event.lastEventId,
              event: eventType,
              data: event.data as T,
            };
            setLastMessage(message);
            onMessage?.(message);
          }
        });
      });
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e : new Error("Failed to connect"));
    }
  }, [
    url,
    enabled,
    withCredentials,
    onMessage,
    onError,
    onOpen,
    reconnect,
    reconnectInterval,
    maxReconnectAttempts,
    eventTypes,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setStatus("disconnected");
    reconnectAttemptsRef.current = 0;
    onClose?.();
  }, [onClose]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    status,
    lastMessage,
    error,
    connect,
    disconnect,
    isConnected: status === "connected",
    isConnecting: status === "connecting",
  };
}

/**
 * Hook for SSE with agent events
 */
export function useAgentSSE(token: string | null) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return useSSE<{
    type: "agent_status" | "task_update" | "message" | "error";
    agent?: string;
    status?: string;
    task?: unknown;
    message?: unknown;
    error?: string;
  }>({
    url: `${baseUrl}/api/events/agents`,
    enabled: !!token,
    withCredentials: true,
    eventTypes: ["agent_status", "task_update", "message", "error"],
    reconnect: true,
    maxReconnectAttempts: 15,
  });
}

/**
 * Hook for SSE with conversation/chat events
 */
export function useConversationSSE(
  token: string | null,
  conversationId: string | null
) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return useSSE<{
    type: "message" | "typing" | "stream" | "complete" | "error";
    content?: string;
    agent?: string;
    messageId?: string;
  }>({
    url: `${baseUrl}/api/events/conversations/${conversationId}`,
    enabled: !!token && !!conversationId,
    withCredentials: true,
    eventTypes: ["message", "typing", "stream", "complete", "error"],
    reconnect: true,
  });
}
