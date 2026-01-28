"use client";

import { useState, useMemo } from "react";
import { usePlansStore, PlanStatusFilter, PlanSortBy } from "@/stores/plans-store";
import { PlanListItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TooltipProvider,
} from "@/components/ui/tooltip";
import { PlanCard } from "./plan-card";
import {
  Search,
  SortAsc,
  RefreshCw,
  Loader2,
  FileText,
  CheckSquare,
  Trash2,
  X,
} from "lucide-react";

interface PlansListProps {
  plans: PlanListItem[];
  isLoading: boolean;
  selectedPlanId: string | null;
  onSelectPlan: (planId: string) => void;
  onViewPlan?: (planId: string) => void;
  onClonePlan?: (planId: string) => void;
  onDeletePlan?: (planId: string) => void;
  onPausePlan?: (planId: string) => void;
  onResumePlan?: (planId: string) => void;
  onFollowUpPlan?: (planId: string) => void;
  onRefresh?: () => void;
  className?: string;
}

const FILTER_OPTIONS: { value: PlanStatusFilter; label: string; priority?: number }[] = [
  { value: "all", label: "All Plans" },
  { value: "active", label: "Executing", priority: 1 },
  { value: "draft", label: "Draft", priority: 2 },
  { value: "pending", label: "Pending", priority: 3 },
  { value: "paused", label: "Paused" },
  { value: "stuck", label: "Stuck" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const SORT_OPTIONS: { value: PlanSortBy; label: string }[] = [
  { value: "updated", label: "Last Updated" },
  { value: "created", label: "Created" },
  { value: "progress", label: "Progress" },
  { value: "title", label: "Title" },
];

export function PlansList({
  plans,
  isLoading,
  selectedPlanId,
  onSelectPlan,
  onViewPlan,
  onClonePlan,
  onDeletePlan,
  onPausePlan,
  onResumePlan,
  onFollowUpPlan,
  onRefresh,
  className,
}: PlansListProps) {
  const {
    statusFilter,
    searchQuery,
    sortBy,
    setStatusFilter,
    setSearchQuery,
    setSortBy,
    isSelectMode,
    selectedIds,
    setSelectMode,
    toggleSelect,
    selectAll,
    clearSelection,
  } = usePlansStore();

  // Filter and sort plans
  const filteredPlans = useMemo(() => {
    let result = [...plans];

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((p) =>
        p.title.toLowerCase().includes(query) ||
        (p.description && p.description.toLowerCase().includes(query))
      );
    }

    // Apply status filter
    if (statusFilter !== "all") {
      result = result.filter((p) => {
        const status = p.status.toLowerCase();
        switch (statusFilter) {
          case "active":
            return p.is_running || status === "approved" || status === "executing";
          case "draft":
            return status === "draft" || status === "exploring" || status === "drafting";
          case "pending":
            return status === "pending" || status === "awaiting_approval";
          case "paused":
            return status === "paused";
          case "stuck":
            return p.is_stuck;
          case "completed":
            return status === "completed";
          case "failed":
            return status === "failed";
          default:
            return true;
        }
      });
    }

    // Priority sorting: executing plans first, then drafts, then rest
    result.sort((a, b) => {
      const getPriority = (plan: PlanListItem) => {
        const status = plan.status.toLowerCase();
        if (plan.is_running || status === "executing" || status === "approved") return 0;
        if (status === "draft" || status === "exploring" || status === "drafting") return 1;
        if (status === "pending" || status === "awaiting_approval") return 2;
        if (plan.is_stuck) return 3;
        if (status === "paused") return 4;
        return 5;
      };
      return getPriority(a) - getPriority(b);
    });

    // Apply sorting
    result.sort((a, b) => {
      switch (sortBy) {
        case "updated":
          return new Date(b.updated_at || b.created_at).getTime() -
            new Date(a.updated_at || a.created_at).getTime();
        case "created":
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case "progress":
          const progressA = a.total_steps > 0 ? a.completed_steps / a.total_steps : 0;
          const progressB = b.total_steps > 0 ? b.completed_steps / b.total_steps : 0;
          return progressB - progressA;
        case "title":
          return a.title.localeCompare(b.title);
        default:
          return 0;
      }
    });

    return result;
  }, [plans, searchQuery, statusFilter, sortBy]);

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Search and filters */}
      <div className="p-4 border-b space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search plans..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
              onClick={() => setSearchQuery("")}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {FILTER_OPTIONS.map((option) => (
            <Button
              key={option.value}
              variant={statusFilter === option.value ? "default" : "outline"}
              size="sm"
              className="h-7 text-xs shrink-0"
              onClick={() => setStatusFilter(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>

        {/* Sort and actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as PlanSortBy)}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SortAsc className="h-3 w-3 mr-1" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant={isSelectMode ? "secondary" : "ghost"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setSelectMode(!isSelectMode)}
            >
              <CheckSquare className="h-3 w-3 mr-1" />
              Select
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onRefresh}
              disabled={isLoading}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            </Button>
          </div>
        </div>
      </div>

      {/* Bulk actions bar */}
      {isSelectMode && selectedIds.size > 0 && (
        <div className="px-4 py-2 border-b bg-primary/5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selectedIds.size} selected</span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={selectAll}>
              Select All
            </Button>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={clearSelection}>
              Clear
            </Button>
          </div>
          <Button
            variant="destructive"
            size="sm"
            className="h-6 text-xs"
            onClick={() => {
              // Handle bulk delete through parent
              Array.from(selectedIds).forEach((id) => onDeletePlan?.(id));
            }}
          >
            <Trash2 className="h-3 w-3 mr-1" />
            Delete
          </Button>
        </div>
      )}

      {/* Results count */}
      <div className="px-4 py-2 text-xs text-muted-foreground border-b">
        {filteredPlans.length} {filteredPlans.length === 1 ? "plan" : "plans"}
      </div>

      {/* Plans list */}
      <ScrollArea className="flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : filteredPlans.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <FileText className="h-10 w-10 mb-3 opacity-50" />
            <p className="text-sm font-medium">No plans found</p>
            <p className="text-xs mt-1">
              {searchQuery ? "Try a different search term" : "Use /plan to create one"}
            </p>
          </div>
        ) : (
          <TooltipProvider>
            <div className="p-4 space-y-3">
              {filteredPlans.map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  isSelected={selectedPlanId === plan.id}
                  isSelectMode={isSelectMode}
                  isChecked={selectedIds.has(plan.id)}
                  onSelect={onSelectPlan}
                  onView={onViewPlan}
                  onClone={onClonePlan}
                  onDelete={onDeletePlan}
                  onPause={onPausePlan}
                  onResume={onResumePlan}
                  onFollowUp={onFollowUpPlan}
                  onToggleCheck={toggleSelect}
                />
              ))}
            </div>
          </TooltipProvider>
        )}
      </ScrollArea>
    </div>
  );
}
