import { create } from "zustand";
import { plansApi, branchApi, PlanListItem, PlanDetail, PlanHistoryEntry } from "@/lib/api";
import {
  BranchStrategy,
  BranchStrategyResult,
  BranchConfig,
  DEFAULT_BRANCH_CONFIG,
  determineBranchStrategy,
  generateBranchName,
} from "@/lib/plan-branch-utils";

export type PlanStatusFilter = "all" | "active" | "draft" | "pending" | "paused" | "completed" | "failed" | "stuck";
export type PlanSortBy = "created" | "updated" | "progress" | "title";

interface PlansState {
  // List state
  plans: PlanListItem[];
  isLoading: boolean;
  statusFilter: PlanStatusFilter;
  searchQuery: string;
  sortBy: PlanSortBy;
  totalPlans: number;

  // Selected plan state
  selectedPlanId: string | null;
  selectedPlan: PlanDetail | null;
  planHistory: PlanHistoryEntry[];
  isLoadingPlan: boolean;
  isLoadingHistory: boolean;

  // Edit mode state
  isEditing: boolean;
  editDraft: Partial<PlanDetail> | null;
  isSaving: boolean;

  // Detail panel state
  isDetailPanelOpen: boolean;
  detailPanelTab: "steps" | "history" | "settings";

  // Selection mode (for bulk actions)
  isSelectMode: boolean;
  selectedIds: Set<string>;

  // Branch integration state
  currentBranch: string | null;
  branchStrategy: BranchStrategyResult | null;
  isCreatingBranch: boolean;
  branchError: string | null;
  planSourceBranch: string | null;
  planWorkingBranch: string | null;
  branchConfig: BranchConfig;

  // Actions - List
  fetchPlans: (token: string, projectId?: string) => Promise<void>;
  setStatusFilter: (filter: PlanStatusFilter) => void;
  setSearchQuery: (query: string) => void;
  setSortBy: (sortBy: PlanSortBy) => void;
  refreshPlans: (token: string, projectId?: string) => Promise<void>;

  // Actions - Selected plan
  selectPlan: (token: string, planId: string) => Promise<void>;
  clearSelectedPlan: () => void;
  fetchPlanHistory: (token: string, planId: string) => Promise<void>;

  // Actions - CRUD
  updatePlan: (token: string, planId: string, data: Partial<PlanDetail>) => Promise<boolean>;
  deletePlan: (token: string, planId: string) => Promise<boolean>;
  clonePlan: (token: string, planId: string, newTitle?: string) => Promise<string | null>;
  pausePlan: (token: string, planId: string) => Promise<boolean>;
  resumePlan: (token: string, planId: string) => Promise<boolean>;
  followUpPlan: (token: string, planId: string, context?: string) => Promise<boolean>;

  // Actions - Edit mode
  startEditing: () => void;
  cancelEditing: () => void;
  updateEditDraft: (changes: Partial<PlanDetail>) => void;
  saveEditDraft: (token: string) => Promise<boolean>;

  // Actions - Detail panel
  openDetailPanel: (planId?: string) => void;
  closeDetailPanel: () => void;
  setDetailPanelTab: (tab: "steps" | "history" | "settings") => void;

