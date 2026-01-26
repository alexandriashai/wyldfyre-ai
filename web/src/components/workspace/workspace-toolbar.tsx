"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { workspaceApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  GitBranch,
  Upload,
  RefreshCw,
  Search,
  Save,
  Circle,
  RotateCcw,
} from "lucide-react";
import { BranchSwitcher } from "./branch-switcher";

export function WorkspaceToolbar() {
  const { token } = useAuthStore();
  const { projects, selectedProject, selectProject } = useProjectStore();
  const {
    activeProjectId,
    setActiveProject,
    gitStatus,
    setGitStatus,
    deployStatus,
    setDeployStatus,
    autoSave,
    setAutoSave,
    setSearchOpen,
  } = useWorkspaceStore();

  const [isDeploying, setIsDeploying] = useState(false);
  const [showGitPopover, setShowGitPopover] = useState(false);

  const fetchGitStatus = useCallback(async () => {
    if (!token || !activeProjectId) return;
    try {
      const status = await workspaceApi.getGitStatus(token, activeProjectId);
      setGitStatus(status);
    } catch {
      // Git might not be initialized
      setGitStatus(null);
    }
  }, [token, activeProjectId, setGitStatus]);

  // Fetch git status when project changes
  useEffect(() => {
    if (token && activeProjectId) {
      fetchGitStatus();
    }
  }, [token, activeProjectId, fetchGitStatus]);

  const handleDeploy = async () => {
    if (!token || !activeProjectId || isDeploying) return;
    setIsDeploying(true);
    setDeployStatus({ isDeploying: true, stage: "Starting deploy...", progress: 0, error: null });

    try {
      const result = await workspaceApi.deploy(token, activeProjectId);
      setDeployStatus({
        isDeploying: false,
        stage: null,
        progress: 100,
        error: result.status === "failed" ? result.message : null,
      });
      // Refresh git status after deploy
      await fetchGitStatus();
    } catch (err: any) {
      setDeployStatus({
        isDeploying: false,
        stage: null,
        progress: 0,
        error: err.message || "Deploy failed",
      });
    } finally {
      setIsDeploying(false);
    }
  };

  const handleProjectChange = (projectId: string) => {
    setActiveProject(projectId);
    const project = projects.find((p) => p.id === projectId);
    if (project && token) {
      selectProject(project);
    }
  };

  const modifiedCount = gitStatus
    ? gitStatus.modified.length + gitStatus.untracked.length + gitStatus.staged.length
    : 0;

  const healthDot = "bg-gray-400"; // Default unknown

  return (
    <div className="flex h-10 items-center gap-2 border-b bg-card px-3 shrink-0">
      {/* Project Selector */}
      <Select value={activeProjectId || ""} onValueChange={handleProjectChange}>
        <SelectTrigger className="h-7 w-[180px] text-xs">
          <SelectValue placeholder="Select project" />
        </SelectTrigger>
        <SelectContent>
          {projects.filter((p) => p.status === "active").map((project) => (
            <SelectItem key={project.id} value={project.id} className="text-xs">
              {project.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Branch Switcher */}
      {activeProjectId && (
        <BranchSwitcher
          projectId={activeProjectId}
          onBranchChange={fetchGitStatus}
        />
      )}

      {/* File Changes Badge */}
      {gitStatus && modifiedCount > 0 && (
        <Popover open={showGitPopover} onOpenChange={setShowGitPopover}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 gap-1.5 text-xs px-2">
              <span className="rounded-full bg-amber-500/20 text-amber-600 px-1.5 text-[10px] font-medium">
                {modifiedCount} changed
              </span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-64 p-3" align="start">
            <div className="space-y-2">
              <p className="text-xs font-medium">Uncommitted Changes</p>
              {gitStatus.modified.length > 0 && (
                <div>
                  <p className="text-xs text-amber-600 font-medium">Modified ({gitStatus.modified.length})</p>
                  {gitStatus.modified.slice(0, 5).map((f) => (
                    <p key={f.path} className="text-[10px] text-muted-foreground truncate">{f.path}</p>
                  ))}
                </div>
              )}
              {gitStatus.untracked.length > 0 && (
                <div>
                  <p className="text-xs text-green-600 font-medium">Untracked ({gitStatus.untracked.length})</p>
                  {gitStatus.untracked.slice(0, 5).map((f) => (
                    <p key={f} className="text-[10px] text-muted-foreground truncate">{f}</p>
                  ))}
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>
      )}

      <div className="flex-1" />

      {/* Search */}
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={() => setSearchOpen(true)}
        title="Search files (Ctrl+Shift+F)"
      >
        <Search className="h-3.5 w-3.5" />
      </Button>

      {/* Auto-save toggle */}
      <Button
        variant={autoSave ? "secondary" : "ghost"}
        size="sm"
        className="h-7 text-xs px-2 hidden sm:flex"
        onClick={() => setAutoSave(!autoSave)}
        title={autoSave ? "Auto-save enabled" : "Auto-save disabled"}
      >
        <Save className="h-3.5 w-3.5 mr-1" />
        {autoSave ? "Auto" : "Manual"}
      </Button>

      {/* Refresh git */}
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={fetchGitStatus}
        title="Refresh git status"
      >
        <RefreshCw className="h-3.5 w-3.5" />
      </Button>

      {/* Deploy */}
      <Button
        variant="default"
        size="sm"
        className="h-7 text-xs gap-1.5"
        onClick={handleDeploy}
        disabled={isDeploying || !activeProjectId}
      >
        <Upload className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">
          {isDeploying ? "Deploying..." : "Deploy"}
        </span>
      </Button>
    </div>
  );
}
