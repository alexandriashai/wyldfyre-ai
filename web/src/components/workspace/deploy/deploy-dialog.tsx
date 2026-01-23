"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { workspaceApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Upload, CheckCircle2, XCircle, Loader2 } from "lucide-react";

interface DeployDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeployDialog({ open, onOpenChange }: DeployDialogProps) {
  const { token } = useAuthStore();
  const { activeProjectId, gitStatus, setGitStatus, setDeployStatus } = useWorkspaceStore();
  const [message, setMessage] = useState("");
  const [isDeploying, setIsDeploying] = useState(false);
  const [result, setResult] = useState<{ status: string; message: string } | null>(null);

  const modifiedCount = gitStatus
    ? gitStatus.modified.length + gitStatus.untracked.length
    : 0;

  const handleDeploy = async () => {
    if (!token || !activeProjectId) return;

    setIsDeploying(true);
    setResult(null);
    setDeployStatus({ isDeploying: true, stage: "Deploying...", progress: 50, error: null });

    try {
      const res = await workspaceApi.deploy(
        token,
        activeProjectId,
        message || undefined
      );

      setResult({ status: res.status, message: res.message || "Deploy complete" });

      if (res.status === "completed") {
        setDeployStatus({ isDeploying: false, stage: null, progress: 100, error: null });
        // Refresh git status
        const status = await workspaceApi.getGitStatus(token, activeProjectId);
        setGitStatus(status);
      } else {
        setDeployStatus({ isDeploying: false, stage: null, progress: 0, error: res.message });
      }
    } catch (err: any) {
      setResult({ status: "failed", message: err.message || "Deploy failed" });
      setDeployStatus({ isDeploying: false, stage: null, progress: 0, error: err.message });
    } finally {
      setIsDeploying(false);
    }
  };

  const handleClose = () => {
    if (!isDeploying) {
      setResult(null);
      setMessage("");
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Deploy Project
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Status summary */}
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              {modifiedCount > 0
                ? `${modifiedCount} file${modifiedCount > 1 ? "s" : ""} will be committed and deployed.`
                : "No uncommitted changes. Deploy will sync current state."}
            </p>
            {gitStatus?.branch && (
              <p className="text-xs text-muted-foreground">
                Branch: {gitStatus.branch}
              </p>
            )}
          </div>

          {/* Commit message */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">
              Commit message (optional)
            </label>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={`Deploy: ${new Date().toLocaleString()}`}
              className="w-full mt-1 text-sm bg-background border rounded-md px-3 py-2 outline-none focus:ring-1 focus:ring-primary"
              disabled={isDeploying}
            />
          </div>

          {/* Result */}
          {result && (
            <div className={`flex items-center gap-2 p-3 rounded-md text-sm ${
              result.status === "completed"
                ? "bg-green-500/10 text-green-600"
                : "bg-red-500/10 text-red-600"
            }`}>
              {result.status === "completed" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0" />
              )}
              <span>{result.message}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isDeploying}>
            {result ? "Close" : "Cancel"}
          </Button>
          {!result && (
            <Button onClick={handleDeploy} disabled={isDeploying}>
              {isDeploying ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deploying...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Deploy
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
