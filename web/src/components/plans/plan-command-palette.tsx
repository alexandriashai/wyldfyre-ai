"use client";

import { useState, useEffect, useCallback } from "react";
import { usePlansStore } from "@/stores/plans-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Play,
  Pause,
  Copy,
  Trash2,
  RotateCcw,
  Pencil,
  Eye,
  Plus,
  RefreshCw,
  CheckSquare,
  XCircle,
  ListTodo,
} from "lucide-react";

interface PlanCommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId?: string;
}

export function PlanCommandPalette({ open, onOpenChange, projectId }: PlanCommandPaletteProps) {
  const { token } = useAuthStore();
  const {
    selectedPlan,
    selectedPlanId,
    plans,
    selectPlan,
    pausePlan,
    resumePlan,
    clonePlan,
    deletePlan,
    followUpPlan,
    startEditing,
    refreshPlans,
    openDetailPanel,
    setSelectMode,
  } = usePlansStore();

  const handleCommand = useCallback(async (command: string) => {
    if (!token) return;
    onOpenChange(false);

    switch (command) {
      case "view":
        if (selectedPlanId) {
          openDetailPanel(selectedPlanId);
        }
        break;
      case "edit":
        startEditing();
        break;
      case "pause":
        if (selectedPlanId) {
          await pausePlan(token, selectedPlanId);
          await refreshPlans(token, projectId);
        }
        break;
      case "resume":
        if (selectedPlanId) {
          await resumePlan(token, selectedPlanId);
          await refreshPlans(token, projectId);
        }
        break;
      case "clone":
        if (selectedPlanId) {
          await clonePlan(token, selectedPlanId);
          await refreshPlans(token, projectId);
        }
        break;
      case "delete":
        if (selectedPlanId && confirm("Are you sure you want to delete this plan?")) {
          await deletePlan(token, selectedPlanId);
          await refreshPlans(token, projectId);
        }
        break;
      case "follow-up":
        if (selectedPlanId) {
          await followUpPlan(token, selectedPlanId);
          await refreshPlans(token, projectId);
        }
        break;
      case "refresh":
        await refreshPlans(token, projectId);
        break;
      case "select-mode":
        setSelectMode(true);
        break;
      default:
        // Check if it's a plan selection
        if (command.startsWith("select-")) {
          const planId = command.replace("select-", "");
          await selectPlan(token, planId);
        }
        break;
    }
  }, [token, selectedPlanId, projectId, onOpenChange, openDetailPanel, startEditing, pausePlan, resumePlan, clonePlan, deletePlan, followUpPlan, refreshPlans, setSelectMode, selectPlan]);

  // Determine available actions based on selected plan state
  const canPause = selectedPlan?.is_running && selectedPlan?.status.toLowerCase() !== "paused";
  const canResume = selectedPlan?.status.toLowerCase() === "paused" ||
    (selectedPlan?.is_stuck && !selectedPlan?.is_running);
  const canFollowUp = selectedPlan?.is_stuck;
  const canDelete = !selectedPlan?.is_running;

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search plans or type a command..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        {/* Quick actions for selected plan */}
        {selectedPlan && (
          <CommandGroup heading="Current Plan Actions">
            <CommandItem onSelect={() => handleCommand("view")}>
              <Eye className="h-4 w-4 mr-2" />
              View Details
            </CommandItem>
            <CommandItem onSelect={() => handleCommand("edit")}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit Plan
            </CommandItem>
            {canPause && (
              <CommandItem onSelect={() => handleCommand("pause")}>
                <Pause className="h-4 w-4 mr-2" />
                Pause Execution
              </CommandItem>
            )}
            {canResume && (
              <CommandItem onSelect={() => handleCommand("resume")}>
                <Play className="h-4 w-4 mr-2" />
                Resume Execution
              </CommandItem>
            )}
            {canFollowUp && (
              <CommandItem onSelect={() => handleCommand("follow-up")}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Follow Up
              </CommandItem>
            )}
            <CommandItem onSelect={() => handleCommand("clone")}>
              <Copy className="h-4 w-4 mr-2" />
              Clone Plan
            </CommandItem>
            {canDelete && (
              <CommandItem
                onSelect={() => handleCommand("delete")}
                className="text-destructive"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Plan
              </CommandItem>
            )}
          </CommandGroup>
        )}

        <CommandSeparator />

        {/* General actions */}
        <CommandGroup heading="General">
          <CommandItem onSelect={() => handleCommand("refresh")}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh Plans
          </CommandItem>
          <CommandItem onSelect={() => handleCommand("select-mode")}>
            <CheckSquare className="h-4 w-4 mr-2" />
            Toggle Select Mode
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Recent plans */}
        {plans.length > 0 && (
          <CommandGroup heading="Recent Plans">
            {plans.slice(0, 10).map((plan) => (
              <CommandItem
                key={plan.id}
                onSelect={() => handleCommand(`select-${plan.id}`)}
                className={cn(
                  selectedPlanId === plan.id && "bg-accent"
                )}
              >
                <ListTodo className="h-4 w-4 mr-2" />
                <span className="flex-1 truncate">{plan.title}</span>
                {plan.is_running && (
                  <span className="text-[10px] text-blue-500">Running</span>
                )}
                {plan.is_stuck && (
                  <span className="text-[10px] text-orange-500">Stuck</span>
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}

// Hook to open command palette with keyboard shortcut
export function usePlanCommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+Shift+P or Ctrl+Shift+P
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "p") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return { open, setOpen };
}
