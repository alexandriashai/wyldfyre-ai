"use client";

import { useEffect } from "react";
import { usePlansStore } from "@/stores/plans-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  getRiskBadgeStyle,
  formatBranchStrategy,
} from "@/lib/plan-branch-utils";
import {
  GitBranch,
  GitBranchPlus,
  AlertTriangle,
  Shield,
  Loader2,
  Check,
  ArrowRight,
  Info,
} from "lucide-react";

interface PlanBranchIndicatorProps {
  className?: string;
  showDetails?: boolean;
}

export function PlanBranchIndicator({
  className,
  showDetails = false,
}: PlanBranchIndicatorProps) {
  const { token } = useAuthStore();
  const { selectedProject } = useProjectStore();
  const {
    selectedPlan,
    currentBranch,
    branchStrategy,
    planSourceBranch,
    planWorkingBranch,
    isCreatingBranch,
    branchError,
    fetchCurrentBranch,
    createPlanBranch,
    switchToPlanBranch,
    switchToSourceBranch,
    clearBranchError,
  } = usePlansStore();

  // Fetch current branch when component mounts or project changes
  useEffect(() => {
    if (token && selectedProject?.id) {
      fetchCurrentBranch(token, selectedProject.id);
    }
  }, [token, selectedProject?.id, fetchCurrentBranch]);

  if (!selectedPlan || !branchStrategy) {
    return null;
  }

  const { badge, badgeVariant, description } = formatBranchStrategy(branchStrategy);
  const riskStyle = getRiskBadgeStyle(branchStrategy.riskLevel);

  const handleCreateBranch = async () => {
    if (!token || !selectedProject?.id) return;
    clearBranchError();
    await createPlanBranch(token, selectedProject.id);
  };

  const handleSwitchToPlanBranch = async () => {
    if (!token || !selectedProject?.id) return;
    await switchToPlanBranch(token, selectedProject.id);
  };

  const handleSwitchToSourceBranch = async () => {
    if (!token || !selectedProject?.id) return;
    await switchToSourceBranch(token, selectedProject.id);
  };

  // Compact indicator (for plan panel header)
  if (!showDetails) {
    return (
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 px-2 text-xs gap-1",
              branchStrategy.isProtectedBranch && "text-amber-500",
              className
            )}
          >
            {branchStrategy.isProtectedBranch ? (
              <Shield className="h-3 w-3" />
            ) : (
              <GitBranch className="h-3 w-3" />
            )}
            <span className="max-w-[80px] truncate">
              {planWorkingBranch || currentBranch || "—"}
            </span>
            {branchStrategy.strategy === "new-branch" && !planWorkingBranch && (
              <Badge variant="outline" className="h-4 px-1 text-[9px] ml-0.5">
                new
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-3" align="start">
          <BranchDetails
            branchStrategy={branchStrategy}
            currentBranch={currentBranch}
            planSourceBranch={planSourceBranch}
            planWorkingBranch={planWorkingBranch}
            isCreatingBranch={isCreatingBranch}
            branchError={branchError}
            onCreateBranch={handleCreateBranch}
            onSwitchToPlanBranch={handleSwitchToPlanBranch}
            onSwitchToSourceBranch={handleSwitchToSourceBranch}
          />
        </PopoverContent>
      </Popover>
    );
  }

  // Full details view
  return (
    <div className={cn("space-y-3", className)}>
      <BranchDetails
        branchStrategy={branchStrategy}
        currentBranch={currentBranch}
        planSourceBranch={planSourceBranch}
        planWorkingBranch={planWorkingBranch}
        isCreatingBranch={isCreatingBranch}
        branchError={branchError}
        onCreateBranch={handleCreateBranch}
        onSwitchToPlanBranch={handleSwitchToPlanBranch}
        onSwitchToSourceBranch={handleSwitchToSourceBranch}
      />
    </div>
  );
}

interface BranchDetailsProps {
  branchStrategy: NonNullable<ReturnType<typeof usePlansStore.getState>["branchStrategy"]>;
  currentBranch: string | null;
  planSourceBranch: string | null;
  planWorkingBranch: string | null;
  isCreatingBranch: boolean;
  branchError: string | null;
  onCreateBranch: () => void;
  onSwitchToPlanBranch: () => void;
  onSwitchToSourceBranch: () => void;
}

