"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useMemoryStore } from "@/stores/memory-store";
import { memoryApi, projectsApi, Project } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
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
import {
  Search,
  Brain,
  Database,
  FileText,
  Loader2,
  Pencil,
  Trash2,
  Download,
  Upload,
  CheckSquare,
  Square,
  Network,
  List,
  SortAsc,
  X,
  FolderOpen,
  Globe,
} from "lucide-react";

interface SearchResult {
  id: string;
  content: string;
  phase: string;
  category: string;
  score: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

interface Learning {
  id: string;
  phase: string;
  category?: string;
  content: string;
  outcome: string;
  created_at: string;
  importance?: number;
  scope?: string;
  project_id?: string;
  project_name?: string;
}

const scopes = [
  { value: "global", label: "Global", icon: Globe },
  { value: "project", label: "Project", icon: FolderOpen },
];

interface MemoryStats {
  total_memories: number;
  by_tier: Record<string, number>;
  by_agent: Record<string, number>;
}

const phases = [
  { value: "observe", label: "OBSERVE" },
  { value: "think", label: "THINK" },
  { value: "plan", label: "PLAN" },
  { value: "build", label: "BUILD" },
  { value: "execute", label: "EXECUTE" },
  { value: "verify", label: "VERIFY" },
  { value: "learn", label: "LEARN" },
];

const phaseColors: Record<string, string> = {
  observe: "bg-blue-500/20 text-blue-600",
  think: "bg-amber-500/20 text-amber-600",
  plan: "bg-purple-500/20 text-purple-600",
  build: "bg-green-500/20 text-green-600",
  execute: "bg-orange-500/20 text-orange-600",
  verify: "bg-cyan-500/20 text-cyan-600",
  learn: "bg-pink-500/20 text-pink-600",
};

export default function MemoryPage() {
  const { token } = useAuthStore();
  const {
    selectedIds,
    isSelectMode,
    viewMode,
    sortBy,
    toggleSelect,
    selectAll,
    clearSelection,
    setSelectMode,
    setViewMode,
    setSortBy,
  } = useMemoryStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingLearnings, setIsLoadingLearnings] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editPhase, setEditPhase] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [learningsError, setLearningsError] = useState<string | null>(null);
  // Create memory state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createContent, setCreateContent] = useState("");
  const [createPhase, setCreatePhase] = useState("");
  const [createCategory, setCreateCategory] = useState("");
  const [createScope, setCreateScope] = useState("global");
  const [createProjectId, setCreateProjectId] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Project filtering
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectFilter, setSelectedProjectFilter] = useState<string | null>(null);
  const [selectedScopeFilter, setSelectedScopeFilter] = useState<string | null>(null);
  // Edit memory - additional fields
  const [editScope, setEditScope] = useState("");
  const [editProjectId, setEditProjectId] = useState("");

  useEffect(() => {
    if (token) {
      fetchStats();
      fetchLearnings();
      fetchProjects();
    }
  }, [token]);

  const fetchProjects = async () => {
    if (!token) return;
    try {
      const response = await projectsApi.list(token);
      setProjects(response.projects || []);
    } catch (error) {
      console.error("Failed to fetch projects:", error);
    }
  };

  const fetchStats = async () => {
    if (!token) return;
    try {
      const response = await memoryApi.stats(token);
      setStats(response);
    } catch (error) {
      console.error("Failed to fetch memory stats:", error);
    } finally {
      setIsLoadingStats(false);
    }
  };

  const fetchLearnings = async (phase?: string, projectId?: string, scope?: string) => {
    if (!token) return;
    setIsLoadingLearnings(true);
    setLearningsError(null);
    try {
      const response = await memoryApi.learnings(
        token,
        phase || undefined,
        projectId || undefined,
        scope || undefined
      );
      if ((response as any).error) {
        setLearningsError((response as any).error);
        setLearnings([]);
      } else {
        setLearnings(response.learnings);
      }
    } catch (error) {
      console.error("Failed to fetch learnings:", error);
      setLearningsError(error instanceof Error ? error.message : "Failed to fetch learnings");
    } finally {
      setIsLoadingLearnings(false);
    }
  };

  const handleSearch = async () => {
    if (!token || !searchQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      const response = await memoryApi.search(token, searchQuery.trim(), 20);
      if ((response as any).error) {
        setSearchError((response as any).error);
        setSearchResults([]);
      } else {
        setSearchResults(response.results);
      }
    } catch (error) {
      console.error("Failed to search memory:", error);
      setSearchError(error instanceof Error ? error.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const handleCreateMemory = async () => {
    if (!token || !createContent.trim()) return;
    setIsCreating(true);
    try {
      const result = await memoryApi.store(token, {
        content: createContent.trim(),
        phase: createPhase && createPhase !== "none" ? createPhase : undefined,
        category: createCategory || undefined,
        scope: createScope || "global",
        project_id: createScope === "project" && createProjectId ? createProjectId : undefined,
      });
      if ((result as any).error) {
        console.error("Store failed:", (result as any).error);
      } else {
        setCreateContent("");
        setCreatePhase("");
        setCreateCategory("");
        setCreateScope("global");
        setCreateProjectId("");
        setIsCreateOpen(false);
        fetchLearnings(selectedPhase || undefined, selectedProjectFilter || undefined, selectedScopeFilter || undefined);
        fetchStats();
      }
    } catch (error) {
      console.error("Failed to store memory:", error);
    } finally {
      setIsCreating(false);
    }
  };

  const handlePhaseFilter = (phase: string | null) => {
    setSelectedPhase(phase);
    fetchLearnings(phase || undefined, selectedProjectFilter || undefined, selectedScopeFilter || undefined);
  };

  const handleProjectFilter = (projectId: string | null) => {
    setSelectedProjectFilter(projectId);
    fetchLearnings(selectedPhase || undefined, projectId || undefined, selectedScopeFilter || undefined);
  };

  const handleScopeFilter = (scope: string | null) => {
    setSelectedScopeFilter(scope);
    if (scope !== "project") {
      setSelectedProjectFilter(null);
    }
    fetchLearnings(selectedPhase || undefined, selectedProjectFilter || undefined, scope || undefined);
  };

  const handleEditStart = (item: { id: string; content: string; phase?: string; category?: string; scope?: string; project_id?: string }) => {
    setEditingId(item.id);
    setEditContent(item.content);
    setEditPhase(item.phase || "");
    setEditCategory(item.category || "");
    setEditScope(item.scope || "global");
    setEditProjectId(item.project_id || "");
  };

  const handleEditSave = async () => {
    if (!token || !editingId) return;
    setIsUpdating(true);
    try {
      await memoryApi.update(token, editingId, {
        content: editContent || undefined,
        phase: editPhase || undefined,
        category: editCategory || undefined,
        scope: editScope || undefined,
        project_id: editScope === "project" && editProjectId ? editProjectId : null,
      });
      fetchLearnings(selectedPhase || undefined, selectedProjectFilter || undefined, selectedScopeFilter || undefined);
      if (searchQuery) handleSearch();
      setEditingId(null);
    } catch (error) {
      console.error("Failed to update memory:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await memoryApi.delete(token, id);
      setLearnings((prev) => prev.filter((l) => l.id !== id));
      setSearchResults((prev) => prev.filter((r) => r.id !== id));
      setDeletingId(null);
      fetchStats();
    } catch (error) {
      console.error("Failed to delete memory:", error);
    }
  };

  const handleBulkDelete = async () => {
    if (!token || selectedIds.size === 0) return;
    setIsBulkDeleting(true);
    try {
      for (const id of selectedIds) {
        await memoryApi.delete(token, id);
      }
      setLearnings((prev) => prev.filter((l) => !selectedIds.has(l.id)));
      setSearchResults((prev) => prev.filter((r) => !selectedIds.has(r.id)));
      clearSelection();
      fetchStats();
    } catch (error) {
      console.error("Bulk delete error:", error);
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const handleExport = (format: "json" | "csv") => {
    const data = selectedIds.size > 0
      ? learnings.filter((l) => selectedIds.has(l.id))
      : learnings;

    let content: string;
    let filename: string;
    let mimeType: string;

    if (format === "json") {
      content = JSON.stringify(data, null, 2);
      filename = "memories.json";
      mimeType = "application/json";
    } else {
      const headers = "ID,Phase,Category,Content,Outcome,Created\n";
      const rows = data.map((l) =>
        `"${l.id}","${l.phase}","${l.category || ""}","${l.content.replace(/"/g, '""')}","${l.outcome}","${l.created_at}"`
      ).join("\n");
      content = headers + rows;
      filename = "memories.csv";
      mimeType = "text/csv";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;

    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const items = Array.isArray(data) ? data : [data];

      let imported = 0;
      for (const item of items) {
        if (item.content) {
          try {
            await memoryApi.store(token, {
              content: item.content,
              phase: item.phase || undefined,
              category: item.category || undefined,
            });
            imported++;
          } catch (err) {
            console.error("Failed to import item:", err);
          }
        }
      }

      console.log(`Imported ${imported}/${items.length} memories`);
      fetchLearnings(selectedPhase || undefined);
      fetchStats();
    } catch (error) {
      console.error("Import failed:", error);
    }

    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Create a project ID to name mapping
  const projectNameMap = useMemo(() => {
    const map = new Map<string, string>();
    projects.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [projects]);

  // Enrich learnings with project names
  const enrichedLearnings = useMemo(() => {
    return learnings.map((l) => ({
      ...l,
      project_name: l.project_id ? projectNameMap.get(l.project_id) : undefined,
    }));
  }, [learnings, projectNameMap]);

  // Sort learnings
  const sortedLearnings = useMemo(() => {
    const sorted = [...enrichedLearnings];
    switch (sortBy) {
      case "date":
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        break;
      case "importance":
        sorted.sort((a, b) => (b.importance || 0) - (a.importance || 0));
        break;
      case "phase":
        sorted.sort((a, b) => (a.phase || "").localeCompare(b.phase || ""));
        break;
      case "project":
        sorted.sort((a, b) => (a.project_name || "zzz").localeCompare(b.project_name || "zzz"));
        break;
      case "scope":
        sorted.sort((a, b) => (a.scope || "global").localeCompare(b.scope || "global"));
        break;
      default:
        break;
    }
    return sorted;
  }, [enrichedLearnings, sortBy]);

  return (
    <div className="p-4 sm:p-6 h-full overflow-y-auto overflow-x-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold">Memory</h1>
          <p className="text-sm text-muted-foreground">Browse and manage the AI memory system</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap shrink-0">
          <Button
            size="sm"
            className="h-7 text-xs"
            onClick={() => setIsCreateOpen(true)}
          >
            <Brain className="h-3 w-3 mr-1" />
            Store Memory
          </Button>
          <Button
            variant={isSelectMode ? "secondary" : "outline"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setSelectMode(!isSelectMode)}
          >
            <CheckSquare className="h-3 w-3 mr-1" />
            Select
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => handleExport("json")}>
            <Download className="h-3 w-3 mr-1" />
            JSON
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => handleExport("csv")}>
            <Download className="h-3 w-3 mr-1" />
            CSV
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-3 w-3 mr-1" />
            Import
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImport}
          />
        </div>
      </div>

      {/* Bulk actions bar */}
      {isSelectMode && selectedIds.size > 0 && (
        <div className="mb-4 flex items-center justify-between p-2 bg-primary/5 border rounded-md">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{selectedIds.size} selected</span>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => selectAll(learnings.map((l) => l.id))}>
              Select All
            </Button>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={clearSelection}>
              Clear
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-6 text-xs" onClick={() => handleExport("json")}>
              Export Selected
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="h-6 text-xs"
              onClick={handleBulkDelete}
              disabled={isBulkDeleting}
            >
              {isBulkDeleting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Trash2 className="h-3 w-3 mr-1" />}
              Delete
            </Button>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Total Memories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              <span className="text-xl font-bold">{isLoadingStats ? "-" : stats?.total_memories || 0}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Hot Tier</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-red-500" />
              <span className="text-xl font-bold">{isLoadingStats ? "-" : stats?.by_tier?.hot || 0}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Warm Tier</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-yellow-500" />
              <span className="text-xl font-bold">{isLoadingStats ? "-" : stats?.by_tier?.warm || 0}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Cold Tier</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-500" />
              <span className="text-xl font-bold">{isLoadingStats ? "-" : stats?.by_tier?.cold || 0}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="search" className="space-y-4">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="search">Search</TabsTrigger>
            <TabsTrigger value="learnings">Learnings</TabsTrigger>
            <TabsTrigger value="graph">Graph</TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2">
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SortAsc className="h-3 w-3 mr-1" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="relevance">Relevance</SelectItem>
                <SelectItem value="date">Date</SelectItem>
                <SelectItem value="importance">Importance</SelectItem>
                <SelectItem value="phase">Phase</SelectItem>
                <SelectItem value="project">Project</SelectItem>
                <SelectItem value="scope">Scope</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <TabsContent value="search" className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={isSearching} size="sm">
              {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </Button>
          </div>

          {searchError && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive text-sm mb-3">
              <X className="h-4 w-4 shrink-0" />
              <span>{searchError}</span>
            </div>
          )}

          <ScrollArea className="h-[500px] w-full">
            {searchResults.length === 0 && !searchError ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <Search className="h-12 w-12 mb-4 opacity-50" />
                <p>Search for memories using natural language</p>
              </div>
            ) : (
              <div className="space-y-3">
                {searchResults.map((result) => (
                  <Card key={result.id} className="group">
                    <CardContent className="pt-3 pb-3 px-3">
                      <div className="flex items-start gap-2">
                        {isSelectMode && (
                          <button onClick={() => toggleSelect(result.id)} className="mt-1 shrink-0">
                            {selectedIds.has(result.id) ? (
                              <CheckSquare className="h-4 w-4 text-primary" />
                            ) : (
                              <Square className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap mb-1">
                            {result.phase && (
                              <Badge className={`text-[10px] h-4 px-1.5 shrink-0 ${phaseColors[result.phase] || ""}`}>
                                {result.phase}
                              </Badge>
                            )}
                            {result.category && <Badge variant="secondary" className="text-[10px] h-4 px-1.5 shrink-0">{result.category}</Badge>}
                            <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0">
                              {(result.score * 100).toFixed(0)}%
                            </Badge>
                          </div>
                          <p className="text-sm break-words">{result.content}</p>
                          {result.created_at && (
                            <p className="text-[10px] text-muted-foreground mt-1">{new Date(result.created_at).toLocaleString()}</p>
                          )}
                        </div>
                        <div className="flex gap-0.5 shrink-0 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleEditStart(result)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={() => setDeletingId(result.id)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="learnings" className="space-y-4">
          {/* Phase filter */}
          <div className="flex flex-wrap gap-1.5">
            <Button variant={selectedPhase === null ? "default" : "outline"} size="sm" className="h-6 text-xs" onClick={() => handlePhaseFilter(null)}>
              All Phases
            </Button>
            {phases.map((phase) => (
              <Button
                key={phase.value}
                variant={selectedPhase === phase.value ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs"
                onClick={() => handlePhaseFilter(phase.value)}
              >
                {phase.label}
              </Button>
            ))}
          </div>

          {/* Scope and Project filter */}
          <div className="flex flex-wrap gap-2 items-center">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Scope:</span>
              <Button
                variant={selectedScopeFilter === null ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs"
                onClick={() => handleScopeFilter(null)}
              >
                All
              </Button>
              <Button
                variant={selectedScopeFilter === "global" ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs"
                onClick={() => handleScopeFilter("global")}
              >
                <Globe className="h-3 w-3 mr-1" />
                Global
              </Button>
              <Button
                variant={selectedScopeFilter === "project" ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs"
                onClick={() => handleScopeFilter("project")}
              >
                <FolderOpen className="h-3 w-3 mr-1" />
                Project
              </Button>
            </div>

            {(selectedScopeFilter === "project" || selectedScopeFilter === null) && projects.length > 0 && (
              <Select
                value={selectedProjectFilter || "all"}
                onValueChange={(v) => handleProjectFilter(v === "all" ? null : v)}
              >
                <SelectTrigger className="h-6 w-40 text-xs">
                  <FolderOpen className="h-3 w-3 mr-1" />
                  <SelectValue placeholder="All projects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Projects</SelectItem>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {learningsError && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive text-sm mb-3">
              <X className="h-4 w-4 shrink-0" />
              <span>{learningsError}</span>
            </div>
          )}

          <ScrollArea className="h-[500px] w-full">
            {isLoadingLearnings ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            ) : sortedLearnings.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <FileText className="h-12 w-12 mb-4 opacity-50" />
                <p>No learnings found</p>
              </div>
            ) : (
              <div className="space-y-2">
                {sortedLearnings.map((learning) => (
                  <Card key={learning.id} className="group">
                    <CardContent className="pt-3 pb-3 px-3">
                      <div className="flex items-start gap-2">
                        {isSelectMode && (
                          <button onClick={() => toggleSelect(learning.id)} className="mt-1 shrink-0">
                            {selectedIds.has(learning.id) ? (
                              <CheckSquare className="h-4 w-4 text-primary" />
                            ) : (
                              <Square className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1 flex-wrap mb-1">
                            {learning.phase && (
                              <Badge className={`text-[10px] h-4 px-1.5 shrink-0 ${phaseColors[learning.phase] || ""}`}>
                                {learning.phase}
                              </Badge>
                            )}
                            {learning.category && <Badge variant="secondary" className="text-[10px] h-4 px-1.5 shrink-0">{learning.category}</Badge>}
                            <Badge variant={learning.outcome === "success" ? "default" : "destructive"} className="text-[10px] h-4 px-1.5 shrink-0">
                              {learning.outcome}
                            </Badge>
                            {learning.scope === "global" && (
                              <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0 bg-blue-500/10 text-blue-600 border-blue-500/30">
                                <Globe className="h-2.5 w-2.5 mr-0.5" />
                                Global
                              </Badge>
                            )}
                            {learning.scope === "project" && (
                              <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0 bg-amber-500/10 text-amber-600 border-amber-500/30 max-w-[120px]">
                                <FolderOpen className="h-2.5 w-2.5 mr-0.5 shrink-0" />
                                <span className="truncate">{learning.project_name || "Project"}</span>
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm break-words">{learning.content}</p>
                          <p className="text-[10px] text-muted-foreground mt-1">
                            {learning.created_at ? new Date(learning.created_at).toLocaleString() : "Date unknown"}
                          </p>
                        </div>
                        <div className="flex gap-0.5 shrink-0 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleEditStart(learning)}>
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={() => setDeletingId(learning.id)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="graph" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Network className="h-4 w-4" />
                Knowledge Graph
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[500px] flex items-center justify-center bg-muted/20 rounded-lg border border-dashed relative overflow-hidden">
                {learnings.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No memories to visualize</p>
                ) : (
                  <div className="relative w-full h-full">
                    {/* Simple graph visualization using positioned nodes */}
                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                      {learnings.slice(0, 20).map((learning, i) => {
                        // Draw connections between related nodes
                        const nextIdx = (i + 1) % Math.min(learnings.length, 20);
                        const cx1 = 50 + (Math.cos(i * (2 * Math.PI / Math.min(learnings.length, 20))) * 35);
                        const cy1 = 50 + (Math.sin(i * (2 * Math.PI / Math.min(learnings.length, 20))) * 35);
                        const cx2 = 50 + (Math.cos(nextIdx * (2 * Math.PI / Math.min(learnings.length, 20))) * 35);
                        const cy2 = 50 + (Math.sin(nextIdx * (2 * Math.PI / Math.min(learnings.length, 20))) * 35);
                        return (
                          <line
                            key={`line-${i}`}
                            x1={`${cx1}%`}
                            y1={`${cy1}%`}
                            x2={`${cx2}%`}
                            y2={`${cy2}%`}
                            stroke="currentColor"
                            strokeOpacity={0.1}
                            strokeWidth={1}
                          />
                        );
                      })}
                    </svg>
                    {learnings.slice(0, 20).map((learning, i) => {
                      const total = Math.min(learnings.length, 20);
                      const angle = i * (2 * Math.PI / total);
                      const radius = 35;
                      const x = 50 + Math.cos(angle) * radius;
                      const y = 50 + Math.sin(angle) * radius;
                      const phaseColor = phaseColors[learning.phase] || "bg-muted text-foreground";

                      return (
                        <div
                          key={learning.id}
                          className={`absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-transform hover:scale-110 ${phaseColor} rounded-full flex items-center justify-center`}
                          style={{
                            left: `${x}%`,
                            top: `${y}%`,
                            width: `${20 + (learning.importance || 3) * 4}px`,
                            height: `${20 + (learning.importance || 3) * 4}px`,
                          }}
                          title={learning.content.slice(0, 100)}
                        >
                          <span className="text-[8px] font-bold">{learning.phase?.[0]?.toUpperCase()}</span>
                        </div>
                      );
                    })}
                    <div className="absolute bottom-3 left-3 flex flex-wrap gap-1.5">
                      {phases.map((p) => (
                        <div key={p.value} className="flex items-center gap-1">
                          <div className={`w-2.5 h-2.5 rounded-full ${phaseColors[p.value]?.split(" ")[0] || "bg-muted"}`} />
                          <span className="text-[9px] text-muted-foreground">{p.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground mt-2 text-center">
                Node size = importance level. Color = PAI phase. Install react-force-graph-2d for interactive physics simulation.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <Dialog open={!!editingId} onOpenChange={() => setEditingId(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Memory</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Content</Label>
              <Textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={4} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Phase</Label>
                <Select value={editPhase} onValueChange={setEditPhase}>
                  <SelectTrigger><SelectValue placeholder="Select phase" /></SelectTrigger>
                  <SelectContent>
                    {phases.map((p) => (<SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Category</Label>
                <Input value={editCategory} onChange={(e) => setEditCategory(e.target.value)} placeholder="e.g., discovery" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Scope</Label>
                <Select value={editScope} onValueChange={setEditScope}>
                  <SelectTrigger><SelectValue placeholder="Select scope" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">
                      <div className="flex items-center gap-1.5">
                        <Globe className="h-3 w-3" />
                        Global
                      </div>
                    </SelectItem>
                    <SelectItem value="project">
                      <div className="flex items-center gap-1.5">
                        <FolderOpen className="h-3 w-3" />
                        Project
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {editScope === "project" && (
                <div className="grid gap-2">
                  <Label>Project</Label>
                  <Select value={editProjectId} onValueChange={setEditProjectId}>
                    <SelectTrigger><SelectValue placeholder="Select project" /></SelectTrigger>
                    <SelectContent>
                      {projects.map((p) => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
            <Button onClick={handleEditSave} disabled={isUpdating}>{isUpdating ? "Saving..." : "Save"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={!!deletingId} onOpenChange={() => setDeletingId(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete Memory?</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">This will permanently delete this memory.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => deletingId && handleDelete(deletingId)}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Memory Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Store New Memory</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Content</Label>
              <Textarea
                value={createContent}
                onChange={(e) => setCreateContent(e.target.value)}
                rows={4}
                placeholder="What should the AI remember?"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Phase (optional)</Label>
                <Select value={createPhase} onValueChange={setCreatePhase}>
                  <SelectTrigger><SelectValue placeholder="Select phase" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {phases.map((p) => (<SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Category (optional)</Label>
                <Input
                  value={createCategory}
                  onChange={(e) => setCreateCategory(e.target.value)}
                  placeholder="e.g., preference, fact"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Scope</Label>
                <Select value={createScope} onValueChange={setCreateScope}>
                  <SelectTrigger><SelectValue placeholder="Select scope" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">
                      <div className="flex items-center gap-1.5">
                        <Globe className="h-3 w-3" />
                        Global - Available everywhere
                      </div>
                    </SelectItem>
                    <SelectItem value="project">
                      <div className="flex items-center gap-1.5">
                        <FolderOpen className="h-3 w-3" />
                        Project - Specific to a project
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {createScope === "project" && (
                <div className="grid gap-2">
                  <Label>Project</Label>
                  <Select value={createProjectId} onValueChange={setCreateProjectId}>
                    <SelectTrigger><SelectValue placeholder="Select project" /></SelectTrigger>
                    <SelectContent>
                      {projects.map((p) => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreateMemory} disabled={isCreating || !createContent.trim()}>
              {isCreating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Storing...</> : "Store Memory"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
