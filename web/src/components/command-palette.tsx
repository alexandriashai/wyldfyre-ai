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
  FileCode,
  GitCompare,
  Terminal,
  Send,
  Eye,
  Play,
  Pause,
  Square,
  Upload,
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
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const [mode, setMode] = React.useState<"command" | "file">("command");
  const router = useRouter();
  const { logout } = useAuthStore();
  const { createConversation, planStatus, setActiveAgent, availableAgents } = useChatStore();
  const { token } = useAuthStore();
  const { selectedProject } = useProjectStore();
  const {
    openFiles,
    setActiveFile,
    setDiffMode,
    setTerminalOpen,
    setRightPanelMode,
    diffMode,
    isTerminalOpen,
    rightPanelMode,
    recentFiles,
    pinnedFiles,
    activeFilePath,
  } = useWorkspaceStore();

  // Keyboard shortcuts
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      // Cmd+K: Open command palette
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setMode("command");
        setOpen((open) => !open);
      }
      // Cmd+P: Quick file open
      if (e.key === "p" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        setMode("file");
        setOpen(true);
      }
      // Cmd+Shift+D: Toggle diff view
      if (e.key === "d" && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        if (activeFilePath) {
          setDiffMode(!diffMode, activeFilePath);
        }
      }
      // Cmd+`: Toggle terminal
      if (e.key === "`" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setTerminalOpen(!isTerminalOpen);
      }
      // Cmd+Shift+P: Toggle preview/chat panel
      if (e.key === "p" && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        const modes: ("preview" | "chat" | "design")[] = ["preview", "chat", "design"];
        const currentIndex = modes.indexOf(rightPanelMode);
        const nextMode = modes[(currentIndex + 1) % modes.length];
        setRightPanelMode(nextMode);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [diffMode, isTerminalOpen, rightPanelMode, activeFilePath, setDiffMode, setTerminalOpen, setRightPanelMode]);

  const runCommand = React.useCallback((command: () => void) => {
    setOpen(false);
    setMode("command");
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
    if (token && selectedProject?.id) {
      await createConversation(token, selectedProject.id);
      router.push("/workspace/chats");
    }
  };

  // All files for quick file open
  const allFiles = React.useMemo(() => {
    const files = new Set<string>();
    // Add pinned files first
    pinnedFiles.forEach(f => files.add(f));
    // Then recent files
    recentFiles.forEach(f => files.add(f));
    // Then open files
    openFiles.forEach(f => files.add(f.path));
    return Array.from(files);
  }, [pinnedFiles, recentFiles, openFiles]);

  const isExecuting = planStatus === "APPROVED";

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder={mode === "file" ? "Search files..." : "Type a command or search..."}
      />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        {mode === "file" ? (
          // File search mode
          <>
            {pinnedFiles.length > 0 && (
              <CommandGroup heading="Pinned">
                {pinnedFiles.map((file) => (
                  <CommandItem
                    key={file}
                    onSelect={() => runCommand(() => setActiveFile(file))}
                  >
                    <FileCode className="mr-2 h-4 w-4" />
                    <span className="font-mono text-sm">{file.split("/").pop()}</span>
                    <span className="ml-2 text-xs text-muted-foreground truncate">
                      {file}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {recentFiles.length > 0 && (
              <CommandGroup heading="Recent">
                {recentFiles.filter(f => !pinnedFiles.includes(f)).slice(0, 10).map((file) => (
                  <CommandItem
                    key={file}
                    onSelect={() => runCommand(() => setActiveFile(file))}
                  >
                    <FileCode className="mr-2 h-4 w-4" />
                    <span className="font-mono text-sm">{file.split("/").pop()}</span>
                    <span className="ml-2 text-xs text-muted-foreground truncate">
                      {file}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {openFiles.length > 0 && (
              <CommandGroup heading="Open Files">
                {openFiles.map((file) => (
                  <CommandItem
                    key={file.path}
                    onSelect={() => runCommand(() => setActiveFile(file.path))}
                  >
                    <FileCode className="mr-2 h-4 w-4" />
                    <span className="font-mono text-sm">{file.path.split("/").pop()}</span>
                    {file.isDirty && (
                      <span className="ml-2 text-xs text-amber-500">modified</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </>
        ) : (
          // Command mode
          <>
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
              <CommandItem onSelect={() => runCommand(() => { setMode("file"); })}>
                <Search className="mr-2 h-4 w-4" />
                Quick Open File
                <CommandShortcut>⌘P</CommandShortcut>
              </CommandItem>
            </CommandGroup>

            <CommandSeparator />

            <CommandGroup heading="Workspace">
              <CommandItem
                onSelect={() => runCommand(() => {
                  if (activeFilePath) setDiffMode(!diffMode, activeFilePath);
                })}
              >
                <GitCompare className="mr-2 h-4 w-4" />
                {diffMode ? "Close Diff View" : "Show Git Diff"}
                <CommandShortcut>⌘⇧D</CommandShortcut>
              </CommandItem>
              <CommandItem
                onSelect={() => runCommand(() => setTerminalOpen(!isTerminalOpen))}
              >
                <Terminal className="mr-2 h-4 w-4" />
                {isTerminalOpen ? "Hide Terminal" : "Show Terminal"}
                <CommandShortcut>⌘`</CommandShortcut>
              </CommandItem>
              <CommandItem
                onSelect={() => runCommand(() => setRightPanelMode("preview"))}
              >
                <Eye className="mr-2 h-4 w-4" />
                Show Preview Panel
              </CommandItem>
              <CommandItem
                onSelect={() => runCommand(() => setRightPanelMode("chat"))}
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                Show Chat Panel
              </CommandItem>
            </CommandGroup>

            {isExecuting && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Task Control">
                  <CommandItem onSelect={() => runCommand(() => {})}>
                    <Pause className="mr-2 h-4 w-4 text-amber-500" />
                    Pause Execution
                  </CommandItem>
                  <CommandItem onSelect={() => runCommand(() => {})}>
                    <Square className="mr-2 h-4 w-4 text-red-500" />
                    Cancel Task
                  </CommandItem>
                </CommandGroup>
              </>
            )}

            <CommandSeparator />

            <CommandGroup heading="Target Agent">
              <CommandItem
                onSelect={() => runCommand(() => setActiveAgent(null))}
              >
                <Bot className="mr-2 h-4 w-4 text-purple-500" />
                Auto (Wyld decides)
              </CommandItem>
              {availableAgents.map((agent) => {
                const icons: Record<string, React.ElementType> = {
                  wyld: Flame,
                  code: Code2,
                  data: Database,
                  infra: Server,
                  research: Search,
                  qa: ShieldCheck,
                };
                const Icon = icons[agent] || Bot;
                const colors: Record<string, string> = {
                  wyld: "text-purple-500",
                  code: "text-blue-500",
                  data: "text-emerald-500",
                  infra: "text-orange-500",
                  research: "text-cyan-500",
                  qa: "text-pink-500",
                };
                return (
                  <CommandItem
                    key={agent}
                    onSelect={() => runCommand(() => setActiveAgent(agent))}
                  >
                    <Icon className={`mr-2 h-4 w-4 ${colors[agent] || ""}`} />
                    <span className="capitalize">{agent}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>

            <CommandSeparator />

            <CommandGroup heading="Navigation">
              <CommandItem onSelect={() => runCommand(() => router.push("/chat"))}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Chat
                <CommandShortcut>C</CommandShortcut>
              </CommandItem>
              <CommandItem onSelect={() => runCommand(() => router.push("/agents"))}>
                <Bot className="mr-2 h-4 w-4" />
                Agents
                <CommandShortcut>A</CommandShortcut>
              </CommandItem>
              <CommandItem onSelect={() => runCommand(() => router.push("/domains"))}>
                <Globe className="mr-2 h-4 w-4" />
                Domains
                <CommandShortcut>D</CommandShortcut>
              </CommandItem>
              <CommandItem onSelect={() => runCommand(() => router.push("/memory"))}>
                <Brain className="mr-2 h-4 w-4" />
                Memory
                <CommandShortcut>M</CommandShortcut>
              </CommandItem>
              <CommandItem onSelect={() => runCommand(() => router.push("/settings"))}>
                <Settings className="mr-2 h-4 w-4" />
                Settings
                <CommandShortcut>S</CommandShortcut>
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
          </>
        )}
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

// Shortcut badges for displaying available shortcuts
export function KeyboardShortcuts() {
  return (
    <div className="text-xs text-muted-foreground space-y-1">
      <div className="flex justify-between">
        <span>Command palette</span>
        <kbd className="font-mono bg-muted px-1 rounded">⌘K</kbd>
      </div>
      <div className="flex justify-between">
        <span>Quick open</span>
        <kbd className="font-mono bg-muted px-1 rounded">⌘P</kbd>
      </div>
      <div className="flex justify-between">
        <span>Toggle diff</span>
        <kbd className="font-mono bg-muted px-1 rounded">⌘⇧D</kbd>
      </div>
      <div className="flex justify-between">
        <span>Toggle terminal</span>
        <kbd className="font-mono bg-muted px-1 rounded">⌘`</kbd>
      </div>
    </div>
  );
}
