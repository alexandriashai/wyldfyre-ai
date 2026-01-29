"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useBrowserStore, TestCredential } from "@/stores/browser-store";
import { BrowserToolbar } from "./browser-toolbar";
import { BrowserViewport } from "./browser-viewport";
import { BrowserCredentials } from "./browser-credentials";
import { BrowserSettings } from "./browser-settings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AlertCircle, Key, Network, Settings, Terminal, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "wss://api.wyldfyre.ai";

export function BrowserPanel() {
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
  } = useBrowserStore();

  // State for auth prompt dialog
  const [showAuthDialog, setShowAuthDialog] = useState(false);
  const [authCorrelationId, setAuthCorrelationId] = useState<string | null>(null);

  // Get credential count for current project
  const credentialCount = activeProjectId
    ? (credentials[activeProjectId] || []).length
    : 0;

  // Get credentials for current project
  const projectCredentials = activeProjectId
    ? (credentials[activeProjectId] || [])
    : [];

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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

      // Send viewport settings to browser service
      const viewport = getViewportPreset(activeProjectId);
      ws.send(JSON.stringify({
        type: "set_viewport",
        width: viewport.width,
        height: viewport.height,
        deviceScaleFactor: viewport.deviceScaleFactor || 1,
        isMobile: viewport.isMobile || false,
        hasTouch: viewport.hasTouch || false,
      }));

      // Send permissions to browser service
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

      // Attempt reconnect if we were previously connected
      if (isConnected) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connectToBrowser();
        }, 3000);
      }
    };

    wsRef.current = ws;
  }, [token, activeProjectId, connect, setConnected, setError, isConnected]);

  // Handle incoming WebSocket messages
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
          setLoading(false);
          break;

        case "session_ready":
          setConnected(true, data.session_id);
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
          // Handle command results
          if (data.result?.error) {
            setError(data.result.error);
          }
          setLoading(false);
          break;

        case "browser_prompt":
          // Handle auth and other prompts from browser service
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

        default:
          console.log("Unknown browser message:", data.type);
      }
    },
    [setConnected, setFrame, setCurrentUrl, setLoading, addConsoleMessage, setError, setActivePrompt]
  );

  // Disconnect from browser
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

  // Send command to browser
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

  // Navigation handlers
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

  const handleClose = useCallback(() => {
    sendCommand("close");
    disconnectFromBrowser();
  }, [sendCommand, disconnectFromBrowser]);

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

  // Handle credential selection for auth
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

  // Handle manual login option
  const handleManualLogin = useCallback(() => {
    sendCommand("auth_response", {
      decision: "manual",
      correlation_id: authCorrelationId,
    });
    setShowAuthDialog(false);
    setAuthCorrelationId(null);
    setActivePrompt(null);
  }, [sendCommand, authCorrelationId, setActivePrompt]);

  // Handle skip auth option
  const handleSkipAuth = useCallback(() => {
    sendCommand("auth_response", {
      decision: "skip",
      correlation_id: authCorrelationId,
    });
    setShowAuthDialog(false);
    setAuthCorrelationId(null);
    setActivePrompt(null);
  }, [sendCommand, authCorrelationId, setActivePrompt]);

  // Cleanup on unmount
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

  // Count errors in console
  const errorCount = consoleMessages.filter(
    (m) => m.level === "error" || m.level === "warn"
  ).length;

  // Count failed network requests
  const failedRequestCount = networkRequests.filter(
    (r) => r.error || (r.status && r.status >= 400)
  ).length;

  if (!activeProjectId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        Select a project to use the browser
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <BrowserToolbar
        onNavigate={handleNavigate}
        onBack={handleBack}
        onForward={handleForward}
        onRefresh={handleRefresh}
        onClose={handleClose}
        onConnect={connectToBrowser}
      />

      {/* Main content area with tabs */}
      <Tabs defaultValue="viewport" className="flex-1 flex flex-col min-h-0">
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-8 px-2 shrink-0">
          <TabsTrigger
            value="viewport"
            className="text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            Viewport
          </TabsTrigger>
          <TabsTrigger
            value="console"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Terminal className="h-3 w-3" />
            Console
            {errorCount > 0 && (
              <Badge variant="destructive" className="h-4 px-1 text-[10px]">
                {errorCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="network"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Network className="h-3 w-3" />
            Network
            {failedRequestCount > 0 && (
              <Badge variant="destructive" className="h-4 px-1 text-[10px]">
                {failedRequestCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="credentials"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Key className="h-3 w-3" />
            Credentials
            {credentialCount > 0 && (
              <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                {credentialCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="settings"
            className="gap-1 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Settings className="h-3 w-3" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="viewport" className="flex-1 m-0 min-h-0">
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
                    {msg.source && (
                      <span className="opacity-50 ml-2">
                        ({msg.source}:{msg.line})
                      </span>
                    )}
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
                    {req.error && (
                      <AlertCircle className="h-3 w-3 text-destructive shrink-0" />
                    )}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="credentials" className="flex-1 m-0 min-h-0">
          {activeProjectId && (
            <BrowserCredentials projectId={activeProjectId} />
          )}
        </TabsContent>

        <TabsContent value="settings" className="flex-1 m-0 min-h-0">
          {activeProjectId && (
            <BrowserSettings projectId={activeProjectId} />
          )}
        </TabsContent>
      </Tabs>

      {/* Auth Prompt Dialog */}
      <Dialog open={showAuthDialog} onOpenChange={setShowAuthDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Authentication Required
            </DialogTitle>
            <DialogDescription>
              {activePrompt?.message ||
                "The browser has detected a login page. How would you like to proceed?"}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {projectCredentials.length > 0 ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Select credentials to use:</p>
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
                          {credential.domain && ` (${credential.domain})`}
                        </span>
                      </div>
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-sm text-muted-foreground">
                <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No saved credentials for this project</p>
                <p className="text-xs mt-1">
                  Add credentials in the Credentials tab to use them here
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={handleManualLogin} className="w-full sm:w-auto">
              Log in manually
            </Button>
            <Button variant="ghost" onClick={handleSkipAuth} className="w-full sm:w-auto">
              Skip
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
