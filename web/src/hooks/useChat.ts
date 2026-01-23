"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useAgentStore } from "@/stores/agent-store";
import { useAuthStore } from "@/stores/auth-store";

// Use wss:// for secure connection, endpoint is /ws/chat
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "wss://api.wyldfyre.ai";

interface PlanStep {
  id: string;
  order: number;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "skipped";
  agent?: string;
  files?: string[];
  todos?: string[];
  changes?: Array<{ file: string; action: string; summary: string }>;
  output?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

interface ChatMessage {
  type: "message" | "token" | "connected" | "pong" | "error" | "agent_status" | "agent_action" | "subscribed" | "unsubscribed" | "message_ack" | "command_result" | "command_error" | "memory_saved" | "plan_update" | "task_control_ack" | "message_queued" | "step_update" | "conversation_renamed" | "deploy_progress";
  title?: string;
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
  command?: string;
  tags?: string[];
  memory_tags?: string[];
  plan_content?: string;
  plan_status?: string;
  // Step update fields
  plan_id?: string;
  steps?: PlanStep[];
  current_step?: number;
  modification?: string;
  // Deploy progress fields
  domain?: string;
  stage?: string;
  progress?: number;
  log?: string;
}

export type ConnectionState = "connected" | "connecting" | "disconnected" | "reconnecting";

export function useChat() {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;

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
    updatePlan,
    updateSteps,
    setMessageStatus,
    markMessageFailed,
    setConnectionState,
    flushPendingMessages,
    queueMessage,
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
          if (data.agent && data.action && data.description) {
            addAgentAction(data.agent, data.action, data.description, data.timestamp);
          }
          break;

        case "message_ack":
          // Message acknowledgment - mark as sent and clear previous actions
          if (data.message_id) {
            setMessageStatus(data.message_id, "sent");
          }
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
          // If there's a message_id, mark it as failed
          if (data.message_id) {
            markMessageFailed(data.message_id);
          }
          clearStreamingMessage();
          setIsSending(false);
          break;

        case "command_result":
          if (data.content && data.action !== "plan_creating") {
            addMessage({
              id: crypto.randomUUID(),
              role: "assistant",
              content: data.content,
              agent: "system",
              created_at: data.timestamp || new Date().toISOString(),
            });
            setIsSending(false);
          }
          if (data.plan_content !== undefined) {
            if (data.plan_content === "" || data.plan_content === null) {
              useChatStore.getState().clearPlan();
            } else {
              updatePlan(
                data.plan_content,
                data.plan_status as "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED" | null
              );
            }
          }
          break;

        case "command_error":
          if (data.error) {
            addMessage({
              id: crypto.randomUUID(),
              role: "assistant",
              content: `Command error: ${data.error}`,
              agent: "system",
              created_at: data.timestamp || new Date().toISOString(),
            });
          }
          break;

        case "memory_saved":
          console.log("Memory saved with tags:", data.tags);
          break;

        case "plan_update":
          if (data.plan_content !== undefined) {
            updatePlan(
              data.plan_content,
              data.plan_status as "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED" | null
            );
            setIsSending(false);
          }
          break;

        case "step_update":
          if (data.steps) {
            updateSteps(data.steps, data.current_step || 0);
            if (data.modification) {
              console.log(`[Plan] Modified: ${data.modification}`);
            }
          }
          break;

        case "task_control_ack":
          console.log(`Task ${data.action} acknowledged`);
          break;

        case "message_queued":
          console.log("Message queued:", data.content);
          break;

        case "conversation_renamed":
          if (data.conversation_id && data.title) {
            useChatStore.getState().renameConversationLocal(data.conversation_id, data.title);
          }
          break;

        case "deploy_progress":
          // Emit a custom event for deploy progress tracking
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("deploy_progress", { detail: data }));
          }
          break;

        default:
          console.log("Unknown message type:", data.type);
      }
    } catch (e) {
      console.error("Failed to parse WebSocket message:", e);
    }
  }, [addMessage, updateStreamingMessage, clearStreamingMessage, setIsSending, updateAgentStatus, addAgentAction, clearAgentActions, updatePlan, updateSteps, setMessageStatus, markMessageFailed]);

  const connect = useCallback(() => {
    const wsUrl = getWsUrl();
    if (!wsUrl || socketRef.current?.readyState === WebSocket.OPEN) return;

    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    setIsConnecting(true);
    setConnectionState(reconnectAttemptsRef.current > 0 ? "reconnecting" : "connecting");

    try {
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        setConnectionState("connected");
        reconnectAttemptsRef.current = 0;
        startPingInterval();

        // Flush pending messages on reconnect
        const pending = flushPendingMessages();
        if (pending.length > 0) {
          pending.forEach((msg) => {
            socket.send(JSON.stringify({
              type: "chat",
              conversation_id: msg.conversationId,
              project_id: msg.projectId || undefined,
              content: msg.content,
              message_id: msg.id,
            }));
            setMessageStatus(msg.id, "sending");
          });
        }
      };

      socket.onclose = (event) => {
        setIsConnected(false);
        setIsConnecting(false);
        stopPingInterval();

        // Don't reconnect if closed normally (code 1000) or auth failed (4001)
        if (event.code !== 1000 && event.code !== 4001) {
          setConnectionState("reconnecting");
          // Attempt to reconnect with exponential backoff
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            reconnectAttemptsRef.current++;
            reconnectTimeoutRef.current = setTimeout(connect, delay);
          } else {
            setConnectionState("disconnected");
          }
        } else {
          setConnectionState("disconnected");
        }
      };

      socket.onerror = () => {
        setIsConnecting(false);
      };

      socket.onmessage = handleMessage;

      socketRef.current = socket;
    } catch (e) {
      console.error("Failed to create WebSocket:", e);
      setIsConnecting(false);
      setConnectionState("disconnected");
    }
  }, [getWsUrl, handleMessage, startPingInterval, stopPingInterval, setConnectionState, flushPendingMessages, setMessageStatus]);

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
      setConnectionState("disconnected");
    }
  }, [stopPingInterval, setConnectionState]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!currentConversation) {
        console.error("No conversation selected");
        return;
      }

      const messageId = crypto.randomUUID();

      // Add user message immediately (optimistic)
      const userMessage = {
        id: messageId,
        role: "user" as const,
        content,
        created_at: new Date().toISOString(),
        status: "sending" as const,
      };
      addMessage(userMessage);
      setMessageStatus(messageId, "sending");
      setIsSending(true);

      // If disconnected, queue the message
      if (socketRef.current?.readyState !== WebSocket.OPEN) {
        queueMessage({
          id: messageId,
          content,
          conversationId: currentConversation.id,
          projectId: currentConversation.project_id || undefined,
        });
        return;
      }

      // Send to server
      try {
        socketRef.current.send(JSON.stringify({
          type: "chat",
          conversation_id: currentConversation.id,
          project_id: currentConversation.project_id || undefined,
          content,
          message_id: messageId,
        }));
      } catch {
        markMessageFailed(messageId);
      }
    },
    [currentConversation, addMessage, setIsSending, setMessageStatus, queueMessage, markMessageFailed]
  );

  const retryMessage = useCallback(
    (messageId: string) => {
      const state = useChatStore.getState();
      const message = state.messages.find((m) => m.id === messageId);
      if (!message || !currentConversation) return;

      // Reset status to sending
      setMessageStatus(messageId, "sending");
      setIsSending(true);

      if (socketRef.current?.readyState !== WebSocket.OPEN) {
        queueMessage({
          id: messageId,
          content: message.content,
          conversationId: currentConversation.id,
          projectId: currentConversation.project_id || undefined,
        });
        return;
      }

      try {
        socketRef.current.send(JSON.stringify({
          type: "chat",
          conversation_id: currentConversation.id,
          project_id: currentConversation.project_id || undefined,
          content: message.content,
          message_id: messageId,
        }));
      } catch {
        markMessageFailed(messageId);
      }
    },
    [currentConversation, setMessageStatus, setIsSending, queueMessage, markMessageFailed]
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

  // Task control methods (Claude CLI style)
  const pauseTask = useCallback(() => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || !currentConversation) {
      return;
    }
    socketRef.current.send(JSON.stringify({
      type: "task_control",
      action: "pause",
      conversation_id: currentConversation.id,
    }));
  }, [currentConversation]);

  const resumeTask = useCallback(() => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || !currentConversation) {
      return;
    }
    socketRef.current.send(JSON.stringify({
      type: "task_control",
      action: "resume",
      conversation_id: currentConversation.id,
    }));
  }, [currentConversation]);

  const cancelTask = useCallback(() => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || !currentConversation) {
      return;
    }
    socketRef.current.send(JSON.stringify({
      type: "task_control",
      action: "cancel",
      conversation_id: currentConversation.id,
    }));
  }, [currentConversation]);

  const addMessageWhileBusy = useCallback((content: string) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN || !currentConversation) {
      return;
    }
    socketRef.current.send(JSON.stringify({
      type: "add_message",
      content,
      conversation_id: currentConversation.id,
    }));
  }, [currentConversation]);

  return {
    isConnected,
    isConnecting,
    connectionState: useChatStore.getState().connectionState,
    connect,
    disconnect,
    sendMessage,
    retryMessage,
    subscribeToConversation,
    unsubscribeFromConversation,
    // Task control
    pauseTask,
    resumeTask,
    cancelTask,
    addMessageWhileBusy,
  };
}
