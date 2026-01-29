"use client";

import { useState, useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectStore } from "@/stores/project-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface TelosFile {
  filename: string;
  exists: boolean;
  is_static: boolean;
  last_modified: string | null;
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
  "MISSION.md": "Project's core purpose and goals",
  "BELIEFS.md": "Project values and principles",
  "NARRATIVES.md": "Context and background for AI",
  "MODELS.md": "Mental frameworks for reasoning",
};

export function ProjectTelosSettings() {
  const { token } = useAuthStore();
  const { selectedProject } = useProjectStore();
  const [files, setFiles] = useState<TelosFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("MISSION.md");
  const [fileContent, setFileContent] = useState<string>("");
  const [originalContent, setOriginalContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Wizard state
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardMessages, setWizardMessages] = useState<WizardMessage[]>([]);
  const [wizardInput, setWizardInput] = useState("");
  const [wizardLoading, setWizardLoading] = useState(false);
  const [wizardSuggestedContent, setWizardSuggestedContent] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const projectId = selectedProject?.id;
  const projectName = selectedProject?.name;

  // Fetch files list
  useEffect(() => {
    if (!token || !projectId) return;

    const fetchFiles = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/telos/files?project_id=${projectId}`, {
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
  }, [token, projectId]);

  // Fetch file content when selected file changes
  useEffect(() => {
    if (!token || !selectedFile || !projectId) return;

    const fetchContent = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/telos/file/${selectedFile}?project_id=${projectId}`, {
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
  }, [token, selectedFile, projectId]);

  // Scroll wizard messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [wizardMessages]);

  const handleSave = async () => {
    if (!token || !projectId) return;
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
          project_id: projectId,
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
    setWizardMessages([
      {
        role: "assistant",
        content: `Let's define the ${selectedFile.replace(".md", "").toLowerCase()} for **${projectName}**.\n\nThis will give the AI specific context about this project to guide its work.\n\nReady to begin?`,
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
      const res = await fetch(`${API_BASE}/api/telos/wizard/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: [...wizardMessages, { role: "user", content: userMessage }],
          target_file: selectedFile.replace(".md", ""),
          project_id: projectId,
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

  if (!selectedProject) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          Project TELOS
        </CardTitle>
        <CardDescription>
          Define project-specific mission, beliefs, and context for the AI
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* File Selector */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {staticFiles.map((file) => (
            <button
              key={file.filename}
              onClick={() => setSelectedFile(file.filename)}
              className={cn(
                "flex flex-col items-center gap-1.5 p-2 rounded-lg border transition-all hover:bg-muted",
                selectedFile === file.filename && "border-primary bg-primary/5 ring-1 ring-primary"
              )}
            >
              {FILE_ICONS[file.filename] || <FileText className="h-4 w-4" />}
              <span className="text-xs font-medium">{file.filename.replace(".md", "")}</span>
              {file.exists ? (
                <Badge variant="outline" className="text-[9px] px-1 py-0 text-green-500 border-green-500/30">
                  Set
                </Badge>
              ) : (
                <Badge variant="outline" className="text-[9px] px-1 py-0 text-muted-foreground">
                  Empty
                </Badge>
              )}
            </button>
          ))}
        </div>

        {message && (
          <div
            className={cn(
              "flex items-center gap-2 rounded-md p-2 text-sm",
              message.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
            )}
          >
            {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {message.text}
          </div>
        )}

        <div className="space-y-2">
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
              <Wand2 className="h-4 w-4 mr-1" />
              Wizard
            </Button>
          </div>

          <Textarea
            value={fileContent}
            onChange={(e) => setFileContent(e.target.value)}
            placeholder={`# ${selectedFile.replace(".md", "")}\n\nDefine this project's ${selectedFile.replace(".md", "").toLowerCase()} here...`}
            className="min-h-[200px] font-mono text-sm"
            disabled={isLoading}
            maxLength={20000}
          />

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {hasChanges ? "Unsaved changes" : "No changes"}
            </p>
            <Button size="sm" onClick={handleSave} disabled={isSaving || !hasChanges}>
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-1" />
                  Save
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>

      {/* Wizard Dialog */}
      <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-primary" />
              TELOS Wizard - {selectedFile.replace(".md", "")}
            </DialogTitle>
            <DialogDescription>
              Setting up project-specific context for {projectName}
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
    </Card>
  );
}
