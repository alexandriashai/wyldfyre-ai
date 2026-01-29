"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { useToast } from "@/hooks/useToast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Github,
  Shield,
  CheckCircle,
  AlertTriangle,
  FileCode,
  TestTube,
  Loader2,
  Settings,
  Target,
} from "lucide-react";
import { GitHubProjectSettingsCard } from "@/components/workspace/github-project-settings";
import { ProjectTelosSettings } from "@/components/settings/project-telos-settings";
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

  // Quality settings
  const [qualityEnabled, setQualityEnabled] = useState(true);
  const [lintOnSave, setLintOnSave] = useState(true);
  const [lintOnCommit, setLintOnCommit] = useState(true);
  const [lintCommand, setLintCommand] = useState("");
  const [formatOnSave, setFormatOnSave] = useState(false);
  const [formatOnCommit, setFormatOnCommit] = useState(true);
  const [formatCommand, setFormatCommand] = useState("");
  const [typeCheckEnabled, setTypeCheckEnabled] = useState(true);
  const [typeCheckCommand, setTypeCheckCommand] = useState("");
  const [runTestsOnCommit, setRunTestsOnCommit] = useState(false);
  const [testCommand, setTestCommand] = useState("");
  const [autoFixLintErrors, setAutoFixLintErrors] = useState(true);
  const [blockOnErrors, setBlockOnErrors] = useState(false);

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

      // Quality settings
      const qs = p.quality_settings;
      if (qs) {
        setQualityEnabled(qs.enabled ?? true);
        setLintOnSave(qs.lint_on_save ?? true);
        setLintOnCommit(qs.lint_on_commit ?? true);
        setLintCommand(qs.lint_command || "");
        setFormatOnSave(qs.format_on_save ?? false);
        setFormatOnCommit(qs.format_on_commit ?? true);
        setFormatCommand(qs.format_command || "");
        setTypeCheckEnabled(qs.type_check_enabled ?? true);
        setTypeCheckCommand(qs.type_check_command || "");
        setRunTestsOnCommit(qs.run_tests_on_commit ?? false);
        setTestCommand(qs.test_command || "");
        setAutoFixLintErrors(qs.auto_fix_lint_errors ?? true);
        setBlockOnErrors(qs.block_on_errors ?? false);
      }
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
        quality_settings: {
          enabled: qualityEnabled,
          lint_on_save: lintOnSave,
          lint_on_commit: lintOnCommit,
          lint_command: lintCommand || null,
          format_on_save: formatOnSave,
          format_on_commit: formatOnCommit,
          format_command: formatCommand || null,
          type_check_enabled: typeCheckEnabled,
          type_check_command: typeCheckCommand || null,
          run_tests_on_commit: runTestsOnCommit,
          test_command: testCommand || null,
          auto_fix_lint_errors: autoFixLintErrors,
          block_on_errors: blockOnErrors,
          custom_checks: {},
        },
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

  if (!selectedProject) {
    return (
      <div className="flex flex-col h-full items-center justify-center p-6">
        <div className="text-center space-y-2">
          <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-medium">No Project Selected</h2>
          <p className="text-sm text-muted-foreground">
            Select a project from the sidebar to view its settings
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto overflow-y-auto h-full">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold">Project Settings</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Configure settings for {selectedProject.name}
        </p>
      </div>

      <Tabs defaultValue="general" className="space-y-6">
        <TabsList className="w-full sm:w-auto flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="general" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Settings className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">General</span>
          </TabsTrigger>
          <TabsTrigger value="docker" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Container className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Docker</span>
          </TabsTrigger>
          <TabsTrigger value="quality" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Shield className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Quality</span>
          </TabsTrigger>
          <TabsTrigger value="telos" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Target className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">TELOS</span>
          </TabsTrigger>
          <TabsTrigger value="github" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Github className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">GitHub</span>
          </TabsTrigger>
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Project Information</CardTitle>
              <CardDescription>Basic project details and paths</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Project Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Project"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="rootPath" className="flex items-center gap-2">
                  <FolderOpen className="h-4 w-4" />
                  Root Path
                </Label>
                <Input
                  id="rootPath"
                  value={rootPath}
                  onChange={(e) => setRootPath(e.target.value)}
                  className="font-mono"
                  placeholder="/home/projects/my-site"
                />
                <p className="text-xs text-muted-foreground">
                  The filesystem path where project files are stored
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="primaryUrl" className="flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Primary URL
                </Label>
                <Input
                  id="primaryUrl"
                  value={primaryUrl}
                  onChange={(e) => setPrimaryUrl(e.target.value)}
                  placeholder="https://mysite.com"
                />
              </div>

              {!dockerEnabled && (
                <div className="space-y-2">
                  <Label htmlFor="terminalUser" className="flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Terminal User
                  </Label>
                  <Input
                    id="terminalUser"
                    value={terminalUser}
                    onChange={(e) => setTerminalUser(e.target.value)}
                    className="font-mono"
                    placeholder="e.g., project-www"
                  />
                  <p className="text-xs text-muted-foreground">
                    System user for terminal sessions. Enable Docker for better isolation.
                  </p>
                </div>
              )}

              <Separator className="my-4" />

              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save Changes
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Docker Tab */}
        <TabsContent value="docker" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Docker Environment</CardTitle>
              <CardDescription>Isolated container environment for your project</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Enable Docker Isolation</Label>
                  <p className="text-sm text-muted-foreground">
                    Run your project in an isolated Docker container
                  </p>
                </div>
                <Switch checked={dockerEnabled} onCheckedChange={setDockerEnabled} />
              </div>
            </CardContent>
          </Card>

          {dockerEnabled && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Container Status</CardTitle>
                  <CardDescription>Manage your Docker container</CardDescription>
                </CardHeader>
                <CardContent>
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
                        Status: {containerStatus || "Not created"}
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
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Project Type</CardTitle>
                  <CardDescription>Select your project's technology stack</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    {PROJECT_TYPES.map((type) => (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => setDockerProjectType(type.value)}
                        className={cn(
                          "p-3 rounded-lg border text-left transition-colors",
                          dockerProjectType === type.value
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
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
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Runtime Configuration</CardTitle>
                  <CardDescription>Version and resource settings</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    {dockerProjectType === "node" && (
                      <div className="space-y-2">
                        <Label>Node.js Version</Label>
                        <Select value={dockerNodeVersion} onValueChange={setDockerNodeVersion}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {NODE_VERSIONS.map((v) => (
                              <SelectItem key={v} value={v}>Node {v}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {dockerProjectType === "php" && (
                      <div className="space-y-2">
                        <Label>PHP Version</Label>
                        <Select value={dockerPhpVersion} onValueChange={setDockerPhpVersion}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {PHP_VERSIONS.map((v) => (
                              <SelectItem key={v} value={v}>PHP {v}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {dockerProjectType === "python" && (
                      <div className="space-y-2">
                        <Label>Python Version</Label>
                        <Select value={dockerPythonVersion} onValueChange={setDockerPythonVersion}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {PYTHON_VERSIONS.map((v) => (
                              <SelectItem key={v} value={v}>Python {v}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    <div className="space-y-2">
                      <Label className="flex items-center gap-1">
                        <HardDrive className="h-3.5 w-3.5" />
                        Memory Limit
                      </Label>
                      <Select value={dockerMemoryLimit} onValueChange={setDockerMemoryLimit}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {MEMORY_OPTIONS.map((v) => (
                            <SelectItem key={v} value={v}>{v}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label className="flex items-center gap-1">
                        <Cpu className="h-3.5 w-3.5" />
                        CPU Cores
                      </Label>
                      <Select value={dockerCpuLimit} onValueChange={setDockerCpuLimit}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CPU_OPTIONS.map((v) => (
                            <SelectItem key={v} value={v}>{v} cores</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Separator />

                  <div className="space-y-2">
                    <Label>Exposed Ports</Label>
                    <Input
                      value={dockerExposePorts}
                      onChange={(e) => setDockerExposePorts(e.target.value)}
                      className="font-mono"
                      placeholder="3000, 8080, 5432"
                    />
                    <p className="text-xs text-muted-foreground">
                      Comma-separated list of ports to expose from the container
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Environment Variables</Label>
                    <textarea
                      value={dockerEnvVars}
                      onChange={(e) => setDockerEnvVars(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono h-24 resize-none"
                      placeholder="DATABASE_URL=postgres://...&#10;API_KEY=xxx"
                    />
                    <p className="text-xs text-muted-foreground">
                      One per line: KEY=value. These are injected into the container.
                    </p>
                  </div>

                  <Separator className="my-4" />

                  <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Save Changes
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Quality Tab */}
        <TabsContent value="quality" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Code Quality</CardTitle>
              <CardDescription>Configure linting, formatting, and testing</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Enable Code Quality Checks</Label>
                  <p className="text-sm text-muted-foreground">
                    Run automated checks on your code
                  </p>
                </div>
                <Switch checked={qualityEnabled} onCheckedChange={setQualityEnabled} />
              </div>
            </CardContent>
          </Card>

          {qualityEnabled && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    Linting
                  </CardTitle>
                  <CardDescription>Detect code issues and style problems</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="lintOnSave"
                        checked={lintOnSave}
                        onChange={(e) => setLintOnSave(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <Label htmlFor="lintOnSave">Lint on save</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="lintOnCommit"
                        checked={lintOnCommit}
                        onChange={(e) => setLintOnCommit(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <Label htmlFor="lintOnCommit">Lint on commit</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">
                      Custom lint command (leave empty for auto-detect)
                    </Label>
                    <Input
                      value={lintCommand}
                      onChange={(e) => setLintCommand(e.target.value)}
                      className="font-mono"
                      placeholder="e.g., npm run lint, ruff check ."
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileCode className="h-5 w-5 text-blue-500" />
                    Formatting
                  </CardTitle>
                  <CardDescription>Automatically format your code</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="formatOnSave"
                        checked={formatOnSave}
                        onChange={(e) => setFormatOnSave(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <Label htmlFor="formatOnSave">Format on save</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="formatOnCommit"
                        checked={formatOnCommit}
                        onChange={(e) => setFormatOnCommit(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <Label htmlFor="formatOnCommit">Format on commit</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">
                      Custom format command (leave empty for auto-detect)
                    </Label>
                    <Input
                      value={formatCommand}
                      onChange={(e) => setFormatCommand(e.target.value)}
                      className="font-mono"
                      placeholder="e.g., npm run format, black ."
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                    Type Checking
                  </CardTitle>
                  <CardDescription>Catch type errors before runtime</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="typeCheckEnabled"
                      checked={typeCheckEnabled}
                      onChange={(e) => setTypeCheckEnabled(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <Label htmlFor="typeCheckEnabled">Enable type checking</Label>
                  </div>

                  {typeCheckEnabled && (
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">
                        Custom type check command (leave empty for auto-detect)
                      </Label>
                      <Input
                        value={typeCheckCommand}
                        onChange={(e) => setTypeCheckCommand(e.target.value)}
                        className="font-mono"
                        placeholder="e.g., npx tsc --noEmit, mypy ."
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TestTube className="h-5 w-5 text-purple-500" />
                    Testing
                  </CardTitle>
                  <CardDescription>Run automated tests</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="runTestsOnCommit"
                      checked={runTestsOnCommit}
                      onChange={(e) => setRunTestsOnCommit(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <Label htmlFor="runTestsOnCommit">Run tests on commit</Label>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">
                      Custom test command (leave empty for auto-detect)
                    </Label>
                    <Input
                      value={testCommand}
                      onChange={(e) => setTestCommand(e.target.value)}
                      className="font-mono"
                      placeholder="e.g., npm test, pytest"
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Agent Behavior</CardTitle>
                  <CardDescription>How agents handle code quality issues</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Auto-fix Lint Errors</Label>
                      <p className="text-sm text-muted-foreground">
                        Automatically fix lint errors after tasks
                      </p>
                    </div>
                    <Switch checked={autoFixLintErrors} onCheckedChange={setAutoFixLintErrors} />
                  </div>

                  <Separator />

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Block on Errors</Label>
                      <p className="text-sm text-muted-foreground">
                        Block commits if quality errors exist
                      </p>
                    </div>
                    <Switch checked={blockOnErrors} onCheckedChange={setBlockOnErrors} />
                  </div>

                  <Separator className="my-4" />

                  <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Save Changes
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* TELOS Tab */}
        <TabsContent value="telos" className="space-y-6">
          <ProjectTelosSettings />
        </TabsContent>

        {/* GitHub Tab */}
        <TabsContent value="github" className="space-y-6">
          <GitHubProjectSettingsCard
            projectId={selectedProject.id}
            projectName={selectedProject.name}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
