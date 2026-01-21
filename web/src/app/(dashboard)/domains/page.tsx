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
import { Plus, Loader2, Filter } from "lucide-react";
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

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Domains</h1>
          <p className="text-muted-foreground">
            Manage your web domains and SSL certificates
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Project Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Select value={projectFilter} onValueChange={setProjectFilter}>
              <SelectTrigger className="w-[180px]">
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
              <Button>
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
    </div>
  );
}
