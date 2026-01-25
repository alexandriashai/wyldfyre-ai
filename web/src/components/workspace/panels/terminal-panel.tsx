"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useProjectStore } from "@/stores/project-store";
import { Button } from "@/components/ui/button";
import { X, Container, Terminal, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import "@xterm/xterm/css/xterm.css";

// Common terminal keyboard shortcuts for mobile
const MOBILE_KEYS = [
  { label: "Tab", code: "\t" },
  { label: "Esc", code: "\x1b" },
  { label: "Ctrl+C", code: "\x03" },
  { label: "Ctrl+D", code: "\x04" },
  { label: "Ctrl+Z", code: "\x1a" },
  { label: "Ctrl+L", code: "\x0c" },
] as const;

const ARROW_KEYS = [
  { label: "↑", code: "\x1b[A", icon: ChevronUp },
  { label: "↓", code: "\x1b[B", icon: ChevronDown },
  { label: "←", code: "\x1b[D", icon: ChevronLeft },
  { label: "→", code: "\x1b[C", icon: ChevronRight },
] as const;

interface TerminalPanelProps {
  /** Force always show (for mobile tab mode) */
  alwaysShow?: boolean;
  /** Force mobile view (passed from mobile workspace) */
  isMobileView?: boolean;
}

export function TerminalPanel({ alwaysShow = false, isMobileView = false }: TerminalPanelProps) {
  const { token } = useAuthStore();
  const { activeProjectId, isTerminalOpen, setTerminalOpen, setMobileActiveTab } = useWorkspaceStore();
  const { selectedProject } = useProjectStore();

  // Detect mobile viewport (or use prop)
  const [detectedMobile, setDetectedMobile] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const searchAddonRef = useRef<any>(null);

  useEffect(() => {
    const checkMobile = () => setDetectedMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Use prop if provided, otherwise use detection
  const isMobile = isMobileView || detectedMobile;

  // On mobile, always show when rendered; on desktop, use isTerminalOpen
  const shouldShow = isMobile || alwaysShow || isTerminalOpen;
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<any>(null);

  const focusTerminal = useCallback(() => {
    if (!xtermRef.current) return;

    // Focus the terminal
    xtermRef.current.focus();

    // On mobile, also try to focus the internal textarea directly
    if (isMobile && terminalRef.current) {
      const textarea = terminalRef.current.querySelector('textarea');
      if (textarea) {
        textarea.focus();
        // Force mobile keyboard to appear
        textarea.click();
      }
    }
  }, [isMobile]);

  const sendKey = useCallback((code: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(new TextEncoder().encode(code));
    focusTerminal();
  }, [focusTerminal]);

  const toggleSearch = useCallback(() => {
    if (!searchAddonRef.current) return;
    if (showSearch) {
      searchAddonRef.current.clearDecorations();
    }
    setShowSearch(!showSearch);
  }, [showSearch]);

  const initTerminal = useCallback(async () => {
    if (!terminalRef.current || !token || !activeProjectId || !selectedProject) return;

    // Dynamic imports for xterm (client-only)
    const { Terminal } = await import("@xterm/xterm");
    const { FitAddon } = await import("@xterm/addon-fit");
    const { WebLinksAddon } = await import("@xterm/addon-web-links");
    const { SearchAddon } = await import("@xterm/addon-search");
    const { Unicode11Addon } = await import("@xterm/addon-unicode11");

    // WebGL addon disabled - causes rendering issues on some devices
    // TODO: Re-enable with proper fallback detection
    const WebglAddon: any = null;

    // Clean up existing instance
    if (xtermRef.current) {
      xtermRef.current.dispose();
    }
    if (wsRef.current) {
      wsRef.current.close();
    }

    const term = new Terminal({
      fontSize: isMobile ? 14 : 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      theme: {
        background: "#1a1b26",
        foreground: "#a9b1d6",
        cursor: "#c0caf5",
        cursorAccent: "#1a1b26",
        selectionBackground: "#33467c",
        black: "#32344a",
        red: "#f7768e",
        green: "#9ece6a",
        yellow: "#e0af68",
        blue: "#7aa2f7",
        magenta: "#ad8ee6",
        cyan: "#449dab",
        white: "#787c99",
        brightBlack: "#444b6a",
        brightRed: "#ff7a93",
        brightGreen: "#b9f27c",
        brightYellow: "#ff9e64",
        brightBlue: "#7da6ff",
        brightMagenta: "#bb9af7",
        brightCyan: "#0db9d7",
        brightWhite: "#acb0d0",
      },
      cursorBlink: true,
      allowProposedApi: true,
      scrollback: 10000,
      // Mobile-specific settings
      screenReaderMode: false,
      macOptionIsMeta: true,
      // Enable copy on selection
      rightClickSelectsWord: true,
    });

    // Load addons
    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    const searchAddon = new SearchAddon();
    const unicode11Addon = new Unicode11Addon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.loadAddon(searchAddon);
    term.loadAddon(unicode11Addon);

    // Activate unicode 11 for better emoji support
    term.unicode.activeVersion = '11';

    // Open terminal in DOM
    term.open(terminalRef.current);

    // WebGL addon disabled - see above

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;
    searchAddonRef.current = searchAddon;

    // Fit terminal and get dimensions
    const doFit = () => {
      if (!terminalRef.current || !fitAddonRef.current) return { rows: 24, cols: 80 };
      const rect = terminalRef.current.getBoundingClientRect();
      // Only fit if container has actual dimensions
      if (rect.width > 50 && rect.height > 50) {
        try {
          fitAddonRef.current.fit();
          return { rows: term.rows, cols: term.cols };
        } catch {
          // Ignore fit errors
        }
      }
      return { rows: term.rows || 24, cols: term.cols || 80 };
    };

    // Build WebSocket URL
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const apiHost = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, "") || "localhost:8000";
    const rootPath = selectedProject.root_path || "/tmp";
    const terminalUser = (selectedProject as any).terminal_user || "";
    const projectName = selectedProject.name || "";
    const dockerEnabled = (selectedProject as any).docker_enabled || false;

    let wsUrl = `${wsProtocol}//${apiHost}/ws/terminal?token=${encodeURIComponent(token)}&project_id=${encodeURIComponent(activeProjectId)}&root_path=${encodeURIComponent(rootPath)}&project_name=${encodeURIComponent(projectName)}&docker_enabled=${dockerEnabled}`;
    if (!dockerEnabled && terminalUser) {
      wsUrl += `&terminal_user=${encodeURIComponent(terminalUser)}`;
    }

    // Initial fit
    doFit();

    // Connect WebSocket after a brief delay to ensure dimensions are ready
    const connectTimeout = setTimeout(() => {
      const { rows, cols } = doFit();

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      // Send resize function
      const sendResize = () => {
        if (ws.readyState === WebSocket.OPEN) {
          const { rows, cols } = doFit();
          ws.send(JSON.stringify({ type: "resize", rows, cols }));
          // Also send a special tmux refresh command
          ws.send(JSON.stringify({ type: "tmux-refresh" }));
        }
      };

      ws.onopen = () => {
        // Send initial size immediately
        console.log(`Terminal connected with size: ${cols}x${rows}`);
        ws.send(JSON.stringify({ type: "resize", rows, cols }));

        // Send multiple resize signals to ensure tmux picks up the size
        // This is needed because tmux may not resize on first message
        setTimeout(sendResize, 100);
        setTimeout(sendResize, 300);
        setTimeout(sendResize, 500);
        setTimeout(sendResize, 1000);

        // On mobile, be more aggressive with resize signals
        if (isMobile) {
          setTimeout(sendResize, 1500);
          setTimeout(sendResize, 2000);
          setTimeout(sendResize, 3000);
        }

        // Focus terminal after connection
        setTimeout(() => term.focus(), 200);
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(event.data));
        } else {
          term.write(event.data);
        }
      };

      ws.onclose = () => {
        term.write("\r\n\x1b[33m[Terminal disconnected]\x1b[0m\r\n");
      };

      ws.onerror = () => {
        term.write("\r\n\x1b[31m[Connection error]\x1b[0m\r\n");
      };

      // Send input to WebSocket
      term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(new TextEncoder().encode(data));
        }
      });

      // Handle terminal resize - send to backend
      term.onResize(({ rows, cols }) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "resize", rows, cols }));
        }
      });

      // Clipboard handling
      term.attachCustomKeyEventHandler((event) => {
        // Ctrl+Shift+F for search
        if (event.ctrlKey && event.shiftKey && event.key === 'F') {
          toggleSearch();
          return false;
        }
        // Copy: Ctrl+Shift+C (Windows/Linux) or Cmd+C (Mac)
        if ((event.ctrlKey && event.shiftKey && event.key === 'C') ||
            (event.metaKey && event.key === 'c')) {
          const selection = term.getSelection();
          if (selection) {
            navigator.clipboard.writeText(selection);
            return false;
          }
        }
        // Paste: Ctrl+Shift+V (Windows/Linux) or Cmd+V (Mac)
        if ((event.ctrlKey && event.shiftKey && event.key === 'V') ||
            (event.metaKey && event.key === 'v')) {
          navigator.clipboard.readText().then(text => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(new TextEncoder().encode(text));
            }
          });
          return false;
        }
        return true;
      });

    }, isMobile ? 300 : 100);

    // Right-click to copy selection
    const contextHandler = (e: MouseEvent) => {
      const selection = term.getSelection();
      if (selection) {
        e.preventDefault();
        navigator.clipboard.writeText(selection);
      }
    };
    terminalRef.current?.addEventListener('contextmenu', contextHandler);

    // Cleanup function
    return () => {
      clearTimeout(connectTimeout);
      terminalRef.current?.removeEventListener('contextmenu', contextHandler);
    };
  }, [token, activeProjectId, selectedProject, isMobile, toggleSearch]);

  useEffect(() => {
    let cleanup: (() => void) | undefined;

    if (shouldShow) {
      const init = async () => {
        cleanup = await initTerminal();
      };
      init();
    }

    return () => {
      cleanup?.();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (xtermRef.current) {
        xtermRef.current.dispose();
        xtermRef.current = null;
      }
    };
  }, [shouldShow, initTerminal]);

  // Handle container resize with debouncing
  useEffect(() => {
    if (!shouldShow || !fitAddonRef.current) return;

    let fitTimeout: NodeJS.Timeout;
    const debouncedFit = () => {
      clearTimeout(fitTimeout);
      fitTimeout = setTimeout(() => {
        try {
          fitAddonRef.current?.fit();
        } catch {
          // Ignore fit errors during transitions
        }
      }, 50);
    };

    const observer = new ResizeObserver(() => {
      debouncedFit();
    });

    // Observe both the terminal element and its container
    if (terminalRef.current) {
      observer.observe(terminalRef.current);
    }
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    // Also fit on window resize
    window.addEventListener('resize', debouncedFit);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', debouncedFit);
      clearTimeout(fitTimeout);
    };
  }, [shouldShow]);

  if (!shouldShow) return null;

  return (
    <div
      ref={containerRef}
      className="flex flex-col bg-[#1a1b26] h-full w-full"
    >
      {/* Terminal header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#32344a] shrink-0 h-8">
        <div className="flex items-center gap-2">
          {(selectedProject as any)?.docker_enabled ? (
            <Container className="h-3.5 w-3.5 text-blue-400" />
          ) : (
            <Terminal className="h-3.5 w-3.5 text-green-400" />
          )}
          <span className="text-xs font-medium text-[#a9b1d6]">
            {(selectedProject as any)?.docker_enabled ? "Container" : "Terminal"} — {selectedProject?.name || "Project"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-[#a9b1d6] hover:text-white hover:bg-[#32344a]"
            onClick={toggleSearch}
            title="Search (Ctrl+Shift+F)"
          >
            <Search className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-[#a9b1d6] hover:text-white hover:bg-[#32344a]"
            onClick={() => {
              if (isMobile) {
                setMobileActiveTab("editor");
              } else {
                setTerminalOpen(false);
              }
            }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Search bar */}
      {showSearch && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[#32344a] bg-[#24253a] shrink-0">
          <input
            type="text"
            placeholder="Search..."
            className="flex-1 bg-[#1a1b26] text-[#a9b1d6] text-xs px-2 py-1 rounded border border-[#32344a] focus:outline-none focus:border-[#7aa2f7]"
            onChange={(e) => {
              if (searchAddonRef.current) {
                searchAddonRef.current.findNext(e.target.value);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                searchAddonRef.current?.findNext(e.currentTarget.value);
              } else if (e.key === 'Escape') {
                setShowSearch(false);
                searchAddonRef.current?.clearDecorations();
              }
            }}
            autoFocus
          />
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-[#a9b1d6] hover:text-white"
            onClick={() => {
              const input = containerRef.current?.querySelector('input');
              if (input && searchAddonRef.current) {
                searchAddonRef.current.findPrevious(input.value);
              }
            }}
          >
            Prev
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs text-[#a9b1d6] hover:text-white"
            onClick={() => {
              const input = containerRef.current?.querySelector('input');
              if (input && searchAddonRef.current) {
                searchAddonRef.current.findNext(input.value);
              }
            }}
          >
            Next
          </Button>
        </div>
      )}

      {/* Mobile keyboard toolbar */}
      {isMobile && (
        <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[#32344a] bg-[#24253a] overflow-x-auto shrink-0">
          {/* Common keys */}
          {MOBILE_KEYS.map((key) => (
            <button
              key={key.label}
              onClick={() => sendKey(key.code)}
              className="px-2.5 py-1 text-xs font-medium bg-[#32344a] text-[#a9b1d6] rounded hover:bg-[#414868] active:bg-[#565f89] whitespace-nowrap"
            >
              {key.label}
            </button>
          ))}

          {/* Separator */}
          <div className="w-px h-5 bg-[#32344a] mx-1" />

          {/* Arrow keys */}
          {ARROW_KEYS.map((key) => {
            const Icon = key.icon;
            return (
              <button
                key={key.label}
                onClick={() => sendKey(key.code)}
                className="p-1.5 bg-[#32344a] text-[#a9b1d6] rounded hover:bg-[#414868] active:bg-[#565f89]"
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
        </div>
      )}

      {/* Terminal container */}
      <div
        ref={terminalRef}
        className="flex-1 min-h-0 overflow-hidden"
        style={{
          // Use flexbox to fill remaining space
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={focusTerminal}
        onTouchEnd={(e) => {
          e.preventDefault();
          focusTerminal();
        }}
      />
    </div>
  );
}
