import { useCallback } from "react";
import { create } from "zustand";
import { agentsApi } from "@/lib/api";
import { notifications } from "@/lib/notifications";

export type ActionStatus = "running" | "success" | "error";

export interface AgentAction {
  id: string;
  agent: string;
  action: string;
  description: string;
  timestamp: string;
  type?: "tool_call" | "tool_result" | "thinking" | "info" | "error" | "parallel" | "subagent";
  duration?: number;
  output?: string;
  status?: ActionStatus;
  groupId?: string;
  // Subagent-specific fields
  isSubagent?: boolean;
  subagentType?: "explore" | "plan" | "subagent";
}

export interface ActionGroup {
  id: string;
  actions: AgentAction[];
  startTime: string;
  endTime?: string;
  duration?: number;
  isParallel?: boolean;
  iteration?: number;
  tokenUsage?: { input: number; output: number };
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
  actionGroups: ActionGroup[];
  currentIteration: number;
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
  actionGroups: [],
  currentIteration: 0,
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

    // Deduplicate: check if exact same action already in recent log
    const isDuplicate = state.actionLog.slice(-5).some(
      (a) => a.agent === agent && a.action === action && a.description === description
    );
    if (isDuplicate) {
      return;
    }

    // Detect subagent actions
    const isSubagent = action.startsWith("subagent_");
    let subagentType: AgentAction["subagentType"] = undefined;
    if (isSubagent) {
      // Extract subagent type from description (e.g., "explore: Starting...")
      const match = description.match(/^(explore|plan|subagent):/i);
      if (match) {
        subagentType = match[1].toLowerCase() as AgentAction["subagentType"];
      }
    }

    // Infer action type from the action string
    let type: AgentAction["type"] = "info";
    let status: ActionStatus = "success";
    if (isSubagent) {
      type = "subagent";
      if (action.includes("start") || action.includes("tool_call")) {
        status = "running";
      } else if (action.includes("error")) {
        status = "error";
      }
    } else if (action.includes("tool_call") || action.includes("calling") || action.includes("execute")) {
      type = "tool_call";
      status = "running";
    } else if (action.includes("tool_result") || action.includes("result")) {
      type = "tool_result";
    } else if (action.includes("think") || action.includes("reasoning")) {
      type = "thinking";
    } else if (action.includes("error") || action.includes("fail")) {
      type = "error";
      status = "error";
    } else if (action.includes("parallel")) {
      type = "parallel";
    }

    const now = timestamp || new Date().toISOString();
    const groupId = state.actionGroups.length > 0
      ? state.actionGroups[state.actionGroups.length - 1].id
      : crypto.randomUUID();

    const newAction: AgentAction = {
      id: crypto.randomUUID(),
      agent,
      action,
      description,
      timestamp: now,
      type,
      status,
      groupId,
      isSubagent,
      subagentType,
    };

    // Add to action log, keeping within max size
    const updatedLog = [...state.actionLog, newAction];
    if (updatedLog.length > state.maxActionLogSize) {
      updatedLog.shift();
    }

    // Update action groups
    let groups = [...state.actionGroups];
    let currentIteration = state.currentIteration;

    // If tool_result comes after tool_call, compute duration
    if (type === "tool_result" && state.actionLog.length > 0) {
      const lastToolCall = [...state.actionLog].reverse().find((a) => a.type === "tool_call" && a.status === "running");
      if (lastToolCall) {
        const duration = new Date(now).getTime() - new Date(lastToolCall.timestamp).getTime();
        newAction.duration = duration;
        // Update the tool_call status
        const callIdx = updatedLog.findIndex((a) => a.id === lastToolCall.id);
        if (callIdx >= 0) {
          updatedLog[callIdx] = { ...updatedLog[callIdx], status: "success", duration };
        }
      }
    }

    // Group logic: create new group when thinking starts, or when action type changes significantly
    const lastGroup = groups[groups.length - 1];
    if (!lastGroup || type === "thinking") {
      if (type === "thinking") {
        currentIteration++;
      }
      groups.push({
        id: crypto.randomUUID(),
        actions: [newAction],
        startTime: now,
        iteration: currentIteration,
      });
    } else {
      // Add to current group
      lastGroup.actions.push(newAction);
      lastGroup.endTime = now;
      lastGroup.duration = new Date(now).getTime() - new Date(lastGroup.startTime).getTime();
    }

    // Keep groups manageable
    if (groups.length > 50) {
      groups = groups.slice(-50);
    }

    set((state) => ({
      actionLog: updatedLog,
      actionGroups: groups,
      currentIteration,
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
      actionGroups: [],
      currentIteration: 0,
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
// Note: These listeners are intentionally global and never removed
// They persist for the lifetime of the app
if (typeof window !== "undefined") {
  const handleFocus = () => useAgentStore.getState().setAppFocused(true);
  const handleBlur = () => useAgentStore.getState().setAppFocused(false);
  const handleVisibility = () => useAgentStore.getState().setAppFocused(!document.hidden);

  window.addEventListener("focus", handleFocus);
  window.addEventListener("blur", handleBlur);
  document.addEventListener("visibilitychange", handleVisibility);
}

// === Selector hooks for performance ===
// These minimize re-renders by selecting only the data needed

/**
 * Get a specific agent by name. Only re-renders when that agent changes.
 */
export const useAgent = (name: string) =>
  useAgentStore(useCallback((state) => state.agents.find((a) => a.name === name), [name]));

/**
 * Get a specific agent's status. Only re-renders when status changes.
 */
export const useAgentStatus = (name: string) =>
  useAgentStore(
    useCallback(
      (state) => {
        const agent = state.agents.find((a) => a.name === name);
        return agent?.status;
      },
      [name]
    )
  );

/**
 * Get list of agent names only. Avoids re-renders from status/task changes.
 */
export const useAgentNames = () =>
  useAgentStore(
    useCallback((state) => state.agents.map((a) => a.name), [])
  );

/**
 * Get just the loading and error state.
 */
export const useAgentLoadingState = () =>
  useAgentStore(
    useCallback((state) => ({ isLoading: state.isLoading, error: state.error }), [])
  );

/**
 * Get the current action log.
 */
export const useActionLog = () =>
  useAgentStore(useCallback((state) => state.actionLog, []));

/**
 * Get action groups for timeline display.
 */
export const useActionGroups = () =>
  useAgentStore(useCallback((state) => state.actionGroups, []));

/**
 * Get current iteration number.
 */
export const useCurrentIteration = () =>
  useAgentStore(useCallback((state) => state.currentIteration, []));
