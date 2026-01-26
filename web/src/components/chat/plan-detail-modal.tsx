"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { plansApi, PlanDetail, StepProgress, PlanHistoryEntry } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CheckCircle,
  Circle,
  Clock,
  XCircle,
  SkipForward,
  Loader2,
  AlertTriangle,
  Bot,
  RotateCcw,
  Save,
  Send,
  History,
  ChevronDown,
  ChevronRight,
  FileText,
  Play,
  Pause,
  Info,
} from "lucide-react";

interface PlanDetailModalProps {
  planId: string | null;
  onClose: () => void;
  onEdit?: (planId: string) => void;
}

const STEP_STATUS_CONFIG = {
  pending: { icon: Circle, color: "text-muted-foreground", label: "Pending" },
  in_progress: { icon: Clock, color: "text-blue-500", label: "In Progress" },
  completed: { icon: CheckCircle, color: "text-green-500", label: "Completed" },
  skipped: { icon: SkipForward, color: "text-yellow-500", label: "Skipped" },
  failed: { icon: XCircle, color: "text-red-500", label: "Failed" },
};

const PLAN_STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  exploring: { icon: Loader2, color: "text-blue-400", label: "Exploring" },
  drafting: { icon: FileText, color: "text-purple-500", label: "Drafting" },
  pending: { icon: Clock, color: "text-yellow-500", label: "Pending Approval" },
  approved: { icon: CheckCircle, color: "text-green-500", label: "Approved" },
  executing: { icon: Play, color: "text-blue-500", label: "Executing" },
  paused: { icon: Pause, color: "text-orange-500", label: "Paused" },
  completed: { icon: CheckCircle, color: "text-emerald-600", label: "Completed" },
  cancelled: { icon: XCircle, color: "text-gray-500", label: "Cancelled" },
  failed: { icon: XCircle, color: "text-red-500", label: "Failed" },
};

