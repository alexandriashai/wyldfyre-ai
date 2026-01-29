"use client";

import { useBrowserStore, BrowserPermissions, VIEWPORT_PRESETS, ViewportPreset } from "@/stores/browser-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Camera,
  MapPin,
  Mic,
  Bell,
  Clipboard,
  Music,
  Settings,
  Monitor,
  Smartphone,
  Tablet,
} from "lucide-react";

interface BrowserSettingsProps {
  projectId: string;
}

const permissionConfig: {
  key: keyof BrowserPermissions;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    key: "geolocation",
    label: "Location",
    description: "Allow access to device location",
    icon: MapPin,
  },
  {
    key: "camera",
    label: "Camera",
    description: "Allow access to video camera",
    icon: Camera,
  },
  {
    key: "microphone",
    label: "Microphone",
    description: "Allow access to microphone for audio",
    icon: Mic,
  },
  {
    key: "notifications",
    label: "Notifications",
    description: "Allow browser notifications",
    icon: Bell,
  },
  {
    key: "clipboard",
    label: "Clipboard",
    description: "Allow read/write to clipboard",
    icon: Clipboard,
  },
  {
    key: "midi",
    label: "MIDI Devices",
    description: "Allow access to MIDI instruments",
    icon: Music,
  },
];

export function BrowserSettings({ projectId }: BrowserSettingsProps) {
  const { permissions, setPermission, viewports, setViewportPreset, getViewportPreset } = useBrowserStore();
  const projectPermissions = permissions[projectId] || {
    geolocation: false,
    camera: false,
    microphone: false,
    notifications: false,
    clipboard: false,
    midi: false,
  };
  const currentViewport = getViewportPreset(projectId);

  const mobilePresets = VIEWPORT_PRESETS.filter((p) => p.category === "mobile");
  const tabletPresets = VIEWPORT_PRESETS.filter((p) => p.category === "tablet");
  const desktopPresets = VIEWPORT_PRESETS.filter((p) => p.category === "desktop");

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b flex items-center gap-2">
        <Settings className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Browser Settings</span>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-4">
          {/* Viewport Section */}
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Viewport Size
            </h4>
            <p className="text-xs text-muted-foreground mb-3">
              Select a device viewport for browser testing. Agents can also specify viewport when running tasks.
            </p>
            <Select
              value={currentViewport.id}
              onValueChange={(value) => setViewportPreset(projectId, value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue>
                  <div className="flex items-center gap-2">
                    {currentViewport.category === "mobile" && <Smartphone className="h-4 w-4" />}
                    {currentViewport.category === "tablet" && <Tablet className="h-4 w-4" />}
                    {currentViewport.category === "desktop" && <Monitor className="h-4 w-4" />}
                    <span>{currentViewport.name}</span>
                    <span className="text-muted-foreground text-xs">
                      ({currentViewport.width}x{currentViewport.height})
                    </span>
                  </div>
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel className="flex items-center gap-2">
                    <Smartphone className="h-3.5 w-3.5" /> Mobile
                  </SelectLabel>
                  {mobilePresets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id}>
                      <div className="flex items-center justify-between w-full gap-4">
                        <span>{preset.name}</span>
                        <span className="text-muted-foreground text-xs">
                          {preset.width}x{preset.height}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel className="flex items-center gap-2">
                    <Tablet className="h-3.5 w-3.5" /> Tablet
                  </SelectLabel>
                  {tabletPresets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id}>
                      <div className="flex items-center justify-between w-full gap-4">
                        <span>{preset.name}</span>
                        <span className="text-muted-foreground text-xs">
                          {preset.width}x{preset.height}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel className="flex items-center gap-2">
                    <Monitor className="h-3.5 w-3.5" /> Desktop
                  </SelectLabel>
                  {desktopPresets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id}>
                      <div className="flex items-center justify-between w-full gap-4">
                        <span>{preset.name}</span>
                        <span className="text-muted-foreground text-xs">
                          {preset.width}x{preset.height}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          {/* Permissions Section */}
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Permissions
            </h4>
            <p className="text-xs text-muted-foreground mb-4">
              Grant these permissions to the browser for testing features that require device access.
            </p>
            <div className="space-y-3">
              {permissionConfig.map(({ key, label, description, icon: Icon }) => (
                <div
                  key={key}
                  className="flex items-center justify-between p-2 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-md bg-background">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <Label
                        htmlFor={`perm-${key}`}
                        className="text-sm font-medium cursor-pointer"
                      >
                        {label}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {description}
                      </p>
                    </div>
                  </div>
                  <Switch
                    id={`perm-${key}`}
                    checked={projectPermissions[key]}
                    onCheckedChange={(checked) =>
                      setPermission(projectId, key, checked)
                    }
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Info Note */}
          <div className="p-3 rounded-lg border border-amber-500/20 bg-amber-500/5">
            <p className="text-xs text-amber-600 dark:text-amber-400">
              <strong>Note:</strong> Permissions are applied when a new browser session starts.
              If the browser is already running, restart the session to apply changes.
            </p>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
