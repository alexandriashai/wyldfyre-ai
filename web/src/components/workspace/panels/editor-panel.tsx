"use client";

import dynamic from "next/dynamic";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Button } from "@/components/ui/button";
import { X, Circle, PanelLeftOpen, Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// Dynamically import Monaco to avoid SSR issues
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.default),
  { ssr: false, loading: () => <div className="flex-1 flex items-center justify-center"><div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div> }
);

interface EditorPanelProps {
  onSave?: () => void;
}

export function EditorPanel({ onSave }: EditorPanelProps) {
  const {
    openFiles,
    activeFilePath,
    setActiveFile,
    closeFile,
    updateFileContent,
    isFileTreeCollapsed,
    setFileTreeCollapsed,
    activeProjectId,
  } = useWorkspaceStore();

  const activeFile = openFiles.find((f) => f.path === activeFilePath);

  // Detect if we're in dark mode
  const isDark = typeof window !== "undefined" &&
    document.documentElement.classList.contains("dark");

  if (openFiles.length === 0) {
    return (
      <div className="flex flex-col h-full bg-background">
        {isFileTreeCollapsed && (
          <div className="border-b px-2 py-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setFileTreeCollapsed(false)}
            >
              <PanelLeftOpen className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-1">
            <p className="text-sm text-muted-foreground">No file open</p>
            <p className="text-xs text-muted-foreground">
              Select a file from the tree to start editing
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Tab bar */}
      <div className="flex items-center border-b shrink-0 overflow-x-auto">
        {isFileTreeCollapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 ml-1"
            onClick={() => setFileTreeCollapsed(false)}
          >
            <PanelLeftOpen className="h-3.5 w-3.5" />
          </Button>
        )}
        {openFiles.map((file) => (
          <div
            key={file.path}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 text-xs border-r cursor-pointer hover:bg-muted/50 shrink-0 max-w-[160px]",
              file.path === activeFilePath && "bg-background border-b-0 border-b-2 border-b-primary"
            )}
            onClick={() => setActiveFile(file.path)}
          >
            {file.isDirty && (
              <Circle className="h-2 w-2 fill-amber-500 text-amber-500 shrink-0" />
            )}
            <span className="truncate">{file.path.split("/").pop()}</span>
            <button
              className="ml-1 p-0.5 rounded hover:bg-muted shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                closeFile(file.path);
              }}
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </div>
        ))}
      </div>

      {/* Editor content */}
      <div className="flex-1 min-h-0">
        {activeFile?.is_binary ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <div className="text-center space-y-2">
              <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">Binary file</p>
              <p className="text-xs text-muted-foreground">{activeFile.path}</p>
            </div>
          </div>
        ) : activeFile ? (
          <MonacoEditor
            height="100%"
            language={activeFile.language || "plaintext"}
            value={activeFile.content}
            theme={isDark ? "vs-dark" : "light"}
            onChange={(value) => {
              if (value !== undefined) {
                updateFileContent(activeFile.path, value);
              }
            }}
            options={{
              minimap: { enabled: true },
              fontSize: 13,
              wordWrap: "on",
              automaticLayout: true,
              scrollBeyondLastLine: false,
              lineNumbers: "on",
              tabSize: 2,
              renderWhitespace: "selection",
              bracketPairColorization: { enabled: true },
              padding: { top: 8 },
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
