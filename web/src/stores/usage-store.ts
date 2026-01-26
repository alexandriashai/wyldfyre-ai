import { create } from "zustand";
import { useCallback } from "react";

export interface UsageSnapshot {
  input_tokens: number;
  output_tokens: number;
  cost: number;
  timestamp: string;
}

interface UsageState {
  // Current request usage
  currentInputTokens: number;
  currentOutputTokens: number;
  currentCost: number;

  // Session totals
  sessionInputTokens: number;
  sessionOutputTokens: number;
  sessionCost: number;
  requestCount: number;

  // History for trends
  usageHistory: UsageSnapshot[];
  maxHistorySize: number;

  // Rate info
  tokensPerSecond: number;
  lastUpdateTime: string | null;

  // Actions
  updateUsage: (input: number, output: number, cost: number) => void;
  incrementUsage: (input: number, output: number, cost: number) => void;
  resetSession: () => void;
  resetCurrent: () => void;
}

export const useUsageStore = create<UsageState>((set, get) => ({
  currentInputTokens: 0,
  currentOutputTokens: 0,
  currentCost: 0,

  sessionInputTokens: 0,
  sessionOutputTokens: 0,
  sessionCost: 0,
  requestCount: 0,

  usageHistory: [],
  maxHistorySize: 100,

  tokensPerSecond: 0,
  lastUpdateTime: null,

  updateUsage: (input: number, output: number, cost: number) => {
    const now = new Date().toISOString();
    const state = get();

    // Calculate tokens per second if we have a previous update
    let tps = 0;
    if (state.lastUpdateTime) {
      const elapsed = (new Date(now).getTime() - new Date(state.lastUpdateTime).getTime()) / 1000;
      if (elapsed > 0 && elapsed < 60) {
        const newTokens = (input - state.currentInputTokens) + (output - state.currentOutputTokens);
        tps = Math.round(newTokens / elapsed);
      }
    }

    set({
      currentInputTokens: input,
      currentOutputTokens: output,
      currentCost: cost,
      tokensPerSecond: tps > 0 ? tps : state.tokensPerSecond,
      lastUpdateTime: now,
    });
  },

  incrementUsage: (input: number, output: number, cost: number) => {
    const now = new Date().toISOString();
    const state = get();

    // Add to session totals
    const newSessionInput = state.sessionInputTokens + input;
    const newSessionOutput = state.sessionOutputTokens + output;
    const newSessionCost = state.sessionCost + cost;

    // Create snapshot for history
    const snapshot: UsageSnapshot = {
      input_tokens: input,
      output_tokens: output,
      cost,
      timestamp: now,
    };

    // Maintain history size
    const history = [...state.usageHistory, snapshot];
    if (history.length > state.maxHistorySize) {
      history.shift();
    }

    set({
      currentInputTokens: input,
      currentOutputTokens: output,
      currentCost: cost,
      sessionInputTokens: newSessionInput,
      sessionOutputTokens: newSessionOutput,
      sessionCost: newSessionCost,
      requestCount: state.requestCount + 1,
      usageHistory: history,
      lastUpdateTime: now,
    });
  },

  resetSession: () => {
    set({
      currentInputTokens: 0,
      currentOutputTokens: 0,
      currentCost: 0,
      sessionInputTokens: 0,
      sessionOutputTokens: 0,
      sessionCost: 0,
      requestCount: 0,
      usageHistory: [],
      tokensPerSecond: 0,
      lastUpdateTime: null,
    });
  },

  resetCurrent: () => {
    set({
      currentInputTokens: 0,
      currentOutputTokens: 0,
      currentCost: 0,
      tokensPerSecond: 0,
    });
  },
}));

// === Selector hooks for performance ===

/**
 * Get current usage only
 */
export const useCurrentUsage = () =>
  useUsageStore(
    useCallback(
      (state) => ({
        input: state.currentInputTokens,
        output: state.currentOutputTokens,
        cost: state.currentCost,
        tps: state.tokensPerSecond,
      }),
      []
    )
  );

/**
 * Get session totals only
 */
export const useSessionUsage = () =>
  useUsageStore(
    useCallback(
      (state) => ({
        input: state.sessionInputTokens,
        output: state.sessionOutputTokens,
        cost: state.sessionCost,
        requests: state.requestCount,
      }),
      []
    )
  );

/**
 * Format token count for display (e.g., 12400 -> "12.4k")
 */
export function formatTokenCount(tokens: number): string {
  if (tokens < 1000) return tokens.toString();
  if (tokens < 10000) return (tokens / 1000).toFixed(1) + "k";
  if (tokens < 1000000) return Math.round(tokens / 1000) + "k";
  return (tokens / 1000000).toFixed(1) + "M";
}

/**
 * Format cost for display (e.g., 0.42 -> "$0.42")
 */
export function formatCost(cost: number): string {
  if (cost < 0.01) return "<$0.01";
  if (cost < 1) return "$" + cost.toFixed(2);
  return "$" + cost.toFixed(2);
}
