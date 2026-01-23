"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";
import { PreviewPanel } from "../preview/preview-panel";
import { WorkspaceChatPanel } from "../chat-panel";
import { Button } from "@/components/ui/button";
import { Monitor, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

export function RightPanel() {
  const { rightPanelMode, setRightPanelMode } = useWorkspaceStore();

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Panel tabs */}
      <div className="flex items-center border-b shrink-0">
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            "h-8 rounded-none border-b-2 text-xs gap-1.5",
            rightPanelMode === "preview"
              ? "border-b-primary text-primary"
              : "border-b-transparent text-muted-foreground"
          )}
          onClick={() => setRightPanelMode("preview")}
        >
          <Monitor className="h-3.5 w-3.5" />
          Preview
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            "h-8 rounded-none border-b-2 text-xs gap-1.5",
            rightPanelMode === "chat"
              ? "border-b-primary text-primary"
              : "border-b-transparent text-muted-foreground"
          )}
          onClick={() => setRightPanelMode("chat")}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Chat
        </Button>
      </div>

      {/* Panel content */}
      <div className="flex-1 min-h-0">
        {rightPanelMode === "preview" ? <PreviewPanel /> : <WorkspaceChatPanel />}
      </div>
    </div>
  );
}
