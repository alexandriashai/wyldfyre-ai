"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { usePreferencesStore, ACCENT_COLORS } from "@/stores/preferences-store";
import { formatShortcut } from "@/hooks/useKeyboardShortcuts";
import { settingsApi, notificationsApi, conversationsApi, memoryApi } from "@/lib/api";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  User,
  Key,
  Bell,
  Shield,
  Loader2,
  CheckCircle,
  AlertCircle,
  BellRing,
  BellOff,
  Palette,
  Keyboard,
  Bot,
  Database,
  Accessibility,
  Sun,
  Moon,
  Monitor,
  RotateCcw,
  Download,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NotificationSettings {
  task_completions: boolean;
  agent_errors: boolean;
  ssl_expiration: boolean;
  system_updates: boolean;
}

export default function SettingsPage() {
  const { user, token, fetchUser } = useAuthStore();
  const [displayName, setDisplayName] = useState(user?.display_name || "");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Password state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Notifications state
  const [notifications, setNotifications] = useState<NotificationSettings>({
    task_completions: true,
    agent_errors: true,
    ssl_expiration: true,
    system_updates: false,
  });
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

  // Push notifications
  const {
    permission,
    isSupported,
    isSubscribed,
    isLoading: isPushLoading,
    error: pushError,
    subscribe: subscribePush,
    unsubscribe: unsubscribePush,
  } = usePushNotifications();
  const [pushMessage, setPushMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Shortcut rebinding state
  const [rebindingId, setRebindingId] = useState<string | null>(null);

  // Export state
  const [isExporting, setIsExporting] = useState<string | null>(null);

  // Preferences
  const {
    theme,
    accentColor,
    fontSize,
    compactMode,
    defaultModelTier,
    maxIterations,
    autoApprovePlans,
    preferredAgent,
    reducedMotion,
    highContrast,
    screenReaderHints,
    shortcuts,
    setTheme,
    setAccentColor,
    setFontSize,
    setCompactMode,
    setDefaultModelTier,
    setMaxIterations,
    setAutoApprovePlans,
    setPreferredAgent,
    setReducedMotion,
    setHighContrast,
    setScreenReaderHints,
    updateShortcut,
    resetShortcuts,
    resetAll,
  } = usePreferencesStore();

  // Update display name when user changes
  useEffect(() => {
    if (user?.display_name) {
      setDisplayName(user.display_name);
    }
  }, [user?.display_name]);

  // Fetch notification settings on mount
  useEffect(() => {
    if (token) {
      settingsApi.getNotifications(token)
        .then(setNotifications)
        .catch(() => {});
    }
  }, [token]);

  // Keyboard shortcut rebinding listener
  useEffect(() => {
    if (!rebindingId) return;

    const handler = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      // Ignore lone modifier keys
      if (["Control", "Shift", "Alt", "Meta"].includes(e.key)) return;

      updateShortcut(rebindingId, {
        key: e.key,
        ctrlKey: e.ctrlKey || e.metaKey,
        shiftKey: e.shiftKey,
        altKey: e.altKey,
      });
      setRebindingId(null);
    };

    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [rebindingId, updateShortcut]);

  const handleSaveProfile = async () => {
    if (!token) return;
    setIsSavingProfile(true);
    setProfileMessage(null);

    try {
      await settingsApi.updateProfile(token, { display_name: displayName });
      await fetchUser();
      setProfileMessage({ type: "success", text: "Profile updated successfully" });
    } catch (error) {
      setProfileMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to update profile" });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleUpdatePassword = async () => {
    if (!token) return;

    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: "error", text: "Passwords do not match" });
      return;
    }

    if (newPassword.length < 8) {
      setPasswordMessage({ type: "error", text: "Password must be at least 8 characters" });
      return;
    }

    setIsSavingPassword(true);
    setPasswordMessage(null);

    try {
      await settingsApi.updatePassword(token, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage({ type: "success", text: "Password updated successfully" });
    } catch (error) {
      setPasswordMessage({ type: "error", text: error instanceof Error ? error.message : "Failed to update password" });
    } finally {
      setIsSavingPassword(false);
    }
  };

  const handleNotificationChange = async (key: keyof NotificationSettings, value: boolean) => {
    if (!token) return;

    const newSettings = { ...notifications, [key]: value };
    setNotifications(newSettings);
    setIsSavingNotifications(true);

    try {
      await settingsApi.updateNotifications(token, { [key]: value });
    } catch (error) {
      setNotifications(notifications);
    } finally {
      setIsSavingNotifications(false);
    }
  };

  const handlePushSubscribe = async () => {
    if (!token) return;
    setPushMessage(null);

    try {
      const subscriptionData = await subscribePush();
      if (subscriptionData) {
        await notificationsApi.subscribe(token, subscriptionData);
        setPushMessage({ type: "success", text: "Push notifications enabled" });
      }
    } catch (error) {
      setPushMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to enable push notifications"
      });
    }
  };

  const handlePushUnsubscribe = async () => {
    if (!token) return;
    setPushMessage(null);

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await notificationsApi.unsubscribe(token, subscription.endpoint);
      }

      await unsubscribePush();
      setPushMessage({ type: "success", text: "Push notifications disabled" });
    } catch (error) {
      setPushMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to disable push notifications"
      });
    }
  };

  const handleExportConversations = async () => {
    if (!token) return;
    setIsExporting("conversations");
    try {
      const conversations = await conversationsApi.list(token);
      const blob = new Blob([JSON.stringify(conversations, null, 2)], { type: "application/json" });
      downloadBlob(blob, "conversations-export.json");
    } catch (error) {
      console.error("Export failed:", error);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportMemories = async () => {
    if (!token) return;
    setIsExporting("memories");
    try {
      const memories = await memoryApi.search(token, "", 1000);
      const blob = new Blob([JSON.stringify(memories, null, 2)], { type: "application/json" });
      downloadBlob(blob, "memories-export.json");
    } catch (error) {
      console.error("Export failed:", error);
    } finally {
      setIsExporting(null);
    }
  };

  const handleExportPreferences = () => {
    const prefs = usePreferencesStore.getState();
    const { setTheme: _, setAccentColor: _a, setFontSize: _b, ...exportData } = prefs as any;
    const data = {
      theme: prefs.theme,
      accentColor: prefs.accentColor,
      fontSize: prefs.fontSize,
      compactMode: prefs.compactMode,
      defaultModelTier: prefs.defaultModelTier,
      maxIterations: prefs.maxIterations,
      autoApprovePlans: prefs.autoApprovePlans,
      preferredAgent: prefs.preferredAgent,
      reducedMotion: prefs.reducedMotion,
      highContrast: prefs.highContrast,
      screenReaderHints: prefs.screenReaderHints,
      shortcuts: prefs.shortcuts,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    downloadBlob(blob, "preferences-export.json");
  };

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold">Settings</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Manage your account, appearance, and preferences
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="w-full sm:w-auto flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="profile" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <User className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Profile</span>
          </TabsTrigger>
          <TabsTrigger value="appearance" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Palette className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Appearance</span>
          </TabsTrigger>
          <TabsTrigger value="shortcuts" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Keyboard className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Shortcuts</span>
          </TabsTrigger>
          <TabsTrigger value="agents" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Agents</span>
          </TabsTrigger>
          <TabsTrigger value="security" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Shield className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Security</span>
          </TabsTrigger>
          <TabsTrigger value="notifications" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Bell className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Alerts</span>
          </TabsTrigger>
          <TabsTrigger value="data" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Database className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">Data</span>
          </TabsTrigger>
          <TabsTrigger value="accessibility" className="flex-1 sm:flex-initial gap-1.5 text-xs sm:text-sm px-2 sm:px-3">
            <Accessibility className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span className="hidden sm:inline">A11y</span>
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update your account profile information
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {profileMessage && (
                <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                  profileMessage.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
                }`}>
                  {profileMessage.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                  {profileMessage.text}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={user?.email || ""} disabled className="bg-muted" />
                <p className="text-xs text-muted-foreground">Email cannot be changed</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="displayName">Display Name</Label>
                <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Your name" />
              </div>

              <div className="space-y-2">
                <Label>Role</Label>
                <Input value={user?.role || "user"} disabled className="bg-muted capitalize" />
              </div>

              <Separator className="my-4" />

              <Button onClick={handleSaveProfile} disabled={isSavingProfile}>
                {isSavingProfile ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</> : "Save Changes"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Appearance Tab */}
        <TabsContent value="appearance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Theme</CardTitle>
              <CardDescription>Choose your preferred color scheme</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                {([
                  { value: "light", icon: Sun, label: "Light" },
                  { value: "dark", icon: Moon, label: "Dark" },
                  { value: "system", icon: Monitor, label: "System" },
                ] as const).map(({ value, icon: Icon, label }) => (
                  <button
                    key={value}
                    onClick={() => setTheme(value)}
                    className={cn(
                      "flex flex-col items-center gap-2 rounded-lg border p-4 transition-all hover:bg-muted",
                      theme === value && "border-primary bg-primary/5 ring-1 ring-primary"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="text-sm font-medium">{label}</span>
                    {theme === value && <Check className="h-3 w-3 text-primary" />}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Accent Color</CardTitle>
              <CardDescription>Choose your accent color for UI elements</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {ACCENT_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setAccentColor(color)}
                    className={cn(
                      "h-8 w-8 rounded-full transition-all hover:scale-110",
                      accentColor === color && "ring-2 ring-offset-2 ring-offset-background ring-foreground scale-110"
                    )}
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Font Size</CardTitle>
              <CardDescription>Adjust the base font size for the interface</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Size: {fontSize}px</span>
                <Button variant="ghost" size="sm" onClick={() => setFontSize(14)} className="h-7 text-xs">
                  Reset
                </Button>
              </div>
              <Slider
                value={[fontSize]}
                onValueChange={([val]) => setFontSize(val)}
                min={12}
                max={20}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>12px</span>
                <span>16px</span>
                <span>20px</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Layout</CardTitle>
              <CardDescription>Adjust the UI density</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Compact Mode</Label>
                  <p className="text-sm text-muted-foreground">
                    Reduce padding and spacing throughout the UI
                  </p>
                </div>
                <Switch checked={compactMode} onCheckedChange={setCompactMode} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Shortcuts Tab */}
        <TabsContent value="shortcuts">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Keyboard Shortcuts</CardTitle>
                  <CardDescription>Click a shortcut to rebind it. Press Escape to cancel.</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={resetShortcuts}>
                  <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                  Reset All
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.id}
                    className={cn(
                      "flex items-center justify-between p-3 rounded-md transition-colors",
                      rebindingId === shortcut.id ? "bg-primary/10 border border-primary/30" : "hover:bg-muted"
                    )}
                  >
                    <span className="text-sm font-medium">{shortcut.label}</span>
                    <button
                      onClick={() => setRebindingId(rebindingId === shortcut.id ? null : shortcut.id)}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-xs font-mono transition-all",
                        rebindingId === shortcut.id
                          ? "bg-primary text-primary-foreground animate-pulse"
                          : "bg-muted hover:bg-muted/80 border"
                      )}
                    >
                      {rebindingId === shortcut.id ? "Press keys..." : formatShortcut(shortcut)}
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Agent Preferences Tab */}
        <TabsContent value="agents">
          <Card>
            <CardHeader>
              <CardTitle>Agent Preferences</CardTitle>
              <CardDescription>Configure default behavior for AI agents</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label>Default Model Tier</Label>
                <Select value={defaultModelTier} onValueChange={(v) => setDefaultModelTier(v as any)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard">Standard (Fast, cost-effective)</SelectItem>
                    <SelectItem value="advanced">Advanced (Balanced)</SelectItem>
                    <SelectItem value="reasoning">Reasoning (Complex tasks)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  The model tier used for new conversations by default
                </p>
              </div>

              <Separator />

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Max Iterations</Label>
                  <Badge variant="secondary" className="font-mono">{maxIterations}</Badge>
                </div>
                <Slider
                  value={[maxIterations]}
                  onValueChange={([val]) => setMaxIterations(val)}
                  min={5}
                  max={100}
                  step={5}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground">
                  Maximum number of iterations an agent can take per task
                </p>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Auto-Approve Plans</Label>
                  <p className="text-sm text-muted-foreground">
                    Automatically approve agent plans without manual review
                  </p>
                </div>
                <Switch checked={autoApprovePlans} onCheckedChange={setAutoApprovePlans} />
              </div>

              <Separator />

              <div className="space-y-2">
                <Label>Preferred Agent</Label>
                <Select value={preferredAgent} onValueChange={setPreferredAgent}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto (System decides)</SelectItem>
                    <SelectItem value="coder">Coder</SelectItem>
                    <SelectItem value="researcher">Researcher</SelectItem>
                    <SelectItem value="planner">Planner</SelectItem>
                    <SelectItem value="reviewer">Reviewer</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  The agent type used for new conversations
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>Update your account password</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {passwordMessage && (
                <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                  passwordMessage.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
                }`}>
                  {passwordMessage.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                  {passwordMessage.text}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="currentPassword">Current Password</Label>
                <Input id="currentPassword" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">New Password</Label>
                <Input id="newPassword" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm New Password</Label>
                <Input id="confirmPassword" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
              </div>

              <Separator className="my-4" />

              <Button onClick={handleUpdatePassword} disabled={isSavingPassword || !currentPassword || !newPassword || !confirmPassword}>
                {isSavingPassword ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Updating...</> : "Update Password"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>Managed through AWS Secrets Manager</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { name: "Anthropic API", prefix: "sk-ant-api03-" },
                { name: "OpenAI API", prefix: "sk-proj-" },
                { name: "Cloudflare API", prefix: "" },
              ].map((api) => (
                <div key={api.name} className="rounded-lg border p-3 bg-muted/50">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{api.name}</p>
                    <Badge variant="outline" className="text-green-500 border-green-500/30 text-[10px]">Connected</Badge>
                  </div>
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Contact your administrator to update API keys.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BellRing className="h-5 w-5" />
                Push Notifications
              </CardTitle>
              <CardDescription>Receive notifications even when the browser is closed</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {pushMessage && (
                <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                  pushMessage.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
                }`}>
                  {pushMessage.type === "success" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                  {pushMessage.text}
                </div>
              )}

              {pushError && (
                <div className="flex items-center gap-2 rounded-md p-3 text-sm bg-destructive/15 text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {pushError.message}
                </div>
              )}

              {!isSupported ? (
                <div className="rounded-lg border p-4 bg-muted/50">
                  <p className="text-sm text-muted-foreground">
                    Push notifications are not supported in this browser.
                  </p>
                </div>
              ) : permission === "denied" ? (
                <div className="rounded-lg border p-4 bg-destructive/10">
                  <p className="text-sm text-destructive">
                    Push notifications have been blocked. Allow them in your browser settings.
                  </p>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="flex items-center gap-2">
                      {isSubscribed ? (
                        <><BellRing className="h-4 w-4 text-green-500" /> Push notifications enabled</>
                      ) : (
                        <><BellOff className="h-4 w-4 text-muted-foreground" /> Push notifications disabled</>
                      )}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {isSubscribed ? "You'll receive push notifications for important events" : "Enable to receive notifications for agent events"}
                    </p>
                  </div>
                  <Button
                    variant={isSubscribed ? "outline" : "default"}
                    onClick={isSubscribed ? handlePushUnsubscribe : handlePushSubscribe}
                    disabled={isPushLoading}
                  >
                    {isPushLoading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Loading...</> : isSubscribed ? "Disable" : "Enable"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notification Types</CardTitle>
              <CardDescription>Choose which events you want to be notified about</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {([
                  { key: "task_completions", label: "Task Completions", desc: "Notify when agents complete tasks" },
                  { key: "agent_errors", label: "Agent Errors", desc: "Notify when agents encounter errors" },
                  { key: "ssl_expiration", label: "SSL Expiration", desc: "Notify before SSL certificates expire" },
                  { key: "system_updates", label: "System Updates", desc: "Notify about system updates and maintenance" },
                ] as const).map(({ key, label, desc }, i) => (
                  <div key={key}>
                    {i > 0 && <Separator className="mb-4" />}
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>{label}</Label>
                        <p className="text-sm text-muted-foreground">{desc}</p>
                      </div>
                      <Switch
                        checked={notifications[key]}
                        onCheckedChange={(checked) => handleNotificationChange(key, checked)}
                        disabled={isSavingNotifications}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Data Tab */}
        <TabsContent value="data">
          <Card>
            <CardHeader>
              <CardTitle>Export Data</CardTitle>
              <CardDescription>Download your data in JSON format</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <p className="text-sm font-medium">Conversations</p>
                  <p className="text-xs text-muted-foreground">All conversations and messages</p>
                </div>
                <Button variant="outline" size="sm" onClick={handleExportConversations} disabled={isExporting === "conversations"}>
                  {isExporting === "conversations" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5 mr-1.5" />}
                  Export
                </Button>
              </div>

              <div className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <p className="text-sm font-medium">Memories</p>
                  <p className="text-xs text-muted-foreground">All stored knowledge and learnings</p>
                </div>
                <Button variant="outline" size="sm" onClick={handleExportMemories} disabled={isExporting === "memories"}>
                  {isExporting === "memories" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5 mr-1.5" />}
                  Export
                </Button>
              </div>

              <div className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <p className="text-sm font-medium">Preferences</p>
                  <p className="text-xs text-muted-foreground">Theme, shortcuts, and agent preferences</p>
                </div>
                <Button variant="outline" size="sm" onClick={handleExportPreferences}>
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Export
                </Button>
              </div>

              <Separator className="my-4" />

              <div className="rounded-lg border border-destructive/30 p-4 bg-destructive/5">
                <h4 className="text-sm font-medium text-destructive mb-1">Danger Zone</h4>
                <p className="text-xs text-muted-foreground mb-3">
                  Account deletion is permanent and cannot be undone. Contact an administrator to delete your account.
                </p>
                <Button variant="destructive" size="sm" disabled>
                  Delete Account
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Accessibility Tab */}
        <TabsContent value="accessibility">
          <Card>
            <CardHeader>
              <CardTitle>Accessibility</CardTitle>
              <CardDescription>Configure accessibility preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Reduced Motion</Label>
                  <p className="text-sm text-muted-foreground">
                    Minimize animations and transitions throughout the UI
                  </p>
                </div>
                <Switch checked={reducedMotion} onCheckedChange={setReducedMotion} />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>High Contrast</Label>
                  <p className="text-sm text-muted-foreground">
                    Increase contrast between foreground and background elements
                  </p>
                </div>
                <Switch checked={highContrast} onCheckedChange={setHighContrast} />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Screen Reader Hints</Label>
                  <p className="text-sm text-muted-foreground">
                    Add additional ARIA labels and descriptions for screen readers
                  </p>
                </div>
                <Switch checked={screenReaderHints} onCheckedChange={setScreenReaderHints} />
              </div>

              <Separator />

              <div className="pt-2">
                <Button variant="outline" onClick={resetAll}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset All Preferences
                </Button>
                <p className="text-xs text-muted-foreground mt-2">
                  This will reset all appearance, shortcut, and accessibility settings to defaults.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
