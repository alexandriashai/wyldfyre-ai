"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { memoryApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Search, Brain, Database, FileText, Loader2 } from "lucide-react";

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
  content: string;
  outcome: string;
  created_at: string;
}

interface MemoryStats {
  total_memories: number;
  by_tier: Record<string, number>;
  by_agent: Record<string, number>;
}

// Phase values must match backend PAIPhase enum (lowercase)
const phases = [
  { value: "observe", label: "OBSERVE" },
  { value: "think", label: "THINK" },
  { value: "plan", label: "PLAN" },
  { value: "build", label: "BUILD" },
  { value: "execute", label: "EXECUTE" },
  { value: "verify", label: "VERIFY" },
  { value: "learn", label: "LEARN" },
];

export default function MemoryPage() {
  const { token } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingLearnings, setIsLoadingLearnings] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(true);

  useEffect(() => {
    if (token) {
      fetchStats();
      fetchLearnings();
    }
  }, [token]);

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

  const fetchLearnings = async (phase?: string) => {
    if (!token) return;
    setIsLoadingLearnings(true);
    try {
      const response = await memoryApi.learnings(token, phase || undefined);
      setLearnings(response.learnings);
    } catch (error) {
      console.error("Failed to fetch learnings:", error);
    } finally {
      setIsLoadingLearnings(false);
    }
  };

  const handleSearch = async () => {
    if (!token || !searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const response = await memoryApi.search(token, searchQuery.trim(), 20);
      setSearchResults(response.results);
    } catch (error) {
      console.error("Failed to search memory:", error);
    } finally {
      setIsSearching(false);
    }
  };

  const handlePhaseFilter = (phase: string | null) => {
    setSelectedPhase(phase);
    fetchLearnings(phase || undefined);
  };

  return (
    <div className="p-4 sm:p-6 h-full overflow-y-auto">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold">Memory</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Browse and search the AI memory system
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Memories
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              <span className="text-2xl font-bold">
                {isLoadingStats ? "-" : stats?.total_memories || 0}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Hot Tier
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-red-500" />
              <span className="text-2xl font-bold">
                {isLoadingStats ? "-" : stats?.by_tier?.hot || 0}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Warm Tier
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-yellow-500" />
              <span className="text-2xl font-bold">
                {isLoadingStats ? "-" : stats?.by_tier?.warm || 0}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cold Tier
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">
                {isLoadingStats ? "-" : stats?.by_tier?.cold || 0}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="search" className="space-y-4">
        <TabsList>
          <TabsTrigger value="search">Semantic Search</TabsTrigger>
          <TabsTrigger value="learnings">Learnings</TabsTrigger>
        </TabsList>

        <TabsContent value="search" className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={isSearching}>
              {isSearching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
            </Button>
          </div>

          <ScrollArea className="h-[500px]">
            {searchResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <Search className="h-12 w-12 mb-4 opacity-50" />
                <p>Search for memories using natural language</p>
              </div>
            ) : (
              <div className="space-y-4">
                {searchResults.map((result) => (
                  <Card key={result.id}>
                    <CardContent className="pt-4">
                      <div className="flex justify-between items-start mb-2">
                        <Badge variant="outline">
                          Score: {(result.score * 100).toFixed(1)}%
                        </Badge>
                      </div>
                      <p className="text-sm">{result.content}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="learnings" className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant={selectedPhase === null ? "default" : "outline"}
              size="sm"
              onClick={() => handlePhaseFilter(null)}
            >
              All
            </Button>
            {phases.map((phase) => (
              <Button
                key={phase.value}
                variant={selectedPhase === phase.value ? "default" : "outline"}
                size="sm"
                onClick={() => handlePhaseFilter(phase.value)}
              >
                {phase.label}
              </Button>
            ))}
          </div>

          <ScrollArea className="h-[500px]">
            {isLoadingLearnings ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            ) : learnings.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <FileText className="h-12 w-12 mb-4 opacity-50" />
                <p>No learnings found</p>
              </div>
            ) : (
              <div className="space-y-4">
                {learnings.map((learning) => (
                  <Card key={learning.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <Badge>{learning.phase}</Badge>
                        <Badge
                          variant={learning.outcome === "success" ? "default" : "destructive"}
                        >
                          {learning.outcome}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm">{learning.content}</p>
                      <p className="text-xs text-muted-foreground mt-2">
                        {learning.created_at ? new Date(learning.created_at).toLocaleString() : "Date unknown"}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
