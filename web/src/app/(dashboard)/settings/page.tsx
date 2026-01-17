"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { authApi, settingsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { User, Key, Bell, Shield, Loader2, CheckCircle, AlertCircle } from "lucide-react";

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
        .catch(() => {
          // Use default settings if fetch fails
        });
    }
  }, [token]);

  const handleSaveProfile = async () => {
    if (!token) return;
    setIsSavingProfile(true);
    setProfileMessage(null);

    try {
      await authApi.updateProfile(token, { display_name: displayName });
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
      await authApi.updatePassword(token, {
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
      // Revert on error
      setNotifications(notifications);
    } finally {
      setIsSavingNotifications(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and preferences
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-2">
            <Shield className="h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="h-4 w-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="api" className="gap-2">
            <Key className="h-4 w-4" />
            API Keys
          </TabsTrigger>
        </TabsList>

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
                  {profileMessage.type === "success" ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  {profileMessage.text}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={user?.email || ""}
                  disabled
                  className="bg-muted"
                />
                <p className="text-xs text-muted-foreground">
                  Email cannot be changed
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="displayName">Display Name</Label>
                <Input
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                />
              </div>

              <div className="space-y-2">
                <Label>Role</Label>
                <Input value={user?.role || "user"} disabled className="bg-muted capitalize" />
              </div>

              <Separator className="my-4" />

              <Button onClick={handleSaveProfile} disabled={isSavingProfile}>
                {isSavingProfile ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Changes"
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
              <CardDescription>
                Manage your password and security preferences
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {passwordMessage && (
                <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                  passwordMessage.type === "success" ? "bg-green-500/15 text-green-500" : "bg-destructive/15 text-destructive"
                }`}>
                  {passwordMessage.type === "success" ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  {passwordMessage.text}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="currentPassword">Current Password</Label>
                <Input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">New Password</Label>
                <Input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm New Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              <Separator className="my-4" />

              <Button
                onClick={handleUpdatePassword}
                disabled={isSavingPassword || !currentPassword || !newPassword || !confirmPassword}
              >
                {isSavingPassword ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Updating...
                  </>
                ) : (
                  "Update Password"
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>
                Configure how you receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Task Completions</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify when agents complete tasks
                    </p>
                  </div>
                  <Switch
                    checked={notifications.task_completions}
                    onCheckedChange={(checked) => handleNotificationChange("task_completions", checked)}
                    disabled={isSavingNotifications}
                  />
                </div>

                <Separator />

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Agent Errors</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify when agents encounter errors
                    </p>
                  </div>
                  <Switch
                    checked={notifications.agent_errors}
                    onCheckedChange={(checked) => handleNotificationChange("agent_errors", checked)}
                    disabled={isSavingNotifications}
                  />
                </div>

                <Separator />

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>SSL Expiration</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify before SSL certificates expire
                    </p>
                  </div>
                  <Switch
                    checked={notifications.ssl_expiration}
                    onCheckedChange={(checked) => handleNotificationChange("ssl_expiration", checked)}
                    disabled={isSavingNotifications}
                  />
                </div>

                <Separator />

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>System Updates</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify about system updates and maintenance
                    </p>
                  </div>
                  <Switch
                    checked={notifications.system_updates}
                    onCheckedChange={(checked) => handleNotificationChange("system_updates", checked)}
                    disabled={isSavingNotifications}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api">
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>
                Manage API keys for external integrations
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border p-4 bg-muted/50">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium">Anthropic API</p>
                  <span className="text-xs text-green-500">Connected</span>
                </div>
                <Input
                  value="sk-ant-api03-••••••••••••••••"
                  disabled
                  className="font-mono text-sm"
                />
              </div>

              <div className="rounded-lg border p-4 bg-muted/50">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium">OpenAI API</p>
                  <span className="text-xs text-green-500">Connected</span>
                </div>
                <Input
                  value="sk-proj-••••••••••••••••"
                  disabled
                  className="font-mono text-sm"
                />
              </div>

              <div className="rounded-lg border p-4 bg-muted/50">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium">Cloudflare API</p>
                  <span className="text-xs text-green-500">Connected</span>
                </div>
                <Input
                  value="••••••••••••••••••••••••"
                  disabled
                  className="font-mono text-sm"
                />
              </div>

              <p className="text-sm text-muted-foreground">
                API keys are managed securely through AWS Secrets Manager. Contact
                your administrator to update API keys.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
