import { create } from "zustand";
import { agentsApi } from "@/lib/api";
import { notifications } from "@/lib/notifications";

interface AgentAction {
  id: string;
  agent: string;
  action: string;
  description: string;
  timestamp: string;
}

interface Agent {
  name: string;
  status: string;
  current_task?: string;
  current_action?: AgentAction;
  last_heartbeat?: string;
  metrics?: Record<string, number>;
  capabilities?: string[];
  permission_level?: number;
}

interface AgentLog {
  timestamp: string;
  level: string;
  message: string;
}

interface AgentState {
  agents: Agent[];
  selectedAgent: Agent | null;
  agentLogs: AgentLog[];
  isLoading: boolean;
  error: string | null;
  // Track previous statuses for change detection
  previousStatuses: Record<string, string>;
  // Track if app is in foreground for notifications
  isAppFocused: boolean;
  // Real-time action log (Claude Code style)
  actionLog: AgentAction[];
  maxActionLogSize: number;

  // Actions
  fetchAgents: (token: string) => Promise<void>;
  fetchAgent: (token: string, name: string) => Promise<void>;
  fetchAgentLogs: (token: string, name: string, limit?: number) => Promise<void>;
  restartAgent: (token: string, name: string) => Promise<void>;
  updateAgentStatus: (
    name: string,
    status: string,
    currentTask?: string,
    notifyOnChange?: boolean
  ) => void;
  addAgentAction: (
    agent: string,
    action: string,
    description: string,
    timestamp?: string
  ) => void;
  clearAgentActions: () => void;
  setSelectedAgent: (agent: Agent | null) => void;
  setError: (error: string | null) => void;
  setAppFocused: (focused: boolean) => void;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  selectedAgent: null,
  agentLogs: [],
  isLoading: false,
  error: null,
  previousStatuses: {},
  isAppFocused: true,
  actionLog: [],
  maxActionLogSize: 100,

  fetchAgents: async (token: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await agentsApi.list(token);

      // Ensure agents is always an array
      const agents = Array.isArray(response) ? response : [];

      // Initialize previous statuses
      const previousStatuses: Record<string, string> = {};
      agents.forEach((agent: Agent) => {
        previousStatuses[agent.name] = agent.status;
      });

      set({ agents, previousStatuses });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch agents";
      set({ error: message, agents: [] });
    } finally {
      set({ isLoading: false });
    }
  },

  fetchAgent: async (token: string, name: string) => {
    set({ isLoading: true, error: null });
    try {
      const agent = await agentsApi.get(token, name);
      set({ selectedAgent: agent });

      // Also update the agent in the agents list
      set((state) => ({
        agents: state.agents.map((a) =>
          a.name === name ? { ...a, ...agent } : a
        ),
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch agent details";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  fetchAgentLogs: async (token: string, name: string, limit: number = 100) => {
    set({ isLoading: true, error: null });
    try {
      const logs = await agentsApi.logs(token, name, limit);
      set({ agentLogs: logs });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch agent logs";
      set({ error: message });
    } finally {
      set({ isLoading: false });
    }
  },

  restartAgent: async (token: string, name: string) => {
    set({ isLoading: true, error: null });
    try {
      await agentsApi.restart(token, name);
      // Update status to restarting
      set((state) => ({
        agents: state.agents.map((a) =>
          a.name === name ? { ...a, status: "starting" } : a
        ),
        previousStatuses: {
          ...state.previousStatuses,
          [name]: "starting",
        },
      }));

      // Show notification
      const state = get();
      if (!state.isAppFocused) {
        notifications.agentStatus(name, "busy", `${name} is restarting...`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to restart agent";
      set({ error: message });

      // Notify on error
      notifications.error("Restart Failed", `Failed to restart ${name}: ${message}`);

      throw err;
    } finally {
      set({ isLoading: false });
    }
  },

  updateAgentStatus: (
    name: string,
    status: string,
    currentTask?: string,
    notifyOnChange = true
  ) => {
    const state = get();
    const previousStatus = state.previousStatuses[name];

    // Update the agent status
    set((state) => ({
      agents: state.agents.map((a) =>
        a.name === name
          ? {
              ...a,
              status,
              current_task: currentTask,
              last_heartbeat: new Date().toISOString(),
            }
          : a
      ),
      selectedAgent:
        state.selectedAgent?.name === name
          ? { ...state.selectedAgent, status, current_task: currentTask }
          : state.selectedAgent,
      previousStatuses: {
        ...state.previousStatuses,
        [name]: status,
      },
    }));

    // Check if status changed significantly and notify
    if (notifyOnChange && previousStatus && previousStatus !== status) {
      const shouldNotify =
        // Notify when agent goes offline
        (status === "offline" && previousStatus !== "offline") ||
        // Notify when agent encounters error
        (status === "error" && previousStatus !== "error") ||
        // Notify when agent comes back online from error/offline
        (status === "online" &&
          (previousStatus === "offline" || previousStatus === "error"));

      if (shouldNotify && !state.isAppFocused) {
        const displayName = name.charAt(0).toUpperCase() + name.slice(1);
        notifications.agentStatus(
          displayName,
          status as "online" | "offline" | "busy" | "error"
        );
      }
    }
  },

  addAgentAction: (
    agent: string,
    action: string,
    description: string,
    timestamp?: string
  ) => {
    const state = get();
    const newAction: AgentAction = {
      id: crypto.randomUUID(),
      agent,
      action,
      description,
      timestamp: timestamp || new Date().toISOString(),
    };

    // Add to action log, keeping within max size
    const updatedLog = [...state.actionLog, newAction];
    if (updatedLog.length > state.maxActionLogSize) {
      updatedLog.shift(); // Remove oldest
    }

    // Update agent's current action
    set((state) => ({
      actionLog: updatedLog,
      agents: state.agents.map((a) =>
        a.name === agent
          ? { ...a, current_action: newAction }
          : a
      ),
    }));
  },

  clearAgentActions: () => {
    set((state) => ({
      actionLog: [],
      agents: state.agents.map((a) => ({
        ...a,
        current_action: undefined,
      })),
    }));
  },

  setSelectedAgent: (agent: Agent | null) => {
    set({ selectedAgent: agent, agentLogs: [] });
  },

  setError: (error: string | null) => set({ error }),

  setAppFocused: (focused: boolean) => {
    set({ isAppFocused: focused });
  },
}));

// Track app focus state for notifications
if (typeof window !== "undefined") {
  window.addEventListener("focus", () => {
    useAgentStore.getState().setAppFocused(true);
  });

  window.addEventListener("blur", () => {
    useAgentStore.getState().setAppFocused(false);
  });

  document.addEventListener("visibilitychange", () => {
    useAgentStore.getState().setAppFocused(!document.hidden);
  });
}
