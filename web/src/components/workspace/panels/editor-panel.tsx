"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Button } from "@/components/ui/button";
import { X, Circle, PanelLeftOpen, Image as ImageIcon, Terminal, SplitSquareHorizontal, GitBranch, Blocks, Code2 } from "lucide-react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { cn } from "@/lib/utils";
import { Breadcrumbs } from "../editor/breadcrumbs";
import { GitDiffEditor } from "../editor/diff-editor";

// Dynamically import Monaco to avoid SSR issues
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.default),
  { ssr: false, loading: () => <div className="flex-1 flex items-center justify-center"><div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div> }
);

// Dynamically import GrapesJS Visual Editor
const VisualEditorPanel = dynamic(
  () => import("../visual-editor/visual-editor-panel").then((mod) => mod.VisualEditorPanel),
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
    isTerminalOpen,
    setTerminalOpen,
    splitEditor,
    splitFilePath,
    setSplitEditor,
    diffMode,
    diffFilePath,
    setDiffMode,
    gitStatus,
    activeProjectId,
    setMobileActiveTab,
  } = useWorkspaceStore();

  // Detect mobile viewport
  const [isMobile, setIsMobile] = useState(false);
  const [visualEditorMode, setVisualEditorMode] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const activeFile = openFiles.find((f) => f.path === activeFilePath);
  const isVisualEditable = activeFile && /\.(html?|htm|twig)$/i.test(activeFile.path);

  // Reset visual editor mode when switching to non-HTML file
  useEffect(() => {
    if (!isVisualEditable && visualEditorMode) {
      setVisualEditorMode(false);
    }
  }, [isVisualEditable, visualEditorMode]);

  // Detect theme after mount to avoid SSR hydration mismatch
  const [editorTheme, setEditorTheme] = useState("vs-dark");
  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setEditorTheme(isDark ? "vs-dark" : "vs");

    // Watch for theme changes
    const observer = new MutationObserver(() => {
      const dark = document.documentElement.classList.contains("dark");
      setEditorTheme(dark ? "vs-dark" : "vs");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

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
        {/* Spacer + toolbar buttons */}
        <div className="ml-auto shrink-0 flex items-center gap-0.5 pr-1">
          {/* Visual Editor toggle for HTML files */}
          {isVisualEditable && (
            <Button
              variant={visualEditorMode ? "secondary" : "ghost"}
              size="icon"
              className="h-6 w-6"
              onClick={() => setVisualEditorMode(!visualEditorMode)}
              title={visualEditorMode ? "Switch to Code Editor" : "Switch to Visual Editor"}
            >
              {visualEditorMode ? <Code2 className="h-3.5 w-3.5" /> : <Blocks className="h-3.5 w-3.5" />}
            </Button>
          )}
          {activeFile && gitStatus?.modified?.some((f) => f.path === activeFile.path) && (
            <Button
              variant={diffMode ? "secondary" : "ghost"}
              size="icon"
              className="h-6 w-6"
              onClick={() => {
                if (diffMode && diffFilePath === activeFile.path) {
                  setDiffMode(false);
                } else {
                  setDiffMode(true, activeFile.path);
                }
              }}
              title="Toggle Git Diff"
            >
              <GitBranch className="h-3.5 w-3.5" />
            </Button>
          )}
          {/* Hide split editor button on mobile - not practical on small screens */}
          {!isMobile && (
            <Button
              variant={splitEditor ? "secondary" : "ghost"}
              size="icon"
              className="h-6 w-6"
              onClick={() => {
                if (splitEditor) {
                  setSplitEditor(false);
                } else if (openFiles.length > 1) {
                  const otherFile = openFiles.find((f) => f.path !== activeFilePath);
                  setSplitEditor(true, otherFile?.path || null);
                }
              }}
              title="Split Editor"
              disabled={openFiles.length < 2}
            >
              <SplitSquareHorizontal className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant={isTerminalOpen ? "secondary" : "ghost"}
            size="icon"
            className="h-6 w-6"
            onClick={() => {
              if (isMobile) {
                // On mobile, switch to terminal tab
                setMobileActiveTab("terminal");
              } else {
                // On desktop, toggle terminal panel
                setTerminalOpen(!isTerminalOpen);
              }
            }}
            title="Toggle Terminal (Ctrl+`)"
          >
            <Terminal className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Breadcrumbs */}
      <Breadcrumbs />

      {/* Editor content */}
      <div className="flex-1 min-h-0">
        {diffMode && diffFilePath ? (
          <GitDiffEditor />
        ) : visualEditorMode && isVisualEditable ? (
          <VisualEditorPanel />
        ) : activeFile?.is_binary ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <div className="text-center space-y-2">
              <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">Binary file</p>
              <p className="text-xs text-muted-foreground">{activeFile.path}</p>
            </div>
          </div>
        ) : activeFile && splitEditor ? (
          <PanelGroup direction="horizontal">
            <Panel defaultSize={50} minSize={25}>
              <MonacoEditor
                height="100%"
                language={activeFile.language || "plaintext"}
                value={activeFile.content}
                theme={editorTheme}
                onChange={(value) => {
                  if (value !== undefined) {
                    updateFileContent(activeFile.path, value);
                  }
                }}
                options={{
                  minimap: { enabled: false },
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
            </Panel>
            <PanelResizeHandle className="w-[3px] bg-border hover:bg-primary/50 transition-colors" />
            <Panel defaultSize={50} minSize={25}>
              {(() => {
                const splitFile = openFiles.find((f) => f.path === splitFilePath);
                if (!splitFile) return (
                  <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                    No file selected for split view
                  </div>
                );
                return (
                  <div className="flex flex-col h-full">
                    <div className="flex items-center justify-between px-2 py-1 border-b bg-muted/30 shrink-0">
                      <span className="text-[11px] text-muted-foreground truncate">
                        {splitFile.path.split("/").pop()}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5"
                        onClick={() => setSplitEditor(false)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                    <div className="flex-1 min-h-0">
                      <MonacoEditor
                        height="100%"
                        language={splitFile.language || "plaintext"}
                        value={splitFile.content}
                        theme={editorTheme}
                        onChange={(value) => {
                          if (value !== undefined) {
                            updateFileContent(splitFile.path, value);
                          }
                        }}
                        options={{
                          minimap: { enabled: false },
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
                    </div>
                  </div>
                );
              })()}
            </Panel>
          </PanelGroup>
        ) : activeFile ? (
          <MonacoEditor
            height="100%"
            language={activeFile.language || "plaintext"}
            value={activeFile.content}
            theme={editorTheme}
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
