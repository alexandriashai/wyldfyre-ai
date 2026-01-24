"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useWorkspaceStore, FileNode } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { workspaceApi } from "@/lib/api";
import {
  ChevronRight,
  ChevronDown,
  File,
  Folder,
  FolderOpen,
  Image,
  FileCode,
  FileText,
  FileJson,
  Star,
  Trash2,
  Pencil,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface FileTreeProps {
  nodes: FileNode[];
  onFileOpen: (path: string) => void;
  onRefresh: () => void;
  depth: number;
}

const FILE_ICONS: Record<string, typeof File> = {
  ".tsx": FileCode,
  ".ts": FileCode,
  ".jsx": FileCode,
  ".js": FileCode,
  ".py": FileCode,
  ".html": FileCode,
  ".css": FileCode,
  ".scss": FileCode,
  ".json": FileJson,
  ".md": FileText,
  ".txt": FileText,
  ".png": Image,
  ".jpg": Image,
  ".jpeg": Image,
  ".gif": Image,
  ".svg": Image,
  ".webp": Image,
};

function getFileIcon(name: string) {
  const ext = "." + name.split(".").pop()?.toLowerCase();
  return FILE_ICONS[ext] || File;
}

export function FileTree({ nodes, onFileOpen, onRefresh, depth }: FileTreeProps) {
  return (
    <div>
      {nodes.map((node) => (
        <FileTreeNode
          key={node.path}
          node={node}
          onFileOpen={onFileOpen}
          onRefresh={onRefresh}
          depth={depth}
        />
      ))}
    </div>
  );
}

interface FileTreeNodeProps {
  node: FileNode;
  onFileOpen: (path: string) => void;
  onRefresh: () => void;
  depth: number;
}

function FileTreeNode({ node, onFileOpen, onRefresh, depth }: FileTreeNodeProps) {
  const { token } = useAuthStore();
  const {
    activeProjectId,
    expandedPaths,
    toggleExpanded,
    activeFilePath,
    pinnedFiles,
    togglePinnedFile,
  } = useWorkspaceStore();

  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.name);
  const [contextMenuOpen, setContextMenuOpen] = useState(false);

  const isExpanded = expandedPaths.has(node.path);
  const isActive = activeFilePath === node.path;
  const isPinned = pinnedFiles.includes(node.path);
  const isDirectory = node.type === "directory";

  const handleClick = () => {
    if (isDirectory) {
      toggleExpanded(node.path);
    } else {
      onFileOpen(node.path);
    }
  };

  const handleDelete = async () => {
    if (!token || !activeProjectId) return;
    try {
      await workspaceApi.deleteFile(token, activeProjectId, node.path);
      onRefresh();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const handleRename = async () => {
    if (!token || !activeProjectId || !renameValue.trim() || renameValue === node.name) {
      setIsRenaming(false);
      return;
    }

    const parentPath = node.path.includes("/")
      ? node.path.substring(0, node.path.lastIndexOf("/"))
      : "";
    const newPath = parentPath ? `${parentPath}/${renameValue.trim()}` : renameValue.trim();

    try {
      await workspaceApi.renameFile(token, activeProjectId, node.path, newPath);
      onRefresh();
    } catch (err) {
      console.error("Rename failed:", err);
    }
    setIsRenaming(false);
  };

  const Icon = isDirectory
    ? (isExpanded ? FolderOpen : Folder)
    : getFileIcon(node.name);

  return (
    <div>
      <DropdownMenu open={contextMenuOpen} onOpenChange={(open) => {
        if (!open) setContextMenuOpen(false);
      }}>
        <DropdownMenuTrigger asChild>
          <div
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs hover:bg-muted/50 transition-colors group",
              isActive && "bg-primary/10 text-primary",
            )}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
            onClick={handleClick}
            onContextMenu={(e) => {
              e.preventDefault();
              setContextMenuOpen(true);
            }}
          >
            {isDirectory && (
              <span className="shrink-0">
                {isExpanded ? (
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3 w-3 text-muted-foreground" />
                )}
              </span>
            )}
            {!isDirectory && <span className="w-3 shrink-0" />}

            <Icon className={cn(
              "h-3.5 w-3.5 shrink-0",
              isDirectory ? "text-amber-500" : "text-muted-foreground"
            )} />

            {isRenaming ? (
              <input
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRename();
                  if (e.key === "Escape") setIsRenaming(false);
                }}
                onBlur={handleRename}
                className="flex-1 text-xs bg-background border rounded px-1 outline-none focus:ring-1 focus:ring-primary min-w-0"
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="truncate flex-1">{node.name}</span>
            )}

            {isPinned && (
              <Star className="h-2.5 w-2.5 text-amber-500 shrink-0 opacity-60" />
            )}
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-40">
          <DropdownMenuItem
            className="text-xs"
            onClick={() => {
              setIsRenaming(true);
              setRenameValue(node.name);
            }}
          >
            <Pencil className="h-3 w-3 mr-2" />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-xs"
            onClick={() => togglePinnedFile(node.path)}
          >
            <Star className="h-3 w-3 mr-2" />
            {isPinned ? "Unpin" : "Pin"}
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-xs text-destructive focus:text-destructive"
            onClick={handleDelete}
          >
            <Trash2 className="h-3 w-3 mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Children */}
      {isDirectory && isExpanded && node.children && (
        <FileTree
          nodes={node.children}
          onFileOpen={onFileOpen}
          onRefresh={onRefresh}
          depth={depth + 1}
        />
      )}
    </div>
  );
}
