"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";
import { FileTreePanel } from "./panels/file-tree-panel";
import { EditorPanel } from "./panels/editor-panel";
import { PreviewPanel } from "./preview/preview-panel";
import { WorkspaceChatPanel } from "./chat-panel";
import { cn } from "@/lib/utils";
import { Files, Code2, Monitor, MessageSquare } from "lucide-react";

interface MobileWorkspaceProps {
  onFileOpen: (path: string) => void;
  onRefresh: () => void;
  onSave: () => void;
}

const tabs = [
  { id: "files" as const, icon: Files, label: "Files" },
  { id: "editor" as const, icon: Code2, label: "Editor" },
  { id: "preview" as const, icon: Monitor, label: "Preview" },
  { id: "chat" as const, icon: MessageSquare, label: "Chat" },
];

export function MobileWorkspace({ onFileOpen, onRefresh, onSave }: MobileWorkspaceProps) {
  const { mobileActiveTab, setMobileActiveTab, openFiles } = useWorkspaceStore();

  return (
    <div className="flex flex-col h-full w-full">
      {/* Active panel (full screen) */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {mobileActiveTab === "files" && (
          <FileTreePanel onFileOpen={onFileOpen} onRefresh={onRefresh} />
        )}
        {mobileActiveTab === "editor" && (
          <EditorPanel onSave={onSave} />
        )}
        {mobileActiveTab === "preview" && (
          <PreviewPanel />
        )}
        {mobileActiveTab === "chat" && (
          <WorkspaceChatPanel />
        )}
      </div>

      {/* Bottom tab bar */}
      <div className="flex items-center border-t bg-card shrink-0 safe-area-bottom">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = mobileActiveTab === tab.id;
          const hasIndicator = tab.id === "editor" && openFiles.some((f) => f.isDirty);

          return (
            <button
              key={tab.id}
              onClick={() => setMobileActiveTab(tab.id)}
              className={cn(
                "flex-1 flex flex-col items-center gap-0.5 py-2 relative",
                isActive ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px]">{tab.label}</span>
              {hasIndicator && (
                <span className="absolute top-1.5 right-1/3 h-1.5 w-1.5 rounded-full bg-amber-500" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
