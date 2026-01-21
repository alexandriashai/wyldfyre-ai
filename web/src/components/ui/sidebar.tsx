"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn, getStatusBgColor } from "@/lib/utils";
import { useAgentStore } from "@/stores/agent-store";
import { ProjectSelector } from "@/components/projects/project-selector";
import {
  MessageSquare,
  Bot,
  Globe,
  Brain,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  BarChart3,
  FolderKanban,
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
  isMobileOpen?: boolean;
  onMobileToggle?: () => void;
}

const navItems = [
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/projects", icon: FolderKanban, label: "Projects" },
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/domains", icon: Globe, label: "Domains" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/usage", icon: BarChart3, label: "Usage" },
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

export function Sidebar({ isCollapsed, onToggle, isMobileOpen, onMobileToggle }: SidebarProps) {
  const pathname = usePathname();
  const { agents } = useAgentStore();

  const getAgentStatus = (name: string) => {
    const agent = agents.find((a) => a.name === name);
    return agent?.status || "unknown";
  };

  // Close mobile menu when navigating
  const handleNavClick = () => {
    if (onMobileToggle && isMobileOpen) {
      onMobileToggle();
    }
  };

  return (
    <div
      className={cn(
        "relative flex flex-col border-r bg-card transition-all duration-300",
        // Desktop: normal sidebar behavior
        "hidden md:flex",
        isCollapsed ? "md:w-16" : "md:w-64",
        // Mobile: off-canvas drawer
        isMobileOpen && "fixed inset-y-0 left-0 z-50 flex w-64 shadow-xl"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4 justify-between">
        <Link href="/chat" className="flex items-center gap-2" onClick={handleNavClick}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-5 w-5" />
          </div>
          {(!isCollapsed || isMobileOpen) && (
            <span className="font-semibold">AI Infrastructure</span>
          )}
        </Link>
        {/* Mobile close button */}
        {isMobileOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onMobileToggle}
            className="md:hidden h-8 w-8"
          >
            <X className="h-5 w-5" />
          </Button>
        )}
      </div>

      {/* Project Selector */}
      <div className={cn("px-3 py-3 border-b", isCollapsed && !isMobileOpen && "px-2")}>
        <ProjectSelector collapsed={isCollapsed && !isMobileOpen} />
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-2 py-4">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            // Desktop collapsed view
            if (isCollapsed && !isMobileOpen) {
              return (
                <Tooltip key={item.href} delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Link
                      href={item.href}
                      onClick={handleNavClick}
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

            // Desktop expanded or mobile view
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={handleNavClick}
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
        <div className={cn("px-2", isCollapsed && !isMobileOpen && "px-0")}>
          {(!isCollapsed || isMobileOpen) && (
            <p className="mb-2 px-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Agents
            </p>
          )}
          <div className="space-y-1">
            {agentNames.map((agent) => {
              const status = getAgentStatus(agent.name);

              // Desktop collapsed view
              if (isCollapsed && !isMobileOpen) {
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

              // Desktop expanded or mobile view
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

      {/* Collapse Toggle - desktop only */}
      <div className="border-t p-2 hidden md:block">
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
