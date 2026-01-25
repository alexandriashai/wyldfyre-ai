"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { workspaceApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { X, GitBranch } from "lucide-react";

const DiffEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.DiffEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    ),
  }
);

export function GitDiffEditor() {
  const { token } = useAuthStore();
  const { diffFilePath, diffMode, setDiffMode, activeProjectId, openFiles } =
    useWorkspaceStore();
  const [originalContent, setOriginalContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Detect theme
  const [editorTheme, setEditorTheme] = useState("vs-dark");
  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setEditorTheme(isDark ? "vs-dark" : "vs");
    const observer = new MutationObserver(() => {
      setEditorTheme(document.documentElement.classList.contains("dark") ? "vs-dark" : "vs");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  // Fetch original (git HEAD) content
  useEffect(() => {
    if (!token || !activeProjectId || !diffFilePath || !diffMode) return;

    const fetchOriginal = async () => {
      setIsLoading(true);
      try {
        const result = await workspaceApi.getGitFileContent(
          token,
          activeProjectId,
          diffFilePath,
          "HEAD"
        );
        setOriginalContent(result.content || "");
      } catch {
        // File might be new (not in git)
        setOriginalContent("");
      } finally {
        setIsLoading(false);
      }
    };

    fetchOriginal();
  }, [token, activeProjectId, diffFilePath, diffMode]);

  if (!diffMode || !diffFilePath) return null;

  const currentFile = openFiles.find((f) => f.path === diffFilePath);
  const modifiedContent = currentFile?.content || "";
  const fileName = diffFilePath.split("/").pop() || "";
  const language = currentFile?.language || undefined;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-2">
          <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium">{fileName}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 font-medium">
            Modified
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setDiffMode(false)}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Diff Editor */}
      <div className="flex-1 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <DiffEditor
            original={originalContent}
            modified={modifiedContent}
            language={language}
            theme={editorTheme}
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 13,
              scrollBeyondLastLine: false,
            }}
          />
        )}
      </div>
    </div>
  );
}
