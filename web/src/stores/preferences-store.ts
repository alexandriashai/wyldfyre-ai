import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ShortcutBinding {
  id: string;
  label: string;
  key: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
}

export interface UserPreferences {
  // Appearance
  theme: "light" | "dark" | "system";
  accentColor: string;
  fontSize: number;
  compactMode: boolean;

  // Agent preferences
  defaultModelTier: "standard" | "advanced" | "reasoning";
  maxIterations: number;
  autoApprovePlans: boolean;
  preferredAgent: string;

  // Accessibility
  reducedMotion: boolean;
  highContrast: boolean;
  screenReaderHints: boolean;

  // Keyboard shortcuts
  shortcuts: ShortcutBinding[];
}

interface PreferencesState extends UserPreferences {
  // Actions
  setTheme: (theme: "light" | "dark" | "system") => void;
  setAccentColor: (color: string) => void;
  setFontSize: (size: number) => void;
  setCompactMode: (compact: boolean) => void;
  setDefaultModelTier: (tier: "standard" | "advanced" | "reasoning") => void;
  setMaxIterations: (max: number) => void;
  setAutoApprovePlans: (auto: boolean) => void;
  setPreferredAgent: (agent: string) => void;
  setReducedMotion: (reduced: boolean) => void;
  setHighContrast: (high: boolean) => void;
  setScreenReaderHints: (hints: boolean) => void;
  updateShortcut: (id: string, binding: Partial<ShortcutBinding>) => void;
  resetShortcuts: () => void;
  resetAll: () => void;
}

const DEFAULT_SHORTCUTS: ShortcutBinding[] = [
  { id: "new-chat", label: "New Conversation", key: "n", ctrlKey: true },
  { id: "toggle-sidebar", label: "Toggle Sidebar", key: "b", ctrlKey: true },
  { id: "search", label: "Focus Search", key: "/", ctrlKey: false },
  { id: "escape", label: "Close/Cancel", key: "Escape" },
  { id: "send-message", label: "Send Message", key: "Enter", ctrlKey: false },
  { id: "new-line", label: "New Line in Input", key: "Enter", shiftKey: true },
  { id: "toggle-agent-panel", label: "Toggle Agent Panel", key: ".", ctrlKey: true },
  { id: "focus-input", label: "Focus Chat Input", key: "i", ctrlKey: true },
];

const ACCENT_COLORS = [
  "#6366f1", // indigo (default)
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#f43f5e", // rose
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#14b8a6", // teal
  "#06b6d4", // cyan
  "#3b82f6", // blue
];

export { ACCENT_COLORS };

const DEFAULT_PREFERENCES: Omit<UserPreferences, never> = {
  theme: "system",
  accentColor: "#6366f1",
  fontSize: 14,
  compactMode: false,
  defaultModelTier: "advanced",
  maxIterations: 25,
  autoApprovePlans: false,
  preferredAgent: "auto",
  reducedMotion: false,
  highContrast: false,
  screenReaderHints: false,
  shortcuts: DEFAULT_SHORTCUTS,
};

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      ...DEFAULT_PREFERENCES,

      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
      setAccentColor: (accentColor) => {
        set({ accentColor });
        applyAccentColor(accentColor);
      },
      setFontSize: (fontSize) => {
        set({ fontSize });
        applyFontSize(fontSize);
      },
      setCompactMode: (compactMode) => set({ compactMode }),
      setDefaultModelTier: (defaultModelTier) => set({ defaultModelTier }),
      setMaxIterations: (maxIterations) => set({ maxIterations }),
      setAutoApprovePlans: (autoApprovePlans) => set({ autoApprovePlans }),
      setPreferredAgent: (preferredAgent) => set({ preferredAgent }),
      setReducedMotion: (reducedMotion) => {
        set({ reducedMotion });
        applyReducedMotion(reducedMotion);
      },
      setHighContrast: (highContrast) => {
        set({ highContrast });
        applyHighContrast(highContrast);
      },
      setScreenReaderHints: (screenReaderHints) => set({ screenReaderHints }),
      updateShortcut: (id, binding) => {
        set((state) => ({
          shortcuts: state.shortcuts.map((s) =>
            s.id === id ? { ...s, ...binding } : s
          ),
        }));
      },
      resetShortcuts: () => set({ shortcuts: DEFAULT_SHORTCUTS }),
      resetAll: () => {
        set(DEFAULT_PREFERENCES);
        applyTheme(DEFAULT_PREFERENCES.theme);
        applyAccentColor(DEFAULT_PREFERENCES.accentColor);
        applyFontSize(DEFAULT_PREFERENCES.fontSize);
        applyReducedMotion(DEFAULT_PREFERENCES.reducedMotion);
        applyHighContrast(DEFAULT_PREFERENCES.highContrast);
      },
    }),
    {
      name: "wyld-preferences",
    }
  )
);

// CSS variable application functions
function applyTheme(theme: "light" | "dark" | "system") {
  if (typeof window === "undefined") return;
  const root = document.documentElement;

  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", prefersDark);
  } else {
    root.classList.toggle("dark", theme === "dark");
  }
}

function applyAccentColor(color: string) {
  if (typeof window === "undefined") return;
  document.documentElement.style.setProperty("--accent-color", color);
  // Convert hex to HSL for Tailwind compatibility
  const hsl = hexToHSL(color);
  if (hsl) {
    document.documentElement.style.setProperty("--primary", `${hsl.h} ${hsl.s}% ${hsl.l}%`);
  }
}

function applyFontSize(size: number) {
  if (typeof window === "undefined") return;
  document.documentElement.style.setProperty("--base-font-size", `${size}px`);
}

function applyReducedMotion(reduced: boolean) {
  if (typeof window === "undefined") return;
  document.documentElement.classList.toggle("reduce-motion", reduced);
}

function applyHighContrast(high: boolean) {
  if (typeof window === "undefined") return;
  document.documentElement.classList.toggle("high-contrast", high);
}

function hexToHSL(hex: string): { h: number; s: number; l: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return null;

  let r = parseInt(result[1], 16) / 255;
  let g = parseInt(result[2], 16) / 255;
  let b = parseInt(result[3], 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }

  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

// Initialize preferences on load
export function initializePreferences() {
  if (typeof window === "undefined") return;
  const state = usePreferencesStore.getState();
  applyTheme(state.theme);
  applyAccentColor(state.accentColor);
  applyFontSize(state.fontSize);
  applyReducedMotion(state.reducedMotion);
  applyHighContrast(state.highContrast);
}
