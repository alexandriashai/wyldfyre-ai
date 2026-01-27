"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { cn, getAgentColor, getAgentBgColor, formatDate } from "@/lib/utils";
import { useChatStore, MessageStatus } from "@/stores/chat-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Bot, User, Check, X, RefreshCw, Loader2, AlertCircle, WifiOff, Lightbulb } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { SynthesizeModal } from "./synthesize-modal";
import { MarkdownRenderer, StreamingMarkdown } from "./markdown-renderer";

interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  agent?: string;
  created_at: string;
  isStreaming?: boolean;
  status?: MessageStatus;
}

// Check if message contains a pending plan that needs approval
function isPendingPlanMessage(content: string): boolean {
  return (
    (content.includes("## Plan:") || content.includes("## Plan:")) &&
    (content.includes("/plan approve") || content.includes("Status:** Pending"))
  );
}

function PlanActionButtons({ onApprove, onReject }: { onApprove: () => void; onReject: () => void }) {
  return (
    <div className="flex gap-2 mt-3 pt-3 border-t border-border">
      <Button
        size="sm"
        variant="default"
        onClick={onApprove}
        className="flex-1 bg-green-600 hover:bg-green-700 h-9"
      >
        <Check className="h-4 w-4 mr-1" />
        <span className="hidden sm:inline">Approve</span>
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={onReject}
        className="flex-1 text-destructive hover:text-destructive h-9"
      >
        <X className="h-4 w-4 mr-1" />
        <span className="hidden sm:inline">Reject</span>
      </Button>
    </div>
  );
}

interface ContinuationButtonsProps {
  stepTitle: string;
  iterationsUsed: number;
  progressEstimate: number;
  estimatedRemaining: number;
  filesModified: string[];
  onContinue: (additionalIterations: number) => void;
  onCancel: () => void;
}

function ContinuationButtons({
  stepTitle,
  iterationsUsed,
  progressEstimate,
  estimatedRemaining,
  filesModified,
  onContinue,
  onCancel,
}: ContinuationButtonsProps) {
  return (
    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
      <div className="flex items-start gap-2 mb-2">
        <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
            Step reached maximum iterations
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            &quot;{stepTitle}&quot; used {iterationsUsed} iterations (~{progressEstimate}% complete)
          </p>
          {filesModified.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              Files modified: {filesModified.slice(0, 3).join(", ")}
              {filesModified.length > 3 && ` +${filesModified.length - 3} more`}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground mb-3">
        Estimated ~{estimatedRemaining} more iterations needed. Continue?
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="default"
          onClick={() => onContinue(10)}
          className="bg-amber-600 hover:bg-amber-700 h-8"
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1" />
          +10 iterations
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onContinue(25)}
          className="h-8"
        >
          +25 iterations
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onContinue(50)}
          className="h-8"
        >
          +50 iterations
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onCancel}
          className="h-8 text-muted-foreground"
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

function MessageStatusIndicator({ status, onRetry }: { status?: MessageStatus; onRetry?: () => void }) {
  if (!status || status === "sent") return null;

  if (status === "sending") {
    return (
      <div className="flex items-center gap-1 mt-1">
        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Sending...</span>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex items-center gap-2 mt-1">
        <AlertCircle className="h-3 w-3 text-destructive" />
        <span className="text-xs text-destructive">Failed to send</span>
        {onRetry && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRetry}
            className="h-5 px-2 text-xs text-primary hover:text-primary"
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Retry
          </Button>
        )}
      </div>
    );
  }

  return null;
}

interface MessageBubbleProps {
  message: Message;
  onPlanAction?: (action: string) => void;
  onRetry?: (messageId: string) => void;
  onSynthesize?: (content: string) => void;
  onOpenInEditor?: (code: string, language?: string, filename?: string) => void;
}

