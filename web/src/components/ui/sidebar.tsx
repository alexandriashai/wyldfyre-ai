"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn, getStatusBgColor } from "@/lib/utils";
import { useAgentStore } from "@/stores/agent-store";
import {
  MessageSquare,
  Bot,
  Globe,
  Brain,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "./button";
import { ScrollArea } from "./scroll-area";
import { Separator } from "./separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "./tooltip";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/domains", icon: Globe, label: "Domains" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

const agentNames = [
  { name: "supervisor", label: "Supervisor" },
  { name: "code_agent", label: "Code" },
  { name: "data_agent", label: "Data" },
  { name: "infra_agent", label: "Infra" },
  { name: "research_agent", label: "Research" },
  { name: "qa_agent", label: "QA" },
];

export function Sidebar({ isCollapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { agents } = useAgentStore();

  const getAgentStatus = (name: string) => {
    const agent = agents.find((a) => a.name === name);
    return agent?.status || "unknown";
  };

  return (
    <div
      className={cn(
        "relative flex flex-col border-r bg-card transition-all duration-300",
        isCollapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/chat" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-5 w-5" />
          </div>
          {!isCollapsed && (
            <span className="font-semibold">AI Infrastructure</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-2 py-4">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            if (isCollapsed) {
              return (
                <Tooltip key={item.href} delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-md mx-auto",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <Separator className="my-4" />

        {/* Agent Status */}
        <div className={cn("px-2", isCollapsed && "px-0")}>
          {!isCollapsed && (
            <p className="mb-2 px-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Agents
            </p>
          )}
          <div className="space-y-1">
            {agentNames.map((agent) => {
              const status = getAgentStatus(agent.name);

              if (isCollapsed) {
                return (
                  <Tooltip key={agent.name} delayDuration={0}>
                    <TooltipTrigger asChild>
                      <div className="flex h-8 w-8 items-center justify-center mx-auto">
                        <div
                          className={cn(
                            "h-2 w-2 rounded-full",
                            getStatusBgColor(status)
                          )}
                        />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      {agent.label}: {status}
                    </TooltipContent>
                  </Tooltip>
                );
              }

              return (
                <div
                  key={agent.name}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm"
                >
                  <div
                    className={cn(
                      "h-2 w-2 rounded-full",
                      getStatusBgColor(status)
                    )}
                  />
                  <span className="text-muted-foreground">{agent.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </ScrollArea>

      {/* Collapse Toggle */}
      <div className="border-t p-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className={cn("w-full", isCollapsed && "px-0")}
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4 mr-2" />
              Collapse
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
