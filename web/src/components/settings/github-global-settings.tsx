"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { githubApi, GitHubGlobalSettings, GitHubTestResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Github,
  Loader2,
  CheckCircle,
  AlertCircle,
  Key,
  RefreshCw,
  Eye,
  EyeOff,
} from "lucide-react";

export function GitHubGlobalSettingsCard() {
  const { token } = useAuthStore();
  const [settings, setSettings] = useState<GitHubGlobalSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<GitHubTestResult | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form state
  const [enabled, setEnabled] = useState(true);
  const [newPat, setNewPat] = useState("");
  const [showPat, setShowPat] = useState(false);

  // Fetch settings on mount
  useEffect(() => {
    if (!token) return;

    setIsLoading(true);
    githubApi.getGlobalSettings(token)
      .then((data) => {
        setSettings(data);
        setEnabled(data.enabled);
      })
      .catch(() => {
        setMessage({ type: "error", text: "Failed to load GitHub settings" });
      })
      .finally(() => setIsLoading(false));
  }, [token]);

  const handleSave = async () => {
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      const data = await githubApi.updateGlobalSettings(token, {
        enabled,
        pat: newPat || undefined,
      });
      setSettings(data);
      setNewPat("");
      setMessage({ type: "success", text: "GitHub settings saved" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to save settings" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearPat = async () => {
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      const data = await githubApi.updateGlobalSettings(token, {
        clear_pat: true,
      });
      setSettings(data);
      setTestResult(null);
      setMessage({ type: "success", text: "Admin PAT cleared, using .env PAT" });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to clear PAT" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    if (!token) return;

    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await githubApi.testGlobalPat(token);
      setTestResult(result);
    } catch (error) {
      setTestResult({
        success: false,
        username: null,
        scopes: null,
        error: error instanceof Error ? error.message : "Test failed",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const getPatSourceBadge = () => {
    if (!settings?.pat_configured) {
      return <Badge variant="outline" className="text-yellow-500 border-yellow-500/30">Not Configured</Badge>;
    }
    if (settings.pat_source === "env") {
      return <Badge variant="outline" className="text-green-500 border-green-500/30">Using .env PAT</Badge>;
    }
    if (settings.pat_source === "admin") {
      return <Badge variant="outline" className="text-blue-500 border-blue-500/30">Admin Override</Badge>;
    }
    return null;
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Github className="h-5 w-5" />
            <CardTitle>GitHub Integration</CardTitle>
          </div>
          {getPatSourceBadge()}
        </div>
        <CardDescription>
          Configure GitHub Personal Access Token for authenticated operations
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {message && (
          <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
            message.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
          }`}>
            {message.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {message.text}
          </div>
        )}

        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Enable GitHub Integration</Label>
            <p className="text-sm text-muted-foreground">
              Allow GitHub operations (push, pull, PRs)
            </p>
          </div>
          <Switch checked={enabled} onCheckedChange={setEnabled} />
        </div>

        <Separator />

        {/* PAT Status */}
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Current PAT Status</Label>
            <div className="rounded-lg border p-3 bg-muted/50">
              {settings?.pat_configured ? (
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    {settings.pat_source === "env" ? "Using PAT from .env file" : "Using admin-configured PAT"}
                  </p>
                  {settings.pat_last_updated && (
                    <p className="text-xs text-muted-foreground">
                      Last updated: {new Date(settings.pat_last_updated).toLocaleString()}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No PAT configured. Add GITHUB_PAT to .env or configure below.
                </p>
              )}
            </div>
          </div>

          {/* Test Connection */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={isTesting || !settings?.pat_configured}
            >
              {isTesting ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Testing...</>
              ) : (
                <><RefreshCw className="h-3.5 w-3.5 mr-1.5" />Test Connection</>
              )}
            </Button>

            {testResult && (
              <div className={`flex items-center gap-1.5 text-sm ${
                testResult.success ? "text-green-500" : "text-destructive"
              }`}>
                {testResult.success ? (
                  <><CheckCircle className="h-4 w-4" />Connected as {testResult.username}</>
                ) : (
                  <><AlertCircle className="h-4 w-4" />{testResult.error}</>
                )}
              </div>
            )}
          </div>

          {testResult?.success && testResult.scopes && (
            <div className="flex flex-wrap gap-1.5">
              <span className="text-xs text-muted-foreground">Scopes:</span>
              {testResult.scopes.map((scope) => (
                <Badge key={scope} variant="secondary" className="text-xs">
                  {scope}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* Override PAT */}
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-pat">Override PAT (Optional)</Label>
            <p className="text-xs text-muted-foreground">
              Set a different PAT that overrides the .env value
            </p>
          </div>

          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                id="new-pat"
                type={showPat ? "text" : "password"}
                value={newPat}
                onChange={(e) => setNewPat(e.target.value)}
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPat(!showPat)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPat ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</>
              ) : (
                <><Key className="h-4 w-4 mr-2" />Save Settings</>
              )}
            </Button>

            {settings?.pat_source === "admin" && (
              <Button variant="outline" onClick={handleClearPat} disabled={isSaving}>
                Use .env Default
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
