"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useChatStore } from "@/stores/chat-store";
import { cn, formatRelativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  MoreVertical,
  MessageSquare,
  ClipboardList,
  Archive,
  Trash2,
  Pencil,
  FolderKanban,
  Loader2,
  Globe,
} from "lucide-react";
import { projectsApi, ProjectWithStats } from "@/lib/api";

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

export default function ProjectsPage() {
  const router = useRouter();
  const { token } = useAuthStore();
  const {
    projects,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
    selectProject,
    isLoading,
  } = useProjectStore();
  const { fetchConversations, setProjectFilter } = useChatStore();

  const [showNewProject, setShowNewProject] = useState(false);
  const [showEditProject, setShowEditProject] = useState<string | null>(null);
  const [showDeleteProject, setShowDeleteProject] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projectColor, setProjectColor] = useState(PROJECT_COLORS[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Project stats
  const [projectStats, setProjectStats] = useState<Record<string, ProjectWithStats>>({});

  useEffect(() => {
    if (token) {
      fetchProjects(token);
    }
  }, [token, fetchProjects]);

  // Fetch detailed stats for each project
  useEffect(() => {
    const fetchStats = async () => {
      if (!token) return;

      const statsMap: Record<string, ProjectWithStats> = {};
      for (const project of projects) {
        try {
          const stats = await projectsApi.get(token, project.id);
          statsMap[project.id] = stats;
        } catch (e) {
          // Ignore errors for individual projects
        }
      }
      setProjectStats(statsMap);
    };

    if (projects.length > 0) {
      fetchStats();
    }
  }, [token, projects]);

  const handleCreateProject = async () => {
    if (!token || !projectName.trim()) return;

    setIsSubmitting(true);
    try {
      await createProject(token, {
        name: projectName.trim(),
        description: projectDescription.trim() || undefined,
        color: projectColor,
      });
      setShowNewProject(false);
      resetForm();
    } catch (error) {
      console.error("Failed to create project:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateProject = async () => {
    if (!token || !showEditProject || !projectName.trim()) return;

    setIsSubmitting(true);
    try {
      await updateProject(token, showEditProject, {
        name: projectName.trim(),
        description: projectDescription.trim() || undefined,
        color: projectColor,
      });
      setShowEditProject(null);
      resetForm();
    } catch (error) {
      console.error("Failed to update project:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProject = async (archive: boolean) => {
    if (!token || !showDeleteProject) return;

    setIsSubmitting(true);
    try {
      await deleteProject(token, showDeleteProject, archive);
      setShowDeleteProject(null);
    } catch (error) {
      console.error("Failed to delete project:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectProject = async (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    if (project) {
      selectProject(project);
      setProjectFilter(project.id);
      if (token) {
        await fetchConversations(token, project.id);
      }
      router.push("/chat");
    }
  };

  const openEditDialog = (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    if (project) {
      setProjectName(project.name);
      setProjectDescription(project.description || "");
      setProjectColor(project.color || PROJECT_COLORS[0]);
      setShowEditProject(projectId);
    }
  };

  const resetForm = () => {
    setProjectName("");
    setProjectDescription("");
    setProjectColor(PROJECT_COLORS[0]);
  };

  if (isLoading && projects.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container py-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-muted-foreground">
            Organize your conversations and tasks by project
          </p>
        </div>
        <Button onClick={() => setShowNewProject(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Project
        </Button>
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FolderKanban className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
            <p className="text-muted-foreground text-center mb-4 max-w-md">
              Projects help you organize conversations and tasks for different
              site builds or work streams. Create your first project to get started.
            </p>
            <Button onClick={() => setShowNewProject(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => {
            const stats = projectStats[project.id];
            return (
              <Card
                key={project.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => handleSelectProject(project.id)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-4 w-4 rounded"
                        style={{ backgroundColor: project.color || "#6B7280" }}
                      />
                      <CardTitle className="text-lg">{project.name}</CardTitle>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            openEditDialog(project.id);
                          }}
                        >
                          <Pencil className="h-4 w-4 mr-2" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowDeleteProject(project.id);
                          }}
                          className="text-destructive"
                        >
                          <Archive className="h-4 w-4 mr-2" />
                          Archive
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  {project.description && (
                    <CardDescription className="line-clamp-2">
                      {project.description}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <MessageSquare className="h-4 w-4" />
                      <span>{stats?.conversation_count || 0}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <ClipboardList className="h-4 w-4" />
                      <span>{stats?.task_count || 0}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Globe className="h-4 w-4" />
                      <span>{stats?.domain_count || 0}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Created {formatRelativeTime(project.created_at)}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

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
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-desc">Description (optional)</Label>
              <Input
                id="project-desc"
                placeholder="Brief description of the project"
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
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
                      projectColor === color
                        ? "ring-2 ring-offset-2 ring-primary"
                        : "hover:scale-110"
                    )}
                    style={{ backgroundColor: color }}
                    onClick={() => setProjectColor(color)}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowNewProject(false);
                resetForm();
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateProject}
              disabled={!projectName.trim() || isSubmitting}
            >
              {isSubmitting ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Project Dialog */}
      <Dialog
        open={!!showEditProject}
        onOpenChange={() => {
          setShowEditProject(null);
          resetForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Project</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-project-name">Project Name</Label>
              <Input
                id="edit-project-name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-project-desc">Description</Label>
              <Input
                id="edit-project-desc"
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
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
                      projectColor === color
                        ? "ring-2 ring-offset-2 ring-primary"
                        : "hover:scale-110"
                    )}
                    style={{ backgroundColor: color }}
                    onClick={() => setProjectColor(color)}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowEditProject(null);
                resetForm();
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateProject}
              disabled={!projectName.trim() || isSubmitting}
            >
              {isSubmitting ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!showDeleteProject}
        onOpenChange={() => setShowDeleteProject(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive Project?</DialogTitle>
            <DialogDescription>
              This will archive the project. Conversations and tasks will remain
              but the project will be hidden from the active list.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteProject(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleDeleteProject(true)}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Archiving..." : "Archive Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
