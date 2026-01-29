import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ConsoleMessage {
  level: "log" | "warn" | "error" | "info" | "debug";
  message: string;
  timestamp: string;
  source?: string;
  line?: number;
}

export interface NetworkRequest {
  url: string;
  method: string;
  status?: number;
  statusText?: string;
  resourceType?: string;
  error?: string;
  timestamp: string;
}

export interface BrowserNarration {
  action: string;
  detail?: string;
  thumbnail?: string;
  url?: string;
  timestamp: string;
}

export interface BrowserPrompt {
  promptType: "auth" | "input" | "confirm" | "choice";
  message: string;
  options?: string[];
  correlationId?: string;
  timestamp: string;
}

export interface TestCredential {
  id: string;
  label: string; // e.g., "Admin Account", "Test User", "Provider Login"
  username: string;
  password: string;
  domain?: string; // Optional domain/site this credential is for
  notes?: string; // Additional notes about when to use
  createdAt: string;
}

// Playwright browser permissions
export type BrowserPermission =
  | "geolocation"
  | "midi"
  | "notifications"
  | "camera"
  | "microphone"
  | "clipboard-read"
  | "clipboard-write"
  | "payment-handler";

export interface BrowserPermissions {
  geolocation: boolean;
  camera: boolean;
  microphone: boolean;
  notifications: boolean;
  clipboard: boolean; // Covers clipboard-read and clipboard-write
  midi: boolean;
}

// Viewport presets
export interface ViewportPreset {
  id: string;
  name: string;
  width: number;
  height: number;
  deviceScaleFactor?: number;
  isMobile?: boolean;
  hasTouch?: boolean;
  category: "mobile" | "tablet" | "desktop" | "auto";
}

export const VIEWPORT_PRESETS: ViewportPreset[] = [
  // Auto-resize (matches container size)
  { id: "auto", name: "Auto (Fit Panel)", width: 0, height: 0, category: "auto" },

  // Mobile devices
  { id: "iphone-se", name: "iPhone SE", width: 375, height: 667, deviceScaleFactor: 2, isMobile: true, hasTouch: true, category: "mobile" },
  { id: "iphone-12", name: "iPhone 12/13", width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true, category: "mobile" },
  { id: "iphone-14-pro-max", name: "iPhone 14 Pro Max", width: 430, height: 932, deviceScaleFactor: 3, isMobile: true, hasTouch: true, category: "mobile" },
  { id: "pixel-5", name: "Pixel 5", width: 393, height: 851, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true, category: "mobile" },
  { id: "samsung-s21", name: "Samsung Galaxy S21", width: 360, height: 800, deviceScaleFactor: 3, isMobile: true, hasTouch: true, category: "mobile" },

  // Tablets
  { id: "ipad-mini", name: "iPad Mini", width: 768, height: 1024, deviceScaleFactor: 2, isMobile: true, hasTouch: true, category: "tablet" },
  { id: "ipad-air", name: "iPad Air", width: 820, height: 1180, deviceScaleFactor: 2, isMobile: true, hasTouch: true, category: "tablet" },
  { id: "ipad-pro-11", name: "iPad Pro 11\"", width: 834, height: 1194, deviceScaleFactor: 2, isMobile: true, hasTouch: true, category: "tablet" },
  { id: "ipad-pro-12", name: "iPad Pro 12.9\"", width: 1024, height: 1366, deviceScaleFactor: 2, isMobile: true, hasTouch: true, category: "tablet" },

  // Desktop
  { id: "laptop", name: "Laptop", width: 1280, height: 720, category: "desktop" },
  { id: "laptop-hd", name: "Laptop HD", width: 1366, height: 768, category: "desktop" },
  { id: "desktop", name: "Desktop", width: 1440, height: 900, category: "desktop" },
  { id: "desktop-hd", name: "Desktop HD", width: 1920, height: 1080, category: "desktop" },
  { id: "desktop-4k", name: "Desktop 4K", width: 2560, height: 1440, category: "desktop" },
];

// Keywords that suggest browser automation intent
export const BROWSER_INTENT_KEYWORDS = [
  // Navigation
  "go to", "navigate to", "open", "visit", "browse to", "load",
  // Checking/Testing
  "check the site", "check the page", "test the", "verify the",
  "look at", "show me", "see the", "view the",
  // Interaction
  "click on", "click the", "fill out", "fill in", "submit the form",
  "log in", "login", "sign in", "sign up",
  // Debugging
  "debug the", "inspect the", "check for errors", "find the bug",
  // Specific pages
  "homepage", "home page", "landing page", "login page", "checkout",
  // URLs
  "http://", "https://", ".com", ".org", ".net", ".io",
];

