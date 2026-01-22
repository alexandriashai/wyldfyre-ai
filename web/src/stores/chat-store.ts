import { create } from "zustand";
import { conversationsApi, Conversation as ApiConversation } from "@/lib/api";
import { notifications } from "@/lib/notifications";

interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  agent?: string;
  created_at: string;
  isStreaming?: boolean;
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
}

type PlanStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED" | null;

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

  // Plan state (Claude CLI style)
  currentPlan: string | null;
  planStatus: PlanStatus;

  // Filters
  projectFilter: string | null;

  // Actions
  fetchConversations: (token: string, projectId?: string | null) => Promise<void>;
  selectConversation: (token: string, id: string) => Promise<void>;
  createConversation: (token: string, title?: string, projectId?: string, domainId?: string) => Promise<Conversation>;
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

  // Plan actions
  updatePlan: (content: string, status?: PlanStatus) => void;
  approvePlan: (token: string) => Promise<void>;
  rejectPlan: (token: string) => Promise<void>;
  clearPlan: () => void;

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
  currentPlan: null,
  planStatus: null,
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
        currentPlan: conversation.plan_content,
        planStatus: conversation.plan_status as PlanStatus,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load conversation";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  createConversation: async (token: string, title?: string, projectId?: string, domainId?: string) => {
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
    set((state) => ({
      messages: [...state.messages, message],
    }));
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

  // Plan actions
  updatePlan: (content: string, status?: PlanStatus) => {
    set({
      currentPlan: content,
      planStatus: status || "DRAFT",
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
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to reject plan";
      set({ error: message });
      throw err;
    }
  },

  clearPlan: () => {
    set({ currentPlan: null, planStatus: null });
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
