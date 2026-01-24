"use client";

import { useState, useEffect, useCallback } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { domainsApi, projectsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { RefreshCw, ExternalLink, Globe } from "lucide-react";

export function PreviewPanel() {
  const { token } = useAuthStore();
  const { activeProjectId, deployStatus } = useWorkspaceStore();
  const { projects } = useProjectStore();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDomainUrl = useCallback(async () => {
    if (!token || !activeProjectId) return;
    setIsLoading(true);
    setError(null);
    try {
      // Check project store first for immediate primary_url
      const storeProject = projects.find((p) => p.id === activeProjectId);
      if (storeProject?.primary_url) {
        setPreviewUrl(storeProject.primary_url);
        setIsLoading(false);
        return;
      }

      // Fall back to API call for fresh data
      const project = await projectsApi.get(token, activeProjectId);
      if (project.primary_url) {
        setPreviewUrl(project.primary_url);
        return;
      }

      // Fall back to domain with is_primary, then first domain
      const domains = await domainsApi.list(token, { project_id: activeProjectId });
      const primary = domains.find((d: any) => d.is_primary) || domains[0];
      if (primary) {
        setPreviewUrl(`https://${primary.domain_name}`);
      } else {
        setPreviewUrl(null);
      }
    } catch (err) {
      console.error("Preview: failed to fetch domain URL:", err);
      setError(err instanceof Error ? err.message : "Failed to load preview URL");
      setPreviewUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [token, activeProjectId, projects]);

  // Fetch domain URL for the project
  useEffect(() => {
    if (token && activeProjectId) {
      fetchDomainUrl();
    } else if (!activeProjectId) {
      // Don't show "no domain" if project hasn't loaded yet
      setIsLoading(projects.length === 0);
    }
  }, [token, activeProjectId, fetchDomainUrl, projects.length]);

  // Auto-refresh after deploy
  useEffect(() => {
    if (!deployStatus.isDeploying && deployStatus.progress === 100 && !deployStatus.error) {
      // Wait a moment for the server to catch up
      const timer = setTimeout(() => {
        setRefreshKey((k) => k + 1);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [deployStatus]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <RefreshCw className="h-6 w-6 text-muted-foreground animate-spin" />
        <p className="text-sm text-muted-foreground">Loading preview...</p>
      </div>
    );
  }

  if (!previewUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <Globe className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {error ? "Failed to load preview" : "No domain configured"}
        </p>
        <p className="text-xs text-muted-foreground text-center px-4">
          {error || "Link a domain to this project to see a live preview"}
        </p>
        {error && (
          <Button variant="ghost" size="sm" onClick={fetchDomainUrl}>
            Retry
          </Button>
        )}
      </div>
    );
  }

  const iframeUrl = `${previewUrl}?_t=${refreshKey}`;

  return (
    <div className="flex flex-col h-full">
      {/* URL bar */}
      <div className="flex items-center gap-1 px-2 py-1 border-b shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 shrink-0"
          onClick={handleRefresh}
          title="Refresh preview"
        >
          <RefreshCw className="h-3 w-3" />
        </Button>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-muted-foreground truncate">{previewUrl}</p>
        </div>
        <a
          href={previewUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0"
        >
          <Button variant="ghost" size="icon" className="h-6 w-6">
            <ExternalLink className="h-3 w-3" />
          </Button>
        </a>
      </div>

      {/* iframe */}
      <div className="flex-1 min-h-0">
        <iframe
          key={refreshKey}
          src={iframeUrl}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          title="Site Preview"
          onLoad={() => setIsLoading(false)}
        />
      </div>
    </div>
  );
}
