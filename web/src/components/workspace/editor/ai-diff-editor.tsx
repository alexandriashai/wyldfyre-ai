"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  X,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  FileCode,
  ExternalLink,
  Copy,
  CheckCircle2,
} from "lucide-react";

const DiffEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.DiffEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    ),
  }
);

export interface AIFileChange {
  id: string;
  path: string;
  before: string;
  after: string;
  language?: string;
  summary?: string;
  stepId?: string;
}

interface AIDiffEditorProps {
  changes: AIFileChange[];
  onAccept: (changeId: string) => void;
  onReject: (changeId: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
  onOpenInEditor?: (path: string) => void;
  onClose: () => void;
  className?: string;
}

export function AIDiffEditor({
  changes,
  onAccept,
  onReject,
  onAcceptAll,
  onRejectAll,
  onOpenInEditor,
  onClose,
  className,
}: AIDiffEditorProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  // Theme detection
  const [editorTheme, setEditorTheme] = useState("vs-dark");
  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setEditorTheme(isDark ? "vs-dark" : "vs");
    const observer = new MutationObserver(() => {
      setEditorTheme(document.documentElement.classList.contains("dark") ? "vs-dark" : "vs");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const currentChange = changes[currentIndex];

  const handleAccept = useCallback(() => {
    if (!currentChange) return;
    setAcceptedIds((prev) => new Set(prev).add(currentChange.id));
    onAccept(currentChange.id);
    // Auto-advance to next unprocessed change
    if (currentIndex < changes.length - 1) {
      setCurrentIndex((i) => i + 1);
    }
  }, [currentChange, currentIndex, changes.length, onAccept]);

  const handleReject = useCallback(() => {
    if (!currentChange) return;
    setRejectedIds((prev) => new Set(prev).add(currentChange.id));
    onReject(currentChange.id);
    // Auto-advance to next unprocessed change
    if (currentIndex < changes.length - 1) {
      setCurrentIndex((i) => i + 1);
    }
  }, [currentChange, currentIndex, changes.length, onReject]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" && currentIndex > 0) {
        setCurrentIndex((i) => i - 1);
      } else if (e.key === "ArrowRight" && currentIndex < changes.length - 1) {
        setCurrentIndex((i) => i + 1);
      } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        handleAccept();
      } else if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, changes.length, onClose, handleAccept]);

  const handleCopy = async () => {
    if (!currentChange) return;
    await navigator.clipboard.writeText(currentChange.after);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (changes.length === 0) return null;

  const pendingCount = changes.filter(
    (c) => !acceptedIds.has(c.id) && !rejectedIds.has(c.id)
  ).length;

  const fileName = currentChange?.path.split("/").pop() || "";
  const isProcessed = acceptedIds.has(currentChange?.id) || rejectedIds.has(currentChange?.id);
  const isAccepted = acceptedIds.has(currentChange?.id);
  const isRejected = rejectedIds.has(currentChange?.id);

  return (
    <div className={cn("flex flex-col h-full bg-background border-l", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-gradient-to-r from-purple-500/5 to-blue-500/5 shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-purple-500" />
          <span className="text-sm font-medium">AI Changes Preview</span>
          <Badge variant="secondary" className="text-[10px] h-5">
            {pendingCount} pending
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-green-600 hover:text-green-700 hover:bg-green-500/10"
            onClick={onAcceptAll}
            disabled={pendingCount === 0}
          >
            <Check className="h-3.5 w-3.5 mr-1" />
            Accept All
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-red-600 hover:text-red-700 hover:bg-red-500/10"
            onClick={onRejectAll}
            disabled={pendingCount === 0}
          >
            <X className="h-3.5 w-3.5 mr-1" />
            Reject All
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 ml-2"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* File Navigation */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-muted/30 shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
          disabled={currentIndex === 0}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <FileCode className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium truncate" title={currentChange?.path}>
            {fileName}
          </span>
          {isAccepted && (
            <Badge variant="outline" className="h-4 px-1.5 text-[9px] text-green-500 border-green-500/30">
              Accepted
            </Badge>
          )}
          {isRejected && (
            <Badge variant="outline" className="h-4 px-1.5 text-[9px] text-red-500 border-red-500/30">
              Rejected
            </Badge>
          )}
          <span className="text-[10px] text-muted-foreground ml-auto shrink-0">
            {currentIndex + 1} / {changes.length}
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setCurrentIndex((i) => Math.min(changes.length - 1, i + 1))}
          disabled={currentIndex === changes.length - 1}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Summary */}
      {currentChange?.summary && (
        <div className="px-3 py-2 border-b bg-muted/20 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">Summary: </span>
          {currentChange.summary}
        </div>
      )}

      {/* Diff Editor */}
      <div className="flex-1 min-h-0">
        <DiffEditor
          original={currentChange?.before || ""}
          modified={currentChange?.after || ""}
          language={currentChange?.language}
          theme={editorTheme}
          options={{
            readOnly: true,
            renderSideBySide: true,
            minimap: { enabled: false },
            fontSize: 13,
            scrollBeyondLastLine: false,
            originalEditable: false,
            enableSplitViewResizing: true,
          }}
        />
      </div>

      {/* File indicator bar */}
      <div className="flex gap-1 px-3 py-1.5 border-t bg-muted/30 overflow-x-auto shrink-0">
        {changes.map((change, i) => (
          <button
            key={change.id}
            onClick={() => setCurrentIndex(i)}
            className={cn(
              "w-2 h-2 rounded-full shrink-0 transition-all",
              i === currentIndex && "ring-2 ring-offset-1 ring-primary",
              acceptedIds.has(change.id) && "bg-green-500",
              rejectedIds.has(change.id) && "bg-red-500",
              !acceptedIds.has(change.id) && !rejectedIds.has(change.id) && "bg-muted-foreground/40"
            )}
            title={change.path.split("/").pop()}
          />
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-3 py-2 border-t bg-card shrink-0">
        <Button
          variant="outline"
          size="sm"
          className="h-8"
          onClick={handleCopy}
        >
          {copied ? (
            <CheckCircle2 className="h-3.5 w-3.5 mr-1.5 text-green-500" />
          ) : (
            <Copy className="h-3.5 w-3.5 mr-1.5" />
          )}
          {copied ? "Copied" : "Copy"}
        </Button>
        {onOpenInEditor && (
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => onOpenInEditor(currentChange.path)}
          >
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            Open in Editor
          </Button>
        )}
        <div className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-red-600 border-red-500/30 hover:bg-red-500/10"
          onClick={handleReject}
          disabled={isProcessed}
        >
          <X className="h-3.5 w-3.5 mr-1.5" />
          Reject
        </Button>
        <Button
          size="sm"
          className="h-8 bg-green-600 hover:bg-green-700"
          onClick={handleAccept}
          disabled={isProcessed}
        >
          <Check className="h-3.5 w-3.5 mr-1.5" />
          Accept
        </Button>
      </div>
    </div>
  );
}

// Compact notification for when changes are available
export function AIChangesNotification({
  count,
  onClick,
}: {
  count: number;
  onClick: () => void;
}) {
  if (count === 0) return null;

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 bg-purple-500/10 hover:bg-purple-500/20 border-b transition-colors"
    >
      <Sparkles className="h-4 w-4 text-purple-500" />
      <span className="text-sm font-medium">
        {count} AI change{count !== 1 ? "s" : ""} pending review
      </span>
      <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto" />
    </button>
  );
}
