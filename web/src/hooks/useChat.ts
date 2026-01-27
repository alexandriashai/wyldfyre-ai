"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useChatStore, PlanChange } from "@/stores/chat-store";
import { useAgentStore } from "@/stores/agent-store";
import { useAuthStore } from "@/stores/auth-store";
import { useUsageStore } from "@/stores/usage-store";

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
  type: "message" | "token" | "connected" | "pong" | "error" | "agent_status" | "agent_action" | "subscribed" | "unsubscribed" | "message_ack" | "command_result" | "command_error" | "memory_saved" | "plan_update" | "plan_status" | "task_control_ack" | "message_queued" | "step_update" | "conversation_renamed" | "deploy_progress" | "usage_update" | "supervisor_thinking" | "step_confidence_update" | "plan_change" | "todo_progress" | "file_change_preview" | "available_agents" | "continuation_required" | "thinking_stream";
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
  // Usage update fields
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  // Supervisor thinking fields
  phase?: "evaluating" | "deciding" | "replanning" | "course_correcting";
  step_id?: string;
  confidence?: number;
  // Thinking stream fields (narrative reasoning)
  thought_type?: "reasoning" | "decision" | "analysis" | "observation";
  context?: Record<string, any>;
  // Confidence update fields
  old_confidence?: number;
  new_confidence?: number;
  reason?: string;
  // Plan change fields
  change_type?: "step_added" | "step_removed" | "step_modified" | "step_reordered";
  before?: object;
  after?: object;
  // Todo progress fields
  todo_index?: number;
  status_message?: string;
  // File change preview fields
  path?: string;
  before_content?: string;
  after_content?: string;
  language?: string;
  summary?: string;
  // Available agents
  agents?: string[];
  // Continuation request fields
  step_title?: string;
  iterations_used?: number;
  progress_estimate?: number;
  estimated_remaining?: number;
  files_modified?: string[];
  message?: string;
}

export type ConnectionState = "connected" | "connecting" | "disconnected" | "reconnecting";

type PlanStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED" | null;

/** Normalize plan_status from backend (may be lowercase) to uppercase for frontend */
function normalizePlanStatus(status?: string | null): PlanStatus {
  if (!status) return null;
  const upper = status.toUpperCase();
  if (["DRAFT", "PENDING", "APPROVED", "REJECTED", "COMPLETED"].includes(upper)) {
    return upper as PlanStatus;
  }
  // Map backend execution states to frontend equivalents
  if (upper === "EXECUTING" || upper === "PAUSED") return "APPROVED";
  if (upper === "EXPLORING" || upper === "DRAFTING") return "DRAFT";
  return "DRAFT";
}

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
                normalizePlanStatus(data.plan_status)
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
            const planStatus = normalizePlanStatus(data.plan_status);
            updatePlan(data.plan_content, planStatus);
            setIsSending(false);
          }
          break;

        case "plan_status":
          if (data.plan_status) {
            const normalized = normalizePlanStatus(data.plan_status);
            if (normalized === "COMPLETED") {
              useChatStore.getState().clearPlan();
            } else {
              const currentPlan = useChatStore.getState().currentPlan;
              if (currentPlan) {
                updatePlan(currentPlan, normalized);
              }
            }
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

        case "usage_update":
          if (data.input_tokens !== undefined || data.output_tokens !== undefined) {
            useUsageStore.getState().updateUsage(
              data.input_tokens || 0,
              data.output_tokens || 0,
              data.cost || 0
            );
          }
          break;

        case "supervisor_thinking":
          if (data.content && data.phase) {
            useChatStore.getState().addSupervisorThought({
              content: data.content,
              phase: data.phase,
              timestamp: data.timestamp || new Date().toISOString(),
              stepId: data.step_id,
              confidence: data.confidence,
            });
          }
          break;

        case "step_confidence_update":
          if (data.step_id && data.old_confidence !== undefined && data.new_confidence !== undefined) {
            useChatStore.getState().addConfidenceUpdate({
              stepId: data.step_id,
              oldConfidence: data.old_confidence,
              newConfidence: data.new_confidence,
              reason: data.reason || "",
              timestamp: data.timestamp || new Date().toISOString(),
            });
          }
          break;

        case "plan_change":
          if (data.change_type && data.step_id) {
            useChatStore.getState().addPlanChange({
              changeType: data.change_type,
              stepId: data.step_id,
              stepTitle: data.title,
              reason: data.reason || "",
              timestamp: data.timestamp || new Date().toISOString(),
              before: data.before as PlanChange["before"],
              after: data.after as PlanChange["after"],
            });
          }
          break;

        case "todo_progress":
          if (data.step_id && data.todo_index !== undefined) {
            useChatStore.getState().updateTodoProgress({
              stepId: data.step_id,
              todoIndex: data.todo_index,
              progress: data.progress || 0,
              statusMessage: data.status_message || "",
              timestamp: data.timestamp || new Date().toISOString(),
            });
          }
          break;

        case "file_change_preview":
          if (data.path && data.after_content !== undefined) {
            useChatStore.getState().addFileChangePreview({
              id: data.message_id || crypto.randomUUID(),
              path: data.path,
              before: data.before_content || "",
              after: data.after_content,
              language: data.language,
              summary: data.summary,
              stepId: data.step_id,
            });
          }
          break;

        case "available_agents":
          if (data.agents) {
            useChatStore.getState().setAvailableAgents(data.agents);
          }
          break;

        case "continuation_required":
          // Agent hit max iterations and needs user decision to continue
          if (data.step_id) {
            useChatStore.getState().setContinuationRequest({
              stepId: data.step_id,
              stepTitle: data.step_title || "Current step",
              iterationsUsed: data.iterations_used || 0,
              progressEstimate: data.progress_estimate || 0,
              estimatedRemaining: data.estimated_remaining || 10,
              filesModified: data.files_modified || [],
              message: data.message || "Step reached maximum iterations.",
              timestamp: data.timestamp || new Date().toISOString(),
              planId: data.plan_id,
              conversationId: data.conversation_id,
            });
            setIsSending(false);
          }
          break;

        case "thinking_stream":
          // Narrative thinking/reasoning for Thinking panel
          if (data.content && data.thought_type) {
            useChatStore.getState().addThinkingEntry({
              type: data.thought_type,
              content: data.content,
              context: data.context,
              agent: data.agent || "supervisor",
              timestamp: data.timestamp || new Date().toISOString(),
            });
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
    (content: string, targetAgent?: string) => {
      if (!currentConversation) {
        console.error("No conversation selected");
        return;
      }

      const messageId = crypto.randomUUID();
      const activeAgent = targetAgent || useChatStore.getState().activeAgent;

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

      // Send to server with optional target agent
      try {
        socketRef.current.send(JSON.stringify({
          type: "chat",
          conversation_id: currentConversation.id,
          project_id: currentConversation.project_id || undefined,
          content,
          message_id: messageId,
          target_agent: activeAgent || undefined,
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
