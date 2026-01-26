"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { plansApi, PlanListItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Play,
  Pause,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Eye,
  Copy,
  Trash2,
  RotateCcw,
  Loader2,
  FileText,
  RefreshCw,
} from "lucide-react";

interface PlanListProps {
  onSelectPlan: (planId: string) => void;
  onEditPlan?: (planId: string) => void;
  projectId?: string;
  className?: string;
}

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; bgColor: string; label: string }> = {
  executing: { icon: Play, color: "text-blue-500", bgColor: "bg-blue-500/10", label: "Running" },
  approved: { icon: CheckCircle, color: "text-green-500", bgColor: "bg-green-500/10", label: "Approved" },
  pending: { icon: Clock, color: "text-yellow-500", bgColor: "bg-yellow-500/10", label: "Pending" },
  paused: { icon: Pause, color: "text-orange-500", bgColor: "bg-orange-500/10", label: "Paused" },
  completed: { icon: CheckCircle, color: "text-emerald-600", bgColor: "bg-emerald-500/10", label: "Completed" },
  failed: { icon: XCircle, color: "text-red-500", bgColor: "bg-red-500/10", label: "Failed" },
  cancelled: { icon: XCircle, color: "text-gray-500", bgColor: "bg-gray-500/10", label: "Cancelled" },
  exploring: { icon: Loader2, color: "text-blue-400", bgColor: "bg-blue-400/10", label: "Exploring" },
  drafting: { icon: FileText, color: "text-purple-500", bgColor: "bg-purple-500/10", label: "Drafting" },
};

const FILTER_OPTIONS = [
  { value: "all", label: "All Plans" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "stuck", label: "Stuck" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export function PlanList({ onSelectPlan, onEditPlan, projectId, className }: PlanListProps) {
  const { token } = useAuthStore();
  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [filter, setFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPlans = async () => {
    if (!token) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await plansApi.listPlans(token, {
        status: filter === "all" ? undefined : filter,
        project_id: projectId,
      });
      setPlans(result.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plans");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, [token, filter, projectId]);

  const handleFollowUp = async (planId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;

    try {
      await plansApi.followUpPlan(token, planId);
      fetchPlans();
    } catch (err) {
      console.error("Failed to follow up plan:", err);
    }
  };

  const handleClone = async (planId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;

    try {
      await plansApi.clonePlan(token, planId);
      fetchPlans();
    } catch (err) {
      console.error("Failed to clone plan:", err);
    }
  };

  const handleDelete = async (planId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!token) return;

    if (!confirm("Are you sure you want to delete this plan?")) return;

    try {
      await plansApi.deletePlan(token, planId);
      fetchPlans();
    } catch (err) {
      console.error("Failed to delete plan:", err);
    }
  };

  const getStatusConfig = (status: string) => {
    return STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  };

  if (isLoading) {
    return (
      <div className={cn("flex items-center justify-center p-8", className)}>
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("flex flex-col items-center justify-center p-8 gap-2", className)}>
        <AlertTriangle className="h-6 w-6 text-destructive" />
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" size="sm" onClick={fetchPlans}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Filter bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h3 className="text-sm font-medium">Plans</h3>
        <div className="flex items-center gap-2">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              {FILTER_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={fetchPlans}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Plan list */}
      <ScrollArea className="flex-1">
        {plans.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-muted-foreground">
            <FileText className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-sm">No plans found</p>
            <p className="text-xs">Use /plan to create one</p>
          </div>
        ) : (
          <div className="divide-y">
            <TooltipProvider>
              {plans.map((plan) => {
                const config = getStatusConfig(plan.status);
                const Icon = config.icon;
                const progress = plan.total_steps > 0
                  ? (plan.completed_steps / plan.total_steps) * 100
                  : 0;

                return (
                  <div
                    key={plan.id}
                    className={cn(
                      "p-3 hover:bg-accent/50 cursor-pointer transition-colors",
                      plan.is_running && "bg-blue-500/5"
                    )}
                    onClick={() => onSelectPlan(plan.id)}
                  >
                    <div className="flex items-start gap-3">
                      {/* Status icon */}
                      <div className={cn("rounded-md p-1.5 shrink-0", config.bgColor)}>
                        <Icon className={cn(
                          "h-4 w-4",
                          config.color,
                          plan.is_running && "animate-pulse"
                        )} />
                      </div>

                      {/* Plan info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{plan.title}</span>
                          {plan.is_stuck && (
                            <Badge variant="outline" className="text-[10px] h-4 px-1 border-orange-500 text-orange-500">
                              Stuck
                            </Badge>
                          )}
                          {plan.is_running && (
                            <Badge variant="outline" className="text-[10px] h-4 px-1 border-blue-500 text-blue-500">
                              Running
                            </Badge>
                          )}
                        </div>

                        {/* Progress bar */}
                        {plan.total_steps > 0 && (
                          <div className="flex items-center gap-2 mt-1.5">
                            <Progress value={progress} className="h-1.5 flex-1" />
                            <span className="text-[10px] text-muted-foreground shrink-0">
                              {plan.completed_steps}/{plan.total_steps}
                            </span>
                          </div>
                        )}

                        {/* Meta info */}
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-[10px] text-muted-foreground">
                            {plan.id.slice(0, 8)}
                          </span>
                          <Badge variant="secondary" className="text-[10px] h-4 px-1">
                            {config.label}
                          </Badge>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectPlan(plan.id);
                              }}
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>View</TooltipContent>
                        </Tooltip>

                        {plan.is_stuck && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-orange-500 hover:text-orange-600"
                                onClick={(e) => handleFollowUp(plan.id, e)}
                              >
                                <RotateCcw className="h-3.5 w-3.5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Follow Up</TooltipContent>
                          </Tooltip>
                        )}

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => handleClone(plan.id, e)}
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Clone</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={(e) => handleDelete(plan.id, e)}
                              disabled={plan.is_running}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete</TooltipContent>
                        </Tooltip>
                      </div>
                    </div>
                  </div>
                );
              })}
            </TooltipProvider>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
