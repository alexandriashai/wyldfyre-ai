"use client";

import { useState, useEffect, useMemo } from "react";
import { useAuthStore } from "@/stores/auth-store";
import {
  usageApi,
  DailySummary,
  UsageHistory,
  BudgetStatus,
  AgentBreakdown,
  ReconciliationResponse,
  SyncStatusResponse,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
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
  BarChart3,
  Download,
  Calendar,
  RefreshCw,
  CheckCircle,
  XCircle,
  Scale,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const CHART_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
];

type TimeRange = "7d" | "30d" | "90d";

export default function UsagePage() {
  const { token } = useAuthStore();
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);
  const [history, setHistory] = useState<UsageHistory | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  const [agentBreakdown, setAgentBreakdown] = useState<AgentBreakdown[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");

  useEffect(() => {
    if (token) fetchAllData();
  }, [token, timeRange]);

  const days = timeRange === "7d" ? 7 : timeRange === "90d" ? 90 : 30;

  const fetchAllData = async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const [daily, hist, budget, agents, recon, status] = await Promise.all([
        usageApi.daily(token),
        usageApi.history(token, days),
        usageApi.budget(token),
        usageApi.byAgent(token, days),
        usageApi.reconciliation(token, days).catch(() => null),
        usageApi.syncStatus(token).catch(() => null),
      ]);
      setDailySummary(daily);
      setHistory(hist);
      setBudgetStatus(budget);
      setAgentBreakdown(agents.breakdown || []);
      setReconciliation(recon);
      setSyncStatus(status);
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSync = async () => {
    if (!token || isSyncing) return;
    setIsSyncing(true);
    try {
      await usageApi.triggerSync(token, 7);
      // Refresh data after sync
      await fetchAllData();
    } catch (error) {
      console.error("Failed to sync:", error);
    } finally {
      setIsSyncing(false);
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
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
    return tokens.toString();
  };

  // Prepare chart data from history
  const chartData = useMemo(() => {
    if (!history?.daily_data) return [];
    return history.daily_data.map((day) => ({
      date: new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      cost: Number(day.cost?.toFixed(4) || 0),
      tokens: day.tokens || 0,
      inputTokens: day.input_tokens || 0,
      outputTokens: day.output_tokens || 0,
      cachedTokens: day.cached_tokens || 0,
      requests: day.requests || 0,
    }));
  }, [history]);

  // Compute 7-day moving average
  const chartDataWithMA = useMemo(() => {
    return chartData.map((item, idx) => {
      const window = chartData.slice(Math.max(0, idx - 6), idx + 1);
      const avg = window.reduce((sum, d) => sum + d.cost, 0) / window.length;
      return { ...item, movingAvg: Number(avg.toFixed(4)) };
    });
  }, [chartData]);

  // Agent donut data
  const agentDonutData = useMemo(() => {
    return agentBreakdown.map((agent) => ({
      name: agent.agent_type,
      value: agent.cost,
    }));
  }, [agentBreakdown]);

  const exportCSV = () => {
    if (!history?.daily_data) return;
    const headers = "Date,Cost,Tokens,Requests\n";
    const rows = history.daily_data.map((d) =>
      `${d.date},${d.cost},${d.tokens},${d.requests}`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `usage-${timeRange}.csv`;
    a.click();
    URL.revokeObjectURL(url);
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Usage Analytics</h1>
          <p className="text-sm text-muted-foreground">Monitor API token usage and costs</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Time range selector */}
          <div className="flex border rounded-md">
            {(["7d", "30d", "90d"] as TimeRange[]).map((range) => (
              <Button
                key={range}
                variant={timeRange === range ? "secondary" : "ghost"}
                size="sm"
                className="h-7 px-2 text-xs rounded-none first:rounded-l-md last:rounded-r-md"
                onClick={() => setTimeRange(range)}
              >
                {range}
              </Button>
            ))}
          </div>
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={exportCSV}>
            <Download className="h-3 w-3 mr-1" />
            CSV
          </Button>
        </div>
      </div>

      {/* Budget Warning */}
      {budgetStatus && budgetStatus.daily_percentage > 80 && (
        <div className="mb-6 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0" />
          <div>
            <p className="font-medium text-yellow-500 text-sm">Budget Warning</p>
            <p className="text-xs text-muted-foreground">
              {budgetStatus.daily_percentage.toFixed(1)}% of daily budget used
            </p>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Today&apos;s Spend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-green-500" />
              <span className="text-xl font-bold">{formatCost(dailySummary?.total_cost || 0)}</span>
            </div>
            {budgetStatus && <Progress value={budgetStatus.daily_percentage} className="mt-2 h-1.5" />}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Projected Daily</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-blue-500" />
              <span className="text-xl font-bold">{formatCost(budgetStatus?.projected_daily || 0)}</span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              {formatCost(budgetStatus?.hourly_rate || 0)}/hr
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Input Tokens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ArrowUpRight className="h-4 w-4 text-purple-500" />
              <span className="text-xl font-bold">{formatTokens(dailySummary?.total_input_tokens || 0)}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Output Tokens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ArrowDownRight className="h-4 w-4 text-orange-500" />
              <span className="text-xl font-bold">{formatTokens(dailySummary?.total_output_tokens || 0)}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid gap-6 md:grid-cols-2 mb-6">
        {/* Cost Trend Line Chart */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Cost Trend ({timeRange})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartDataWithMA}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    interval={Math.floor(chartDataWithMA.length / 7)}
                  />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    formatter={((value: number, name: string) => [
                      `$${value.toFixed(4)}`,
                      name === "movingAvg" ? "7-day avg" : "Daily cost",
                    ]) as any}
                  />
                  <Line
                    type="monotone"
                    dataKey="cost"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="movingAvg"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Token Breakdown Stacked Bar */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Token Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData.slice(-14)}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={1} />
                  <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => formatTokens(v)} />
                  <Tooltip formatter={((value: number) => formatTokens(value)) as any} />
                  <Bar dataKey="inputTokens" stackId="tokens" fill="#8b5cf6" name="Input" />
                  <Bar dataKey="outputTokens" stackId="tokens" fill="#f59e0b" name="Output" />
                  <Bar dataKey="cachedTokens" stackId="tokens" fill="#10b981" name="Cached" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Agent Cost Donut */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              Cost by Agent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              {agentDonutData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={agentDonutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                      labelLine={false}
                    >
                      {agentDonutData.map((_, index) => (
                        <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={((value: number) => formatCost(value)) as any} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  No data
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="alerts" className="space-y-4">
        <TabsList>
          <TabsTrigger value="alerts">Budget Alerts</TabsTrigger>
          <TabsTrigger value="history">History Table</TabsTrigger>
          <TabsTrigger value="reconciliation">Local vs. Provider</TabsTrigger>
        </TabsList>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <AlertTriangle className="h-4 w-4" />
                Budget Alerts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {!budgetStatus?.alerts?.length ? (
                  <p className="text-muted-foreground text-center py-4 text-sm">
                    No budget alerts configured. Configure alerts in Settings.
                  </p>
                ) : (
                  budgetStatus.alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className={`p-3 rounded-lg border ${
                        alert.is_exceeded
                          ? "border-red-500/50 bg-red-500/10"
                          : "border-muted"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{alert.name}</span>
                          <Badge variant={alert.is_active ? "default" : "secondary"} className="text-[10px] h-4">
                            {alert.is_active ? "Active" : "Off"}
                          </Badge>
                          {alert.is_exceeded && <Badge variant="destructive" className="text-[10px] h-4">Exceeded</Badge>}
                        </div>
                        <span className="text-xs text-muted-foreground">{alert.period}</span>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-xs">
                          <span>{formatCost(alert.current_spend)} / {formatCost(alert.threshold_amount)}</span>
                          <span>{alert.percentage_used.toFixed(1)}%</span>
                        </div>
                        <Progress
                          value={Math.min(alert.percentage_used, 100)}
                          className={`h-1.5 ${alert.is_exceeded ? "[&>div]:bg-red-500" : ""}`}
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Daily History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-[400px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card">
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium text-muted-foreground">Date</th>
                      <th className="text-right py-2 font-medium text-muted-foreground">Cost</th>
                      <th className="text-right py-2 font-medium text-muted-foreground">Tokens</th>
                      <th className="text-right py-2 font-medium text-muted-foreground">Requests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!history?.daily_data?.length ? (
                      <tr>
                        <td colSpan={4} className="text-center py-8 text-muted-foreground">No data</td>
                      </tr>
                    ) : (
                      history.daily_data.slice().reverse().map((day) => (
                        <tr key={day.date} className="border-b border-muted/30 hover:bg-muted/20">
                          <td className="py-1.5">
                            {new Date(day.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                          </td>
                          <td className="text-right font-medium">{formatCost(day.cost)}</td>
                          <td className="text-right">{formatTokens(day.tokens)}</td>
                          <td className="text-right">{day.requests}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {history && (
                <div className="mt-4 pt-4 border-t grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-lg font-bold">{formatCost(history.total_cost)}</p>
                    <p className="text-xs text-muted-foreground">Total Cost</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold">{formatTokens(history.total_tokens)}</p>
                    <p className="text-xs text-muted-foreground">Total Tokens</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold">{history.total_requests}</p>
                    <p className="text-xs text-muted-foreground">Total Requests</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reconciliation" className="space-y-4">
          {/* Sync Status Cards */}
          <div className="grid gap-4 grid-cols-1 md:grid-cols-3 mb-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">Anthropic</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  {syncStatus?.anthropic?.configured ? (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-sm font-medium">
                    {syncStatus?.anthropic?.configured ? "Configured" : "Not Configured"}
                  </span>
                </div>
                {syncStatus?.anthropic?.last_sync && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Last sync: {new Date(syncStatus.anthropic.last_sync.completed_at).toLocaleString()}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">OpenAI</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  {syncStatus?.openai?.configured ? (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-sm font-medium">
                    {syncStatus?.openai?.configured ? "Configured" : "Not Configured"}
                  </span>
                </div>
                {syncStatus?.openai?.last_sync && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Last sync: {new Date(syncStatus.openai.last_sync.completed_at).toLocaleString()}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium text-muted-foreground">Sync Now</CardTitle>
              </CardHeader>
              <CardContent>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full h-8"
                  onClick={handleSync}
                  disabled={isSyncing || (!syncStatus?.anthropic?.configured && !syncStatus?.openai?.configured)}
                >
                  {isSyncing ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3 mr-1" />
                  )}
                  {isSyncing ? "Syncing..." : "Sync Provider Data"}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Summary Cards */}
          {reconciliation && (
            <div className="grid gap-4 grid-cols-1 md:grid-cols-3 mb-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Local Estimate</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-blue-500" />
                    <span className="text-xl font-bold">{formatCost(reconciliation.local_total)}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Provider Reported</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-green-500" />
                    <span className="text-xl font-bold">{formatCost(reconciliation.provider_total)}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Difference</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Scale className="h-4 w-4 text-orange-500" />
                    <span className={`text-xl font-bold ${
                      reconciliation.total_difference > 0 ? "text-red-500" :
                      reconciliation.total_difference < 0 ? "text-green-500" : ""
                    }`}>
                      {reconciliation.total_difference > 0 ? "+" : ""}
                      {formatCost(reconciliation.total_difference)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({reconciliation.total_difference_percentage > 0 ? "+" : ""}
                      {reconciliation.total_difference_percentage.toFixed(1)}%)
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Scale className="h-4 w-4" />
                Cost Comparison by Model
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!reconciliation?.by_model?.length ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  <p>No reconciliation data available.</p>
                  <p className="text-xs mt-2">
                    Configure admin API keys and sync to see provider-reported costs.
                  </p>
                </div>
              ) : (
                <div className="max-h-[400px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card">
                      <tr className="border-b">
                        <th className="text-left py-2 font-medium text-muted-foreground">Model</th>
                        <th className="text-right py-2 font-medium text-muted-foreground">Local</th>
                        <th className="text-right py-2 font-medium text-muted-foreground">Provider</th>
                        <th className="text-right py-2 font-medium text-muted-foreground">Diff</th>
                        <th className="text-right py-2 font-medium text-muted-foreground">%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reconciliation.by_model.map((row) => (
                        <tr key={row.model} className="border-b border-muted/30 hover:bg-muted/20">
                          <td className="py-1.5 font-medium">{row.model}</td>
                          <td className="text-right">{formatCost(row.local_cost)}</td>
                          <td className="text-right">{formatCost(row.provider_cost)}</td>
                          <td className={`text-right ${
                            row.difference > 0 ? "text-red-500" :
                            row.difference < 0 ? "text-green-500" : ""
                          }`}>
                            {row.difference > 0 ? "+" : ""}
                            {formatCost(row.difference)}
                          </td>
                          <td className={`text-right ${
                            row.difference_percentage > 5 ? "text-red-500" :
                            row.difference_percentage < -5 ? "text-green-500" : ""
                          }`}>
                            {row.difference_percentage > 0 ? "+" : ""}
                            {row.difference_percentage.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
