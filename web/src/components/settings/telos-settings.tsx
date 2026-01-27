"use client";

import { useState, useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Loader2,
  CheckCircle,
  AlertCircle,
  Wand2,
  Save,
  FileText,
  Target,
  Heart,
  BookOpen,
  Brain,
  Sparkles,
  Send,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface TelosFile {
  filename: string;
  exists: boolean;
  is_static: boolean;
  last_modified: string | null;
}

interface Project {
  id: string;
  name: string;
}

interface WizardMessage {
  role: "user" | "assistant";
  content: string;
}

const FILE_ICONS: Record<string, React.ReactNode> = {
  "MISSION.md": <Target className="h-4 w-4" />,
  "BELIEFS.md": <Heart className="h-4 w-4" />,
  "NARRATIVES.md": <BookOpen className="h-4 w-4" />,
  "MODELS.md": <Brain className="h-4 w-4" />,
};

const FILE_DESCRIPTIONS: Record<string, string> = {
  "MISSION.md": "Your core purpose and vision",
  "BELIEFS.md": "Values and guiding principles",
  "NARRATIVES.md": "Story and context for the AI",
  "MODELS.md": "Mental frameworks for reasoning",
};

export function TelosSettings() {
  const { token } = useAuthStore();
  const [files, setFiles] = useState<TelosFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("MISSION.md");
  const [fileContent, setFileContent] = useState<string>("");
  const [originalContent, setOriginalContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Project selection
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [scope, setScope] = useState<"system" | "project">("system");

  // Wizard state
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardMessages, setWizardMessages] = useState<WizardMessage[]>([]);
  const [wizardInput, setWizardInput] = useState("");
  const [wizardLoading, setWizardLoading] = useState(false);
  const [wizardSuggestedContent, setWizardSuggestedContent] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch files list
  useEffect(() => {
    if (!token) return;

    const fetchFiles = async () => {
      setIsLoading(true);
      try {
        const projectParam = scope === "project" && selectedProject ? `?project_id=${selectedProject}` : "";
        const res = await fetch(`${API_BASE}/api/telos/files${projectParam}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setFiles(data.files || []);
        }
      } catch (error) {
        console.error("Failed to fetch TELOS files:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchFiles();
  }, [token, scope, selectedProject]);

  // Fetch projects list
  useEffect(() => {
    if (!token) return;

    const fetchProjects = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/projects`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setProjects(data.projects || []);
        }
      } catch (error) {
        console.error("Failed to fetch projects:", error);
      }
    };

    fetchProjects();
  }, [token]);

  // Fetch file content when selected file changes
  useEffect(() => {
    if (!token || !selectedFile) return;

    const fetchContent = async () => {
      setIsLoading(true);
      try {
        const projectParam = scope === "project" && selectedProject ? `?project_id=${selectedProject}` : "";
        const res = await fetch(`${API_BASE}/api/telos/file/${selectedFile}${projectParam}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setFileContent(data.content || "");
          setOriginalContent(data.content || "");
        }
      } catch (error) {
        console.error("Failed to fetch file content:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchContent();
  }, [token, selectedFile, scope, selectedProject]);

  // Scroll wizard messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [wizardMessages]);

  const handleSave = async () => {
    if (!token) return;
    setIsSaving(true);
    setMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/telos/file/${selectedFile}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content: fileContent,
          project_id: scope === "project" ? selectedProject : null,
        }),
      });

      if (res.ok) {
        setOriginalContent(fileContent);
        setMessage({ type: "success", text: `${selectedFile} saved successfully` });
      } else {
        const error = await res.json();
        setMessage({ type: "error", text: error.detail || "Failed to save" });
      }
    } catch (error) {
      setMessage({ type: "error", text: "Failed to save file" });
    } finally {
      setIsSaving(false);
    }
  };

  const startWizard = () => {
    const projectName = selectedProject
      ? projects.find((p) => p.id === selectedProject)?.name
      : null;

    setWizardMessages([
      {
        role: "assistant",
        content: scope === "system"
          ? `Let's define your ${selectedFile.replace(".md", "").toLowerCase()}. I'll ask you some questions to help articulate what matters most.\n\nTake your time with each answer - this is foundational thinking that will guide how your AI understands your organization.\n\nReady to begin?`
          : `Let's define the ${selectedFile.replace(".md", "").toLowerCase()} for **${projectName || "this project"}**.\n\nThis will complement your system-level TELOS with project-specific context.\n\nReady to begin?`,
      },
    ]);
    setWizardInput("");
    setWizardSuggestedContent(null);
    setWizardOpen(true);
  };

  const sendWizardMessage = async () => {
    if (!token || !wizardInput.trim() || wizardLoading) return;

    const userMessage = wizardInput.trim();
    setWizardInput("");
    setWizardMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setWizardLoading(true);

    try {
      const projectName = selectedProject
        ? projects.find((p) => p.id === selectedProject)?.name
        : null;

      const res = await fetch(`${API_BASE}/api/telos/wizard/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: [...wizardMessages, { role: "user", content: userMessage }],
          target_file: selectedFile.replace(".md", ""),
          project_id: scope === "project" ? selectedProject : null,
          project_name: projectName,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setWizardMessages((prev) => [...prev, { role: "assistant", content: data.message }]);

        if (data.suggested_content) {
          setWizardSuggestedContent(data.suggested_content);
        }
      } else {
        setWizardMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, I encountered an error. Please try again." },
        ]);
      }
    } catch (error) {
      setWizardMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Connection error. Please try again." },
      ]);
    } finally {
      setWizardLoading(false);
    }
  };

  const applyWizardContent = () => {
    if (wizardSuggestedContent) {
      setFileContent(wizardSuggestedContent);
      setWizardOpen(false);
      setMessage({ type: "success", text: "Content applied. Review and save when ready." });
    }
  };

  const hasChanges = fileContent !== originalContent;
  const staticFiles = files.filter((f) => f.is_static);
  const dynamicFiles = files.filter((f) => !f.is_static);

  return (
    <div className="space-y-6">
      {/* Scope Selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">TELOS Scope</CardTitle>
          <CardDescription>
            Configure system-wide or project-specific goals and context
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <Tabs value={scope} onValueChange={(v) => setScope(v as "system" | "project")}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="system">
                    <Target className="h-4 w-4 mr-2" />
                    System
                  </TabsTrigger>
                  <TabsTrigger value="project">
                    <FolderOpen className="h-4 w-4 mr-2" />
                    Project
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {scope === "project" && (
              <Select value={selectedProject || ""} onValueChange={setSelectedProject}>
                <SelectTrigger className="w-full sm:w-[200px]">
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Static Files (Wizard-editable) */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Core TELOS Files
          </CardTitle>
          <CardDescription>
            Define your mission, beliefs, and context. Use the wizard for guided setup.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            {staticFiles.map((file) => (
              <button
                key={file.filename}
                onClick={() => setSelectedFile(file.filename)}
                className={cn(
                  "flex flex-col items-center gap-2 p-3 rounded-lg border transition-all hover:bg-muted",
                  selectedFile === file.filename && "border-primary bg-primary/5 ring-1 ring-primary"
                )}
              >
                {FILE_ICONS[file.filename] || <FileText className="h-4 w-4" />}
                <span className="text-xs font-medium">{file.filename.replace(".md", "")}</span>
                {file.exists ? (
                  <Badge variant="outline" className="text-[10px] text-green-500 border-green-500/30">
                    Configured
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px] text-muted-foreground">
                    Not set
                  </Badge>
                )}
              </button>
            ))}
          </div>

          {message && (
            <div
              className={cn(
                "flex items-center gap-2 rounded-md p-3 text-sm mb-4",
                message.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
              )}
            >
              {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              {message.text}
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium flex items-center gap-2">
                  {FILE_ICONS[selectedFile] || <FileText className="h-4 w-4" />}
                  {selectedFile}
                </h4>
                <p className="text-xs text-muted-foreground">
                  {FILE_DESCRIPTIONS[selectedFile] || "TELOS configuration file"}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={startWizard}>
                <Wand2 className="h-4 w-4 mr-2" />
                Setup Wizard
              </Button>
            </div>

            <Textarea
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              placeholder={`# ${selectedFile.replace(".md", "")}\n\nDefine your ${selectedFile.replace(".md", "").toLowerCase()} here...`}
              className="min-h-[300px] font-mono text-sm"
              disabled={isLoading}
              maxLength={20000}
            />
            <p className="text-xs text-muted-foreground text-right">
              {fileContent.length.toLocaleString()} / 20,000 characters
            </p>

            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                {hasChanges ? "You have unsaved changes" : "No changes"}
              </p>
              <Button onClick={handleSave} disabled={isSaving || !hasChanges}>
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dynamic Files (Read-only) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dynamic TELOS Files</CardTitle>
          <CardDescription>
            Auto-populated by the system based on your activity
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {dynamicFiles.map((file) => (
              <div
                key={file.filename}
                className="flex items-center gap-2 p-2 rounded-md border bg-muted/50"
              >
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs">{file.filename.replace(".md", "")}</span>
                <Badge variant="secondary" className="text-[10px] ml-auto">
                  Auto
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Wizard Dialog */}
      <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-primary" />
              TELOS Setup Wizard - {selectedFile.replace(".md", "")}
            </DialogTitle>
            <DialogDescription>
              {scope === "system"
                ? "I'll help you articulate your organization's core context"
                : `Setting up project-specific context for ${projects.find((p) => p.id === selectedProject)?.name || "this project"}`}
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="flex-1 min-h-[300px] pr-4">
            <div className="space-y-4">
              {wizardMessages.map((msg, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex",
                    msg.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] rounded-lg px-4 py-2 text-sm",
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    )}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {wizardLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg px-4 py-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {wizardSuggestedContent && (
            <div className="border rounded-lg p-3 bg-green-500/10 border-green-500/30">
              <p className="text-sm font-medium text-green-600 mb-2">Content Ready</p>
              <p className="text-xs text-muted-foreground mb-2">
                The wizard has generated content for {selectedFile}. Click apply to use it.
              </p>
              <Button size="sm" onClick={applyWizardContent}>
                <CheckCircle className="h-4 w-4 mr-2" />
                Apply to Editor
              </Button>
            </div>
          )}

          <DialogFooter className="flex-row gap-2">
            <div className="flex-1">
              <div className="flex gap-2">
                <Textarea
                  value={wizardInput}
                  onChange={(e) => setWizardInput(e.target.value)}
                  placeholder="Type your response..."
                  className="min-h-[60px] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendWizardMessage();
                    }
                  }}
                />
                <Button
                  onClick={sendWizardMessage}
                  disabled={wizardLoading || !wizardInput.trim()}
                  className="self-end"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
