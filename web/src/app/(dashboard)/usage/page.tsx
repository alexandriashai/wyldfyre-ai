"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import {
  usageApi,
  DailySummary,
  UsageHistory,
  BudgetStatus,
  AgentBreakdown,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  DollarSign,
  TrendingUp,
  Cpu,
  AlertTriangle,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  BarChart3,
} from "lucide-react";

export default function UsagePage() {
  const { token } = useAuthStore();
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);
  const [history, setHistory] = useState<UsageHistory | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  const [agentBreakdown, setAgentBreakdown] = useState<AgentBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (token) {
      fetchAllData();
    }
  }, [token]);

  const fetchAllData = async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const [daily, hist, budget, agents] = await Promise.all([
        usageApi.daily(token),
        usageApi.history(token, 30),
        usageApi.budget(token),
        usageApi.byAgent(token, 30),
      ]);
      setDailySummary(daily);
      setHistory(hist);
      setBudgetStatus(budget);
      setAgentBreakdown(agents.breakdown);
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatCost = (cost: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(cost);
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`;
    }
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold">Usage Analytics</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Monitor API token usage and costs
        </p>
      </div>

      {/* Budget Status Alert */}
      {budgetStatus && budgetStatus.daily_percentage > 80 && (
        <div className="mb-6 p-3 sm:p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0" />
          <div>
            <p className="font-medium text-yellow-500 text-sm sm:text-base">Budget Warning</p>
            <p className="text-xs sm:text-sm text-muted-foreground">
              You&apos;ve used {budgetStatus.daily_percentage.toFixed(1)}% of your daily budget
            </p>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Today&apos;s Spend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-green-500" />
              <span className="text-2xl font-bold">
                {formatCost(dailySummary?.total_cost || 0)}
              </span>
            </div>
            {budgetStatus && (
              <Progress
                value={budgetStatus.daily_percentage}
                className="mt-2 h-2"
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Hourly Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">
                {formatCost(budgetStatus?.hourly_rate || 0)}/hr
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Projected: {formatCost(budgetStatus?.projected_daily || 0)}/day
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Input Tokens
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ArrowUpRight className="h-5 w-5 text-purple-500" />
              <span className="text-2xl font-bold">
                {formatTokens(dailySummary?.total_input_tokens || 0)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Output Tokens
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ArrowDownRight className="h-5 w-5 text-orange-500" />
              <span className="text-2xl font-bold">
                {formatTokens(dailySummary?.total_output_tokens || 0)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="breakdown" className="space-y-4">
        <TabsList>
          <TabsTrigger value="breakdown">Breakdown</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="alerts">Budget Alerts</TabsTrigger>
        </TabsList>

        <TabsContent value="breakdown" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Cost by Agent */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  Cost by Agent (30 days)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {agentBreakdown.length === 0 ? (
                    <p className="text-muted-foreground text-center py-4">
                      No usage data available
                    </p>
                  ) : (
                    agentBreakdown.map((agent) => (
                      <div key={agent.agent_type} className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="font-medium capitalize">
                            {agent.agent_type}
                          </span>
                          <span className="text-muted-foreground">
                            {formatCost(agent.cost)} ({agent.percentage.toFixed(1)}%)
                          </span>
                        </div>
                        <Progress value={agent.percentage} className="h-2" />
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Cost by Model */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5" />
                  Cost by Model (Today)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {!dailySummary?.breakdown_by_model?.length ? (
                    <p className="text-muted-foreground text-center py-4">
                      No usage data available
                    </p>
                  ) : (
                    dailySummary.breakdown_by_model.map((model) => (
                      <div key={model.model} className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="font-medium">{model.model}</span>
                          <span className="text-muted-foreground">
                            {formatCost(model.cost)} ({model.percentage.toFixed(1)}%)
                          </span>
                        </div>
                        <Progress value={model.percentage} className="h-2" />
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Today's Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Today&apos;s Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">
                    {dailySummary?.request_count || 0}
                  </p>
                  <p className="text-sm text-muted-foreground">API Requests</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">
                    {formatTokens(dailySummary?.total_input_tokens || 0)}
                  </p>
                  <p className="text-sm text-muted-foreground">Input Tokens</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">
                    {formatTokens(dailySummary?.total_output_tokens || 0)}
                  </p>
                  <p className="text-sm text-muted-foreground">Output Tokens</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">
                    {formatTokens(dailySummary?.total_cached_tokens || 0)}
                  </p>
                  <p className="text-sm text-muted-foreground">Cached Tokens</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">
                    {formatCost(dailySummary?.total_cost || 0)}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Cost</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                30-Day Usage History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-2">
                  <div className="grid grid-cols-4 gap-4 text-sm font-medium text-muted-foreground border-b pb-2">
                    <span>Date</span>
                    <span className="text-right">Cost</span>
                    <span className="text-right">Tokens</span>
                    <span className="text-right">Requests</span>
                  </div>
                  {!history?.daily_data?.length ? (
                    <p className="text-muted-foreground text-center py-8">
                      No historical data available
                    </p>
                  ) : (
                    history.daily_data
                      .slice()
                      .reverse()
                      .map((day) => (
                        <div
                          key={day.date}
                          className="grid grid-cols-4 gap-4 text-sm py-2 border-b border-muted/30"
                        >
                          <span>
                            {new Date(day.date).toLocaleDateString("en-US", {
                              weekday: "short",
                              month: "short",
                              day: "numeric",
                            })}
                          </span>
                          <span className="text-right font-medium">
                            {formatCost(day.cost)}
                          </span>
                          <span className="text-right">
                            {formatTokens(day.tokens)}
                          </span>
                          <span className="text-right">{day.requests}</span>
                        </div>
                      ))
                  )}
                </div>
              </ScrollArea>
              {history && (
                <div className="mt-4 pt-4 border-t">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-lg font-bold">
                        {formatCost(history.total_cost)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Total Cost (30d)
                      </p>
                    </div>
                    <div>
                      <p className="text-lg font-bold">
                        {formatTokens(history.total_tokens)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Total Tokens (30d)
                      </p>
                    </div>
                    <div>
                      <p className="text-lg font-bold">{history.total_requests}</p>
                      <p className="text-sm text-muted-foreground">
                        Total Requests (30d)
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Budget Alerts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {!budgetStatus?.alerts?.length ? (
                  <p className="text-muted-foreground text-center py-4">
                    No budget alerts configured
                  </p>
                ) : (
                  budgetStatus.alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className={`p-4 rounded-lg border ${
                        alert.is_exceeded
                          ? "border-red-500/50 bg-red-500/10"
                          : "border-muted"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{alert.name}</span>
                          <Badge
                            variant={alert.is_active ? "default" : "secondary"}
                          >
                            {alert.is_active ? "Active" : "Inactive"}
                          </Badge>
                          {alert.is_exceeded && (
                            <Badge variant="destructive">Exceeded</Badge>
                          )}
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {alert.period}
                        </span>
                      </div>
                      {alert.description && (
                        <p className="text-sm text-muted-foreground mb-2">
                          {alert.description}
                        </p>
                      )}
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>
                            {formatCost(alert.current_spend)} / {formatCost(alert.threshold_amount)}
                          </span>
                          <span>{alert.percentage_used.toFixed(1)}%</span>
                        </div>
                        <Progress
                          value={Math.min(alert.percentage_used, 100)}
                          className={`h-2 ${
                            alert.is_exceeded ? "[&>div]:bg-red-500" : ""
                          }`}
                        />
                      </div>
                      {alert.trigger_count > 0 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Triggered {alert.trigger_count} times
                          {alert.last_triggered_at &&
                            ` - Last: ${new Date(alert.last_triggered_at).toLocaleString()}`}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
