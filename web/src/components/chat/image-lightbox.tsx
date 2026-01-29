"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { Maximize2, X } from "lucide-react";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

interface ImageLightboxProps {
  src: string;
  alt?: string;
  className?: string;
  thumbnailSize?: "sm" | "md" | "lg";
}

/**
 * Image component with thumbnail preview and lightbox expand.
 * Perfect for screenshots in chat messages.
 */
export function ImageLightbox({
  src,
  alt = "Screenshot",
  className,
  thumbnailSize = "md"
}: ImageLightboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  const sizeClasses = {
    sm: "max-w-[120px] max-h-[80px]",
    md: "max-w-[200px] max-h-[150px]",
    lg: "max-w-[300px] max-h-[200px]",
  };

  return (
    <>
      {/* Thumbnail */}
      <div
        className={cn(
          "relative inline-block cursor-pointer group rounded-lg overflow-hidden border border-border",
          "hover:border-primary/50 transition-all duration-200",
          "bg-muted/50",
          className
        )}
        onClick={() => setIsOpen(true)}
      >
        <img
          src={src}
          alt={alt}
          className={cn(
            "object-contain",
            sizeClasses[thumbnailSize],
            !isLoaded && "opacity-0"
          )}
          onLoad={() => setIsLoaded(true)}
        />
        {!isLoaded && (
          <div className={cn("flex items-center justify-center", sizeClasses[thumbnailSize])}>
            <div className="animate-pulse bg-muted rounded w-full h-full min-h-[60px]" />
          </div>
        )}
        {/* Expand indicator */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
          <Maximize2 className="h-5 w-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        {/* Label */}
        <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs px-2 py-1 truncate">
          {alt}
        </div>
      </div>

      {/* Lightbox Dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-[90vw] max-h-[90vh] p-0 overflow-hidden bg-black/95 border-none">
          <VisuallyHidden>
            <DialogTitle>{alt}</DialogTitle>
          </VisuallyHidden>
          <div className="relative w-full h-full flex items-center justify-center p-4">
            {/* Close button */}
            <button
              onClick={() => setIsOpen(false)}
              className="absolute top-2 right-2 p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors z-10"
            >
              <X className="h-5 w-5" />
            </button>
            {/* Full image */}
            <img
              src={src}
              alt={alt}
              className="max-w-full max-h-[85vh] object-contain rounded-lg"
            />
            {/* Caption */}
            <div className="absolute bottom-4 left-4 right-4 text-center">
              <span className="bg-black/70 text-white text-sm px-3 py-1 rounded-full">
                {alt}
              </span>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Detects screenshot/image patterns in message content and extracts them.
 * Supports base64 data URLs and image file paths.
 */
export function extractScreenshots(content: string): {
  screenshots: Array<{ src: string; alt: string }>;
  cleanContent: string;
} {
  const screenshots: Array<{ src: string; alt: string }> = [];
  let cleanContent = content;

  // Match base64 image data URLs
  const base64Pattern = /!\[([^\]]*)\]\((data:image\/[^;]+;base64,[^)]+)\)/g;
  let match;

  while ((match = base64Pattern.exec(content)) !== null) {
    screenshots.push({
      alt: match[1] || "Screenshot",
      src: match[2],
    });
  }

  // Remove matched images from content for cleaner display
  cleanContent = content.replace(base64Pattern, "");

  // Match screenshot file paths (common patterns)
  const filePattern = /!\[([^\]]*)\]\((\/[^)]+\.(png|jpg|jpeg|gif|webp))\)/gi;
  while ((match = filePattern.exec(content)) !== null) {
    screenshots.push({
      alt: match[1] || "Screenshot",
      src: match[2],
    });
  }
  cleanContent = cleanContent.replace(filePattern, "");

  // Match inline base64 patterns without markdown syntax
  const inlineBase64 = /\[Screenshot: ([^\]]+)\]\s*\n?(data:image\/[^;]+;base64,[^\s]+)/g;
  while ((match = inlineBase64.exec(content)) !== null) {
    screenshots.push({
      alt: match[1] || "Screenshot",
      src: match[2],
    });
  }
  cleanContent = cleanContent.replace(inlineBase64, "");

  return { screenshots, cleanContent: cleanContent.trim() };
}
