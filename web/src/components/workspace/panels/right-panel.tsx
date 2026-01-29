"use client";

import { useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { PreviewPanel } from "../preview/preview-panel";
import { BrowserPanel } from "../browser/browser-panel";
import { PRPanel } from "./pr-panel";
import { GitPanel } from "./git-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Globe, GitPullRequest, GitBranch, Monitor } from "lucide-react";

export function RightPanel() {
  const { activeProjectId, gitStatus } = useWorkspaceStore();
  const [activeTab, setActiveTab] = useState("preview");

  // Calculate total changes for badge
  const totalChanges = (gitStatus?.staged?.length || 0) +
    (gitStatus?.modified?.length || 0) +
    (gitStatus?.untracked?.length || 0);

  return (
    <div className="flex flex-col h-full bg-card">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-9 px-2 shrink-0">
          <TabsTrigger
            value="preview"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Globe className="h-3.5 w-3.5" />
            Preview
          </TabsTrigger>
          <TabsTrigger
            value="browser"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <Monitor className="h-3.5 w-3.5" />
            Debug
          </TabsTrigger>
          <TabsTrigger
            value="git"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <GitBranch className="h-3.5 w-3.5" />
            Git
            {totalChanges > 0 && (
              <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">
                {totalChanges}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="prs"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <GitPullRequest className="h-3.5 w-3.5" />
            PRs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="flex-1 m-0 min-h-0">
          <PreviewPanel />
        </TabsContent>

        <TabsContent value="browser" className="flex-1 m-0 min-h-0">
          {activeProjectId ? (
            <BrowserPanel />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a project to use browser debug
            </div>
          )}
        </TabsContent>

        <TabsContent value="git" className="flex-1 m-0 min-h-0">
          {activeProjectId ? (
            <GitPanel />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a project to manage git
            </div>
          )}
        </TabsContent>

        <TabsContent value="prs" className="flex-1 m-0 min-h-0">
          {activeProjectId ? (
            <PRPanel projectId={activeProjectId} />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a project to view PRs
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
