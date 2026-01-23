"use client";

import { useEffect, useCallback } from "react";
import { usePreferencesStore, ShortcutBinding } from "@/stores/preferences-store";

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
 * Get a configured shortcut binding by ID, falling back to default if not found
 */
function getConfiguredBinding(shortcuts: ShortcutBinding[], id: string): ShortcutBinding | undefined {
  return shortcuts.find((s) => s.id === id);
}

/**
 * Common keyboard shortcuts for the app - uses configurable bindings from preferences
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
  const configuredShortcuts = usePreferencesStore((s) => s.shortcuts);
  const shortcuts: KeyboardShortcut[] = [];

  if (onNewChat) {
    const binding = getConfiguredBinding(configuredShortcuts, "new-chat");
    shortcuts.push({
      key: binding?.key || "n",
      ctrlKey: binding?.ctrlKey ?? true,
      shiftKey: binding?.shiftKey,
      altKey: binding?.altKey,
      callback: onNewChat,
      description: "New conversation",
    });
  }

  if (onToggleSidebar) {
    const binding = getConfiguredBinding(configuredShortcuts, "toggle-sidebar");
    shortcuts.push({
      key: binding?.key || "b",
      ctrlKey: binding?.ctrlKey ?? true,
      shiftKey: binding?.shiftKey,
      altKey: binding?.altKey,
      callback: onToggleSidebar,
      description: "Toggle sidebar",
    });
  }

  if (onSearch) {
    const binding = getConfiguredBinding(configuredShortcuts, "search");
    shortcuts.push({
      key: binding?.key || "/",
      ctrlKey: binding?.ctrlKey,
      shiftKey: binding?.shiftKey,
      altKey: binding?.altKey,
      callback: onSearch,
      description: "Focus search",
    });
  }

  if (onEscape) {
    const binding = getConfiguredBinding(configuredShortcuts, "escape");
    shortcuts.push({
      key: binding?.key || "Escape",
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

/**
 * Format a shortcut binding for display
 */
export function formatShortcut(binding: ShortcutBinding): string {
  const parts: string[] = [];
  if (binding.ctrlKey) parts.push("Ctrl");
  if (binding.shiftKey) parts.push("Shift");
  if (binding.altKey) parts.push("Alt");

  const keyDisplay = binding.key === " " ? "Space" :
    binding.key === "Escape" ? "Esc" :
    binding.key === "Enter" ? "Enter" :
    binding.key === "ArrowUp" ? "Up" :
    binding.key === "ArrowDown" ? "Down" :
    binding.key === "ArrowLeft" ? "Left" :
    binding.key === "ArrowRight" ? "Right" :
    binding.key.length === 1 ? binding.key.toUpperCase() :
    binding.key;

  parts.push(keyDisplay);
  return parts.join(" + ");
}
