"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { domainsApi } from "@/lib/api";
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
import { Plus, Loader2 } from "lucide-react";

interface Domain {
  id: string;
  domain_name: string;
  status: string;
  ssl_status: string;
  created_at: string;
}

export default function DomainsPage() {
  const { token } = useAuthStore();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    fetchDomains();
  }, [token]);

  const fetchDomains = async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const response = await domainsApi.list(token);
      setDomains(response.domains);
    } catch (error) {
      console.error("Failed to fetch domains:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddDomain = async () => {
    if (!token || !newDomain.trim()) return;
    setIsAdding(true);
    try {
      await domainsApi.create(token, { domain_name: newDomain.trim() });
      setNewDomain("");
      setIsAddDialogOpen(false);
      fetchDomains();
    } catch (error) {
      console.error("Failed to add domain:", error);
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeploy = async (domainName: string) => {
    if (!token) return;
    try {
      await domainsApi.deploy(token, domainName, { type: "git" });
      // Show success notification
    } catch (error) {
      console.error("Failed to deploy:", error);
    }
  };

  const handleDelete = async (domainName: string) => {
    if (!token) return;
    try {
      await domainsApi.delete(token, domainName);
      setDeleteConfirm(null);
      fetchDomains();
    } catch (error) {
      console.error("Failed to delete domain:", error);
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
