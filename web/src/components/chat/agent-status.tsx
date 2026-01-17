"use client";

import { useAgentStore } from "@/stores/agent-store";
import { cn, getStatusColor, getAgentColor } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Bot, Loader2 } from "lucide-react";

export function AgentStatus() {
  const { agents } = useAgentStore();

  // Find busy agents
  const busyAgents = agents.filter(
    (agent) => agent.status === "busy" && agent.current_task
  );

  if (busyAgents.length === 0) {
    return null;
  }

  return (
    <div className="border-b bg-muted/50 px-4 py-2">
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm font-medium">Agents working:</span>
      </div>
      <div className="mt-2 space-y-2">
        {busyAgents.map((agent) => (
          <div key={agent.name} className="flex items-center gap-3">
            <div className={cn("flex items-center gap-2", getAgentColor(agent.name))}>
              <Bot className="h-4 w-4" />
              <span className="text-sm font-medium capitalize">
                {agent.name.replace("_", " ")}
              </span>
            </div>
            <div className="flex-1">
              <Progress value={50} className="h-1" />
            </div>
            <span className="text-xs text-muted-foreground truncate max-w-[200px]">
              {agent.current_task}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
