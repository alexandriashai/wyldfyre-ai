"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GitCommit, History } from "lucide-react";
import { CommitPanel } from "./commit-panel";
import { HistoryPanel } from "./history-panel";

export function GitPanel() {
  const [activeTab, setActiveTab] = useState("commit");

  return (
    <div className="flex flex-col h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-9 px-2 shrink-0">
          <TabsTrigger
            value="commit"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <GitCommit className="h-3.5 w-3.5" />
            Commit
          </TabsTrigger>
          <TabsTrigger
            value="history"
            className="gap-1.5 text-xs data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full"
          >
            <History className="h-3.5 w-3.5" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="commit" className="flex-1 m-0 min-h-0">
          <CommitPanel />
        </TabsContent>

        <TabsContent value="history" className="flex-1 m-0 min-h-0">
          <HistoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
