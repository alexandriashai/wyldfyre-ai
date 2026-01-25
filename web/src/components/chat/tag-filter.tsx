"use client";

import { ALL_TAGS } from "@/lib/constants";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

export function TagFilter() {
  const { tagFilter, toggleTagFilter } = useChatStore();

  return (
    <div className="px-2 py-1.5 border-b">
      <ScrollArea className="w-full whitespace-nowrap">
        <div className="flex gap-1">
          {ALL_TAGS.map((tag) => {
            const isActive = tagFilter.includes(tag.value);
            return (
              <button
                key={tag.value}
                onClick={() => toggleTagFilter(tag.value)}
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors shrink-0",
                  isActive
                    ? "text-white"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
                style={isActive ? { backgroundColor: tag.color } : undefined}
              >
                {tag.label}
              </button>
            );
          })}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
    </div>
  );
}
