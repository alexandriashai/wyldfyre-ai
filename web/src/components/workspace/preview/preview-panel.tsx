"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useBrowserStore } from "@/stores/browser-store";
import { domainsApi, projectsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { RefreshCw, ExternalLink, Globe, Copy, Check, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function PreviewPanel() {
  const { token } = useAuthStore();
  const { activeProjectId, deployStatus } = useWorkspaceStore();
  const { projects } = useProjectStore();
  const { permissions } = useBrowserStore();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [currentUrl, setCurrentUrl] = useState<string | null>(null); // Tracks iframe navigation
  const [refreshKey, setRefreshKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [clearing, setClearing] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Build iframe allow attribute based on browser permissions
  const iframeAllowAttribute = useMemo(() => {
    if (!activeProjectId) return "";
    const projectPerms = permissions[activeProjectId];
    if (!projectPerms) return "";

    const allowPolicies: string[] = [];
    if (projectPerms.geolocation) allowPolicies.push("geolocation");
    if (projectPerms.camera) allowPolicies.push("camera");
    if (projectPerms.microphone) allowPolicies.push("microphone");
    if (projectPerms.clipboard) {
      allowPolicies.push("clipboard-read");
      allowPolicies.push("clipboard-write");
    }
    // Note: midi and notifications are not typically iframe feature policies
    // but we can add fullscreen and other common ones
    allowPolicies.push("fullscreen"); // Always allow fullscreen

    return allowPolicies.join("; ");
  }, [activeProjectId, permissions]);

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

  // Reset currentUrl when previewUrl changes
  useEffect(() => {
    setCurrentUrl(previewUrl);
  }, [previewUrl]);

  // Listen for URL changes from iframe
  useEffect(() => {
    if (!previewUrl) return;

    const handleMessage = (event: MessageEvent) => {
      // Validate origin matches our preview URL's origin
      try {
        const previewOrigin = new URL(previewUrl).origin;
        if (event.origin !== previewOrigin) return;
      } catch {
        return;
      }

      // Handle url-change messages
      if (event.data?.type === "url-change" && typeof event.data.url === "string") {
        setCurrentUrl(event.data.url);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [previewUrl]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleCopyUrl = async () => {
    const urlToCopy = currentUrl || previewUrl;
    if (!urlToCopy) return;
    try {
      await navigator.clipboard.writeText(urlToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy URL:", err);
    }
  };

  const handleClearCacheAndCookies = async () => {
    if (!previewUrl) return;
    setClearing(true);

    // Send a message to the iframe to clear its storage (if it listens)
    try {
      iframeRef.current?.contentWindow?.postMessage(
        { type: "clear-site-data" },
        new URL(previewUrl).origin
      );
    } catch (err) {
      // Cross-origin, can't send message - that's okay
    }

    // Force a fresh reload by:
    // 1. Setting iframe src to about:blank briefly
    // 2. Then reloading with a new cache-busting key
    if (iframeRef.current) {
      iframeRef.current.src = "about:blank";
    }

    // Wait a moment, then reload with cache-busting
    setTimeout(() => {
      setRefreshKey((k) => k + 1);
      setClearing(false);
    }, 100);
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
      <div className="flex flex-col gap-1 px-2 py-1.5 border-b shrink-0 bg-muted/30">
        {/* URL display row */}
        <div className="flex items-center gap-1">
          <div className="flex-1 min-w-0 flex items-center gap-1 px-2 py-1 bg-background rounded border text-xs">
            <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
            <span className="truncate text-foreground font-mono">{currentUrl || previewUrl}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={handleCopyUrl}
            title="Copy URL"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>

        {/* Action buttons row */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs gap-1"
            onClick={handleRefresh}
            title="Refresh preview"
          >
            <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
            Refresh
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs gap-1"
            onClick={handleClearCacheAndCookies}
            disabled={clearing}
            title="Clear cache and cookies, then refresh"
          >
            <Trash2 className={cn("h-3 w-3", clearing && "animate-pulse")} />
            Clear & Reload
          </Button>
          <div className="flex-1" />
          <a
            href={currentUrl || previewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0"
          >
            <Button variant="ghost" size="sm" className="h-6 text-xs gap-1">
              <ExternalLink className="h-3 w-3" />
              Open
            </Button>
          </a>
        </div>
      </div>

      {/* iframe */}
      <div className="flex-1 min-h-0">
        <iframe
          ref={iframeRef}
          key={refreshKey}
          src={iframeUrl}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
          allow={iframeAllowAttribute}
          title="Site Preview"
          onLoad={() => setIsLoading(false)}
        />
      </div>
    </div>
  );
}
