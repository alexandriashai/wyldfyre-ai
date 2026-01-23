"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Globe,
  Lock,
  Upload,
  Trash2,
  ExternalLink,
  FolderKanban,
  Pencil,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Skull,
  CheckSquare,
  Square,
  Loader2,
} from "lucide-react";
import { Domain } from "@/lib/api";

interface DeployProgress {
  domain: string;
  stage: "building" | "deploying" | "verifying" | "complete" | "failed";
  progress: number;
  message?: string;
}

interface DomainTableProps {
  domains: Domain[];
  onDeploy?: (name: string) => void;
  onDelete?: (name: string) => void;
  onEdit?: (domain: Domain) => void;
  selectedDomains?: Set<string>;
  onToggleSelect?: (name: string) => void;
  isSelectMode?: boolean;
}

const statusColors: Record<string, string> = {
  active: "bg-green-500/10 text-green-500",
  pending: "bg-yellow-500/10 text-yellow-500",
  suspended: "bg-red-500/10 text-red-500",
  deleted: "bg-gray-500/10 text-gray-500",
};

const DEPLOY_STAGES: Record<string, { label: string; progress: number }> = {
  building: { label: "Building", progress: 25 },
  deploying: { label: "Deploying", progress: 50 },
  verifying: { label: "Verifying", progress: 75 },
  complete: { label: "Complete", progress: 100 },
  failed: { label: "Failed", progress: 0 },
};

function getSSLDaysRemaining(expiresAt: string | null): number | null {
  if (!expiresAt) return null;
  const expires = new Date(expiresAt);
  const now = new Date();
  return Math.ceil((expires.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function SSLBadge({ domain }: { domain: Domain }) {
  if (!domain.ssl_enabled) {
    return (
      <Badge variant="outline" className="text-muted-foreground gap-1">
        <Lock className="h-3 w-3" />
        Inactive
      </Badge>
    );
  }

  const daysRemaining = getSSLDaysRemaining(domain.ssl_expires_at);

  if (daysRemaining === null) {
    return (
      <Badge variant="outline" className="text-green-500 border-green-500/50 gap-1">
        <ShieldCheck className="h-3 w-3" />
        Active
      </Badge>
    );
  }

  if (daysRemaining <= 0) {
    return (
      <Badge variant="destructive" className="gap-1">
        <Skull className="h-3 w-3" />
        Expired
      </Badge>
    );
  }

  if (daysRemaining <= 7) {
    return (
      <Badge variant="outline" className="text-red-500 border-red-500/50 gap-1">
        <ShieldX className="h-3 w-3" />
        {daysRemaining}d
      </Badge>
    );
  }

  if (daysRemaining <= 30) {
    return (
      <Badge variant="outline" className="text-yellow-500 border-yellow-500/50 gap-1">
        <ShieldAlert className="h-3 w-3" />
        {daysRemaining}d
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="text-green-500 border-green-500/50 gap-1">
      <ShieldCheck className="h-3 w-3" />
      {daysRemaining}d
    </Badge>
  );
}

function HealthDot({ domain }: { domain: Domain }) {
  // Active domains with SSL get a green dot, others get gray
  const isHealthy = domain.status === "active" && domain.ssl_enabled;
  return (
    <div
      className={cn(
        "h-2.5 w-2.5 rounded-full shrink-0",
        isHealthy ? "bg-green-500" : domain.status === "active" ? "bg-yellow-500" : "bg-red-500"
      )}
      title={isHealthy ? "Healthy" : domain.status === "active" ? "SSL issue" : "Unhealthy"}
    />
  );
}

function DeployProgressBar({ progress }: { progress: DeployProgress }) {
  const stage = DEPLOY_STAGES[progress.stage];
  const isFailed = progress.stage === "failed";
  const isComplete = progress.stage === "complete";

  return (
    <div className="space-y-1 min-w-[140px]">
      <div className="flex items-center justify-between text-[10px]">
        <span className={cn(
          "font-medium",
          isFailed && "text-destructive",
          isComplete && "text-green-500"
        )}>
          {stage.label}...
        </span>
        {!isFailed && <span className="text-muted-foreground">{progress.progress}%</span>}
      </div>
      <Progress
        value={progress.progress}
        className={cn(
          "h-1.5",
          isFailed && "[&>div]:bg-destructive",
          isComplete && "[&>div]:bg-green-500"
        )}
      />
      {progress.message && (
        <p className="text-[9px] text-muted-foreground truncate max-w-[160px]">
          {progress.message}
        </p>
      )}
    </div>
  );
}

export function DomainTable({
  domains,
  onDeploy,
  onDelete,
  onEdit,
  selectedDomains,
  onToggleSelect,
  isSelectMode = false,
}: DomainTableProps) {
  const [deployProgress, setDeployProgress] = useState<Record<string, DeployProgress>>({});

  // Listen for deploy_progress events from WebSocket
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as DeployProgress;
      if (detail?.domain) {
        setDeployProgress((prev) => ({
          ...prev,
          [detail.domain]: detail,
        }));

        // Auto-clear completed deploys after 5s
        if (detail.stage === "complete" || detail.stage === "failed") {
          setTimeout(() => {
            setDeployProgress((prev) => {
              const next = { ...prev };
              delete next[detail.domain];
              return next;
            });
          }, 5000);
        }
      }
    };

    window.addEventListener("deploy_progress", handler);
    return () => window.removeEventListener("deploy_progress", handler);
  }, []);

  if (domains.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <Globe className="h-12 w-12 mb-4 opacity-50" />
        <p>No domains configured</p>
        <p className="text-sm">Add a domain to get started</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {isSelectMode && <TableHead className="w-8" />}
          <TableHead className="w-6" />
          <TableHead>Domain</TableHead>
          <TableHead>Project</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>SSL</TableHead>
          <TableHead>Deploy</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {domains.map((domain) => {
          const isSelected = selectedDomains?.has(domain.domain_name) || false;
          const progress = deployProgress[domain.domain_name];
          const isDeploying = progress && progress.stage !== "complete" && progress.stage !== "failed";

          return (
            <TableRow
              key={domain.id}
              className={cn(isSelected && "bg-primary/5")}
            >
              {isSelectMode && (
                <TableCell className="pr-0">
                  <button onClick={() => onToggleSelect?.(domain.domain_name)}>
                    {isSelected ? (
                      <CheckSquare className="h-4 w-4 text-primary" />
                    ) : (
                      <Square className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                </TableCell>
              )}
              <TableCell className="pr-0">
                <HealthDot domain={domain} />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Globe className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{domain.domain_name}</span>
                  <a
                    href={`https://${domain.domain_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </TableCell>
              <TableCell>
                {domain.project_name ? (
                  <div className="flex items-center gap-2">
                    <FolderKanban className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{domain.project_name}</span>
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <Badge variant="outline" className={cn(statusColors[domain.status])}>
                  {domain.status}
                </Badge>
              </TableCell>
              <TableCell>
                <SSLBadge domain={domain} />
              </TableCell>
              <TableCell>
                {progress ? (
                  <DeployProgressBar progress={progress} />
                ) : (
                  <span className="text-xs text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1.5">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => onEdit?.(domain)}
                    title="Edit domain"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => onDeploy?.(domain.domain_name)}
                    disabled={!!isDeploying}
                  >
                    {isDeploying ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <>
                        <Upload className="h-3 w-3 mr-1" />
                        Deploy
                      </>
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:text-destructive"
                    onClick={() => onDelete?.(domain.domain_name)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export { getSSLDaysRemaining };
