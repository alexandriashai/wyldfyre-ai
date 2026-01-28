"use client";

import { PlanListItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
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
  MoreVertical,
  Square,
  CheckSquare,
} from "lucide-react";
import { PlanContextMenu } from "./plan-context-menu";

export interface PlanCardProps {
  plan: PlanListItem;
  isSelected?: boolean;
  isSelectMode?: boolean;
  isChecked?: boolean;
  onSelect: (planId: string) => void;
  onView?: (planId: string) => void;
  onClone?: (planId: string) => void;
  onDelete?: (planId: string) => void;
  onPause?: (planId: string) => void;
  onResume?: (planId: string) => void;
  onFollowUp?: (planId: string) => void;
  onToggleCheck?: (planId: string) => void;
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
  draft: { icon: FileText, color: "text-purple-500", bgColor: "bg-purple-500/10", label: "Draft" },
};

function getStatusConfig(status: string) {
  return STATUS_CONFIG[status.toLowerCase()] || STATUS_CONFIG.pending;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function PlanCard({
  plan,
  isSelected,
  isSelectMode,
  isChecked,
  onSelect,
  onView,
  onClone,
  onDelete,
  onPause,
  onResume,
  onFollowUp,
  onToggleCheck,
}: PlanCardProps) {
  const config = getStatusConfig(plan.status);
  const Icon = config.icon;
  const progress = plan.total_steps > 0
    ? (plan.completed_steps / plan.total_steps) * 100
    : 0;

  return (
    <PlanContextMenu
      plan={plan}
      onView={onView}
      onClone={onClone}
      onDelete={onDelete}
      onPause={onPause}
      onResume={onResume}
      onFollowUp={onFollowUp}
    >
      <div
        className={cn(
          "p-4 rounded-lg border bg-card hover:bg-accent/50 cursor-pointer transition-all",
          isSelected && "ring-2 ring-primary border-primary",
          plan.is_running && "border-blue-500/50 bg-blue-500/5"
        )}
        onClick={() => onSelect(plan.id)}
      >
        <div className="flex items-start gap-3">
          {/* Select checkbox */}
          {isSelectMode && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleCheck?.(plan.id);
              }}
              className="mt-0.5 shrink-0"
            >
              {isChecked ? (
                <CheckSquare className="h-4 w-4 text-primary" />
              ) : (
                <Square className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
          )}

          {/* Status icon */}
          <div className={cn("rounded-md p-2 shrink-0", config.bgColor)}>
            <Icon className={cn(
              "h-4 w-4",
              config.color,
              plan.is_running && "animate-pulse"
            )} />
          </div>

          {/* Plan info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm truncate">{plan.title}</span>
              {plan.is_stuck && (
                <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-orange-500 text-orange-500">
                  <AlertTriangle className="h-2.5 w-2.5 mr-0.5" />
                  Stuck
                </Badge>
              )}
              {plan.is_running && (
                <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-blue-500 text-blue-500">
                  <Loader2 className="h-2.5 w-2.5 mr-0.5 animate-spin" />
                  Running
                </Badge>
              )}
            </div>

            {/* Description preview */}
            {plan.description && (
              <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                {plan.description}
              </p>
            )}

            {/* Progress bar */}
            {plan.total_steps > 0 && (
              <div className="flex items-center gap-2 mt-2">
                <Progress value={progress} className="h-1.5 flex-1" />
                <span className="text-[10px] text-muted-foreground shrink-0 font-mono">
                  {plan.completed_steps}/{plan.total_steps}
                </span>
              </div>
            )}

            {/* Meta info */}
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
                {config.label}
              </Badge>
              <span className="text-[10px] text-muted-foreground">
                {formatDate(plan.updated_at || plan.created_at)}
              </span>
            </div>
          </div>

          {/* Quick actions */}
          {!isSelectMode && (
            <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={(e) => {
                      e.stopPropagation();
                      onView?.(plan.id);
                    }}
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>View Details</TooltipContent>
              </Tooltip>
            </div>
          )}
        </div>
      </div>
    </PlanContextMenu>
  );
}
