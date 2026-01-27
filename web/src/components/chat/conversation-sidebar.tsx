"use client";

import { useState, useMemo } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useProjectStore } from "@/stores/project-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  MessageSquare,
  Plus,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Search,
  Star,
  StarOff,
  Pin,
  CheckSquare,
  Square,
  X,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { getTagInfo } from "@/lib/constants";
import { TagFilter } from "./tag-filter";
import { TagEditor } from "./tag-editor";

interface ConversationSidebarProps {
  isCollapsed?: boolean;
  onToggle?: () => void;
  projectId?: string;
}

type DateGroup = "Pinned" | "Today" | "Yesterday" | "Last 7 Days" | "Last 30 Days" | "Older";

function getDateGroup(dateString: string): DateGroup {
  if (!dateString) return "Older";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Older";
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return "Last 7 Days";
  if (diffDays < 30) return "Last 30 Days";
  return "Older";
}

function formatRelativeTime(dateString: string): string {
  if (!dateString) return "";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "";
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } else if (diffDays === 1) {
    return "Yesterday";
  } else if (diffDays < 7) {
    return date.toLocaleDateString([], { weekday: "short" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function ConversationSidebar({
  isCollapsed = false,
  onToggle,
  projectId,
}: ConversationSidebarProps) {
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    selectConversation,
    createConversation,
    deleteConversation,
    isLoading,
    pinnedConversations,
    togglePinConversation,
    searchQuery,
    setSearchQuery,
  } = useChatStore();
  const { selectedProject, projects } = useProjectStore();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);
  const [isMultiSelect, setIsMultiSelect] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  // Filter and group conversations
  const filteredAndGrouped = useMemo(() => {
    let filtered = conversations;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = conversations.filter(
        (c) => c.title?.toLowerCase().includes(query)
      );
    }

    // Separate pinned and unpinned
    const pinned = filtered.filter((c) => pinnedConversations.has(c.id));
    const unpinned = filtered.filter((c) => !pinnedConversations.has(c.id));

    // Group unpinned by date
    const groups: Record<DateGroup, typeof conversations> = {
      Pinned: pinned,
      Today: [],
      Yesterday: [],
      "Last 7 Days": [],
      "Last 30 Days": [],
      Older: [],
    };

    unpinned.forEach((conv) => {
      const group = getDateGroup(conv.updated_at || conv.created_at);
      groups[group].push(conv);
    });

    return groups;
  }, [conversations, searchQuery, pinnedConversations]);

  const handleCreateConversation = async () => {
    if (!token || !selectedProject?.id) return;
    try {
      await createConversation(token, selectedProject.id, "New Chat");
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    if (isMultiSelect) {
      const newSelected = new Set(selectedIds);
      if (newSelected.has(id)) newSelected.delete(id);
      else newSelected.add(id);
      setSelectedIds(newSelected);
      return;
    }
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

  const handleBulkDelete = async () => {
    if (!token) return;
    for (const id of selectedIds) {
      try {
        await deleteConversation(token, id);
      } catch (error) {
        console.error("Failed to delete:", error);
      }
    }
    setSelectedIds(new Set());
    setIsMultiSelect(false);
    setBulkDeleteOpen(false);
  };

  const getProjectColor = (projectId: string | null) => {
    if (!projectId) return null;
    const project = projects.find((p) => p.id === projectId);
    return project?.color || null;
  };

  if (isCollapsed) {
    return (
      <div className="flex flex-col h-full w-12 border-r bg-muted/20">
        <Button variant="ghost" size="icon" className="m-1" onClick={onToggle} title="Expand sidebar">
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="m-1" onClick={handleCreateConversation} disabled={isLoading} title="New conversation">
          <Plus className="h-4 w-4" />
        </Button>
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            {conversations.slice(0, 20).map((conv) => (
              <Button
                key={conv.id}
                variant={currentConversation?.id === conv.id ? "secondary" : "ghost"}
                size="icon"
                className="m-1"
                onClick={() => handleSelectConversation(conv.id)}
                title={conv.title || "Untitled"}
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            ))}
          </ScrollArea>
        </div>
      </div>
    );
  }

  const renderGroup = (label: DateGroup, items: typeof conversations) => {
    if (items.length === 0) return null;

    return (
      <div key={label} className="mb-2">
        <div className="px-3 py-1">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
            {label === "Pinned" ? (
              <span className="flex items-center gap-1">
                <Pin className="h-2.5 w-2.5" />
                Pinned
              </span>
            ) : label}
          </span>
        </div>
        {items.map((conv) => {
          const isPinned = pinnedConversations.has(conv.id);
          const isSelected = selectedIds.has(conv.id);
          const projectColor = getProjectColor(conv.project_id ?? null);

          return (
            <div
              key={conv.id}
              className={cn(
                "group flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted transition-colors mx-1",
                currentConversation?.id === conv.id && !isMultiSelect && "bg-muted",
                isSelected && "bg-primary/10 border border-primary/30"
              )}
              onClick={() => handleSelectConversation(conv.id)}
            >
              {isMultiSelect ? (
                <div className="shrink-0">
                  {isSelected ? (
                    <CheckSquare className="h-4 w-4 text-primary" />
                  ) : (
                    <Square className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              ) : (
                <div className="relative shrink-0">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  {projectColor && (
                    <div
                      className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border border-background"
                      style={{ backgroundColor: projectColor }}
                    />
                  )}
                </div>
              )}

              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-sm truncate",
                  isPinned && "font-medium"
                )}>
                  {conv.title || "Untitled"}
                </p>
                <div className="flex items-center gap-1">
                  <p className="text-[10px] text-muted-foreground truncate">
                    {formatRelativeTime(conv.updated_at || conv.created_at)}
                    {(conv.message_count ?? 0) > 0 && ` · ${conv.message_count} msgs`}
                  </p>
                  {conv.tags && conv.tags.length > 0 && (
                    <div className="flex gap-0.5 shrink-0">
                      {conv.tags.slice(0, 2).map((tag) => {
                        const info = getTagInfo(tag);
                        return (
                          <span
                            key={tag}
                            className="h-1.5 w-1.5 rounded-full"
                            style={{ backgroundColor: info?.color || "#6B7280" }}
                            title={info?.label || tag}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {!isMultiSelect && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-3 w-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40">
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        togglePinConversation(conv.id);
                      }}
                    >
                      {isPinned ? (
                        <><StarOff className="h-4 w-4 mr-2" />Unpin</>
                      ) : (
                        <><Star className="h-4 w-4 mr-2" />Pin</>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild onClick={(e) => e.stopPropagation()}>
                      <div>
                        <TagEditor conversationId={conv.id} currentTags={conv.tags || []} />
                      </div>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteClick(conv.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full w-64 border-r bg-muted/20">
      {/* Header */}
      <div className="flex items-center justify-between p-2 border-b">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleCreateConversation} disabled={isLoading} title="New conversation">
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            variant={isMultiSelect ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => {
              setIsMultiSelect(!isMultiSelect);
              if (isMultiSelect) setSelectedIds(new Set());
            }}
            title="Multi-select"
          >
            <CheckSquare className="h-3.5 w-3.5" />
          </Button>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onToggle} title="Collapse sidebar">
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      {/* Search */}
      <div className="px-2 py-1.5 border-b">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-7 text-xs pl-7 pr-7"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-0.5 top-1/2 -translate-y-1/2 h-6 w-6"
              onClick={() => setSearchQuery("")}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {/* Tag Filter */}
      <TagFilter />

      {/* Bulk actions bar */}
      {isMultiSelect && selectedIds.size > 0 && (
        <div className="flex items-center justify-between px-2 py-1.5 border-b bg-primary/5">
          <span className="text-xs font-medium">{selectedIds.size} selected</span>
          <Button
            variant="destructive"
            size="sm"
            className="h-6 text-xs px-2"
            onClick={() => setBulkDeleteOpen(true)}
          >
            <Trash2 className="h-3 w-3 mr-1" />
            Delete
          </Button>
        </div>
      )}

      {/* Conversations list */}
      <ScrollArea className="flex-1">
        <div className="py-1">
          {conversations.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8 px-4">
              No conversations yet.
              <br />
              Click + to start a new chat.
            </p>
          ) : (
            <>
              {renderGroup("Pinned", filteredAndGrouped.Pinned)}
              {renderGroup("Today", filteredAndGrouped.Today)}
              {renderGroup("Yesterday", filteredAndGrouped.Yesterday)}
              {renderGroup("Last 7 Days", filteredAndGrouped["Last 7 Days"])}
              {renderGroup("Last 30 Days", filteredAndGrouped["Last 30 Days"])}
              {renderGroup("Older", filteredAndGrouped.Older)}
            </>
          )}
        </div>
      </ScrollArea>

      {/* Delete single confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The conversation and all its messages will be permanently deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk delete confirmation */}
      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {selectedIds.size} conversations?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {selectedIds.size} conversation{selectedIds.size !== 1 ? "s" : ""} and all their messages.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleBulkDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
