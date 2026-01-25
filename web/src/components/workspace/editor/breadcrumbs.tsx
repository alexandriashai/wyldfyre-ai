"use client";

import { useWorkspaceStore } from "@/stores/workspace-store";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function Breadcrumbs() {
  const { activeFilePath, setActiveFile, toggleExpanded } = useWorkspaceStore();

  if (!activeFilePath) return null;

  const segments = activeFilePath.split("/").filter(Boolean);

  const handleSegmentClick = (index: number) => {
    // Build path up to this segment and expand it in the tree
    const folderPath = "/" + segments.slice(0, index + 1).join("/");
    toggleExpanded(folderPath);
  };

  return (
    <div className="flex items-center gap-0.5 px-3 py-1 border-b bg-muted/30 overflow-x-auto shrink-0">
      {segments.map((segment, index) => {
        const isLast = index === segments.length - 1;
        return (
          <div key={index} className="flex items-center gap-0.5 shrink-0">
            {index > 0 && (
              <ChevronRight className="h-3 w-3 text-muted-foreground/50 shrink-0" />
            )}
            <button
              className={cn(
                "text-[11px] px-1 py-0.5 rounded hover:bg-muted transition-colors",
                isLast
                  ? "font-medium text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
              onClick={() => !isLast && handleSegmentClick(index)}
            >
              {segment}
            </button>
          </div>
        );
      })}
    </div>
  );
}