  // Actions - Selection mode
  setSelectMode: (enabled: boolean) => void;
  toggleSelect: (planId: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  bulkDelete: (token: string) => Promise<number>;

  // Actions - Step management
  updateStep: (token: string, planId: string, stepId: string, data: Record<string, unknown>) => Promise<boolean>;
  addStep: (token: string, planId: string, afterStepId: string | null, step: Record<string, unknown>) => Promise<boolean>;
  removeStep: (token: string, planId: string, stepId: string) => Promise<boolean>;
  reorderSteps: (token: string, planId: string, stepIds: string[]) => Promise<boolean>;

  // Actions - Branch integration
  fetchCurrentBranch: (token: string, projectId: string) => Promise<void>;
  calculateBranchStrategy: () => void;
  createPlanBranch: (token: string, projectId: string, branchName?: string) => Promise<boolean>;
  switchToPlanBranch: (token: string, projectId: string) => Promise<boolean>;
  switchToSourceBranch: (token: string, projectId: string) => Promise<boolean>;
  setCurrentBranch: (branch: string | null) => void;
  setBranchConfig: (config: Partial<BranchConfig>) => void;
  clearBranchError: () => void;
}

export const usePlansStore = create<PlansState>((set, get) => ({
  // Initial state - List
  plans: [],
  isLoading: false,
  statusFilter: "all",
  searchQuery: "",
  sortBy: "updated",
  totalPlans: 0,

  // Initial state - Selected plan
  selectedPlanId: null,
  selectedPlan: null,
  planHistory: [],
  isLoadingPlan: false,
  isLoadingHistory: false,

  // Initial state - Edit mode
  isEditing: false,
  editDraft: null,
  isSaving: false,

  // Initial state - Detail panel
  isDetailPanelOpen: false,
  detailPanelTab: "steps",

  // Initial state - Selection mode
  isSelectMode: false,
  selectedIds: new Set(),

  // Initial state - Branch integration
  currentBranch: null,
  branchStrategy: null,
  isCreatingBranch: false,
  branchError: null,
  planSourceBranch: null,
  planWorkingBranch: null,
  branchConfig: DEFAULT_BRANCH_CONFIG,

  // List actions
  fetchPlans: async (token: string, projectId?: string) => {
    set({ isLoading: true });
    try {
      // Always fetch all plans - frontend handles filtering
      const result = await plansApi.listPlans(token, {
        project_id: projectId,
        limit: 100, // Fetch more plans to ensure we get all statuses
      });
      set({
        plans: result.plans,
        totalPlans: result.total,
        isLoading: false,
      });
    } catch (error) {
      console.error("Failed to fetch plans:", error);
      set({ isLoading: false });
    }
  },

  setStatusFilter: (filter: PlanStatusFilter) => {
    set({ statusFilter: filter });
  },

  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  setSortBy: (sortBy: PlanSortBy) => {
    set({ sortBy });
  },

  refreshPlans: async (token: string, projectId?: string) => {
    await get().fetchPlans(token, projectId);
  },

  // Selected plan actions
  selectPlan: async (token: string, planId: string) => {
    set({ isLoadingPlan: true, selectedPlanId: planId });
    try {
      const plan = await plansApi.getPlan(token, planId, true);
      set({
        selectedPlan: plan,
        isLoadingPlan: false,
        isDetailPanelOpen: true,
      });
    } catch (error) {
      console.error("Failed to fetch plan:", error);
      set({ isLoadingPlan: false });
    }
  },

  clearSelectedPlan: () => {
    set({
      selectedPlanId: null,
      selectedPlan: null,
      planHistory: [],
      isEditing: false,
      editDraft: null,
    });
  },

  fetchPlanHistory: async (token: string, planId: string) => {
    set({ isLoadingHistory: true });
    try {
      const result = await plansApi.getPlanHistory(token, planId);
      set({ planHistory: result.entries, isLoadingHistory: false });
    } catch (error) {
      console.error("Failed to fetch plan history:", error);
      set({ isLoadingHistory: false });
    }
  },

  // CRUD actions
  updatePlan: async (token: string, planId: string, data: Partial<PlanDetail>) => {
    try {
      await plansApi.updatePlan(token, planId, {
        title: data.title,
        description: data.description,
        status: data.status,
        metadata: data.metadata,
      });
      // Refresh the selected plan
      if (get().selectedPlanId === planId) {
        await get().selectPlan(token, planId);
      }
      return true;
    } catch (error) {
      console.error("Failed to update plan:", error);
      return false;
    }
  },

  deletePlan: async (token: string, planId: string) => {
    try {
      await plansApi.deletePlan(token, planId);
      set((state) => ({
        plans: state.plans.filter((p) => p.id !== planId),
        totalPlans: state.totalPlans - 1,
        selectedPlanId: state.selectedPlanId === planId ? null : state.selectedPlanId,
        selectedPlan: state.selectedPlanId === planId ? null : state.selectedPlan,
        isDetailPanelOpen: state.selectedPlanId === planId ? false : state.isDetailPanelOpen,
      }));
      return true;
    } catch (error) {
      console.error("Failed to delete plan:", error);
      return false;
    }
  },

  clonePlan: async (token: string, planId: string, newTitle?: string) => {
    try {
      const result = await plansApi.clonePlan(token, planId, newTitle);
      if (result.success && result.plan_id) {
        // Refresh plans list
        await get().fetchPlans(token);
        return result.plan_id;
      }
      return null;
    } catch (error) {
      console.error("Failed to clone plan:", error);
      return null;
    }
  },

  pausePlan: async (token: string, planId: string) => {
    try {
      await plansApi.pausePlan(token, planId);
      // Update local state
      set((state) => ({
        plans: state.plans.map((p) =>
          p.id === planId ? { ...p, status: "paused", is_running: false } : p
        ),
      }));
      if (get().selectedPlanId === planId) {
        await get().selectPlan(token, planId);
      }
      return true;
    } catch (error) {
      console.error("Failed to pause plan:", error);
      return false;
    }
  },

  resumePlan: async (token: string, planId: string) => {
    try {
      await plansApi.resumePlan(token, planId);
      // Update local state
      set((state) => ({
        plans: state.plans.map((p) =>
          p.id === planId ? { ...p, status: "approved", is_running: true } : p
        ),
      }));
      if (get().selectedPlanId === planId) {
        await get().selectPlan(token, planId);
      }
      return true;
    } catch (error) {
      console.error("Failed to resume plan:", error);
      return false;
    }
  },

  followUpPlan: async (token: string, planId: string, context?: string) => {
    try {
      await plansApi.followUpPlan(token, planId, context);
      if (get().selectedPlanId === planId) {
        await get().selectPlan(token, planId);
      }
      return true;
    } catch (error) {
      console.error("Failed to follow up plan:", error);
      return false;
    }
  },

  // Edit mode actions
  startEditing: () => {
    const { selectedPlan } = get();
    if (selectedPlan) {
      set({
        isEditing: true,
        editDraft: { ...selectedPlan },
      });
    }
  },

  cancelEditing: () => {
    set({
      isEditing: false,
      editDraft: null,
    });
  },

  updateEditDraft: (changes: Partial<PlanDetail>) => {
    set((state) => ({
      editDraft: state.editDraft ? { ...state.editDraft, ...changes } : null,
    }));
  },

  saveEditDraft: async (token: string) => {
    const { editDraft, selectedPlanId } = get();
    if (!editDraft || !selectedPlanId) return false;

    set({ isSaving: true });
    try {
      const success = await get().updatePlan(token, selectedPlanId, editDraft);
      if (success) {
        set({ isEditing: false, editDraft: null, isSaving: false });
        return true;
      }
      set({ isSaving: false });
      return false;
    } catch (error) {
      console.error("Failed to save edit draft:", error);
      set({ isSaving: false });
      return false;
    }
  },

  // Detail panel actions
  openDetailPanel: (planId?: string) => {
    if (planId) {
      set({ selectedPlanId: planId });
    }
    set({ isDetailPanelOpen: true });
  },

  closeDetailPanel: () => {
    set({
      isDetailPanelOpen: false,
      isEditing: false,
      editDraft: null,
    });
  },

  setDetailPanelTab: (tab: "steps" | "history" | "settings") => {
    set({ detailPanelTab: tab });
  },

  // Selection mode actions
  setSelectMode: (enabled: boolean) => {
    set({
      isSelectMode: enabled,
      selectedIds: enabled ? get().selectedIds : new Set(),
    });
  },

  toggleSelect: (planId: string) => {
    set((state) => {
      const newSelected = new Set(state.selectedIds);
      if (newSelected.has(planId)) {
        newSelected.delete(planId);
      } else {
        newSelected.add(planId);
      }
      return { selectedIds: newSelected };
    });
  },

  selectAll: () => {
    set((state) => ({
      selectedIds: new Set(state.plans.map((p) => p.id)),
    }));
  },

  clearSelection: () => {
    set({ selectedIds: new Set() });
  },

  bulkDelete: async (token: string) => {
    const { selectedIds } = get();
    let deleted = 0;

    for (const planId of selectedIds) {
      const success = await get().deletePlan(token, planId);
      if (success) deleted++;
    }

    set({ selectedIds: new Set(), isSelectMode: false });
    return deleted;
  },

  // Step management actions
  updateStep: async (token: string, planId: string, stepId: string, data: Record<string, unknown>) => {
    const { selectedPlan } = get();
    if (!selectedPlan) return false;

    try {
      const updatedSteps = selectedPlan.steps.map((s) =>
        s.id === stepId ? { ...s, ...data } : s
      );
      await plansApi.updatePlan(token, planId, {
        steps: updatedSteps.map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          status: s.status,
          agent: s.agent,
          todos: s.todos,
        })),
      });
      await get().selectPlan(token, planId);
      return true;
    } catch (error) {
      console.error("Failed to update step:", error);
      return false;
    }
  },

