"use client";

import { useState } from "react";
import { useBrowserStore } from "@/stores/browser-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Globe,
  X,
  Play,
  Square,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BrowserToolbarProps {
  onNavigate: (url: string) => void;
  onBack: () => void;
  onForward: () => void;
  onRefresh: () => void;
  onClose: () => void;
  onConnect: () => void;
}

export function BrowserToolbar({
  onNavigate,
  onBack,
  onForward,
  onRefresh,
  onClose,
  onConnect,
}: BrowserToolbarProps) {
  const { currentUrl, isLoading, isConnected } = useBrowserStore();
  const [urlInput, setUrlInput] = useState(currentUrl);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput.trim()) {
      let url = urlInput.trim();
      // Add https:// if no protocol
      if (!url.match(/^https?:\/\//)) {
        url = `https://${url}`;
      }
      onNavigate(url);
    }
  };

  return (
    <div className="flex flex-col gap-1 px-2 py-1.5 border-b shrink-0 bg-muted/30">
      {/* Navigation controls row */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onBack}
          disabled={!isConnected || isLoading}
          title="Go back"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onForward}
          disabled={!isConnected || isLoading}
          title="Go forward"
        >
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onRefresh}
          disabled={!isConnected || isLoading}
          title="Refresh"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
        </Button>

        {/* URL input */}
        <form onSubmit={handleSubmit} className="flex-1 min-w-0">
          <div className="flex items-center gap-1 px-2 py-1 bg-background rounded border text-xs">
            <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
            <Input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter URL..."
              className="flex-1 h-5 px-1 py-0 border-0 bg-transparent text-xs font-mono focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={!isConnected}
            />
          </div>
        </form>

        {/* Connection control */}
        {isConnected ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-destructive hover:text-destructive"
            onClick={onClose}
            title="Close browser"
          >
            <Square className="h-3.5 w-3.5" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-green-500 hover:text-green-600"
            onClick={onConnect}
            title="Start browser"
          >
            <Play className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {/* Status row */}
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground px-1">
        <div
          className={cn(
            "w-1.5 h-1.5 rounded-full",
            isConnected ? "bg-green-500" : "bg-muted-foreground"
          )}
        />
        <span>{isConnected ? "Connected" : "Disconnected"}</span>
        {isLoading && <span className="text-blue-500">Loading...</span>}
        {currentUrl && (
          <span className="truncate flex-1 text-right font-mono">{currentUrl}</span>
        )}
      </div>
    </div>
  );
}
