"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { TerminalPanel } from "@/components/workspace/panels/terminal-panel";

export default function WorkspaceTerminalPage() {
  const { token } = useAuthStore();
  const { selectedProject } = useProjectStore();
  const { setActiveProject } = useWorkspaceStore();

  // Ensure active project is set
  useEffect(() => {
    if (selectedProject) {
      setActiveProject(selectedProject.id);
    }
  }, [selectedProject, setActiveProject]);

  if (!selectedProject) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Select a project to use the terminal</p>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full md:h-[calc(100dvh-3.5rem)]"
      style={{
        // Use dvh on mobile for proper orientation handling
        height: '100%',
        minHeight: 0,
      }}
    >
      <TerminalPanel alwaysShow />
    </div>
  );
}
