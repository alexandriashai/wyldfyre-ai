"use client";

import Link from "next/link";
import { cn, getStatusColor, getStatusBgColor, getAgentColor, getAgentBgColor, formatRelativeTime, type AgentType, type AgentStatus } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, RefreshCw, ExternalLink } from "lucide-react";

interface Agent {
  name: string;
  status: string;
  current_task?: string;
  last_heartbeat?: string;
  metrics?: Record<string, number>;
}

interface AgentCardProps {
  agent: Agent;
  onRestart?: () => void;
  isRestarting?: boolean;
}

const agentDescriptions: Record<string, string> = {
  supervisor: "Task routing, orchestration, and user interface",
  code_agent: "Git operations, coding, refactoring, and debugging",
  data_agent: "SQL queries, data analysis, ETL, and backups",
  infra_agent: "Docker, Nginx, domains, SSL/TLS, and monitoring",
  research_agent: "Web search, documentation, and synthesis",
  qa_agent: "Testing, code review, security, and validation",
};

export function AgentCard({ agent, onRestart, isRestarting }: AgentCardProps) {
  const displayName = agent.name.replace("_", " ");

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn("rounded-lg p-2", getAgentBgColor(agent.name as AgentType))}>
              <Bot className={cn("h-5 w-5", getAgentColor(agent.name as AgentType))} />
            </div>
            <div>
              <CardTitle className="text-lg capitalize">{displayName}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {agentDescriptions[agent.name] || "AI Agent"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "h-3 w-3 rounded-full",
                getStatusBgColor(agent.status as AgentStatus)
              )}
            />
            <span className={cn("text-sm font-medium capitalize", getStatusColor(agent.status as AgentStatus))}>
              {agent.status}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {agent.current_task && (
            <div className="rounded-md bg-muted p-2">
              <p className="text-xs text-muted-foreground">Current Task</p>
              <p className="text-sm truncate">{agent.current_task}</p>
            </div>
          )}

          {agent.last_heartbeat && (
            <p className="text-xs text-muted-foreground">
              Last seen: {formatRelativeTime(agent.last_heartbeat)}
            </p>
          )}

          {agent.metrics && Object.keys(agent.metrics).length > 0 && (
            <div className="grid grid-cols-3 gap-2 text-center">
              {Object.entries(agent.metrics).slice(0, 3).map(([key, value]) => (
                <div key={key} className="rounded-md bg-muted p-2">
                  <p className="text-xs text-muted-foreground capitalize">
                    {key.replace("_", " ")}
                  </p>
                  <p className="text-lg font-semibold">{value}</p>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={onRestart}
              disabled={isRestarting || agent.status === "starting"}
            >
              <RefreshCw className={cn("h-4 w-4 mr-1", isRestarting && "animate-spin")} />
              Restart
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/agents/${agent.name}`}>
                <ExternalLink className="h-4 w-4 mr-1" />
                Details
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
