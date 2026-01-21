"use client";

import { useState } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  Clock,
  Pencil,
} from "lucide-react";

// Simple markdown-like rendering
function renderPlanContent(content: string) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];

  lines.forEach((line, i) => {
    // Headers
    if (line.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="font-semibold text-sm mt-3 mb-1">
          {line.slice(4)}
        </h4>
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="font-semibold mt-3 mb-1">
          {line.slice(3)}
        </h3>
      );
    } else if (line.startsWith("# ")) {
      elements.push(
        <h2 key={i} className="font-bold text-lg mt-4 mb-2">
          {line.slice(2)}
        </h2>
      );
    }
    // List items
    else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="ml-4 text-sm">
          {line.slice(2)}
        </li>
      );
    }
    // Numbered list items
    else if (/^\d+\.\s/.test(line)) {
      elements.push(
        <li key={i} className="ml-4 text-sm list-decimal">
          {line.replace(/^\d+\.\s/, "")}
        </li>
      );
    }
    // Code blocks
    else if (line.startsWith("```")) {
      // Skip code block markers
    }
    // Empty lines
    else if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    }
    // Regular text
    else {
      elements.push(
        <p key={i} className="text-sm">
          {line}
        </p>
      );
    }
  });

  return elements;
}

interface PlanPanelProps {
  className?: string;
}

export function PlanPanel({ className }: PlanPanelProps) {
  const { token } = useAuthStore();
  const {
    currentPlan,
    planStatus,
    approvePlan,
    rejectPlan,
    currentConversation,
  } = useChatStore();

  const [isOpen, setIsOpen] = useState(true);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  if (!currentPlan) {
    return null;
  }

  const handleApprove = async () => {
    if (!token) return;
    setIsApproving(true);
    try {
      await approvePlan(token);
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    if (!token) return;
    setIsRejecting(true);
    try {
      await rejectPlan(token);
    } finally {
      setIsRejecting(false);
    }
  };

  const statusConfig = {
    DRAFT: {
      label: "Draft",
      variant: "secondary" as const,
      icon: Pencil,
    },
    PENDING: {
      label: "Pending Approval",
      variant: "outline" as const,
      icon: Clock,
    },
    APPROVED: {
      label: "Approved",
      variant: "default" as const,
      icon: Check,
    },
    REJECTED: {
      label: "Rejected",
      variant: "destructive" as const,
      icon: X,
    },
    COMPLETED: {
      label: "Completed",
      variant: "default" as const,
      icon: Check,
    },
  };

  const status = planStatus ? statusConfig[planStatus] : statusConfig.DRAFT;
  const StatusIcon = status.icon;
  const showActions = planStatus === "PENDING" || planStatus === "DRAFT";

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("border-b bg-muted/30", className)}
    >
      <CollapsibleTrigger asChild>
        <div className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-muted/50 transition-colors">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Plan</span>
            <Badge variant={status.variant} className="h-5 text-xs">
              <StatusIcon className="h-3 w-3 mr-1" />
              {status.label}
            </Badge>
          </div>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-4 pb-3">
          <ScrollArea className="max-h-64">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              {renderPlanContent(currentPlan)}
            </div>
          </ScrollArea>

          {showActions && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t">
              <Button
                variant="default"
                size="sm"
                onClick={handleApprove}
                disabled={isApproving || isRejecting}
                className="flex-1"
              >
                <Check className="h-4 w-4 mr-2" />
                {isApproving ? "Approving..." : "Approve Plan"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleReject}
                disabled={isApproving || isRejecting}
                className="flex-1"
              >
                <X className="h-4 w-4 mr-2" />
                {isRejecting ? "Rejecting..." : "Reject"}
              </Button>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
