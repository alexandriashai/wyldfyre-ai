"use client";

import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";

interface AgentLog {
  timestamp: string;
  level: string;
  message: string;
}

interface AgentLogsProps {
  logs: AgentLog[];
  isLoading?: boolean;
}

const levelColors: Record<string, string> = {
  debug: "text-gray-500",
  info: "text-blue-500",
  warning: "text-yellow-500",
  error: "text-red-500",
};

export function AgentLogs({ logs, isLoading }: AgentLogsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        No logs available
      </div>
    );
  }

  return (
    <ScrollArea className="h-[400px] rounded-md border bg-muted/50">
      <div className="p-4 font-mono text-sm">
        {logs.map((log, index) => (
          <div key={index} className="flex gap-4 py-1 hover:bg-muted/50">
            <span className="text-muted-foreground shrink-0">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={cn(
                "uppercase font-semibold w-16 shrink-0",
                levelColors[log.level] || "text-gray-500"
              )}
            >
              {log.level}
            </span>
            <span className="break-all">{log.message}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