function BranchDetails({
  branchStrategy,
  currentBranch,
  planSourceBranch,
  planWorkingBranch,
  isCreatingBranch,
  branchError,
  onCreateBranch,
  onSwitchToPlanBranch,
  onSwitchToSourceBranch,
}: BranchDetailsProps) {
  const riskStyle = getRiskBadgeStyle(branchStrategy.riskLevel);
  const needsNewBranch = branchStrategy.strategy === "new-branch" && !planWorkingBranch;
  const isOnPlanBranch = planWorkingBranch && currentBranch === planWorkingBranch;
  const isOnSourceBranch = planSourceBranch && currentBranch === planSourceBranch;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-sm">Branch Strategy</span>
        </div>
        <Badge variant="outline" className={cn("text-[10px]", riskStyle.className)}>
          {branchStrategy.riskLevel} risk
        </Badge>
      </div>

      {/* Strategy description */}
      <div className="flex items-start gap-2 p-2 rounded-md bg-muted/50 text-xs">
        <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
        <p className="text-muted-foreground">{branchStrategy.reason}</p>
      </div>

      {/* Protected branch warning */}
      {branchStrategy.isProtectedBranch && (
        <div className="flex items-start gap-2 p-2 rounded-md bg-amber-500/10 border border-amber-500/30 text-xs">
          <Shield className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
          <p className="text-amber-600 dark:text-amber-400">
            <strong>{currentBranch}</strong> is a protected branch. Changes must be made on a separate branch.
          </p>
        </div>
      )}

      {/* Branch info */}
      <div className="space-y-2">
        {/* Source branch */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Source:</span>
          <div className="flex items-center gap-1.5">
            <code className="bg-muted px-1.5 py-0.5 rounded text-[10px]">
              {planSourceBranch || currentBranch || "—"}
            </code>
            {isOnSourceBranch && (
              <Badge variant="secondary" className="h-4 px-1 text-[9px]">
                current
              </Badge>
            )}
          </div>
        </div>

        {/* Working branch (if different) */}
        {(planWorkingBranch || branchStrategy.suggestedBranchName) && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Working:</span>
            <div className="flex items-center gap-1.5">
              <code className="bg-muted px-1.5 py-0.5 rounded text-[10px]">
                {planWorkingBranch || branchStrategy.suggestedBranchName}
              </code>
              {planWorkingBranch ? (
                isOnPlanBranch ? (
                  <Badge variant="default" className="h-4 px-1 text-[9px]">
                    current
                  </Badge>
                ) : (
                  <Badge variant="outline" className="h-4 px-1 text-[9px]">
                    switch
                  </Badge>
                )
              ) : (
                <Badge variant="outline" className="h-4 px-1 text-[9px]">
                  proposed
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {branchError && (
        <div className="flex items-start gap-2 p-2 rounded-md bg-destructive/10 border border-destructive/30 text-xs">
          <AlertTriangle className="h-3.5 w-3.5 text-destructive mt-0.5 shrink-0" />
          <p className="text-destructive">{branchError}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t">
        {needsNewBranch && (
          <Button
            size="sm"
            className="flex-1 h-8 text-xs"
            onClick={onCreateBranch}
            disabled={isCreatingBranch}
          >
            {isCreatingBranch ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <GitBranchPlus className="h-3.5 w-3.5 mr-1.5" />
            )}
            Create Branch
          </Button>
        )}

        {planWorkingBranch && !isOnPlanBranch && (
          <Button
            size="sm"
            variant="outline"
            className="flex-1 h-8 text-xs"
            onClick={onSwitchToPlanBranch}
            disabled={isCreatingBranch}
          >
            <ArrowRight className="h-3.5 w-3.5 mr-1.5" />
            Switch to Plan Branch
          </Button>
        )}

        {planWorkingBranch && isOnPlanBranch && planSourceBranch !== planWorkingBranch && (
          <Button
            size="sm"
            variant="ghost"
            className="flex-1 h-8 text-xs"
            onClick={onSwitchToSourceBranch}
            disabled={isCreatingBranch}
          >
            <ArrowRight className="h-3.5 w-3.5 mr-1.5 rotate-180" />
            Back to Source
          </Button>
        )}

        {!needsNewBranch && !planWorkingBranch && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Check className="h-3.5 w-3.5 text-green-500" />
            Executing on current branch
          </div>
        )}
      </div>
    </div>
  );
}
