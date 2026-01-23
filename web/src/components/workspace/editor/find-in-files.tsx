"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { workspaceApi, FileSearchResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { X, Search, File } from "lucide-react";

export function FindInFiles() {
  const { token } = useAuthStore();
  const {
    activeProjectId,
    isSearchOpen,
    setSearchOpen,
    searchQuery,
    setSearchQuery,
  } = useWorkspaceStore();

  const [results, setResults] = useState<FileSearchResult[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [isSearching, setIsSearching] = useState(false);

  // Debounced search
  useEffect(() => {
    if (!token || !activeProjectId || searchQuery.length < 3) {
      setResults([]);
      setTotalMatches(0);
      return;
    }

    const timer = setTimeout(() => {
      performSearch();
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, token, activeProjectId]);

  const performSearch = async () => {
    if (!token || !activeProjectId || searchQuery.length < 3) return;

    setIsSearching(true);
    try {
      const data = await workspaceApi.searchFiles(token, activeProjectId, searchQuery);
      setResults(data.matches);
      setTotalMatches(data.total_matches);
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleResultClick = (result: FileSearchResult) => {
    // Open the file at the given line
    const { openFile, setActiveFile, addRecentFile, setMobileActiveTab } = useWorkspaceStore.getState();

    // Fetch and open the file
    if (token && activeProjectId) {
      workspaceApi.getFileContent(token, activeProjectId, result.path).then((fileData) => {
        openFile({
          path: fileData.path,
          content: fileData.content,
          originalContent: fileData.content,
          language: fileData.language,
          isDirty: false,
          is_binary: fileData.is_binary,
        });
        addRecentFile(result.path);
        setMobileActiveTab("editor");
        setSearchOpen(false);
      });
    }
  };

  if (!isSearchOpen) return null;

  // Group results by file
  const groupedResults: Record<string, FileSearchResult[]> = {};
  results.forEach((r) => {
    if (!groupedResults[r.path]) groupedResults[r.path] = [];
    groupedResults[r.path].push(r);
  });

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-start justify-center pt-[10vh]">
      <div className="w-full max-w-2xl bg-card border rounded-lg shadow-xl mx-4">
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search in files..."
            className="flex-1 text-sm bg-transparent outline-none"
            autoFocus
          />
          {isSearching && (
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setSearchOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Results */}
        <ScrollArea className="max-h-[60vh]">
          {searchQuery.length < 3 ? (
            <p className="text-xs text-muted-foreground text-center py-8">
              Type at least 3 characters to search
            </p>
          ) : results.length === 0 && !isSearching ? (
            <p className="text-xs text-muted-foreground text-center py-8">
              No results found
            </p>
          ) : (
            <div className="py-2">
              {totalMatches > 0 && (
                <p className="text-xs text-muted-foreground px-4 py-1">
                  {totalMatches} match{totalMatches !== 1 ? "es" : ""} in{" "}
                  {Object.keys(groupedResults).length} file{Object.keys(groupedResults).length !== 1 ? "s" : ""}
                </p>
              )}
              {Object.entries(groupedResults).map(([filePath, matches]) => (
                <div key={filePath} className="mb-2">
                  <div className="flex items-center gap-1.5 px-4 py-1 text-xs font-medium text-muted-foreground">
                    <File className="h-3 w-3" />
                    <span className="truncate">{filePath}</span>
                    <span className="text-[10px] ml-auto">({matches.length})</span>
                  </div>
                  {matches.map((match, idx) => (
                    <button
                      key={`${match.path}-${match.line_number}-${idx}`}
                      className="w-full text-left px-6 py-1 hover:bg-muted/50 flex items-baseline gap-2"
                      onClick={() => handleResultClick(match)}
                    >
                      <span className="text-[10px] text-muted-foreground shrink-0 w-6 text-right">
                        {match.line_number}
                      </span>
                      <span className="text-xs font-mono truncate">
                        {match.line_content}
                      </span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t text-[10px] text-muted-foreground">
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Esc</kbd> to close
          {" · "}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> to open file
        </div>
      </div>
    </div>
  );
}
