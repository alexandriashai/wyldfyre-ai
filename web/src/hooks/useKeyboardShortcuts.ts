"use client";

import { useEffect, useCallback } from "react";

type KeyboardShortcut = {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  callback: () => void;
  description?: string;
};

type UseKeyboardShortcutsOptions = {
  enabled?: boolean;
  preventDefault?: boolean;
};

/**
 * Hook for managing keyboard shortcuts
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  options: UseKeyboardShortcutsOptions = {}
) {
  const { enabled = true, preventDefault = true } = options;

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Don't trigger shortcuts when typing in inputs
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        // Allow Escape key in inputs
        if (event.key !== "Escape") return;
      }

      for (const shortcut of shortcuts) {
        const matchesKey = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const matchesCtrl = shortcut.ctrlKey ? event.ctrlKey : !event.ctrlKey;
        const matchesMeta = shortcut.metaKey ? event.metaKey : !event.metaKey;
        const matchesShift = shortcut.shiftKey ? event.shiftKey : !event.shiftKey;
        const matchesAlt = shortcut.altKey ? event.altKey : !event.altKey;

        // For cross-platform support, check both Ctrl and Meta for "Ctrl+X" shortcuts
        const matchesModifier =
          (shortcut.ctrlKey && (event.ctrlKey || event.metaKey)) ||
          (shortcut.metaKey && (event.metaKey || event.ctrlKey)) ||
          (matchesCtrl && matchesMeta);

        if (
          matchesKey &&
          matchesModifier &&
          matchesShift &&
          matchesAlt
        ) {
          if (preventDefault) {
            event.preventDefault();
          }
          shortcut.callback();
          return;
        }
      }
    },
    [shortcuts, enabled, preventDefault]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Common keyboard shortcuts for the app
 */
export function useAppShortcuts({
  onNewChat,
  onToggleSidebar,
  onSearch,
  onEscape,
}: {
  onNewChat?: () => void;
  onToggleSidebar?: () => void;
  onSearch?: () => void;
  onEscape?: () => void;
}) {
  const shortcuts: KeyboardShortcut[] = [];

  if (onNewChat) {
    shortcuts.push({
      key: "n",
      ctrlKey: true,
      callback: onNewChat,
      description: "New conversation",
    });
  }

  if (onToggleSidebar) {
    shortcuts.push({
      key: "b",
      ctrlKey: true,
      callback: onToggleSidebar,
      description: "Toggle sidebar",
    });
  }

  if (onSearch) {
    shortcuts.push({
      key: "/",
      callback: onSearch,
      description: "Focus search",
    });
  }

  if (onEscape) {
    shortcuts.push({
      key: "Escape",
      callback: onEscape,
      description: "Close/Cancel",
    });
  }

  useKeyboardShortcuts(shortcuts);
}

/**
 * Hook to focus an element with a keyboard shortcut
 */
export function useFocusShortcut(
  ref: React.RefObject<HTMLElement>,
  key: string,
  modifiers: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean } = {}
) {
  useKeyboardShortcuts([
    {
      key,
      ...modifiers,
      callback: () => ref.current?.focus(),
    },
  ]);
}
