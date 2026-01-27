"use client";

import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useChatStore } from "@/stores/chat-store";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Undo2,
  Redo2,
  History,
  FileText,
  Loader2,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface RollbackControlsProps {
  planId?: string;
  stepId?: string;
  taskId?: string;
  className?: string;
  compact?: boolean;
}

export function RollbackControls({
  planId,
  stepId,
  taskId,
  className,
  compact = false,
}: RollbackControlsProps) {
  const { rollback, redo } = useChat();
  const { isRollingBack, lastRollbackResult, planSteps } = useChatStore();

  const [showHistory, setShowHistory] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"rollback" | "redo" | null>(null);
  const [previewResult, setPreviewResult] = useState<{
    filesRestored: string[];
    filesDeleted: string[];
  } | null>(null);

  // Check if we have rollback data available
  const hasRollbackTarget = planId || taskId;

  // Find step info if stepId provided
  const stepInfo = stepId
    ? planSteps.find((s) => s.id === stepId)
    : null;

  const handlePreview = async (action: "rollback" | "redo") => {
    // Trigger dry run to preview changes
    if (action === "rollback") {
      rollback({
        planId,
        taskId,
        stepId,
        dryRun: true,
      });
    } else {
      redo({
        planId,
        taskId,
        stepId,
        dryRun: true,
      });
    }
    setConfirmAction(action);
  };

  const handleConfirm = () => {
    if (confirmAction === "rollback") {
      rollback({
        planId,
        taskId,
        stepId,
        dryRun: false,
      });
    } else if (confirmAction === "redo") {
      redo({
        planId,
        taskId,
        stepId,
        dryRun: false,
      });
    }
    setConfirmAction(null);
    setPreviewResult(null);
  };

  const handleCancel = () => {
    setConfirmAction(null);
    setPreviewResult(null);
  };

  if (!hasRollbackTarget) {
    return null;
  }

  // Compact mode - just icons
  if (compact) {
    return (
      <div className={cn("flex items-center gap-1", className)}>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => handlePreview("rollback")}
          disabled={isRollingBack}
          title="Undo changes"
        >
          {isRollingBack ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Undo2 className="h-3.5 w-3.5" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => handlePreview("redo")}
          disabled={isRollingBack}
          title="Redo changes"
        >
          <Redo2 className="h-3.5 w-3.5" />
        </Button>

        <AlertDialog open={confirmAction !== null} onOpenChange={() => handleCancel()}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {confirmAction === "rollback" ? "Undo Changes?" : "Redo Changes?"}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {confirmAction === "rollback"
                  ? "This will restore files to their previous state. This action can be redone later."
                  : "This will reapply the changes that were previously undone."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirm}>
                {confirmAction === "rollback" ? "Undo" : "Redo"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  // Full mode with labels
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => handlePreview("rollback")}
          disabled={isRollingBack}
          className="h-8"
        >
          {isRollingBack ? (
            <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
          ) : (
            <Undo2 className="h-3.5 w-3.5 mr-1.5" />
          )}
          Undo{stepId ? " Step" : ""}
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => handlePreview("redo")}
          disabled={isRollingBack}
          className="h-8"
        >
          <Redo2 className="h-3.5 w-3.5 mr-1.5" />
          Redo{stepId ? " Step" : ""}
        </Button>

        <Popover open={showHistory} onOpenChange={setShowHistory}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8">
              <History className="h-3.5 w-3.5 mr-1.5" />
              History
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80" align="start">
            <div className="space-y-2">
              <p className="text-sm font-medium">Change History</p>
              {lastRollbackResult ? (
                <div className="space-y-2 text-xs">
                  <div className="flex items-center gap-2">
                    {lastRollbackResult.success ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span>
                      Last action: {lastRollbackResult.filesRestored.length} files restored,{" "}
                      {lastRollbackResult.filesDeleted.length} files deleted
                    </span>
                  </div>
                  {lastRollbackResult.filesRestored.length > 0 && (
                    <div className="pl-6">
                      <p className="text-muted-foreground mb-1">Restored:</p>
                      <ul className="list-disc list-inside">
                        {lastRollbackResult.filesRestored.slice(0, 5).map((f) => (
                          <li key={f} className="truncate" title={f}>
                            {f.split("/").pop()}
                          </li>
                        ))}
                        {lastRollbackResult.filesRestored.length > 5 && (
                          <li className="text-muted-foreground">
                            +{lastRollbackResult.filesRestored.length - 5} more
                          </li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No rollback history yet</p>
              )}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {stepInfo && (
        <p className="text-xs text-muted-foreground">
          Step: {stepInfo.title}
        </p>
      )}

      {/* Confirmation Dialog */}
      <AlertDialog open={confirmAction !== null} onOpenChange={() => handleCancel()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmAction === "rollback" ? "Undo Changes?" : "Redo Changes?"}
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                {confirmAction === "rollback"
                  ? "This will restore files to their previous state."
                  : "This will reapply the changes that were previously undone."}
              </p>
              {previewResult && (
                <div className="mt-2 p-2 bg-muted rounded text-sm">
                  <p className="font-medium mb-1">Files affected:</p>
                  <ul className="list-disc list-inside text-xs">
                    {previewResult.filesRestored.slice(0, 5).map((f) => (
                      <li key={f} className="flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        <span className="truncate">{f.split("/").pop()}</span>
                      </li>
                    ))}
                    {previewResult.filesRestored.length > 5 && (
                      <li className="text-muted-foreground">
                        +{previewResult.filesRestored.length - 5} more files
                      </li>
                    )}
                  </ul>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                This action can be {confirmAction === "rollback" ? "redone" : "undone"} later.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirm}
              className={
                confirmAction === "rollback"
                  ? "bg-orange-600 hover:bg-orange-700"
                  : ""
              }
            >
              {isRollingBack ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : confirmAction === "rollback" ? (
                <Undo2 className="h-4 w-4 mr-1" />
              ) : (
                <Redo2 className="h-4 w-4 mr-1" />
              )}
              {confirmAction === "rollback" ? "Undo Changes" : "Redo Changes"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// Simpler inline version for step items
export function StepRollbackButton({
  planId,
  stepId,
  className,
}: {
  planId: string;
  stepId: string;
  className?: string;
}) {
  return (
    <RollbackControls
      planId={planId}
      stepId={stepId}
      className={className}
      compact
    />
  );
}
