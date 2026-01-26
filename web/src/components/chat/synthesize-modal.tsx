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

interface EvidenceDetail {
  verdict: "VERIFIED" | "PARTIALLY_VERIFIED" | "UNVERIFIED" | "CONTRADICTED";
  supporting_evidence: string[];
  contradicting_evidence: string[];
  files_searched: number;
  summary?: string;
}

interface Proposal {
  action: "create" | "update" | "delete";
  content: string | null;
  phase?: string;  // PAI phase (observe, think, plan, build, execute, verify, learn)
  category?: string;
  confidence: number;
  verified: boolean;
  scope: string;
  evidence?: string;
  evidence_detail?: EvidenceDetail;
  reason?: string;
  related_existing?: { id: string; content: string; similarity: number } | null;
}

type SynthesizeMode = "conversation" | "codebase" | "question";

interface SynthesizeModalProps {
  content: string;
  conversationId?: string;
  projectId?: string;
  domainId?: string;
  onClose: () => void;
  // Optional initial mode - defaults to "conversation"
  initialMode?: SynthesizeMode;
  // For question mode: the question to ask
  question?: string;
  // For codebase mode: specific file patterns to analyze
  filePatterns?: string[];
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

function VerdictBadge({ verdict }: { verdict: string }) {
  const config: Record<string, { label: string; className: string }> = {
    VERIFIED: { label: "Verified", className: "bg-green-500/15 text-green-600 border-green-500/30" },
    PARTIALLY_VERIFIED: { label: "Partial", className: "bg-yellow-500/15 text-yellow-600 border-yellow-500/30" },
    UNVERIFIED: { label: "Unverified", className: "bg-gray-500/15 text-gray-600 border-gray-500/30" },
    CONTRADICTED: { label: "Contradicted", className: "bg-red-500/15 text-red-600 border-red-500/30" },
  };
  const { label, className } = config[verdict] || config.UNVERIFIED;

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

          {/* Evidence Detail */}
          {proposal.evidence_detail && (
            <div className="space-y-1 text-[11px]">
              <div className="flex items-center gap-2">
                <VerdictBadge verdict={proposal.evidence_detail.verdict} />
                <span className="text-muted-foreground">
                  {proposal.evidence_detail.files_searched} files searched
                </span>
              </div>
              {proposal.evidence_detail.summary && (
                <p className="text-muted-foreground">{proposal.evidence_detail.summary}</p>
              )}
              {proposal.evidence_detail.supporting_evidence.length > 0 && (
                <details className="text-green-600">
                  <summary className="cursor-pointer">
                    {proposal.evidence_detail.supporting_evidence.length} supporting evidence
                  </summary>
                  <ul className="mt-1 ml-3 list-disc text-[10px]">
                    {proposal.evidence_detail.supporting_evidence.slice(0, 3).map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </details>
              )}
              {proposal.evidence_detail.contradicting_evidence.length > 0 && (
                <details className="text-red-600">
                  <summary className="cursor-pointer">
                    {proposal.evidence_detail.contradicting_evidence.length} contradicting evidence
                  </summary>
                  <ul className="mt-1 ml-3 list-disc text-[10px]">
                    {proposal.evidence_detail.contradicting_evidence.slice(0, 3).map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          {/* Legacy evidence (if no evidence_detail) */}
          {!proposal.evidence_detail && proposal.evidence && (
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

export function SynthesizeModal({
  content,
  conversationId,
  projectId,
  domainId,
  onClose,
  initialMode = "conversation",
  question,
  filePatterns,
}: SynthesizeModalProps) {
  const { token } = useAuthStore();
  const [mode, setMode] = useState<SynthesizeMode>(initialMode);
  // Start in "idle" state for question/codebase modes, "extracting" for conversation
  const [phase, setPhase] = useState<LoadingPhase>(initialMode === "conversation" ? "extracting" : "done");
  const [isLoading, setIsLoading] = useState(initialMode === "conversation");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<boolean[]>([]);
  const [editedContents, setEditedContents] = useState<string[]>([]);
  const [editedScopes, setEditedScopes] = useState<string[]>([]);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [filesAnalyzed, setFilesAnalyzed] = useState<string[]>([]);
  const [questionInput, setQuestionInput] = useState(question || "");
  const [hasStarted, setHasStarted] = useState(initialMode === "conversation");

  // Fetch proposals
  const fetchProposals = async () => {
    if (!token) return;

    setHasStarted(true);
    setIsLoading(true);
    setPhase("extracting");
    setError(null);
    setAnswer(null);
    setProposals([]);

    try {
      // Simulate phase progression (backend does all steps)
      const phaseTimer = setTimeout(() => setPhase("verifying"), 2000);
      const phaseTimer2 = setTimeout(() => setPhase("classifying"), 4000);

      const result = await memoryApi.synthesize(token!, {
        content: mode === "question" ? questionInput : content,
        project_id: projectId,
        domain_id: domainId,
        conversation_id: conversationId,
        verify: true,
        mode,
        question: mode === "question" ? questionInput : undefined,
        file_patterns: filePatterns,
      });

      clearTimeout(phaseTimer);
      clearTimeout(phaseTimer2);

      setProposals(result.proposals || []);
      setSelected((result.proposals || []).map(() => true));
      setEditedContents((result.proposals || []).map((p: Proposal) => p.content || ""));
      setEditedScopes((result.proposals || []).map((p: Proposal) => p.scope || "project"));
      setAnswer(result.answer || null);
      setFilesAnalyzed(result.files_analyzed || []);
      setPhase("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to synthesize learnings");
      setPhase("error");
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch on mount for conversation mode, or when user triggers codebase/question mode
  useEffect(() => {
    if (mode === "conversation") {
      fetchProposals();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
            phase: proposal.phase || "learn",  // Include phase
            category: proposal.category,
            scope: editedScope,
            project_id: projectId,
            domain_id: domainId,
            confidence: proposal.confidence,
          });
        } else if (proposal.action === "update" && proposal.related_existing) {
          await memoryApi.update(token, proposal.related_existing.id, {
            content: editedContent,
            phase: proposal.phase,  // Include phase
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

  const phaseText: Record<LoadingPhase, string> = {
    extracting: mode === "codebase" ? "Analyzing codebase..." : mode === "question" ? "Searching codebase..." : "Extracting learnings...",
    verifying: "Verifying against codebase...",
    classifying: "Classifying proposals...",
    done: "",
    error: "",
  };

  const modeDescriptions: Record<SynthesizeMode, string> = {
    conversation: "Extract learnings from this message",
    codebase: "Analyze project files to understand how the application works",
    question: "Ask a question about the codebase and store the answer as knowledge",
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Synthesize Learnings</DialogTitle>
          <DialogDescription>
            {modeDescriptions[mode]}
          </DialogDescription>
        </DialogHeader>

        {/* Mode Selector */}
        <div className="flex gap-2 pb-2 border-b">
          {(["conversation", "codebase", "question"] as SynthesizeMode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                if (m === mode) return;
                setMode(m);
                setHasStarted(false);
                setIsLoading(false);
                setProposals([]);
                setAnswer(null);
                setError(null);
                setPhase("done");
                // Auto-start conversation mode
                if (m === "conversation") {
                  setTimeout(() => fetchProposals(), 0);
                }
              }}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-sm rounded-md transition-colors",
                mode === m
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground",
                isLoading && "opacity-50 cursor-not-allowed"
              )}
            >
              {m === "conversation" ? "From Message" : m === "codebase" ? "Analyze Codebase" : "Ask Question"}
            </button>
          ))}
        </div>

        {/* Question Input (for question mode) */}
        {mode === "question" && !hasStarted && (
          <div className="space-y-2 py-2">
            <label className="text-sm font-medium">What would you like to know about the codebase?</label>
            {!projectId && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-md px-3 py-2 text-sm text-yellow-600">
                ⚠️ No project selected. Select a project in the workspace to analyze its codebase.
              </div>
            )}
            <textarea
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              placeholder="e.g., How does the review system work? What is the authentication flow?"
              className="w-full text-sm bg-background border border-border rounded-md px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              rows={3}
              disabled={!projectId}
            />
            <Button
              onClick={fetchProposals}
              disabled={!questionInput.trim() || isLoading || !projectId}
              className="w-full"
            >
              Analyze Codebase
            </Button>
          </div>
        )}

        {/* Codebase mode trigger */}
        {mode === "codebase" && !hasStarted && (
          <div className="flex flex-col items-center py-4 gap-3">
            {!projectId && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-md px-3 py-2 text-sm text-yellow-600 w-full text-center">
                ⚠️ No project selected. Select a project in the workspace first.
              </div>
            )}
            <p className="text-sm text-muted-foreground text-center">
              This will analyze source files in your project to extract knowledge about how the application works.
            </p>
            <Button onClick={fetchProposals} disabled={isLoading || !projectId}>
              Start Analysis
            </Button>
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-y-auto space-y-3 py-2">
          {/* Loading state */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{phaseText[phase]}</p>
            </div>
          )}

          {/* Error state */}
          {!isLoading && phase === "error" && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <AlertTriangle className="h-8 w-8 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
              <Button variant="outline" size="sm" onClick={() => { setHasStarted(false); setError(null); }}>
                Try Again
              </Button>
            </div>
          )}

          {/* No results (only show if completed and no answer) */}
          {!isLoading && hasStarted && phase === "done" && proposals.length === 0 && !answer && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <CheckCircle className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {mode === "conversation"
                  ? "No learnings extracted from this message"
                  : mode === "codebase"
                  ? "No learnings found in the analyzed files"
                  : "Could not find an answer in the codebase"}
              </p>
            </div>
          )}

          {/* Answer display (for question mode) */}
          {!isLoading && answer && (
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 space-y-2">
              <h4 className="font-medium text-sm flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-primary" />
                Answer
              </h4>
              <p className="text-sm whitespace-pre-wrap">{answer}</p>
              {filesAnalyzed.length > 0 && (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">
                    Based on {filesAnalyzed.length} files analyzed
                  </summary>
                  <ul className="mt-1 ml-3 list-disc">
                    {filesAnalyzed.slice(0, 10).map((file, i) => (
                      <li key={i} className="font-mono">{file}</li>
                    ))}
                    {filesAnalyzed.length > 10 && <li>...and {filesAnalyzed.length - 10} more</li>}
                  </ul>
                </details>
              )}
            </div>
          )}

          {/* Proposals list */}
          {!isLoading && proposals.length > 0 && (
            <>
              <div className="flex items-center justify-between px-1">
                <p className="text-xs text-muted-foreground">
                  {proposals.length} learning{proposals.length !== 1 ? "s" : ""} to store
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

        {!isLoading && proposals.length > 0 && (
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

        {!isLoading && hasStarted && proposals.length === 0 && !answer && (
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        )}

        {/* Close button for answer-only results (question mode with answer but no proposals) */}
        {!isLoading && answer && proposals.length === 0 && (
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
