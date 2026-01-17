"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useAgentStore } from "@/stores/agent-store";
import { cn, getStatusColor, getStatusBgColor, getAgentColor } from "@/lib/utils";
import { AgentLogs } from "@/components/agents/agent-logs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowLeft, Bot, RefreshCw } from "lucide-react";

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.name as string;

  const { token } = useAuthStore();
  const { selectedAgent, agentLogs, fetchAgent, fetchAgentLogs, restartAgent, isLoading } = useAgentStore();
  const [isRestarting, setIsRestarting] = useState(false);

  useEffect(() => {
    if (token && agentName) {
      fetchAgent(token, agentName);
      fetchAgentLogs(token, agentName);
    }
  }, [token, agentName, fetchAgent, fetchAgentLogs]);

  const handleRestart = async () => {
    if (!token) return;
    setIsRestarting(true);
    try {
      await restartAgent(token, agentName);
    } finally {
      setIsRestarting(false);
    }
  };

  const handleRefreshLogs = () => {
    if (token) {
      fetchAgentLogs(token, agentName);
    }
  };

  if (isLoading && !selectedAgent) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!selectedAgent) {
    return (
      <div className="p-6">
        <Button variant="ghost" onClick={() => router.push("/agents")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Agents
        </Button>
        <div className="mt-8 text-center text-muted-foreground">
          Agent not found
        </div>
      </div>
    );
  }

  const displayName = selectedAgent.name.replace("_", " ");

  return (
    <div className="p-6">
      <Button variant="ghost" className="mb-4" onClick={() => router.push("/agents")}>
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Agents
      </Button>

      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className={cn("rounded-xl p-3", `${getAgentColor(selectedAgent.name).replace("text-", "bg-")}/10`)}>
            <Bot className={cn("h-8 w-8", getAgentColor(selectedAgent.name))} />
          </div>
          <div>
            <h1 className="text-2xl font-bold capitalize">{displayName}</h1>
            <div className="flex items-center gap-2 mt-1">
              <div
                className={cn(
                  "h-2 w-2 rounded-full",
                  getStatusBgColor(selectedAgent.status)
                )}
              />
              <span className={cn("text-sm capitalize", getStatusColor(selectedAgent.status))}>
                {selectedAgent.status}
              </span>
              {selectedAgent.permission_level !== undefined && (
                <span className="text-sm text-muted-foreground">
                  | Permission Level: {selectedAgent.permission_level}
                </span>
              )}
            </div>
          </div>
        </div>

        <Button onClick={handleRestart} disabled={isRestarting}>
          <RefreshCw className={cn("h-4 w-4 mr-2", isRestarting && "animate-spin")} />
          Restart Agent
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3 mb-6">
        {selectedAgent.metrics && Object.entries(selectedAgent.metrics).map(([key, value]) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground capitalize">
                {key.replace("_", " ")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedAgent.capabilities && selectedAgent.capabilities.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Capabilities</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {selectedAgent.capabilities.map((capability) => (
                <span
                  key={capability}
                  className="rounded-full bg-muted px-3 py-1 text-sm"
                >
                  {capability}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="logs">
        <div className="flex items-center justify-between mb-4">
          <TabsList>
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="tasks">Recent Tasks</TabsTrigger>
          </TabsList>
          <Button variant="outline" size="sm" onClick={handleRefreshLogs}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        <TabsContent value="logs">
          <AgentLogs logs={agentLogs} isLoading={isLoading} />
        </TabsContent>

        <TabsContent value="tasks">
          <div className="rounded-md border p-8 text-center text-muted-foreground">
            Recent tasks will be displayed here
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
