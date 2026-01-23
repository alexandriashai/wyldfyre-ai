"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
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
  Plus,
  Trash2,
  MoreVertical,
  Pencil,
  LayoutDashboard,
} from "lucide-react";
import { Button } from "./button";
import { ScrollArea } from "./scroll-area";
import { Separator } from "./separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "./tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./alert-dialog";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  isMobileOpen?: boolean;
  onMobileToggle?: () => void;
}

const navItems = [
  { href: "/workspace", icon: LayoutDashboard, label: "Workspace" },
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/projects", icon: FolderKanban, label: "Projects" },
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/domains", icon: Globe, label: "Domains" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/usage", icon: BarChart3, label: "Usage" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar({ isCollapsed, onToggle, isMobileOpen, onMobileToggle }: SidebarProps) {
  const pathname = usePathname();
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    selectConversation,
    createConversation,
    updateConversation,
    deleteConversation,
    isLoading,
  } = useChatStore();
  const { selectedProject } = useProjectStore();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Close mobile menu when navigating
  const handleNavClick = () => {
    if (onMobileToggle && isMobileOpen) {
      onMobileToggle();
    }
  };

  const handleCreateConversation = async () => {
    if (!token) return;
    try {
      await createConversation(token, "New Chat", selectedProject?.id);
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    if (!token || id === currentConversation?.id) return;
    try {
      await selectConversation(token, id);
    } catch (error) {
      console.error("Failed to select conversation:", error);
    }
  };

  const handleDeleteClick = (id: string) => {
    setConversationToDelete(id);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!token || !conversationToDelete) return;
    try {
      await deleteConversation(token, conversationToDelete);
      setDeleteDialogOpen(false);
      setConversationToDelete(null);
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  };

  const handleRenameStart = (conv: { id: string; title: string }) => {
    setRenamingId(conv.id);
    setRenameValue(conv.title);
  };

  const handleRenameSubmit = async () => {
    if (!token || !renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    try {
      await updateConversation(token, renamingId, { title: renameValue.trim() });
    } catch (error) {
      console.error("Failed to rename conversation:", error);
    }
    setRenamingId(null);
  };

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: "short" });
    }
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
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
      <div className="px-2 py-4">
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
      </div>

      {/* Conversations List */}
      <div className="flex flex-col border-t min-h-0 flex-1">
        {(!isCollapsed || isMobileOpen) ? (
          <>
            <div className="flex items-center justify-between px-3 py-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Chats
              </p>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleCreateConversation}
                disabled={isLoading}
                title="New conversation"
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
            <ScrollArea className="flex-1">
              <div className="px-2 pb-2 space-y-0.5">
                {conversations.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-3">
                    No conversations yet.
                  </p>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.id}
                      className={cn(
                        "group flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted transition-colors",
                        currentConversation?.id === conv.id && "bg-muted"
                      )}
                      onClick={() => renamingId !== conv.id && handleSelectConversation(conv.id)}
                    >
                      <MessageSquare className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                      <div className="flex-1 min-w-0">
                        {renamingId === conv.id ? (
                          <input
                            ref={renameInputRef}
                            type="text"
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onBlur={handleRenameSubmit}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleRenameSubmit();
                              if (e.key === "Escape") setRenamingId(null);
                            }}
                            className="text-xs font-medium w-full bg-background border rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-primary"
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <>
                            <p className="text-xs font-medium truncate">{conv.title}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {formatDate(conv.updated_at)}
                            </p>
                          </>
                        )}
                      </div>
                      {renamingId !== conv.id && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreVertical className="h-3 w-3" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              className="text-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRenameStart(conv);
                              }}
                            >
                              <Pencil className="h-3.5 w-3.5 mr-2" />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive text-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteClick(conv.id);
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </>
        ) : (
          <div className="flex flex-col items-center py-2 gap-1">
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleCreateConversation}
                  disabled={isLoading}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">New Chat</TooltipContent>
            </Tooltip>
            <ScrollArea className="flex-1 w-full">
              <div className="flex flex-col items-center gap-1">
                {conversations.map((conv) => (
                  <Tooltip key={conv.id} delayDuration={0}>
                    <TooltipTrigger asChild>
                      <Button
                        variant={currentConversation?.id === conv.id ? "secondary" : "ghost"}
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleSelectConversation(conv.id)}
                      >
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right">{conv.title}</TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The conversation and all its messages
              will be permanently deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
