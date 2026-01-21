"use client";

import { useEffect, useRef } from "react";
import { cn, getAgentColor, getAgentBgColor, formatDate } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  agent?: string;
  created_at: string;
  isStreaming?: boolean;
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-2 p-3 w-full overflow-hidden",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <Avatar className={cn("h-8 w-8 shrink-0", !isUser && message.agent && getAgentBgColor(message.agent))}>
        <AvatarFallback>
          {isUser ? (
            <User className="h-4 w-4" />
          ) : (
            <Bot className={cn("h-4 w-4", message.agent && getAgentColor(message.agent))} />
          )}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "flex flex-col gap-1 min-w-0 overflow-hidden",
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
            "rounded-lg px-3 py-2 max-w-full overflow-hidden",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          )}
        >
          <div className="prose prose-sm dark:prose-invert max-w-full break-words overflow-x-auto [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-all">
            <ReactMarkdown
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const isInline = !match;

                  if (isInline) {
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  }

                  return (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                    >
                      {String(children).replace(/\n$/, "")}
                    </SyntaxHighlighter>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        <span className="text-xs text-muted-foreground">
          {formatDate(message.created_at)}
        </span>
      </div>
    </div>
  );
}

function StreamingMessage({ content, agent }: { content: string; agent?: string }) {
  if (!content) return null;

  return (
    <div className="flex gap-2 p-3 w-full overflow-hidden">
      <Avatar className={cn("h-8 w-8 shrink-0", agent && getAgentBgColor(agent))}>
        <AvatarFallback>
          <Bot className={cn("h-4 w-4", agent && getAgentColor(agent))} />
        </AvatarFallback>
      </Avatar>

      <div className="flex flex-col gap-1 min-w-0 overflow-hidden">
        {agent && (
          <span className={cn("text-xs font-medium capitalize", getAgentColor(agent))}>
            {agent.replace("_", " ")}
          </span>
        )}

        <div className="bg-muted rounded-lg px-3 py-2 max-w-full overflow-hidden">
          <div className="prose prose-sm dark:prose-invert max-w-full break-words">
            <ReactMarkdown>{content}</ReactMarkdown>
            <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function MessageList() {
  const { messages, streamingMessage } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingMessage]);

  if (messages.length === 0 && !streamingMessage) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center text-muted-foreground p-4">
        <div className="text-center">
          <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Start a conversation with the AI agents</p>
          <p className="text-sm mt-1">Type a message below to get started</p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 min-h-0 w-full">
      <div className="flex flex-col w-full overflow-hidden">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {streamingMessage && <StreamingMessage content={streamingMessage} />}
        <div ref={scrollRef} />
      </div>
    </ScrollArea>
  );
}