function StepCard({ step, isCurrentStep }: { step: StepProgress; isCurrentStep: boolean }) {
  const [isExpanded, setIsExpanded] = useState(isCurrentStep);
  const config = STEP_STATUS_CONFIG[step.status] || STEP_STATUS_CONFIG.pending;
  const Icon = config.icon;
  const isCompleted = step.status === "completed";
  const isActive = step.status === "in_progress";

  return (
    <div
      className={cn(
        "border rounded-lg transition-all",
        isCurrentStep && "border-blue-500/50 bg-blue-500/5",
        isCompleted && "border-green-500/30 bg-green-500/5",
        step.status === "failed" && "border-red-500/30 bg-red-500/5"
      )}
    >
      <div
        className="flex items-center gap-3 p-3 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className={cn("shrink-0", isActive && "animate-pulse")}>
          <Icon className={cn("h-5 w-5", config.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className={cn(
              "font-medium text-sm",
              isCompleted && "line-through text-muted-foreground"
            )}>
              Step {step.index + 1}: {step.title}
            </h4>
            {step.agent && (
              <Badge variant="outline" className="text-[10px] h-4 px-1">
                <Bot className="h-2.5 w-2.5 mr-0.5" />
                {step.agent}
              </Badge>
            )}
          </div>
          {step.total_todos > 0 && (
            <div className="flex items-center gap-2 mt-1">
              <Progress
                value={(step.completed_todos / step.total_todos) * 100}
                className="h-1 flex-1"
              />
              <span className="text-[10px] text-muted-foreground">
                {step.completed_todos}/{step.total_todos} todos
              </span>
            </div>
          )}
        </div>
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 pt-0 border-t">
          {/* Description */}
          {step.description && (
            <p className="text-xs text-muted-foreground mt-2">
              {step.description}
            </p>
          )}

          {/* Todos */}
          {step.todos.length > 0 && (
            <div className="mt-3 space-y-1.5">
              <h5 className="text-xs font-medium text-muted-foreground">Todos</h5>
              {step.todos.map((todo, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex items-start gap-2 text-xs",
                    todo.completed && "text-muted-foreground"
                  )}
                >
                  {todo.completed ? (
                    <CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0 mt-0.5" />
                  ) : (
                    <Circle className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                  )}
                  <span className={cn(todo.completed && "line-through")}>
                    {todo.text}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Notes */}
          {step.notes.length > 0 && (
            <div className="mt-3 space-y-1">
              <h5 className="text-xs font-medium text-muted-foreground">Notes</h5>
              {step.notes.map((note, i) => (
                <div key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                  <Info className="h-3 w-3 shrink-0 mt-0.5" />
                  <span>{note}</span>
                </div>
              ))}
            </div>
          )}

          {/* Output */}
          {step.output && (
            <div className="mt-3">
              <h5 className="text-xs font-medium text-muted-foreground mb-1">Output</h5>
              <pre className="text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-24 overflow-y-auto whitespace-pre-wrap">
                {step.output}
              </pre>
            </div>
          )}

          {/* Error */}
          {step.error && (
            <div className="mt-3">
              <h5 className="text-xs font-medium text-red-500 mb-1">Error</h5>
              <pre className="text-[10px] bg-red-500/10 text-red-600 p-2 rounded overflow-x-auto">
                {step.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryTimeline({ entries }: { entries: PlanHistoryEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-muted-foreground">
        <History className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No history entries</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {entries.map((entry, i) => (
        <div key={i} className="flex items-start gap-3">
          <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center shrink-0">
            <Clock className="h-3 w-3 text-muted-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium capitalize">{entry.action.replace(/_/g, " ")}</span>
              {entry.actor && (
                <Badge variant="outline" className="text-[10px] h-4 px-1">
                  {entry.actor}
                </Badge>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {new Date(entry.timestamp).toLocaleString()}
            </p>
            {entry.details && (
              <p className="text-xs text-muted-foreground mt-1">{entry.details}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function PlanDetailModal({ planId, onClose, onEdit }: PlanDetailModalProps) {
  const { token } = useAuthStore();
  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [history, setHistory] = useState<PlanHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("steps");

  // AI Modify state
  const [modifyRequest, setModifyRequest] = useState("");
  const [isModifying, setIsModifying] = useState(false);

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");

  useEffect(() => {
    if (!planId || !token) return;

    const fetchPlan = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [planData, historyData] = await Promise.all([
          plansApi.getPlan(token, planId),
          plansApi.getPlanHistory(token, planId),
        ]);
        setPlan(planData);
        setHistory(historyData.entries);
        setEditTitle(planData.title);
        setEditDescription(planData.description || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plan");
      } finally {
        setIsLoading(false);
      }
    };

    fetchPlan();
  }, [planId, token]);

  const handleSaveEdit = async () => {
    if (!plan || !token) return;

    try {
      const result = await plansApi.updatePlan(token, plan.id, {
        title: editTitle,
        description: editDescription,
      });
      if (result.plan) {
        setPlan(result.plan);
      }
      setIsEditing(false);
    } catch (err) {
      console.error("Failed to update plan:", err);
    }
  };

  const handleModify = async () => {
    if (!plan || !token || !modifyRequest.trim()) return;

    setIsModifying(true);
    try {
      await plansApi.modifyPlan(token, plan.id, modifyRequest);
      setModifyRequest("");
      // Refresh plan
      const updatedPlan = await plansApi.getPlan(token, plan.id);
      setPlan(updatedPlan);
    } catch (err) {
      console.error("Failed to modify plan:", err);
    } finally {
      setIsModifying(false);
    }
  };

  const handleFollowUp = async () => {
    if (!plan || !token) return;

    try {
      await plansApi.followUpPlan(token, plan.id);
      // Refresh plan
      const updatedPlan = await plansApi.getPlan(token, plan.id);
      setPlan(updatedPlan);
    } catch (err) {
      console.error("Failed to follow up:", err);
    }
  };

  const handlePause = async () => {
    if (!plan || !token) return;

    try {
      await plansApi.pausePlan(token, plan.id);
      const updatedPlan = await plansApi.getPlan(token, plan.id);
      setPlan(updatedPlan);
    } catch (err) {
      console.error("Failed to pause:", err);
    }
  };

  const handleResume = async () => {
    if (!plan || !token) return;

    try {
      await plansApi.resumePlan(token, plan.id);
      const updatedPlan = await plansApi.getPlan(token, plan.id);
      setPlan(updatedPlan);
    } catch (err) {
      console.error("Failed to resume:", err);
    }
  };

  const statusConfig = plan ? PLAN_STATUS_CONFIG[plan.status] || PLAN_STATUS_CONFIG.pending : null;

  return (
    <Dialog open={!!planId} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center p-8 gap-2">
            <AlertTriangle className="h-6 w-6 text-destructive" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        ) : plan ? (
          <>
            <DialogHeader>
              {isEditing ? (
                <div className="space-y-2">
                  <Input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Plan title"
                    className="text-lg font-semibold"
                  />
                  <Textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Plan description"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveEdit}>
                      <Save className="h-4 w-4 mr-1" />
                      Save
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <DialogTitle className="text-lg">{plan.title}</DialogTitle>
                    {statusConfig && (
                      <Badge variant="outline" className={cn("text-xs", statusConfig.color)}>
                        <statusConfig.icon className={cn("h-3 w-3 mr-1", plan.is_running && "animate-spin")} />
                        {statusConfig.label}
                      </Badge>
                    )}
                    {plan.is_stuck && (
                      <Badge variant="outline" className="text-xs border-orange-500 text-orange-500">
                        Stuck
                      </Badge>
                    )}
                  </div>
                  {plan.description && (
                    <DialogDescription className="text-sm">
                      {plan.description}
                    </DialogDescription>
                  )}
                </>
              )}
            </DialogHeader>

            {/* Progress bar */}
            <div className="px-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>Progress</span>
                <span>{Math.round(plan.overall_progress * 100)}%</span>
              </div>
              <Progress value={plan.overall_progress * 100} className="h-2" />
            </div>

            {/* Quick actions */}
            <div className="flex items-center gap-2 flex-wrap">
              {!isEditing && (
                <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                  Edit
                </Button>
              )}
              {plan.is_running && (
                <Button size="sm" variant="outline" onClick={handlePause}>
                  <Pause className="h-4 w-4 mr-1" />
                  Pause
                </Button>
              )}
              {plan.status === "paused" && (
                <Button size="sm" variant="outline" onClick={handleResume}>
                  <Play className="h-4 w-4 mr-1" />
                  Resume
                </Button>
              )}
              {plan.is_stuck && (
                <Button size="sm" variant="default" onClick={handleFollowUp}>
                  <RotateCcw className="h-4 w-4 mr-1" />
                  Follow Up
                </Button>
              )}
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
              <TabsList className="shrink-0">
                <TabsTrigger value="steps">Steps & Todos</TabsTrigger>
                <TabsTrigger value="modify">AI Modify</TabsTrigger>
                <TabsTrigger value="history">History</TabsTrigger>
              </TabsList>

              <TabsContent value="steps" className="flex-1 overflow-hidden mt-2">
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2 pr-4">
                    {plan.steps.map((step) => (
                      <StepCard
                        key={step.id}
                        step={step}
                        isCurrentStep={step.index === plan.current_step_index}
                      />
                    ))}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="modify" className="flex-1 overflow-hidden mt-2">
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium mb-2">AI-Assisted Modification</h4>
                    <p className="text-xs text-muted-foreground mb-3">
                      Describe how you want to modify this plan. The AI will update the steps accordingly.
                    </p>
                    <Textarea
                      placeholder="e.g., Add a testing step after implementation, Remove the deployment step, Reorder steps..."
                      value={modifyRequest}
                      onChange={(e) => setModifyRequest(e.target.value)}
                      rows={3}
                    />
                    <Button
                      className="mt-2"
                      onClick={handleModify}
                      disabled={isModifying || !modifyRequest.trim() || plan.is_running}
                    >
                      {isModifying ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4 mr-2" />
                      )}
                      Send to AI
                    </Button>
                    {plan.is_running && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Pause the plan to make modifications.
                      </p>
                    )}
                  </div>

                  {plan.is_stuck && (
                    <div className="border-t pt-4">
                      <h4 className="text-sm font-medium mb-2">Resume Stuck Plan</h4>
                      <p className="text-xs text-muted-foreground mb-3">
                        This plan is stuck. Click below to have the AI analyze what went wrong and suggest how to proceed.
                      </p>
                      <Button variant="default" onClick={handleFollowUp}>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Analyze & Resume
                      </Button>
                    </div>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="history" className="flex-1 overflow-hidden mt-2">
                <ScrollArea className="h-[400px]">
                  <div className="pr-4">
                    <HistoryTimeline entries={history} />
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
