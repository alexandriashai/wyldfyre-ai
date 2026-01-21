"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  HelpCircle,
  Trash2,
  FileText,
  Brain,
  Bookmark,
  Wrench,
  Bot,
  Activity,
} from "lucide-react";

export interface Command {
  name: string;
  description: string;
  usage: string;
  aliases: string[];
  icon: React.ElementType;
}

const COMMANDS: Command[] = [
  {
    name: "help",
    description: "Show available commands",
    usage: "/help",
    aliases: ["?", "h"],
    icon: HelpCircle,
  },
  {
    name: "clear",
    description: "Clear conversation history",
    usage: "/clear",
    aliases: ["c"],
    icon: Trash2,
  },
  {
    name: "plan",
    description: "Enter planning mode for structured task breakdown",
    usage: "/plan [task description]",
    aliases: ["p"],
    icon: FileText,
  },
  {
    name: "memory",
    description: "Search project memory for relevant context",
    usage: "/memory [search query]",
    aliases: ["mem", "m"],
    icon: Brain,
  },
  {
    name: "remember",
    description: "Save information to project memory",
    usage: "/remember [text to save]",
    aliases: ["rem", "r"],
    icon: Bookmark,
  },
  {
    name: "tools",
    description: "List available tools for the current agent",
    usage: "/tools",
    aliases: ["t"],
    icon: Wrench,
  },
  {
    name: "agent",
    description: "Switch to a specific agent for the conversation",
    usage: "/agent [agent-name]",
    aliases: ["a"],
    icon: Bot,
  },
  {
    name: "status",
    description: "Show current system and agent status",
    usage: "/status",
    aliases: ["s"],
    icon: Activity,
  },
];

interface CommandSuggestionsProps {
  filter: string;
  onSelect: (command: Command) => void;
  onClose: () => void;
  selectedIndex: number;
}

export function CommandSuggestions({
  filter,
  onSelect,
  onClose,
  selectedIndex,
}: CommandSuggestionsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter commands based on input
  const filteredCommands = COMMANDS.filter((cmd) => {
    const searchTerm = filter.toLowerCase();
    return (
      cmd.name.toLowerCase().startsWith(searchTerm) ||
      cmd.aliases.some((alias) => alias.toLowerCase().startsWith(searchTerm))
    );
  });

  // Scroll selected item into view
  useEffect(() => {
    if (containerRef.current && selectedIndex >= 0) {
      const items = containerRef.current.querySelectorAll("[data-command-item]");
      const selectedItem = items[selectedIndex];
      if (selectedItem) {
        selectedItem.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  if (filteredCommands.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 right-0 mb-2 bg-popover border rounded-lg shadow-lg overflow-hidden z-50"
    >
      <div className="p-2 border-b bg-muted/50">
        <p className="text-xs text-muted-foreground">
          Type a command or use arrow keys to navigate
        </p>
      </div>
      <div className="max-h-[300px] overflow-y-auto">
        {filteredCommands.map((command, index) => {
          const Icon = command.icon;
          const isSelected = index === selectedIndex;

          return (
            <button
              key={command.name}
              data-command-item
              className={cn(
                "w-full flex items-start gap-3 p-3 text-left transition-colors",
                isSelected ? "bg-accent" : "hover:bg-accent/50"
              )}
              onClick={() => onSelect(command)}
              onMouseEnter={() => {}}
            >
              <div
                className={cn(
                  "rounded-md p-1.5 shrink-0",
                  isSelected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{command.usage}</span>
                  {command.aliases.length > 0 && (
                    <div className="flex gap-1">
                      {command.aliases.map((alias) => (
                        <Badge key={alias} variant="outline" className="text-xs px-1 py-0">
                          /{alias}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs text-muted-foreground truncate">
                  {command.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function getFilteredCommands(filter: string): Command[] {
  return COMMANDS.filter((cmd) => {
    const searchTerm = filter.toLowerCase();
    return (
      cmd.name.toLowerCase().startsWith(searchTerm) ||
      cmd.aliases.some((alias) => alias.toLowerCase().startsWith(searchTerm))
    );
  });
}

export { COMMANDS };
