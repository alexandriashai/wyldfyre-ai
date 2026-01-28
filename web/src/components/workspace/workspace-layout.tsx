"use client";

import { useEffect, useCallback, useRef } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { workspaceApi } from "@/lib/api";
import { WorkspaceToolbar } from "./workspace-toolbar";
import { FileTreePanel } from "./panels/file-tree-panel";
import { EditorPanel } from "./panels/editor-panel";
import { RightPanel } from "./panels/right-panel";
import { TerminalPanel } from "./panels/terminal-panel";
import { FileChatPanel } from "./panels/file-chat-panel";
import { MobileWorkspace } from "./mobile-workspace";
import { FindInFiles } from "./editor/find-in-files";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";

export function WorkspaceLayout() {
  const { token } = useAuthStore();
  const { projects, selectedProject } = useProjectStore();
  const {
    activeProjectId,
    setActiveProject,
    setFileTree,
    setFileTreeLoading,
    panelSizes,
    setPanelSizes,
    isFileTreeCollapsed,
    isTerminalOpen,
    isFileChatExpanded,
    setFileChatExpanded,
    showHiddenFiles,
    openFile,
    setActiveFile,
    addRecentFile,
    setMobileActiveTab,
    autoSave,
    openFiles,
    activeFilePath,
    updateFileContent,
    markFileSaved,
    branchChangeCounter,
  } = useWorkspaceStore();

  // Initialize active project
  useEffect(() => {
    if (!activeProjectId && selectedProject) {
      setActiveProject(selectedProject.id);
    } else if (!activeProjectId && projects.length > 0) {
      const activeProjects = projects.filter((p) => p.status === "active");
      if (activeProjects.length > 0) {
        setActiveProject(activeProjects[0].id);
      }
    }
  }, [activeProjectId, selectedProject, projects, setActiveProject]);

  // Fetch file tree when project changes or branch changes
  useEffect(() => {
    if (token && activeProjectId) {
      fetchFileTree();
    }
  }, [token, activeProjectId, showHiddenFiles, branchChangeCounter]);

  const fetchFileTree = useCallback(async () => {
    if (!token || !activeProjectId) return;
    setFileTreeLoading(true);
    try {
      const result = await workspaceApi.getFileTree(token, activeProjectId, {
        depth: 4,
        show_hidden: showHiddenFiles,
      });
      setFileTree(result.nodes);
    } catch (err) {
      console.error("Failed to fetch file tree:", err);
      setFileTree([]);
    } finally {
      setFileTreeLoading(false);
    }
  }, [token, activeProjectId, showHiddenFiles, setFileTree, setFileTreeLoading]);

  // Handle file open
  const handleFileOpen = useCallback(async (path: string) => {
    if (!token || !activeProjectId) return;

    // Check if already open
    const existing = openFiles.find((f) => f.path === path);
    if (existing) {
      setActiveFile(path);
      addRecentFile(path);
      return;
    }

    try {
      const result = await workspaceApi.getFileContent(token, activeProjectId, path);
      openFile({
        path: result.path,
        content: result.content,
        originalContent: result.content,
        language: result.language,
        isDirty: false,
        is_binary: result.is_binary,
      });
      addRecentFile(path);
      // Switch to editor tab on mobile
      setMobileActiveTab("editor");
    } catch (err) {
      console.error("Failed to open file:", err);
    }
  }, [token, activeProjectId, openFiles, openFile, setActiveFile, addRecentFile, setMobileActiveTab]);

  // Track in-progress saves to prevent race conditions
  const savingRef = useRef<Set<string>>(new Set());

  // Auto-save debounce
  useEffect(() => {
    if (!autoSave || !token || !activeProjectId) return;

    const dirtyFiles = openFiles.filter((f) => f.isDirty);
    if (dirtyFiles.length === 0) return;

    const timer = setTimeout(async () => {
      for (const file of dirtyFiles) {
        // Skip files already being saved
        if (savingRef.current.has(file.path)) continue;
        savingRef.current.add(file.path);
        try {
          await workspaceApi.writeFileContent(token, activeProjectId, file.path, file.content);
          markFileSaved(file.path);
        } catch (err) {
          console.error("Auto-save failed:", err);
        } finally {
          savingRef.current.delete(file.path);
        }
      }
    }, 10000); // 10 second debounce

    return () => clearTimeout(timer);
  }, [openFiles, autoSave, token, activeProjectId, markFileSaved]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+S: Save current file
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSaveCurrentFile();
      }
      // Ctrl+Shift+F: Find in files
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "F") {
        e.preventDefault();
        useWorkspaceStore.getState().setSearchOpen(true);
      }
      // Ctrl+W: Close current tab
      if ((e.ctrlKey || e.metaKey) && e.key === "w") {
        e.preventDefault();
        if (activeFilePath) {
          useWorkspaceStore.getState().closeFile(activeFilePath);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeFilePath]);

  const handleSaveCurrentFile = async () => {
    if (!token || !activeProjectId || !activeFilePath) return;
    const file = openFiles.find((f) => f.path === activeFilePath);
    if (!file || !file.isDirty) return;

    try {
      await workspaceApi.writeFileContent(token, activeProjectId, file.path, file.content);
      markFileSaved(file.path);
    } catch (err) {
      console.error("Save failed:", err);
    }
  };

  // No project configured
  if (!activeProjectId) {
    return (
      <div className="flex flex-col h-full">
        <WorkspaceToolbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <p className="text-muted-foreground">Select a project to start working</p>
            <p className="text-xs text-muted-foreground">
              Projects need a root_path configured to use the workspace
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      <WorkspaceToolbar />

      {/* Desktop: 3-panel layout */}
      <div className="hidden md:flex flex-1 min-h-0">
        <PanelGroup
          direction="horizontal"
          onLayout={(sizes) => setPanelSizes(sizes)}
        >
          {!isFileTreeCollapsed && (
            <>
              <Panel
                defaultSize={panelSizes[0] || 15}
                minSize={10}
                maxSize={30}
              >
                <FileTreePanel onFileOpen={handleFileOpen} onRefresh={fetchFileTree} />
              </Panel>
              <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 transition-colors" />
            </>
          )}

          <Panel defaultSize={isFileTreeCollapsed ? 70 : (panelSizes[1] || 55)} minSize={30}>
            <PanelGroup direction="vertical">
              {/* Code Editor */}
              <Panel defaultSize={isFileChatExpanded ? (isTerminalOpen ? 50 : 60) : (isTerminalOpen ? 70 : 100)} minSize={20}>
                <EditorPanel onSave={handleSaveCurrentFile} />
              </Panel>

              {/* File Chat - below editor (collapsible) */}
              {isFileChatExpanded && (
                <>
                  <PanelResizeHandle className="h-1 bg-border hover:bg-primary/50 transition-colors cursor-row-resize" />
                  <Panel defaultSize={isTerminalOpen ? 20 : 40} minSize={10}>
                    <FileChatPanel />
                  </Panel>
                </>
              )}

              {/* Terminal */}
              {isTerminalOpen && (
                <>
                  <PanelResizeHandle className="h-1 bg-border hover:bg-primary/50 transition-colors cursor-row-resize" />
                  <Panel defaultSize={30} minSize={15}>
                    <TerminalPanel />
                  </Panel>
                </>
              )}
            </PanelGroup>
          </Panel>

          <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 transition-colors" />

          <Panel defaultSize={panelSizes[2] || 30} minSize={20}>
            <RightPanel />
          </Panel>
        </PanelGroup>
      </div>

      {/* Mobile: Single panel with tabs */}
      <div className="flex md:hidden flex-1 min-h-0">
        <MobileWorkspace
          onFileOpen={handleFileOpen}
          onRefresh={fetchFileTree}
          onSave={handleSaveCurrentFile}
        />
      </div>

      {/* Find in Files overlay */}
      <FindInFiles />
    </div>
  );
}
