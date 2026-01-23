"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { WorkspaceLayout } from "@/components/workspace/workspace-layout";

export default function WorkspacePage() {
  const { token } = useAuthStore();
  const { fetchProjects, projects } = useProjectStore();

  // Ensure projects are loaded
  useEffect(() => {
    if (token && projects.length === 0) {
      fetchProjects(token);
    }
  }, [token, projects.length, fetchProjects]);

  return <WorkspaceLayout />;
}
