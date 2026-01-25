"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { FolderOpen } from "lucide-react";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token } = useAuthStore();
  const { fetchProjects, projects, selectedProject } = useProjectStore();

  useEffect(() => {
    if (token && projects.length === 0) {
      fetchProjects(token);
    }
  }, [token, projects.length, fetchProjects]);

  if (!selectedProject) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-4 max-w-md px-4">
          <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground" />
          <h2 className="text-xl font-semibold">Select a project to get started</h2>
          <p className="text-muted-foreground">
            Choose a project from the sidebar to access files, chats, and settings.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
