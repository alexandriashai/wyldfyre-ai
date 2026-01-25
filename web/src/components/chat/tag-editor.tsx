"use client";

import { useState } from "react";
import { CHAT_TAGS, getTagInfo } from "@/lib/constants";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tag } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagEditorProps {
  conversationId: string;
  currentTags: string[];
}

export function TagEditor({ conversationId, currentTags }: TagEditorProps) {
  const { token } = useAuthStore();
  const { updateConversationTags } = useChatStore();
  const [selectedTags, setSelectedTags] = useState<string[]>(currentTags);
  const [open, setOpen] = useState(false);

  const handleToggleTag = (value: string) => {
    setSelectedTags((prev) =>
      prev.includes(value)
        ? prev.filter((t) => t !== value)
        : [...prev, value]
    );
  };

  const handleSave = async () => {
    if (!token) return;
    await updateConversationTags(token, conversationId, selectedTags);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs gap-1">
          <Tag className="h-3 w-3" />
          Tags
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-3" align="start">
        <div className="space-y-3">
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
              Lifecycle
            </p>
            <div className="space-y-1">
              {CHAT_TAGS.lifecycle.map((tag) => (
                <label
                  key={tag.value}
                  className="flex items-center gap-2 cursor-pointer hover:bg-muted rounded px-1 py-0.5"
                >
                  <input
                    type="checkbox"
                    checked={selectedTags.includes(tag.value)}
                    onChange={() => handleToggleTag(tag.value)}
                    className="h-3 w-3 rounded"
                  />
                  <span
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: tag.color }}
                  />
                  <span className="text-xs">{tag.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
              System
            </p>
            <div className="space-y-1">
              {CHAT_TAGS.system.map((tag) => (
                <label
                  key={tag.value}
                  className="flex items-center gap-2 cursor-pointer hover:bg-muted rounded px-1 py-0.5"
                >
                  <input
                    type="checkbox"
                    checked={selectedTags.includes(tag.value)}
                    onChange={() => handleToggleTag(tag.value)}
                    className="h-3 w-3 rounded"
                  />
                  <span
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: tag.color }}
                  />
                  <span className="text-xs">{tag.label}</span>
                </label>
              ))}
            </div>
          </div>

          <Button onClick={handleSave} size="sm" className="w-full h-7 text-xs">
            Save Tags
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
