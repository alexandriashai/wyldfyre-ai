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
import { Textarea } from "@/components/ui/textarea";
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
  DollarSign,
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
  const [projectPrimaryUrl, setProjectPrimaryUrl] = useState("");
  const [projectRootPath, setProjectRootPath] = useState("");
  const [projectAgentContext, setProjectAgentContext] = useState("");
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
        primary_url: projectPrimaryUrl.trim() || undefined,
        root_path: projectRootPath.trim() || undefined,
        agent_context: projectAgentContext.trim() || undefined,
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
        primary_url: projectPrimaryUrl.trim() || undefined,
        root_path: projectRootPath.trim() || undefined,
        agent_context: projectAgentContext.trim() || undefined,
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
      setProjectPrimaryUrl(project.primary_url || "");
      setProjectRootPath(project.root_path || "");
      setProjectAgentContext(project.agent_context || "");
      setProjectColor(project.color || PROJECT_COLORS[0]);
      setShowEditProject(projectId);
    }
  };

  const resetForm = () => {
    setProjectName("");
    setProjectDescription("");
    setProjectPrimaryUrl("");
    setProjectRootPath("");
    setProjectAgentContext("");
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
    <div className="container py-4 sm:py-6 px-4 sm:px-6 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Projects</h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Organize your conversations and tasks by project
          </p>
        </div>
        <Button onClick={() => setShowNewProject(true)} className="w-full sm:w-auto">
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
                    <div className="flex items-center gap-1" title="Conversations">
                      <MessageSquare className="h-3.5 w-3.5" />
                      <span>{stats?.conversation_count || 0}</span>
                    </div>
                    <div className="flex items-center gap-1" title="Tasks">
                      <ClipboardList className="h-3.5 w-3.5" />
                      <span>{stats?.task_count || 0}</span>
                    </div>
                    <div className="flex items-center gap-1" title="Domains">
                      <Globe className="h-3.5 w-3.5" />
                      <span>{stats?.domain_count || 0}</span>
                    </div>
                    <div className="flex items-center gap-1 ml-auto" title="Total Spend">
                      <DollarSign className="h-3.5 w-3.5" />
                      <span>{stats?.total_cost ? stats.total_cost.toFixed(2) : "0.00"}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Updated {formatRelativeTime(project.updated_at)}
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
              <Label htmlFor="project-primary-url">Primary URL (optional)</Label>
              <Input
                id="project-primary-url"
                type="url"
                placeholder="https://example.com"
                value={projectPrimaryUrl}
                onChange={(e) => setProjectPrimaryUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                The main URL for this project. Sets the matching domain as primary.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-root-path">Project Root (optional)</Label>
              <Input
                id="project-root-path"
                placeholder="/home/wyld-web/static/my-site/"
                value={projectRootPath}
                onChange={(e) => setProjectRootPath(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Project base directory for chats, tasks, and git. Auto-derived from primary URL if not set.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-context">Agent Context (optional)</Label>
              <Textarea
                id="project-context"
                placeholder="Instructions or context for AI agents working on this project. Include info about domains, directories, tech stack, etc."
                value={projectAgentContext}
                onChange={(e) => setProjectAgentContext(e.target.value)}
                rows={4}
              />
              <p className="text-xs text-muted-foreground">
                This context will be provided to agents when working on this project
              </p>
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
              <Label htmlFor="edit-project-primary-url">Primary URL</Label>
              <Input
                id="edit-project-primary-url"
                type="url"
                placeholder="https://example.com"
                value={projectPrimaryUrl}
                onChange={(e) => setProjectPrimaryUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                The main URL for this project. Sets the matching domain as primary.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-project-root-path">Project Root</Label>
              <Input
                id="edit-project-root-path"
                placeholder="/home/wyld-web/static/my-site/"
                value={projectRootPath}
                onChange={(e) => setProjectRootPath(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Project base directory for chats, tasks, and git. Auto-derived from primary URL if not set.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-project-context">Agent Context</Label>
              <Textarea
                id="edit-project-context"
                placeholder="Instructions or context for AI agents working on this project"
                value={projectAgentContext}
                onChange={(e) => setProjectAgentContext(e.target.value)}
                rows={4}
              />
              <p className="text-xs text-muted-foreground">
                This context will be provided to agents when working on this project
              </p>
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
