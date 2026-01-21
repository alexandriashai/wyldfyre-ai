"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  FolderKanban,
  ChevronDown,
  Plus,
  Check,
  Layers,
} from "lucide-react";

interface ProjectSelectorProps {
  collapsed?: boolean;
}

const PROJECT_COLORS = [
  "#3B82F6", // blue
  "#10B981", // green
  "#F59E0B", // amber
  "#EF4444", // red
  "#8B5CF6", // violet
  "#EC4899", // pink
  "#06B6D4", // cyan
  "#84CC16", // lime
];

export function ProjectSelector({ collapsed }: ProjectSelectorProps) {
  const { token } = useAuthStore();
  const {
    projects,
    selectedProject,
    fetchProjects,
    selectProject,
    createProject,
  } = useProjectStore();
  const { fetchConversations, setProjectFilter } = useChatStore();

  const [isOpen, setIsOpen] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectColor, setNewProjectColor] = useState(PROJECT_COLORS[0]);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (token) {
      fetchProjects(token);
    }
  }, [token, fetchProjects]);

  const handleSelectProject = async (project: typeof selectedProject) => {
    selectProject(project);
    setProjectFilter(project?.id || null);
    setIsOpen(false);

    if (token) {
      await fetchConversations(token, project?.id);
    }
  };

  const handleCreateProject = async () => {
    if (!token || !newProjectName.trim()) return;

    setIsCreating(true);
    try {
      const project = await createProject(token, {
        name: newProjectName.trim(),
        color: newProjectColor,
      });
      selectProject(project);
      setProjectFilter(project.id);
      setShowNewProject(false);
      setNewProjectName("");

      await fetchConversations(token, project.id);
    } catch (error) {
      console.error("Failed to create project:", error);
    } finally {
      setIsCreating(false);
    }
  };

  if (collapsed) {
    return (
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10"
          >
            {selectedProject ? (
              <div
                className="h-4 w-4 rounded"
                style={{ backgroundColor: selectedProject.color || "#6B7280" }}
              />
            ) : (
              <Layers className="h-4 w-4" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="right" align="start" className="w-56">
          <DropdownMenuLabel>Projects</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => handleSelectProject(null)}
            className="cursor-pointer"
          >
            <Layers className="h-4 w-4 mr-2" />
            All Projects
            {!selectedProject && <Check className="h-4 w-4 ml-auto" />}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {projects.map((project) => (
            <DropdownMenuItem
              key={project.id}
              onClick={() => handleSelectProject(project)}
              className="cursor-pointer"
            >
              <div
                className="h-3 w-3 rounded mr-2"
                style={{ backgroundColor: project.color || "#6B7280" }}
              />
              <span className="truncate flex-1">{project.name}</span>
              {selectedProject?.id === project.id && (
                <Check className="h-4 w-4 ml-auto" />
              )}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setShowNewProject(true)}
            className="cursor-pointer"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Project
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  return (
    <>
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between"
          >
            <div className="flex items-center gap-2 truncate">
              {selectedProject ? (
                <>
                  <div
                    className="h-3 w-3 rounded shrink-0"
                    style={{ backgroundColor: selectedProject.color || "#6B7280" }}
                  />
                  <span className="truncate">{selectedProject.name}</span>
                </>
              ) : (
                <>
                  <Layers className="h-4 w-4 shrink-0" />
                  <span>All Projects</span>
                </>
              )}
            </div>
            <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56">
          <DropdownMenuLabel>Projects</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => handleSelectProject(null)}
            className="cursor-pointer"
          >
            <Layers className="h-4 w-4 mr-2" />
            All Projects
            {!selectedProject && <Check className="h-4 w-4 ml-auto" />}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {projects.length === 0 ? (
            <div className="px-2 py-4 text-center text-sm text-muted-foreground">
              No projects yet
            </div>
          ) : (
            projects.map((project) => (
              <DropdownMenuItem
                key={project.id}
                onClick={() => handleSelectProject(project)}
                className="cursor-pointer"
              >
                <div
                  className="h-3 w-3 rounded mr-2 shrink-0"
                  style={{ backgroundColor: project.color || "#6B7280" }}
                />
                <span className="truncate flex-1">{project.name}</span>
                {selectedProject?.id === project.id && (
                  <Check className="h-4 w-4 ml-auto shrink-0" />
                )}
              </DropdownMenuItem>
            ))
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setShowNewProject(true)}
            className="cursor-pointer"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Project
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* New Project Dialog */}
      <Dialog open={showNewProject} onOpenChange={setShowNewProject}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
            <DialogDescription>
              Projects help you organize conversations and tasks for different
              site builds or work streams.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="project-name">Project Name</Label>
              <Input
                id="project-name"
                placeholder="e.g., Client Site - ABC Corp"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleCreateProject();
                  }
                }}
              />
            </div>
            <div className="grid gap-2">
              <Label>Color</Label>
              <div className="flex gap-2">
                {PROJECT_COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={cn(
                      "h-8 w-8 rounded-full transition-all",
                      newProjectColor === color
                        ? "ring-2 ring-offset-2 ring-primary"
                        : "hover:scale-110"
                    )}
                    style={{ backgroundColor: color }}
                    onClick={() => setNewProjectColor(color)}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewProject(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateProject}
              disabled={!newProjectName.trim() || isCreating}
            >
              {isCreating ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
