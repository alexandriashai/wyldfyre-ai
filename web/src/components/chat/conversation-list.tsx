"use client";

import { useState } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn, formatRelativeTime, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MessageSquare, Plus, Trash2 } from "lucide-react";

export function ConversationList() {
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    selectConversation,
    createConversation,
    deleteConversation,
  } = useChatStore();

  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!token) return;
    setIsCreating(true);
    try {
      await createConversation(token);
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

  return (
    <div className="flex flex-col h-full border-r w-64">
      <div className="p-4 border-b">
        <Button
          onClick={handleCreate}
          disabled={isCreating}
          className="w-full"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No conversations yet
            </div>
          ) : (
            conversations.map((conversation) => (
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
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {truncate(conversation.title || "New Chat", 20)}
                  </p>
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
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity",
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
            ))
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
