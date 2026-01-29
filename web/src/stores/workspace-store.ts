import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number | null;
  modified_at?: string | null;
  children?: FileNode[] | null;
  is_binary?: boolean;
}

export interface OpenFile {
  path: string;
  content: string;
  originalContent: string;
  language: string | null;
  isDirty: boolean;
  is_binary?: boolean;
}

export interface GitFileStatus {
  path: string;
  status: string;
}

export interface GitStatus {
  branch: string | null;
  is_clean: boolean;
  modified: GitFileStatus[];
  untracked: string[];
  staged: GitFileStatus[];
  ahead: number;
  behind: number;
  has_remote: boolean;
}

export interface DeployStatus {
  isDeploying: boolean;
  stage: string | null;
  progress: number;
  error: string | null;
}

interface WorkspaceState {
  // Project/Domain selection
  activeProjectId: string | null;
  activeDomainId: string | null;

  // File tree
  fileTree: FileNode[];
  expandedPaths: Set<string>;
  isFileTreeLoading: boolean;

  // Editor
  openFiles: OpenFile[];
  activeFilePath: string | null;

  // Panels
  rightPanelMode: 'preview' | 'chat' | 'design';
  panelSizes: number[];
  isFileTreeCollapsed: boolean;
  isFileChatExpanded: boolean;
  isChatSidebarCollapsed: boolean;
  isTerminalOpen: boolean;
  splitEditor: boolean;
  splitFilePath: string | null;
  diffMode: boolean;
  diffFilePath: string | null;

  // Mobile
  mobileActiveTab: 'files' | 'editor' | 'git' | 'terminal' | 'browser' | 'chat';

  // Settings
  autoSave: boolean;
  autoSaveDelay: number;
  showHiddenFiles: boolean;

  // Deploy
  deployStatus: DeployStatus;

  // Git
  gitStatus: GitStatus | null;

  // Search
  searchQuery: string;
  isSearchOpen: boolean;

  // Pinned files
  pinnedFiles: string[];

  // Recent files
  recentFiles: string[];

  // Chat-linked file (for file-specific chat context)
  linkedFile: string | null;

  // Current active file path (shortcut)
  activeFile: string | null;

  // Actions
  setActiveProject: (id: string | null) => void;
  setActiveDomain: (id: string | null) => void;
  setFileTree: (tree: FileNode[]) => void;
  setFileTreeLoading: (loading: boolean) => void;
  toggleExpanded: (path: string) => void;
  setExpandedPaths: (paths: Set<string>) => void;
  openFile: (file: OpenFile) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  updateFileContent: (path: string, content: string) => void;
  markFileSaved: (path: string) => void;
  setRightPanelMode: (mode: 'preview' | 'chat' | 'design') => void;
  setPanelSizes: (sizes: number[]) => void;
  setFileTreeCollapsed: (collapsed: boolean) => void;
  setFileChatExpanded: (expanded: boolean) => void;
  setChatSidebarCollapsed: (collapsed: boolean) => void;
  setTerminalOpen: (open: boolean) => void;
  setSplitEditor: (split: boolean, filePath?: string | null) => void;
  setDiffMode: (enabled: boolean, filePath?: string | null) => void;
  setMobileActiveTab: (tab: 'files' | 'editor' | 'git' | 'terminal' | 'browser' | 'chat') => void;
  setAutoSave: (enabled: boolean) => void;
  setShowHiddenFiles: (show: boolean) => void;
  setDeployStatus: (status: Partial<DeployStatus>) => void;
  setGitStatus: (status: GitStatus | null) => void;
  setSearchQuery: (query: string) => void;
  setSearchOpen: (open: boolean) => void;
  togglePinnedFile: (path: string) => void;
  addRecentFile: (path: string) => void;
  refreshFileInTree: (path: string, node: FileNode) => void;
  removeFileFromTree: (path: string) => void;
  setLinkedFile: (path: string | null) => void;
  clearOpenFiles: () => void;
  markBranchChanged: () => void;
  branchChangeCounter: number;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      // Initial state
      activeProjectId: null,
      activeDomainId: null,
      fileTree: [],
      expandedPaths: new Set<string>(),
      isFileTreeLoading: false,
      openFiles: [],
      activeFilePath: null,
      rightPanelMode: 'preview',
      panelSizes: [15, 55, 30],
      isFileTreeCollapsed: false,
      isFileChatExpanded: true,
      isChatSidebarCollapsed: false,
      isTerminalOpen: false,
      splitEditor: false,
      splitFilePath: null,
      diffMode: false,
      diffFilePath: null,
      mobileActiveTab: 'files',
      autoSave: true,
      autoSaveDelay: 10000,
      showHiddenFiles: false,
      deployStatus: { isDeploying: false, stage: null, progress: 0, error: null },
      gitStatus: null,
      searchQuery: '',
      isSearchOpen: false,
      pinnedFiles: [],
      recentFiles: [],
      linkedFile: null,
      activeFile: null,
      branchChangeCounter: 0,

      // Actions
      setActiveProject: (id) => set({
        activeProjectId: id,
        openFiles: [],
        activeFilePath: null,
        fileTree: [],
        expandedPaths: new Set<string>(),
        gitStatus: null,
        searchQuery: "",
        isSearchOpen: false,
        deployStatus: { isDeploying: false, stage: null, progress: 0, error: null },
      }),
      setActiveDomain: (id) => set({ activeDomainId: id }),

