import { create } from "zustand";

export interface MemoryNode {
  id: string;
  content: string;
  phase?: string;
  scope?: string;
  importance?: number;
  agent_source?: string;
  created_at?: string;
  similarity?: number;
}

interface MemoryState {
  // Selection state
  selectedIds: Set<string>;
  isSelectMode: boolean;

  // View mode
  viewMode: "list" | "graph";

  // Filters
  filterPhase: string | null;
  filterScope: string | null;
  filterImportance: number | null;
  sortBy: "relevance" | "date" | "importance" | "phase";

  // Actions
  toggleSelect: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearSelection: () => void;
  setSelectMode: (mode: boolean) => void;
  setViewMode: (mode: "list" | "graph") => void;
  setFilterPhase: (phase: string | null) => void;
  setFilterScope: (scope: string | null) => void;
  setFilterImportance: (level: number | null) => void;
  setSortBy: (sort: "relevance" | "date" | "importance" | "phase") => void;
}

export const useMemoryStore = create<MemoryState>((set) => ({
  selectedIds: new Set<string>(),
  isSelectMode: false,
  viewMode: "list",
  filterPhase: null,
  filterScope: null,
  filterImportance: null,
  sortBy: "relevance",

  toggleSelect: (id: string) => {
    set((state) => {
      const newSet = new Set(state.selectedIds);
      if (newSet.has(id)) newSet.delete(id);
      else newSet.add(id);
      return { selectedIds: newSet };
    });
  },

  selectAll: (ids: string[]) => {
    set({ selectedIds: new Set(ids) });
  },

  clearSelection: () => {
    set({ selectedIds: new Set<string>(), isSelectMode: false });
  },

  setSelectMode: (mode: boolean) => {
    set({ isSelectMode: mode });
    if (!mode) set({ selectedIds: new Set<string>() });
  },

  setViewMode: (mode) => set({ viewMode: mode }),
  setFilterPhase: (phase) => set({ filterPhase: phase }),
  setFilterScope: (scope) => set({ filterScope: scope }),
  setFilterImportance: (level) => set({ filterImportance: level }),
  setSortBy: (sort) => set({ sortBy: sort }),
}));
