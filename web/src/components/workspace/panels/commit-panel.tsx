"use client";

import { useState, useEffect, useCallback } from "react";
import { useWorkspaceStore, GitStatus } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { workspaceApi, ApiError } from "@/lib/api";
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
  Undo2,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
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

interface HookFailure {
  hook_name: string;
  error_output: string;
  files_affected: string[];
}

interface HookFailureInfo {
  message: string;
  hook_failed: boolean;
  hook_failures: HookFailure[];
  raw_error: string;
  files_to_fix: string[];
}

export function CommitPanel() {
  const { token } = useAuthStore();
  const { activeProjectId, gitStatus, setGitStatus } = useWorkspaceStore();
  const { createConversation, selectConversation, setPrefillMessage } = useChatStore();
  const { toast } = useToast();

  const [commitMessage, setCommitMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [stagedOpen, setStagedOpen] = useState(true);
  const [unstagedOpen, setUnstagedOpen] = useState(true);
  const [untrackedOpen, setUntrackedOpen] = useState(true);

  // Hook failure state
  const [hookFailure, setHookFailure] = useState<HookFailureInfo | null>(null);
  const [isStartingFixChat, setIsStartingFixChat] = useState(false);

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

    // Clear any previous hook failure
    setHookFailure(null);
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

      // Check if this is a hook failure
      if (err instanceof ApiError && err.status === 422 && err.details) {
        const details = err.details as HookFailureInfo;
        if (details.hook_failed) {
          setHookFailure(details);
          toast({
            title: "Pre-commit hooks failed",
            description: "Linting or formatting errors detected. Fix them or ask AI to help.",
            variant: "destructive",
          });
          return;
        }
      }

      toast({
        title: "Commit failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsCommitting(false);
    }
  };

  const handleFixWithAI = async () => {
    if (!hookFailure || !activeProjectId || !token) return;

    setIsStartingFixChat(true);
    try {
      // Build the error context message
      const errorContext = hookFailure.hook_failures
        .map((hf) => `### ${hf.hook_name} errors:\n\`\`\`\n${hf.error_output.slice(0, 1500)}\n\`\`\``)
        .join("\n\n");

      const filesToFix = hookFailure.files_to_fix.length > 0
        ? `\n\nFiles to fix:\n${hookFailure.files_to_fix.map((f) => `- ${f}`).join("\n")}`
        : "";

      const message = `I tried to commit but the pre-commit hooks failed with linting/formatting errors. Please fix these errors so I can commit.\n\n${errorContext}${filesToFix}`;

      // Create a new conversation with the error context
      const conversation = await createConversation(token, activeProjectId, "Fix lint errors");
      if (conversation?.id) {
        // Select the conversation to make it current
        await selectConversation(token, conversation.id);
        // Set the prefill message so the chat input picks it up
        setPrefillMessage(message);
        // Clear the hook failure state
        setHookFailure(null);
        toast({
          title: "Started fix conversation",
          description: "Click send to have AI analyze the errors",
        });
      }
    } catch (err) {
      console.error("Failed to start fix chat:", err);
      toast({
        title: "Failed to start chat",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsStartingFixChat(false);
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

  const handleRevertAll = async () => {
    if (!token || !activeProjectId) return;

    setIsReverting(true);
    try {
      const result = await workspaceApi.gitRevertFiles(token, activeProjectId);
      toast({
        title: "Changes reverted",
        description: `${result.reverted_files} file(s) restored to last commit`,
      });
      await refreshStatus();
    } catch (err) {
      console.error("Revert failed:", err);
      toast({
        title: "Revert failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsReverting(false);
    }
  };

  const handleGenerateMessage = async () => {
    if (!token || !activeProjectId) return;

    setIsGenerating(true);
    try {
      const result = await workspaceApi.generateCommitMessage(token, activeProjectId);
      setCommitMessage(result.full_message);
      toast({
        title: "Commit message generated",
        description: result.title.slice(0, 50) + (result.title.length > 50 ? "..." : ""),
      });
    } catch (err) {
      console.error("Generate message failed:", err);
      toast({
        title: "Failed to generate message",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsGenerating(false);
    }
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
            <div className="relative">
              <Textarea
                placeholder="Commit message..."
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                className="min-h-[60px] text-sm resize-none pr-10"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    handleCommit();
                  }
                }}
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1 h-7 w-7 text-muted-foreground hover:text-primary"
                onClick={handleGenerateMessage}
                disabled={isGenerating || totalChanges === 0}
                title="Generate commit message with AI"
              >
                {isGenerating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
              </Button>
            </div>
            {/* Hook failure alert */}
            {hookFailure && (
              <div className="mb-2 p-3 bg-destructive/10 border border-destructive/30 rounded-md">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-destructive">Pre-commit hooks failed</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {hookFailure.hook_failures.length} hook(s) failed
                        {hookFailure.files_to_fix.length > 0 && ` • ${hookFailure.files_to_fix.length} file(s) need fixes`}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 flex-shrink-0"
                    onClick={() => setHookFailure(null)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="default"
                    className="flex-1"
                    onClick={handleFixWithAI}
                    disabled={isStartingFixChat}
                  >
                    {isStartingFixChat ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <Wand2 className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    Fix with AI
                  </Button>
                </div>
                {hookFailure.files_to_fix.length > 0 && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    <details>
                      <summary className="cursor-pointer hover:text-foreground">
                        Show affected files ({hookFailure.files_to_fix.length})
                      </summary>
                      <ul className="mt-1 space-y-0.5 pl-2">
                        {hookFailure.files_to_fix.slice(0, 10).map((file) => (
                          <li key={file} className="truncate">{file}</li>
                        ))}
                        {hookFailure.files_to_fix.length > 10 && (
                          <li className="text-muted-foreground">
                            ...and {hookFailure.files_to_fix.length - 10} more
                          </li>
                        )}
                      </ul>
                    </details>
                  </div>
                )}
              </div>
            )}

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
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={modifiedCount === 0 || isReverting}
                    className="text-destructive hover:text-destructive"
                  >
                    {isReverting ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    ) : (
                      <Undo2 className="h-3.5 w-3.5 mr-1" />
                    )}
                    Revert
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Revert all changes?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will discard all {modifiedCount} modified file(s) and restore them to their last committed state. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleRevertAll}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Revert All
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
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
