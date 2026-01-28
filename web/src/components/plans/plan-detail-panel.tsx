"use client";

import { useState, useEffect } from "react";
import { usePlansStore } from "@/stores/plans-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { StepList } from "./step-list";
import { PlanBranchIndicator } from "./plan-branch-indicator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  X,
  Pencil,
  Save,
  Play,
  Pause,
  Copy,
  Trash2,
  RotateCcw,
  Clock,
  CheckCircle,
  AlertTriangle,
  Loader2,
  History,
  Settings,
  ListTodo,
  FileText,
  ExternalLink,
} from "lucide-react";

interface PlanDetailPanelProps {
  className?: string;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "—";
  const date = new Date(dateStr);
  return date.toLocaleString();
}

export function PlanDetailPanel({ className }: PlanDetailPanelProps) {
  const { token } = useAuthStore();
  const {
    selectedPlan,
    selectedPlanId,
    planHistory,
    isLoadingPlan,
    isLoadingHistory,
    isDetailPanelOpen,
    detailPanelTab,
    isEditing,
    editDraft,
    isSaving,
    closeDetailPanel,
    setDetailPanelTab,
    startEditing,
    cancelEditing,
    updateEditDraft,
    saveEditDraft,
    fetchPlanHistory,
    pausePlan,
    resumePlan,
    clonePlan,
    deletePlan,
    followUpPlan,
    refreshPlans,
  } = usePlansStore();

  // Fetch history when history tab is selected
  useEffect(() => {
    if (detailPanelTab === "history" && selectedPlanId && token) {
      fetchPlanHistory(token, selectedPlanId);
    }
  }, [detailPanelTab, selectedPlanId, token, fetchPlanHistory]);

  const handleSave = async () => {
    if (!token) return;
    const success = await saveEditDraft(token);
    if (success) {
      await refreshPlans(token);
    }
  };

  const handlePause = async () => {
    if (!token || !selectedPlanId) return;
    await pausePlan(token, selectedPlanId);
    await refreshPlans(token);
  };

  const handleResume = async () => {
    if (!token || !selectedPlanId) return;
    await resumePlan(token, selectedPlanId);
    await refreshPlans(token);
  };

  const handleClone = async () => {
    if (!token || !selectedPlanId) return;
    await clonePlan(token, selectedPlanId);
    await refreshPlans(token);
  };

  const handleDelete = async () => {
    if (!token || !selectedPlanId) return;
    if (!confirm("Are you sure you want to delete this plan?")) return;
    await deletePlan(token, selectedPlanId);
    closeDetailPanel();
    await refreshPlans(token);
  };

  const handleFollowUp = async () => {
    if (!token || !selectedPlanId) return;
    await followUpPlan(token, selectedPlanId);
    await refreshPlans(token);
  };

  if (!selectedPlan) return null;

  const plan = isEditing && editDraft ? { ...selectedPlan, ...editDraft } : selectedPlan;
  const progress = plan.total_steps > 0
    ? (plan.completed_steps / plan.total_steps) * 100
    : 0;
  const isPaused = plan.status.toLowerCase() === "paused";
  const isRunning = plan.is_running;
  const isStuck = plan.is_stuck;

  return (
    <Sheet open={isDetailPanelOpen} onOpenChange={(open) => !open && closeDetailPanel()}>
      <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col">
        <SheetHeader className="px-4 py-3 border-b shrink-0">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-lg font-semibold truncate pr-4">
              {isEditing ? (
                <Input
                  value={editDraft?.title || ""}
                  onChange={(e) => updateEditDraft({ title: e.target.value })}
                  className="h-8 text-lg font-semibold"
                />
              ) : (
                plan.title
              )}
            </SheetTitle>
            <div className="flex items-center gap-1 shrink-0">
              {isEditing ? (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={cancelEditing}
                    disabled={isSaving}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={isSaving}
                  >
                    {isSaving ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4 mr-1" />
                    )}
                    Save
                  </Button>
                </>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={startEditing}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </SheetHeader>

        {isLoadingPlan ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            {/* Status and progress bar */}
            <div className="px-4 py-3 border-b space-y-3 shrink-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge
                  variant={
                    plan.status.toLowerCase() === "completed" ? "default" :
                    plan.status.toLowerCase() === "failed" ? "destructive" :
                    "secondary"
                  }
                >
                  {plan.status}
                </Badge>
                {isRunning && (
                  <Badge variant="outline" className="border-blue-500 text-blue-500">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Running
                  </Badge>
                )}
                {isStuck && (
                  <Badge variant="outline" className="border-orange-500 text-orange-500">
                    <AlertTriangle className="h-3 w-3 mr-1" />
                    Stuck
                  </Badge>
                )}
                {plan.conversation_id && (
                  <Badge variant="outline" className="text-xs">
                    <ExternalLink className="h-3 w-3 mr-1" />
                    Linked to chat
                  </Badge>
                )}
                <PlanBranchIndicator />
              </div>

              {plan.total_steps > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Progress</span>
                    <span className="font-medium">{plan.completed_steps}/{plan.total_steps} steps</span>
                  </div>
                  <Progress value={progress} className="h-2" />
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-2 flex-wrap">
                {isRunning && !isPaused && (
                  <Button variant="outline" size="sm" onClick={handlePause}>
                    <Pause className="h-4 w-4 mr-1" />
                    Pause
                  </Button>
                )}
                {(isPaused || (isStuck && !isRunning)) && (
                  <Button variant="outline" size="sm" onClick={handleResume}>
                    <Play className="h-4 w-4 mr-1" />
                    Resume
                  </Button>
                )}
                {isStuck && (
                  <Button variant="outline" size="sm" onClick={handleFollowUp}>
                    <RotateCcw className="h-4 w-4 mr-1" />
                    Follow Up
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={handleClone}>
                  <Copy className="h-4 w-4 mr-1" />
                  Clone
                </Button>
                {!isRunning && (
                  <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={handleDelete}>
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </Button>
                )}
              </div>
            </div>

            {/* Tabs */}
            <Tabs
              value={detailPanelTab}
              onValueChange={(v) => setDetailPanelTab(v as typeof detailPanelTab)}
              className="flex-1 flex flex-col min-h-0"
            >
              <TabsList className="mx-4 mt-2 shrink-0">
                <TabsTrigger value="steps" className="flex-1">
                  <ListTodo className="h-4 w-4 mr-1.5" />
                  Steps
                </TabsTrigger>
                <TabsTrigger value="history" className="flex-1">
                  <History className="h-4 w-4 mr-1.5" />
                  History
                </TabsTrigger>
                <TabsTrigger value="settings" className="flex-1">
                  <Settings className="h-4 w-4 mr-1.5" />
                  Details
                </TabsTrigger>
              </TabsList>

              <TabsContent value="steps" className="flex-1 min-h-0 mt-0 data-[state=active]:flex data-[state=active]:flex-col">
                <ScrollArea className="flex-1 px-4 py-3">
                  <StepList
                    steps={plan.steps}
                    currentStepIndex={plan.current_step_index}
                    planId={selectedPlanId || ""}
                    isEditing={isEditing}
                  />
                </ScrollArea>
              </TabsContent>

              <TabsContent value="history" className="flex-1 min-h-0 mt-0 data-[state=active]:flex data-[state=active]:flex-col">
                <ScrollArea className="flex-1 px-4 py-3">
                  {isLoadingHistory ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : planHistory.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                      <History className="h-8 w-8 mb-2 opacity-50" />
                      <p className="text-sm">No history available</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {planHistory.map((entry, i) => (
                        <Card key={i} className="p-3">
                          <div className="flex items-start gap-2">
                            <Clock className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-medium text-sm">{entry.action}</span>
                                {entry.actor && (
                                  <Badge variant="outline" className="text-[10px] h-4">
                                    {entry.actor}
                                  </Badge>
                                )}
                              </div>
                              {entry.details && (
                                <p className="text-xs text-muted-foreground mt-0.5">
                                  {entry.details}
                                </p>
                              )}
                              <p className="text-[10px] text-muted-foreground mt-1">
                                {formatDate(entry.timestamp)}
                              </p>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="settings" className="flex-1 min-h-0 mt-0 data-[state=active]:flex data-[state=active]:flex-col">
                <ScrollArea className="flex-1 px-4 py-3">
                  <div className="space-y-4">
                    {/* Description */}
                    <div className="space-y-2">
                      <Label>Description</Label>
                      {isEditing ? (
                        <Textarea
                          value={editDraft?.description || ""}
                          onChange={(e) => updateEditDraft({ description: e.target.value })}
                          rows={3}
                        />
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {plan.description || "No description"}
                        </p>
                      )}
                    </div>

                    {/* Metadata */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Created</Label>
                        <p className="text-sm">{formatDate(plan.created_at)}</p>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Updated</Label>
                        <p className="text-sm">{formatDate(plan.updated_at)}</p>
                      </div>
                      {plan.approved_at && (
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Approved</Label>
                          <p className="text-sm">{formatDate(plan.approved_at)}</p>
                        </div>
                      )}
                      {plan.completed_at && (
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Completed</Label>
                          <p className="text-sm">{formatDate(plan.completed_at)}</p>
                        </div>
                      )}
                    </div>

                    {/* Exploration notes */}
                    {plan.exploration_notes && plan.exploration_notes.length > 0 && (
                      <div className="space-y-2">
                        <Label>Exploration Notes</Label>
                        <Card className="p-3">
                          <ul className="text-sm text-muted-foreground space-y-1">
                            {plan.exploration_notes.map((note, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <FileText className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                                <span>{note}</span>
                              </li>
                            ))}
                          </ul>
                        </Card>
                      </div>
                    )}

                    {/* Files explored */}
                    {plan.files_explored && plan.files_explored.length > 0 && (
                      <div className="space-y-2">
                        <Label>Files Explored</Label>
                        <div className="flex flex-wrap gap-1">
                          {plan.files_explored.map((file, i) => (
                            <Badge key={i} variant="secondary" className="text-[10px] font-mono">
                              {file.split("/").pop()}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Branch Strategy */}
                    <div className="space-y-2">
                      <Label>Branch Strategy</Label>
                      <PlanBranchIndicator showDetails />
                    </div>

                    {/* Plan ID */}
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Plan ID</Label>
                      <p className="text-sm font-mono text-muted-foreground">{plan.id}</p>
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
