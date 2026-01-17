"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { io, Socket } from "socket.io-client";
import { useChatStore } from "@/stores/chat-store";
import { useAgentStore } from "@/stores/agent-store";
import { useAuthStore } from "@/stores/auth-store";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface ChatMessage {
  type: "message" | "agent_status" | "task_update" | "error";
  payload: {
    id?: string;
    content?: string;
    role?: string;
    agent?: string;
    status?: string;
    task_id?: string;
    progress?: number;
    error?: string;
  };
}

export function useChat() {
  const socketRef = useRef<Socket | null>(null);
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
  const { updateAgentStatus } = useAgentStore();

  const connect = useCallback(() => {
    if (!token || socketRef.current?.connected) return;

    setIsConnecting(true);

    const socket = io(WS_URL, {
      auth: { token },
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socket.on("connect", () => {
      setIsConnected(true);
      setIsConnecting(false);

      // Subscribe to current conversation if there is one
      if (currentConversation) {
        socket.emit("subscribe", {
          channel: "conversation",
          conversation_id: currentConversation.id,
        });
      }
    });

    socket.on("disconnect", () => {
      setIsConnected(false);
    });

    socket.on("connect_error", (error) => {
      console.error("Connection error:", error);
      setIsConnecting(false);
    });

    socket.on("message", (data: ChatMessage) => {
      handleMessage(data);
    });

    socket.on("stream", (data: { content: string; done: boolean; message?: ChatMessage["payload"] }) => {
      if (data.done && data.message) {
        finalizeStreamingMessage({
          id: data.message.id || crypto.randomUUID(),
          role: (data.message.role as "user" | "assistant" | "system" | "tool") || "assistant",
          content: data.message.content || "",
          agent: data.message.agent,
          created_at: new Date().toISOString(),
        });
        setIsSending(false);
      } else {
        updateStreamingMessage(data.content);
      }
    });

    socket.on("agent_status", (data: { agent: string; status: string; task?: string }) => {
      updateAgentStatus(data.agent, data.status, data.task);
    });

    socket.on("error", (data: { message: string }) => {
      console.error("Socket error:", data.message);
      clearStreamingMessage();
      setIsSending(false);
    });

    socketRef.current = socket;
  }, [token, currentConversation, addMessage, updateStreamingMessage, finalizeStreamingMessage, clearStreamingMessage, setIsSending, updateAgentStatus]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const handleMessage = useCallback((data: ChatMessage) => {
    switch (data.type) {
      case "message":
        if (data.payload.content) {
          addMessage({
            id: data.payload.id || crypto.randomUUID(),
            role: (data.payload.role as "user" | "assistant" | "system" | "tool") || "assistant",
            content: data.payload.content,
            agent: data.payload.agent,
            created_at: new Date().toISOString(),
          });
        }
        break;
      case "agent_status":
        if (data.payload.agent && data.payload.status) {
          updateAgentStatus(data.payload.agent, data.payload.status);
        }
        break;
      case "error":
        console.error("Server error:", data.payload.error);
        break;
    }
  }, [addMessage, updateAgentStatus]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!socketRef.current?.connected || !currentConversation) {
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
      socketRef.current.emit("send_message", {
        conversation_id: currentConversation.id,
        content,
      });
    },
    [currentConversation, addMessage, setIsSending]
  );

  const subscribeToConversation = useCallback(
    (conversationId: string) => {
      if (!socketRef.current?.connected) return;

      socketRef.current.emit("subscribe", {
        channel: "conversation",
        conversation_id: conversationId,
      });
    },
    []
  );

  const unsubscribeFromConversation = useCallback(
    (conversationId: string) => {
      if (!socketRef.current?.connected) return;

      socketRef.current.emit("unsubscribe", {
        channel: "conversation",
        conversation_id: conversationId,
      });
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
