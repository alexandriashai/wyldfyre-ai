"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useProjectStore } from "@/stores/project-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  MessageSquare,
  Plus,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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

interface ConversationSidebarProps {
  isCollapsed?: boolean;
  onToggle?: () => void;
}

export function ConversationSidebar({
  isCollapsed = false,
  onToggle,
}: ConversationSidebarProps) {
  const { token } = useAuthStore();
  const {
    conversations,
    currentConversation,
    selectConversation,
    createConversation,
    deleteConversation,
    isLoading,
  } = useChatStore();
  const { selectedProject } = useProjectStore();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);

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

  if (isCollapsed) {
    return (
      <div className="flex flex-col h-full w-12 border-r bg-muted/20">
        <Button
          variant="ghost"
          size="icon"
          className="m-1"
          onClick={onToggle}
          title="Expand sidebar"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="m-1"
          onClick={handleCreateConversation}
          disabled={isLoading}
          title="New conversation"
        >
          <Plus className="h-4 w-4" />
        </Button>
        <div className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            {conversations.map((conv) => (
              <Button
                key={conv.id}
                variant={currentConversation?.id === conv.id ? "secondary" : "ghost"}
                size="icon"
                className="m-1"
                onClick={() => handleSelectConversation(conv.id)}
                title={conv.title}
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            ))}
          </ScrollArea>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-64 border-r bg-muted/20">
      <div className="flex items-center justify-between p-3 border-b">
        <h3 className="font-medium text-sm">Conversations</h3>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleCreateConversation}
            disabled={isLoading}
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onToggle}
            title="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {conversations.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No conversations yet.
              <br />
              Click + to start a new chat.
            </p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={cn(
                  "group flex items-center gap-2 rounded-md p-2 cursor-pointer hover:bg-muted transition-colors",
                  currentConversation?.id === conv.id && "bg-muted"
                )}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <MessageSquare className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{conv.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(conv.updated_at)}
                  </p>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-3 w-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
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
              </div>
            ))
          )}
        </div>
      </ScrollArea>

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
    </div>
  );
}
