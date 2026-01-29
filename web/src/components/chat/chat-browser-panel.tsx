"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useBrowserStore, TestCredential } from "@/stores/browser-store";
import { BrowserViewport } from "@/components/workspace/browser/browser-viewport";
import { BrowserCredentials } from "@/components/workspace/browser/browser-credentials";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertCircle,
  ExternalLink,
  Key,
  Maximize2,
  Monitor,
  Network,
  Play,
  RefreshCw,
  ShieldAlert,
  Smartphone,
  Square,
  Tablet,
  Terminal,
  X,
  Globe,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { VIEWPORT_PRESETS, ViewportPreset } from "@/stores/browser-store";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "wss://api.wyldfyre.ai";

interface ChatBrowserPanelProps {
  onClose?: () => void;
}

export function ChatBrowserPanel({ onClose }: ChatBrowserPanelProps) {
  const { token } = useAuthStore();
  const { activeProjectId } = useWorkspaceStore();
  const {
    isConnected,
    currentUrl,
    consoleMessages,
    networkRequests,
    credentials,
    activePrompt,
    connect,
    disconnect,
    setConnected,
    setCurrentUrl,
    setFrame,
    setLoading,
    setError,
    addConsoleMessage,
    addNetworkRequest,
    setActivePrompt,
    reset,
    getEnabledPermissions,
    getViewportPreset,
    setViewportPreset,
  } = useBrowserStore();

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const viewportContainerRef = useRef<HTMLDivElement>(null);
  const [urlInput, setUrlInput] = useState("");
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  // Auth prompt state
  const [showAuthDialog, setShowAuthDialog] = useState(false);
  const [authCorrelationId, setAuthCorrelationId] = useState<string | null>(null);

  const credentialCount = activeProjectId
    ? (credentials[activeProjectId] || []).length
    : 0;
  const projectCredentials = activeProjectId
    ? (credentials[activeProjectId] || [])
    : [];

  const currentViewport = activeProjectId ? getViewportPreset(activeProjectId) : VIEWPORT_PRESETS.find(p => p.id === "desktop")!;

  // Connect to browser WebSocket
  const connectToBrowser = useCallback(() => {
    if (!token || !activeProjectId) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    connect(activeProjectId);

    const wsUrl = `${WS_URL}/browser?token=${encodeURIComponent(token)}&project_id=${encodeURIComponent(activeProjectId)}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("Browser WebSocket connected");
      setConnected(true);

      // Send viewport settings
      const viewport = getViewportPreset(activeProjectId);
      // For auto mode, use container size; for presets, use preset dimensions
      const width = viewport.id === "auto" && containerSize.width > 0 ? containerSize.width : (viewport.width || 1280);
      const height = viewport.id === "auto" && containerSize.height > 0 ? containerSize.height : (viewport.height || 720);
      ws.send(JSON.stringify({
        type: "set_viewport",
        width,
        height,
        deviceScaleFactor: viewport.deviceScaleFactor || 1,
        isMobile: viewport.isMobile || false,
        hasTouch: viewport.hasTouch || false,
      }));

      // Send permissions
      const permissions = getEnabledPermissions(activeProjectId);
      if (permissions.length > 0) {
        ws.send(JSON.stringify({
          type: "set_permissions",
          permissions,
        }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error("Failed to parse browser message:", e);
      }
    };

    ws.onerror = (error) => {
      console.error("Browser WebSocket error:", error);
      setError("Connection error");
    };

    ws.onclose = () => {
      console.log("Browser WebSocket closed");
      setConnected(false);
      wsRef.current = null;

      if (isConnected) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connectToBrowser();
        }, 3000);
      }
    };

    wsRef.current = ws;
  }, [token, activeProjectId, connect, setConnected, setError, isConnected, getViewportPreset, getEnabledPermissions, containerSize]);

  const handleMessage = useCallback(
    (data: any) => {
      switch (data.type) {
        case "connected":
          setConnected(true, data.sessionId);
          break;
        case "frame":
          setFrame(data.data, data.timestamp);
          break;
        case "url_change":
          setCurrentUrl(data.url, data.title);
          setUrlInput(data.url);
          setLoading(false);
          break;
        case "session_ready":
          setConnected(true, data.session_id);
          if (data.url) {
            setUrlInput(data.url);
          }
          break;
        case "console":
          addConsoleMessage({
            level: data.level,
            message: data.message,
            timestamp: data.timestamp,
            source: data.source,
            line: data.line,
          });
          break;
        case "network":
          addNetworkRequest({
            url: data.url,
            method: data.method,
            status: data.status,
            statusText: data.status_text,
            resourceType: data.resource_type,
            timestamp: data.timestamp,
          });
          break;
        case "network_error":
          addNetworkRequest({
            url: data.url,
            method: data.method,
            error: data.error,
            timestamp: data.timestamp,
          });
          break;
        case "error":
          setError(data.error);
          break;
        case "task_result":
          if (data.result?.error) {
            setError(data.result.error);
          }
          setLoading(false);
          break;
        case "browser_prompt":
          if (data.prompt_type === "auth") {
            setAuthCorrelationId(data.correlation_id);
            setShowAuthDialog(true);
          }
          setActivePrompt({
            promptType: data.prompt_type,
            message: data.message,
            options: data.options,
            correlationId: data.correlation_id,
            timestamp: data.timestamp,
          });
          break;
      }
    },
    [setConnected, setFrame, setCurrentUrl, setLoading, addConsoleMessage, addNetworkRequest, setError, setActivePrompt]
  );

  const disconnectFromBrowser = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    disconnect();
  }, [disconnect]);

  const sendCommand = useCallback(
    (type: string, payload: any = {}) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket not connected");
        return;
      }
      wsRef.current.send(JSON.stringify({ type, ...payload }));
    },
    []
  );

  const handleNavigate = useCallback(
    (url: string) => {
      setLoading(true);
      sendCommand("navigate", { url });
    },
    [sendCommand, setLoading]
  );

  const handleBack = useCallback(() => {
    setLoading(true);
    sendCommand("back");
  }, [sendCommand, setLoading]);

  const handleForward = useCallback(() => {
    setLoading(true);
    sendCommand("forward");
  }, [sendCommand, setLoading]);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    sendCommand("refresh");
  }, [sendCommand, setLoading]);

  const handleClick = useCallback(
    (x: number, y: number) => {
      setLoading(true);
      sendCommand("click", { x, y });
    },
    [sendCommand, setLoading]
  );

  const handleScroll = useCallback(
    (deltaX: number, deltaY: number) => {
      sendCommand("scroll", { deltaX, deltaY });
    },
    [sendCommand]
  );

  const handleSelectCredential = useCallback(
    (credential: TestCredential) => {
      sendCommand("auth_response", {
        decision: "use_credentials",
        username: credential.username,
        password: credential.password,
        correlation_id: authCorrelationId,
      });
      setShowAuthDialog(false);
      setAuthCorrelationId(null);
      setActivePrompt(null);
    },
    [sendCommand, authCorrelationId, setActivePrompt]
  );

  const handleManualLogin = useCallback(() => {
    sendCommand("auth_response", {
      decision: "manual",
      correlation_id: authCorrelationId,
    });
    setShowAuthDialog(false);
    setAuthCorrelationId(null);
    setActivePrompt(null);
  }, [sendCommand, authCorrelationId, setActivePrompt]);

  const handleSkipAuth = useCallback(() => {
    sendCommand("auth_response", {
      decision: "skip",
      correlation_id: authCorrelationId,
    });
    setShowAuthDialog(false);
    setAuthCorrelationId(null);
    setActivePrompt(null);
  }, [sendCommand, authCorrelationId, setActivePrompt]);

  const handleViewportChange = useCallback((presetId: string) => {
    if (!activeProjectId) return;
    setViewportPreset(activeProjectId, presetId);

    const preset = VIEWPORT_PRESETS.find(p => p.id === presetId);
    if (preset && wsRef.current?.readyState === WebSocket.OPEN) {
      // For auto mode, use container size; for presets, use preset dimensions
      const width = presetId === "auto" && containerSize.width > 0 ? containerSize.width : preset.width;
      const height = presetId === "auto" && containerSize.height > 0 ? containerSize.height : preset.height;
      sendCommand("set_viewport", {
        width: width || 1280,
        height: height || 720,
        deviceScaleFactor: preset.deviceScaleFactor || 1,
        isMobile: preset.isMobile || false,
        hasTouch: preset.hasTouch || false,
      });
    }
  }, [activeProjectId, setViewportPreset, sendCommand, containerSize]);

  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      reset();
    };
  }, [reset]);

  // Track container size for auto-resize mode
  useEffect(() => {
    const container = viewportContainerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        // Only update if size actually changed (with some tolerance for floating point)
        if (Math.abs(width - containerSize.width) > 1 || Math.abs(height - containerSize.height) > 1) {
          setContainerSize({ width: Math.floor(width), height: Math.floor(height) });
        }
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [containerSize.width, containerSize.height]);

  // Send viewport update when container size changes in auto mode
  useEffect(() => {
    if (!isConnected || !activeProjectId) return;
    if (containerSize.width === 0 || containerSize.height === 0) return;

    const viewport = getViewportPreset(activeProjectId);
    if (viewport.id !== "auto") return;

    // Debounce the viewport update
    const timeoutId = setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "set_viewport",
          width: containerSize.width,
          height: containerSize.height,
          deviceScaleFactor: 1,
          isMobile: false,
          hasTouch: false,
        }));
      }
    }, 100); // 100ms debounce

    return () => clearTimeout(timeoutId);
  }, [containerSize.width, containerSize.height, isConnected, activeProjectId, getViewportPreset]);

  // Update URL input when currentUrl changes
  useEffect(() => {
    if (currentUrl) {
      setUrlInput(currentUrl);
    }
  }, [currentUrl]);

  const errorCount = consoleMessages.filter(
    (m) => m.level === "error" || m.level === "warn"
  ).length;
  const failedRequestCount = networkRequests.filter(
    (r) => r.error || (r.status && r.status >= 400)
  ).length;

  const mobilePresets = VIEWPORT_PRESETS.filter((p) => p.category === "mobile");
  const tabletPresets = VIEWPORT_PRESETS.filter((p) => p.category === "tablet");
  const desktopPresets = VIEWPORT_PRESETS.filter((p) => p.category === "desktop");

  if (!activeProjectId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground p-4">
        Select a project to use the browser
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border-l">
      {/* Compact header */}
      <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/30 shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onClose}
          title="Close browser panel"
        >
          <X className="h-4 w-4" />
        </Button>

        {!isConnected ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1"
            onClick={connectToBrowser}
          >
            <Play className="h-3 w-3" />
            Start
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1"
            onClick={disconnectFromBrowser}
          >
            <Square className="h-3 w-3" />
            Stop
          </Button>
        )}

        {/* Viewport selector */}
        <Select value={currentViewport.id} onValueChange={handleViewportChange}>
          <SelectTrigger className="h-7 w-auto gap-1 text-xs">
            {currentViewport.category === "auto" && <Maximize2 className="h-3 w-3" />}
            {currentViewport.category === "mobile" && <Smartphone className="h-3 w-3" />}
            {currentViewport.category === "tablet" && <Tablet className="h-3 w-3" />}
            {currentViewport.category === "desktop" && <Monitor className="h-3 w-3" />}
            <span className="hidden sm:inline">
              {currentViewport.id === "auto"
                ? (containerSize.width > 0 ? `${containerSize.width}x${containerSize.height}` : "Auto")
                : `${currentViewport.width}x${currentViewport.height}`}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel><Maximize2 className="h-3 w-3 inline mr-1" />Auto</SelectLabel>
              <SelectItem value="auto">Auto (Fit Panel)</SelectItem>
            </SelectGroup>
            <SelectGroup>
              <SelectLabel><Smartphone className="h-3 w-3 inline mr-1" />Mobile</SelectLabel>
              {mobilePresets.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name} ({p.width}x{p.height})</SelectItem>
              ))}
            </SelectGroup>
            <SelectGroup>
              <SelectLabel><Tablet className="h-3 w-3 inline mr-1" />Tablet</SelectLabel>
              {tabletPresets.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name} ({p.width}x{p.height})</SelectItem>
              ))}
            </SelectGroup>
            <SelectGroup>
              <SelectLabel><Monitor className="h-3 w-3 inline mr-1" />Desktop</SelectLabel>
              {desktopPresets.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name} ({p.width}x{p.height})</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {currentUrl && (
          <a
            href={currentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0"
          >
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <ExternalLink className="h-3 w-3" />
            </Button>
          </a>
        )}
      </div>

      {/* URL bar */}
      {isConnected && (
        <div className="flex items-center gap-1 px-2 py-1 border-b shrink-0">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleBack}>
            <ChevronLeft className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleForward}>
            <ChevronRight className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleRefresh}>
            <RefreshCw className="h-3 w-3" />
          </Button>
          <form
            className="flex-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (urlInput) handleNavigate(urlInput);
            }}
          >
            <Input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter URL..."
              className="h-6 text-xs"
            />
          </form>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="viewport" className="flex-1 flex flex-col min-h-0">
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-7 px-2 shrink-0">
          <TabsTrigger
            value="viewport"
            className="text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-2"
          >
            <Globe className="h-3 w-3 mr-1" />
            View
          </TabsTrigger>
          <TabsTrigger
            value="console"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-2"
          >
            <Terminal className="h-3 w-3" />
            {errorCount > 0 && (
              <Badge variant="destructive" className="h-4 px-1 text-[10px]">
                {errorCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="network"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-2"
          >
            <Network className="h-3 w-3" />
            {failedRequestCount > 0 && (
              <Badge variant="destructive" className="h-4 px-1 text-[10px]">
                {failedRequestCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="credentials"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-2"
          >
            <Key className="h-3 w-3" />
            {credentialCount > 0 && (
              <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                {credentialCount}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="viewport" className="flex-1 m-0 min-h-0" ref={viewportContainerRef}>
          <BrowserViewport onClick={handleClick} onScroll={handleScroll} />
        </TabsContent>

        <TabsContent value="console" className="flex-1 m-0 min-h-0">
          <ScrollArea className="h-full">
            <div className="p-2 space-y-1">
              {consoleMessages.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No console messages
                </p>
              ) : (
                consoleMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={cn(
                      "text-xs font-mono p-1 rounded",
                      msg.level === "error" && "bg-destructive/10 text-destructive",
                      msg.level === "warn" && "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
                      msg.level === "info" && "bg-blue-500/10 text-blue-700 dark:text-blue-400",
                      (msg.level === "log" || msg.level === "debug") && "text-muted-foreground"
                    )}
                  >
                    <span className="opacity-50">[{msg.level}]</span> {msg.message}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="network" className="flex-1 m-0 min-h-0">
          <ScrollArea className="h-full">
            <div className="p-2 space-y-1">
              {networkRequests.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No network requests
                </p>
              ) : (
                networkRequests.map((req, i) => (
                  <div
                    key={i}
                    className={cn(
                      "text-xs font-mono p-1 rounded flex items-center gap-2",
                      req.error || (req.status && req.status >= 400)
                        ? "bg-destructive/10 text-destructive"
                        : "text-muted-foreground"
                    )}
                  >
                    <Badge
                      variant={
                        req.status && req.status >= 400
                          ? "destructive"
                          : req.status && req.status >= 200 && req.status < 300
                          ? "default"
                          : "secondary"
                      }
                      className="h-4 px-1 text-[10px] shrink-0"
                    >
                      {req.status || "ERR"}
                    </Badge>
                    <span className="truncate">{req.url}</span>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="credentials" className="flex-1 m-0 min-h-0">
          <BrowserCredentials projectId={activeProjectId} />
        </TabsContent>
      </Tabs>

      {/* Auth Dialog */}
      <Dialog open={showAuthDialog} onOpenChange={setShowAuthDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Authentication Required
            </DialogTitle>
            <DialogDescription>
              {activePrompt?.message || "Login page detected. How would you like to proceed?"}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {projectCredentials.length > 0 ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Select credentials:</p>
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {projectCredentials.map((credential) => (
                    <Button
                      key={credential.id}
                      variant="outline"
                      className="w-full justify-start h-auto py-2"
                      onClick={() => handleSelectCredential(credential)}
                    >
                      <div className="flex flex-col items-start">
                        <span className="font-medium">{credential.label}</span>
                        <span className="text-xs text-muted-foreground">
                          {credential.username}
                        </span>
                      </div>
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-sm text-muted-foreground">
                <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No saved credentials</p>
              </div>
            )}
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={handleManualLogin}>
              Log in manually
            </Button>
            <Button variant="ghost" onClick={handleSkipAuth}>
              Skip
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
