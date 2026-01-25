import { create } from "zustand";
import { conversationsApi, Conversation as ApiConversation } from "@/lib/api";
import { notifications } from "@/lib/notifications";

export type MessageStatus = "sending" | "sent" | "failed";

interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  agent?: string;
  created_at: string;
  isStreaming?: boolean;
  status?: MessageStatus;
}

interface Conversation {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  domain_id?: string | null;
  plan_content?: string | null;
  plan_status?: string | null;
  plan_approved_at?: string | null;
  message_count?: number;
  tags?: string[];
}

type PlanStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED" | null;

export interface PlanStep {
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

interface ChatState {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  streamingMessage: string;
  // Track if app is in foreground for notifications
  isAppFocused: boolean;

  // Message status tracking
  messageStatuses: Record<string, MessageStatus>;
  pendingMessages: Array<{ id: string; content: string; conversationId: string; projectId?: string }>;

  // Connection state
  connectionState: "connected" | "connecting" | "disconnected" | "reconnecting";

  // Plan state (Claude CLI style)
  currentPlan: string | null;
  planStatus: PlanStatus;
  planSteps: PlanStep[];
  currentStepIndex: number;

  // Conversation organization
  pinnedConversations: Set<string>;
  searchQuery: string;

  // Filters
  tagFilter: string[];
  projectFilter: string | null;

