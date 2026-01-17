"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Bot,
  Globe,
  Brain,
  Settings,
  LogOut,
  Search,
  Plus,
  Moon,
  Sun,
  Flame,
  Code2,
  Database,
  Server,
  ShieldCheck,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();
  const { logout } = useAuthStore();
  const { createConversation } = useChatStore();
  const { token } = useAuthStore();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const runCommand = React.useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  const toggleTheme = () => {
    const root = document.documentElement;
    const isDark = root.classList.contains("dark");
    root.classList.remove("light", "dark");
    root.classList.add(isDark ? "light" : "dark");
    localStorage.setItem("theme", isDark ? "light" : "dark");
  };

  const handleNewChat = async () => {
    if (token) {
      await createConversation(token);
      router.push("/chat");
    }
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Quick Actions">
          <CommandItem onSelect={() => runCommand(handleNewChat)}>
            <Plus className="mr-2 h-4 w-4" />
            New Conversation
            <CommandShortcut>N</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(toggleTheme)}>
            <Sun className="mr-2 h-4 w-4 dark:hidden" />
            <Moon className="mr-2 h-4 w-4 hidden dark:block" />
            Toggle Theme
            <CommandShortcut>T</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigation">
          <CommandItem onSelect={() => runCommand(() => router.push("/chat"))}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Chat
            <CommandShortcut>C</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents"))}
          >
            <Bot className="mr-2 h-4 w-4" />
            Agents
            <CommandShortcut>A</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/domains"))}
          >
            <Globe className="mr-2 h-4 w-4" />
            Domains
            <CommandShortcut>D</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/memory"))}
          >
            <Brain className="mr-2 h-4 w-4" />
            Memory
            <CommandShortcut>M</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/settings"))}
          >
            <Settings className="mr-2 h-4 w-4" />
            Settings
            <CommandShortcut>S</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Agents">
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/wyld"))}
          >
            <Flame className="mr-2 h-4 w-4 text-purple-500" />
            Wyld (Supervisor)
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/code"))}
          >
            <Code2 className="mr-2 h-4 w-4 text-blue-500" />
            Code Agent
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/data"))}
          >
            <Database className="mr-2 h-4 w-4 text-emerald-500" />
            Data Agent
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/infra"))}
          >
            <Server className="mr-2 h-4 w-4 text-orange-500" />
            Infra Agent
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/research"))}
          >
            <Search className="mr-2 h-4 w-4 text-cyan-500" />
            Research Agent
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents/qa"))}
          >
            <ShieldCheck className="mr-2 h-4 w-4 text-pink-500" />
            QA Agent
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Account">
          <CommandItem
            onSelect={() =>
              runCommand(() => {
                logout();
                router.push("/login");
              })
            }
          >
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

// Keyboard hint component for showing in UI
export function CommandPaletteHint({ className }: { className?: string }) {
  return (
    <button
      onClick={() => {
        const event = new KeyboardEvent("keydown", {
          key: "k",
          metaKey: true,
          bubbles: true,
        });
        document.dispatchEvent(event);
      }}
      className={`inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-1 text-xs text-muted-foreground hover:bg-muted/80 ${className}`}
    >
      <kbd className="font-mono">⌘</kbd>
      <kbd className="font-mono">K</kbd>
    </button>
  );
}
