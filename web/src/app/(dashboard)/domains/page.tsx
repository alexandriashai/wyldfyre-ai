"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { domainsApi, projectsApi, ApiError, Domain } from "@/lib/api";
import { DomainTable } from "@/components/domains/domain-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2, Filter, RefreshCw } from "lucide-react";
import { toast } from "@/hooks/useToast";

export default function DomainsPage() {
  const { token } = useAuthStore();
  const { projects, fetchProjects } = useProjectStore();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [newDomainProjectId, setNewDomainProjectId] = useState<string>("");
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [isAdding, setIsAdding] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [editDomain, setEditDomain] = useState<Domain | null>(null);
  const [editProjectId, setEditProjectId] = useState<string>("");
  const [editWebRoot, setEditWebRoot] = useState<string>("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    if (token) {
      fetchProjects(token);
    }
  }, [token, fetchProjects]);

  useEffect(() => {
    fetchDomains();
  }, [token, projectFilter]);

  const fetchDomains = async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const params = projectFilter !== "all" ? { project_id: projectFilter } : undefined;
      const response = await domainsApi.list(token, params);
      setDomains(response);
    } catch (error) {
      console.error("Failed to fetch domains:", error);
      const message = error instanceof ApiError ? error.message : "Failed to load domains";
      toast({
        title: "Error loading domains",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddDomain = async () => {
    if (!token || !newDomain.trim()) return;
    setIsAdding(true);
    try {
      await domainsApi.create(token, {
        domain_name: newDomain.trim(),
        project_id: newDomainProjectId && newDomainProjectId !== "none" ? newDomainProjectId : undefined,
      });
      toast({
        title: "Domain added",
        description: `${newDomain.trim()} has been added successfully.`,
      });
      setNewDomain("");
      setNewDomainProjectId("");
      setIsAddDialogOpen(false);
      fetchDomains();
    } catch (error) {
      console.error("Failed to add domain:", error);
      const message = error instanceof ApiError ? error.message : "Failed to add domain";
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeploy = async (domainName: string) => {
    if (!token) return;
    try {
      const result = await domainsApi.deploy(token, domainName);
      toast({
        title: "Deployment started",
        description: result.message || `Deploying ${domainName}...`,
      });
    } catch (error) {
      console.error("Failed to deploy:", error);
      const message = error instanceof ApiError ? error.message : "Failed to deploy domain";
      toast({
        title: "Deploy failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (domainName: string) => {
    if (!token) return;
    try {
      await domainsApi.delete(token, domainName);
      toast({
        title: "Domain deleted",
        description: `${domainName} has been removed.`,
      });
      setDeleteConfirm(null);
      fetchDomains();
    } catch (error) {
      console.error("Failed to delete domain:", error);
      const message = error instanceof ApiError ? error.message : "Failed to delete domain";
      toast({
        title: "Delete failed",
        description: message,
        variant: "destructive",
      });
      setDeleteConfirm(null);
    }
  };

  const handleEditOpen = (domain: Domain) => {
    setEditDomain(domain);
    setEditProjectId(domain.project_id || "none");
    setEditWebRoot(domain.web_root || "");
  };

  const handleUpdate = async () => {
    if (!token || !editDomain) return;
    setIsUpdating(true);
    try {
      await domainsApi.update(token, editDomain.domain_name, {
        project_id: editProjectId === "none" ? null : editProjectId,
        web_root: editWebRoot || undefined,
      });
      toast({
        title: "Domain updated",
        description: `${editDomain.domain_name} has been updated.`,
      });
      setEditDomain(null);
      fetchDomains();
    } catch (error) {
      console.error("Failed to update domain:", error);
      const message = error instanceof ApiError ? error.message : "Failed to update domain";
      toast({
        title: "Update failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSync = async () => {
    if (!token || !editDomain) return;
    setIsSyncing(true);
    try {
      const result = await domainsApi.sync(token, editDomain.domain_name);
      toast({
        title: "Sync started",
        description: result.message || "Syncing nginx config values...",
      });
      // Refresh the domains list after a short delay to allow sync to complete
      setTimeout(() => {
        fetchDomains();
      }, 2000);
    } catch (error) {
      console.error("Failed to sync domain:", error);
      const message = error instanceof ApiError ? error.message : "Failed to sync domain config";
      toast({
        title: "Sync failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-col gap-4 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Domains</h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Manage your web domains and SSL certificates
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Project Filter */}
          <div className="flex items-center gap-2 flex-1 sm:flex-initial">
            <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
            <Select value={projectFilter} onValueChange={setProjectFilter}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Filter by project" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Projects</SelectItem>
                {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: project.color || "#6B7280" }}
                      />
                      {project.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button className="w-full sm:w-auto">
                <Plus className="h-4 w-4 mr-2" />
                Add Domain
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Domain</DialogTitle>
                <DialogDescription>
                  Add a new domain to your infrastructure. SSL certificates will
                  be automatically provisioned.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="domain">Domain Name</Label>
                  <Input
                    id="domain"
                    placeholder="example.com"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="project">Project (optional)</Label>
                  <Select value={newDomainProjectId} onValueChange={setNewDomainProjectId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a project" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No project</SelectItem>
                      {projects.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          <div className="flex items-center gap-2">
                            <div
                              className="h-2 w-2 rounded-full"
                              style={{ backgroundColor: project.color || "#6B7280" }}
                            />
                            {project.name}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddDomain} disabled={isAdding || !newDomain.trim()}>
                  {isAdding ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    "Add Domain"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          <DomainTable
            domains={domains}
            onDeploy={handleDeploy}
            onDelete={(name) => setDeleteConfirm(name)}
            onEdit={handleEditOpen}
          />
        </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete domain?</DialogTitle>
            <DialogDescription>
              This will remove the domain {deleteConfirm} and all its
              configurations. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit domain dialog */}
      <Dialog open={!!editDomain} onOpenChange={() => setEditDomain(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Domain</DialogTitle>
            <DialogDescription>
              Update settings for {editDomain?.domain_name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-project">Project</Label>
              <Select value={editProjectId} onValueChange={setEditProjectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a project" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No project</SelectItem>
                  {projects.map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: project.color || "#6B7280" }}
                        />
                        {project.name}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-web-root">Web Root</Label>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSync}
                  disabled={isSyncing}
                  className="h-7 text-xs"
                >
                  {isSyncing ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3 mr-1" />
                  )}
                  Sync from nginx
                </Button>
              </div>
              <Input
                id="edit-web-root"
                placeholder="/var/www/example.com"
                value={editWebRoot}
                onChange={(e) => setEditWebRoot(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                The directory path where the website files are stored
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDomain(null)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={isUpdating}>
              {isUpdating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