  addStep: async (token: string, planId: string, afterStepId: string | null, step: Record<string, unknown>) => {
    const { selectedPlan } = get();
    if (!selectedPlan) return false;

    try {
      const newSteps = [...selectedPlan.steps];
      const insertIndex = afterStepId
        ? newSteps.findIndex((s) => s.id === afterStepId) + 1
        : 0;

      // Convert string[] to TodoItem[]
      const rawTodos = step.todos as string[] || [];
      const todoItems = rawTodos.map((text) => ({ text, completed: false }));

      newSteps.splice(insertIndex, 0, {
        id: crypto.randomUUID(),
        index: insertIndex,
        title: step.title as string || "New Step",
        description: step.description as string || "",
        status: "pending",
        agent: step.agent as string,
        todos: todoItems,
        notes: [],
        completed_todos: 0,
        total_todos: todoItems.length,
      });

      // Reindex steps
      newSteps.forEach((s, i) => {
        s.index = i;
      });

      await plansApi.updatePlan(token, planId, {
        steps: newSteps.map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          status: s.status,
          agent: s.agent,
          todos: s.todos,
        })),
      });
      await get().selectPlan(token, planId);
      return true;
    } catch (error) {
      console.error("Failed to add step:", error);
      return false;
    }
  },

  removeStep: async (token: string, planId: string, stepId: string) => {
    const { selectedPlan } = get();
    if (!selectedPlan) return false;

    try {
      const updatedSteps = selectedPlan.steps.filter((s) => s.id !== stepId);
      // Reindex
      updatedSteps.forEach((s, i) => {
        s.index = i;
      });

      await plansApi.updatePlan(token, planId, {
        steps: updatedSteps.map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          status: s.status,
          agent: s.agent,
          todos: s.todos,
        })),
      });
      await get().selectPlan(token, planId);
      return true;
    } catch (error) {
      console.error("Failed to remove step:", error);
      return false;
    }
  },

  reorderSteps: async (token: string, planId: string, stepIds: string[]) => {
    const { selectedPlan } = get();
    if (!selectedPlan) return false;

    try {
      const stepMap = new Map(selectedPlan.steps.map((s) => [s.id, s]));
      const reorderedSteps = stepIds
        .map((id) => stepMap.get(id))
        .filter((s): s is NonNullable<typeof s> => s !== undefined);

      // Reindex
      reorderedSteps.forEach((s, i) => {
        s.index = i;
      });

      await plansApi.updatePlan(token, planId, {
        steps: reorderedSteps.map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description,
          status: s.status,
          agent: s.agent,
          todos: s.todos,
        })),
      });
      await get().selectPlan(token, planId);
      return true;
    } catch (error) {
      console.error("Failed to reorder steps:", error);
      return false;
    }
  },

  // Branch integration actions
  fetchCurrentBranch: async (token: string, projectId: string) => {
    try {
      const result = await branchApi.getBranches(token, projectId);
      const currentBranch = result.current || null;
      set({ currentBranch });

      // Recalculate strategy with new branch info
      get().calculateBranchStrategy();
    } catch (error) {
      console.error("Failed to fetch current branch:", error);
    }
  },

  calculateBranchStrategy: () => {
    const { selectedPlan, currentBranch, branchConfig } = get();
    if (!selectedPlan || !currentBranch) {
      set({ branchStrategy: null });
      return;
    }

    const strategy = determineBranchStrategy(selectedPlan, currentBranch, branchConfig);
    set({
      branchStrategy: strategy,
      planSourceBranch: currentBranch,
    });
  },

  createPlanBranch: async (token: string, projectId: string, branchName?: string) => {
    const { selectedPlan, branchStrategy, branchConfig } = get();
    if (!selectedPlan) return false;

    set({ isCreatingBranch: true, branchError: null });

    try {
      const finalBranchName = branchName ||
        branchStrategy?.suggestedBranchName ||
        generateBranchName(selectedPlan, branchConfig);

      // Create and checkout the new branch
      await branchApi.checkoutBranch(token, projectId, {
        branch: finalBranchName,
        create: true,
      });

      set({
        isCreatingBranch: false,
        planWorkingBranch: finalBranchName,
        currentBranch: finalBranchName,
      });

      // Recalculate strategy
      get().calculateBranchStrategy();

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create branch";
      set({
        isCreatingBranch: false,
        branchError: message,
      });
      return false;
    }
  },

  switchToPlanBranch: async (token: string, projectId: string) => {
    const { planWorkingBranch } = get();
    if (!planWorkingBranch) return false;

    set({ isCreatingBranch: true, branchError: null });

    try {
      await branchApi.checkoutBranch(token, projectId, {
        branch: planWorkingBranch,
        create: false,
      });

      set({
        isCreatingBranch: false,
        currentBranch: planWorkingBranch,
      });

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to switch branch";
      set({
        isCreatingBranch: false,
        branchError: message,
      });
      return false;
    }
  },

  switchToSourceBranch: async (token: string, projectId: string) => {
    const { planSourceBranch } = get();
    if (!planSourceBranch) return false;

    set({ isCreatingBranch: true, branchError: null });

    try {
      await branchApi.checkoutBranch(token, projectId, {
        branch: planSourceBranch,
        create: false,
      });

      set({
        isCreatingBranch: false,
        currentBranch: planSourceBranch,
      });

      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to switch branch";
      set({
        isCreatingBranch: false,
        branchError: message,
      });
      return false;
    }
  },

  setCurrentBranch: (branch: string | null) => {
    set({ currentBranch: branch });
    get().calculateBranchStrategy();
  },

  setBranchConfig: (config: Partial<BranchConfig>) => {
    set((state) => ({
      branchConfig: { ...state.branchConfig, ...config },
    }));
    get().calculateBranchStrategy();
  },

  clearBranchError: () => {
    set({ branchError: null });
  },
}));
