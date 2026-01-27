"use client";

import { useState, useEffect, useCallback } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { workspaceApi, GitLogEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  GitCommit,
  RefreshCw,
  Copy,
  ExternalLink,
  ChevronDown,
  User,
  Calendar,
  FileText,
  Loader2,
} from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { formatDistanceToNow } from "date-fns";

interface CommitItemProps {
  entry: GitLogEntry;
  isFirst?: boolean;
  isLast?: boolean;
}

function CommitItem({ entry, isFirst, isLast }: CommitItemProps) {
  const [expanded, setExpanded] = useState(false);
  const { toast } = useToast();

  const copyHash = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(entry.hash);
    toast({ title: "Commit hash copied" });
  };

  const formattedDate = (() => {
    try {
      if (!entry.date) return "unknown";
      const date = new Date(entry.date);
      // Check if date is valid
      if (isNaN(date.getTime())) return "unknown";
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return "unknown";
    }
  })();

  // Split message into subject and body
  const [subject, ...bodyLines] = entry.message.split("\n");
  const body = bodyLines.filter((l) => l.trim()).join("\n");

  return (
    <div className="relative">
      {/* Timeline connector */}
      <div className="absolute left-[11px] top-0 bottom-0 w-px bg-border">
        {isFirst && <div className="absolute top-0 h-4 w-px bg-background" />}
        {isLast && <div className="absolute bottom-0 h-4 w-px bg-background" />}
      </div>

      {/* Commit node - larger touch target on mobile */}
      <div
        className={cn(
          "relative pl-8 pr-3 py-3 sm:py-2 hover:bg-muted/50 active:bg-muted transition-colors cursor-pointer touch-manipulation",
          expanded && "bg-muted/30"
        )}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Commit dot */}
        <div className="absolute left-[7px] top-4 sm:top-3 w-[9px] h-[9px] rounded-full bg-primary border-2 border-background" />

        {/* Content */}
        <div className="flex flex-col gap-1.5 sm:gap-1">
          {/* Subject line */}
          <div className="flex items-start gap-2">
            <p className="text-sm flex-1 line-clamp-2">{subject}</p>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 sm:h-5 sm:w-5 shrink-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 hover:opacity-100"
                  onClick={copyHash}
                >
                  <Copy className="h-4 w-4 sm:h-3 sm:w-3" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy hash</TooltipContent>
            </Tooltip>
          </div>

          {/* Metadata line - wrap on mobile */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
            <span className="font-mono text-primary">{entry.short_hash}</span>
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              <span className="truncate max-w-[100px] sm:max-w-none">{entry.author}</span>
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {formattedDate}
            </span>
            {entry.files_changed !== null && entry.files_changed > 0 && (
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                {entry.files_changed}
              </span>
            )}
          </div>

          {/* Expanded body */}
          {expanded && body && (
            <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground whitespace-pre-wrap font-mono overflow-x-auto">
              {body}
            </div>
          )}
        </div>

        {/* Expand indicator */}
        {body && (
          <ChevronDown
            className={cn(
              "absolute right-3 top-4 sm:top-3 h-4 w-4 sm:h-3.5 sm:w-3.5 text-muted-foreground transition-transform",
              expanded && "rotate-180"
            )}
          />
        )}
      </div>
    </div>
  );
}

export function HistoryPanel() {
  const { token } = useAuthStore();
  const { activeProjectId, gitStatus } = useWorkspaceStore();
  const { toast } = useToast();

  const [entries, setEntries] = useState<GitLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [limit, setLimit] = useState(20);

  const loadHistory = useCallback(async (loadLimit: number = limit) => {
    if (!token || !activeProjectId) return;

    setIsLoading(true);
    try {
      const result = await workspaceApi.getGitLog(token, activeProjectId, loadLimit);
      setEntries(result.entries || []);
    } catch (err) {
      console.error("Failed to load git history:", err);
      toast({ title: "Failed to load git history", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [token, activeProjectId, limit, toast]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const loadMore = () => {
    const newLimit = limit + 20;
    setLimit(newLimit);
    loadHistory(newLimit);
  };

  if (!activeProjectId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4">
        <GitCommit className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">Select a project to view history</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2">
          <GitCommit className="h-4 w-4" />
          <span className="font-medium text-sm">Commit History</span>
          {gitStatus?.branch && (
            <Badge variant="outline" className="text-xs">
              {gitStatus.branch}
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => loadHistory()}
          disabled={isLoading}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
        </Button>
      </div>

      {/* Commit list */}
      {isLoading && entries.length === 0 ? (
        <div className="flex items-center justify-center flex-1">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground p-4">
          <GitCommit className="h-8 w-8 mb-2 opacity-50" />
          <p className="text-sm">No commits yet</p>
        </div>
      ) : (
        <ScrollArea className="flex-1">
          <div className="py-2">
            {entries.map((entry, idx) => (
              <CommitItem
                key={entry.hash}
                entry={entry}
                isFirst={idx === 0}
                isLast={idx === entries.length - 1}
              />
            ))}

            {/* Load more button */}
            {entries.length >= limit && (
              <div className="px-3 py-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={loadMore}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  Load more
                </Button>
              </div>
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
