"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { memoryApi } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle, AlertTriangle, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface Proposal {
  action: "create" | "update" | "delete";
  content: string | null;
  category?: string;
  confidence: number;
  verified: boolean;
  scope: string;
  evidence?: string;
  reason?: string;
  related_existing?: { id: string; content: string; similarity: number } | null;
}

interface SynthesizeModalProps {
  content: string;
  conversationId?: string;
  projectId?: string;
  domainId?: string;
  onClose: () => void;
}

type LoadingPhase = "extracting" | "verifying" | "classifying" | "done" | "error";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "bg-green-500/15 text-green-600 border-green-500/30"
      : confidence >= 0.6
      ? "bg-yellow-500/15 text-yellow-600 border-yellow-500/30"
      : "bg-red-500/15 text-red-600 border-red-500/30";

  return (
    <span className={cn("inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium", color)}>
      {Math.round(confidence * 100)}%
    </span>
  );
}

function ActionBadge({ action }: { action: string }) {
  const config = {
    create: { label: "New", className: "bg-green-500/15 text-green-600 border-green-500/30" },
    update: { label: "Update", className: "bg-blue-500/15 text-blue-600 border-blue-500/30" },
    delete: { label: "Obsolete", className: "bg-red-500/15 text-red-600 border-red-500/30" },
  };
  const { label, className } = config[action as keyof typeof config] || config.create;

  return (
    <span className={cn("inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium", className)}>
      {label}
    </span>
  );
}

