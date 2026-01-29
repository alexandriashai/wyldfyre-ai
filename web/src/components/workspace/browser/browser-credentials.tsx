"use client";

import { useState } from "react";
import { useBrowserStore, TestCredential } from "@/stores/browser-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import {
  Eye,
  EyeOff,
  Key,
  MoreVertical,
  Pencil,
  Plus,
  Trash2,
  Copy,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BrowserCredentialsProps {
  projectId: string;
  onSelectCredential?: (credential: TestCredential) => void;
  selectionMode?: boolean;
}

export function BrowserCredentials({
  projectId,
  onSelectCredential,
  selectionMode = false,
}: BrowserCredentialsProps) {
  const { credentials, addCredential, updateCredential, deleteCredential } =
    useBrowserStore();
  const projectCredentials = credentials[projectId] || [];

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingCredential, setEditingCredential] =
    useState<TestCredential | null>(null);
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>(
    {}
  );
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    label: "",
    username: "",
    password: "",
    domain: "",
    notes: "",
  });

  const resetForm = () => {
    setFormData({
      label: "",
      username: "",
      password: "",
      domain: "",
      notes: "",
    });
    setEditingCredential(null);
  };

  const handleSave = () => {
    if (!formData.label || !formData.username || !formData.password) return;

    if (editingCredential) {
      updateCredential(projectId, editingCredential.id, formData);
    } else {
      addCredential(projectId, formData);
    }

    resetForm();
    setIsAddDialogOpen(false);
  };

  const handleEdit = (credential: TestCredential) => {
    setFormData({
      label: credential.label,
      username: credential.username,
      password: credential.password,
      domain: credential.domain || "",
      notes: credential.notes || "",
    });
    setEditingCredential(credential);
    setIsAddDialogOpen(true);
  };

  const handleDelete = (id: string) => {
    deleteCredential(projectId, id);
  };

  const togglePasswordVisibility = (id: string) => {
    setShowPasswords((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSelect = (credential: TestCredential) => {
    if (onSelectCredential) {
      onSelectCredential(credential);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Test Credentials</span>
          <Badge variant="secondary" className="h-5 px-1.5 text-xs">
            {projectCredentials.length}
          </Badge>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={(open) => {
          setIsAddDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 px-2">
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>
                {editingCredential ? "Edit Credential" : "Add Test Credential"}
              </DialogTitle>
              <DialogDescription>
                Store test credentials for browser automation. These are saved
                locally and used when the agent needs to authenticate.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="label">Label *</Label>
                <Input
                  id="label"
                  placeholder="e.g., Admin Account, Test User"
                  value={formData.label}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, label: e.target.value }))
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="domain">Domain (optional)</Label>
                <Input
                  id="domain"
                  placeholder="e.g., dev.blackbook.reviews"
                  value={formData.domain}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, domain: e.target.value }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Helps identify which site this credential is for
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="username">Username / Email *</Label>
                <Input
                  id="username"
                  placeholder="username or email"
                  value={formData.username}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      username: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password *</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="password"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      password: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="notes">Notes (optional)</Label>
                <Input
                  id="notes"
                  placeholder="e.g., Has admin permissions, Use for provider tests"
                  value={formData.notes}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, notes: e.target.value }))
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  resetForm();
                  setIsAddDialogOpen(false);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={
                  !formData.label || !formData.username || !formData.password
                }
              >
                {editingCredential ? "Save Changes" : "Add Credential"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {projectCredentials.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No test credentials saved</p>
              <p className="text-xs mt-1">
                Add credentials to use during browser automation
              </p>
            </div>
          ) : (
            projectCredentials.map((credential) => (
              <Card
                key={credential.id}
                className={cn(
                  "cursor-default",
                  selectionMode &&
                    "cursor-pointer hover:border-primary/50 transition-colors"
                )}
                onClick={() => selectionMode && handleSelect(credential)}
              >
                <CardHeader className="p-3 pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-sm font-medium">
                        {credential.label}
                      </CardTitle>
                      {credential.domain && (
                        <CardDescription className="text-xs">
                          {credential.domain}
                        </CardDescription>
                      )}
                    </div>
                    {!selectionMode && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0"
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleEdit(credential)}>
                            <Pencil className="h-3.5 w-3.5 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => handleDelete(credential.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-3 pt-0 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-16">
                      User:
                    </span>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded flex-1 truncate">
                      {credential.username}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard(credential.username, `user-${credential.id}`);
                      }}
                    >
                      {copiedId === `user-${credential.id}` ? (
                        <Check className="h-3 w-3 text-green-500" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-16">
                      Pass:
                    </span>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded flex-1 truncate">
                      {showPasswords[credential.id]
                        ? credential.password
                        : "••••••••"}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        togglePasswordVisibility(credential.id);
                      }}
                    >
                      {showPasswords[credential.id] ? (
                        <EyeOff className="h-3 w-3" />
                      ) : (
                        <Eye className="h-3 w-3" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard(credential.password, `pass-${credential.id}`);
                      }}
                    >
                      {copiedId === `pass-${credential.id}` ? (
                        <Check className="h-3 w-3 text-green-500" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                  {credential.notes && (
                    <p className="text-xs text-muted-foreground italic">
                      {credential.notes}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
