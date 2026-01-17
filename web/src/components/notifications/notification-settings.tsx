"use client";

import * as React from "react";
import { Bell, BellOff, Smartphone, Volume2, VolumeX, Vibrate } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  usePushNotifications,
  isIOSDevice,
  isIOSPWA,
} from "@/hooks/usePushNotifications";
import {
  getNotificationPreferences,
  setNotificationPreferences,
  type NotificationPreferences,
  registerPushSubscription,
  unregisterPushSubscription,
} from "@/lib/notifications";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "@/hooks/useToast";
import { cn } from "@/lib/utils";

export function NotificationSettings() {
  const { token } = useAuthStore();
  const {
    permission,
    isSupported,
    isSubscribed,
    isLoading,
    subscribe,
    unsubscribe,
  } = usePushNotifications();

  const [preferences, setPreferences] = React.useState<NotificationPreferences>(
    getNotificationPreferences()
  );

  const isIOS = isIOSDevice();
  const isIOSStandalone = isIOSPWA();

  const handlePreferenceChange = (
    key: keyof NotificationPreferences,
    value: boolean
  ) => {
    const updated = { ...preferences, [key]: value };
    setPreferences(updated);
    setNotificationPreferences(updated);
  };

  const handleEnableNotifications = async () => {
    const subscription = await subscribe();

    if (subscription && token) {
      const registered = await registerPushSubscription(token, subscription);
      if (registered) {
        toast({
          title: "Notifications Enabled",
          description: "You'll now receive push notifications from Wyld Fyre.",
        });
        handlePreferenceChange("enabled", true);
      } else {
        toast({
          title: "Registration Failed",
          description: "Failed to register with the server. Try again later.",
          variant: "destructive",
        });
      }
    }
  };

  const handleDisableNotifications = async () => {
    const success = await unsubscribe();

    if (success && token) {
      await unregisterPushSubscription(token, "");
      toast({
        title: "Notifications Disabled",
        description: "You won't receive push notifications anymore.",
      });
      handlePreferenceChange("enabled", false);
    }
  };

  const getPermissionBadge = () => {
    switch (permission) {
      case "granted":
        return <Badge className="bg-emerald-500">Allowed</Badge>;
      case "denied":
        return <Badge variant="destructive">Blocked</Badge>;
      case "unsupported":
        return <Badge variant="secondary">Not Supported</Badge>;
      default:
        return <Badge variant="outline">Not Set</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Push Notifications
              </CardTitle>
              <CardDescription>
                Receive notifications for messages, agent updates, and task
                completions
              </CardDescription>
            </div>
            {getPermissionBadge()}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* iOS Warning */}
          {isIOS && (
            <div
              className={cn(
                "rounded-lg p-4 text-sm",
                isIOSStandalone
                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                  : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
              )}
            >
              <div className="flex items-start gap-3">
                <Smartphone className="h-5 w-5 shrink-0 mt-0.5" />
                <div>
                  {isIOSStandalone ? (
                    <>
                      <p className="font-medium">Running as iOS App</p>
                      <p className="mt-1 opacity-80">
                        Push notifications have limited support on iOS PWAs. You'll
                        receive notifications when the app is open.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="font-medium">Add to Home Screen</p>
                      <p className="mt-1 opacity-80">
                        For the best notification experience on iOS, add Wyld Fyre
                        to your Home Screen using Safari's Share menu.
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Main Enable/Disable Button */}
          {isSupported && permission !== "denied" && (
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Enable Push Notifications</p>
                <p className="text-sm text-muted-foreground">
                  {isSubscribed
                    ? "You're subscribed to push notifications"
                    : "Allow Wyld Fyre to send you notifications"}
                </p>
              </div>
              <Button
                variant={isSubscribed ? "outline" : "default"}
                onClick={
                  isSubscribed
                    ? handleDisableNotifications
                    : handleEnableNotifications
                }
                disabled={isLoading}
              >
                {isLoading ? (
                  "Processing..."
                ) : isSubscribed ? (
                  <>
                    <BellOff className="mr-2 h-4 w-4" />
                    Disable
                  </>
                ) : (
                  <>
                    <Bell className="mr-2 h-4 w-4" />
                    Enable
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Permission Denied Warning */}
          {permission === "denied" && (
            <div className="rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
              <p className="font-medium">Notifications Blocked</p>
              <p className="mt-1">
                You've blocked notifications for this site. To enable them, update
                your browser settings or site permissions.
              </p>
            </div>
          )}

          {/* Not Supported Warning */}
          {!isSupported && (
            <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
              <p className="font-medium">Not Supported</p>
              <p className="mt-1">
                Push notifications are not supported in your browser. Try using a
                modern browser like Chrome, Firefox, or Safari.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>Notification Types</CardTitle>
          <CardDescription>
            Choose which types of notifications you want to receive
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="notif-messages" className="flex flex-col gap-1">
              <span>Messages</span>
              <span className="text-sm font-normal text-muted-foreground">
                New messages from Wyld and other agents
              </span>
            </Label>
            <Switch
              id="notif-messages"
              checked={preferences.messages}
              onCheckedChange={(checked) =>
                handlePreferenceChange("messages", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <Label htmlFor="notif-agents" className="flex flex-col gap-1">
              <span>Agent Status</span>
              <span className="text-sm font-normal text-muted-foreground">
                When agents come online, go offline, or encounter errors
              </span>
            </Label>
            <Switch
              id="notif-agents"
              checked={preferences.agentStatus}
              onCheckedChange={(checked) =>
                handlePreferenceChange("agentStatus", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <Label htmlFor="notif-tasks" className="flex flex-col gap-1">
              <span>Task Updates</span>
              <span className="text-sm font-normal text-muted-foreground">
                When tasks complete or fail
              </span>
            </Label>
            <Switch
              id="notif-tasks"
              checked={preferences.taskUpdates}
              onCheckedChange={(checked) =>
                handlePreferenceChange("taskUpdates", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <Label htmlFor="notif-errors" className="flex flex-col gap-1">
              <span>Errors</span>
              <span className="text-sm font-normal text-muted-foreground">
                Important error notifications
              </span>
            </Label>
            <Switch
              id="notif-errors"
              checked={preferences.errors}
              onCheckedChange={(checked) =>
                handlePreferenceChange("errors", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>
        </CardContent>
      </Card>

      {/* Sound & Vibration */}
      <Card>
        <CardHeader>
          <CardTitle>Sound & Vibration</CardTitle>
          <CardDescription>
            Control how notifications alert you
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="notif-sound" className="flex items-center gap-2">
              {preferences.sound ? (
                <Volume2 className="h-4 w-4" />
              ) : (
                <VolumeX className="h-4 w-4" />
              )}
              <span>Sound</span>
            </Label>
            <Switch
              id="notif-sound"
              checked={preferences.sound}
              onCheckedChange={(checked) =>
                handlePreferenceChange("sound", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <Label htmlFor="notif-vibrate" className="flex items-center gap-2">
              <Vibrate className="h-4 w-4" />
              <span>Vibration</span>
            </Label>
            <Switch
              id="notif-vibrate"
              checked={preferences.vibrate}
              onCheckedChange={(checked) =>
                handlePreferenceChange("vibrate", checked)
              }
              disabled={!preferences.enabled}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