function ProposalCard({
  proposal,
  selected,
  onToggle,
  editedContent,
  onContentChange,
  editedScope,
  onScopeChange,
}: {
  proposal: Proposal;
  selected: boolean;
  onToggle: () => void;
  editedContent: string;
  onContentChange: (val: string) => void;
  editedScope: string;
  onScopeChange: (val: string) => void;
}) {
  return (
    <div className={cn(
      "border rounded-lg p-3 transition-colors",
      selected ? "border-primary/50 bg-primary/5" : "border-border opacity-60"
    )}>
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="mt-1 h-4 w-4 rounded border-border"
        />
        <div className="flex-1 min-w-0 space-y-2">
          {/* Header: action badge + confidence + verified */}
          <div className="flex items-center gap-2 flex-wrap">
            <ActionBadge action={proposal.action} />
            <ConfidenceBadge confidence={proposal.confidence} />
            {proposal.verified && (
              <span className="inline-flex items-center gap-0.5 text-[10px] text-green-600" title={proposal.evidence || "Verified against codebase"}>
                <ShieldCheck className="h-3 w-3" />
                Verified
              </span>
            )}
            {proposal.category && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {proposal.category}
              </Badge>
            )}
          </div>

          {/* For updates: show old content */}
          {proposal.action === "update" && proposal.related_existing && (
            <div className="text-xs text-muted-foreground line-through bg-muted/50 rounded px-2 py-1">
              {proposal.related_existing.content}
            </div>
          )}

          {/* For deletes: show the obsolete learning */}
          {proposal.action === "delete" && proposal.related_existing && (
            <div className="text-xs text-destructive/80 bg-destructive/5 rounded px-2 py-1">
              {proposal.related_existing.content}
            </div>
          )}

          {/* Editable content (for create/update) */}
          {proposal.action !== "delete" && (
            <textarea
              value={editedContent}
              onChange={(e) => onContentChange(e.target.value)}
              className="w-full text-sm bg-background border border-border rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              rows={2}
              disabled={!selected}
            />
          )}

          {/* Delete reason */}
          {proposal.action === "delete" && proposal.reason && (
            <p className="text-xs text-muted-foreground italic">
              Reason: {proposal.reason}
            </p>
          )}

          {/* Evidence */}
          {proposal.evidence && (
            <p className="text-[11px] text-muted-foreground">
              Evidence: {proposal.evidence}
            </p>
          )}

          {/* Scope selector */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground">Scope:</span>
            <select
              value={editedScope}
              onChange={(e) => onScopeChange(e.target.value)}
              className="text-[11px] bg-background border border-border rounded px-1.5 py-0.5"
              disabled={!selected || proposal.action === "delete"}
            >
              <option value="global">Global</option>
              <option value="project">Project</option>
              <option value="domain">Domain</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SynthesizeModal({ content, conversationId, projectId, domainId, onClose }: SynthesizeModalProps) {
  const { token } = useAuthStore();
  const [phase, setPhase] = useState<LoadingPhase>("extracting");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<boolean[]>([]);
  const [editedContents, setEditedContents] = useState<string[]>([]);
  const [editedScopes, setEditedScopes] = useState<string[]>([]);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch proposals on mount
  useEffect(() => {
    if (!token) return;

    let cancelled = false;

    async function fetchProposals() {
      setPhase("extracting");

      try {
        // Simulate phase progression (backend does all steps)
        const phaseTimer = setTimeout(() => {
          if (!cancelled) setPhase("verifying");
        }, 2000);
        const phaseTimer2 = setTimeout(() => {
          if (!cancelled) setPhase("classifying");
        }, 4000);

        const result = await memoryApi.synthesize(token!, {
          content,
          project_id: projectId,
          domain_id: domainId,
          conversation_id: conversationId,
          verify: true,
        });

        clearTimeout(phaseTimer);
        clearTimeout(phaseTimer2);

        if (cancelled) return;

        setProposals(result.proposals);
        setSelected(result.proposals.map(() => true));
        setEditedContents(result.proposals.map((p) => p.content || ""));
        setEditedScopes(result.proposals.map((p) => p.scope || "project"));
        setPhase("done");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to synthesize learnings");
        setPhase("error");
      }
    }

    fetchProposals();
    return () => { cancelled = true; };
  }, [token, content, projectId, domainId, conversationId]);

  const handleToggle = (index: number) => {
    setSelected((prev) => prev.map((v, i) => (i === index ? !v : v)));
  };

  const handleContentChange = (index: number, value: string) => {
    setEditedContents((prev) => prev.map((v, i) => (i === index ? value : v)));
  };

  const handleScopeChange = (index: number, value: string) => {
    setEditedScopes((prev) => prev.map((v, i) => (i === index ? value : v)));
  };

  const handleApply = async () => {
    if (!token) return;
    setIsApplying(true);

    try {
      for (let i = 0; i < proposals.length; i++) {
        if (!selected[i]) continue;

        const proposal = proposals[i];
        const editedContent = editedContents[i];
        const editedScope = editedScopes[i];

        if (proposal.action === "create") {
          await memoryApi.store(token, {
            content: editedContent,
            category: proposal.category,
            scope: editedScope,
            project_id: projectId,
            domain_id: domainId,
            confidence: proposal.confidence,
          });
        } else if (proposal.action === "update" && proposal.related_existing) {
          await memoryApi.update(token, proposal.related_existing.id, {
            content: editedContent,
            category: proposal.category,
            confidence: proposal.confidence,
          });
        } else if (proposal.action === "delete" && proposal.related_existing) {
          await memoryApi.delete(token, proposal.related_existing.id);
        }
      }

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply learnings");
    } finally {
      setIsApplying(false);
    }
  };

  const selectedCount = selected.filter(Boolean).length;

  const phaseText = {
    extracting: "Extracting learnings...",
    verifying: "Verifying against codebase...",
    classifying: "Classifying proposals...",
    done: "",
    error: "",
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Synthesize Learnings</DialogTitle>
          <DialogDescription>
            Extract and manage knowledge from this message
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto space-y-3 py-2">
          {/* Loading state */}
          {phase !== "done" && phase !== "error" && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{phaseText[phase]}</p>
            </div>
          )}

          {/* Error state */}
          {phase === "error" && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <AlertTriangle className="h-8 w-8 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* No results */}
          {phase === "done" && proposals.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <CheckCircle className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No learnings extracted from this message</p>
            </div>
          )}

          {/* Proposals list */}
          {phase === "done" && proposals.length > 0 && (
            <>
              <div className="flex items-center justify-between px-1">
                <p className="text-xs text-muted-foreground">
                  {proposals.length} proposal{proposals.length !== 1 ? "s" : ""} found
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs h-6"
                  onClick={() => setSelected((prev) => prev.map(() => !prev.every(Boolean)))}
                >
                  {selected.every(Boolean) ? "Deselect All" : "Select All"}
                </Button>
              </div>

              {proposals.map((proposal, index) => (
                <ProposalCard
                  key={index}
                  proposal={proposal}
                  selected={selected[index]}
                  onToggle={() => handleToggle(index)}
                  editedContent={editedContents[index]}
                  onContentChange={(val) => handleContentChange(index, val)}
                  editedScope={editedScopes[index]}
                  onScopeChange={(val) => handleScopeChange(index, val)}
                />
              ))}
            </>
          )}
        </div>

        {phase === "done" && proposals.length > 0 && (
          <DialogFooter>
            <Button variant="outline" onClick={onClose} disabled={isApplying}>
              Cancel
            </Button>
            <Button
              onClick={handleApply}
              disabled={selectedCount === 0 || isApplying}
            >
              {isApplying ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Applying...
                </>
              ) : (
                `Apply ${selectedCount} Selected`
              )}
            </Button>
          </DialogFooter>
        )}

        {(phase === "error" || (phase === "done" && proposals.length === 0)) && (
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
