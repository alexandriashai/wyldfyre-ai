import { create } from "zustand";
import { agentsApi } from "@/lib/api";

interface Agent {
  name: string;
  status: string;
  current_task?: string;
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

  // Actions
  fetchAgents: (token: string) => Promise<void>;
  fetchAgent: (token: string, name: string) => Promise<void>;
  fetchAgentLogs: (token: string, name: string, limit?: number) => Promise<void>;
  restartAgent: (token: string, name: string) => Promise<void>;
  updateAgentStatus: (name: string, status: string, currentTask?: string) => void;
  setSelectedAgent: (agent: Agent | null) => void;
  setError: (error: string | null) => void;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  selectedAgent: null,
  agentLogs: [],
  isLoading: false,
  error: null,

  fetchAgents: async (token: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await agentsApi.list(token);
      set({ agents: response.agents });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch agents";
      set({ error: message });
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
      const response = await agentsApi.logs(token, name, limit);
      set({ agentLogs: response.logs });
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
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to restart agent";
      set({ error: message });
      throw err;
    } finally {
      set({ isLoading: false });
    }
  },

  updateAgentStatus: (name: string, status: string, currentTask?: string) => {
    set((state) => ({
      agents: state.agents.map((a) =>
        a.name === name
          ? { ...a, status, current_task: currentTask, last_heartbeat: new Date().toISOString() }
          : a
      ),
      selectedAgent:
        state.selectedAgent?.name === name
          ? { ...state.selectedAgent, status, current_task: currentTask }
          : state.selectedAgent,
    }));
  },

  setSelectedAgent: (agent: Agent | null) => {
    set({ selectedAgent: agent, agentLogs: [] });
  },

  setError: (error: string | null) => set({ error }),
}));