function MessageBubble({
  message,
  onPlanAction,
  onRetry,
  onSynthesize,
  onOpenInEditor,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showPlanButtons = !isUser && isPendingPlanMessage(message.content) && onPlanAction;
  const isFailed = message.status === "failed";

  return (
    <div
      className={cn(
        "flex gap-2 p-3 w-full overflow-hidden",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <Avatar className={cn(
        "h-7 w-7 sm:h-8 sm:w-8 shrink-0",
        !isUser && message.agent && getAgentBgColor(message.agent)
      )}>
        <AvatarFallback>
          {isUser ? (
            <User className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
          ) : (
            <Bot className={cn("h-3.5 w-3.5 sm:h-4 sm:w-4", message.agent && getAgentColor(message.agent))} />
          )}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "flex flex-col gap-1 min-w-0 overflow-hidden max-w-[85%] sm:max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        {!isUser && message.agent && (
          <span className={cn("text-xs font-medium capitalize", getAgentColor(message.agent))}>
            {message.agent.replace("_", " ")}
          </span>
        )}

        <div
          className={cn(
            "rounded-lg max-w-full",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted",
            isFailed && "border-2 border-destructive/50 bg-destructive/5",
            showPlanButtons ? "flex flex-col" : "px-3 py-2"
          )}
        >
          {/* Scrollable content area for plan messages */}
          <div
            className={cn(
              "prose prose-sm dark:prose-invert max-w-full break-words",
              "[&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-all",
              "[&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1",
              showPlanButtons ? "px-3 pt-2 pb-1 max-h-[50vh] overflow-y-auto" : ""
            )}
          >
            <MarkdownRenderer
              content={message.content}
              onOpenInEditor={onOpenInEditor}
            />
          </div>

          {/* Sticky buttons at bottom for plan messages */}
          {showPlanButtons && (
            <div className="px-3 pb-2 bg-muted sticky bottom-0">
              <PlanActionButtons
                onApprove={() => onPlanAction?.("approve")}
                onReject={() => onPlanAction?.("reject")}
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] sm:text-xs text-muted-foreground">
            {formatDate(message.created_at)}
          </span>
          {isUser && (
            <MessageStatusIndicator
              status={message.status}
              onRetry={onRetry ? () => onRetry(message.id) : undefined}
            />
          )}
          {!isUser && !message.isStreaming && onSynthesize && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSynthesize(message.content)}
              className="h-5 px-1.5 text-xs text-muted-foreground hover:text-primary"
              title="Synthesize learnings from this message"
            >
              <Lightbulb className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function StreamingMessage({ content, agent }: { content: string; agent?: string }) {
  if (!content) return null;

  return (
    <div className="flex gap-2 p-3 w-full overflow-hidden">
      <Avatar className={cn("h-7 w-7 sm:h-8 sm:w-8 shrink-0", agent && getAgentBgColor(agent))}>
        <AvatarFallback>
          <Bot className={cn("h-3.5 w-3.5 sm:h-4 sm:w-4", agent && getAgentColor(agent))} />
        </AvatarFallback>
      </Avatar>

      <div className="flex flex-col gap-1 min-w-0 overflow-hidden max-w-[85%] sm:max-w-[80%]">
        {agent && (
          <span className={cn("text-xs font-medium capitalize", getAgentColor(agent))}>
            {agent.replace("_", " ")}
          </span>
        )}

        <div className="bg-muted rounded-lg px-3 py-2 max-w-full overflow-hidden">
          <div className="prose prose-sm dark:prose-invert max-w-full break-words">
            <StreamingMarkdown content={content} />
            <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1 rounded-sm" />
          </div>
        </div>
      </div>
    </div>
  );
}

function ConnectionBanner({ state }: { state: string }) {
  if (state === "connected") return null;

  const config = {
    connecting: { icon: Loader2, text: "Connecting...", className: "bg-blue-500/10 text-blue-500" },
    reconnecting: { icon: WifiOff, text: "Reconnecting", className: "bg-yellow-500/10 text-yellow-500" },
    disconnected: { icon: WifiOff, text: "Disconnected", className: "bg-destructive/10 text-destructive" },
  };

  const { icon: Icon, text, className } = config[state as keyof typeof config] || config.disconnected;

  return (
    <div className={cn("flex items-center justify-center gap-2 py-2 px-4 text-sm font-medium", className)}>
      <Icon className={cn("h-4 w-4", state === "connecting" || state === "reconnecting" ? "animate-spin" : "")} />
      <span>{text}</span>
      {state === "reconnecting" && (
        <span className="inline-flex gap-0.5">
          <span className="animate-bounce [animation-delay:0ms]">.</span>
          <span className="animate-bounce [animation-delay:150ms]">.</span>
          <span className="animate-bounce [animation-delay:300ms]">.</span>
        </span>
      )}
    </div>
  );
}

export function MessageList() {
  const { messages, streamingMessage, connectionState, currentConversation, continuationRequest, clearContinuationRequest } = useChatStore();
  const { sendMessage, retryMessage } = useChat();
  const { activeProjectId, openFile, setActiveFile } = useWorkspaceStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [synthesizeContent, setSynthesizeContent] = useState<string | null>(null);

  // Auto-scroll to bottom when new messages arrive or on mount
  useEffect(() => {
    const scrollToBottom = () => {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    };
    const timer = setTimeout(scrollToBottom, 50);
    return () => clearTimeout(timer);
  }, [messages, streamingMessage, continuationRequest]);

  // Scroll to bottom on initial load
  useEffect(() => {
    if (containerRef.current && messages.length > 0) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, []);

  // Handle plan actions (approve/reject)
  const handlePlanAction = useCallback((action: string) => {
    sendMessage(`/plan ${action}`);
  }, [sendMessage]);

  // Handle continuation request
  const handleContinue = useCallback((additionalIterations: number) => {
    sendMessage(`Continue the current step. You have ${additionalIterations} more iterations. Pick up exactly where you left off and complete the task.`);
    clearContinuationRequest();
  }, [sendMessage, clearContinuationRequest]);

  const handleCancelContinuation = useCallback(() => {
    sendMessage("Skip this step and move on to the next one. Mark the current step as incomplete.");
    clearContinuationRequest();
  }, [sendMessage, clearContinuationRequest]);

  // Handle retry
  const handleRetry = useCallback((messageId: string) => {
    retryMessage(messageId);
  }, [retryMessage]);

  // Handle opening code in editor
  const handleOpenInEditor = useCallback((code: string, language?: string, filename?: string) => {
    // Generate a filename if not provided
    const ext = language === "typescript" || language === "tsx" ? "ts" :
                language === "javascript" || language === "jsx" ? "js" :
                language === "python" ? "py" :
                language === "html" ? "html" :
                language === "css" ? "css" :
                language || "txt";

    const generatedFilename = filename || `snippet-${Date.now()}.${ext}`;

    // Open as a new unsaved file in the editor
    openFile({
      path: generatedFilename,
      content: code,
      originalContent: "",
      language: language || null,
      isDirty: true,
    });
    setActiveFile(generatedFilename);
  }, [openFile, setActiveFile]);

  if (messages.length === 0 && !streamingMessage) {
    return (
      <div className="flex-1 min-h-0 flex flex-col">
        <ConnectionBanner state={connectionState} />
        <div className="flex-1 flex items-center justify-center text-muted-foreground p-4">
          <div className="text-center">
            <Bot className="h-10 w-10 sm:h-12 sm:w-12 mx-auto mb-4 opacity-50" />
            <p className="text-sm sm:text-base">Start a conversation with the AI agents</p>
            <p className="text-xs sm:text-sm mt-1">Type a message below to get started</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <ConnectionBanner state={connectionState} />
      <div
        ref={containerRef}
        className="flex-1 min-h-0 w-full overflow-y-auto overscroll-contain"
      >
        <div className="flex flex-col w-full">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onPlanAction={handlePlanAction}
              onRetry={handleRetry}
              onSynthesize={setSynthesizeContent}
              onOpenInEditor={handleOpenInEditor}
            />
          ))}
          {streamingMessage && <StreamingMessage content={streamingMessage} />}
          {continuationRequest && (
            <div className="px-3 sm:px-4 py-2">
              <ContinuationButtons
                stepTitle={continuationRequest.stepTitle}
                iterationsUsed={continuationRequest.iterationsUsed}
                progressEstimate={continuationRequest.progressEstimate}
                estimatedRemaining={continuationRequest.estimatedRemaining}
                filesModified={continuationRequest.filesModified}
                onContinue={handleContinue}
                onCancel={handleCancelContinuation}
              />
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </div>

      {synthesizeContent && (
        <SynthesizeModal
          content={synthesizeContent}
          conversationId={currentConversation?.id}
          projectId={currentConversation?.project_id ?? activeProjectId ?? undefined}
          onClose={() => setSynthesizeContent(null)}
        />
      )}
    </div>
  );
}
