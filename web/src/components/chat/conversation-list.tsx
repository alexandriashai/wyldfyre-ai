"use client";

import { useState, useMemo } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { cn, formatRelativeTime, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MessageSquare, Plus, Trash2, Search, FileText } from "lucide-react";

interface ConversationListProps {
  collapsed?: boolean;
}

// Group conversations by date
function groupByDate<T extends { id: string; updated_at: string }>(conversations: T[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const groups: { [key: string]: T[] } = {
    Today: [],
    Yesterday: [],
    "This Week": [],
    Earlier: [],
  };

  conversations.forEach((conv) => {
    const convDate = new Date(conv.updated_at);
    if (convDate >= today) {
      groups.Today.push(conv);
    } else if (convDate >= yesterday) {
      groups.Yesterday.push(conv);
    } else if (convDate >= lastWeek) {
      groups["This Week"].push(conv);
    } else {
      groups.Earlier.push(conv);
    }
  });

  return groups;
}

export function ConversationList({ collapsed }: ConversationListProps) {
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    selectConversation,
    createConversation,
    deleteConversation,
    projectFilter,
  } = useChatStore();
  const { selectedProject, getProjectById } = useProjectStore();

  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Filter and group conversations
  const filteredConversations = useMemo(() => {
    let filtered = conversations;

    // Filter by search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.title?.toLowerCase().includes(query) ||
          c.id.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [conversations, searchQuery]);

  const groupedConversations = useMemo(
    () => groupByDate(filteredConversations),
    [filteredConversations]
  );

  const handleCreate = async () => {
    if (!token) return;
    setIsCreating(true);
    try {
      await createConversation(token, undefined, selectedProject?.id);
    } finally {
      setIsCreating(false);
    }
  };

  const handleSelect = async (id: string) => {
    if (!token || id === currentConversation?.id) return;
    await selectConversation(token, id);
  };

  const handleDelete = async () => {
    if (!token || !deleteId) return;
    await deleteConversation(token, deleteId);
    setDeleteId(null);
  };

  if (collapsed) {
    return null;
  }

  return (
    <div className="flex flex-col h-full border-r w-64">
      <div className="p-4 border-b space-y-3">
        <Button
          onClick={handleCreate}
          disabled={isCreating}
          className="w-full"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2">
          {filteredConversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              {searchQuery ? "No matching conversations" : "No conversations yet"}
            </div>
          ) : (
            Object.entries(groupedConversations).map(
              ([group, convs]) =>
                convs.length > 0 && (
                  <div key={group} className="mb-4">
                    <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {group}
                    </div>
                    <div className="space-y-1">
                      {convs.map((conversation) => {
                        const project = conversation.project_id
                          ? getProjectById(conversation.project_id)
                          : null;

                        return (
                          <div
                            key={conversation.id}
                            className={cn(
                              "group flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer transition-colors",
                              conversation.id === currentConversation?.id
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted"
                            )}
                            onClick={() => handleSelect(conversation.id)}
                          >
                            {conversation.plan_status ? (
                              <FileText className="h-4 w-4 shrink-0" />
                            ) : (
                              <MessageSquare className="h-4 w-4 shrink-0" />
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <p className="text-sm font-medium truncate flex-1">
                                  {truncate(conversation.title || "New Chat", 18)}
                                </p>
                                {project && !projectFilter && (
                                  <div
                                    className="h-2 w-2 rounded-full shrink-0"
                                    style={{ backgroundColor: project.color || "#6B7280" }}
                                    title={project.name}
                                  />
                                )}
                              </div>
                              <div className="flex items-center gap-1.5">
                                <p
                                  className={cn(
                                    "text-xs",
                                    conversation.id === currentConversation?.id
                                      ? "text-primary-foreground/70"
                                      : "text-muted-foreground"
                                  )}
                                >
                                  {formatRelativeTime(conversation.updated_at)}
                                </p>
                                {conversation.plan_status && (
                                  <Badge
                                    variant={
                                      conversation.plan_status === "APPROVED"
                                        ? "default"
                                        : conversation.plan_status === "PENDING"
                                        ? "secondary"
                                        : "outline"
                                    }
                                    className="h-4 text-[10px] px-1"
                                  >
                                    Plan
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className={cn(
                                "h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity shrink-0",
                                conversation.id === currentConversation?.id
                                  ? "text-primary-foreground hover:text-primary-foreground hover:bg-primary-foreground/20"
                                  : "text-muted-foreground hover:text-destructive"
                              )}
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteId(conversation.id);
                              }}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )
            )
          )}
        </div>
      </ScrollArea>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete the
              conversation and all its messages.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
