"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useAgentStore } from "@/stores/agent-store";
import { useAuthStore } from "@/stores/auth-store";

// Use wss:// for secure connection, endpoint is /ws/chat
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "wss://api.wyldfyre.ai";

interface ChatMessage {
  type: "message" | "token" | "connected" | "pong" | "error" | "agent_status" | "agent_action" | "subscribed" | "unsubscribed" | "message_ack";
  conversation_id?: string;
  message_id?: string;
  content?: string;
  token?: string;
  agent?: string;
  status?: string;
  task?: string;
  action?: string;
  description?: string;
  user_id?: string;
  username?: string;
  timestamp?: string;
  error?: string;
}

export function useChat() {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const { token } = useAuthStore();
  const {
    currentConversation,
    addMessage,
    updateStreamingMessage,
    finalizeStreamingMessage,
    clearStreamingMessage,
    setIsSending,
  } = useChatStore();
  const { updateAgentStatus, addAgentAction, clearAgentActions } = useAgentStore();

  // Build WebSocket URL with token
  const getWsUrl = useCallback(() => {
    if (!token) return null;
    // Remove any trailing /ws if present, we'll add the full path
    const baseUrl = WS_BASE_URL.replace(/\/ws\/?$/, "");
    return `${baseUrl}/ws/chat?token=${encodeURIComponent(token)}`;
  }, [token]);

  const startPingInterval = useCallback(() => {
    // Send ping every 25 seconds to keep connection alive
    pingIntervalRef.current = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);
  }, []);

  const stopPingInterval = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: ChatMessage = JSON.parse(event.data);

      switch (data.type) {
        case "connected":
          console.log("WebSocket connected:", data.username);
          break;

        case "message":
          if (data.content) {
            addMessage({
              id: data.message_id || crypto.randomUUID(),
              role: "assistant",
              content: data.content,
              agent: data.agent,
              created_at: data.timestamp || new Date().toISOString(),
            });
            setIsSending(false);
          }
          break;

        case "token":
          // Streaming token
          if (data.token) {
            updateStreamingMessage(data.token);
          }
          break;

        case "agent_status":
          if (data.agent && data.status) {
            updateAgentStatus(data.agent, data.status, data.task);
          }
          break;

        case "agent_action":
          console.log("[WebSocket] Received agent_action:", data);
          if (data.agent && data.action && data.description) {
            addAgentAction(data.agent, data.action, data.description, data.timestamp);
          }
          break;

        case "message_ack":
          // Message acknowledgment, clear previous actions for new task
          clearAgentActions();
          break;

        case "pong":
          // Heartbeat response, ignore
          break;

        case "subscribed":
        case "unsubscribed":
          // Subscription confirmation, ignore
          break;

        case "error":
          console.error("Server error:", data.error);
          clearStreamingMessage();
          setIsSending(false);
          break;

        default:
          console.log("Unknown message type:", data.type);
      }
    } catch (e) {
      console.error("Failed to parse WebSocket message:", e);
    }
  }, [addMessage, updateStreamingMessage, clearStreamingMessage, setIsSending, updateAgentStatus, addAgentAction, clearAgentActions]);

  const connect = useCallback(() => {
    const wsUrl = getWsUrl();
    if (!wsUrl || socketRef.current?.readyState === WebSocket.OPEN) return;

    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    setIsConnecting(true);

    try {
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
        startPingInterval();
        console.log("WebSocket connected");
      };

      socket.onclose = (event) => {
        setIsConnected(false);
        setIsConnecting(false);
        stopPingInterval();

        // Don't reconnect if closed normally (code 1000) or auth failed (4001)
        if (event.code !== 1000 && event.code !== 4001) {
          // Attempt to reconnect with exponential backoff
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            reconnectAttemptsRef.current++;
            console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);
            reconnectTimeoutRef.current = setTimeout(connect, delay);
          }
        }
      };

      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsConnecting(false);
      };

      socket.onmessage = handleMessage;

      socketRef.current = socket;
    } catch (e) {
      console.error("Failed to create WebSocket:", e);
      setIsConnecting(false);
    }
  }, [getWsUrl, handleMessage, startPingInterval, stopPingInterval]);

  const disconnect = useCallback(() => {
    stopPingInterval();

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.close(1000, "User disconnected");
      socketRef.current = null;
      setIsConnected(false);
    }
  }, [stopPingInterval]);

  const sendMessage = useCallback(
    (content: string) => {
      if (socketRef.current?.readyState !== WebSocket.OPEN || !currentConversation) {
        console.error("Not connected or no conversation selected");
        return;
      }

      // Add user message immediately
      const userMessage = {
        id: crypto.randomUUID(),
        role: "user" as const,
        content,
        created_at: new Date().toISOString(),
      };
      addMessage(userMessage);
      setIsSending(true);

      // Send to server
      socketRef.current.send(JSON.stringify({
        type: "chat",
        conversation_id: currentConversation.id,
        content,
      }));
    },
    [currentConversation, addMessage, setIsSending]
  );

  const subscribeToConversation = useCallback(
    (conversationId: string) => {
      if (socketRef.current?.readyState !== WebSocket.OPEN) return;

      socketRef.current.send(JSON.stringify({
        type: "subscribe",
        conversation_id: conversationId,
      }));
    },
    []
  );

  const unsubscribeFromConversation = useCallback(
    (conversationId: string) => {
      if (socketRef.current?.readyState !== WebSocket.OPEN) return;

      socketRef.current.send(JSON.stringify({
        type: "unsubscribe",
        conversation_id: conversationId,
      }));
    },
    []
  );

  // Auto-connect when token is available
  useEffect(() => {
    if (token && !socketRef.current) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [token, connect, disconnect]);

  // Subscribe to new conversation when selected
  useEffect(() => {
    if (currentConversation && isConnected) {
      subscribeToConversation(currentConversation.id);
    }
  }, [currentConversation, isConnected, subscribeToConversation]);

  return {
    isConnected,
    isConnecting,
    connect,
    disconnect,
    sendMessage,
    subscribeToConversation,
    unsubscribeFromConversation,
  };
}
