"use client";

import { ReactNode } from "react";
import { PlanListItem } from "@/lib/api";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
  Eye,
  Copy,
  Trash2,
  Pause,
  Play,
  RotateCcw,
  Pencil,
  ExternalLink,
  MessageSquare,
} from "lucide-react";

interface PlanContextMenuProps {
  plan: PlanListItem;
  children: ReactNode;
  onView?: (planId: string) => void;
  onEdit?: (planId: string) => void;
  onClone?: (planId: string) => void;
  onDelete?: (planId: string) => void;
  onPause?: (planId: string) => void;
  onResume?: (planId: string) => void;
  onFollowUp?: (planId: string) => void;
  onOpenInChat?: (planId: string) => void;
}

export function PlanContextMenu({
  plan,
  children,
  onView,
  onEdit,
  onClone,
  onDelete,
  onPause,
  onResume,
  onFollowUp,
  onOpenInChat,
}: PlanContextMenuProps) {
  const isPaused = plan.status.toLowerCase() === "paused";
  const isRunning = plan.is_running;
  const isStuck = plan.is_stuck;
  const canPause = isRunning && !isPaused;
  const canResume = isPaused || (isStuck && !isRunning);
  const canDelete = !isRunning;

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        {children}
      </ContextMenuTrigger>
      <ContextMenuContent className="w-48">
        <ContextMenuItem onClick={() => onView?.(plan.id)}>
          <Eye className="h-4 w-4 mr-2" />
          View Details
        </ContextMenuItem>

        {onEdit && (
          <ContextMenuItem onClick={() => onEdit(plan.id)}>
            <Pencil className="h-4 w-4 mr-2" />
            Edit Plan
          </ContextMenuItem>
        )}

        {onOpenInChat && plan.conversation_id && (
          <ContextMenuItem onClick={() => onOpenInChat(plan.id)}>
            <MessageSquare className="h-4 w-4 mr-2" />
            Open in Chat
          </ContextMenuItem>
        )}

        <ContextMenuSeparator />

        {canPause && onPause && (
          <ContextMenuItem onClick={() => onPause(plan.id)}>
            <Pause className="h-4 w-4 mr-2" />
            Pause Execution
          </ContextMenuItem>
        )}

        {canResume && onResume && (
          <ContextMenuItem onClick={() => onResume(plan.id)}>
            <Play className="h-4 w-4 mr-2" />
            Resume Execution
          </ContextMenuItem>
        )}

        {isStuck && onFollowUp && (
          <ContextMenuItem onClick={() => onFollowUp(plan.id)}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Follow Up
          </ContextMenuItem>
        )}

        <ContextMenuSeparator />

        <ContextMenuItem onClick={() => onClone?.(plan.id)}>
          <Copy className="h-4 w-4 mr-2" />
          Clone Plan
        </ContextMenuItem>

        {canDelete && onDelete && (
          <ContextMenuItem
            onClick={() => onDelete(plan.id)}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete Plan
          </ContextMenuItem>
        )}
      </ContextMenuContent>
    </ContextMenu>
  );
}
