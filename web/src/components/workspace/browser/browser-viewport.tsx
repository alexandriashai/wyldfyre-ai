"use client";

import { useEffect, useRef, useState } from "react";
import { useBrowserStore } from "@/stores/browser-store";
import { Monitor, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface BrowserViewportProps {
  onClick?: (x: number, y: number) => void;
  onScroll?: (deltaX: number, deltaY: number) => void;
}

export function BrowserViewport({ onClick, onScroll }: BrowserViewportProps) {
  const { currentFrame, isConnected, isLoading, error } = useBrowserStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  // Draw frame to canvas
  useEffect(() => {
    if (!currentFrame || !canvasRef.current) return;

    const img = new Image();
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Set canvas size to match image
      canvas.width = img.width;
      canvas.height = img.height;

      // Draw image
      ctx.drawImage(img, 0, 0);

      // Calculate scale to fit container
      if (containerRef.current) {
        const containerWidth = containerRef.current.clientWidth;
        const containerHeight = containerRef.current.clientHeight;
        const scaleX = containerWidth / img.width;
        const scaleY = containerHeight / img.height;
        setScale(Math.min(scaleX, scaleY, 1));
      }
    };
    img.src = `data:image/jpeg;base64,${currentFrame}`;
  }, [currentFrame]);

  // Handle click on canvas
  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onClick || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();

    // Calculate click position relative to original image size
    const x = Math.round((e.clientX - rect.left) / scale);
    const y = Math.round((e.clientY - rect.top) / scale);

    onClick(x, y);
  };

  // Handle scroll
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (!onScroll) return;
    e.preventDefault();
    onScroll(e.deltaX, e.deltaY);
  };

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <Monitor className="h-12 w-12" />
        <p className="text-sm">Browser not connected</p>
        <p className="text-xs text-center px-4">
          Click the play button to start a browser session
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-destructive">
        <Monitor className="h-12 w-12" />
        <p className="text-sm">Connection error</p>
        <p className="text-xs text-center px-4">{error}</p>
      </div>
    );
  }

  if (isLoading && !currentFrame) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <p className="text-sm">Connecting to browser...</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden bg-muted/20 flex items-center justify-center"
      onWheel={handleWheel}
    >
      {currentFrame ? (
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          className={cn(
            "cursor-pointer shadow-lg",
            isLoading && "opacity-50"
          )}
          style={{
            transform: `scale(${scale})`,
            transformOrigin: "center",
          }}
        />
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <Monitor className="h-8 w-8" />
          <p className="text-xs">Waiting for frames...</p>
        </div>
      )}

      {/* Loading overlay */}
      {isLoading && currentFrame && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
