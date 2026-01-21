import { create } from "zustand";
import { persist } from "zustand/middleware";
import { projectsApi, Project, ProjectWithStats } from "@/lib/api";

interface ProjectState {
  projects: Project[];
  selectedProject: Project | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProjects: (token: string) => Promise<void>;
  selectProject: (project: Project | null) => void;
  createProject: (token: string, data: { name: string; description?: string; color?: string; icon?: string }) => Promise<Project>;
  updateProject: (token: string, id: string, data: { name?: string; description?: string; status?: string; color?: string; icon?: string }) => Promise<void>;
  deleteProject: (token: string, id: string, archive?: boolean) => Promise<void>;
  getProjectById: (id: string) => Project | undefined;
  clearSelection: () => void;
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      projects: [],
      selectedProject: null,
      isLoading: false,
      error: null,

      fetchProjects: async (token: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await projectsApi.list(token, { status: "ACTIVE" });
          set({ projects: response.projects });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to fetch projects";
          set({ error: message });
        } finally {
          set({ isLoading: false });
        }
      },

      selectProject: (project: Project | null) => {
        set({ selectedProject: project });
      },

      createProject: async (token: string, data) => {
        set({ isLoading: true, error: null });
        try {
          const project = await projectsApi.create(token, data);
          set((state) => ({
            projects: [project, ...state.projects],
          }));
          return project;
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to create project";
          set({ error: message });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      updateProject: async (token: string, id: string, data) => {
        set({ isLoading: true, error: null });
        try {
          const updatedProject = await projectsApi.update(token, id, data);
          set((state) => ({
            projects: state.projects.map((p) =>
              p.id === id ? updatedProject : p
            ),
            selectedProject:
              state.selectedProject?.id === id
                ? updatedProject
                : state.selectedProject,
          }));
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to update project";
          set({ error: message });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      deleteProject: async (token: string, id: string, archive = true) => {
        try {
          await projectsApi.delete(token, id, archive);
          set((state) => ({
            projects: state.projects.filter((p) => p.id !== id),
            selectedProject:
              state.selectedProject?.id === id ? null : state.selectedProject,
          }));
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to delete project";
          set({ error: message });
          throw err;
        }
      },

      getProjectById: (id: string) => {
        return get().projects.find((p) => p.id === id);
      },

      clearSelection: () => {
        set({ selectedProject: null });
      },
    }),
    {
      name: "project-store",
      partialize: (state) => ({
        selectedProject: state.selectedProject,
      }),
    }
  )
);
