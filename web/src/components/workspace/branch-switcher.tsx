"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { branchApi, Branch, BranchListResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  GitBranch,
  Plus,
  GitMerge,
  Trash2,
  Loader2,
  Check,
  ChevronsUpDown,
  ArrowUp,
  ArrowDown,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BranchSwitcherProps {
  projectId: string;
  onBranchChange?: (branch: string) => void;
}

export function BranchSwitcher({ projectId, onBranchChange }: BranchSwitcherProps) {
  const { token } = useAuthStore();
  const [open, setOpen] = useState(false);
  const [branchData, setBranchData] = useState<BranchListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showMergeDialog, setShowMergeDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  // Create branch form
  const [newBranchName, setNewBranchName] = useState("");
  const [startPoint, setStartPoint] = useState("");
  const [checkoutAfterCreate, setCheckoutAfterCreate] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  // Merge form
  const [mergeBranch, setMergeBranch] = useState("");
  const [mergeNoFf, setMergeNoFf] = useState(false);
  const [mergeSquash, setMergeSquash] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [mergeResult, setMergeResult] = useState<{ success: boolean; message: string } | null>(null);

  // Delete form
  const [deleteBranch, setDeleteBranch] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchBranches = useCallback(async () => {
    if (!token || !projectId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await branchApi.getBranches(token, projectId);
      setBranchData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load branches");
    } finally {
      setIsLoading(false);
    }
  }, [token, projectId]);

  // Fetch branches when popover opens
  useEffect(() => {
    if (open && token && projectId) {
      fetchBranches();
    }
  }, [open, token, projectId, fetchBranches]);

  const handleCheckout = async (branchName: string) => {
    if (!token || !projectId) return;

    setIsLoading(true);
    try {
      await branchApi.checkoutBranch(token, projectId, { branch: branchName });
      await fetchBranches();
      onBranchChange?.(branchName);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to checkout branch");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateBranch = async () => {
    if (!token || !projectId || !newBranchName.trim()) return;

    setIsCreating(true);
    try {
      await branchApi.createBranch(token, projectId, {
        name: newBranchName.trim(),
        start_point: startPoint || undefined,
        checkout: checkoutAfterCreate,
      });
      await fetchBranches();
      if (checkoutAfterCreate) {
        onBranchChange?.(newBranchName.trim());
      }
      setShowCreateDialog(false);
      setNewBranchName("");
      setStartPoint("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create branch");
    } finally {
      setIsCreating(false);
    }
  };

  const handleMergeBranch = async () => {
    if (!token || !projectId || !mergeBranch) return;

    setIsMerging(true);
    setMergeResult(null);
    try {
      const result = await branchApi.mergeBranch(token, projectId, {
        source: mergeBranch,
        no_ff: mergeNoFf,
        squash: mergeSquash,
      });
      if (result.success) {
        setMergeResult({ success: true, message: `Merged ${mergeBranch} successfully` });
        await fetchBranches();
        setTimeout(() => {
          setShowMergeDialog(false);
          setMergeResult(null);
          setMergeBranch("");
        }, 1500);
      } else if (result.conflicts && result.conflicts.length > 0) {
        setMergeResult({
          success: false,
          message: `Merge conflicts in ${result.conflicts.length} file(s): ${result.conflicts.slice(0, 3).join(", ")}${result.conflicts.length > 3 ? "..." : ""}`,
        });
      }
    } catch (err) {
      setMergeResult({
        success: false,
        message: err instanceof Error ? err.message : "Merge failed",
      });
    } finally {
      setIsMerging(false);
    }
  };

  const handleDeleteBranch = async () => {
    if (!token || !projectId || !deleteBranch) return;

    setIsDeleting(true);
    try {
      await branchApi.deleteBranch(token, projectId, deleteBranch);
      await fetchBranches();
      setShowDeleteDialog(false);
      setDeleteBranch("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete branch");
    } finally {
      setIsDeleting(false);
    }
  };

  const currentBranch = branchData?.current || "main";
  const localBranches = branchData?.branches.filter((b) => !b.is_remote) || [];
  const remoteBranches = branchData?.branches.filter((b) => b.is_remote) || [];
  const currentBranchInfo = branchData?.branches.find((b) => b.is_current);

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 text-xs px-2"
            role="combobox"
            aria-expanded={open}
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span className="hidden sm:inline max-w-[100px] truncate">
              {currentBranch}
            </span>
            {currentBranchInfo && (currentBranchInfo.ahead > 0 || currentBranchInfo.behind > 0) && (
              <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                {currentBranchInfo.ahead > 0 && (
                  <span className="flex items-center">
                    <ArrowUp className="h-2.5 w-2.5" />
                    {currentBranchInfo.ahead}
                  </span>
                )}
                {currentBranchInfo.behind > 0 && (
                  <span className="flex items-center">
                    <ArrowDown className="h-2.5 w-2.5" />
                    {currentBranchInfo.behind}
                  </span>
                )}
              </span>
            )}
            <ChevronsUpDown className="h-3 w-3 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[280px] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search branches..." />
            <CommandList>
              {isLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-6 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 mr-2" />
                  {error}
                </div>
              ) : (
                <>
                  <CommandEmpty>No branches found.</CommandEmpty>

                  {localBranches.length > 0 && (
                    <CommandGroup heading="Local Branches">
                      {localBranches.map((branch) => (
                        <CommandItem
                          key={branch.name}
                          value={branch.name}
                          onSelect={() => handleCheckout(branch.name)}
                          className="flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2">
                            {branch.is_current && (
                              <Check className="h-3.5 w-3.5 text-primary" />
                            )}
                            <span className={cn(!branch.is_current && "ml-5")}>
                              {branch.name}
                            </span>
                          </div>
                          {(branch.ahead > 0 || branch.behind > 0) && (
                            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                              {branch.ahead > 0 && (
                                <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                                  +{branch.ahead}
                                </Badge>
                              )}
                              {branch.behind > 0 && (
                                <Badge variant="outline" className="h-4 px-1 text-[10px]">
                                  -{branch.behind}
                                </Badge>
                              )}
                            </div>
                          )}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  )}

                  {remoteBranches.length > 0 && (
                    <CommandGroup heading="Remote Branches">
                      {remoteBranches.slice(0, 10).map((branch) => (
                        <CommandItem
                          key={branch.name}
                          value={branch.name}
                          onSelect={() => handleCheckout(branch.name.replace("origin/", ""))}
                          className="text-muted-foreground"
                        >
                          <span className="ml-5">{branch.name}</span>
                        </CommandItem>
                      ))}
                      {remoteBranches.length > 10 && (
                        <CommandItem disabled className="text-xs text-muted-foreground">
                          ... and {remoteBranches.length - 10} more
                        </CommandItem>
                      )}
                    </CommandGroup>
                  )}

                  <CommandSeparator />

                  <CommandGroup>
                    <CommandItem
                      onSelect={() => {
                        setOpen(false);
                        setShowCreateDialog(true);
                      }}
                    >
                      <Plus className="h-3.5 w-3.5 mr-2" />
                      Create Branch...
                    </CommandItem>
                    <CommandItem
                      onSelect={() => {
                        setOpen(false);
                        setShowMergeDialog(true);
                      }}
                    >
                      <GitMerge className="h-3.5 w-3.5 mr-2" />
                      Merge Branch...
                    </CommandItem>
                    <CommandItem
                      onSelect={() => {
                        setOpen(false);
                        setShowDeleteDialog(true);
                      }}
                      className="text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5 mr-2" />
                      Delete Branch...
                    </CommandItem>
                    <CommandItem onSelect={fetchBranches}>
                      <RefreshCw className="h-3.5 w-3.5 mr-2" />
                      Refresh
                    </CommandItem>
                  </CommandGroup>
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Create Branch Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Branch</DialogTitle>
            <DialogDescription>
              Create a new branch from the current HEAD or a specific starting point.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="branch-name">Branch Name</Label>
              <Input
                id="branch-name"
                value={newBranchName}
                onChange={(e) => setNewBranchName(e.target.value)}
                placeholder="feature/my-feature"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="start-point">Start From (Optional)</Label>
              <Select value={startPoint} onValueChange={setStartPoint}>
                <SelectTrigger>
                  <SelectValue placeholder="Current HEAD" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Current HEAD</SelectItem>
                  {localBranches.map((branch) => (
                    <SelectItem key={branch.name} value={branch.name}>
                      {branch.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="checkout-after">Switch to branch after creating</Label>
              <Switch
                id="checkout-after"
                checked={checkoutAfterCreate}
                onCheckedChange={setCheckoutAfterCreate}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateBranch} disabled={isCreating || !newBranchName.trim()}>
              {isCreating ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating...</>
              ) : (
                "Create Branch"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Merge Branch Dialog */}
      <Dialog open={showMergeDialog} onOpenChange={setShowMergeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge Branch</DialogTitle>
            <DialogDescription>
              Merge a branch into the current branch ({currentBranch}).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Branch to Merge</Label>
              <Select value={mergeBranch} onValueChange={setMergeBranch}>
                <SelectTrigger>
                  <SelectValue placeholder="Select branch..." />
                </SelectTrigger>
                <SelectContent>
                  {localBranches
                    .filter((b) => !b.is_current)
                    .map((branch) => (
                      <SelectItem key={branch.name} value={branch.name}>
                        {branch.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="no-ff">No fast-forward</Label>
                  <p className="text-xs text-muted-foreground">Always create a merge commit</p>
                </div>
                <Switch id="no-ff" checked={mergeNoFf} onCheckedChange={setMergeNoFf} />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="squash">Squash commits</Label>
                  <p className="text-xs text-muted-foreground">Combine all commits into one</p>
                </div>
                <Switch id="squash" checked={mergeSquash} onCheckedChange={setMergeSquash} />
              </div>
            </div>
            {mergeResult && (
              <div className={cn(
                "flex items-center gap-2 p-3 rounded-md text-sm",
                mergeResult.success ? "bg-green-500/15 text-green-600" : "bg-destructive/15 text-destructive"
              )}>
                {mergeResult.success ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                {mergeResult.message}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMergeDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleMergeBranch} disabled={isMerging || !mergeBranch}>
              {isMerging ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Merging...</>
              ) : (
                <><GitMerge className="h-4 w-4 mr-2" />Merge</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Branch Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Branch</DialogTitle>
            <DialogDescription>
              This will permanently delete the selected branch. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Branch to Delete</Label>
              <Select value={deleteBranch} onValueChange={setDeleteBranch}>
                <SelectTrigger>
                  <SelectValue placeholder="Select branch..." />
                </SelectTrigger>
                <SelectContent>
                  {localBranches
                    .filter((b) => !b.is_current)
                    .map((branch) => (
                      <SelectItem key={branch.name} value={branch.name}>
                        {branch.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            {deleteBranch && (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
                <p className="text-sm text-destructive">
                  Are you sure you want to delete branch &quot;{deleteBranch}&quot;?
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteBranch}
              disabled={isDeleting || !deleteBranch}
            >
              {isDeleting ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Deleting...</>
              ) : (
                <><Trash2 className="h-4 w-4 mr-2" />Delete</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