// Check if a message suggests browser automation intent
export function detectBrowserIntent(message: string): boolean {
  const lowerMessage = message.toLowerCase();
  return BROWSER_INTENT_KEYWORDS.some(keyword => lowerMessage.includes(keyword));
}

// Browser tool names that should trigger panel opening
export const BROWSER_TOOL_NAMES = [
  "browser_open", "browser_navigate", "browser_click", "browser_type",
  "browser_screenshot", "browser_get_content", "browser_wait",
  "browser_check_auth", "browser_prompt_user", "browser_evaluate",
  "browser_get_console_errors", "browser_get_network_errors",
  "browser_find_elements", "browser_scroll",
];

interface BrowserState {
  // Panel visibility (for chat browser panel)
  showChatBrowserPanel: boolean;

  // Connection state
  isConnected: boolean;
  sessionId: string | null;
  projectId: string | null;

  // Current page state
  currentUrl: string;
  pageTitle: string;
  isLoading: boolean;

  // Viewport
  currentFrame: string | null; // base64 encoded frame
  frameTimestamp: number;
  viewportWidth: number;
  viewportHeight: number;

  // Captured data
  consoleMessages: ConsoleMessage[];
  networkRequests: NetworkRequest[];
  narrations: BrowserNarration[];

  // Prompts
  activePrompt: BrowserPrompt | null;

  // Errors
  error: string | null;

  // Test credentials (persisted per project)
  credentials: Record<string, TestCredential[]>; // projectId -> credentials

  // Browser permissions (persisted per project)
  permissions: Record<string, BrowserPermissions>; // projectId -> permissions

  // Viewport settings (persisted per project)
  viewports: Record<string, string>; // projectId -> viewport preset id

  // Actions
  connect: (projectId: string) => void;
  disconnect: () => void;
  setConnected: (connected: boolean, sessionId?: string) => void;
  setCurrentUrl: (url: string, title?: string) => void;
  setLoading: (loading: boolean) => void;
  setFrame: (frame: string, timestamp?: number) => void;
  setViewport: (width: number, height: number) => void;
  addConsoleMessage: (message: ConsoleMessage) => void;
  addNetworkRequest: (request: NetworkRequest) => void;
  addNarration: (narration: BrowserNarration) => void;
  setActivePrompt: (prompt: BrowserPrompt | null) => void;
  setError: (error: string | null) => void;
  clearConsole: () => void;
  clearNetwork: () => void;
  clearNarrations: () => void;
  reset: () => void;

  // Credential actions
  addCredential: (projectId: string, credential: Omit<TestCredential, "id" | "createdAt">) => void;
  updateCredential: (projectId: string, id: string, updates: Partial<TestCredential>) => void;
  deleteCredential: (projectId: string, id: string) => void;
  getProjectCredentials: (projectId: string) => TestCredential[];

  // Permission actions
  setPermission: (projectId: string, permission: keyof BrowserPermissions, enabled: boolean) => void;
  getProjectPermissions: (projectId: string) => BrowserPermissions;
  getEnabledPermissions: (projectId: string) => BrowserPermission[];

  // Viewport actions
  setViewportPreset: (projectId: string, presetId: string) => void;
  getViewportPreset: (projectId: string) => ViewportPreset;

  // Panel visibility actions
  setShowChatBrowserPanel: (show: boolean) => void;
  openBrowserPanelIfNeeded: (message: string) => boolean; // Returns true if panel was opened
}

const initialState = {
  showChatBrowserPanel: false,
  isConnected: false,
  sessionId: null,
  projectId: null,
  currentUrl: "",
  pageTitle: "",
  isLoading: false,
  currentFrame: null,
  frameTimestamp: 0,
  viewportWidth: 1280,
  viewportHeight: 720,
  consoleMessages: [] as ConsoleMessage[],
  networkRequests: [] as NetworkRequest[],
  narrations: [] as BrowserNarration[],
  activePrompt: null as BrowserPrompt | null,
  error: null as string | null,
  credentials: {} as Record<string, TestCredential[]>,
  permissions: {} as Record<string, BrowserPermissions>,
  viewports: {} as Record<string, string>,
};

const defaultPermissions: BrowserPermissions = {
  geolocation: false,
  camera: false,
  microphone: false,
  notifications: false,
  clipboard: false,
  midi: false,
};

