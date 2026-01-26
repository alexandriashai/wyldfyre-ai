"use client";

import { useState, useEffect, useCallback } from "react";
import { useWorkspaceStore, GitStatus } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { workspaceApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  Plus,
  Minus,
  GitCommit,
  RefreshCw,
  FileCode,
  FilePlus,
  FileX,
  FileQuestion,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Check,
  Square,
} from "lucide-react";
import { useToast } from "@/hooks/useToast";

interface FileItemProps {
  path: string;
  status: string;
  isStaged: boolean;
  isSelected: boolean;
  onToggleSelect: () => void;
  onStage?: () => void;
  onUnstage?: () => void;
}

function getStatusIcon(status: string) {
  switch (status) {
    case "M":
    case "modified":
      return <FileCode className="h-3.5 w-3.5 text-amber-500" />;
    case "A":
    case "added":
      return <FilePlus className="h-3.5 w-3.5 text-green-500" />;
    case "D":
    case "deleted":
      return <FileX className="h-3.5 w-3.5 text-red-500" />;
    case "?":
    case "untracked":
      return <FileQuestion className="h-3.5 w-3.5 text-muted-foreground" />;
    default:
      return <FileCode className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "M":
    case "modified":
      return <Badge variant="outline" className="text-[10px] px-1 py-0 text-amber-500 border-amber-500/50">M</Badge>;
    case "A":
    case "added":
      return <Badge variant="outline" className="text-[10px] px-1 py-0 text-green-500 border-green-500/50">A</Badge>;
    case "D":
    case "deleted":
      return <Badge variant="outline" className="text-[10px] px-1 py-0 text-red-500 border-red-500/50">D</Badge>;
    case "R":
    case "renamed":
      return <Badge variant="outline" className="text-[10px] px-1 py-0 text-blue-500 border-blue-500/50">R</Badge>;
    default:
      return <Badge variant="outline" className="text-[10px] px-1 py-0">?</Badge>;
  }
}

function FileItem({ path, status, isStaged, isSelected, onToggleSelect, onStage, onUnstage }: FileItemProps) {
  const fileName = path.split("/").pop() || path;
  const dirPath = path.includes("/") ? path.substring(0, path.lastIndexOf("/")) : "";

  return (
    <div className="flex items-center gap-2 py-2 sm:py-1.5 px-2 hover:bg-muted/50 active:bg-muted rounded-md group touch-manipulation">
      {/* Larger touch target for checkbox on mobile */}
      <button
        onClick={onToggleSelect}
        className="h-5 w-5 sm:h-4 sm:w-4 shrink-0 flex items-center justify-center rounded border border-muted-foreground/40 hover:border-primary active:border-primary transition-colors"
      >
        {isSelected && <Check className="h-3 w-3 sm:h-2.5 sm:w-2.5 text-primary" />}
      </button>
      {getStatusIcon(status)}
      <div className="flex-1 min-w-0 flex items-center gap-1.5">
        <span className="text-sm sm:text-xs truncate">{fileName}</span>
        {dirPath && (
          <span className="text-xs sm:text-[10px] text-muted-foreground truncate hidden sm:inline">{dirPath}</span>
        )}
      </div>
      {getStatusBadge(status)}
      {isStaged && onUnstage && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 sm:h-5 sm:w-5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            onUnstage();
          }}
          title="Unstage"
        >
          <Minus className="h-4 w-4 sm:h-3 sm:w-3" />
        </Button>
      )}
      {!isStaged && onStage && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 sm:h-5 sm:w-5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            onStage();
          }}
          title="Stage"
        >
          <Plus className="h-4 w-4 sm:h-3 sm:w-3" />
        </Button>
      )}
    </div>
  );
}

