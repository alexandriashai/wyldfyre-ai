"use client";

import { useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { workspaceApi } from "@/lib/api";
import { FileTree } from "../file-tree/file-tree";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  RefreshCw,
  Plus,
  FolderPlus,
  Eye,
  EyeOff,
  Star,
  ChevronLeft,
} from "lucide-react";

interface FileTreePanelProps {
  onFileOpen: (path: string) => void;
  onRefresh: () => void;
}

export function FileTreePanel({ onFileOpen, onRefresh }: FileTreePanelProps) {
  const { token } = useAuthStore();
  const {
    activeProjectId,
    fileTree,
    isFileTreeLoading,
    showHiddenFiles,
    setShowHiddenFiles,
    setFileTreeCollapsed,
    pinnedFiles,
    recentFiles,
  } = useWorkspaceStore();

  const [isCreating, setIsCreating] = useState<"file" | "folder" | null>(null);
  const [newName, setNewName] = useState("");

  const handleCreate = async () => {
    if (!token || !activeProjectId || !newName.trim()) {
      setIsCreating(null);
      return;
    }

    try {
      await workspaceApi.createFile(
        token,
        activeProjectId,
        newName.trim(),
        isCreating === "folder"
      );
      onRefresh();
    } catch (err) {
      console.error("Failed to create:", err);
    }

    setIsCreating(null);
    setNewName("");
  };

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Header */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b shrink-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex-1">
          Files
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={() => setIsCreating("file")}
          title="New file"
        >
          <Plus className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={() => setIsCreating("folder")}
          title="New folder"
        >
          <FolderPlus className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={() => setShowHiddenFiles(!showHiddenFiles)}
          title={showHiddenFiles ? "Hide hidden files" : "Show hidden files"}
        >
          {showHiddenFiles ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={onRefresh}
          title="Refresh"
        >
          <RefreshCw className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5 hidden lg:flex"
          onClick={() => setFileTreeCollapsed(true)}
          title="Collapse file tree"
        >
          <ChevronLeft className="h-3 w-3" />
        </Button>
      </div>

      {/* New file/folder input */}
      {isCreating && (
        <div className="px-2 py-1 border-b">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreate();
              if (e.key === "Escape") setIsCreating(null);
            }}
            onBlur={handleCreate}
            placeholder={isCreating === "folder" ? "Folder name..." : "File name..."}
            className="w-full text-xs bg-background border rounded px-2 py-1 outline-none focus:ring-1 focus:ring-primary"
            autoFocus
          />
        </div>
      )}

      {/* Pinned Files */}
      {pinnedFiles.length > 0 && (
        <div className="px-2 py-1 border-b">
          <p className="text-[10px] font-medium text-muted-foreground uppercase mb-1">Pinned</p>
          {pinnedFiles.map((path) => (
            <button
              key={path}
              onClick={() => onFileOpen(path)}
              className="flex items-center gap-1 w-full text-left text-xs py-0.5 hover:text-primary truncate"
            >
              <Star className="h-2.5 w-2.5 text-amber-500 shrink-0" />
              <span className="truncate">{path.split("/").pop()}</span>
            </button>
          ))}
        </div>
      )}

      {/* File Tree */}
      <ScrollArea className="flex-1">
        {isFileTreeLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : fileTree.length === 0 ? (
          <div className="px-3 py-4 text-center">
            <p className="text-xs text-muted-foreground">
              No files found. Configure the project root_path first.
            </p>
          </div>
        ) : (
          <div className="py-1">
            <FileTree
              nodes={fileTree}
              onFileOpen={onFileOpen}
              onRefresh={onRefresh}
              depth={0}
            />
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
