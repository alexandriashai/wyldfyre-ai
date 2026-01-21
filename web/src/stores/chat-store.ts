import { create } from "zustand";
import { conversationsApi } from "@/lib/api";
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

  // Actions
  fetchConversations: (token: string) => Promise<void>;
  selectConversation: (token: string, id: string) => Promise<void>;
  createConversation: (token: string, title?: string) => Promise<Conversation>;
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

  fetchConversations: async (token: string) => {
    set({ isLoading: true, error: null });
    try {
      const conversations = await conversationsApi.list(token);
      set({ conversations: conversations.map(c => ({ ...c, status: "active" })) });
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
          title: conversation.title,
          status: "active",
          created_at: "",
          updated_at: "",
        },
        messages: conversation.messages,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load conversation";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  createConversation: async (token: string, title?: string) => {
    set({ isLoading: true, error: null });
    try {
      const conversation = await conversationsApi.create(token, title);
      const newConversation: Conversation = {
        id: conversation.id,
        title: conversation.title,
        status: "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      set((state) => ({
        conversations: [newConversation, ...state.conversations],
        currentConversation: newConversation,
        messages: [],
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

  deleteConversation: async (token: string, id: string) => {
    try {
      await conversationsApi.delete(token, id);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        currentConversation:
          state.currentConversation?.id === id ? null : state.currentConversation,
        messages: state.currentConversation?.id === id ? [] : state.messages,
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

  updateStreamingMessage: (content: string) => {
    set({ streamingMessage: content });
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
    set({ messages: [], currentConversation: null });
  },

  setAppFocused: (focused: boolean) => {
    set({ isAppFocused: focused });
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
