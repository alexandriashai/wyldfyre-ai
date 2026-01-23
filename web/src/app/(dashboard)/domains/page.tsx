"use client";

import { useState, useEffect, useMemo } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { domainsApi, ApiError, Domain } from "@/lib/api";
import { DomainTable, getSSLDaysRemaining } from "@/components/domains/domain-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
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
import {
  Plus,
  Loader2,
  Filter,
  RefreshCw,
  ShieldAlert,
  Upload,
  CheckSquare,
  X,
} from "lucide-react";
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

  // Multi-select state
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(new Set());
  const [isBatchDeploying, setIsBatchDeploying] = useState(false);

  // SSL expiry warnings
  const sslWarnings = useMemo(() => {
    return domains.filter((d) => {
      if (!d.ssl_enabled || !d.ssl_expires_at) return false;
      const days = getSSLDaysRemaining(d.ssl_expires_at);
      return days !== null && days <= 30;
    });
  }, [domains]);

  const expiredCount = useMemo(() => {
    return domains.filter((d) => {
      if (!d.ssl_enabled || !d.ssl_expires_at) return false;
      const days = getSSLDaysRemaining(d.ssl_expires_at);
      return days !== null && days <= 0;
    }).length;
  }, [domains]);

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
      toast({ title: "Error loading domains", description: message, variant: "destructive" });
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
      toast({ title: "Domain added", description: `${newDomain.trim()} has been added successfully.` });
      setNewDomain("");
      setNewDomainProjectId("");
      setIsAddDialogOpen(false);
      fetchDomains();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to add domain";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeploy = async (domainName: string) => {
    if (!token) return;
    try {
      const result = await domainsApi.deploy(token, domainName);
      toast({ title: "Deployment started", description: result.message || `Deploying ${domainName}...` });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to deploy domain";
      toast({ title: "Deploy failed", description: message, variant: "destructive" });
    }
  };

  const handleBatchDeploy = async () => {
    if (!token || selectedDomains.size === 0) return;
    setIsBatchDeploying(true);
    const names = Array.from(selectedDomains);

    for (const name of names) {
      try {
        await domainsApi.deploy(token, name);
      } catch (error) {
        console.error(`Deploy failed for ${name}:`, error);
      }
    }

    toast({
      title: "Batch deploy started",
      description: `Deploying ${names.length} domain${names.length > 1 ? "s" : ""}...`,
    });
    setIsBatchDeploying(false);
    setSelectedDomains(new Set());
    setIsSelectMode(false);
  };

  const handleDelete = async (domainName: string) => {
    if (!token) return;
    try {
      await domainsApi.delete(token, domainName);
      toast({ title: "Domain deleted", description: `${domainName} has been removed.` });
      setDeleteConfirm(null);
      fetchDomains();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to delete domain";
      toast({ title: "Delete failed", description: message, variant: "destructive" });
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
      toast({ title: "Domain updated", description: `${editDomain.domain_name} has been updated.` });
      setEditDomain(null);
      fetchDomains();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to update domain";
      toast({ title: "Update failed", description: message, variant: "destructive" });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSync = async () => {
    if (!token || !editDomain) return;
    setIsSyncing(true);
    try {
      const result = await domainsApi.sync(token, editDomain.domain_name);
      toast({ title: "Sync started", description: result.message || "Syncing nginx config values..." });
      setTimeout(() => fetchDomains(), 2000);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to sync domain config";
      toast({ title: "Sync failed", description: message, variant: "destructive" });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleToggleSelect = (name: string) => {
    setSelectedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-col gap-4 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Domains</h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Manage your web domains, SSL certificates, and deployments
          </p>
        </div>

        {/* SSL Warning Banner */}
        {sslWarnings.length > 0 && (
          <Card className="border-yellow-500/50 bg-yellow-500/5">
            <CardContent className="flex items-center gap-3 p-3">
              <ShieldAlert className="h-5 w-5 text-yellow-500 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium">
                  {expiredCount > 0
                    ? `${expiredCount} certificate${expiredCount > 1 ? "s" : ""} expired, ${sslWarnings.length - expiredCount} expiring within 30 days`
                    : `${sslWarnings.length} certificate${sslWarnings.length > 1 ? "s" : ""} expiring within 30 days`
                  }
                </p>
                <p className="text-xs text-muted-foreground">
                  {sslWarnings.map((d) => d.domain_name).join(", ")}
                </p>
              </div>
            </CardContent>
          </Card>
        )}

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
                      <div className="h-2 w-2 rounded-full" style={{ backgroundColor: project.color || "#6B7280" }} />
                      {project.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Select mode toggle */}
          <Button
            variant={isSelectMode ? "secondary" : "outline"}
            size="sm"
            onClick={() => {
              setIsSelectMode(!isSelectMode);
              if (isSelectMode) setSelectedDomains(new Set());
            }}
            className="w-full sm:w-auto"
          >
            <CheckSquare className="h-4 w-4 mr-2" />
            {isSelectMode ? "Cancel" : "Select"}
          </Button>

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
                  <Input id="domain" placeholder="example.com" value={newDomain} onChange={(e) => setNewDomain(e.target.value)} />
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
                            <div className="h-2 w-2 rounded-full" style={{ backgroundColor: project.color || "#6B7280" }} />
                            {project.name}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleAddDomain} disabled={isAdding || !newDomain.trim()}>
                  {isAdding ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Adding...</> : "Add Domain"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Batch actions bar */}
        {isSelectMode && selectedDomains.size > 0 && (
          <div className="flex items-center justify-between rounded-lg border bg-primary/5 p-3">
            <span className="text-sm font-medium">
              {selectedDomains.size} domain{selectedDomains.size > 1 ? "s" : ""} selected
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={handleBatchDeploy}
                disabled={isBatchDeploying}
              >
                {isBatchDeploying ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Deploying...</>
                ) : (
                  <><Upload className="h-3.5 w-3.5 mr-1.5" />Deploy All</>
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => {
                  setSelectedDomains(new Set());
                  setIsSelectMode(false);
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
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
            isSelectMode={isSelectMode}
            selectedDomains={selectedDomains}
            onToggleSelect={handleToggleSelect}
          />
        </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete domain?</DialogTitle>
            <DialogDescription>
              This will remove the domain {deleteConfirm} and all its configurations. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>
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
            <DialogDescription>Update settings for {editDomain?.domain_name}</DialogDescription>
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
                        <div className="h-2 w-2 rounded-full" style={{ backgroundColor: project.color || "#6B7280" }} />
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
                <Button variant="ghost" size="sm" onClick={handleSync} disabled={isSyncing} className="h-7 text-xs">
                  {isSyncing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                  Sync from nginx
                </Button>
              </div>
              <Input id="edit-web-root" placeholder="/var/www/example.com" value={editWebRoot} onChange={(e) => setEditWebRoot(e.target.value)} />
              <p className="text-xs text-muted-foreground">The directory path where the website files are stored</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDomain(null)}>Cancel</Button>
            <Button onClick={handleUpdate} disabled={isUpdating}>
              {isUpdating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</> : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