export const useBrowserStore = create<BrowserState>()(
  persist(
    (set, get) => ({
      ...initialState,

      connect: (projectId: string) => {
        set({
          projectId,
          isLoading: true,
          error: null,
        });
      },

      disconnect: () => {
        set({
          isConnected: false,
          sessionId: null,
          isLoading: false,
        });
      },

      setConnected: (connected: boolean, sessionId?: string) => {
        set({
          isConnected: connected,
          sessionId: sessionId || null,
          isLoading: false,
        });
      },

      setCurrentUrl: (url: string, title?: string) => {
        set({
          currentUrl: url,
          pageTitle: title || get().pageTitle,
        });
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      setFrame: (frame: string, timestamp?: number) => {
        set({
          currentFrame: frame,
          frameTimestamp: timestamp || Date.now(),
        });
      },

      setViewport: (width: number, height: number) => {
        set({
          viewportWidth: width,
          viewportHeight: height,
        });
      },

      addConsoleMessage: (message: ConsoleMessage) => {
        set((state) => ({
          consoleMessages: [...state.consoleMessages.slice(-99), message],
        }));
      },

      addNetworkRequest: (request: NetworkRequest) => {
        set((state) => ({
          networkRequests: [...state.networkRequests.slice(-99), request],
        }));
      },

      addNarration: (narration: BrowserNarration) => {
        set((state) => ({
          narrations: [...state.narrations.slice(-49), narration],
        }));
      },

      setActivePrompt: (prompt: BrowserPrompt | null) => {
        set({ activePrompt: prompt });
      },

      setError: (error: string | null) => {
        set({ error, isLoading: false });
      },

      clearConsole: () => {
        set({ consoleMessages: [] });
      },

      clearNetwork: () => {
        set({ networkRequests: [] });
      },

      clearNarrations: () => {
        set({ narrations: [] });
      },

      reset: () => {
        // Keep credentials when resetting other state
        const { credentials } = get();
        set({ ...initialState, credentials });
      },

      // Credential management
      addCredential: (projectId: string, credential: Omit<TestCredential, "id" | "createdAt">) => {
        const id = crypto.randomUUID();
        const newCredential: TestCredential = {
          ...credential,
          id,
          createdAt: new Date().toISOString(),
        };
        set((state) => ({
          credentials: {
            ...state.credentials,
            [projectId]: [...(state.credentials[projectId] || []), newCredential],
          },
        }));
      },

      updateCredential: (projectId: string, id: string, updates: Partial<TestCredential>) => {
        set((state) => ({
          credentials: {
            ...state.credentials,
            [projectId]: (state.credentials[projectId] || []).map((cred) =>
              cred.id === id ? { ...cred, ...updates } : cred
            ),
          },
        }));
      },

      deleteCredential: (projectId: string, id: string) => {
        set((state) => ({
          credentials: {
            ...state.credentials,
            [projectId]: (state.credentials[projectId] || []).filter((cred) => cred.id !== id),
          },
        }));
      },

      getProjectCredentials: (projectId: string) => {
        return get().credentials[projectId] || [];
      },

      // Permission management
      setPermission: (projectId: string, permission: keyof BrowserPermissions, enabled: boolean) => {
        set((state) => ({
          permissions: {
            ...state.permissions,
            [projectId]: {
              ...(state.permissions[projectId] || defaultPermissions),
              [permission]: enabled,
            },
          },
        }));
      },

      getProjectPermissions: (projectId: string) => {
        return get().permissions[projectId] || defaultPermissions;
      },

      getEnabledPermissions: (projectId: string) => {
        const perms = get().permissions[projectId] || defaultPermissions;
        const enabled: BrowserPermission[] = [];
        if (perms.geolocation) enabled.push("geolocation");
        if (perms.camera) enabled.push("camera");
        if (perms.microphone) enabled.push("microphone");
        if (perms.notifications) enabled.push("notifications");
        if (perms.clipboard) {
          enabled.push("clipboard-read");
          enabled.push("clipboard-write");
        }
        if (perms.midi) enabled.push("midi");
        return enabled;
      },

      // Viewport management
      setViewportPreset: (projectId: string, presetId: string) => {
        set((state) => ({
          viewports: {
            ...state.viewports,
            [projectId]: presetId,
          },
        }));
      },

      getViewportPreset: (projectId: string) => {
        const presetId = get().viewports[projectId] || "auto";
        return VIEWPORT_PRESETS.find((p) => p.id === presetId) || VIEWPORT_PRESETS.find((p) => p.id === "auto")!;
      },

      // Panel visibility
      setShowChatBrowserPanel: (show: boolean) => {
        set({ showChatBrowserPanel: show });
      },

      openBrowserPanelIfNeeded: (message: string) => {
        if (get().showChatBrowserPanel) return false; // Already open
        if (detectBrowserIntent(message)) {
          set({ showChatBrowserPanel: true });
          return true;
        }
        return false;
      },
    }),
    {
      name: "browser-settings",
      // Persist credentials, permissions, and viewports
      partialize: (state) => ({
        credentials: state.credentials,
        permissions: state.permissions,
        viewports: state.viewports,
      }),
    }
  )
);
