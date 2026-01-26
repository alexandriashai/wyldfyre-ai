"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { githubApi, GitHubProjectSettings, GitHubRepo, GitHubTestResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
import { Switch } from "@/components/ui/switch";
import {
  Github,
  Loader2,
  CheckCircle,
  AlertCircle,
  Plus,
  Link,
  ExternalLink,
  Key,
  RefreshCw,
  Eye,
  EyeOff,
  Unlink,
  Lock,
  Globe,
} from "lucide-react";

interface GitHubProjectSettingsCardProps {
  projectId: string;
  projectName: string;
}

export function GitHubProjectSettingsCard({ projectId, projectName }: GitHubProjectSettingsCardProps) {
  const { token } = useAuthStore();
  const [settings, setSettings] = useState<GitHubProjectSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // PAT override state
  const [showPatSection, setShowPatSection] = useState(false);
  const [newPat, setNewPat] = useState("");
  const [showPat, setShowPat] = useState(false);

  // Create repo dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createRepoName, setCreateRepoName] = useState(projectName.toLowerCase().replace(/\s+/g, "-"));
  const [createRepoDesc, setCreateRepoDesc] = useState("");
  const [createRepoPrivate, setCreateRepoPrivate] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  // Link repo dialog state
  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [availableRepos, setAvailableRepos] = useState<GitHubRepo[]>([]);
  const [selectedRepoUrl, setSelectedRepoUrl] = useState("");
  const [manualRepoUrl, setManualRepoUrl] = useState("");
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);
  const [isLinking, setIsLinking] = useState(false);

  // Fetch settings on mount
  useEffect(() => {
    if (!token) return;

    setIsLoading(true);
    githubApi.getProjectSettings(token, projectId)
      .then(setSettings)
      .catch(() => {
        setMessage({ type: "error", text: "Failed to load GitHub settings" });
      })
      .finally(() => setIsLoading(false));
  }, [token, projectId]);

  // Fetch available repos when link dialog opens
  useEffect(() => {
    if (!showLinkDialog || !token) return;

    setIsLoadingRepos(true);
    githubApi.listRepos(token)
      .then(setAvailableRepos)
      .catch(() => {})
      .finally(() => setIsLoadingRepos(false));
  }, [showLinkDialog, token]);

  const handleSavePat = async () => {
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      const data = await githubApi.updateProjectSettings(token, projectId, {
        pat: newPat || undefined,
      });
      setSettings(data);
      setNewPat("");
      setShowPatSection(false);
      setMessage({ type: "success", text: "Project PAT saved" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to save PAT" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearPat = async () => {
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      await githubApi.clearProjectSettings(token, projectId);
      setSettings((prev) => prev ? { ...prev, has_override: false } : null);
      setMessage({ type: "success", text: "Project PAT cleared, using global PAT" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to clear PAT" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateRepo = async () => {
    if (!token) return;

    setIsCreating(true);
    setMessage(null);

    try {
      const repo = await githubApi.initRepo(token, projectId, {
        name: createRepoName,
        description: createRepoDesc || undefined,
        private: createRepoPrivate,
      });

      setSettings((prev) => prev ? {
        ...prev,
        repo_url: repo.clone_url,
        repo_name: repo.full_name,
        repo_linked: true,
      } : null);

      setShowCreateDialog(false);
      setMessage({ type: "success", text: `Repository ${repo.full_name} created and linked` });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to create repository" });
    } finally {
      setIsCreating(false);
    }
  };

  const handleLinkRepo = async () => {
    if (!token) return;

    const repoUrl = selectedRepoUrl || manualRepoUrl;
    if (!repoUrl) return;

    setIsLinking(true);
    setMessage(null);

    try {
      await githubApi.linkRepo(token, projectId, {
        repo_url: repoUrl,
        init_git: true,
      });

      // Extract repo name from URL
      const match = repoUrl.match(/github\.com[:/]([^/]+\/[^/.]+)/);
      const repoName = match ? match[1] : repoUrl;

      setSettings((prev) => prev ? {
        ...prev,
        repo_url: repoUrl,
        repo_name: repoName,
        repo_linked: true,
      } : null);

      setShowLinkDialog(false);
      setSelectedRepoUrl("");
      setManualRepoUrl("");
      setMessage({ type: "success", text: `Repository linked successfully` });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to link repository" });
    } finally {
      setIsLinking(false);
    }
  };

  const handleUnlinkRepo = async () => {
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      await githubApi.updateProjectSettings(token, projectId, {
        repo_url: "",
      });
      setSettings((prev) => prev ? {
        ...prev,
        repo_url: null,
        repo_name: null,
        repo_linked: false,
      } : null);
      setMessage({ type: "success", text: "Repository unlinked" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to unlink repository" });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Github className="h-5 w-5" />
          <CardTitle>GitHub Repository</CardTitle>
        </div>
        <CardDescription>
          Link this project to a GitHub repository for version control
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {message && (
          <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
            message.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
          }`}>
            {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {message.text}
          </div>
        )}

        {/* Repository Info or Setup */}
        {settings?.repo_linked ? (
          <div className="space-y-4">
            <div className="rounded-lg border p-4 bg-muted/50">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{settings.repo_name}</p>
                  <p className="text-xs text-muted-foreground font-mono">{settings.repo_url}</p>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`https://github.com/${settings.repo_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                  <Button variant="ghost" size="sm" onClick={handleUnlinkRepo} disabled={isSaving}>
                    <Unlink className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex gap-3">
            {/* Create New Repo Dialog */}
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button variant="outline" className="flex-1">
                  <Plus className="h-4 w-4 mr-2" />
                  Create New Repository
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create GitHub Repository</DialogTitle>
                  <DialogDescription>
                    Create a new repository and link it to this project
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="repo-name">Repository Name</Label>
                    <Input
                      id="repo-name"
                      value={createRepoName}
                      onChange={(e) => setCreateRepoName(e.target.value)}
                      placeholder="my-project"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="repo-desc">Description (Optional)</Label>
                    <Input
                      id="repo-desc"
                      value={createRepoDesc}
                      onChange={(e) => setCreateRepoDesc(e.target.value)}
                      placeholder="A brief description of your project"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {createRepoPrivate ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
                      <Label>Private Repository</Label>
                    </div>
                    <Switch checked={createRepoPrivate} onCheckedChange={setCreateRepoPrivate} />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateRepo} disabled={isCreating || !createRepoName}>
                    {isCreating ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating...</>
                    ) : (
                      "Create Repository"
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Link Existing Repo Dialog */}
            <Dialog open={showLinkDialog} onOpenChange={setShowLinkDialog}>
              <DialogTrigger asChild>
                <Button variant="outline" className="flex-1">
                  <Link className="h-4 w-4 mr-2" />
                  Link Existing Repository
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Link GitHub Repository</DialogTitle>
                  <DialogDescription>
                    Connect an existing repository to this project
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Select Repository</Label>
                    {isLoadingRepos ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      <Select value={selectedRepoUrl} onValueChange={setSelectedRepoUrl}>
                        <SelectTrigger>
                          <SelectValue placeholder="Choose a repository..." />
                        </SelectTrigger>
                        <SelectContent>
                          {availableRepos.map((repo) => (
                            <SelectItem key={repo.id} value={repo.clone_url}>
                              <div className="flex items-center gap-2">
                                {repo.private ? <Lock className="h-3 w-3" /> : <Globe className="h-3 w-3" />}
                                {repo.full_name}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-background px-2 text-muted-foreground">Or enter URL</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="repo-url">Repository URL</Label>
                    <Input
                      id="repo-url"
                      value={manualRepoUrl}
                      onChange={(e) => {
                        setManualRepoUrl(e.target.value);
                        setSelectedRepoUrl("");
                      }}
                      placeholder="https://github.com/user/repo"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowLinkDialog(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleLinkRepo}
                    disabled={isLinking || (!selectedRepoUrl && !manualRepoUrl)}
                  >
                    {isLinking ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Linking...</>
                    ) : (
                      "Link Repository"
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}

        <Separator />

        {/* PAT Override Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>PAT Override</Label>
              <p className="text-xs text-muted-foreground">
                {settings?.has_override
                  ? "This project uses a custom PAT"
                  : "Using global PAT (from settings)"}
              </p>
            </div>
            <Badge variant="outline" className={settings?.has_override ? "text-blue-500 border-blue-500/30" : ""}>
              {settings?.has_override ? "Project Override" : "Using Global"}
            </Badge>
          </div>

          {showPatSection ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    type={showPat ? "text" : "password"}
                    value={newPat}
                    onChange={(e) => setNewPat(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPat(!showPat)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPat ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSavePat} disabled={isSaving || !newPat}>
                  {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowPatSection(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setShowPatSection(true)}>
                <Key className="h-3.5 w-3.5 mr-1.5" />
                Set Project PAT
              </Button>
              {settings?.has_override && (
                <Button size="sm" variant="outline" onClick={handleClearPat} disabled={isSaving}>
                  Clear Override
                </Button>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