export function CommitPanel() {
  const { token } = useAuthStore();
  const { activeProjectId, gitStatus, setGitStatus } = useWorkspaceStore();
  const { toast } = useToast();

  const [commitMessage, setCommitMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [stagedOpen, setStagedOpen] = useState(true);
  const [unstagedOpen, setUnstagedOpen] = useState(true);
  const [untrackedOpen, setUntrackedOpen] = useState(true);

  // Selection state for batch operations
  const [selectedStaged, setSelectedStaged] = useState<Set<string>>(new Set());
  const [selectedUnstaged, setSelectedUnstaged] = useState<Set<string>>(new Set());
  const [selectedUntracked, setSelectedUntracked] = useState<Set<string>>(new Set());

  // Files to commit (staged by default, or selected from unstaged/untracked)
  const [filesToCommit, setFilesToCommit] = useState<string[]>([]);

  const refreshStatus = useCallback(async () => {
    if (!token || !activeProjectId) return;

    setIsLoading(true);
    try {
      const status = await workspaceApi.getGitStatus(token, activeProjectId);
      setGitStatus(status);
    } catch (err) {
      console.error("Failed to refresh git status:", err);
      toast({ title: "Failed to refresh git status", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [token, activeProjectId, setGitStatus]);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // Update files to commit when selection changes
  useEffect(() => {
    const files: string[] = [];

    // Add all staged files
    gitStatus?.staged?.forEach((f) => files.push(f.path));

    // Add selected unstaged files
    selectedUnstaged.forEach((path) => files.push(path));

    // Add selected untracked files
    selectedUntracked.forEach((path) => files.push(path));

    setFilesToCommit(files);
  }, [gitStatus, selectedUnstaged, selectedUntracked]);

  const handleCommit = async () => {
    if (!token || !activeProjectId || !commitMessage.trim()) {
      toast({ title: "Please enter a commit message", variant: "destructive" });
      return;
    }

    if (filesToCommit.length === 0) {
      toast({ title: "No files to commit", variant: "destructive" });
      return;
    }

    setIsCommitting(true);
    try {
      const result = await workspaceApi.gitCommit(
        token,
        activeProjectId,
        commitMessage.trim(),
        filesToCommit
      );

      toast({
        title: `Committed ${result.files_changed} file(s)`,
        description: result.commit_hash?.slice(0, 7),
      });

      setCommitMessage("");
      setSelectedUnstaged(new Set());
      setSelectedUntracked(new Set());
      await refreshStatus();
    } catch (err) {
      console.error("Commit failed:", err);
      toast({
        title: "Commit failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsCommitting(false);
    }
  };

  const handleStageAll = () => {
    const allUnstaged = new Set<string>();
    gitStatus?.modified?.forEach((f) => allUnstaged.add(f.path));
    setSelectedUnstaged(allUnstaged);

    const allUntracked = new Set<string>();
    gitStatus?.untracked?.forEach((path) => allUntracked.add(path));
    setSelectedUntracked(allUntracked);
  };

  const handleUnstageAll = () => {
    setSelectedUnstaged(new Set());
    setSelectedUntracked(new Set());
  };

  const toggleSelectUnstaged = (path: string) => {
    setSelectedUnstaged((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const toggleSelectUntracked = (path: string) => {
    setSelectedUntracked((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  if (!activeProjectId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4">
        <GitCommit className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">Select a project to manage commits</p>
      </div>
    );
  }

  const stagedCount = gitStatus?.staged?.length || 0;
  const modifiedCount = gitStatus?.modified?.length || 0;
  const untrackedCount = gitStatus?.untracked?.length || 0;
  const totalChanges = stagedCount + modifiedCount + untrackedCount;

  const isClean = gitStatus?.is_clean && totalChanges === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2">
          <GitCommit className="h-4 w-4" />
          <span className="font-medium text-sm">Source Control</span>
          {totalChanges > 0 && (
            <Badge variant="secondary" className="text-xs">
              {totalChanges}
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={refreshStatus}
          disabled={isLoading}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
        </Button>
      </div>

      {isClean ? (
        <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground p-4">
          <CheckCircle2 className="h-8 w-8 mb-2 text-green-500 opacity-70" />
          <p className="text-sm">No changes to commit</p>
          <p className="text-xs mt-1">Working tree clean</p>
        </div>
      ) : (
        <>
          {/* Commit message input */}
          <div className="p-3 border-b">
            <Textarea
              placeholder="Commit message..."
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              className="min-h-[60px] text-sm resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  handleCommit();
                }
              }}
            />
            <div className="flex items-center gap-2 mt-2">
              <Button
                size="sm"
                className="flex-1"
                onClick={handleCommit}
                disabled={isCommitting || !commitMessage.trim() || filesToCommit.length === 0}
              >
                {isCommitting ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <GitCommit className="h-3.5 w-3.5 mr-1.5" />
                )}
                Commit ({filesToCommit.length})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleStageAll}
                disabled={modifiedCount + untrackedCount === 0}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                All
              </Button>
            </div>
          </div>

          {/* File lists */}
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {/* Staged Changes */}
              {stagedCount > 0 && (
                <Collapsible open={stagedOpen} onOpenChange={setStagedOpen}>
                  <CollapsibleTrigger className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-muted/50 rounded-md text-sm font-medium">
                    {stagedOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <span className="text-green-600">Staged Changes</span>
                    <Badge variant="secondary" className="text-xs ml-auto">
                      {stagedCount}
                    </Badge>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-1">
                    {gitStatus?.staged?.map((file) => (
                      <FileItem
                        key={file.path}
                        path={file.path}
                        status={file.status}
                        isStaged={true}
                        isSelected={true}
                        onToggleSelect={() => {}}
                      />
                    ))}
                  </CollapsibleContent>
                </Collapsible>
              )}

              {/* Modified (Unstaged) */}
              {modifiedCount > 0 && (
                <Collapsible open={unstagedOpen} onOpenChange={setUnstagedOpen}>
                  <CollapsibleTrigger className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-muted/50 rounded-md text-sm font-medium">
                    {unstagedOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <span className="text-amber-600">Changes</span>
                    <Badge variant="secondary" className="text-xs ml-auto">
                      {modifiedCount}
                    </Badge>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-1">
                    {gitStatus?.modified?.map((file) => (
                      <FileItem
                        key={file.path}
                        path={file.path}
                        status={file.status}
                        isStaged={false}
                        isSelected={selectedUnstaged.has(file.path)}
                        onToggleSelect={() => toggleSelectUnstaged(file.path)}
                        onStage={() => {
                          setSelectedUnstaged((prev) => new Set(prev).add(file.path));
                        }}
                      />
                    ))}
                  </CollapsibleContent>
                </Collapsible>
              )}

              {/* Untracked */}
              {untrackedCount > 0 && (
                <Collapsible open={untrackedOpen} onOpenChange={setUntrackedOpen}>
                  <CollapsibleTrigger className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-muted/50 rounded-md text-sm font-medium">
                    {untrackedOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <span className="text-muted-foreground">Untracked</span>
                    <Badge variant="secondary" className="text-xs ml-auto">
                      {untrackedCount}
                    </Badge>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-1">
                    {gitStatus?.untracked?.map((path) => (
                      <FileItem
                        key={path}
                        path={path}
                        status="?"
                        isStaged={false}
                        isSelected={selectedUntracked.has(path)}
                        onToggleSelect={() => toggleSelectUntracked(path)}
                        onStage={() => {
                          setSelectedUntracked((prev) => new Set(prev).add(path));
                        }}
                      />
                    ))}
                  </CollapsibleContent>
                </Collapsible>
              )}
            </div>
          </ScrollArea>
        </>
      )}

      {/* Branch info footer */}
      {gitStatus && (
        <div className="flex items-center justify-between px-3 py-2 border-t text-xs text-muted-foreground bg-muted/30">
          <div className="flex items-center gap-1.5">
            <span className="font-medium">{gitStatus.branch || "detached"}</span>
            {gitStatus.has_remote && (
              <>
                {gitStatus.ahead > 0 && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0">
                    ↑{gitStatus.ahead}
                  </Badge>
                )}
                {gitStatus.behind > 0 && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0">
                    ↓{gitStatus.behind}
                  </Badge>
                )}
              </>
            )}
          </div>
          {!gitStatus.has_remote && (
            <span className="text-amber-500">No remote</span>
          )}
        </div>
      )}
    </div>
  );
}
