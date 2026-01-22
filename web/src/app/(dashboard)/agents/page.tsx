"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useAgentStore } from "@/stores/agent-store";
import { AgentCard } from "@/components/agents/agent-card";

export default function AgentsPage() {
  const { token } = useAuthStore();
  const { agents, restartAgent, isLoading } = useAgentStore();
  const [restartingAgent, setRestartingAgent] = useState<string | null>(null);

  const handleRestart = async (name: string) => {
    if (!token) return;
    setRestartingAgent(name);
    try {
      await restartAgent(token, name);
    } finally {
      setRestartingAgent(null);
    }
  };

  return (
    <div className="p-4 sm:p-6">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold">Agents</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Monitor and manage your AI agents
        </p>
      </div>

      {isLoading && agents.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.name}
              agent={agent}
              onRestart={() => handleRestart(agent.name)}
              isRestarting={restartingAgent === agent.name}
            />
          ))}
        </div>
      )}
    </div>
  );
}