  // Actions
  fetchConversations: (token: string, projectId?: string | null) => Promise<void>;
  selectConversation: (token: string, id: string) => Promise<void>;
  createConversation: (token: string, projectId: string, title?: string, domainId?: string) => Promise<Conversation>;
  updateConversation: (token: string, id: string, data: { title?: string; project_id?: string }) => Promise<void>;
  deleteConversation: (token: string, id: string) => Promise<void>;
  addMessage: (message: Message) => void;
  receiveMessage: (message: Message, showNotification?: boolean) => void;
  updateStreamingMessage: (content: string) => void;
  finalizeStreamingMessage: (message: Message) => void;
  clearStreamingMessage: () => void;
  setIsSending: (isSending: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
  setAppFocused: (focused: boolean) => void;

  // Message status actions
  setMessageStatus: (messageId: string, status: MessageStatus) => void;
  markMessageFailed: (messageId: string) => void;
  queueMessage: (message: { id: string; content: string; conversationId: string; projectId?: string }) => void;
  flushPendingMessages: () => Array<{ id: string; content: string; conversationId: string; projectId?: string }>;
  removeFromQueue: (messageId: string) => void;

  // Connection state
  setConnectionState: (state: "connected" | "connecting" | "disconnected" | "reconnecting") => void;

  // Plan actions
  updatePlan: (content: string, status?: PlanStatus) => void;
  updateSteps: (steps: PlanStep[], currentStep: number) => void;
  approvePlan: (token: string) => Promise<void>;
  rejectPlan: (token: string) => Promise<void>;
  clearPlan: () => void;

  // Local state updates (from WebSocket pushes)
  renameConversationLocal: (conversationId: string, title: string) => void;

  // Conversation organization
  togglePinConversation: (conversationId: string) => void;
  setSearchQuery: (query: string) => void;

  // Tag actions
  toggleTagFilter: (tag: string) => void;
  setTagFilter: (tags: string[]) => void;
  updateConversationTags: (token: string, id: string, tags: string[]) => Promise<void>;

  // Filter actions
  setProjectFilter: (projectId: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  isLoading: false,
  isSending: false,
  error: null,
  streamingMessage: "",
  isAppFocused: true,
  messageStatuses: {},
  pendingMessages: [],
  connectionState: "disconnected",
  currentPlan: null,
  planStatus: null,
  planSteps: [],
  currentStepIndex: 0,
  pinnedConversations: new Set<string>(),
  searchQuery: "",
  tagFilter: [],
  projectFilter: null,

  fetchConversations: async (token: string, projectId?: string | null) => {
    set({ isLoading: true, error: null });
    try {
      const response = await conversationsApi.list(token, {
        project_id: projectId || undefined,
      });
      set({
        conversations: response.conversations.map(c => ({
          id: c.id,
          title: c.title || "New Conversation",
          status: c.status,
          created_at: c.created_at,
          updated_at: c.updated_at,
          project_id: c.project_id,
          domain_id: c.domain_id,
          plan_content: c.plan_content,
          plan_status: c.plan_status,
          plan_approved_at: c.plan_approved_at,
          tags: c.tags || [],
        })),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch conversations";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  selectConversation: async (token: string, id: string) => {
    set({ isLoading: true, error: null });
    try {
      const conversation = await conversationsApi.get(token, id);
      set({
        currentConversation: {
          id: conversation.id,
          title: conversation.title || "New Conversation",
          status: conversation.status,
          created_at: conversation.created_at,
          updated_at: conversation.updated_at,
          project_id: conversation.project_id,
          domain_id: conversation.domain_id,
          plan_content: conversation.plan_content,
          plan_status: conversation.plan_status,
          plan_approved_at: conversation.plan_approved_at,
        },
        messages: conversation.messages,
        // Don't restore plan panel for terminal states (completed/rejected)
        currentPlan: conversation.plan_status &&
          ["completed", "rejected"].includes(conversation.plan_status.toLowerCase())
          ? null
          : conversation.plan_content,
        planStatus: conversation.plan_status &&
          ["completed", "rejected"].includes(conversation.plan_status.toLowerCase())
          ? null
          : conversation.plan_status
            ? (conversation.plan_status.toUpperCase() as PlanStatus)
            : null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load conversation";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  createConversation: async (token: string, projectId: string, title?: string, domainId?: string) => {
    set({ isLoading: true, error: null });
    try {
      const conversation = await conversationsApi.create(token, {
        title,
        project_id: projectId,
        domain_id: domainId,
      });
      const newConversation: Conversation = {
        id: conversation.id,
        title: conversation.title || "New Conversation",
        status: conversation.status,
        created_at: conversation.created_at,
        updated_at: conversation.updated_at,
        project_id: conversation.project_id,
        domain_id: conversation.domain_id,
        plan_content: conversation.plan_content,
        plan_status: conversation.plan_status,
        plan_approved_at: conversation.plan_approved_at,
      };
      set((state) => ({
        conversations: [newConversation, ...state.conversations],
        currentConversation: newConversation,
        messages: [],
        currentPlan: null,
        planStatus: null,
      }));
      return newConversation;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create conversation";
      set({ error: message });
      throw err;
    } finally {
      set({ isLoading: false });
    }
  },

  updateConversation: async (token: string, id: string, data: { title?: string; project_id?: string }) => {
    try {
      const updated = await conversationsApi.update(token, id, data);
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id
            ? {
                ...c,
                title: updated.title || c.title,
                project_id: updated.project_id,
              }
            : c
        ),
        currentConversation:
          state.currentConversation?.id === id
            ? {
                ...state.currentConversation,
                title: updated.title || state.currentConversation.title,
                project_id: updated.project_id,
              }
            : state.currentConversation,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update conversation";
      set({ error: message });
      throw err;
    }
  },

  deleteConversation: async (token: string, id: string) => {
    try {
      await conversationsApi.delete(token, id);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        currentConversation:
          state.currentConversation?.id === id ? null : state.currentConversation,
        messages: state.currentConversation?.id === id ? [] : state.messages,
        currentPlan: state.currentConversation?.id === id ? null : state.currentPlan,
        planStatus: state.currentConversation?.id === id ? null : state.planStatus,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete conversation";
      set({ error: message });
    }
  },

  addMessage: (message: Message) => {
    set((state) => {
      // Deduplicate by checking if message with same content exists in last 10 messages
      const recentMessages = state.messages.slice(-10);
      const isDuplicate = recentMessages.some(
        (m) => m.content === message.content && m.role === message.role
      );
      if (isDuplicate) {
        console.log("[ChatStore] Skipping duplicate message:", message.content.slice(0, 50));
        return state;
      }
      return {
        messages: [...state.messages, message],
      };
    });
  },

  // New method that also handles notifications
  receiveMessage: (message: Message, showNotification = true) => {
    const state = get();

    // Add message to store
    set((state) => ({
      messages: [...state.messages, message],
    }));

    // Show notification if app is not focused and message is from assistant
    if (
      showNotification &&
      !state.isAppFocused &&
      message.role === "assistant" &&
      state.currentConversation
    ) {
      const agentName = message.agent || "Wyld";
      const preview = message.content.slice(0, 150);

      notifications.newMessage(
        agentName,
        preview,
        state.currentConversation.id
      );
    }
  },

  updateStreamingMessage: (token: string) => {
    set((state) => ({ streamingMessage: state.streamingMessage + token }));
  },

  finalizeStreamingMessage: (message: Message) => {
    const state = get();

    set((state) => ({
      messages: [...state.messages, message],
      streamingMessage: "",
    }));

    // Show notification if app is not focused
    if (!state.isAppFocused && state.currentConversation) {
      const agentName = message.agent || "Wyld";
      const preview = message.content.slice(0, 150);

      notifications.newMessage(
        agentName,
        preview,
        state.currentConversation.id
      );
    }
  },

  clearStreamingMessage: () => {
    set({ streamingMessage: "" });
  },

  setIsSending: (isSending: boolean) => {
    set({ isSending });
  },

  setError: (error: string | null) => set({ error }),

  clearMessages: () => {
    set({ messages: [], currentConversation: null, currentPlan: null, planStatus: null });
  },

  setAppFocused: (focused: boolean) => {
    set({ isAppFocused: focused });
  },

  // Message status actions
  setMessageStatus: (messageId: string, status: MessageStatus) => {
    set((state) => ({
      messageStatuses: { ...state.messageStatuses, [messageId]: status },
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, status } : m
      ),
    }));
  },

  markMessageFailed: (messageId: string) => {
    set((state) => ({
      messageStatuses: { ...state.messageStatuses, [messageId]: "failed" },
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, status: "failed" as MessageStatus } : m
      ),
      isSending: false,
    }));
  },

  queueMessage: (message) => {
    set((state) => ({
      pendingMessages: [...state.pendingMessages, message],
    }));
  },

  flushPendingMessages: () => {
    const pending = get().pendingMessages;
    set({ pendingMessages: [] });
    return pending;
  },

  removeFromQueue: (messageId: string) => {
    set((state) => ({
      pendingMessages: state.pendingMessages.filter((m) => m.id !== messageId),
    }));
  },

  // Connection state
  setConnectionState: (connectionState) => {
    set({ connectionState });
  },

  // Plan actions
  updatePlan: (content: string, status?: PlanStatus) => {
    set({
      currentPlan: content,
      planStatus: status || "DRAFT",
      planSteps: [],
      currentStepIndex: 0,
    });
  },

  updateSteps: (steps: PlanStep[], currentStep: number) => {
    // Determine plan status from step states
    let derivedStatus: PlanStatus = get().planStatus;
    if (steps.length > 0) {
      if (steps.some((s) => s.status === "in_progress")) {
        derivedStatus = "APPROVED"; // "APPROVED" displays as "Executing..." in UI
      } else if (steps.every((s) => ["completed", "skipped", "failed"].includes(s.status))) {
        derivedStatus = "COMPLETED";
      }
    }
    set({
      planSteps: steps,
      currentStepIndex: currentStep,
      planStatus: derivedStatus,
    });
  },

  approvePlan: async (token: string) => {
    const state = get();
    if (!state.currentConversation) return;

    try {
      await conversationsApi.approvePlan(token, state.currentConversation.id);
      set({ planStatus: "APPROVED" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to approve plan";
      set({ error: message });
      throw err;
    }
  },

  rejectPlan: async (token: string) => {
    const state = get();
    if (!state.currentConversation) return;

    try {
      await conversationsApi.rejectPlan(token, state.currentConversation.id);
      set({ planStatus: "REJECTED" });
      // Auto-dismiss after rejection
      setTimeout(() => {
        get().clearPlan();
      }, 2000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to reject plan";
      set({ error: message });
      throw err;
    }
  },

  clearPlan: () => {
    set({ currentPlan: null, planStatus: null, planSteps: [], currentStepIndex: 0 });
  },

  // Local state updates (from WebSocket pushes)
  renameConversationLocal: (conversationId: string, title: string) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId ? { ...c, title } : c
      ),
      currentConversation:
        state.currentConversation?.id === conversationId
          ? { ...state.currentConversation, title }
          : state.currentConversation,
    }));
  },

  // Conversation organization
  togglePinConversation: (conversationId: string) => {
    set((state) => {
      const newPinned = new Set(state.pinnedConversations);
      if (newPinned.has(conversationId)) {
        newPinned.delete(conversationId);
      } else {
        newPinned.add(conversationId);
      }
      return { pinnedConversations: newPinned };
    });
  },

  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  // Tag actions
  toggleTagFilter: (tag: string) => {
    set((state) => {
      const newFilter = state.tagFilter.includes(tag)
        ? state.tagFilter.filter((t) => t !== tag)
        : [...state.tagFilter, tag];
      return { tagFilter: newFilter };
    });
  },

  setTagFilter: (tags: string[]) => {
    set({ tagFilter: tags });
  },

  updateConversationTags: async (token: string, id: string, tags: string[]) => {
    try {
      const updated = await conversationsApi.updateTags(token, id, tags);
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id ? { ...c, tags: updated.tags || tags } : c
        ),
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update tags";
      set({ error: message });
    }
  },

  // Filter actions
  setProjectFilter: (projectId: string | null) => {
    set({ projectFilter: projectId });
  },
}));

// Track app focus state for notifications
if (typeof window !== "undefined") {
  window.addEventListener("focus", () => {
    useChatStore.getState().setAppFocused(true);
  });

  window.addEventListener("blur", () => {
    useChatStore.getState().setAppFocused(false);
  });

  // Also track visibility changes (e.g., switching tabs)
  document.addEventListener("visibilitychange", () => {
    useChatStore.getState().setAppFocused(!document.hidden);
  });
}
