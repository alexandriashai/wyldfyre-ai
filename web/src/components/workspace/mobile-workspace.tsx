"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";
import { useBrowserStore } from "@/stores/browser-store";
import { FileTreePanel } from "./panels/file-tree-panel";
import { EditorPanel } from "./panels/editor-panel";
import { PreviewPanel } from "./preview/preview-panel";
import { WorkspaceChatPanel } from "./chat-panel";
import { TerminalPanel } from "./panels/terminal-panel";
import { GitPanel } from "./panels/git-panel";
import { ChatBrowserPanel } from "@/components/chat/chat-browser-panel";
import { cn } from "@/lib/utils";
import { Files, Code2, Monitor, MessageSquare, Terminal, GitBranch, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface MobileWorkspaceProps {
  onFileOpen: (path: string) => void;
  onRefresh: () => void;
  onSave: () => void;
}

const tabs = [
  { id: "files" as const, icon: Files, label: "Files" },
  { id: "editor" as const, icon: Code2, label: "Editor" },
  { id: "git" as const, icon: GitBranch, label: "Git" },
  { id: "terminal" as const, icon: Terminal, label: "Term" },
  { id: "browser" as const, icon: Globe, label: "Debug" },
  { id: "chat" as const, icon: MessageSquare, label: "Chat" },
];

export function MobileWorkspace({ onFileOpen, onRefresh, onSave }: MobileWorkspaceProps) {
  const { mobileActiveTab, setMobileActiveTab, openFiles, gitStatus, activeProjectId } = useWorkspaceStore();
  const { isConnected: isBrowserConnected } = useBrowserStore();

  // Calculate git change count for indicator
  const gitChangeCount = (gitStatus?.staged?.length || 0) +
    (gitStatus?.modified?.length || 0) +
    (gitStatus?.untracked?.length || 0);

  return (
    <div className="flex flex-col h-full w-full">
      {/* Active panel (full screen) */}
      <div className="flex-1 min-h-0 overflow-hidden relative">
        {mobileActiveTab === "files" && (
          <FileTreePanel onFileOpen={onFileOpen} onRefresh={onRefresh} />
        )}
        {mobileActiveTab === "editor" && (
          <EditorPanel onSave={onSave} />
        )}
        {mobileActiveTab === "git" && (
          activeProjectId ? (
            <GitPanel />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a project to manage git
            </div>
          )
        )}
        {mobileActiveTab === "terminal" && (
          <TerminalPanel alwaysShow isMobileView />
        )}
        {mobileActiveTab === "browser" && (
          <ChatBrowserPanel />
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
          const hasEditorIndicator = tab.id === "editor" && openFiles.some((f) => f.isDirty);
          const hasGitIndicator = tab.id === "git" && gitChangeCount > 0;
          const hasBrowserIndicator = tab.id === "browser" && isBrowserConnected;

          return (
            <button
              key={tab.id}
              onClick={() => setMobileActiveTab(tab.id)}
              className={cn(
                "flex-1 flex flex-col items-center gap-0.5 py-2 relative",
                isActive ? "text-primary" : "text-muted-foreground"
              )}
            >
              <div className="relative">
                <Icon className="h-5 w-5" />
                {hasGitIndicator && (
                  <span className="absolute -top-1 -right-2 min-w-[14px] h-[14px] rounded-full bg-primary text-[9px] text-primary-foreground flex items-center justify-center px-0.5">
                    {gitChangeCount > 99 ? "99+" : gitChangeCount}
                  </span>
                )}
              </div>
              <span className="text-[10px]">{tab.label}</span>
              {hasEditorIndicator && (
                <span className="absolute top-1.5 right-1/3 h-1.5 w-1.5 rounded-full bg-amber-500" />
              )}
              {hasBrowserIndicator && (
                <span className="absolute top-1.5 right-1/3 h-1.5 w-1.5 rounded-full bg-green-500" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
