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
  ListTodo,
  GitBranch,
  GitCommit,
} from "lucide-react";

export interface CommandSubcommand {
  command: string;
  description: string;
  usage?: string;
}

export interface Command {
  name: string;
  description: string;
  usage: string;
  aliases: string[];
  icon: React.ElementType;
  subcommands?: CommandSubcommand[];
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
    description: "Plan management - create, browse, edit, and manage plans",
    usage: "/plan [subcommand] [args]",
    aliases: ["p"],
    icon: FileText,
    subcommands: [
      { command: "/plan list", description: "List plans by status", usage: "/plan list [active|paused|completed|failed|stuck|all]" },
      { command: "/plan view", description: "View plan details with progress", usage: "/plan view <plan_id>" },
      { command: "/plan edit", description: "Edit a plan", usage: "/plan edit <plan_id>" },
      { command: "/plan delete", description: "Delete a plan", usage: "/plan delete <plan_id>" },
      { command: "/plan clone", description: "Clone plan as template", usage: "/plan clone <plan_id> [new_title]" },
      { command: "/plan follow-up", description: "Resume stuck/paused plan", usage: "/plan follow-up <plan_id> [context]" },
      { command: "/plan modify", description: "AI-assisted modification", usage: "/plan modify <plan_id> <request>" },
      { command: "/plan history", description: "View modification history", usage: "/plan history <plan_id>" },
      { command: "/plan approve", description: "Approve current plan", usage: "/plan approve" },
      { command: "/plan reject", description: "Reject/cancel current plan", usage: "/plan reject" },
      { command: "/plan status", description: "Show current plan status", usage: "/plan status" },
      { command: "/plan pause", description: "Pause execution", usage: "/plan pause" },
      { command: "/plan resume", description: "Resume execution", usage: "/plan resume" },
    ],
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
  {
    name: "gh",
    description: "GitHub operations - PRs, issues, repos, and more",
    usage: "/gh [subcommand] [args]",
    aliases: ["github"],
    icon: GitBranch,
    subcommands: [
      { command: "/gh pr list", description: "List pull requests", usage: "/gh pr list [state]" },
      { command: "/gh pr create", description: "Create a pull request", usage: "/gh pr create [title]" },
      { command: "/gh pr view", description: "View pull request details", usage: "/gh pr view <number>" },
      { command: "/gh pr checkout", description: "Checkout a pull request branch", usage: "/gh pr checkout <number>" },
      { command: "/gh pr merge", description: "Merge a pull request", usage: "/gh pr merge <number>" },
      { command: "/gh issue list", description: "List issues", usage: "/gh issue list [state]" },
      { command: "/gh issue create", description: "Create an issue", usage: "/gh issue create [title]" },
      { command: "/gh issue view", description: "View issue details", usage: "/gh issue view <number>" },
      { command: "/gh repo view", description: "View repository info", usage: "/gh repo view [repo]" },
      { command: "/gh repo clone", description: "Clone a repository", usage: "/gh repo clone <repo>" },
      { command: "/gh status", description: "Show GitHub CLI auth status", usage: "/gh status" },
      { command: "/gh browse", description: "Open repo in browser", usage: "/gh browse [path]" },
    ],
  },
  {
    name: "git",
    description: "Git operations - push, pull, commit, branch, and more",
    usage: "/git [subcommand] [args]",
    aliases: [],
    icon: GitCommit,
    subcommands: [
      { command: "/git status", description: "Show working tree status", usage: "/git status" },
      { command: "/git push", description: "Push commits to remote", usage: "/git push [remote] [branch]" },
      { command: "/git pull", description: "Pull changes from remote", usage: "/git pull [remote] [branch]" },
      { command: "/git add", description: "Stage files for commit", usage: "/git add <files|.>" },
      { command: "/git commit", description: "Commit staged changes", usage: "/git commit -m \"message\"" },
      { command: "/git branch", description: "List or create branches", usage: "/git branch [name]" },
      { command: "/git checkout", description: "Switch branches or restore files", usage: "/git checkout <branch|file>" },
      { command: "/git merge", description: "Merge a branch", usage: "/git merge <branch>" },
      { command: "/git log", description: "Show commit history", usage: "/git log [--oneline] [-n N]" },
      { command: "/git diff", description: "Show changes", usage: "/git diff [file]" },
      { command: "/git stash", description: "Stash changes", usage: "/git stash [pop|list|drop]" },
      { command: "/git reset", description: "Reset HEAD or unstage files", usage: "/git reset [--hard] [ref]" },
    ],
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
