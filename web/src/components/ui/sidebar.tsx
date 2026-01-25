"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/stores/project-store";
import { ProjectSelector } from "@/components/projects/project-selector";
import {
  MessageSquare,
  Bot,
  Globe,
  Brain,
  Settings,
  Settings2,
  ChevronLeft,
  ChevronRight,
  X,
  BarChart3,
  FileCode,
  Terminal,
} from "lucide-react";
import { Button } from "./button";
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

const projectNavItems = [
  { href: "/workspace/files", icon: FileCode, label: "Files" },
  { href: "/workspace/terminal", icon: Terminal, label: "Terminal" },
  { href: "/workspace/chats", icon: MessageSquare, label: "Chats" },
  { href: "/workspace/settings", icon: Settings2, label: "Project" },
];

const globalNavItems = [
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/domains", icon: Globe, label: "Domains" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/usage", icon: BarChart3, label: "Usage" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar({ isCollapsed, onToggle, isMobileOpen, onMobileToggle }: SidebarProps) {
  const pathname = usePathname();
  const { selectedProject } = useProjectStore();

  const handleNavClick = () => {
    if (onMobileToggle && isMobileOpen) {
      onMobileToggle();
    }
  };

  const renderNavItem = (item: { href: string; icon: any; label: string }) => {
    const isActive = pathname.startsWith(item.href);
    const Icon = item.icon;

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
  };

  return (
    <div
      className={cn(
        "relative flex flex-col border-r bg-card transition-all duration-300",
        "hidden md:flex",
        isCollapsed ? "md:w-16" : "md:w-64",
        isMobileOpen && "fixed inset-y-0 left-0 z-50 flex w-64 shadow-xl"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4 justify-between">
        <Link href="/workspace/files" className="flex items-center gap-2" onClick={handleNavClick}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-5 w-5" />
          </div>
          {(!isCollapsed || isMobileOpen) && (
            <span className="font-semibold">AI Infrastructure</span>
          )}
        </Link>
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

      {/* Project Navigation */}
      {selectedProject && (
        <div className="px-2 py-3">
          {(!isCollapsed || isMobileOpen) && (
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
              Project
            </p>
          )}
          <nav className="space-y-1">
            {projectNavItems.map(renderNavItem)}
          </nav>
        </div>
      )}

      <Separator />

      {/* Global Navigation */}
      <div className="px-2 py-3 flex-1">
        {(!isCollapsed || isMobileOpen) && (
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
            Platform
          </p>
        )}
        <nav className="space-y-1">
          {globalNavItems.map(renderNavItem)}
        </nav>
      </div>

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
