"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { usePlansStore } from "@/stores/plans-store";
import { useProjectStore } from "@/stores/project-store";
import {
  PlansList,
  PlanDetailPanel,
  PlanCommandPalette,
  usePlanCommandPalette,
} from "@/components/plans";
import { Button } from "@/components/ui/button";
import { Loader2, ListTodo, Keyboard, RefreshCw, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

export default function WorkspacePlansPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAuthStore();
  const { selectedProject } = useProjectStore();
  const {
    plans,
    isLoading,
    selectedPlanId,
    fetchPlans,
    selectPlan,
    clonePlan,
    deletePlan,
    pausePlan,
    resumePlan,
    followUpPlan,
    openDetailPanel,
    refreshPlans,
  } = usePlansStore();

  const { open: commandOpen, setOpen: setCommandOpen } = usePlanCommandPalette();
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize and fetch plans
  useEffect(() => {
    const init = async () => {
      if (!token) return;

      await fetchPlans(token, selectedProject?.id);

      // Check for planId in URL query params
      const planId = searchParams.get("id");
      if (planId) {
        await selectPlan(token, planId);
      }

      setIsInitialized(true);
    };

    init();
  }, [token, selectedProject?.id, fetchPlans, selectPlan, searchParams]);

  const handleSelectPlan = useCallback(async (planId: string) => {
    if (!token) return;
    await selectPlan(token, planId);
    // Update URL with plan ID
    router.push(`/workspace/plans?id=${planId}`, { scroll: false });
  }, [token, selectPlan, router]);

  const handleViewPlan = useCallback(async (planId: string) => {
    if (!token) return;
    await selectPlan(token, planId);
    openDetailPanel(planId);
    router.push(`/workspace/plans?id=${planId}`, { scroll: false });
  }, [token, selectPlan, openDetailPanel, router]);

  const handleClonePlan = useCallback(async (planId: string) => {
    if (!token) return;
    const newId = await clonePlan(token, planId);
    if (newId) {
      await refreshPlans(token, selectedProject?.id);
    }
  }, [token, clonePlan, refreshPlans, selectedProject?.id]);

  const handleDeletePlan = useCallback(async (planId: string) => {
    if (!token) return;
    if (!confirm("Are you sure you want to delete this plan?")) return;
    await deletePlan(token, planId);
    await refreshPlans(token, selectedProject?.id);
    // Clear URL if deleted plan was selected
    if (planId === selectedPlanId) {
      router.push("/workspace/plans", { scroll: false });
    }
  }, [token, deletePlan, refreshPlans, selectedProject?.id, selectedPlanId, router]);

  const handlePausePlan = useCallback(async (planId: string) => {
    if (!token) return;
    await pausePlan(token, planId);
    await refreshPlans(token, selectedProject?.id);
  }, [token, pausePlan, refreshPlans, selectedProject?.id]);

  const handleResumePlan = useCallback(async (planId: string) => {
    if (!token) return;
    await resumePlan(token, planId);
    await refreshPlans(token, selectedProject?.id);
  }, [token, resumePlan, refreshPlans, selectedProject?.id]);

  const handleFollowUpPlan = useCallback(async (planId: string) => {
    if (!token) return;
    await followUpPlan(token, planId);
    await refreshPlans(token, selectedProject?.id);
  }, [token, followUpPlan, refreshPlans, selectedProject?.id]);

  const handleRefresh = useCallback(async () => {
    if (!token) return;
    await refreshPlans(token, selectedProject?.id);
  }, [token, refreshPlans, selectedProject?.id]);

  if (!isInitialized) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <div className="flex items-center gap-3">
          <Link href="/workspace/chats">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex items-center gap-2">
            <ListTodo className="h-5 w-5 text-muted-foreground" />
            <h1 className="text-lg font-semibold">Plans</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => setCommandOpen(true)}
          >
            <Keyboard className="h-4 w-4 mr-1.5" />
            <span className="hidden sm:inline">Commands</span>
            <kbd className="ml-2 hidden sm:inline text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {navigator.platform.includes("Mac") ? "⌘⇧P" : "Ctrl+Shift+P"}
            </kbd>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 min-h-0">
        {plans.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <ListTodo className="h-12 w-12 mb-4 opacity-50" />
            <h2 className="text-lg font-medium mb-1">No plans yet</h2>
            <p className="text-sm text-center max-w-sm mb-4">
              Plans help organize complex tasks into steps.
              Use <code className="bg-muted px-1.5 py-0.5 rounded text-xs">/plan</code> in chat to create one.
            </p>
            <Link href="/workspace/chats">
              <Button variant="outline" size="sm">
                Go to Chats
              </Button>
            </Link>
          </div>
        ) : (
          <PlansList
            plans={plans}
            isLoading={isLoading}
            selectedPlanId={selectedPlanId}
            onSelectPlan={handleSelectPlan}
            onViewPlan={handleViewPlan}
            onClonePlan={handleClonePlan}
            onDeletePlan={handleDeletePlan}
            onPausePlan={handlePausePlan}
            onResumePlan={handleResumePlan}
            onFollowUpPlan={handleFollowUpPlan}
            onRefresh={handleRefresh}
            className="h-full"
          />
        )}
      </div>

      {/* Detail panel (slide-out sheet) */}
      <PlanDetailPanel />

      {/* Command palette */}
      <PlanCommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
        projectId={selectedProject?.id}
      />
    </div>
  );
}
