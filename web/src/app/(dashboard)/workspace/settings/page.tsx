"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useToast } from "@/hooks/useToast";
import { Button } from "@/components/ui/button";
import {
  Save,
  FolderOpen,
  Globe,
  Terminal,
  Container,
  Play,
  Square,
  RefreshCw,
  Cpu,
  HardDrive,
} from "lucide-react";
import { cn } from "@/lib/utils";

const PROJECT_TYPES = [
  { value: "node", label: "Node.js", description: "Next.js, React, Vue, etc." },
  { value: "php", label: "PHP", description: "Laravel, WordPress, etc." },
  { value: "python", label: "Python", description: "Django, Flask, FastAPI, etc." },
  { value: "custom", label: "Custom", description: "Basic container with common tools" },
];

const NODE_VERSIONS = ["22", "20", "18", "16"];
const PHP_VERSIONS = ["8.3", "8.2", "8.1", "8.0", "7.4"];
const PYTHON_VERSIONS = ["3.12", "3.11", "3.10", "3.9"];
const MEMORY_OPTIONS = ["512m", "1g", "2g", "4g", "8g"];
const CPU_OPTIONS = ["0.5", "1.0", "2.0", "4.0"];

export default function WorkspaceSettingsPage() {
  const { token } = useAuthStore();
  const { selectedProject, updateProject } = useProjectStore();
  const { toast } = useToast();

  // Basic settings
  const [name, setName] = useState("");
  const [rootPath, setRootPath] = useState("");
  const [primaryUrl, setPrimaryUrl] = useState("");
  const [terminalUser, setTerminalUser] = useState("");

  // Docker settings
  const [dockerEnabled, setDockerEnabled] = useState(false);
  const [dockerProjectType, setDockerProjectType] = useState("node");
  const [dockerNodeVersion, setDockerNodeVersion] = useState("20");
  const [dockerPhpVersion, setDockerPhpVersion] = useState("8.3");
  const [dockerPythonVersion, setDockerPythonVersion] = useState("3.12");
  const [dockerMemoryLimit, setDockerMemoryLimit] = useState("2g");
  const [dockerCpuLimit, setDockerCpuLimit] = useState("2.0");
  const [dockerExposePorts, setDockerExposePorts] = useState("");
  const [dockerEnvVars, setDockerEnvVars] = useState("");
  const [containerStatus, setContainerStatus] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [isContainerAction, setIsContainerAction] = useState(false);

  useEffect(() => {
    if (selectedProject) {
      const p = selectedProject as any;
      setName(p.name || "");
      setRootPath(p.root_path || "");
      setPrimaryUrl(p.primary_url || "");
      setTerminalUser(p.terminal_user || "");

      // Docker settings
      setDockerEnabled(p.docker_enabled || false);
      setDockerProjectType(p.docker_project_type || "node");
      setDockerNodeVersion(p.docker_node_version || "20");
      setDockerPhpVersion(p.docker_php_version || "8.3");
      setDockerPythonVersion(p.docker_python_version || "3.12");
      setDockerMemoryLimit(p.docker_memory_limit || "2g");
      setDockerCpuLimit(p.docker_cpu_limit || "2.0");
      setDockerExposePorts(p.docker_expose_ports || "");
      setDockerEnvVars(p.docker_env_vars || "");
      setContainerStatus(p.docker_container_status || null);
    }
  }, [selectedProject]);

  const handleSave = async () => {
    if (!token || !selectedProject) {
      toast({
        title: "Error",
        description: "No project selected",
        variant: "destructive",
      });
      return;
    }
    setIsSaving(true);
    try {
      await updateProject(token, selectedProject.id, {
        name,
        root_path: rootPath,
        primary_url: primaryUrl,
        terminal_user: dockerEnabled ? undefined : terminalUser,
        docker_enabled: dockerEnabled,
        docker_project_type: dockerProjectType,
        docker_node_version: dockerNodeVersion,
        docker_php_version: dockerPhpVersion,
        docker_python_version: dockerPythonVersion,
        docker_memory_limit: dockerMemoryLimit,
        docker_cpu_limit: dockerCpuLimit,
        docker_expose_ports: dockerExposePorts || undefined,
        docker_env_vars: dockerEnvVars || undefined,
      });
      toast({
        title: "Settings saved",
        description: "Project settings have been updated successfully.",
      });
    } catch (error) {
      console.error("Failed to update project:", error);
      toast({
        title: "Save failed",
        description: error instanceof Error ? error.message : "Failed to save project settings",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleContainerAction = async (action: "start" | "stop" | "rebuild") => {
    if (!token || !selectedProject) return;
    setIsContainerAction(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/projects/${selectedProject.id}/container/${action}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (response.ok) {
        const data = await response.json();
        setContainerStatus(data.status || (action === "stop" ? "stopped" : "running"));
      }
    } catch (error) {
      console.error(`Container ${action} failed:`, error);
    } finally {
      setIsContainerAction(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-6 overflow-y-auto">
      <h1 className="text-2xl font-semibold mb-6">Project Settings</h1>

      <div className="space-y-8 max-w-2xl">
        {/* Basic Settings */}
        <section className="space-y-4">
          <h2 className="text-lg font-medium border-b pb-2">General</h2>

          <div className="space-y-2">
            <label className="text-sm font-medium">Project Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-md border bg-background text-sm"
              placeholder="My Project"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <FolderOpen className="h-4 w-4" />
              Root Path
            </label>
            <input
              type="text"
              value={rootPath}
              onChange={(e) => setRootPath(e.target.value)}
              className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono"
              placeholder="/home/projects/my-site"
            />
            <p className="text-xs text-muted-foreground">
              The filesystem path where project files are stored.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Primary URL
            </label>
            <input
              type="text"
              value={primaryUrl}
              onChange={(e) => setPrimaryUrl(e.target.value)}
              className="w-full px-3 py-2 rounded-md border bg-background text-sm"
              placeholder="https://mysite.com"
            />
          </div>
        </section>

        {/* Docker Settings */}
        <section className="space-y-4">
          <h2 className="text-lg font-medium border-b pb-2 flex items-center gap-2">
            <Container className="h-5 w-5" />
            Docker Environment
          </h2>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setDockerEnabled(!dockerEnabled)}
              className={cn(
                "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                dockerEnabled ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                  dockerEnabled ? "translate-x-6" : "translate-x-1"
                )}
              />
            </button>
            <span className="text-sm font-medium">
              Enable Docker isolation
            </span>
          </div>

          {dockerEnabled && (
            <div className="space-y-4 pl-4 border-l-2 border-primary/20">
              {/* Container Status */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "h-2.5 w-2.5 rounded-full",
                      containerStatus === "running"
                        ? "bg-green-500"
                        : containerStatus === "stopped"
                        ? "bg-yellow-500"
                        : "bg-gray-400"
                    )}
                  />
                  <span className="text-sm">
                    Container: {containerStatus || "Not created"}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleContainerAction("start")}
                    disabled={isContainerAction || containerStatus === "running"}
                  >
                    <Play className="h-3.5 w-3.5 mr-1" />
                    Start
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleContainerAction("stop")}
                    disabled={isContainerAction || containerStatus !== "running"}
                  >
                    <Square className="h-3.5 w-3.5 mr-1" />
                    Stop
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleContainerAction("rebuild")}
                    disabled={isContainerAction}
                  >
                    <RefreshCw className="h-3.5 w-3.5 mr-1" />
                    Rebuild
                  </Button>
                </div>
              </div>

              {/* Project Type */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Project Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {PROJECT_TYPES.map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      onClick={() => setDockerProjectType(type.value)}
                      className={cn(
                        "p-3 rounded-lg border text-left transition-colors",
                        dockerProjectType === type.value
                          ? "border-primary bg-primary/5"
                          : "border-muted hover:border-primary/50"
                      )}
                    >
                      <div className="font-medium text-sm">{type.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {type.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Version Selection */}
              <div className="grid grid-cols-3 gap-4">
                {dockerProjectType === "node" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Node.js Version</label>
                    <select
                      value={dockerNodeVersion}
                      onChange={(e) => setDockerNodeVersion(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border bg-background text-sm"
                    >
                      {NODE_VERSIONS.map((v) => (
                        <option key={v} value={v}>
                          Node {v}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {dockerProjectType === "php" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">PHP Version</label>
                    <select
                      value={dockerPhpVersion}
                      onChange={(e) => setDockerPhpVersion(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border bg-background text-sm"
                    >
                      {PHP_VERSIONS.map((v) => (
                        <option key={v} value={v}>
                          PHP {v}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {dockerProjectType === "python" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Python Version</label>
                    <select
                      value={dockerPythonVersion}
                      onChange={(e) => setDockerPythonVersion(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border bg-background text-sm"
                    >
                      {PYTHON_VERSIONS.map((v) => (
                        <option key={v} value={v}>
                          Python {v}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    <HardDrive className="h-3.5 w-3.5" />
                    Memory
                  </label>
                  <select
                    value={dockerMemoryLimit}
                    onChange={(e) => setDockerMemoryLimit(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border bg-background text-sm"
                  >
                    {MEMORY_OPTIONS.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    <Cpu className="h-3.5 w-3.5" />
                    CPU Cores
                  </label>
                  <select
                    value={dockerCpuLimit}
                    onChange={(e) => setDockerCpuLimit(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border bg-background text-sm"
                  >
                    {CPU_OPTIONS.map((v) => (
                      <option key={v} value={v}>
                        {v} cores
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Exposed Ports */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Exposed Ports</label>
                <input
                  type="text"
                  value={dockerExposePorts}
                  onChange={(e) => setDockerExposePorts(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono"
                  placeholder="3000, 8080, 5432"
                />
                <p className="text-xs text-muted-foreground">
                  Comma-separated list of ports to expose from the container.
                </p>
              </div>

              {/* Environment Variables */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Environment Variables</label>
                <textarea
                  value={dockerEnvVars}
                  onChange={(e) => setDockerEnvVars(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono h-24"
                  placeholder="DATABASE_URL=postgres://...&#10;API_KEY=xxx"
                />
                <p className="text-xs text-muted-foreground">
                  One per line: KEY=value. These are injected into the container.
                </p>
              </div>
            </div>
          )}

          {!dockerEnabled && (
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Terminal className="h-4 w-4" />
                Terminal User (Legacy)
              </label>
              <input
                type="text"
                value={terminalUser}
                onChange={(e) => setTerminalUser(e.target.value)}
                className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono"
                placeholder="e.g., project-www"
              />
              <p className="text-xs text-muted-foreground">
                System user for terminal sessions. Enable Docker for better isolation.
              </p>
            </div>
          )}
        </section>

        <Button type="button" onClick={handleSave} disabled={isSaving} className="gap-2">
          <Save className="h-4 w-4" />
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
