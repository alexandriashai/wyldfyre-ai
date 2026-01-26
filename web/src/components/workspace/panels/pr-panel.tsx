"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { githubApi, GitHubPullRequest, GitHubProjectSettings } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  GitPullRequest,
  Plus,
  ExternalLink,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  GitMerge,
  MessageSquare,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PRPanelProps {
  projectId: string;
}

export function PRPanel({ projectId }: PRPanelProps) {
  const { token } = useAuthStore();
  const { gitStatus } = useWorkspaceStore();
  const [pullRequests, setPullRequests] = useState<GitHubPullRequest[]>([]);
  const [projectSettings, setProjectSettings] = useState<GitHubProjectSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create PR dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [prTitle, setPrTitle] = useState("");
  const [prBody, setPrBody] = useState("");
  const [prBase, setPrBase] = useState("main");
  const [prDraft, setPrDraft] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchPRs = useCallback(async () => {
    if (!token || !projectId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Fetch project settings to check if repo is linked
      const settings = await githubApi.getProjectSettings(token, projectId);
      setProjectSettings(settings);

      if (settings.repo_linked) {
        const prs = await githubApi.listPullRequests(token, projectId);
        setPullRequests(prs);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pull requests");
    } finally {
      setIsLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchPRs();
  }, [fetchPRs]);

  const handleCreatePR = async () => {
    if (!token || !projectId || !prTitle.trim()) return;

    setIsCreating(true);
    setCreateError(null);

    try {
      const currentBranch = gitStatus?.branch || "main";
      const pr = await githubApi.createPullRequest(token, projectId, {
        title: prTitle,
        body: prBody || undefined,
        head: currentBranch,
        base: prBase,
        draft: prDraft,
      });
      setPullRequests((prev) => [pr, ...prev]);
      setShowCreateDialog(false);
      setPrTitle("");
      setPrBody("");
      setPrDraft(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create PR");
    } finally {
      setIsCreating(false);
    }
  };

  const handleMergePR = async (prNumber: number) => {
    if (!token || !projectId) return;

    try {
      await githubApi.mergePullRequest(token, projectId, prNumber, {});
      await fetchPRs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to merge PR");
    }
  };

  const getStatusBadge = (pr: GitHubPullRequest) => {
    if (pr.state === "merged") {
      return (
        <Badge variant="secondary" className="bg-purple-500/15 text-purple-600 border-purple-500/30">
          <GitMerge className="h-3 w-3 mr-1" />
          Merged
        </Badge>
      );
    }
    if (pr.state === "closed") {
      return (
        <Badge variant="secondary" className="bg-red-500/15 text-red-600 border-red-500/30">
          Closed
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="bg-green-500/15 text-green-600 border-green-500/30">
        <Clock className="h-3 w-3 mr-1" />
        Open
      </Badge>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!projectSettings?.repo_linked) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <GitPullRequest className="h-12 w-12 text-muted-foreground/50 mb-4" />
        <h3 className="font-medium mb-2">No Repository Linked</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Link a GitHub repository to view and create pull requests.
        </p>
        <Button variant="outline" asChild>
          <a href={`/workspace/settings`}>
            Configure GitHub
          </a>
        </Button>
      </div>
    );
  }

  const currentBranch = gitStatus?.branch || "main";
  const canCreatePR = currentBranch !== "main" && currentBranch !== "master";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <GitPullRequest className="h-4 w-4" />
          <h3 className="font-medium text-sm">Pull Requests</h3>
          <Badge variant="secondary" className="text-xs">
            {pullRequests.filter((pr) => pr.state === "open").length}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={fetchPRs}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-7 gap-1.5 text-xs" disabled={!canCreatePR}>
                <Plus className="h-3.5 w-3.5" />
                Create PR
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Create Pull Request</DialogTitle>
                <DialogDescription>
                  Create a PR from {currentBranch} to {prBase}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="pr-title">Title</Label>
                  <Input
                    id="pr-title"
                    value={prTitle}
                    onChange={(e) => setPrTitle(e.target.value)}
                    placeholder="Add feature X"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pr-body">Description (Optional)</Label>
                  <Textarea
                    id="pr-body"
                    value={prBody}
                    onChange={(e) => setPrBody(e.target.value)}
                    placeholder="Describe your changes..."
                    rows={4}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Source Branch</Label>
                    <Input value={currentBranch} disabled className="bg-muted" />
                  </div>
                  <div className="space-y-2">
                    <Label>Target Branch</Label>
                    <Select value={prBase} onValueChange={setPrBase}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="main">main</SelectItem>
                        <SelectItem value="master">master</SelectItem>
                        <SelectItem value="develop">develop</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="pr-draft">Create as draft</Label>
                    <p className="text-xs text-muted-foreground">
                      Mark as not ready for review
                    </p>
                  </div>
                  <Switch
                    id="pr-draft"
                    checked={prDraft}
                    onCheckedChange={setPrDraft}
                  />
                </div>
                {createError && (
                  <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/15 text-destructive text-sm">
                    <AlertCircle className="h-4 w-4" />
                    {createError}
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreatePR} disabled={isCreating || !prTitle.trim()}>
                  {isCreating ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating...</>
                  ) : (
                    "Create Pull Request"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 bg-destructive/15 text-destructive text-sm">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* PR List */}
      <ScrollArea className="flex-1">
        {pullRequests.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-center">
            <GitPullRequest className="h-8 w-8 text-muted-foreground/50 mb-2" />
            <p className="text-sm text-muted-foreground">No pull requests</p>
          </div>
        ) : (
          <div className="divide-y">
            {pullRequests.map((pr) => (
              <div
                key={pr.number}
                className="px-4 py-3 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {getStatusBadge(pr)}
                      <span className="text-xs text-muted-foreground">
                        #{pr.number}
                      </span>
                    </div>
                    <h4 className="font-medium text-sm truncate mb-1">
                      {pr.title}
                    </h4>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {pr.user}
                      </span>
                      <span>
                        {pr.head} → {pr.base}
                      </span>
                      {(pr.comments ?? 0) > 0 && (
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {pr.comments}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {pr.state === "open" && pr.mergeable && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => handleMergePR(pr.number)}
                      >
                        <GitMerge className="h-3.5 w-3.5 mr-1" />
                        Merge
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      asChild
                    >
                      <a
                        href={pr.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Hint for non-feature branches */}
      {!canCreatePR && (
        <div className="px-4 py-2 bg-muted/50 border-t text-xs text-muted-foreground">
          Switch to a feature branch to create a pull request
        </div>
      )}
    </div>
  );
}
