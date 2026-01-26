"use client";

import { useChatStore } from "@/stores/chat-store";
import { cn, getAgentColor, getAgentBgColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Bot,
  ChevronDown,
  Check,
  Flame,
  Code2,
  Database,
  Server,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

const agentIcons: Record<string, React.ElementType> = {
  wyld: Flame,
  code: Code2,
  data: Database,
  infra: Server,
  research: Search,
  qa: ShieldCheck,
};

const agentDescriptions: Record<string, string> = {
  wyld: "Supervisor - orchestrates all agents",
  code: "Frontend & backend development",
  data: "Database & data processing",
  infra: "DevOps & infrastructure",
  research: "Web search & documentation",
  qa: "Testing & quality assurance",
};

interface AgentSelectorProps {
  className?: string;
  variant?: "compact" | "full";
}

export function AgentSelector({ className, variant = "compact" }: AgentSelectorProps) {
  const { activeAgent, availableAgents, setActiveAgent } = useChatStore();
  const [open, setOpen] = useState(false);

  const selectedAgent = activeAgent || "wyld";
  const Icon = agentIcons[selectedAgent] || Bot;

  const handleSelect = (agent: string | null) => {
    setActiveAgent(agent);
    setOpen(false);
  };

  if (variant === "compact") {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className={cn(
              "h-8 gap-1.5 px-2 sm:px-3",
              activeAgent && getAgentBgColor(activeAgent),
              className
            )}
          >
            <Icon className={cn("h-3.5 w-3.5", activeAgent && getAgentColor(activeAgent))} />
            <span className="hidden sm:inline text-xs capitalize">
              {selectedAgent}
            </span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56 p-1" align="start">
          <div className="space-y-0.5">
            <button
              onClick={() => handleSelect(null)}
              className={cn(
                "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors",
                !activeAgent && "bg-muted"
              )}
            >
              <Sparkles className="h-4 w-4 text-purple-500" />
              <span className="flex-1 text-left">Auto (Wyld decides)</span>
              {!activeAgent && <Check className="h-3.5 w-3.5 text-primary" />}
            </button>
            <div className="h-px bg-border my-1" />
            {availableAgents.map((agent) => {
              const AgentIcon = agentIcons[agent] || Bot;
              const isSelected = activeAgent === agent;
              return (
                <button
                  key={agent}
                  onClick={() => handleSelect(agent)}
                  className={cn(
                    "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors",
                    isSelected && "bg-muted"
                  )}
                >
                  <AgentIcon className={cn("h-4 w-4", getAgentColor(agent))} />
                  <div className="flex-1 text-left">
                    <span className="capitalize">{agent}</span>
                    <p className="text-[10px] text-muted-foreground">
                      {agentDescriptions[agent]}
                    </p>
                  </div>
                  {isSelected && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
                </button>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>
    );
  }

  // Full variant - horizontal list for desktop
  return (
    <div className={cn("flex items-center gap-1 overflow-x-auto pb-1", className)}>
      <Button
        variant={!activeAgent ? "default" : "ghost"}
        size="sm"
        onClick={() => setActiveAgent(null)}
        className="h-7 px-2 text-xs shrink-0"
      >
        <Sparkles className="h-3 w-3 mr-1" />
        Auto
      </Button>
      {availableAgents.map((agent) => {
        const AgentIcon = agentIcons[agent] || Bot;
        const isSelected = activeAgent === agent;
        return (
          <Button
            key={agent}
            variant={isSelected ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveAgent(agent)}
            className={cn(
              "h-7 px-2 text-xs shrink-0",
              isSelected && getAgentBgColor(agent)
            )}
          >
            <AgentIcon className={cn("h-3 w-3 mr-1", getAgentColor(agent))} />
            <span className="capitalize">{agent}</span>
          </Button>
        );
      })}
    </div>
  );
}

// Inline badge showing current agent
export function AgentBadge({ className }: { className?: string }) {
  const { activeAgent } = useChatStore();

  if (!activeAgent) {
    return (
      <Badge variant="outline" className={cn("text-[10px] h-5 px-1.5", className)}>
        <Sparkles className="h-2.5 w-2.5 mr-0.5 text-purple-500" />
        Auto
      </Badge>
    );
  }

  const Icon = agentIcons[activeAgent] || Bot;
  return (
    <Badge
      variant="outline"
      className={cn("text-[10px] h-5 px-1.5", getAgentBgColor(activeAgent), className)}
    >
      <Icon className={cn("h-2.5 w-2.5 mr-0.5", getAgentColor(activeAgent))} />
      <span className="capitalize">{activeAgent}</span>
    </Badge>
  );
}