      setFileTree: (tree) => set({ fileTree: tree }),
      setFileTreeLoading: (loading) => set({ isFileTreeLoading: loading }),

      toggleExpanded: (path) => set((state) => {
        const next = new Set(state.expandedPaths);
        if (next.has(path)) {
          next.delete(path);
        } else {
          next.add(path);
        }
        return { expandedPaths: next };
      }),

      setExpandedPaths: (paths) => set({ expandedPaths: paths }),

      openFile: (file) => set((state) => {
        const existing = state.openFiles.find((f) => f.path === file.path);
        if (existing) {
          return { activeFilePath: file.path };
        }
        return {
          openFiles: [...state.openFiles, file],
          activeFilePath: file.path,
        };
      }),

      closeFile: (path) => set((state) => {
        const filtered = state.openFiles.filter((f) => f.path !== path);
        let activeFilePath = state.activeFilePath;
        if (activeFilePath === path) {
          activeFilePath = filtered.length > 0 ? filtered[filtered.length - 1].path : null;
        }
        return { openFiles: filtered, activeFilePath };
      }),

      setActiveFile: (path) => set({ activeFilePath: path, activeFile: path }),

      setLinkedFile: (path) => set({ linkedFile: path }),

      updateFileContent: (path, content) => set((state) => ({
        openFiles: state.openFiles.map((f) =>
          f.path === path
            ? { ...f, content, isDirty: content !== f.originalContent }
            : f
        ),
      })),

      markFileSaved: (path) => set((state) => ({
        openFiles: state.openFiles.map((f) =>
          f.path === path
            ? { ...f, isDirty: false, originalContent: f.content }
            : f
        ),
      })),

      setRightPanelMode: (mode) => set({ rightPanelMode: mode }),
      setPanelSizes: (sizes) => set({ panelSizes: sizes }),
      setFileTreeCollapsed: (collapsed) => set({ isFileTreeCollapsed: collapsed }),
      setFileChatExpanded: (expanded) => set({ isFileChatExpanded: expanded }),
      setChatSidebarCollapsed: (collapsed) => set({ isChatSidebarCollapsed: collapsed }),
      setTerminalOpen: (open) => set({ isTerminalOpen: open }),
      setSplitEditor: (split, filePath = null) => set({ splitEditor: split, splitFilePath: filePath }),
      setDiffMode: (enabled, filePath = null) => set({ diffMode: enabled, diffFilePath: filePath }),
      setMobileActiveTab: (tab) => set({ mobileActiveTab: tab }),
      setAutoSave: (enabled) => set({ autoSave: enabled }),
      setShowHiddenFiles: (show) => set({ showHiddenFiles: show }),

      setDeployStatus: (status) => set((state) => ({
        deployStatus: { ...state.deployStatus, ...status },
      })),

      setGitStatus: (status) => set({ gitStatus: status }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      setSearchOpen: (open) => set({ isSearchOpen: open }),

      togglePinnedFile: (path) => set((state) => {
        const pinned = state.pinnedFiles.includes(path)
          ? state.pinnedFiles.filter((p) => p !== path)
          : [...state.pinnedFiles, path];
        return { pinnedFiles: pinned };
      }),

      addRecentFile: (path) => set((state) => {
        const recent = [path, ...state.recentFiles.filter((p) => p !== path)].slice(0, 5);
        return { recentFiles: recent };
      }),

      refreshFileInTree: (path, node) => set((state) => {
        // Simple tree update - re-fetch is preferred for complex cases
        return state;
      }),

      removeFileFromTree: (path) => set((state) => {
        // Simple removal - re-fetch is preferred
        return state;
      }),

      clearOpenFiles: () => set({
        openFiles: [],
        activeFilePath: null,
        activeFile: null,
      }),

      markBranchChanged: () => set((state) => ({
        // Increment counter to trigger effects that depend on branch changes
        branchChangeCounter: state.branchChangeCounter + 1,
        // Clear open files since they may have changed content
        openFiles: [],
        activeFilePath: null,
        activeFile: null,
      })),
    }),
    {
      name: 'workspace-store',
      partialize: (state) => ({
        activeProjectId: state.activeProjectId,
        panelSizes: state.panelSizes,
        rightPanelMode: state.rightPanelMode,
        isFileTreeCollapsed: state.isFileTreeCollapsed,
        isFileChatExpanded: state.isFileChatExpanded,
        isChatSidebarCollapsed: state.isChatSidebarCollapsed,
        autoSave: state.autoSave,
        pinnedFiles: state.pinnedFiles,
        recentFiles: state.recentFiles,
        showHiddenFiles: state.showHiddenFiles,
        expandedPaths: state.expandedPaths,
      }),
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name);
          if (!str) return null;
          const parsed = JSON.parse(str);
          // Convert expandedPaths array back to Set
          if (parsed?.state?.expandedPaths) {
            parsed.state.expandedPaths = new Set(parsed.state.expandedPaths);
          }
          return parsed;
        },
        setItem: (name, value) => {
          // Convert Set to array for serialization
          const toStore = {
            ...value,
            state: {
              ...value.state,
              expandedPaths: value.state?.expandedPaths
                ? Array.from(value.state.expandedPaths)
                : [],
            },
          };
          localStorage.setItem(name, JSON.stringify(toStore));
        },
        removeItem: (name) => localStorage.removeItem(name),
      },
    }
  )
);
